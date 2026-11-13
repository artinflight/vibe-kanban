-- Additive migration for the supported backend; never run against live Vibe here.
CREATE TABLE workspace_review_intent (
    workspace_id BLOB PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
    held INTEGER NOT NULL DEFAULT 0 CHECK (held IN (0,1)),
    version INTEGER NOT NULL DEFAULT 0 CHECK (version >= 0)
);
CREATE TABLE workspace_review_receipts (
    receipt_id TEXT PRIMARY KEY,
    event_key TEXT NOT NULL UNIQUE,
    -- Immutable audit identities intentionally outlive deletion of their parents.
    -- These are historical IDs, not live foreign-key references. The route
    -- validates live ownership before inserting; proof retains exact identity.
    workspace_id BLOB NOT NULL,
    execution_id BLOB NOT NULL,
    payload_hash TEXT NOT NULL,
    proof TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE workspace_review_hold_events (
    workspace_id BLOB NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    event_id TEXT NOT NULL,
    held INTEGER NOT NULL,
    source TEXT NOT NULL,
    PRIMARY KEY (workspace_id,event_id)
);
-- Only the successfully drained, flushed and synced native writer publishes this.
-- Never backfill historical closure from status/completed_at alone.
CREATE TABLE workspace_review_log_finalized (
    execution_id BLOB PRIMARY KEY REFERENCES execution_processes(id) ON DELETE CASCADE,
    finalized_at TEXT NOT NULL,
    raw_bytes INTEGER NOT NULL CHECK (raw_bytes > 0),
    raw_sha256 TEXT NOT NULL CHECK (length(raw_sha256) = 64)
);
-- A changed existing reply must reappear even if it races AFTER acknowledgement.
-- Seen-only writes do not fire this trigger, so duplicates cannot fabricate work.
CREATE TRIGGER reviewed_message_changed AFTER UPDATE OF summary,agent_message_id ON coding_agent_turns
WHEN OLD.summary IS NOT NEW.summary OR OLD.agent_message_id IS NOT NEW.agent_message_id
BEGIN
    UPDATE coding_agent_turns SET seen=0 WHERE id=NEW.id;
END;
