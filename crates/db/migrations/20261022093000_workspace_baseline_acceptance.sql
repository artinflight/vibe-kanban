-- Additive compatibility foundation only. No authorization issuance in this delta.
CREATE TABLE workspace_baseline_acceptance (
 authorization_id TEXT PRIMARY KEY NOT NULL,
 workspace_id BLOB NOT NULL,
 session_id BLOB NOT NULL,
 execution_id BLOB NOT NULL UNIQUE,
 reviewed_sha256 TEXT NOT NULL,
 binding_json TEXT NOT NULL,
 operator_evidence_sha256 TEXT NOT NULL,
 expires_at INTEGER NOT NULL,
 state TEXT NOT NULL CHECK (state IN ('approved','spent_held','spawn_confirmed')),
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now'))
);
CREATE INDEX workspace_baseline_acceptance_workspace ON workspace_baseline_acceptance(workspace_id);
-- Preserve all historical rows and prohibit rollback/reuse of consumed acceptance.
CREATE TRIGGER baseline_acceptance_no_delete BEFORE DELETE ON workspace_baseline_acceptance
BEGIN SELECT RAISE(ABORT, 'baseline acceptance evidence is retained'); END;
CREATE TRIGGER baseline_acceptance_immutable_binding BEFORE UPDATE ON workspace_baseline_acceptance
WHEN OLD.authorization_id IS NOT NEW.authorization_id OR OLD.workspace_id IS NOT NEW.workspace_id
 OR OLD.session_id IS NOT NEW.session_id OR OLD.execution_id IS NOT NEW.execution_id
 OR OLD.reviewed_sha256 IS NOT NEW.reviewed_sha256 OR OLD.binding_json IS NOT NEW.binding_json
 OR OLD.operator_evidence_sha256 IS NOT NEW.operator_evidence_sha256 OR OLD.expires_at IS NOT NEW.expires_at
 OR OLD.created_at IS NOT NEW.created_at
BEGIN SELECT RAISE(ABORT, 'baseline acceptance binding is immutable'); END;
CREATE TRIGGER baseline_acceptance_monotonic BEFORE UPDATE OF state ON workspace_baseline_acceptance
WHEN NOT (OLD.state = NEW.state OR (OLD.state = 'approved' AND NEW.state = 'spent_held')
 OR (OLD.state = 'spent_held' AND NEW.state = 'spawn_confirmed'))
BEGIN SELECT RAISE(ABORT, 'baseline acceptance cannot be refunded'); END;

-- BEFORE INSERT executes before uniqueness replacement; do not permit REPLACE to erase evidence.
CREATE TRIGGER baseline_acceptance_no_replacement BEFORE INSERT ON workspace_baseline_acceptance
WHEN EXISTS(SELECT 1 FROM workspace_baseline_acceptance
 WHERE authorization_id = NEW.authorization_id OR execution_id = NEW.execution_id)
BEGIN SELECT RAISE(ABORT, 'baseline acceptance cannot replace retained evidence'); END;
