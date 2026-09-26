-- Stable local operator scope. Relay/cloud principals require a separate mapping
-- and must never inherit this installation's trusted-local identity.
CREATE TABLE supervisor_installation_identity (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    authority_id BLOB NOT NULL UNIQUE,
    principal_id BLOB NOT NULL UNIQUE
);
INSERT INTO supervisor_installation_identity (singleton, authority_id, principal_id)
VALUES (1, randomblob(16), randomblob(16));
