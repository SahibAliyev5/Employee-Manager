import asyncio
import json
import uuid
from collections import defaultdict
from typing import Dict, Any, Optional
from fastmcp import Client
from config import llm_client, MODEL_NAME, SERVER_PATH
import db

# Ensures parallel Telegram users do not mutate each other's state
EMPLOYEE_LOCKS: Dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

# Global FastMCP client to prevent subprocess thrashing on every message
mcp_client: Optional[Client] = None

# Maximum number of iterations to prevent infinite loops in tool calls
MAX_TOOL_CALL_ITERATIONS = 10

SYSTEM_PROMPT = """You are an autonomous PostgreSQL assistant for an Employee Management System.
Current Employee Operator: {name} (ID: {employee_id}, Role: {role}, Dept: {department}).
Always verify facts and task statuses using your tools. Never fabricate records."""

async def init_mcp():
    global mcp_client
    mcp_client = Client(SERVER_PATH)
    await mcp_client.__aenter__()

async def close_mcp():
    if mcp_client:
        await mcp_client.__aexit__(None, None, None)

async def process_user_turn(employee: Dict[str, Any], user_input: str) -> str:
    emp_id = employee["employee_id"]
    thread_id = await db.get_or_create_thread(emp_id)

    await db.log_message(thread_id, emp_id, role="user", content=user_input)

    formatted_sys_prompt = {
        "role": "system",
        "content": SYSTEM_PROMPT.format(
            name=employee["name"],
            employee_id=emp_id,
            role=employee.get("role", "Staff"),
            department=employee.get("department") or "General"
        )
    }
    history = [formatted_sys_prompt] + await db.fetch_recent_messages(thread_id, limit=12)

    tools = await mcp_client.list_tools()
    openai_tools = [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema,
            },
        } for tool in tools
    ]

    iteration = 0
    while True:
        if iteration >= MAX_TOOL_CALL_ITERATIONS:
            fallback = "I was unable to complete the request within the allowed tool call limit. Please try rephrasing or narrowing your query."
            await db.log_message(thread_id, emp_id, role="assistant", content=fallback)
            return fallback

        iteration += 1

        response = await llm_client.chat.completions.create(
            model=MODEL_NAME,
            messages=history,
            tools=openai_tools,
        )
        message = response.choices[0].message
        history.append(message.model_dump(exclude_none=True))

        if not message.tool_calls:
            final_text = message.content or ""
            await db.log_message(thread_id, emp_id, role="assistant", content=final_text)
            return final_text

        await db.log_message(
            thread_id, emp_id, role="assistant", 
            tool_calls=[tc.model_dump() for tc in message.tool_calls]
        )

        for tool_call in message.tool_calls:
            func_name = tool_call.function.name
            try:
                func_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                func_args = {}

            result = await mcp_client.call_tool(func_name, arguments=func_args)
            output_text = str(result.data) if hasattr(result, "data") else str(result)

            await db.log_message(
                thread_id, emp_id, role="tool", 
                content=output_text, tool_call_id=tool_call.id
            )
            history.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": output_text,
            })