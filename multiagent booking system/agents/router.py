from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from models.state import TravelAgentState
from graph import add_message_to_state, update_state_field


class RouterAgent:
    """Router agent that analyzes customer queries and routes them to appropriate specialized agents"""

    def __init__(self, openai_api_key: str):
        self.llm = ChatOpenAI(
            api_key=openai_api_key,
            model="gpt-4o-mini",
            temperature=0.1
        )

        self.routing_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a travel customer service router. Analyze the customer's query and determine which specialized agent should handle it.

Available agents:
- booking: For travel reservations, flight bookings, hotel bookings, tour packages
- complaint: For customer complaints, cancellations, refunds, service issues, problems
- information: For travel information, recommendations, destination info, how-to questions

Return a JSON response with:
- agent: The chosen agent name ("booking", "complaint", "information")
- confidence: A score from 0-1 indicating confidence in the routing decision
- reasoning: Brief explanation of why this agent was chosen

If the query doesn't clearly fit any category, default to "information"."""),
            ("user", "{query}")
        ])

        self.output_parser = JsonOutputParser()

    def route_query(self, state: TravelAgentState) -> TravelAgentState:
        """Analyze the query and determine which agent should handle it"""

        try:
            # Prepare the routing chain
            routing_chain = self.routing_prompt | self.llm | self.output_parser

            # Get routing decision
            routing_result = routing_chain.invoke({
                "query": state["current_query"]
            })

            agent = routing_result.get("agent", "information")
            confidence = routing_result.get("confidence", 0.5)
            reasoning = routing_result.get("reasoning", "Default routing decision")

            # Update state with routing decision
            state = update_state_field(state, "query_type", agent)
            state = update_state_field(state, "current_agent", agent)

            # Add routing message to conversation
            routing_message = f"Router: I've analyzed your query and determined this is a {agent} request. {reasoning}"

            return add_message_to_state(
                state,
                "agent",
                routing_message,
                "router"
            )

        except Exception as e:
            # Fallback routing based on keywords
            print(f"Router error: {e}. Using fallback routing.")
            return self._fallback_routing(state)

    def _fallback_routing(self, state: TravelAgentState) -> TravelAgentState:
        """Fallback routing using keyword matching when LLM fails"""
        query = state["current_query"].lower()

        # Enhanced keyword-based routing
        booking_keywords = [
            "book", "reserve", "booking", "flight", "hotel", "tour", "package",
            "vacation", "trip", "travel", "reservation", "ticket"
        ]

        complaint_keywords = [
            "complaint", "problem", "issue", "cancel", "refund", "delay",
            "wrong", "mistake", "error", "dissatisfied", "angry", "upset",
            "terrible", "awful", "horrible"
        ]

        if any(keyword in query for keyword in booking_keywords):
            agent = "booking"
            reasoning = "Detected booking-related keywords"
        elif any(keyword in query for keyword in complaint_keywords):
            agent = "complaint"
            reasoning = "Detected complaint-related keywords"
        else:
            agent = "information"
            reasoning = "Defaulting to information agent"

        # Update state
        state = update_state_field(state, "query_type", agent)
        state = update_state_field(state, "current_agent", agent)

        routing_message = f"Router: I've analyzed your query and determined this is a {agent} request. {reasoning}"

        return add_message_to_state(
            state,
            "agent",
            routing_message,
            "router"
        )