import json
from fastmcp import FastMCP
import mcp
from db import get_connection

# Define the recursive query once to use across all tools
TREE_QUERY = """
    WITH RECURSIVE subordinates AS (
        SELECT $1::INT AS id
        UNION ALL
        SELECT rl.subordinate_id
        FROM reporting_lines rl
        INNER JOIN subordinates s ON rl.supervisor_id = s.id
    ) SELECT id FROM subordinates;
"""

def register_tools(mcp: FastMCP):
    @mcp.tool
    async def run_readonly_query(sql_query: str, operator_id: int) -> str:
        """
        Executes a read-only SELECT query against the PostgreSQL database.
        operator_id: The ID of the employee executing the query.
        """
        sanitized = sql_query.strip().lower()
        if not (sanitized.startswith("select") or sanitized.startswith("with")):
            return json.dumps({"error": "Only read-only SELECT queries are permitted."})
        
        if "set " in sanitized or "current_setting" in sanitized:
            return json.dumps({"error": "Permission denied."})

        try:
            async with get_connection() as conn:
                async with conn.transaction():
                    
                    # 1. Fetch allowed IDs
                    allowed_rows = await conn.fetch(TREE_QUERY, operator_id)
                    allowed_ids = ",".join([str(row["id"]) for row in allowed_rows]) or str(operator_id)
                    
                    # 2. Pass IDs to Postgres for RLS using set_config() to support parameters safely
                    await conn.execute("SELECT set_config('app.allowed_ids', $1, true);", allowed_ids)
                    
                    # 3. Lock down permissions
                    await conn.execute("SET LOCAL ROLE readonly_query;")
                    
                    # 4. Run the AI's query
                    rows = await conn.fetch(sql_query)
                    return json.dumps([dict(row) for row in rows], default=str)
                    
        except Exception as e:
            return json.dumps({"error": f"SQL execution failed: {str(e)}"})


    @mcp.tool
    async def log_task_event(
        task_id: int, 
        employee_id: int, 
        new_status: str, 
        note: str,
        operator_id: int,
        old_status: str = None
    ) -> str:
        """
        Logs an event/status update for a given task and updates the active task status.
        
        CRITICAL INSTRUCTIONS FOR AI:
        - employee_id: Use the employee_id provided to you in your system prompt. DO NOT ask the user.
        - operator_id: The system auto-injects this. Provide a dummy integer (e.g., 0) as it will be overwritten. DO NOT ask the user.
        - task_id: If the user gives you a task title (e.g., "CI/CD Pipeline"), use run_readonly_query to find its ID. DO NOT ask the user for the ID.
        - new_status & note: You MUST ask the user for these if they didn't provide them in their request.
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
                async with conn.transaction():
                    
                    # 1. Authorization Check: Fetch allowed IDs
                    allowed_rows = await conn.fetch(TREE_QUERY, operator_id)
                    allowed_ids = [row["id"] for row in allowed_rows]
                    if not allowed_ids:
                        allowed_ids = [operator_id]

                    # 2. Inject allowed IDs into the Postgres transaction for RLS
                    allowed_ids_str = ",".join(map(str, allowed_ids))
                    await conn.execute("SELECT set_config('app.allowed_ids', $1, true);", allowed_ids_str)
                    
                    # 3. Execute the update (RLS will automatically block unauthorized access)
                    update_result = await conn.execute(update_task_query, new_status, task_id)
                    
                    # asyncpg returns 'UPDATE 0' if no rows were matched or if RLS blocked the write
                    if update_result == "UPDATE 0":
                        return json.dumps({"error": "Task not found or permission denied."})
                        
                    # 4. Insert the event log
                    row = await conn.fetchrow(insert_event_query, task_id, employee_id, old_status, new_status, note)
                    return json.dumps({"success": True, "event": dict(row)}, default=str)
                    
        except Exception as e:
            return json.dumps({"error": str(e)})


    @mcp.tool
    async def search_notes(keyword: str, operator_id: int) -> str:
        """
        Performs keyword search on task notes and event logs.
        operator_id: The ID of the employee executing the search.
        """
        # The manual ANY($2::INT[]) filter is removed. 
        # RLS will automatically restrict results to the allowed reporting line.
        query = """
        SELECT task_id, employee_id, new_status, note, occurred_at
        FROM task_events
        WHERE note ILIKE $1
        ORDER BY occurred_at DESC
        LIMIT 20;
        """
        
        try:
            async with get_connection() as conn:
                # We must wrap this in a transaction so set_config(..., true) scopes correctly
                async with conn.transaction():
                    
                    # 1. Authorization Check: Fetch allowed IDs
                    allowed_rows = await conn.fetch(TREE_QUERY, operator_id)
                    allowed_ids = [row["id"] for row in allowed_rows]
                    if not allowed_ids:
                        allowed_ids = [operator_id]
                        
                    # 2. Inject allowed IDs into the Postgres transaction for RLS
                    allowed_ids_str = ",".join(map(str, allowed_ids))
                    await conn.execute("SELECT set_config('app.allowed_ids', $1, true);", allowed_ids_str)
                    
                    # 3. Run the simplified query (RLS handles the data masking)
                    rows = await conn.fetch(query, f"%{keyword}%")
                    return json.dumps([dict(row) for row in rows], default=str)
                    
        except Exception as e:
            return json.dumps({"error": str(e)})