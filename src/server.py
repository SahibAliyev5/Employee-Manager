# ems_server.py
import json
from contextlib import asynccontextmanager
from fastmcp import FastMCP

import sys
from pathlib import Path
# Ensure the directory containing this script (src/) is in sys.path
sys.path.insert(0, str(Path(__file__).parent.resolve()))

from db import init_pool, close_pool, get_connection

@asynccontextmanager
async def server_lifespan(server: FastMCP):
    """Initializes asyncpg pool on server boot and cleans up on shutdown."""
    await init_pool()
    try:
        yield
    finally:
        await close_pool()


mcp = FastMCP("hermes-ems", lifespan=server_lifespan)

@mcp.tool
async def get_database_schema() -> str:
    """
    Returns the complete database schema including all table names and their column definitions.
    Call this tool first if you need to know the database structure.
    """
    query = """
    SELECT 
        table_name, 
        column_name, 
        data_type 
    FROM information_schema.columns 
    WHERE table_schema = 'public'
    ORDER BY table_name, ordinal_position;
    """
    async with get_connection() as conn:
        rows = await conn.fetch(query)
        return json.dumps([dict(row) for row in rows], default=str)


@mcp.tool
async def run_readonly_query(sql_query: str) -> str:
    """
    Executes a read-only SQL query (SELECT) against the database and returns the rows as JSON.
    Use this for querying employees, tasks, or event histories.
    """
    sanitized = sql_query.strip().lower()
    if not (sanitized.startswith("select") or sanitized.startswith("with")):
        return json.dumps({"error": "Only read-only SELECT queries are permitted."})

    try:
        async with get_connection() as conn:
            rows = await conn.fetch(sql_query)
            return json.dumps([dict(row) for row in rows], default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool
async def log_task_event(
    task_id: int, 
    employee_id: int, 
    new_status: str, 
    note: str, 
    old_status: str = None
) -> str:
    """
    Logs an event/status update for a given task into the task_events table.
    Allowed statuses: 'open', 'in_progress', 'blocked', 'review', 'completed'.
    """
    query = """
    INSERT INTO task_events (task_id, employee_id, old_status, new_status, note)
    VALUES ($1, $2, $3, $4, $5)
    RETURNING id, occurred_at;
    """
    try:
        async with get_connection() as conn:
            row = await conn.fetchrow(query, task_id, employee_id, old_status, new_status, note)
            return json.dumps({"success": True, "event": dict(row)}, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool
async def search_notes(keyword: str) -> str:
    """
    Performs keyword search on task notes and event logs.
    """
    query = """
    SELECT task_id, employee_id, new_status, note, occurred_at
    FROM task_events
    WHERE note ILIKE $1
    ORDER BY occurred_at DESC
    LIMIT 20;
    """
    try:
        async with get_connection() as conn:
            rows = await conn.fetch(query, f"%{keyword}%")
            return json.dumps([dict(row) for row in rows], default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    mcp.run()