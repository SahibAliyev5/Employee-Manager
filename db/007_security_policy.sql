-- 1. Enable RLS on your tables
ALTER TABLE employees ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE task_events ENABLE ROW LEVEL SECURITY;

-- 2. Create the policies strictly for the AI's read-only role
CREATE POLICY employee_hierarchy ON employees
    FOR SELECT TO readonly_query
    USING (
        id = ANY(string_to_array(NULLIF(current_setting('app.allowed_ids', true), ''), ',')::INT[])
    );

CREATE POLICY task_hierarchy ON tasks
    FOR SELECT TO readonly_query
    USING (
        assignee_id = ANY(string_to_array(NULLIF(current_setting('app.allowed_ids', true), ''), ',')::INT[])
    );

CREATE POLICY task_event_hierarchy ON task_events
    FOR SELECT TO readonly_query
    USING (
        employee_id = ANY(string_to_array(NULLIF(current_setting('app.allowed_ids', true), ''), ',')::INT[])
    );