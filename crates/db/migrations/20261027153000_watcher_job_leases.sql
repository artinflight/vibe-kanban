-- Job authority is reserved BEFORE controlled child inference, retained through
-- child lifetime and crashes. No history is deleted to make room at the quota.
CREATE TABLE watcher_job_leases (
    id BLOB PRIMARY KEY NOT NULL,
    workspace_id BLOB NOT NULL,
    session_id BLOB NOT NULL,
    execution_id BLOB NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now')),
    closed_at TEXT
);
CREATE INDEX watcher_job_leases_owner ON watcher_job_leases(workspace_id,closed_at);

-- Database serialization is shared with native alert reservation, including
-- writers which do not use the in-process lock. A late job cannot gain authority
-- after its parent ends or another alert reserves this workspace.
CREATE TRIGGER watcher_job_parent_fence BEFORE INSERT ON watcher_job_leases
BEGIN
    SELECT RAISE(ABORT,'watcher job parent unavailable') WHERE NOT EXISTS (
        SELECT 1 FROM execution_processes e JOIN sessions s ON s.id=e.session_id
        WHERE e.id=NEW.execution_id AND s.id=NEW.session_id
          AND s.workspace_id=NEW.workspace_id AND e.status='running'
          AND e.run_reason='codingagent'
    );
    SELECT RAISE(ABORT,'watcher owner reserved') WHERE EXISTS (
        SELECT 1 FROM storage_alert_batches b JOIN storage_alert_attempts a
          ON a.attempt_id=b.latest_attempt_id
        WHERE b.workspace_id=NEW.workspace_id AND a.candidate_execution_id != NEW.execution_id
          AND (a.state='in_flight' OR (a.state='accepted' AND (
              NOT EXISTS(SELECT 1 FROM execution_processes e WHERE e.id=a.execution_id)
              OR EXISTS(SELECT 1 FROM execution_processes e WHERE e.id=a.execution_id AND e.status='running')
          )))
    );
END;
CREATE TRIGGER watcher_job_quota BEFORE INSERT ON watcher_job_leases
BEGIN
    SELECT RAISE(ABORT,'watcher job lease quota') WHERE
      (SELECT count(*) FROM watcher_job_leases WHERE workspace_id=NEW.workspace_id)>=4096
      OR (SELECT count(*) FROM watcher_job_leases)>=65536;
END;
CREATE TRIGGER watcher_alert_job_fence BEFORE INSERT ON storage_alert_attempts
WHEN NEW.state='in_flight'
BEGIN
    SELECT RAISE(ABORT,'independent job lifetime unsettled') WHERE EXISTS (
        SELECT 1 FROM watcher_job_leases j JOIN storage_alert_batches b
          ON b.workspace_id=j.workspace_id
        WHERE b.batch_id=NEW.batch_id AND j.closed_at IS NULL
    );
END;
