CREATE TABLE execution_stop_requests (
    request_id BLOB PRIMARY KEY NOT NULL,
    execution_id BLOB NOT NULL,
    session_id BLOB NOT NULL,
    workspace_id BLOB NOT NULL,
    expected_created_at TEXT NOT NULL,
    reason TEXT NOT NULL CHECK(reason IN ('user_request', 'budget_exhausted')),
    status TEXT NOT NULL DEFAULT 'unknown',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
);
