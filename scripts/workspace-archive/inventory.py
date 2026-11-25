"""Read-only ownership inventory for workspace archival; never moves payloads."""
import argparse
from collections import defaultdict
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import uuid


def uid(value):
    return str(uuid.UUID(bytes=value))


def readonly(path):
    db = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA query_only=ON')
    db.execute('BEGIN')
    return db


def inspect(database, sessions_root, native_state=None):
    """A coherent metadata snapshot, not live custody or retirement permission."""
    sessions_root = Path(sessions_root).absolute()
    with closing(readonly(database)) as db:
        workspaces = {
            uid(r['id']): dict(workspace_id=uid(r['id']), archived=bool(r['archived']),
                              pinned=bool(r['pinned']), worktree=r['container_ref'],
                              sessions=[], native_threads=[], holds=[])
            for r in db.execute('SELECT id,archived,pinned,container_ref FROM workspaces')
        }
        sessions = {}
        for r in db.execute('SELECT id,workspace_id,executor FROM sessions'):
            sid, wid = uid(r['id']), uid(r['workspace_id'])
            if wid not in workspaces:
                raise ValueError('Session has no workspace owner: ' + sid)
            sessions[sid] = wid
            workspaces[wid]['sessions'].append(dict(session_id=sid, executor=r['executor'],
                history_path=str(sessions_root / sid[:2] / sid)))
        for r in db.execute("""SELECT DISTINCT s.workspace_id FROM execution_processes e
                JOIN sessions s ON s.id=e.session_id WHERE e.status='running'"""):
            workspaces[uid(r[0])]['holds'].append('running_execution')
        for table, condition, reason in [
            ('turn_github_sync_incoming', "state != 'handled'", 'pending_input'),
            ('turn_github_sync_user_queue', '1', 'queued_input'),
            ('watcher_job_leases', 'closed_at IS NULL', 'open_watcher_lease'),
        ]:
            for r in db.execute(f'SELECT DISTINCT workspace_id FROM {table} WHERE {condition}'):
                wid = uid(r[0])
                if wid not in workspaces:
                    raise ValueError('Durable input/lease has no workspace owner')
                workspaces[wid]['holds'].append(reason)
        for r in db.execute("SELECT id,payload FROM scratch WHERE scratch_type='DRAFT_FOLLOW_UP'"):
            # Inspect presence only; never return private prompt contents.
            data = json.loads(r['payload'])
            if not isinstance(data, dict) or data.get('type') != 'DRAFT_FOLLOW_UP':
                raise ValueError('Unknown draft envelope')
            body = data.get('data')
            if not isinstance(body, dict) or not isinstance(body.get('message', ''), str):
                raise ValueError('Unknown draft format')
            if body.get('message', '').strip():
                owner = sessions.get(uid(r['id']))
                if owner is not None:
                    workspaces[owner]['holds'].append('draft_input')
        native_owners = defaultdict(set)
        for r in db.execute("""SELECT DISTINCT c.agent_session_id,s.workspace_id
                FROM coding_agent_turns c JOIN execution_processes e ON e.id=c.execution_process_id
                JOIN sessions s ON s.id=e.session_id WHERE c.agent_session_id IS NOT NULL"""):
            native_owners[r[0]].add(uid(r[1]))
        worktree_owners = defaultdict(set)
        for wid, row in workspaces.items():
            if row['worktree']:
                worktree_owners[str(Path(row['worktree']).resolve())].add(wid)
        for owners in worktree_owners.values():
            if len(owners) > 1:
                for wid in owners:
                    workspaces[wid]['holds'].append('shared_worktree')
    native_paths = {}
    if native_state:
        with closing(readonly(native_state)) as db:
            native_paths = dict(db.execute('SELECT id,rollout_path FROM threads'))
    path_owners = defaultdict(set)
    for thread, owners in native_owners.items():
        if path := native_paths.get(thread):
            path_owners[str(Path(path).resolve())].update(owners)
    for thread, owners in native_owners.items():
        path = native_paths.get(thread)
        shared = len(owners) > 1 or (path is not None and
                    len(path_owners[str(Path(path).resolve())]) > 1)
        for wid in owners:
            workspaces[wid]['native_threads'].append(
                dict(thread_id=thread, path=path, shared=shared))
            if shared:
                workspaces[wid]['holds'].append('shared_native_history')
            if path is None:
                workspaces[wid]['holds'].append('unresolved_native_history')
    for row in workspaces.values():
        if row['pinned']:
            row['holds'].append('pinned')
        if not row['archived']:
            row['holds'].append('active_workspace')
        row['holds'] = sorted(set(row['holds']))
        row['sessions'].sort(key=lambda r: r['session_id'])
        row['native_threads'].sort(key=lambda r: r['thread_id'])
        row['metadata_candidate'] = not row['holds']
    rows = sorted(workspaces.values(), key=lambda r: r['workspace_id'])
    return dict(schema='vk-workspace-archive-inventory-v1', workspaces=rows,
                summary=dict(total=len(rows), archived=sum(r['archived'] for r in rows),
                             active=sum(not r['archived'] for r in rows),
                             metadata_candidates=sum(r['metadata_candidate'] for r in rows)),
                live_custody_verified=False, movement_authorized=False,
                backup_exclusion_authorized=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True, type=Path)
    parser.add_argument('--sessions-root', required=True, type=Path)
    parser.add_argument('--native-state', type=Path)
    parser.add_argument('--summary', action='store_true')
    args = parser.parse_args()
    result = inspect(args.database, args.sessions_root, args.native_state)
    print(json.dumps(result['summary'] if args.summary else result, sort_keys=True))


if __name__ == '__main__':
    main()
