from typing import List, Optional, Dict, Any, TypedDict
from datetime import datetime


class CustomerInfo(TypedDict):
    """Customer information structure"""
    customer_id: Optional[str]
    name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    preferences: Dict[str, Any]


class TravelBooking(TypedDict):
    """Travel booking information"""
    booking_id: Optional[str]
    destination: Optional[str]
    departure_date: Optional[str]
    return_date: Optional[str]
    travelers: int
    booking_status: str  # "pending", "confirmed", "cancelled"
    price: Optional[float]


class ConversationMessage(TypedDict):
    """Individual message in conversation"""
    role: str  # "user", "assistant", "agent"
    content: str
    timestamp: datetime
    agent_name: Optional[str]


class TravelAgentState(TypedDict):
    """Main state for the travel customer management system"""
    # Customer information
    customer_info: CustomerInfo

    # Current conversation
    messages: List[ConversationMessage]

    # Current query and context
    current_query: str
    query_type: Optional[str]  # "booking", "complaint", "information", "general"

    # Agent routing
    current_agent: Optional[str]  # "booking", "complaint", "information", "router"
    agent_responses: Dict[str, Any]

    # Travel booking data
    booking_info: TravelBooking

    # System state
    is_complete: bool
    error_message: Optional[str]

    # Metadata
    session_id: str
    created_at: datetime
    updated_at: datetime