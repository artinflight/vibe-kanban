-- Assignment identities only: no authentication accounts or permission grants.
CREATE TABLE local_participants (
    id BLOB PRIMARY KEY NOT NULL CHECK(length(id) = 16),
    username TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

INSERT INTO local_participants (id, username, display_name) VALUES
    (X'5EA00000000040008000000000000001', 'seamus', 'Seamus'),
    (X'5EA00000000040008000000000000002', 'dot', 'dot');

CREATE TABLE local_issue_assignees (
    id BLOB PRIMARY KEY NOT NULL CHECK(length(id) = 16),
    issue_id BLOB NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id BLOB NOT NULL REFERENCES local_participants(id),
    assigned_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE(issue_id, user_id)
);

CREATE INDEX idx_local_issue_assignees_user ON local_issue_assignees(user_id, issue_id);
-- Historical tasks/workspaces deliberately remain unassigned and visible.
