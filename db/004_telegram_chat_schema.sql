-- 1. Telegram Authentication Mapping
CREATE TABLE IF NOT EXISTS authorized_users (
    telegram_id BIGINT PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. Chat Sessions (Threads)
CREATE TABLE IF NOT EXISTS chat_threads (
    thread_id UUID PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

-- 3. Atomic Conversational Turns
CREATE TABLE IF NOT EXISTS chat_messages (
    id BIGSERIAL PRIMARY KEY,
    thread_id UUID NOT NULL REFERENCES chat_threads(thread_id) ON DELETE CASCADE,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('system', 'user', 'assistant', 'tool')),
    content TEXT,
    tool_call_id VARCHAR(64),
    tool_calls JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 4. High-Performance Lookup Indexes
CREATE INDEX idx_auth_users_emp ON authorized_users(employee_id);
CREATE INDEX idx_chat_threads_active ON chat_threads(employee_id, is_active);
CREATE INDEX idx_chat_msgs_thread_order ON chat_messages(thread_id, id ASC);