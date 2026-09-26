-- Records belong to the owning supervisor conversation. They never replace or
-- rewrite the session/process sources they describe.
CREATE TABLE conversation_actions (
    id BLOB PRIMARY KEY NOT NULL,
    conversation_id BLOB NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    request_id BLOB NOT NULL,
    run_id BLOB REFERENCES conversation_runs(id),
    origin_message_id BLOB NOT NULL,
    intent_kind TEXT NOT NULL,
    payload TEXT NOT NULL CHECK (json_valid(payload)),
    payload_digest TEXT NOT NULL,
    route_evidence TEXT NOT NULL CHECK (json_valid(route_evidence)),
    authorisation_source TEXT,
    state TEXT NOT NULL CHECK (state IN ('proposed','approved','dispatching','succeeded','failed','cancelled','rejected','unknown_delivery')),
    revision INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now','subsec')),
    UNIQUE (conversation_id, request_id),
    FOREIGN KEY (conversation_id, origin_message_id) REFERENCES conversation_messages(conversation_id, id)
);
CREATE INDEX conversation_action_state ON conversation_actions(conversation_id,state);

CREATE TABLE conversation_evidence (
    id BLOB PRIMARY KEY NOT NULL,
    conversation_id BLOB NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    source TEXT NOT NULL CHECK (json_valid(source)),
    source_revision TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    availability TEXT NOT NULL CHECK (availability IN ('retained','unavailable')),
    raw_report TEXT,
    captured_at TEXT NOT NULL DEFAULT (datetime('now','subsec')),
    UNIQUE (conversation_id, source, source_revision),
    UNIQUE (conversation_id, id)
);
CREATE TABLE conversation_message_evidence (
    conversation_id BLOB NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    message_id BLOB NOT NULL,
    evidence_id BLOB NOT NULL,
    relationship TEXT NOT NULL CHECK (relationship IN ('summarised','quoted','supporting')),
    PRIMARY KEY (message_id, evidence_id),
    FOREIGN KEY (conversation_id, message_id) REFERENCES conversation_messages(conversation_id,id) ON DELETE CASCADE,
    FOREIGN KEY (conversation_id, evidence_id) REFERENCES conversation_evidence(conversation_id,id) ON DELETE CASCADE
);

CREATE TABLE conversation_memory (
    id BLOB PRIMARY KEY NOT NULL,
    conversation_id BLOB NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    scope_kind TEXT NOT NULL CHECK (scope_kind IN ('global','project','repository','workspace','conversation','session')),
    scope_id BLOB NOT NULL,
    claim_key TEXT NOT NULL,
    body TEXT NOT NULL,
    entity_refs TEXT NOT NULL CHECK (json_valid(entity_refs)),
    state TEXT NOT NULL CHECK (state IN ('proposed','active','superseded','retracted')),
    revision INTEGER NOT NULL DEFAULT 1,
    supersedes_id BLOB,
    source_message_id BLOB NOT NULL,
    author_kind TEXT NOT NULL CHECK (author_kind IN ('user','inferred')),
    valid_until TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now','subsec')),
    FOREIGN KEY (conversation_id, source_message_id) REFERENCES conversation_messages(conversation_id,id)
);
CREATE UNIQUE INDEX conversation_memory_current ON conversation_memory(conversation_id,scope_kind,scope_id,claim_key) WHERE state IN ('active','proposed');
CREATE INDEX conversation_memory_scope ON conversation_memory(conversation_id,scope_kind,scope_id,state);
-- Forgetting blocks re-extraction from the forgotten source while allowing a
-- later explicit instruction to establish a new preference.
CREATE TABLE conversation_forgotten_memory (
    conversation_id BLOB NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    source_message_id BLOB NOT NULL,
    claim_key TEXT NOT NULL,
    scope_kind TEXT NOT NULL,
    scope_id BLOB NOT NULL,
    PRIMARY KEY (conversation_id,source_message_id,claim_key,scope_kind,scope_id)
);
CREATE TABLE conversation_context (
    conversation_id BLOB PRIMARY KEY NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    revision INTEGER NOT NULL DEFAULT 1,
    summary TEXT NOT NULL DEFAULT '',
    covered_through_seq INTEGER NOT NULL DEFAULT 0,
    source_versions TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(source_versions)),
    invalidated_at TEXT
);
