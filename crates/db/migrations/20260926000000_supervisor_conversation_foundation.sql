-- Supervisor-only history. Ordinary session logs and prompts remain authoritative
-- for direct workspace chat and are intentionally not migrated into these tables.
CREATE TABLE conversations (
    id BLOB PRIMARY KEY NOT NULL,
    authority_id BLOB NOT NULL,
    principal_id BLOB NOT NULL,
    next_seq INTEGER NOT NULL DEFAULT 1 CHECK (next_seq >= 1),
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'subsec')),
    archived_at TEXT,
    UNIQUE (authority_id, principal_id)
);

CREATE TABLE conversation_messages (
    id BLOB PRIMARY KEY NOT NULL,
    conversation_id BLOB NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    created_seq INTEGER NOT NULL CHECK (created_seq >= 1),
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    origin TEXT NOT NULL CHECK (origin IN ('typed', 'voice', 'agent', 'derived', 'system')),
    body TEXT NOT NULL CHECK (length(CAST(body AS BLOB)) BETWEEN 1 AND 65536),
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
    status TEXT NOT NULL CHECK (status IN ('accepted', 'final')),
    reply_to_id BLOB,
    client_message_id BLOB,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'subsec')),
    UNIQUE (conversation_id, id),
    UNIQUE (conversation_id, created_seq),
    UNIQUE (conversation_id, client_message_id),
    FOREIGN KEY (conversation_id, reply_to_id)
        REFERENCES conversation_messages(conversation_id, id)
);

CREATE TABLE conversation_runs (
    id BLOB PRIMARY KEY NOT NULL,
    conversation_id BLOB NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    input_message_id BLOB NOT NULL,
    input_revision INTEGER NOT NULL DEFAULT 1,
    accepted_seq INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed', 'interrupted', 'cancelled')),
    generation INTEGER NOT NULL DEFAULT 0 CHECK (generation >= 0),
    lease_owner BLOB,
    lease_until INTEGER,
    context_manifest TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(context_manifest)),
    model_config TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(model_config)),
    usage TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(usage)),
    error TEXT,
    output_message_id BLOB,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'subsec')),
    UNIQUE (input_message_id),
    FOREIGN KEY (conversation_id, input_message_id)
        REFERENCES conversation_messages(conversation_id, id),
    FOREIGN KEY (conversation_id, output_message_id)
        REFERENCES conversation_messages(conversation_id, id),
    CHECK ((status = 'running' AND lease_owner IS NOT NULL AND lease_until IS NOT NULL)
        OR (status != 'running' AND lease_owner IS NULL AND lease_until IS NULL))
);
CREATE UNIQUE INDEX conversation_one_running
    ON conversation_runs(conversation_id) WHERE status = 'running';
CREATE INDEX conversation_pending_runs
    ON conversation_runs(status, conversation_id, accepted_seq);

CREATE TABLE conversation_events (
    conversation_id BLOB NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    seq INTEGER NOT NULL CHECK (seq >= 1),
    event_id BLOB NOT NULL UNIQUE,
    type TEXT NOT NULL,
    schema_version INTEGER NOT NULL DEFAULT 1,
    entity_id BLOB NOT NULL,
    revision INTEGER NOT NULL,
    payload TEXT NOT NULL CHECK (json_valid(payload)),
    occurred_at TEXT NOT NULL DEFAULT (datetime('now', 'subsec')),
    PRIMARY KEY (conversation_id, seq)
);
