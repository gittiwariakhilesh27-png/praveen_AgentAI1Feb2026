from typing import Dict, Any, Optional, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from models.state import TravelAgentState
from graph import add_message_to_state, update_state_field


class ComplaintAgent:
    """Complaint agent for handling customer issues, complaints, and service problems"""

    def __init__(self, openai_api_key: str):
        self.llm = ChatOpenAI(
            api_key=openai_api_key,
            model="gpt-4o-mini",
            temperature=0.1
        )

        self.complaint_analysis_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a customer service specialist handling travel-related complaints. Analyze the customer's complaint and determine:

1. Complaint type: cancellation, refund, delay, service_issue, booking_error, other
2. Severity: low, medium, high, critical
3. Urgency: immediate_action_required, response_within_24h, routine
4. Required actions: refund, rebooking, compensation, escalation, information

Return a JSON response with complaint analysis and recommended solution."""),
            ("user", "{query}")
        ])

        self.solution_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are resolving a customer complaint. Based on the analysis, provide a professional, empathetic response that:

1. Acknowledges the customer's issue
2. Explains what happened (if known)
3. Provides a clear solution or next steps
4. Offers compensation if appropriate
5. Gives contact information for follow-up

Complaint analysis: {analysis}
Customer context: {context}"""),
            ("user", "Please resolve this complaint")
        ])

        self.escalation_prompt = ChatPromptTemplate.from_messages([
            ("system", """You need to escalate this complaint to a supervisor. Provide:

1. Summary of the complaint
2. Why escalation is needed
3. Recommended resolution
4. Urgency level

Complaint: {complaint}"""),
            ("user", "Escalate this complaint")
        ])

        self.output_parser = JsonOutputParser()

    def handle_complaint(self, state: TravelAgentState) -> TravelAgentState:
        """Handle a customer complaint and provide resolution"""

        try:
            # Analyze the complaint
            analysis_chain = self.complaint_analysis_prompt | self.llm | self.output_parser

            analysis_result = analysis_chain.invoke({
                "query": state["current_query"]
            })

            # Store analysis in state
            state = update_state_field(state, "agent_responses", {
                **state["agent_responses"],
                "complaint_analysis": analysis_result
            })

            # Determine response strategy based on severity and type
            complaint_type = analysis_result.get("complaint_type", "other")
            severity = analysis_result.get("severity", "medium")
            urgency = analysis_result.get("urgency", "response_within_24h")

            if severity == "critical" or urgency == "immediate_action_required":
                return self._handle_critical_complaint(state, analysis_result)
            elif complaint_type in ["refund", "cancellation"]:
                return self._handle_refund_cancellation(state, analysis_result)
            else:
                return self._provide_standard_resolution(state, analysis_result)

        except Exception as e:
            print(f"Complaint agent error: {e}")
            error_message = "I apologize for the inconvenience. I'm having trouble processing your complaint right now. Please contact our customer service team directly at support@travelcompany.com or call 1-800-TRAVEL."

            return add_message_to_state(
                state,
                "agent",
                error_message,
                "complaint_agent"
            )

    def _handle_critical_complaint(self, state: TravelAgentState, analysis: Dict[str, Any]) -> TravelAgentState:
        """Handle critical complaints that require immediate attention"""

        escalation_chain = self.escalation_prompt | self.llm

        escalation_response = escalation_chain.invoke({
            "complaint": state["current_query"]
        })

        response_message = f"""Complaint Agent: I understand this is a critical issue that requires immediate attention.

{escalation_response.content}

I have escalated this to our senior customer service team. A representative will contact you within the next hour at the phone number associated with your account.

For urgent matters, you can also call our emergency line at 1-800-TRAVEL-NOW.

We're truly sorry for the inconvenience and will work to resolve this as quickly as possible."""

        return add_message_to_state(
            state,
            "agent",
            response_message,
            "complaint_agent"
        )

    def _handle_refund_cancellation(self, state: TravelAgentState, analysis: Dict[str, Any]) -> TravelAgentState:
        """Handle refund and cancellation requests"""

        complaint_type = analysis.get("complaint_type")

        if complaint_type == "refund":
            response_message = """Complaint Agent: I'm sorry to hear you're requesting a refund. Let me help you with that.

To process your refund request, I'll need:
1. Your booking reference number
2. Reason for the refund request
3. Preferred refund method (original payment method or travel credit)

If you have your booking details handy, I can process this immediately. Otherwise, I can look up your booking using your email address or phone number.

Refunds are typically processed within 5-7 business days once approved."""
        else:  # cancellation
            response_message = """Complaint Agent: I understand you need to cancel your booking. I'll help you through this process.

For cancellations, please note:
- Cancellation policies vary by booking type and timing
- Some bookings may be non-refundable
- Early cancellations typically receive higher refund amounts

Could you provide your booking reference number so I can check your specific cancellation terms and process this for you?"""

        return add_message_to_state(
            state,
            "agent",
            response_message,
            "complaint_agent"
        )

    def _provide_standard_resolution(self, state: TravelAgentState, analysis: Dict[str, Any]) -> TravelAgentState:
        """Provide standard resolution for non-critical complaints"""

        solution_chain = self.solution_prompt | self.llm

        solution_response = solution_chain.invoke({
            "analysis": analysis,
            "context": {
                "booking_info": state["booking_info"],
                "customer_info": state["customer_info"],
                "conversation_history": [msg["content"] for msg in state["messages"][-3:]]
            }
        })

        response_message = f"Complaint Agent: {solution_response.content}"

        return add_message_to_state(
            state,
            "agent",
            response_message,
            "complaint_agent"
        )

    def offer_compensation(self, state: TravelAgentState) -> TravelAgentState:
        """Offer compensation for service issues"""

        compensation_message = """Complaint Agent: As a gesture of goodwill for the inconvenience you've experienced, I'd like to offer you:

1. Full refund of your booking
2. Travel credit for future bookings (150% of booking value)
3. Complimentary upgrade on your next trip
4. Additional travel insurance coverage

Which compensation option would you prefer? I can process this immediately once you let me know."""

        return add_message_to_state(
            state,
            "agent",
            compensation_message,
            "complaint_agent"
        )