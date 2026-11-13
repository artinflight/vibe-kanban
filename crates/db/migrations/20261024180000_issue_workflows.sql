-- Request/phase receipts only; prompts and configuration remain in their existing stores.
CREATE TABLE issue_workflows (
    request_id BLOB PRIMARY KEY NOT NULL CHECK(length(request_id)=16),
    project_id BLOB NOT NULL CHECK(length(project_id)=16),
    request_hash TEXT NOT NULL CHECK(length(request_hash)=64),
    operation TEXT NOT NULL CHECK(operation IN ('create','start','relink')),
    issue_id BLOB NOT NULL CHECK(length(issue_id)=16),
    dot_user_id BLOB NOT NULL CHECK(length(dot_user_id)=16),
    workspace_id BLOB,
    session_id BLOB,
    previous_issue_id BLOB,
    chat_previous_issue_id BLOB,
    chat_completed INTEGER NOT NULL DEFAULT 0 CHECK(chat_completed IN (0,1)),
    link_revision INTEGER,
    phase TEXT NOT NULL CHECK(phase IN ('reserved','linked','launching','started','settled')),
    execution_process_id BLOB,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now'))
);
CREATE INDEX issue_workflows_workspace ON issue_workflows(workspace_id,created_at);
CREATE UNIQUE INDEX issue_workflows_session ON issue_workflows(session_id) WHERE session_id IS NOT NULL;
-- Not FKs: receipts and original identities survive deletion/rollback and cannot
-- be reconstructed from absence. Existing rows/history are never rewritten.
CREATE TABLE workspace_issue_link_revisions (
    workspace_id BLOB PRIMARY KEY NOT NULL,
    revision INTEGER NOT NULL CHECK(revision>=0)
);
CREATE TRIGGER workspace_issue_link_changed AFTER UPDATE OF task_id ON workspaces
WHEN OLD.task_id IS NOT NEW.task_id
BEGIN
    INSERT INTO workspace_issue_link_revisions(workspace_id,revision) VALUES(NEW.id,1)
    ON CONFLICT(workspace_id) DO UPDATE SET revision=revision+1;
END;
-- An initial launch owns its reserved issue context through the native effect
-- boundary. Legacy/UI writers cannot move that context during a partial start.
CREATE TRIGGER issue_workflow_start_link_fence BEFORE UPDATE OF task_id ON workspaces
WHEN OLD.task_id IS NOT NEW.task_id AND EXISTS(
    SELECT 1 FROM issue_workflows r WHERE r.workspace_id=OLD.id AND r.operation='start'
    AND r.phase IN ('reserved','launching'))
BEGIN
    SELECT RAISE(ABORT,'Initial issue workflow has not settled');
END;
-- Freeze the exact repository selection until the first launch settles. These
-- triggers also cover legacy/UI writers without a parallel application lock.
CREATE TRIGGER issue_workflow_repo_update_fence BEFORE UPDATE ON workspace_repos
WHEN EXISTS(SELECT 1 FROM issue_workflows r WHERE r.workspace_id IN (OLD.workspace_id,NEW.workspace_id)
            AND r.operation='start' AND r.phase IN ('reserved','launching'))
BEGIN SELECT RAISE(ABORT,'Initial repository selection is reserved'); END;
CREATE TRIGGER issue_workflow_repo_delete_fence BEFORE DELETE ON workspace_repos
WHEN EXISTS(SELECT 1 FROM issue_workflows r WHERE r.workspace_id=OLD.workspace_id
            AND r.operation='start' AND r.phase IN ('reserved','launching'))
BEGIN SELECT RAISE(ABORT,'Initial repository selection is reserved'); END;
CREATE TRIGGER issue_workflow_repo_insert_fence BEFORE INSERT ON workspace_repos
WHEN EXISTS(SELECT 1 FROM issue_workflows r WHERE r.workspace_id=NEW.workspace_id
            AND r.operation='start' AND r.phase IN ('reserved','launching'))
BEGIN SELECT RAISE(ABORT,'Initial repository selection is reserved'); END;
