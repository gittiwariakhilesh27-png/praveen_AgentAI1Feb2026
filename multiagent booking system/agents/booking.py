from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from datetime import datetime, timedelta

from models.state import TravelAgentState, TravelBooking
from graph import add_message_to_state, update_state_field


class BookingAgent:
    """Booking agent for handling travel reservations and booking requests"""

    def __init__(self, openai_api_key: str):
        self.llm = ChatOpenAI(
            api_key=openai_api_key,
            model="gpt-4o-mini",
            temperature=0.2
        )

        self.booking_analysis_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a travel booking assistant. Extract booking information from the customer's query and provide helpful booking assistance.

Extract the following information if available:
- destination: Where they want to travel
- departure_date: When they want to leave (in YYYY-MM-DD format)
- return_date: When they want to return (in YYYY-MM-DD format)
- travelers: Number of people traveling (default: 1)
- budget: Their budget range if mentioned
- preferences: Any specific preferences (hotel type, flight class, etc.)

Return a JSON response with the extracted information and a helpful response message."""),
            ("user", "{query}")
        ])

        self.booking_confirmation_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are confirming a travel booking. Based on the extracted booking information, create a confirmation message and suggest next steps.

Current booking info: {booking_info}

Provide a professional confirmation response that includes:
- Summary of the booking details
- Next steps for the customer
- Any additional information they might need"""),
            ("user", "Please confirm this booking")
        ])

        self.output_parser = JsonOutputParser()

    def process_booking_request(self, state: TravelAgentState) -> TravelAgentState:
        """Process a booking request and update booking information"""

        try:
            # Extract booking information from the query
            booking_chain = self.booking_analysis_prompt | self.llm | self.output_parser

            booking_result = booking_chain.invoke({
                "query": state["current_query"]
            })

            # Update booking information in state
            updated_booking = self._update_booking_info(state["booking_info"], booking_result)

            state = update_state_field(state, "booking_info", updated_booking)

            # Generate booking response
            response_message = self._generate_booking_response(updated_booking, booking_result)

            return add_message_to_state(
                state,
                "agent",
                response_message,
                "booking_agent"
            )

        except Exception as e:
            print(f"Booking agent error: {e}")
            error_message = "I apologize, but I'm having trouble processing your booking request. Could you please provide more details about your travel plans?"

            return add_message_to_state(
                state,
                "agent",
                error_message,
                "booking_agent"
            )

    def _update_booking_info(self, current_booking: TravelBooking, extracted_info: Dict[str, Any]) -> TravelBooking:
        """Update booking information with extracted data"""
        updated = current_booking.copy()

        # Update fields if they were extracted
        if "destination" in extracted_info and extracted_info["destination"]:
            updated["destination"] = extracted_info["destination"]

        if "departure_date" in extracted_info and extracted_info["departure_date"]:
            updated["departure_date"] = extracted_info["departure_date"]

        if "return_date" in extracted_info and extracted_info["return_date"]:
            updated["return_date"] = extracted_info["return_date"]

        if "travelers" in extracted_info and extracted_info["travelers"]:
            updated["travelers"] = extracted_info["travelers"]

        # Generate booking ID if this is a new booking
        if not updated["booking_id"] and updated["destination"]:
            updated["booking_id"] = f"BK{datetime.now().strftime('%Y%m%d%H%M%S')}"

        return updated

    def _generate_booking_response(self, booking: TravelBooking, extracted_info: Dict[str, Any]) -> str:
        """Generate an appropriate response based on booking information"""

        response_parts = ["Booking Agent: I've analyzed your booking request."]

        # Add booking summary
        if booking["destination"]:
            response_parts.append(f"Destination: {booking['destination']}")

        if booking["departure_date"]:
            response_parts.append(f"Departure: {booking['departure_date']}")

        if booking["return_date"]:
            response_parts.append(f"Return: {booking['return_date']}")

        if booking["travelers"] and booking["travelers"] > 1:
            response_parts.append(f"Travelers: {booking['travelers']}")

        # Add next steps
        if booking["booking_id"]:
            response_parts.append(f"\nBooking ID: {booking['booking_id']}")
            response_parts.append("Your booking is being processed. Would you like me to:")
            response_parts.append("1. Confirm these details and proceed with booking")
            response_parts.append("2. Check availability for these dates")
            response_parts.append("3. Suggest alternative dates or destinations")
            response_parts.append("4. Provide pricing information")
        else:
            response_parts.append("\nI need more information to process your booking. Could you please specify:")
            response_parts.append("- Your destination")
            response_parts.append("- Travel dates")
            response_parts.append("- Number of travelers")

        return " ".join(response_parts)

    def confirm_booking(self, state: TravelAgentState) -> TravelAgentState:
        """Confirm and finalize a booking"""

        try:
            confirmation_chain = self.booking_confirmation_prompt | self.llm

            confirmation_response = confirmation_chain.invoke({
                "booking_info": state["booking_info"]
            })

            # Update booking status
            updated_booking = state["booking_info"].copy()
            updated_booking["booking_status"] = "confirmed"

            state = update_state_field(state, "booking_info", updated_booking)

            return add_message_to_state(
                state,
                "agent",
                f"Booking Agent: {confirmation_response.content}",
                "booking_agent"
            )

        except Exception as e:
            print(f"Booking confirmation error: {e}")
            error_message = "I apologize, but there was an issue confirming your booking. Please contact customer support."

            return add_message_to_state(
                state,
                "agent",
                error_message,
                "booking_agent"
            )