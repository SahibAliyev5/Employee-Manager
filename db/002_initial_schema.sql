-- 001_initial_schema_v6.sql

-- 1. Clean Slate
DROP TABLE IF EXISTS task_events CASCADE;
DROP TABLE IF EXISTS tasks CASCADE;
DROP TABLE IF EXISTS task_statuses CASCADE;
DROP TABLE IF EXISTS reporting_lines CASCADE;
DROP TABLE IF EXISTS employees CASCADE;
DROP TABLE IF EXISTS roles CASCADE;
DROP TABLE IF EXISTS departments CASCADE;

-- 2. Organizational Structure
CREATE TABLE departments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE employees (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    department_id INTEGER NOT NULL REFERENCES departments(id),
    role_id INTEGER NOT NULL REFERENCES roles(id)
);

-- 3. Flexible Hierarchy (Matrix / Directed Graph)
CREATE TABLE reporting_lines (
    supervisor_id INTEGER NOT NULL REFERENCES employees(id),
    subordinate_id INTEGER NOT NULL REFERENCES employees(id),
    PRIMARY KEY (supervisor_id, subordinate_id),
    CHECK (supervisor_id != subordinate_id)
);

-- 4. Status Catalog
CREATE TABLE task_statuses (
    name VARCHAR(50) PRIMARY KEY,
    is_closed BOOLEAN NOT NULL DEFAULT FALSE,
    display_order INTEGER NOT NULL DEFAULT 0
);

-- Seed baseline statuses
INSERT INTO task_statuses (name, is_closed, display_order) VALUES
    ('open',        FALSE, 1),
    ('in_progress', FALSE, 2),
    ('blocked',     FALSE, 3),
    ('review',      FALSE, 4),
    ('completed',   TRUE,  5);

-- 5. Tasks and Event Sourcing
CREATE TABLE tasks (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    assignee_id INTEGER REFERENCES employees(id),
    status VARCHAR(50) NOT NULL DEFAULT 'open' REFERENCES task_statuses(name),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE task_events (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES tasks(id),
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    old_status VARCHAR(50) REFERENCES task_statuses(name),
    new_status VARCHAR(50) NOT NULL REFERENCES task_statuses(name),
    note TEXT,
    raw_message TEXT,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 6. Indexes for Performance
CREATE INDEX employees_department_id_idx ON employees(department_id);
CREATE INDEX employees_role_id_idx ON employees(role_id);
CREATE INDEX reporting_lines_subordinate_id_idx ON reporting_lines(subordinate_id);
CREATE INDEX tasks_assignee_id_idx ON tasks(assignee_id);
CREATE INDEX tasks_status_idx ON tasks(status);
CREATE INDEX task_events_task_id_idx ON task_events(task_id);
CREATE INDEX task_events_new_status_idx ON task_events(new_status);