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

SYSTEM_PROMPT = """You are an AI assistant for an Employee Management System. 
When writing SQL, you must strictly use the following database schema:

TABLE employees (
  id SERIAL PRIMARY KEY,
  name VARCHAR,
  email VARCHAR,
  department VARCHAR
);

TABLE tasks (
  id SERIAL PRIMARY KEY,
  title VARCHAR,
  description TEXT,
  assignee_id INT REFERENCES employees(id),
  status VARCHAR -- ('open', 'in_progress', 'blocked', 'completed')
);

TABLE task_events (
  id SERIAL PRIMARY KEY,
  task_id INT REFERENCES tasks(id),
  employee_id INT REFERENCES employees(id),
  new_status VARCHAR,
  note TEXT,
  created_at TIMESTAMP
);

Never invent tables or columns. If a user asks for data not present in this schema, inform them it is unavailable.
"""

async def init_mcp():
    global mcp_client
    mcp_client = Client(SERVER_PATH)
    await mcp_client.__aenter__()

async def close_mcp():
    if mcp_client:
        await mcp_client.__aexit__(None, None, None)


def sanitize_history(raw_messages: list) -> list:
    """
    Cleans message history to strictly conform to role alternation rules.
    """
    cleaned = []
    
    for msg in raw_messages:
        role = msg.get("role")
        
        # 1. Ensure the sequence begins with a user message.
        # Drop leading assistant/tool messages caused by database pagination slicing.
        if not cleaned and role != "user":
            continue
            
        # 2. Drop orphaned tool messages (tool responses without a preceding tool_call)
        if role == "tool":
            if not cleaned or cleaned[-1].get("role") != "assistant" or not cleaned[-1].get("tool_calls"):
                continue
                
        # 3. Handle unanswered tool calls (if an assistant made a call but a user replied instead)
        if role in ["user", "assistant"] and cleaned and cleaned[-1].get("role") == "assistant" and cleaned[-1].get("tool_calls"):
            cleaned.pop()
        
        # 4. Merge consecutive messages of the same role
        if role == "user" and cleaned and cleaned[-1].get("role") == "user":
            cleaned[-1]["content"] = f"{cleaned[-1].get('content', '')}\n{msg.get('content', '')}"
            continue
            
        if role == "assistant" and cleaned and cleaned[-1].get("role") == "assistant":
            cleaned[-1]["content"] = f"{cleaned[-1].get('content', '')}\n{msg.get('content', '')}"
            continue

        cleaned.append(msg)
        
    # 5. Remove any trailing tool call that was never answered
    if cleaned and cleaned[-1].get("role") == "assistant" and cleaned[-1].get("tool_calls"):
        cleaned.pop()
        
    return cleaned

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
    recent_db_messages = await db.fetch_recent_messages(thread_id, limit=40)
    sanitized_history = sanitize_history(recent_db_messages)
    
    history = [formatted_sys_prompt] + sanitized_history

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

            # Forcefully inject the operator_id into EVERY tool call
            func_args["operator_id"] = emp_id 

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