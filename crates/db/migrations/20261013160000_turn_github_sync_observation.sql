-- A completion callback must acknowledge durable original-history observation.
-- Legacy rows have no such proof: retain them for reconciliation, including old greens.
ALTER TABLE turn_github_sync ADD COLUMN observation_state TEXT NOT NULL DEFAULT 'pending'
    CHECK (observation_state IN ('pending', 'observed', 'failed'));
ALTER TABLE turn_github_sync ADD COLUMN observation_report TEXT;
UPDATE turn_github_sync SET state = 'blocked', report = '{"version":2,"state":"blocked","reason":"completed-turn observation is unproven; original obligation retained"}', retry_at = 0;
CREATE INDEX turn_github_sync_observation ON turn_github_sync(workspace_id, observation_state);
