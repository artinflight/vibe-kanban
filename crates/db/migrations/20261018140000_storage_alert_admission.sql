-- Private durable receipts intentionally outlive owner/history deletion.
CREATE TABLE storage_alert_batches (
    batch_id BLOB PRIMARY KEY NOT NULL,
    workspace_id BLOB NOT NULL,
    session_id BLOB NOT NULL,
    intent_sha256 TEXT NOT NULL,
    intent TEXT NOT NULL,
    latest_attempt_id BLOB
);
CREATE TABLE storage_alert_attempts (
    attempt_id BLOB PRIMARY KEY NOT NULL,
    batch_id BLOB NOT NULL REFERENCES storage_alert_batches(batch_id),
    validation TEXT NOT NULL,
    candidate_execution_id BLOB NOT NULL UNIQUE,
    state TEXT NOT NULL CHECK(state IN ('in_flight', 'accepted', 'deferred', 'rejected')),
    reason TEXT NOT NULL,
    execution_id BLOB,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
    CHECK ((state = 'accepted') = (execution_id IS NOT NULL))
);
CREATE TABLE storage_alert_incidents (
    workspace_id BLOB NOT NULL,
    incident_id BLOB NOT NULL,
    batch_id BLOB NOT NULL REFERENCES storage_alert_batches(batch_id),
    PRIMARY KEY(workspace_id, incident_id)
);
CREATE INDEX storage_alert_batches_owner ON storage_alert_batches(workspace_id);
CREATE INDEX storage_alert_attempts_batch ON storage_alert_attempts(batch_id);
CREATE INDEX storage_alert_incidents_batch ON storage_alert_incidents(batch_id);

-- A cancelled/failed attempt's reserved UUID can never launch late. This also
-- fences an old handler when a client cancels an unbound in-flight request.
CREATE TRIGGER storage_alert_execution_fence BEFORE INSERT ON execution_processes
WHEN EXISTS (SELECT 1 FROM storage_alert_attempts WHERE candidate_execution_id = NEW.id)
BEGIN
    SELECT RAISE(ABORT, 'storage alert attempt fenced') WHERE NOT EXISTS (
        SELECT 1 FROM storage_alert_attempts a JOIN storage_alert_batches b USING(batch_id)
        WHERE a.candidate_execution_id = NEW.id AND a.state = 'in_flight'
          AND b.latest_attempt_id = a.attempt_id AND b.session_id = NEW.session_id
          AND NEW.run_reason = 'codingagent'
    );
END;

-- All native execution creation shares this fence, including callers outside
-- the HTTP route. Dev servers are independent; scripts/coding work are not.
CREATE TRIGGER storage_alert_owner_fence BEFORE INSERT ON execution_processes
WHEN NEW.run_reason != 'devserver'
BEGIN
    SELECT RAISE(ABORT, 'storage alert owner reserved') WHERE EXISTS (
        SELECT 1 FROM storage_alert_batches b
        JOIN storage_alert_attempts a ON a.attempt_id = b.latest_attempt_id
        WHERE b.workspace_id = (SELECT workspace_id FROM sessions WHERE id = NEW.session_id)
          AND a.candidate_execution_id != NEW.id
          AND (a.state = 'in_flight' OR (a.state = 'accepted' AND (NOT EXISTS (
              SELECT 1 FROM execution_processes ep WHERE ep.id = a.execution_id
          ) OR EXISTS (
              SELECT 1 FROM execution_processes ep WHERE ep.id = a.execution_id AND ep.status = 'running'
          ))))
    );
END;

-- Receipt and exact native execution commit in the SAME transaction. No
-- response/acknowledgement or bounded history read is needed to recover it.
CREATE TRIGGER storage_alert_execution_binding AFTER INSERT ON execution_processes
BEGIN
    UPDATE storage_alert_attempts SET state = 'accepted', reason = 'execution_bound', execution_id = NEW.id
    WHERE candidate_execution_id = NEW.id AND state = 'in_flight';
END;
