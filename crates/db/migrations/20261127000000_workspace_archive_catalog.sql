-- The request outbox records desired UI state. These tables record physical
-- custody separately. Only a completed, current cold generation permits a
-- Nightly payload reference; an archived flag never does.
CREATE TABLE workspace_archive_generations (
    workspace_id BLOB NOT NULL,
    request_version INTEGER NOT NULL CHECK (request_version > 0),
    operation_id TEXT NOT NULL UNIQUE,
    manifest_sha256 TEXT NOT NULL CHECK (length(manifest_sha256) = 64),
    manifest TEXT NOT NULL CHECK (json_valid(manifest)),
    recovery_locator TEXT NOT NULL CHECK (json_valid(recovery_locator)),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    PRIMARY KEY (workspace_id, request_version)
);
-- Accepted recovery points outlive workspace deletion and later generations.
CREATE TRIGGER workspace_archive_generation_no_update
BEFORE UPDATE ON workspace_archive_generations
BEGIN SELECT RAISE(ABORT, 'Accepted archive generations are immutable'); END;
CREATE TRIGGER workspace_archive_generation_no_delete
BEFORE DELETE ON workspace_archive_generations
BEGIN SELECT RAISE(ABORT, 'Accepted archive generations require explicit retention review'); END;

CREATE TABLE workspace_archive_state (
    workspace_id BLOB PRIMARY KEY NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    request_version INTEGER NOT NULL CHECK (request_version > 0),
    operation_id TEXT NOT NULL,
    phase TEXT NOT NULL CHECK (phase IN ('preparing','verified','retiring','cold','restoring','active')),
    last_error TEXT,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- Payload is the exact normal follow-up request, including all executor,
-- permission, retry/reset and routing selections. A reserved dispatch is never
-- automatically retried after interruption. Its result must be reconciled.
CREATE TABLE workspace_archive_inputs (
    request_id BLOB PRIMARY KEY NOT NULL,
    workspace_id BLOB NOT NULL REFERENCES workspaces(id),
    session_id BLOB NOT NULL REFERENCES sessions(id),
    payload TEXT NOT NULL CHECK (json_valid(payload)),
    state TEXT NOT NULL CHECK (state IN ('waiting_restore','ready','dispatching','dispatched','held','cancelled')),
    execution_id BLOB,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    CHECK (state != 'dispatched' OR execution_id IS NOT NULL)
);
CREATE INDEX workspace_archive_inputs_pending ON workspace_archive_inputs(workspace_id,state);

-- Physical publication intent is durable before any rename/unlink. Recovery
-- reconciles exact paths and versions under workspace custody; this mutable
-- journal never replaces the immutable B generation or grants exclusion alone.
CREATE TABLE workspace_archive_io (
    operation_id TEXT PRIMARY KEY NOT NULL,
    workspace_id BLOB NOT NULL REFERENCES workspaces(id),
    revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0),
    journal TEXT NOT NULL CHECK (json_valid(journal))
);

-- Warm history reads are durable restore intent, also visible to the mover.
CREATE TABLE workspace_archive_reads (
    workspace_id BLOB PRIMARY KEY NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    requested_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- A protected/offline workspace must not starve later eligible owners.
ALTER TABLE workspace_archive_requests ADD COLUMN last_attempted_at TEXT;
