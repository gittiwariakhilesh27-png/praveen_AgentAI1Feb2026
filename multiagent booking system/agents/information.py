from typing import Dict, Any, Optional, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from models.state import TravelAgentState
from graph import add_message_to_state, update_state_field


class InformationAgent:
    """Information agent for providing travel information, recommendations, and destination details"""

    def __init__(self, openai_api_key: str):
        self.llm = ChatOpenAI(
            api_key=openai_api_key,
            model="gpt-4o-mini",
            temperature=0.3
        )

        self.query_analysis_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a travel information specialist. Analyze the customer's query to understand what type of information they need:

Query types:
- destination_info: Information about a specific place
- travel_tips: Advice on traveling to/from a place
- recommendations: Suggestions for activities, restaurants, hotels
- requirements: Visa, vaccine, or documentation requirements
- general_travel: General travel questions and tips
- weather_seasonal: Weather or best time to visit information

Extract key elements:
- destination: The place they're asking about
- query_type: The type of information needed
- timeframe: When they're planning to travel
- interests: What they're interested in (beaches, culture, adventure, etc.)

Return a JSON response with the analysis."""),
            ("user", "{query}")
        ])

        self.destination_info_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a knowledgeable travel guide providing detailed information about destinations. Provide comprehensive, accurate information including:

1. Key attractions and landmarks
2. Best time to visit and current weather
3. Cultural highlights and local customs
4. Transportation options
5. Safety information
6. Local cuisine recommendations
7. Practical tips for visitors

Destination: {destination}
Travel timeframe: {timeframe}
Interests: {interests}

Keep the response engaging and informative."""),
            ("user", "Tell me about {destination}")
        ])

        self.recommendation_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a travel recommendation expert. Provide personalized recommendations based on:

1. Destination and interests
2. Budget considerations
3. Travel style (luxury, budget, adventure, relaxation)
4. Time of year
5. Group composition (solo, family, couple)

Provide 3-5 specific recommendations with brief explanations.

