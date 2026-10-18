-- Reserve before native dispatch. An unfinished reservation is uncertain and
-- must never be replayed after cancellation, a lost response or a restart.
CREATE TABLE session_steering_receipts (
    request_id BLOB PRIMARY KEY NOT NULL,
    session_id BLOB NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    execution_id BLOB NOT NULL,
    thread_id TEXT NOT NULL,
    turn_id TEXT NOT NULL,
    message_sha256 TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'unknown',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX session_steering_receipts_session ON session_steering_receipts(session_id);
