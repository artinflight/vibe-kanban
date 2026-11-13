UPDATE issue_workflows SET phase='settled',
    execution_process_id=(SELECT id FROM execution_processes WHERE session_id=issue_workflows.session_id ORDER BY created_at,rowid LIMIT 1)
WHERE request_id=? AND phase='launching'
AND EXISTS(SELECT 1 FROM execution_processes WHERE session_id=issue_workflows.session_id
           AND (run_reason='codingagent' OR status IN ('failed','killed')))
AND NOT EXISTS(SELECT 1 FROM execution_processes WHERE session_id=issue_workflows.session_id AND status='running')