Destination: {destination}
Interests: {interests}
Budget: {budget}
Group: {group}"""),
            ("user", "What do you recommend in {destination}?")
        ])

        self.travel_tips_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are providing practical travel tips. Cover:

1. Transportation from airport to city center
2. Local transportation options
3. Money/Currency information
4. Communication (SIM cards, WiFi)
5. Cultural etiquette and customs
6. Safety tips
7. Emergency contacts
8. Useful phrases in local language

Destination: {destination}
Travel duration: {duration}"""),
            ("user", "What are the travel tips for {destination}?")
        ])

        self.output_parser = JsonOutputParser()

    def provide_information(self, state: TravelAgentState) -> TravelAgentState:
        """Provide travel information based on the customer's query"""

        try:
            # Analyze the query to understand what information is needed
            analysis_chain = self.query_analysis_prompt | self.llm | self.output_parser

            analysis_result = analysis_chain.invoke({
                "query": state["current_query"]
            })

            query_type = analysis_result.get("query_type", "general_travel")
            destination = analysis_result.get("destination")
            timeframe = analysis_result.get("timeframe")
            interests = analysis_result.get("interests", [])

            # Route to appropriate information handler
            if query_type == "destination_info":
                return self._provide_destination_info(state, destination, timeframe, interests)
            elif query_type == "recommendations":
                return self._provide_recommendations(state, destination, interests)
            elif query_type == "travel_tips":
                return self._provide_travel_tips(state, destination)
            elif query_type == "requirements":
                return self._provide_requirements_info(state, destination)
            elif query_type == "weather_seasonal":
                return self._provide_weather_info(state, destination, timeframe)
            else:
                return self._provide_general_travel_info(state)

        except Exception as e:
            print(f"Information agent error: {e}")
            error_message = "I apologize, but I'm having trouble retrieving that travel information right now. Could you please rephrase your question or ask about a specific destination?"

            return add_message_to_state(
                state,
                "agent",
                error_message,
                "information_agent"
            )

    def _provide_destination_info(self, state: TravelAgentState, destination: str, timeframe: str, interests: List[str]) -> TravelAgentState:
        """Provide comprehensive destination information"""

        info_chain = self.destination_info_prompt | self.llm

        response = info_chain.invoke({
            "destination": destination or "the location",
            "timeframe": timeframe or "unspecified",
            "interests": ", ".join(interests) if interests else "general tourism"
        })

        response_message = f"Information Agent: Here's what I know about {destination}:\n\n{response.content}"

        return add_message_to_state(
            state,
            "agent",
            response_message,
            "information_agent"
        )

    def _provide_recommendations(self, state: TravelAgentState, destination: str, interests: List[str]) -> TravelAgentState:
        """Provide personalized recommendations"""

        # Extract budget and group info from conversation if available
        budget = "moderate"  # Default
        group = "general"

        # Look for budget mentions in recent messages
        recent_messages = [msg["content"] for msg in state["messages"][-5:]]
        for msg in recent_messages:
            msg_lower = msg.lower()
            if any(word in msg_lower for word in ["luxury", "expensive", "high-end"]):
                budget = "luxury"
            elif any(word in msg_lower for word in ["budget", "cheap", "affordable"]):
                budget = "budget"
            elif any(word in msg_lower for word in ["family", "kids", "children"]):
                group = "family"
            elif any(word in msg_lower for word in ["solo", "alone"]):
                group = "solo"

        rec_chain = self.recommendation_prompt | self.llm

        response = rec_chain.invoke({
            "destination": destination or "your destination",
            "interests": ", ".join(interests) if interests else "general tourism",
            "budget": budget,
            "group": group
        })

        response_message = f"Information Agent: Based on your interests, here are my recommendations for {destination}:\n\n{response.content}"

        return add_message_to_state(
            state,
            "agent",
            response_message,
            "information_agent"
        )

    def _provide_travel_tips(self, state: TravelAgentState, destination: str) -> TravelAgentState:
        """Provide practical travel tips"""

        tips_chain = self.travel_tips_prompt | self.llm

        response = tips_chain.invoke({
            "destination": destination or "your destination",
            "duration": "your trip"  # Could be extracted from booking info
        })

        response_message = f"Information Agent: Here are some practical travel tips for {destination}:\n\n{response.content}"

        return add_message_to_state(
            state,
            "agent",
            response_message,
            "information_agent"
        )

    def _provide_requirements_info(self, state: TravelAgentState, destination: str) -> TravelAgentState:
        """Provide visa, vaccine, and documentation requirements"""

        requirements_message = f"""Information Agent: Here's the requirements information for traveling to {destination}:

**Visa Requirements:**
- Check the latest visa requirements at your government's travel website
- Most countries offer visa on arrival or e-visas
- Processing time varies by nationality

**Health Requirements:**
- COVID-19: Check current entry requirements
- Vaccinations: Consult CDC or WHO guidelines
- Travel insurance is highly recommended

**Documentation:**
- Valid passport (usually 6 months beyond travel dates)
- Return flight itinerary
- Hotel booking confirmation
- Proof of sufficient funds

For the most up-to-date information, I recommend checking:
- Your country's foreign affairs website
- The destination country's embassy website
- International Air Transport Association (IATA) travel requirements

Would you like me to help you check specific requirements for your nationality?"""

        return add_message_to_state(
            state,
            "agent",
            requirements_message,
            "information_agent"
        )

    def _provide_weather_info(self, state: TravelAgentState, destination: str, timeframe: str) -> TravelAgentState:
        """Provide weather and seasonal information"""

        weather_message = f"""Information Agent: Here's the weather information for {destination}:

**Current Season/Weather:**
- Weather patterns vary significantly by location
- Best time to visit depends on your interests

**General Weather Tips:**
- Pack layers regardless of destination
- Check weather apps for real-time updates
- Consider seasonal events and festivals

For specific weather forecasts and best visiting times, I recommend checking:
- Weather websites like Weather.com or AccuWeather
- Local tourism board websites
- Travel forums for real traveler experiences

Would you like recommendations for the best time to visit {destination} based on your interests?"""

        return add_message_to_state(
            state,
            "agent",
            weather_message,
            "information_agent"
        )

    def _provide_general_travel_info(self, state: TravelAgentState) -> TravelAgentState:
        """Provide general travel information"""

        general_message = """Information Agent: I'd be happy to help with your travel questions! I can provide information about:

**Destinations:** Attractions, culture, practical tips, and recommendations
**Planning:** Visa requirements, best times to visit, transportation options
**Activities:** Tours, experiences, and local experiences
**Practical Advice:** Packing tips, safety information, and local customs

Could you please tell me:
- Which destination you're interested in?
- What type of information you need?
- When you're planning to travel?

This will help me give you the most relevant and useful information!"""

        return add_message_to_state(
            state,
            "agent",
            general_message,
            "information_agent"
        )