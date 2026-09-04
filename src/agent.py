import os
import json
import asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI
from fastmcp import Client

from pathlib import Path


# Load environment variables from .env file immediately
load_dotenv()

# Read configurations directly from environment
BASE_URL = os.getenv("HERMES_BASE_URL", "http://localhost:11434/v1")
HERMES_API_KEY = os.getenv("HERMES_API_KEY", "ollama")
MODEL_NAME = os.getenv("HERMES_MODEL", "hf.co/gabriellarson/Hermes-4-14B-GGUF:Q4_K_M")
SERVER_SCRIPT = os.getenv("FAST_MCP_SERVER_SCRIPT", "server.py")
SERVER_PATH = Path(SERVER_SCRIPT).resolve()

# Initialize the OpenAI client pointing to local Ollama
llm_client = AsyncOpenAI(
    base_url=BASE_URL,
    api_key=HERMES_API_KEY,
)

SYSTEM_PROMPT = """You are an autonomous Employee Management System assistant.
You have access to MCP database tools. If you need to know the database structure, call get_database_schema first.
Use run_readonly_query for SQL queries and make explicit table joins using foreign keys."""


async def run_agent_turn(mcp_client: Client, conversation: list):
    """Fetches tools, sends prompt to local LLM, and executes tool calls in a loop."""
    
    # 1. Fetch available tools dynamically from FastMCP server
    tools = await mcp_client.list_tools()
    
    # 2. Convert FastMCP tools to OpenAI Function Calling JSON schema
    openai_tools = [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema,
            },
        }
        for tool in tools
    ]

    while True:
        # 3. Call local Hermes via Ollama's /v1 endpoint
        response = await llm_client.chat.completions.create(
            model=MODEL_NAME,
            messages=conversation,
            tools=openai_tools,
        )
        message = response.choices[0].message
        conversation.append(message)

        # 4. If no tools were called, print the final answer and break loop
        if not message.tool_calls:
            print(f"\nAssistant:\n{message.content}\n")
            break

        # 5. Execute each requested tool
        for tool_call in message.tool_calls:
            func_name = tool_call.function.name
            try:
                func_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                func_args = {}

            print(f"⚙️ Running tool: {func_name}({json.dumps(func_args)})")
            
            # Execute tool against FastMCP server
            result = await mcp_client.call_tool(func_name, arguments=func_args)
            output_text = str(result.data) if hasattr(result, "data") else str(result)
            
            # Append result back into the prompt history
            conversation.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": output_text,
            })


async def main():
    # Pass current os.environ down to the child subprocess
    async with Client(SERVER_PATH) as mcp:
        print(f"Connected to FastMCP Server ({SERVER_SCRIPT}).")
        print(f"Using Model: {MODEL_NAME} at {BASE_URL}\n")
        
        conversation = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        while True:
            try:
                user_input = input("> ").strip()
                if not user_input or user_input.lower() in ["exit", "quit"]:
                    break

                conversation.append({"role": "user", "content": user_input})
                await run_agent_turn(mcp, conversation)
            except (KeyboardInterrupt, EOFError):
                break


if __name__ == "__main__":
    asyncio.run(main())