CREATE TABLE workspace_cleanup_requests (
    workspace_id BLOB PRIMARY KEY NOT NULL,
    requested_at TEXT NOT NULL DEFAULT (datetime('now', 'subsec')),
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);

-- Recover terminal-linked workspaces that were archived by the earlier
-- status-transition implementation but skipped while an execution was active.
INSERT OR IGNORE INTO workspace_cleanup_requests (workspace_id)
SELECT w.id
FROM workspaces w
JOIN tasks t ON t.id = w.task_id
WHERE w.archived = TRUE
  AND w.worktree_deleted = FALSE
  AND (
    t.status = 'done'
    OR lower(t.description) LIKE '%original status: in staging%'
    OR lower(t.description) LIKE '%original status: done%'
    OR lower(t.description) LIKE '%original status: completed%'
  );
