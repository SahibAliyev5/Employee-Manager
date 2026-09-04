-- 002_seed_dummy_data.sql

BEGIN;

-- 1. Departments
INSERT INTO departments (id, name) VALUES
    (1, 'Engineering'),
    (2, 'Product'),
    (3, 'Design')
ON CONFLICT (id) DO NOTHING;

-- 2. Roles
INSERT INTO roles (id, name) VALUES
    (1, 'Engineering Director'),
    (2, 'Engineering Manager'),
    (3, 'Senior Software Engineer'),
    (4, 'Junior Software Engineer'),
    (5, 'Product Lead'),
    (6, 'Product Manager'),
    (7, 'UI/UX Designer')
ON CONFLICT (id) DO NOTHING;

-- 3. Employees
INSERT INTO employees (id, name, department_id, role_id) VALUES
    (1, 'Alice Vance',   1, 1), -- Engineering Director
    (2, 'Bob Stone',     1, 2), -- Engineering Manager
    (3, 'Charlie Day',   1, 3), -- Senior Software Engineer
    (4, 'Dana Scully',   1, 4), -- Junior Software Engineer
    (5, 'Evan Wright',   2, 5), -- Product Lead
    (6, 'Fiona Glen',    2, 6), -- Product Manager
    (7, 'George Clark',  3, 7)  -- UI/UX Designer
ON CONFLICT (id) DO NOTHING;

-- 4. Reporting Lines (Demonstrating direct & matrix lines)
INSERT INTO reporting_lines (supervisor_id, subordinate_id) VALUES
    -- Traditional hierarchy: Alice -> Bob -> Charlie & Dana
    (1, 2),
    (2, 3),
    (2, 4),
    -- Product hierarchy: Evan -> Fiona
    (5, 6),
    -- Cross-functional / matrix report: Fiona also oversees Dana for feature deliverables
    (6, 4)
ON CONFLICT (supervisor_id, subordinate_id) DO NOTHING;

-- Reset identity sequences for tables where IDs were explicitly provided
SELECT setval(pg_get_serial_sequence('departments', 'id'), (SELECT MAX(id) FROM departments));
SELECT setval(pg_get_serial_sequence('roles', 'id'), (SELECT MAX(id) FROM roles));
SELECT setval(pg_get_serial_sequence('employees', 'id'), (SELECT MAX(id) FROM employees));

-- 5. Tasks and Audit-Consistent Event Logs

-- Task 1: "Set up CI/CD Pipeline" -> Currently 'completed'
-- History: created (open) -> in_progress -> review -> completed
INSERT INTO tasks (id, title, description, assignee_id, status, created_at)
VALUES (
    1,
    'Set up CI/CD Pipeline',
    'Configure GitHub Actions for automated linting and tests.',
    3, -- Charlie Day
    'completed',
    NOW() - INTERVAL '5 days'
);

INSERT INTO task_events (task_id, employee_id, old_status, new_status, note, raw_message, occurred_at) VALUES
    (1, 2, NULL, 'open', 'Task created and assigned to Charlie.', 'Create task', NOW() - INTERVAL '5 days'),
    (1, 3, 'open', 'in_progress', 'Started drafting YAML workflows.', 'git branch ci-pipeline', NOW() - INTERVAL '4 days'),
    (1, 3, 'in_progress', 'review', 'PR opened, awaiting review.', 'PR #102 opened', NOW() - INTERVAL '2 days'),
    (1, 2, 'review', 'completed', 'Approved and merged.', 'PR #102 merged', NOW() - INTERVAL '1 day');

-- Task 2: "Build REST API for Tasks" -> Currently 'in_progress'
-- History: created (open) -> in_progress
INSERT INTO tasks (id, title, description, assignee_id, status, created_at)
VALUES (
    2,
    'Build REST API for Tasks',
    'Expose endpoints for tasks and historical event retrieval.',
    4, -- Dana Scully
    'in_progress',
    NOW() - INTERVAL '3 days'
);

INSERT INTO task_events (task_id, employee_id, old_status, new_status, note, raw_message, occurred_at) VALUES
    (2, 2, NULL, 'open', 'Initial assignment.', 'Task created', NOW() - INTERVAL '3 days'),
    (2, 4, 'open', 'in_progress', 'Scaffolding routes and DB queries.', 'WIP commit', NOW() - INTERVAL '2 days');

-- Task 3: "Design Schema Migrations" -> Currently 'blocked'
-- History: created (open) -> in_progress -> blocked
INSERT INTO tasks (id, title, description, assignee_id, status, created_at)
VALUES (
    3,
    'Design Schema Migrations',
    'Finalize reporting lines and status lookup tables.',
    3, -- Charlie Day
    'blocked',
    NOW() - INTERVAL '2 days'
);

INSERT INTO task_events (task_id, employee_id, old_status, new_status, note, raw_message, occurred_at) VALUES
    (3, 1, NULL, 'open', 'Assigned by Alice.', 'Task created', NOW() - INTERVAL '2 days'),
    (3, 3, 'open', 'in_progress', 'Reviewing foreign key constraints.', 'Status change', NOW() - INTERVAL '1 day 12 hours'),
    (3, 3, 'in_progress', 'blocked', 'Waiting on final role hierarchy sign-off.', 'Blocker flagged', NOW() - INTERVAL '6 hours');

-- Task 4: "Dashboard Wireframes" -> Currently 'open'
-- History: created (open)
INSERT INTO tasks (id, title, description, assignee_id, status, created_at)
VALUES (
    4,
    'Dashboard Wireframes',
    'Create Figma mockups for the manager view.',
    7, -- George Clark
    'open',
    NOW() - INTERVAL '1 day'
);

INSERT INTO task_events (task_id, employee_id, old_status, new_status, note, raw_message, occurred_at) VALUES
    (4, 6, NULL, 'open', 'Initial backlog ticket created by Fiona.', 'Task created', NOW() - INTERVAL '1 day');

-- Reset identity sequences for tasks and task_events
SELECT setval(pg_get_serial_sequence('tasks', 'id'), (SELECT MAX(id) FROM tasks));
SELECT setval(pg_get_serial_sequence('task_events', 'id'), (SELECT MAX(id) FROM task_events));

COMMIT;