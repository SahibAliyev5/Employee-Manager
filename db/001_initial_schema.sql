-- 001_initial_schema.sql
-- Hermes employee management system - state-transition event sourcing schema

CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE TEXT SEARCH DICTIONARY az_unaccent (
    TEMPLATE = unaccent,
    RULES    = 'az'
);

CREATE TEXT SEARCH CONFIGURATION az ( COPY = pg_catalog.simple );

ALTER TEXT SEARCH CONFIGURATION az
    ALTER MAPPING FOR word, asciiword, hword, hword_part, asciihword, numword
    WITH az_unaccent, simple;

CREATE TABLE employees (
    id   SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(100)
);

CREATE TABLE tasks (
    id          SERIAL PRIMARY KEY,
    title       VARCHAR(255) NOT NULL,
    description TEXT,
    assignee_id INTEGER REFERENCES employees(id),
    status      VARCHAR(50) NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'in_progress', 'blocked', 'review', 'completed')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE task_events (
    id          SERIAL PRIMARY KEY,
    task_id     INTEGER NOT NULL REFERENCES tasks(id),
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    old_status  VARCHAR(50)
        CHECK (old_status IN ('open', 'in_progress', 'blocked', 'review', 'completed')),
    new_status  VARCHAR(50) NOT NULL
        CHECK (new_status IN ('open', 'in_progress', 'blocked', 'review', 'completed')),
    note        TEXT,
    raw_message TEXT,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    search_vector TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('az', coalesce(note, '') || ' ' || coalesce(raw_message, ''))
    ) STORED
);

CREATE INDEX task_events_search_idx   ON task_events USING GIN (search_vector);
CREATE INDEX task_events_task_id_idx  ON task_events (task_id);
CREATE INDEX tasks_assignee_id_idx    ON tasks (assignee_id);