import json
from datetime import date, datetime
from fastmcp import FastMCP
from db import get_connection

class RecordEncoder(json.JSONEncoder):
    """Handles serialization of PostgreSQL datetimes to JSON."""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)

def register_tools(mcp: FastMCP):
    
    @mcp.tool()
    async def log_task_event(
        task_id: int,
        employee_id: int,
        new_status: str,
        old_status: str | None = None,
        note: str | None = None,
        raw_message: str | None = None
    ) -> str:
        """
        Logs a task state-transition event and updates the active task status.
        Call this when an employee updates a task or changes its state.
        """
        async with get_connection() as conn:
            async with conn.transaction():
                # 1. Update the master task record
                await conn.execute(
                    "UPDATE tasks SET status = $1 WHERE id = $2",
                    new_status, task_id
                )
                
                # 2. Log the immutable event to the write path
                await conn.execute(
                    """
                    INSERT INTO task_events 
                    (task_id, employee_id, old_status, new_status, note, raw_message)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    task_id, employee_id, old_status, new_status, note, raw_message
                )
        return f"Event logged successfully: Task #{task_id} status transitioned to '{new_status}'."

    @mcp.tool()
    async def run_readonly_query(query: str) -> str:
        """
        Executes a raw SQL SELECT query against the database to fetch operational data.
        Use this to analyze tasks, employee workloads, or general database states.
        """
        async with get_connection() as conn:
            # Enforce read-only at the transaction level so Hermes cannot mutate data
            async with conn.transaction(readonly=True):
                records = await conn.fetch(query)
                results = [dict(record) for record in records]
                
        return json.dumps(results, cls=RecordEncoder, indent=2)

    @mcp.tool()
    async def search_notes(keywords: str) -> str:
        """
        Performs a natural language keyword search against historical task notes and events.
        Matches stem logic and diacritics based on the Azerbaijani FTS dictionary.
        """
        query = """
            SELECT 
                task_id, employee_id, old_status, new_status, note, raw_message, occurred_at,
                ts_rank_cd(search_vector, plainto_tsquery('az', $1)) as rank
            FROM task_events
            WHERE search_vector @@ plainto_tsquery('az', $1)
            ORDER BY rank DESC
            LIMIT 10;
        """
        async with get_connection() as conn:
            records = await conn.fetch(query, keywords)
            results = [dict(record) for record in records]
            
        return json.dumps(results, cls=RecordEncoder, indent=2)