-- 1. Create the new AI user with a password
CREATE USER ai_user WITH PASSWORD 'ABC123';

-- 2. Grant full privileges so it can insert/update tasks and chat history
GRANT ALL PRIVILEGES ON DATABASE employee_management TO ai_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ai_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ai_user; 

-- 3. Create the restricted read-only role
CREATE ROLE readonly_query NOLOGIN;
GRANT USAGE ON SCHEMA public TO readonly_query;
GRANT SELECT ON departments, roles, employees, tasks, task_events TO readonly_query;
GRANT SELECT ON reporting_lines, task_statuses TO readonly_query;

-- 4. Grant the ai_user permission to temporarily switch to the read-only role
GRANT readonly_query TO ai_user;