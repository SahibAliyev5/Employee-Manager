-- 009_ai_user_rls_policies.sql

CREATE POLICY ai_user_tasks_policy ON tasks
    FOR ALL TO ai_user
    USING (assignee_id = ANY(string_to_array(NULLIF(current_setting('app.allowed_ids', true), ''), ',')::INT[]))
    WITH CHECK (assignee_id = ANY(string_to_array(NULLIF(current_setting('app.allowed_ids', true), ''), ',')::INT[]));

CREATE POLICY ai_user_events_policy ON task_events
    FOR ALL TO ai_user
    USING (employee_id = ANY(string_to_array(NULLIF(current_setting('app.allowed_ids', true), ''), ',')::INT[]))
    WITH CHECK (employee_id = ANY(string_to_array(NULLIF(current_setting('app.allowed_ids', true), ''), ',')::INT[]));