UPDATE workspaces SET task_id=?,updated_at=strftime('%Y-%m-%d %H:%M:%f','now')
WHERE id=? AND task_id=? AND archived=0 AND worktree_deleted=0
AND COALESCE((SELECT revision FROM workspace_issue_link_revisions WHERE workspace_id=workspaces.id),0)=?
AND EXISTS(SELECT 1 FROM tasks old JOIN tasks next ON next.project_id=old.project_id
           JOIN projects p ON p.id=old.project_id
           WHERE old.id=workspaces.task_id AND next.id=? AND p.id=?
           AND p.remote_project_id IS NULL AND p.archived=0)
