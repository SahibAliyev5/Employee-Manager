import json
from fastmcp import FastMCP
from db import get_connection

def register_tools(mcp: FastMCP):

    @mcp.tool
    async def run_readonly_query(sql_query: str) -> str:
        """
        Executes a read-only SELECT query against the PostgreSQL database.
        
        EXACT TABLES AND COLUMNS:
        - departments (id, name)
        - roles (id, name)
        - employees (id, name, department_id, role_id)
        - tasks (id, title, description, assignee_id, status, created_at)
        - task_events (id, task_id, employee_id, new_status, note, occurred_at)
        """
        sanitized = sql_query.strip().lower()
        if not (sanitized.startswith("select") or sanitized.startswith("with")):
            return json.dumps({"error": "Only read-only SELECT queries are permitted."})
        
        try:
            async with get_connection() as conn:
                rows = await conn.fetch(sql_query)
                return json.dumps([dict(row) for row in rows], default=str)
        except Exception as e:
            return json.dumps({"error": f"SQL execution failed: {str(e)}. Please correct table and column names and retry."})

    @mcp.tool
    async def log_task_event(
        task_id: int, 
        employee_id: int, 
        new_status: str, 
        note: str, 
        old_status: str = None
    ) -> str:
        """
        Logs an event/status update for a given task and updates the active task status.
        Allowed statuses: 'open', 'in_progress', 'blocked', 'review', 'completed'.
        """
        insert_event_query = """
        INSERT INTO task_events (task_id, employee_id, old_status, new_status, note)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, occurred_at;
        """
        update_task_query = """
        UPDATE tasks SET status = $1 WHERE id = $2;
        """
        
        try:
            async with get_connection() as conn:
                # Wrap both operations in a transaction to guarantee event-sourcing sync
                async with conn.transaction():
                    await conn.execute(update_task_query, new_status, task_id)
                    row = await conn.fetchrow(insert_event_query, task_id, employee_id, old_status, new_status, note)
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