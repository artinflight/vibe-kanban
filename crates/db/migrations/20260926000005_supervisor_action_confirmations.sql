CREATE TABLE conversation_confirmations (
    id BLOB PRIMARY KEY NOT NULL,
    conversation_id BLOB NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    action_id BLOB NOT NULL UNIQUE REFERENCES conversation_actions(id) ON DELETE CASCADE,
    principal_id BLOB NOT NULL,
    payload_digest TEXT NOT NULL,
    action_revision INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('pending','accepted','rejected','expired')),
    answered_message_id BLOB,
    created_at TEXT NOT NULL DEFAULT (datetime('now','subsec')),
    FOREIGN KEY(conversation_id, answered_message_id) REFERENCES conversation_messages(conversation_id,id)
);
CREATE INDEX conversation_confirmation_owner ON conversation_confirmations(conversation_id,state);
