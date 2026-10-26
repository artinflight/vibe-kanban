-- One handoff per exact source checkpoint, including uncertain/cancelled dispatch.
-- Retain source sessions/history. A reservation is never a replay instruction.
CREATE TABLE claude_codex_handoffs (
    request_id BLOB PRIMARY KEY NOT NULL,
    session_id BLOB NOT NULL UNIQUE REFERENCES sessions(id),
    execution_id BLOB NOT NULL UNIQUE REFERENCES execution_processes(id),
    request_sha256 TEXT NOT NULL,
    context_sha256 TEXT NOT NULL,
    target_session_id BLOB NOT NULL UNIQUE,
    target_execution_id BLOB,
    status TEXT NOT NULL DEFAULT 'unknown' CHECK(status IN ('unknown', 'started'))
);
