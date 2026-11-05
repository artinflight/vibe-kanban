-- Forward-only additive ownership state. Candidate AND fallback must embed this
-- exact SQLx version/checksum and retain the pre-start/side-effect fences.
-- An older binary's VersionMissing is a HOLD, never authority to unregister the
-- migration, drop these tables/triggers, erase reservations or restore stale data.
-- See VK_PROVIDER_LAUNCH_RECONCILIATION.md for exact-artifact/latest-data rehearsal.
-- Dormant until an explicitly authorized host prepares a provider handoff.
-- No lease expiry releases ownership: ambiguous/failed launches require reconciliation.
CREATE TABLE provider_handoff_reservations (
    transition_id TEXT PRIMARY KEY NOT NULL,
    workspace_id BLOB NOT NULL REFERENCES workspaces(id),
    previous_execution_id BLOB NOT NULL REFERENCES execution_processes(id),
    next_session_id BLOB NOT NULL REFERENCES sessions(id),
    next_execution_id BLOB NOT NULL UNIQUE,
    expected_action TEXT NOT NULL CHECK(length(expected_action) <= 65536),
    snapshot_receipt TEXT NOT NULL,
    ownership_fence TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('reserved','dispatching','running','held','checkpoint_required','released')),
    reason TEXT NOT NULL DEFAULT ''
);
CREATE UNIQUE INDEX provider_handoff_one_workspace_owner
    ON provider_handoff_reservations(workspace_id) WHERE state != 'released';
CREATE TRIGGER provider_handoff_reserve_stopped BEFORE INSERT ON provider_handoff_reservations
BEGIN
    SELECT RAISE(ABORT, 'provider handoff predecessor/workspace is not terminal')
    WHERE NOT EXISTS (
        SELECT 1 FROM execution_processes e JOIN sessions s ON s.id=e.session_id
        WHERE e.id=NEW.previous_execution_id AND s.workspace_id=NEW.workspace_id
          AND e.status IN ('completed','failed','killed') AND e.run_reason='codingagent'
    );
    SELECT RAISE(ABORT, 'provider handoff workspace has a running owner')
    WHERE EXISTS (SELECT 1 FROM execution_processes e JOIN sessions s ON s.id=e.session_id
                  WHERE s.workspace_id=NEW.workspace_id AND e.status='running');
    SELECT RAISE(ABORT, 'provider handoff requires a fresh provider-native session')
    WHERE NOT EXISTS (SELECT 1 FROM sessions s WHERE s.id=NEW.next_session_id
                      AND s.workspace_id=NEW.workspace_id AND s.executor IN ('CLAUDE_CODE','CODEX'))
       OR EXISTS (SELECT 1 FROM execution_processes WHERE session_id=NEW.next_session_id);
END;
-- This guards ALL existing launch callers, not just the new dispatcher. A caller
-- that passed an earlier in-memory check still cannot race the durable reservation.
CREATE TRIGGER provider_handoff_execution_fence BEFORE INSERT ON execution_processes
BEGIN
    SELECT RAISE(ABORT, 'workspace reserved by provider handoff; reconcile before starting')
    WHERE EXISTS (
        SELECT 1 FROM provider_handoff_reservations r JOIN sessions s ON s.workspace_id=r.workspace_id
        WHERE s.id=NEW.session_id AND r.state!='released'
          AND NOT (r.state='dispatching' AND r.next_session_id=NEW.session_id
                   AND r.next_execution_id=NEW.id AND r.expected_action=NEW.executor_action
                   AND NEW.run_reason='codingagent' AND s.executor IN ('CLAUDE_CODE','CODEX'))
    );
END;
CREATE TRIGGER provider_handoff_reactivation_fence BEFORE UPDATE OF status ON execution_processes
WHEN NEW.status='running' AND OLD.status!='running'
BEGIN
    SELECT RAISE(ABORT, 'workspace reserved; stopped execution cannot reactivate')
    WHERE EXISTS (SELECT 1 FROM provider_handoff_reservations r JOIN sessions s ON s.workspace_id=r.workspace_id
                  WHERE s.id=NEW.session_id AND r.state!='released');
END;
-- Explicit opt-in owner survives host restart; no global enrollment/default change.
CREATE TABLE provider_failover_activations (
    workspace_id BLOB PRIMARY KEY NOT NULL REFERENCES workspaces(id),
    work_id TEXT NOT NULL UNIQUE,
    initial_execution_id BLOB NOT NULL UNIQUE REFERENCES execution_processes(id),
    journal_root TEXT NOT NULL,
    source_receipt TEXT NOT NULL,
    owner_generation TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('active','held','released')),
    reason TEXT NOT NULL DEFAULT ''
);
CREATE TRIGGER provider_activation_owner BEFORE INSERT ON provider_failover_activations
BEGIN
    SELECT RAISE(ABORT, 'provider activation execution/workspace mismatch')
    WHERE NOT EXISTS (SELECT 1 FROM execution_processes e JOIN sessions s ON s.id=e.session_id
                      WHERE e.id=NEW.initial_execution_id AND s.workspace_id=NEW.workspace_id AND e.run_reason='codingagent');
    SELECT RAISE(ABORT, 'provider activation has another running owner')
    WHERE EXISTS (SELECT 1 FROM execution_processes e JOIN sessions s ON s.id=e.session_id
                  WHERE s.workspace_id=NEW.workspace_id AND e.status='running' AND e.id!=NEW.initial_execution_id);
END;
CREATE TRIGGER provider_activation_execution_fence BEFORE INSERT ON execution_processes
BEGIN
    SELECT RAISE(ABORT, 'workspace has an activated provider owner; explicit checkpoint dispatch required')
    WHERE EXISTS (SELECT 1 FROM provider_failover_activations a JOIN sessions s ON s.workspace_id=a.workspace_id
                  WHERE s.id=NEW.session_id AND a.state!='released')
    AND NOT EXISTS (SELECT 1 FROM provider_handoff_reservations r
                    WHERE r.state='dispatching' AND r.next_execution_id=NEW.id
                      AND r.next_session_id=NEW.session_id AND r.expected_action=NEW.executor_action);
END;
CREATE TRIGGER provider_activation_reactivation_fence BEFORE UPDATE OF status ON execution_processes
WHEN NEW.status='running' AND OLD.status!='running'
BEGIN
    SELECT RAISE(ABORT, 'activated provider owner cannot reactivate a stopped execution')
    WHERE EXISTS (SELECT 1 FROM provider_failover_activations a JOIN sessions s ON s.workspace_id=a.workspace_id
                  WHERE s.id=NEW.session_id AND a.state!='released');
END;
