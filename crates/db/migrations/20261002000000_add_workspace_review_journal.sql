-- An independent history of flag writes makes a specific pre-change state recoverable.
CREATE TABLE IF NOT EXISTS workspace_review_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    action TEXT NOT NULL CHECK (action IN ('insert', 'update', 'delete')),
    turn_id BLOB NOT NULL,
    execution_process_id BLOB NOT NULL,
    session_id BLOB,
    workspace_id BLOB,
    old_seen INTEGER,
    new_seen INTEGER,
    old_updated_at TEXT,
    new_updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_workspace_review_events_workspace
    ON workspace_review_events(workspace_id, sequence);

CREATE TRIGGER IF NOT EXISTS workspace_review_insert
AFTER INSERT ON coding_agent_turns
BEGIN
    INSERT INTO workspace_review_events (
        action, turn_id, execution_process_id, session_id, workspace_id,
        new_seen, new_updated_at
    ) VALUES (
        'insert', NEW.id, NEW.execution_process_id,
        (SELECT session_id FROM execution_processes WHERE id = NEW.execution_process_id),
        (SELECT s.workspace_id FROM sessions s JOIN execution_processes e
         ON e.session_id = s.id WHERE e.id = NEW.execution_process_id),
        NEW.seen, NEW.updated_at
    );
END;

CREATE TRIGGER IF NOT EXISTS workspace_review_update
AFTER UPDATE OF seen ON coding_agent_turns
WHEN OLD.seen != NEW.seen OR OLD.updated_at != NEW.updated_at
BEGIN
    INSERT INTO workspace_review_events (
        action, turn_id, execution_process_id, session_id, workspace_id,
        old_seen, new_seen, old_updated_at, new_updated_at
    ) VALUES (
        'update', NEW.id, NEW.execution_process_id,
        (SELECT session_id FROM execution_processes WHERE id = NEW.execution_process_id),
        (SELECT s.workspace_id FROM sessions s JOIN execution_processes e
         ON e.session_id = s.id WHERE e.id = NEW.execution_process_id),
        OLD.seen, NEW.seen, OLD.updated_at, NEW.updated_at
    );
END;

CREATE TRIGGER IF NOT EXISTS workspace_review_delete
BEFORE DELETE ON coding_agent_turns
BEGIN
    INSERT INTO workspace_review_events (
        action, turn_id, execution_process_id, session_id, workspace_id,
        old_seen, old_updated_at
    ) VALUES (
        'delete', OLD.id, OLD.execution_process_id,
        (SELECT session_id FROM execution_processes WHERE id = OLD.execution_process_id),
        (SELECT s.workspace_id FROM sessions s JOIN execution_processes e
         ON e.session_id = s.id WHERE e.id = OLD.execution_process_id),
        OLD.seen, OLD.updated_at
    );
END;
