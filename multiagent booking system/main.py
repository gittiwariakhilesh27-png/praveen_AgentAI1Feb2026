#!/usr/bin/env python3
"""
Travel Customer Management Multi-Agent System
Main application entry point with FastAPI interface
"""

import os
import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
import asyncio
from dotenv import load_dotenv

from graph import TravelMultiAgentGraph
from models.state import TravelAgentState, ConversationMessage

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Travel Customer Management System",
    description="Multi-agent system for handling travel customer queries using LangGraph",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the multi-agent graph
try:
    graph = TravelMultiAgentGraph()
except ValueError as e:
    print(f"Error initializing graph: {e}")
    print("Please set your OPENAI_API_KEY environment variable")
    exit(1)


# Pydantic models for API requests/responses
class ChatRequest(BaseModel):
    message: str = Field(..., description="Customer's message or query")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")


class ChatResponse(BaseModel):
    response: str = Field(..., description="Agent's response")
    session_id: str = Field(..., description="Session ID")
    agent_used: Optional[str] = Field(None, description="Which agent handled the request")
    is_complete: bool = Field(..., description="Whether the conversation is complete")
    booking_info: Optional[Dict[str, Any]] = Field(None, description="Current booking information")


class ConversationHistory(BaseModel):
    session_id: str
    messages: List[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class HealthResponse(BaseModel):
    status: str = "healthy"
    timestamp: datetime
    version: str = "1.0.0"


# In-memory storage for conversation sessions (in production, use a database)
conversation_store: Dict[str, TravelAgentState] = {}


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(),
        version="1.0.0"
    )


@app.post("/chat", response_model=ChatResponse)
async def chat_with_agent(request: ChatRequest, background_tasks: BackgroundTasks):
    """Main chat endpoint for customer interactions"""

    try:
        # Get or create session
        session_id = request.session_id
        if not session_id or session_id not in conversation_store:
            session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            conversation_store[session_id] = None

        # Process the query through the multi-agent system
        result_state = graph.process_query(request.message, session_id)

        # Store the updated state
        conversation_store[session_id] = result_state

        # Extract the latest agent response
        agent_messages = [msg for msg in result_state["messages"] if msg["role"] == "agent"]
        latest_response = agent_messages[-1]["content"] if agent_messages else "I'm sorry, I couldn't process your request."

        # Determine which agent was used
        agent_used = result_state.get("current_agent")

        # Clean up old sessions (keep last 100, remove sessions older than 24 hours)
        background_tasks.add_task(cleanup_old_sessions)

        return ChatResponse(
            response=latest_response,
            session_id=session_id,
            agent_used=agent_used,
            is_complete=result_state["is_complete"],
            booking_info=result_state["booking_info"] if result_state["booking_info"]["destination"] else None
        )

    except Exception as e:
        print(f"Error processing chat request: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/conversation/{session_id}", response_model=ConversationHistory)
async def get_conversation_history(session_id: str):
    """Get conversation history for a session"""

    if session_id not in conversation_store:
        raise HTTPException(status_code=404, detail="Session not found")

    state = conversation_store[session_id]

    return ConversationHistory(
        session_id=session_id,
        messages=[
            {
                "role": msg["role"],
                "content": msg["content"],
                "timestamp": msg["timestamp"],
                "agent_name": msg.get("agent_name")
            }
            for msg in state["messages"]
        ],
        created_at=state["created_at"],
        updated_at=state["updated_at"]
    )


@app.delete("/conversation/{session_id}")
async def delete_conversation(session_id: str):
    """Delete a conversation session"""

    if session_id not in conversation_store:
        raise HTTPException(status_code=404, detail="Session not found")

    del conversation_store[session_id]
    return {"message": "Conversation deleted successfully"}


@app.get("/sessions")
async def list_sessions():
    """List all active sessions (for debugging/admin purposes)"""

    sessions = []
    for session_id, state in conversation_store.items():
        if state:
            sessions.append({
                "session_id": session_id,
                "message_count": len(state["messages"]),
                "current_agent": state.get("current_agent"),
                "is_complete": state["is_complete"],
                "created_at": state["created_at"],
                "last_updated": state["updated_at"]
            })

    return {"sessions": sessions, "total": len(sessions)}


async def cleanup_old_sessions():
    """Background task to clean up old conversation sessions"""
    current_time = datetime.now()
    sessions_to_remove = []

    for session_id, state in conversation_store.items():
        if state and (current_time - state["updated_at"]).total_seconds() > 24 * 3600:  # 24 hours
            sessions_to_remove.append(session_id)

    for session_id in sessions_to_remove:
        del conversation_store[session_id]

    # Keep only the most recent 100 sessions
    if len(conversation_store) > 100:
        # Sort by last updated time and keep the newest 100
        sorted_sessions = sorted(
            conversation_store.items(),
            key=lambda x: x[1]["updated_at"] if x[1] else datetime.min,
            reverse=True
        )
        conversation_store.clear()
        for session_id, state in sorted_sessions[:100]:
            conversation_store[session_id] = state


@app.on_event("startup")
async def startup_event():
    """Application startup tasks"""
    print("🚀 Travel Customer Management Multi-Agent System Starting...")
    print("📚 Loading AI models and initializing agents...")
    print("✅ System ready to handle customer queries!")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown tasks"""
    print("🛑 Shutting down Travel Customer Management System...")
    conversation_store.clear()
    print("✅ Shutdown complete")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 9090))
    debug = os.getenv("DEBUG", "False").lower() == "true"

    print(f"🌐 Starting server on port {port}")
    print(f"📖 API documentation available at: http://localhost:{port}/docs")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=debug,
        log_level="info"
    )