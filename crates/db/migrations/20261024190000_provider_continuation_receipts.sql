-- Additive, forward-only. Fallback must embed this version and all launch fences.
-- Accepted receipts and uncertain ownership survive restart; time never releases them.
CREATE TABLE provider_continuation_receipts (
    request_id BLOB PRIMARY KEY NOT NULL,
    workspace_id BLOB NOT NULL REFERENCES workspaces(id),
    session_id BLOB NOT NULL REFERENCES sessions(id),
    executor TEXT NOT NULL CHECK(executor IN ('CODEX','CLAUDE_CODE')),
    intent_sha256 TEXT NOT NULL CHECK(length(intent_sha256)=64),
    configuration_sha256 TEXT NOT NULL CHECK(length(configuration_sha256)=64),
    intent TEXT NOT NULL CHECK(length(intent)<=262144),
    state_token TEXT NOT NULL,
    predecessor_execution_id BLOB REFERENCES execution_processes(id),
    execution_id BLOB NOT NULL UNIQUE,
    expected_action TEXT NOT NULL CHECK(length(expected_action)<=524288),
    status TEXT NOT NULL DEFAULT 'reserved' CHECK(status IN ('reserved','dispatching','admitted','rejected','unknown')),
    ownership TEXT NOT NULL DEFAULT 'held' CHECK(ownership IN ('held','released')),
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now'))
);
CREATE UNIQUE INDEX provider_continuation_one_owner ON provider_continuation_receipts(workspace_id) WHERE ownership='held';
CREATE TRIGGER provider_continuation_reserve BEFORE INSERT ON provider_continuation_receipts
BEGIN
    SELECT RAISE(ABORT,'provider continuation target mismatch') WHERE NOT EXISTS (
        SELECT 1 FROM sessions WHERE id=NEW.session_id AND workspace_id=NEW.workspace_id AND executor=NEW.executor);
    SELECT RAISE(ABORT,'provider continuation owner running') WHERE EXISTS (
        SELECT 1 FROM execution_processes e JOIN sessions s ON s.id=e.session_id WHERE s.workspace_id=NEW.workspace_id AND e.status='running');
    SELECT RAISE(ABORT,'provider continuation queue pending') WHERE EXISTS (
        SELECT 1 FROM turn_github_sync_user_queue WHERE workspace_id=NEW.workspace_id);
    SELECT RAISE(ABORT,'provider continuation input pending') WHERE EXISTS (
        SELECT 1 FROM turn_github_sync_incoming WHERE workspace_id=NEW.workspace_id AND state='received');
    SELECT RAISE(ABORT,'provider continuation child outcome unknown') WHERE EXISTS (
        SELECT 1 FROM subagent_jobs j JOIN sessions s ON s.id=j.session_id WHERE s.workspace_id=NEW.workspace_id AND j.status NOT IN ('completed','failed'));
    SELECT RAISE(ABORT,'provider handoff already owns workspace') WHERE EXISTS (
        SELECT 1 FROM provider_handoff_reservations WHERE workspace_id=NEW.workspace_id AND state!='released') OR EXISTS (
        SELECT 1 FROM provider_failover_activations WHERE workspace_id=NEW.workspace_id AND state!='released');
    SELECT RAISE(ABORT,'provider continuation stale predecessor') WHERE
        NEW.predecessor_execution_id IS NOT (SELECT id FROM execution_processes WHERE session_id=NEW.session_id AND run_reason='codingagent' AND dropped=0 ORDER BY created_at DESC,rowid DESC LIMIT 1);
END;
CREATE TRIGGER provider_continuation_execution BEFORE INSERT ON execution_processes
BEGIN
    SELECT RAISE(ABORT,'workspace reserved by provider continuation') WHERE EXISTS (
        SELECT 1 FROM provider_continuation_receipts r JOIN sessions s ON s.workspace_id=r.workspace_id
        WHERE s.id=NEW.session_id AND r.ownership='held' AND NOT (
            r.status='dispatching' AND r.session_id=NEW.session_id AND r.execution_id=NEW.id
            AND r.expected_action=NEW.executor_action AND NEW.run_reason='codingagent'));
