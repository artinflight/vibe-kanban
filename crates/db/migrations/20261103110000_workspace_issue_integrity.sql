-- Local workspace identity must always resolve to a durable issue and project.
-- Legacy standalone creation stays supported: it gets a dedicated, unassigned
-- issue in Workspace Inbox, in the same statement. Never infer ownership from
-- a title match, delete work, change assignments, or acknowledge any turns.
CREATE TABLE IF NOT EXISTS workspace_issue_recoveries (
    workspace_id BLOB PRIMARY KEY NOT NULL,
    previous_issue_id BLOB,
    recovered_issue_id BLOB NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now'))
);

-- Fail closed on identity collisions rather than silently adopt another issue.
CREATE TEMP TABLE workspace_issue_integrity_check (ok INTEGER CHECK(ok = 1));
INSERT INTO workspace_issue_integrity_check
SELECT NOT EXISTS (
    SELECT 1 FROM workspaces w JOIN tasks t ON t.id = w.id
    WHERE NOT EXISTS (SELECT 1 FROM tasks linked JOIN projects p ON p.id = linked.project_id
                      WHERE linked.id = w.task_id)
);
INSERT INTO workspace_issue_integrity_check
SELECT NOT EXISTS (
    SELECT 1 FROM projects WHERE id = X'779542437AEF4AFDA98407B313FF74DC'
    AND (name <> 'Workspace Inbox' OR remote_project_id IS NOT NULL OR archived <> 0)
);
DROP TABLE workspace_issue_integrity_check;

INSERT INTO workspace_issue_recoveries(workspace_id, previous_issue_id, recovered_issue_id)
SELECT w.id, w.task_id, w.id FROM workspaces w
WHERE NOT EXISTS (SELECT 1 FROM tasks t JOIN projects p ON p.id = t.project_id
                  WHERE t.id = w.task_id);
INSERT INTO projects(id, name)
SELECT X'779542437AEF4AFDA98407B313FF74DC', 'Workspace Inbox'
WHERE EXISTS (SELECT 1 FROM workspace_issue_recoveries)
AND NOT EXISTS (SELECT 1 FROM projects WHERE id = X'779542437AEF4AFDA98407B313FF74DC');
INSERT INTO tasks(id, project_id, title, description, status)
SELECT r.recovered_issue_id, X'779542437AEF4AFDA98407B313FF74DC',
       COALESCE(NULLIF(trim(w.name), ''), w.branch),
       'Recovered workspace issue. Review the project and assignment; original workspace, history and unread state are preserved.',
       'todo'
FROM workspace_issue_recoveries r JOIN workspaces w ON w.id = r.workspace_id
WHERE NOT EXISTS (SELECT 1 FROM tasks WHERE id = r.recovered_issue_id);
UPDATE workspaces SET task_id = (
    SELECT recovered_issue_id FROM workspace_issue_recoveries r WHERE r.workspace_id = workspaces.id
)
WHERE NOT EXISTS (SELECT 1 FROM tasks t JOIN projects p ON p.id = t.project_id
                  WHERE t.id = workspaces.task_id);

CREATE TRIGGER IF NOT EXISTS workspace_issue_validate_insert BEFORE INSERT ON workspaces
WHEN NEW.task_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM tasks t JOIN projects p ON p.id = t.project_id WHERE t.id = NEW.task_id)
BEGIN
    SELECT RAISE(ABORT, 'Workspace requires an existing issue in an existing project');
END;

CREATE TRIGGER IF NOT EXISTS workspace_issue_create_inbox AFTER INSERT ON workspaces
WHEN NEW.task_id IS NULL
BEGIN
    SELECT CASE WHEN EXISTS (SELECT 1 FROM tasks WHERE id = NEW.id)
        THEN RAISE(ABORT, 'Workspace inbox issue identity collision') END;
    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM projects WHERE id = X'779542437AEF4AFDA98407B313FF74DC'
        AND (name <> 'Workspace Inbox' OR remote_project_id IS NOT NULL OR archived <> 0))
        THEN RAISE(ABORT, 'Workspace inbox project is unavailable') END;
    INSERT INTO projects(id, name)
    SELECT X'779542437AEF4AFDA98407B313FF74DC', 'Workspace Inbox'
    WHERE NOT EXISTS (SELECT 1 FROM projects WHERE id = X'779542437AEF4AFDA98407B313FF74DC');
    INSERT INTO tasks(id, project_id, title, description, status)
    VALUES(NEW.id, X'779542437AEF4AFDA98407B313FF74DC',
           COALESCE(NULLIF(trim(NEW.name), ''), NEW.branch),
           'Automatically created for a standalone workspace. Review the project and assignment.', 'todo');
    UPDATE workspaces SET task_id = NEW.id WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS workspace_issue_validate_update BEFORE UPDATE OF task_id ON workspaces
WHEN NOT EXISTS (
    SELECT 1 FROM tasks t JOIN projects p ON p.id = t.project_id WHERE t.id = NEW.task_id)
BEGIN
    SELECT RAISE(ABORT, 'Workspace requires an existing issue in an existing project');
END;

