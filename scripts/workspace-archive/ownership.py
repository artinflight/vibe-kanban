"""Current SQL/native/Git path closure for one physically archived workspace.

Read-only metadata and process checks supplement genuine serving-reader custody.
Plans contain exact bindings, never permissions inferred from names or UI flags.
Current SQL, shared attachment storage and common Git repositories stay live.
"""
from contextlib import closing
import os
from pathlib import Path
import uuid

from catalog import Conflict, identity
import git_dependency
import inventory
import payloads
import process_use


def within(path, root):
    return path == root or root in path.parents


def canonical(path):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts or path.resolve() != path:
        raise Conflict('Payload ownership path is aliased or not canonical')
    return path


WORKSPACE_CONFIG = """# Vibe Kanban Workspace

## Sharing Images In Chat

When you create an image that the user should see in chat, save the file under `.vibe-attachments/` in this workspace and reference it with normal Markdown image syntax:

`![short description](.vibe-attachments/example.png)`

Create `.vibe-attachments/` if needed. Use a relative `.vibe-attachments/...` path, not an absolute filesystem path.
"""


def generated_config(path, repositories):
    if path.name not in ('AGENTS.md', 'CLAUDE.md') or path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
        return False
    value = path.read_text()
    if value == WORKSPACE_CONFIG:
        return True
    prefix = WORKSPACE_CONFIG + '\n## Repository Instructions\n\n'
    remainder = value[len(prefix):] if value.startswith(prefix) else value
    lines = remainder.splitlines()
    allowed = {'@' + r['name'] + '/' + path.name for r in repositories}
    return bool(lines) and len(set(lines)) == len(lines) and set(lines) <= allowed