END;
CREATE TRIGGER provider_continuation_reactivate BEFORE UPDATE OF status ON execution_processes
WHEN NEW.status='running' AND OLD.status!='running'
BEGIN
    SELECT RAISE(ABORT,'workspace has retained continuation ownership') WHERE EXISTS (
        SELECT 1 FROM provider_continuation_receipts r JOIN sessions s ON s.workspace_id=r.workspace_id WHERE s.id=NEW.session_id AND r.ownership='held');
END;
CREATE TRIGGER provider_continuation_identity BEFORE UPDATE ON provider_continuation_receipts
WHEN OLD.request_id!=NEW.request_id OR OLD.workspace_id!=NEW.workspace_id OR OLD.session_id!=NEW.session_id
  OR OLD.executor!=NEW.executor OR OLD.intent_sha256!=NEW.intent_sha256 OR OLD.configuration_sha256!=NEW.configuration_sha256
  OR OLD.intent!=NEW.intent OR OLD.state_token!=NEW.state_token OR OLD.predecessor_execution_id IS NOT NEW.predecessor_execution_id
  OR OLD.execution_id!=NEW.execution_id OR (OLD.expected_action!=NEW.expected_action AND NOT (OLD.status='reserved' AND NEW.status='dispatching'))
BEGIN SELECT RAISE(ABORT,'immutable provider continuation intent'); END;
CREATE TRIGGER provider_continuation_no_delete BEFORE DELETE ON provider_continuation_receipts
BEGIN SELECT RAISE(ABORT,'retain provider continuation receipts'); END;
-- Independent jobs must acquire their normal execution row before effects. Fence
-- new child claims and durable queues too; preserve unrelated workspaces.
CREATE TRIGGER provider_continuation_child BEFORE INSERT ON subagent_jobs
BEGIN
    SELECT RAISE(ABORT,'workspace reserved by another continuation execution') WHERE EXISTS (
        SELECT 1 FROM provider_continuation_receipts r JOIN sessions s ON s.workspace_id=r.workspace_id
        WHERE s.id=NEW.session_id AND r.ownership='held' AND r.execution_id!=NEW.execution_process_id);
END;
CREATE TRIGGER provider_continuation_queue BEFORE INSERT ON turn_github_sync_user_queue
BEGIN
    SELECT RAISE(ABORT,'workspace has retained continuation ownership') WHERE EXISTS (
        SELECT 1 FROM provider_continuation_receipts WHERE workspace_id=NEW.workspace_id AND ownership='held');
END;
CREATE TRIGGER provider_continuation_handoff BEFORE INSERT ON provider_handoff_reservations
BEGIN
    SELECT RAISE(ABORT,'continuation already owns workspace') WHERE EXISTS (
        SELECT 1 FROM provider_continuation_receipts WHERE workspace_id=NEW.workspace_id AND ownership='held');
END;
CREATE TRIGGER provider_continuation_activation BEFORE INSERT ON provider_failover_activations
BEGIN
    SELECT RAISE(ABORT,'continuation already owns workspace') WHERE EXISTS (
        SELECT 1 FROM provider_continuation_receipts WHERE workspace_id=NEW.workspace_id AND ownership='held');
END;
CREATE TRIGGER provider_continuation_child_reactivate BEFORE UPDATE OF status ON subagent_jobs
WHEN NEW.status IN ('running','unresolved','not_found')
BEGIN
    SELECT RAISE(ABORT,'another continuation owns child effects') WHERE EXISTS (
        SELECT 1 FROM provider_continuation_receipts r JOIN sessions s ON s.workspace_id=r.workspace_id
        WHERE s.id=NEW.session_id AND r.ownership='held' AND r.execution_id!=NEW.execution_process_id);
END;
CREATE TRIGGER provider_continuation_session_pin BEFORE UPDATE OF executor,workspace_id,agent_working_dir ON sessions
BEGIN
    SELECT RAISE(ABORT,'continuation session binding is pinned') WHERE EXISTS (
        SELECT 1 FROM provider_continuation_receipts WHERE session_id=OLD.id AND ownership='held')
        AND (OLD.executor IS NOT NEW.executor OR OLD.workspace_id!=NEW.workspace_id OR OLD.agent_working_dir IS NOT NEW.agent_working_dir);
END;
