from langgraph.graph import StateGraph, END
from typing import Dict, Any, List
from datetime import datetime
import uuid
import os

from models.state import TravelAgentState, ConversationMessage, CustomerInfo, TravelBooking
from utils.graph_utils import create_initial_state, add_message_to_state, update_state_field






class TravelMultiAgentGraph:
    """Main graph class for the travel customer management multi-agent system"""

    def __init__(self, openai_api_key: str = None):
        if openai_api_key is None:
            openai_api_key = os.getenv("OPENAI_API_KEY")

        if not openai_api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable or pass it directly.")

        # Import agents here to avoid circular imports
        from agents import RouterAgent, BookingAgent, ComplaintAgent, InformationAgent

        # Initialize agents
        self.router_agent = RouterAgent(openai_api_key)
        self.booking_agent = BookingAgent(openai_api_key)
        self.complaint_agent = ComplaintAgent(openai_api_key)
        self.information_agent = InformationAgent(openai_api_key)

        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        # Create the state graph
        workflow = StateGraph(TravelAgentState)

        # Add nodes (agents will be added here)
        workflow.add_node("router", self._router_agent)
        workflow.add_node("booking_agent", self._booking_agent)
        workflow.add_node("complaint_agent", self._complaint_agent)
        workflow.add_node("information_agent", self._information_agent)
        workflow.add_node("final_response", self._final_response_agent)

        # Add edges
        workflow.set_entry_point("router")

        # Router decides which agent to use
        workflow.add_conditional_edges(
            "router",
            self._route_to_agent,
            {
                "booking": "booking_agent",
                "complaint": "complaint_agent",
                "information": "information_agent",
                "complete": "final_response"
            }
        )

        # Each agent can go back to router or complete
        workflow.add_conditional_edges(
            "booking_agent",
            self._agent_continue_or_complete,
            {
                "continue": "router",
                "complete": "final_response"
            }
        )

        workflow.add_conditional_edges(
            "complaint_agent",
            self._agent_continue_or_complete,
            {
                "continue": "router",
                "complete": "final_response"
            }
        )

        workflow.add_conditional_edges(
            "information_agent",
            self._agent_continue_or_complete,
            {
                "continue": "router",
                "complete": "final_response"
            }
        )

        workflow.add_edge("final_response", END)

        return workflow.compile()

    def _router_agent(self, state: TravelAgentState) -> TravelAgentState:
        """Router agent that determines which specialized agent to use"""
        return self.router_agent.route_query(state)

    def _booking_agent(self, state: TravelAgentState) -> TravelAgentState:
        """Booking agent for handling reservations"""
        return self.booking_agent.process_booking_request(state)

    def _complaint_agent(self, state: TravelAgentState) -> TravelAgentState:
        """Complaint agent for handling customer issues"""
        return self.complaint_agent.handle_complaint(state)

    def _information_agent(self, state: TravelAgentState) -> TravelAgentState:
        """Information agent for providing travel info"""
        return self.information_agent.provide_information(state)

    def _final_response_agent(self, state: TravelAgentState) -> TravelAgentState:
        """Final response compilation"""
        # Compile all agent responses into a final answer
        responses = [msg["content"] for msg in state["messages"] if msg["role"] == "agent"]

        final_response = f"Final Response: {' '.join(responses[-3:])}"  # Last 3 responses

        return update_state_field(
            add_message_to_state(state, "assistant", final_response, "final_response"),
            "is_complete",
            True
        )

    def _route_to_agent(self, state: TravelAgentState) -> str:
        """Determine which agent to route to based on query analysis"""
        query = state["current_query"].lower()

        # Simple keyword-based routing (will be improved with LLM)
        if any(word in query for word in ["book", "reserve", "booking", "flight", "hotel"]):
            return "booking"
        elif any(word in query for word in ["complaint", "problem", "issue", "cancel", "refund"]):
            return "complaint"
        elif any(word in query for word in ["information", "recommend", "suggest", "where", "how"]):
            return "information"
        else:
            return "complete"  # Default to complete if unsure

    def _agent_continue_or_complete(self, state: TravelAgentState) -> str:
        """Determine if agent should continue processing or complete"""
        # For now, always complete after one agent interaction
        # This can be made more sophisticated based on agent responses
        return "complete"

    def process_query(self, query: str, session_id: str = None) -> TravelAgentState:
        """Process a customer query through the multi-agent system"""
        initial_state = create_initial_state(query, session_id)

        # Add the user message
        state_with_user_msg = add_message_to_state(initial_state, "user", query)

        # Run the graph
        final_state = self.graph.invoke(state_with_user_msg)

        return final_state