-- A link must survive issue/project edits and all deletion paths, including
-- writers with foreign_keys disabled. Delete/relink the workspace explicitly first.
CREATE TRIGGER IF NOT EXISTS workspace_issue_protect_delete BEFORE DELETE ON tasks
WHEN EXISTS (SELECT 1 FROM workspaces WHERE task_id = OLD.id)
BEGIN SELECT RAISE(ABORT, 'Relink or delete linked workspaces before deleting their issue'); END;
CREATE TRIGGER IF NOT EXISTS workspace_issue_protect_identity BEFORE UPDATE OF id, project_id ON tasks
WHEN EXISTS (SELECT 1 FROM workspaces WHERE task_id = OLD.id)
AND (NEW.id IS NOT OLD.id OR NOT EXISTS (SELECT 1 FROM projects WHERE id = NEW.project_id))
BEGIN SELECT RAISE(ABORT, 'Cannot invalidate a linked workspace issue'); END;
CREATE TRIGGER IF NOT EXISTS workspace_issue_protect_project_delete BEFORE DELETE ON projects
WHEN EXISTS (SELECT 1 FROM tasks t JOIN workspaces w ON w.task_id = t.id WHERE t.project_id = OLD.id)
BEGIN SELECT RAISE(ABORT, 'Relink or delete linked workspaces before deleting their project'); END;
CREATE TRIGGER IF NOT EXISTS workspace_issue_protect_project_identity BEFORE UPDATE OF id ON projects
WHEN NEW.id IS NOT OLD.id AND EXISTS (
    SELECT 1 FROM tasks t JOIN workspaces w ON w.task_id = t.id WHERE t.project_id = OLD.id)
BEGIN SELECT RAISE(ABORT, 'Cannot invalidate a linked workspace project'); END;

-- REPLACE can skip DELETE triggers when recursive_triggers is disabled. Check
-- the incoming identity too, so legacy upserts cannot bypass the invariant.
CREATE TRIGGER IF NOT EXISTS workspace_issue_protect_issue_insert BEFORE INSERT ON tasks
WHEN EXISTS (SELECT 1 FROM workspaces WHERE task_id = NEW.id)
AND NOT EXISTS (SELECT 1 FROM projects WHERE id = NEW.project_id)
BEGIN SELECT RAISE(ABORT, 'Cannot replace a linked issue with an invalid project'); END;
CREATE TRIGGER IF NOT EXISTS workspace_issue_protect_issue_update_target BEFORE UPDATE OF id, project_id ON tasks
WHEN EXISTS (SELECT 1 FROM workspaces WHERE task_id = NEW.id)
AND NOT EXISTS (SELECT 1 FROM projects WHERE id = NEW.project_id)
BEGIN SELECT RAISE(ABORT, 'Cannot replace a linked issue with an invalid project'); END;
CREATE TRIGGER IF NOT EXISTS workspace_issue_protect_project_insert BEFORE INSERT ON projects
WHEN NEW.remote_project_id IS NOT NULL AND EXISTS (
    SELECT 1 FROM projects p JOIN tasks t ON t.project_id = p.id
    JOIN workspaces w ON w.task_id = t.id
    WHERE p.remote_project_id = NEW.remote_project_id AND p.id IS NOT NEW.id)
BEGIN SELECT RAISE(ABORT, 'Cannot replace a project with linked workspaces'); END;
CREATE TRIGGER IF NOT EXISTS workspace_issue_protect_project_update_target BEFORE UPDATE OF remote_project_id ON projects
WHEN NEW.remote_project_id IS NOT NULL AND EXISTS (
    SELECT 1 FROM projects p JOIN tasks t ON t.project_id = p.id
    JOIN workspaces w ON w.task_id = t.id
    WHERE p.remote_project_id = NEW.remote_project_id AND p.id IS NOT NEW.id)
BEGIN SELECT RAISE(ABORT, 'Cannot replace a project with linked workspaces'); END;

-- SQLite's BLOB PRIMARY KEY alone permits NULL and non-UUID values. Keep the
-- automatic inbox path safe even for imports that bypass typed API writers.
CREATE TRIGGER IF NOT EXISTS workspace_issue_validate_uuid_insert BEFORE INSERT ON workspaces
WHEN typeof(NEW.id) <> 'blob' OR length(NEW.id) <> 16
OR (NEW.task_id IS NOT NULL AND (
    typeof(NEW.task_id) <> 'blob' OR length(NEW.task_id) <> 16 OR NOT EXISTS (
        SELECT 1 FROM tasks t JOIN projects p ON p.id = t.project_id
        WHERE t.id = NEW.task_id AND typeof(p.id) = 'blob' AND length(p.id) = 16)))
BEGIN SELECT RAISE(ABORT, 'Workspace and linked issue/project identities must be UUIDs'); END;
CREATE TRIGGER IF NOT EXISTS workspace_issue_validate_uuid_update BEFORE UPDATE OF id, task_id ON workspaces
WHEN typeof(NEW.id) <> 'blob' OR length(NEW.id) <> 16
OR typeof(NEW.task_id) <> 'blob' OR length(NEW.task_id) <> 16 OR NOT EXISTS (
    SELECT 1 FROM tasks t JOIN projects p ON p.id = t.project_id
    WHERE t.id = NEW.task_id AND typeof(p.id) = 'blob' AND length(p.id) = 16)
BEGIN SELECT RAISE(ABORT, 'Workspace and linked issue/project identities must be UUIDs'); END;
CREATE TRIGGER IF NOT EXISTS workspace_issue_validate_project_uuid_insert BEFORE INSERT ON tasks
WHEN EXISTS (SELECT 1 FROM workspaces WHERE task_id = NEW.id)
AND (typeof(NEW.project_id) <> 'blob' OR length(NEW.project_id) <> 16)
BEGIN SELECT RAISE(ABORT, 'Linked workspace issue project must be a UUID'); END;
CREATE TRIGGER IF NOT EXISTS workspace_issue_validate_project_uuid_update BEFORE UPDATE OF id, project_id ON tasks
WHEN EXISTS (SELECT 1 FROM workspaces WHERE task_id IN (OLD.id, NEW.id))
AND (typeof(NEW.project_id) <> 'blob' OR length(NEW.project_id) <> 16)
BEGIN SELECT RAISE(ABORT, 'Linked workspace issue project must be a UUID'); END;
