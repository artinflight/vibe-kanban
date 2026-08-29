CREATE TABLE local_kanban_tags (
    id BLOB PRIMARY KEY,
    project_id BLOB NOT NULL,
    name TEXT NOT NULL,
    color TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'subsec')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'subsec')),
    UNIQUE(project_id, name)
);

CREATE INDEX idx_local_kanban_tags_project_id
    ON local_kanban_tags(project_id);

CREATE TABLE local_kanban_issue_tags (
    id BLOB PRIMARY KEY,
    issue_id BLOB NOT NULL,
    tag_id BLOB NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'subsec')),
    UNIQUE(issue_id, tag_id),
    FOREIGN KEY(tag_id) REFERENCES local_kanban_tags(id) ON DELETE CASCADE
);

CREATE INDEX idx_local_kanban_issue_tags_issue_id
    ON local_kanban_issue_tags(issue_id);

CREATE INDEX idx_local_kanban_issue_tags_tag_id
    ON local_kanban_issue_tags(tag_id);
