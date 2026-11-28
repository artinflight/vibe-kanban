UPDATE issue_workflows SET phase='launching',updated_at=strftime('%Y-%m-%d %H:%M:%f','now')
WHERE request_id=? AND request_hash=? AND operation='start' AND phase='reserved' AND chat_completed=1
AND EXISTS(SELECT 1 FROM workspaces w JOIN tasks t ON t.id=w.task_id
           JOIN projects p ON p.id=t.project_id JOIN sessions s ON s.workspace_id=w.id
           JOIN local_issue_assignees a ON a.issue_id=t.id
           WHERE w.id=issue_workflows.workspace_id AND t.id=issue_workflows.issue_id
           AND p.id=issue_workflows.project_id AND p.archived=0 AND p.remote_project_id IS NULL
           AND w.archived=0 AND w.worktree_deleted=0 AND s.id=issue_workflows.session_id
           AND a.user_id=issue_workflows.dot_user_id
           AND EXISTS(SELECT 1 FROM local_participants d WHERE d.id=a.user_id AND d.username='dot')
           AND COALESCE((SELECT revision FROM workspace_issue_link_revisions WHERE workspace_id=w.id),0)=issue_workflows.link_revision)
AND NOT EXISTS(SELECT 1 FROM execution_processes e JOIN sessions s ON s.id=e.session_id WHERE s.workspace_id=issue_workflows.workspace_id)
AND EXISTS(SELECT 1 FROM workspace_repos wr WHERE wr.workspace_id=issue_workflows.workspace_id)
AND NOT EXISTS(SELECT 1 FROM workspace_repos wr WHERE wr.workspace_id=issue_workflows.workspace_id
    AND NOT EXISTS(SELECT 1 FROM project_repos pr WHERE pr.repo_id=wr.repo_id AND pr.project_id=issue_workflows.project_id))
