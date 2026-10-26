-- Local board discussion data; participants are display identities, not accounts.
CREATE TABLE local_issue_comments (
    id BLOB PRIMARY KEY NOT NULL CHECK(length(id) = 16),
    issue_id BLOB NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    author_id BLOB REFERENCES local_participants(id),
    parent_id BLOB REFERENCES local_issue_comments(id) ON DELETE CASCADE,
    message TEXT NOT NULL CHECK(length(trim(message)) > 0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX idx_local_issue_comments_issue ON local_issue_comments(issue_id, created_at);
CREATE TABLE local_issue_comment_reactions (
    id BLOB PRIMARY KEY NOT NULL CHECK(length(id) = 16),
    comment_id BLOB NOT NULL REFERENCES local_issue_comments(id) ON DELETE CASCADE,
    user_id BLOB NOT NULL REFERENCES local_participants(id),
    emoji TEXT NOT NULL CHECK(length(trim(emoji)) > 0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE(comment_id, user_id, emoji)
);
