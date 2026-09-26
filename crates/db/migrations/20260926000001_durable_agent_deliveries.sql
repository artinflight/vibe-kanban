-- One delivery ledger shared by ordinary session messaging and orchestration.
-- Original target keys survive workspace deletion for honest delivery history.
CREATE TABLE agent_deliveries (
    position INTEGER PRIMARY KEY AUTOINCREMENT,
    id BLOB NOT NULL UNIQUE,
    action_id BLOB,
    source_kind TEXT NOT NULL CHECK (source_kind IN ('session', 'supervisor', 'voice')),
    source_id BLOB NOT NULL,
    idempotency_key BLOB NOT NULL,
    session_id BLOB NOT NULL,
    workspace_id BLOB NOT NULL,
    data TEXT NOT NULL CHECK (json_valid(data)),
    state TEXT NOT NULL CHECK (state IN ('queued', 'waiting_capacity', 'dispatching', 'started', 'completed', 'failed', 'cancelled', 'unknown_delivery')),
    requested_capacity INTEGER NOT NULL CHECK (requested_capacity IN (0, 1)),
    wait_for_capacity INTEGER NOT NULL CHECK (wait_for_capacity IN (0, 1)),
    predecessor_process_id BLOB,
    claim_id BLOB,
    lease_until INTEGER,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    execution_process_id BLOB,
    error TEXT,
    queued_at TEXT NOT NULL DEFAULT (datetime('now', 'subsec')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'subsec')),
    UNIQUE (source_kind, source_id, idempotency_key, session_id),
    CHECK ((state = 'dispatching' AND claim_id IS NOT NULL AND lease_until IS NOT NULL)
        OR (state != 'dispatching' AND lease_until IS NULL))
);
CREATE INDEX agent_delivery_queue ON agent_deliveries(session_id, state, position);
CREATE INDEX agent_delivery_capacity ON agent_deliveries(state, position);
CREATE INDEX agent_delivery_claim ON agent_deliveries(claim_id);
CREATE INDEX agent_delivery_process ON agent_deliveries(execution_process_id);
