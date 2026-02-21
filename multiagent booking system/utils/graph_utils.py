"""
Utility functions for graph operations and state management
"""

from typing import Any, Dict
from datetime import datetime
import uuid

from models.state import TravelAgentState, ConversationMessage, CustomerInfo, TravelBooking


def create_initial_state(query: str, session_id: str = None) -> TravelAgentState:
    """Create initial state for a new conversation"""
    if session_id is None:
        session_id = str(uuid.uuid4())

    return TravelAgentState(
        customer_info=CustomerInfo(
            customer_id=None,
            name=None,
            email=None,
            phone=None,
            preferences={}
        ),
        messages=[],
        current_query=query,
        query_type=None,
        current_agent=None,
        agent_responses={},
        booking_info=TravelBooking(
            booking_id=None,
            destination=None,
            departure_date=None,
            return_date=None,
            travelers=1,
            booking_status="pending",
            price=None
        ),
        is_complete=False,
        error_message=None,
        session_id=session_id,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )


def add_message_to_state(state: TravelAgentState, role: str, content: str, agent_name: str = None) -> TravelAgentState:
    """Add a message to the conversation state"""
    new_message = ConversationMessage(
        role=role,
        content=content,
        timestamp=datetime.now(),
        agent_name=agent_name
    )

    updated_state = state.copy()
    updated_state["messages"] = state["messages"] + [new_message]
    updated_state["updated_at"] = datetime.now()

    return updated_state


def update_state_field(state: TravelAgentState, field: str, value: Any) -> TravelAgentState:
    """Update a specific field in the state"""
    updated_state = state.copy()
    updated_state[field] = value
    updated_state["updated_at"] = datetime.now()
    return updated_state