class Ownership:
    def __init__(self, database, sessions_root, native_state, native_roots, worktrees_root, *, process_check=process_use.check):
        self.process_check = process_check
        self.database, self.sessions = canonical(database), canonical(sessions_root)
        self.native_state = canonical(native_state)
        self.native_roots = tuple(canonical(p) for p in native_roots)
        self.worktrees = canonical(worktrees_root)
        if not self.native_roots:
            raise Conflict('Current native history roots must be explicitly bound')
        self.identities = {str(p): (p.stat().st_dev, p.stat().st_ino) for p in
                           (self.database, self.sessions, self.native_state, self.worktrees, *self.native_roots)}

    def check_bindings(self):
        for name, expected in self.identities.items():
            p = canonical(name)
            st = p.stat()
            if (st.st_dev, st.st_ino) != expected:
                raise Conflict('Current ownership database or payload root changed')

    def binding(self, workspace, *, archive):
        self.check_bindings()
        workspace = str(uuid.UUID(workspace))
        observed = inventory.inspect(self.database, self.sessions, self.native_state)
        rows = {r['workspace_id']: r for r in observed['workspaces']}
        if workspace not in rows:
            raise Conflict('Workspace no longer exists')
        row = rows[workspace]
        # Restoration must proceed with retained input and an active flag, but
        # cannot race an already running execution or borrow another owner.
        holds = set(row['holds'])
        if not archive:
            holds -= {'active_workspace', 'pinned', 'pending_input', 'queued_input', 'draft_input', 'open_watcher_lease'}
        if holds:
            raise Conflict('Workspace metadata ownership remains protected: ' + ','.join(sorted(holds)))
        with closing(inventory.readonly(self.database)) as db:
            data = dict(db.execute('SELECT branch,container_ref,worktree_deleted FROM workspaces WHERE id=?',
                                   (identity(workspace),)).fetchone())
            repos = [dict(r) for r in db.execute('''SELECT r.path,r.name,wr.target_branch
                FROM workspace_repos wr JOIN repos r ON r.id=wr.repo_id
                WHERE wr.workspace_id=? ORDER BY r.path''', (identity(workspace),))]
            executions = [dict(execution_id=inventory.uid(r['id']), session_id=inventory.uid(r['session_id']),
                               status=r['status'], completed_at=r['completed_at'])
                          for r in db.execute('''SELECT e.id,e.session_id,e.status,e.completed_at
                              FROM execution_processes e JOIN sessions s ON s.id=e.session_id
                              WHERE s.workspace_id=? ORDER BY e.id''', (identity(workspace),))]
        if any(e['status'] not in ('completed', 'failed', 'killed') or e['completed_at'] is None for e in executions):
            raise Conflict('Every execution must have a terminal, closed durable owner')
        container = canonical(data['container_ref']) if data['container_ref'] else None
        if container is not None:
            if not within(container, self.worktrees) or container == self.worktrees:
                raise Conflict('Workspace container lies outside the qualified worktree root')
            for wid, other in rows.items():
                if wid != workspace and other['worktree']:
                    path = canonical(other['worktree'])
                    if within(container, path) or within(path, container):
                        raise Conflict('Workspace container overlaps another workspace owner')
        if repos and container is None:
            raise Conflict('Repository owner has no durable workspace container')
        names = [r['name'] for r in repos]
        if len(set(names)) != len(names) or any(Path(n).name != n or n in ('.', '..') for n in names):
            raise Conflict('Ambiguous repository paths inside the workspace')
        return dict(workspace_id=workspace, sessions=row['sessions'], native_threads=row['native_threads'],
                    workspace=data, repositories=repos, executions=executions)

    def roots(self, binding, *, archived_roots=None):
        """Resolve original roots; restored/cold intents bind absent paths exactly."""
        roots, declared = [], set(archived_roots or ())
        execution_sessions = {e['session_id'] for e in binding['executions']}
        for row in binding['sessions']:
            path = canonical(row['history_path'])
            expected = self.sessions / row['session_id'][:2] / row['session_id']
            if path != expected:
                raise Conflict('Session history ownership differs')
            if os.path.lexists(path) or str(path) in declared:
                roots.append(str(path))
            elif row['session_id'] in execution_sessions:
                raise Conflict('Existing execution history is unresolved or missing')
        for row in binding['native_threads']:
            path = canonical(row['path'])
            if row['shared'] or not any(within(path, root) and path != root for root in self.native_roots):
                raise Conflict('Native history path is shared or outside its qualified owner')
            if not os.path.lexists(path) and str(path) not in declared:
                raise Conflict('Native conversation history is unresolved or missing')
            roots.append(str(path))
        workspace = binding['workspace']
        container = canonical(workspace['container_ref']) if workspace['container_ref'] else None
        if container is not None and (os.path.lexists(container) or str(container) in declared):
            roots.append(str(container))
        elif container is not None and not workspace['worktree_deleted']:
            raise Conflict('Workspace worktree is missing without a completed retirement record')
        if len(set(roots)) != len(roots) or any(within(Path(a), Path(b)) for a in roots for b in roots if a != b):
            raise Conflict('Payload ownership roots overlap')
        return roots

    def plan(self, workspace):
        binding = self.binding(workspace, archive=True)
        roots = self.roots(binding)
        container = binding['workspace']['container_ref']
        if container and Path(container).exists():
            allowed = {r['name'] for r in binding['repositories']} | {'.vibe-attachments'}
            # Custom outer-container files are untracked work, even if every
            # repository itself is clean. Preserve them for explicit review.
            for child in Path(container).iterdir():
                if child.name not in allowed and not generated_config(child, binding['repositories']):
                    raise Conflict('Untracked outer-workspace files remain protected')
        specs = []
        for repo in binding['repositories']:
            path = Path(container) / repo['name']
            spec = (git_dependency.inspect(path, repo['path'], binding['workspace']['branch'])
                    if Path(container).exists() else
                    git_dependency.inspect_branch(repo['path'], binding['workspace']['branch']))
            specs.append(spec)
            if spec.get('admin'):
                roots.append(spec['admin'])
        if not roots:
            raise Conflict('No existing owned payload requires physical archival')
        self.process_check(roots)
        return dict(format='vk-workspace-ownership-v1', roots=sorted(roots), binding=binding, git=specs)

    def validate(self, workspace, plan, *, archive):
        if plan.get('format') != 'vk-workspace-ownership-v1' or plan['binding']['workspace_id'] != workspace:
            raise Conflict('Exact source-qualified workspace ownership required')
        current = self.binding(workspace, archive=archive)
        if current != plan['binding']:
            raise Conflict('Workspace session/native/repository ownership changed')
        roots = self.roots(current, archived_roots=plan['roots'])
        for spec, repo in zip(plan['git'], current['repositories'], strict=True):
            if spec['repository'] != str(canonical(repo['path'])) or spec['branch'] != 'refs/heads/' + current['workspace']['branch']:
                raise Conflict('Shared Git dependency does not belong to the current workspace')
            branch = git_dependency.inspect_branch(repo['path'], current['workspace']['branch'])
            if spec['common'] != branch['common'] or spec['head'] != branch['head']:
                raise Conflict('Shared branch or repository changed; preserve newer work')
            if spec.get('admin'):
                if (Path(spec['admin']).parent != Path(spec['common']) / 'worktrees'
                        or spec['worktree'] != str(Path(current['workspace']['container_ref']) / repo['name'])):
                    raise Conflict('Private Git administrative ownership differs')
                roots.append(spec['admin'])
        if sorted(roots) != plan['roots']:
            raise Conflict('Physical roots differ from the complete current ownership closure')
        self.process_check(roots)

    def complete_restore(self, workspace, plan):
        self.validate(workspace, plan, archive=False)
        for spec in plan['git']:
            git_dependency.verify_live(spec)
