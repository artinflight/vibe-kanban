-- One checkpoint obligation per owner execution. Never store source or prompts here.
CREATE TABLE turn_github_sync (
    -- Immutable IDs deliberately outlive explicit deletion of owner metadata.
    execution_process_id BLOB PRIMARY KEY NOT NULL,
    workspace_id BLOB NOT NULL,
    request TEXT NOT NULL,
    writer_group INTEGER,
    state TEXT NOT NULL DEFAULT 'waiting' CHECK (state IN ('waiting', 'pending', 'blocked', 'verified')),
    attempts INTEGER NOT NULL DEFAULT 0,
    retry_at INTEGER NOT NULL DEFAULT 0,
    report TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
);
CREATE INDEX turn_github_sync_pending ON turn_github_sync(state, retry_at);

-- Existing user queues stay private and survive restart. An uncertain dispatch
-- is retained for review rather than automatically replaying the user's work.
CREATE TABLE turn_github_sync_user_queue (
    session_id BLOB PRIMARY KEY NOT NULL,
    workspace_id BLOB NOT NULL,
    data TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('queued', 'dispatching'))
);

-- Persist before waiting on admission. Failed/cancelled handlers retain input
-- privately; uncertain actions are never replayed automatically.
CREATE TABLE turn_github_sync_incoming (
    id BLOB PRIMARY KEY NOT NULL,
    session_id BLOB NOT NULL,
    workspace_id BLOB NOT NULL,
    data TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'received' CHECK (state IN ('received', 'handled', 'dismissed'))
);
