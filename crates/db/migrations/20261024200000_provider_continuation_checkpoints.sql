-- Forward-only trusted checkpoint bridge. Preserve in candidate AND fallback.
-- Only backend lifecycle code publishes evidence; no HTTP checkpoint mint route.
CREATE TABLE provider_continuation_checkpoints (
    reference TEXT PRIMARY KEY NOT NULL CHECK(length(reference)<=256),
    workspace_id BLOB NOT NULL REFERENCES workspaces(id),
    source_execution_id BLOB NOT NULL REFERENCES execution_processes(id),
    destination_session_id BLOB NOT NULL REFERENCES sessions(id),
    target_token TEXT NOT NULL,
    work_id TEXT NOT NULL,
    owner_generation TEXT NOT NULL,
    legacy_transition TEXT,
    evidence TEXT NOT NULL CHECK(length(evidence)<=262144),
    valid_until_ms INTEGER NOT NULL,
    claimed_request BLOB UNIQUE REFERENCES provider_continuation_receipts(request_id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TRIGGER provider_checkpoint_immutable BEFORE UPDATE ON provider_continuation_checkpoints
WHEN OLD.reference!=NEW.reference OR OLD.workspace_id!=NEW.workspace_id
 OR OLD.source_execution_id!=NEW.source_execution_id OR OLD.destination_session_id!=NEW.destination_session_id
 OR OLD.target_token!=NEW.target_token OR OLD.work_id!=NEW.work_id OR OLD.owner_generation!=NEW.owner_generation
 OR OLD.legacy_transition IS NOT NEW.legacy_transition OR OLD.evidence!=NEW.evidence OR OLD.valid_until_ms!=NEW.valid_until_ms
 OR (OLD.claimed_request IS NOT NULL AND OLD.claimed_request IS NOT NEW.claimed_request)
BEGIN SELECT RAISE(ABORT,'immutable trusted checkpoint or claim'); END;
CREATE TRIGGER provider_checkpoint_no_delete BEFORE DELETE ON provider_continuation_checkpoints
BEGIN SELECT RAISE(ABORT,'retain checkpoint and side-effect evidence'); END;
CREATE TRIGGER provider_checkpoint_claim_binding BEFORE INSERT ON provider_continuation_receipts
WHEN json_extract(NEW.intent,'$.checkpoint_receipt') IS NOT NULL
BEGIN
 SELECT RAISE(ABORT,'checkpoint not exclusively claimed for exact continuation') WHERE NOT EXISTS (
   SELECT 1 FROM provider_continuation_checkpoints c WHERE c.reference=json_extract(NEW.intent,'$.checkpoint_receipt')
   AND c.claimed_request=NEW.request_id AND c.workspace_id=NEW.workspace_id
   AND c.destination_session_id=NEW.session_id AND c.target_token=NEW.state_token);
END;
CREATE INDEX provider_checkpoint_destination ON provider_continuation_checkpoints(destination_session_id,target_token,valid_until_ms) WHERE claimed_request IS NULL;
