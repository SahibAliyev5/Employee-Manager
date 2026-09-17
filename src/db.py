import json
import uuid
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
import asyncpg
from config import DB_DSN

_pool: Optional[asyncpg.Pool] = None

async def init_pool():
    global _pool
    _pool = await asyncpg.create_pool(DB_DSN, min_size=2, max_size=20)

async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None

@asynccontextmanager
async def get_connection():
    """Yields a pooled connection for server.py queries."""
    if _pool is None:
        raise RuntimeError("Database pool has not been initialized.")
    async with _pool.acquire() as conn:
        yield conn

async def get_authorized_employee(telegram_id: int) -> Optional[Dict[str, Any]]:
    """Resolves Telegram ID to the core employee matrix, bypassing RLS safely."""
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM get_authorized_employee_secure($1)", 
            telegram_id
        )
        return dict(row) if row else None

async def get_or_create_thread(employee_id: int) -> uuid.UUID:
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT thread_id FROM chat_threads WHERE employee_id = $1 AND is_active = TRUE",
            employee_id
        )
        if row:
            return row["thread_id"]
        
        new_thread_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO chat_threads (thread_id, employee_id) VALUES ($1, $2)",
            new_thread_id, employee_id
        )
        return new_thread_id

async def reset_active_thread(employee_id: int) -> uuid.UUID:
    """Closes current session context to prevent sliding window hallucination."""
    async with _pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("UPDATE chat_threads SET is_active = FALSE WHERE employee_id = $1", employee_id)
            new_thread_id = uuid.uuid4()
            await conn.execute("INSERT INTO chat_threads (thread_id, employee_id) VALUES ($1, $2)", new_thread_id, employee_id)
            return new_thread_id

async def log_message(thread_id: uuid.UUID, employee_id: int, role: str, 
                      content: Optional[str] = None, tool_call_id: Optional[str] = None, 
                      tool_calls: Optional[Any] = None):
    async with _pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO chat_messages (thread_id, employee_id, role, content, tool_call_id, tool_calls)
            VALUES ($1, $2, $3, $4, $5, CAST($6 AS JSONB))
        """, thread_id, employee_id, role, content, tool_call_id, json.dumps(tool_calls) if tool_calls else None)

async def fetch_recent_messages(thread_id: uuid.UUID, limit: int = 15) -> List[Dict[str, Any]]:
    """Loads the trailing conversational context."""
    async with _pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT role, content, tool_call_id, tool_calls 
            FROM (
                SELECT id, role, content, tool_call_id, tool_calls 
                FROM chat_messages 
                WHERE thread_id = $1 
                ORDER BY id DESC 
                LIMIT $2
            ) sub
            ORDER BY id ASC
        """, thread_id, limit)

    messages = []
    for r in rows:
        msg = {"role": r["role"]}
        if r["content"] is not None:
            msg["content"] = r["content"]
        if r["tool_call_id"]:
            msg["tool_call_id"] = r["tool_call_id"]
        if r["tool_calls"]:
            tc = r["tool_calls"]
            msg["tool_calls"] = json.loads(tc) if isinstance(tc, str) else tc
        messages.append(msg)
    return messages