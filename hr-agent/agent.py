"""
HR LangGraph Agent
==================
Connects to the Employee MCP HTTP server (http://localhost:8000/mcp) and
exposes all its tools to a LangGraph ReAct agent.

Usage
-----
# Start the MCP server first:
#   cd ../employee-mcp && python server.py
#
# Then run interactively:
#   python agent.py
#
# Or ask a one-shot question:
#   python agent.py "Who earns the most in Engineering?"
"""

from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv()

# ── Config ─────────────────────────────────────────────────────────────────
MCP_URL = os.getenv("EMPLOYEE_MCP_URL", "http://localhost:8000/mcp")

SYSTEM_PROMPT = """You are an expert HR assistant with access to a live Employee Directory.

You have the following tools available (call them whenever data is needed):
- list_employees        — list all (optionally active-only) employees
- get_employee          — fetch a single employee by numeric ID
- search_employees      — full-text search by name, email, or job title
- list_departments      — list all departments with headcount
- get_employees_by_department — employees in a specific department
- get_salary_stats      — salary min / max / average (globally or per dept)
- get_schema            — inspect the database: all tables, column names, types, and primary keys
- execute_query         — run a custom read-only SELECT query for anything the above tools don't cover

Guidelines:
- Always use the tools to look up real data; never guess or invent employee details.
- When asked about a person, try search_employees first, then get_employee if you have an ID.
- Summarise results clearly with bullet points or a short table when there are multiple records.
- For salary questions always call get_salary_stats rather than computing averages yourself.
- Keep answers professional and concise.
- If a tool returns an empty list, say so clearly and suggest alternatives.
"""


def _make_client() -> MultiServerMCPClient:
    return MultiServerMCPClient(
        {
            "employee_directory": {
                "url": MCP_URL,
                "transport": "streamable_http",
            }
        }
    )


def _make_llm() -> ChatOpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is required.")
    return ChatOpenAI(
        api_key=api_key,
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0.1,
    )


# ── Single-question helper ─────────────────────────────────────────────────
async def ask(question: str) -> str:
    client = _make_client()
    tools = await client.get_tools()
    agent = create_react_agent(model=_make_llm(), tools=tools, prompt=SYSTEM_PROMPT)
    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=question)]},
        config={"recursion_limit": 25},
    )
    return result["messages"][-1].content


# ── Interactive REPL ───────────────────────────────────────────────────────
async def interactive_loop() -> None:
    print("HR Agent ready. Type 'exit' or 'quit' to stop.\n")

    client = _make_client()
    tools = await client.get_tools()
    agent = create_react_agent(model=_make_llm(), tools=tools, prompt=SYSTEM_PROMPT)

    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not question:
            continue
        if question.lower() in {"exit", "quit", "bye"}:
            print("Goodbye.")
            break

        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=question)]},
            config={"recursion_limit": 25},
        )
        answer = result["messages"][-1].content
        print(f"\nHR Agent: {answer}\n")


# ── Entry point ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) > 1:
        # One-shot mode: python agent.py "your question"
        question = " ".join(sys.argv[1:])
        answer = asyncio.run(ask(question))
        print(f"HR Agent: {answer}")
    else:
        # Interactive REPL
        asyncio.run(interactive_loop())
