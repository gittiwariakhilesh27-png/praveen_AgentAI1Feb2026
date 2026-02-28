from phi.agent import Agent
from phi.model.openai import OpenAIChat

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

def create_basic_agent():

    agent = Agent(
        name="Jarvis",
        model=OpenAIChat(id="gpt-4o"),
        description="You are a helpful AI assistant.",
        # System prompt to guide the agent's behavior
        instructions=[
            "Be concise and helpful.",
            "Ask clarifying questions if needed.",
        ],
        markdown=True,  # Enable markdown formatting in responses
        debug=True,  # Enable debug mode for detailed logs
    )

    return agent


if __name__ == "__main__":
    agent = create_basic_agent()
    response = agent.print_response("What is the capital of France?")
    print(response)