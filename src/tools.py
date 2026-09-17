import json
from fastmcp import FastMCP
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
        operator_id: The ID of the employee executing the action.
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

                    # 2. Verify the task belongs to the operator or a subordinate
                    task = await conn.fetchrow("SELECT assignee_id FROM tasks WHERE id = $1", task_id)
                    if not task:
                        return json.dumps({"error": "Task not found."})
                        
                    if task["assignee_id"] not in allowed_ids:
                        return json.dumps({"error": "Permission denied: You do not have access to modify this task."})

                    # 3. Execute the updates safely
                    await conn.execute(update_task_query, new_status, task_id)
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
        # Note the ANY($2::INT[]) clause which strictly filters the results
        query = """
        SELECT task_id, employee_id, new_status, note, occurred_at
        FROM task_events
        WHERE note ILIKE $1
          AND employee_id = ANY($2::INT[])
        ORDER BY occurred_at DESC
        LIMIT 20;
        """
        
        try:
            async with get_connection() as conn:
                # 1. Authorization Check: Fetch allowed IDs
                allowed_rows = await conn.fetch(TREE_QUERY, operator_id)
                allowed_ids = [row["id"] for row in allowed_rows]
                if not allowed_ids:
                    allowed_ids = [operator_id]
                
                # 2. Run the predefined query using the allowed_ids array
                rows = await conn.fetch(query, f"%{keyword}%", allowed_ids)
                return json.dumps([dict(row) for row in rows], default=str)
                
        except Exception as e:
            return json.dumps({"error": str(e)})