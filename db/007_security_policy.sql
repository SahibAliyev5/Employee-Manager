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


CREATE OR REPLACE FUNCTION get_authorized_employee_secure(p_telegram_id BIGINT)
RETURNS TABLE (
    employee_id INT,
    name VARCHAR,
    department VARCHAR,
    role VARCHAR
) 
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
BEGIN
    -- This executes bypassing RLS because of SECURITY DEFINER
    RETURN QUERY
    SELECT u.employee_id, e.name, d.name, r.name
    FROM authorized_users u
    JOIN employees e ON u.employee_id = e.id
    JOIN departments d ON e.department_id = d.id
    JOIN roles r ON e.role_id = r.id
    WHERE u.telegram_id = p_telegram_id;
END;
$$;