-- Archival intent outbox. This is not a verified archive catalog and grants no
-- authority to delete payloads or exclude them from a backup.
--
-- The archive worker must bind its copy/restore receipt to request_version and
-- recheck requested_state before retiring a source. A flag change during a copy
-- invalidates the old request without destroying its recovery evidence.
CREATE TABLE workspace_archive_requests (
    workspace_id BLOB PRIMARY KEY NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    requested_state TEXT NOT NULL CHECK (requested_state IN ('active', 'archived')),
    request_version INTEGER NOT NULL CHECK (request_version > 0),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- Existing archived work uses the same queue as future archives. No work is
-- dispatched by a migration; the qualified archive consumer remains separate.
INSERT INTO workspace_archive_requests (workspace_id, requested_state, request_version)
SELECT id, 'archived', 1 FROM workspaces WHERE archived = 1;

CREATE TRIGGER workspace_archive_requested_insert
AFTER INSERT ON workspaces WHEN NEW.archived = 1
BEGIN
    INSERT INTO workspace_archive_requests (workspace_id, requested_state, request_version)
    VALUES (NEW.id, 'archived', 1);
END;

CREATE TRIGGER workspace_archive_requested_update
AFTER UPDATE OF archived ON workspaces WHEN OLD.archived != NEW.archived
BEGIN
    INSERT INTO workspace_archive_requests (workspace_id, requested_state, request_version)
    VALUES (NEW.id, CASE WHEN NEW.archived = 1 THEN 'archived' ELSE 'active' END, 1)
    ON CONFLICT(workspace_id) DO UPDATE SET
        requested_state = excluded.requested_state,
        request_version = workspace_archive_requests.request_version + 1,
        updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now');
END;
