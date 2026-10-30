"""Read-only, assigned-owner activity shared by every agent-waking watcher.

Native session/turn/job/queue state is authoritative. Unattributed OS processes
are bounded diagnostics, never evidence that every agent's inventory is unknown.
No prompts, environments, credentials, signals, writes or wake calls are used.
"""
import argparse
import collections
import http.client
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import time
import uuid

TERMINAL = {'completed', 'failed', 'killed'}
JOB_TERMINAL = {'completed', 'failed'}
JOURNAL_TERMINAL = {'completed', 'failed', 'interrupted', 'blocked', 'cancelled'}
MAX_ITEMS = 128


def local_get(path):
    conn = http.client.HTTPConnection('127.0.0.1', 4720, timeout=2)
    try:
        conn.request('GET', path)
        response = conn.getresponse()
        raw = response.read(262145)
        if response.status != 200 or len(raw) > 262144 or response.getheader('Content-Type', '').split(';')[0] != 'application/json':
            raise ValueError('owner_api_unavailable')
        result = json.loads(raw)
        if not isinstance(result, dict) or result.get('success') is not True:
            raise ValueError('owner_api_unavailable')
        return result['data']
    finally:
        conn.close()


def database(config):
    path = Path(config['vibe_db']).resolve(strict=True)
    db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=.5)
    db.execute('PRAGMA query_only=ON')
    deadline = time.monotonic() + 3
    db.set_progress_handler(lambda: int(time.monotonic() > deadline), 10000)
    return db


def custody_issues(config):
    """Keep unresolved lifetime/custody scoped to this workspace, not the host."""
    issues = []
    try:
        wid = uuid.UUID(config['workspace_id']).bytes
        with database(config) as db:
            if db.execute('SELECT 1 FROM watcher_job_leases WHERE workspace_id=? AND closed_at IS NULL LIMIT 1', (wid,)).fetchone():
                issues.append('independent_job_lifetime_unsettled')
            directory = config.get('delegation_journal_dir') or config.get('connector_transport', {}).get('delegation_journal_dir')
            if not directory:
                if config.get('dispatch_transport') == 'connector-follow-up-v1':
                    issues.append('delegation_custody_unconfigured')
                return issues
            threads = db.execute('SELECT DISTINCT cat.agent_session_id FROM coding_agent_turns cat JOIN execution_processes e ON e.id=cat.execution_process_id JOIN sessions s ON s.id=e.session_id WHERE s.workspace_id=? AND cat.agent_session_id IS NOT NULL LIMIT 4097', (wid,)).fetchall()
        if len(threads) > 4096:
            return issues + ['delegation_inventory_limit']
        directory = Path(directory).resolve(strict=True)
        if not directory.is_dir():
            return issues + ['delegation_custody_unavailable']
        budget = 16 * 1024 * 1024
        for (thread,) in threads:
            if not isinstance(thread, str) or not re.fullmatch('[A-Za-z0-9_-]{1,128}', thread):
                return issues + ['delegation_thread_invalid']
            path = directory / (thread + '.json')
            try:
                metadata = path.lstat()
            except FileNotFoundError:
                continue
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > min(2 * 1024 * 1024, budget):
                return issues + ['delegation_journal_unavailable']
            with path.open('rb') as stream:
                raw = stream.read(min(2 * 1024 * 1024, budget) + 1)
            if len(raw) > min(2 * 1024 * 1024, budget):
                return issues + ['delegation_journal_limit']
            budget -= len(raw)
            records = json.loads(raw)
            if not isinstance(records, dict) or len(records) > 4096 or any(not isinstance(r, dict) or r.get('status') not in JOURNAL_TERMINAL for r in records.values()):
                return issues + ['delegation_lifetime_unsettled']
    except (OSError, ValueError, KeyError, sqlite3.Error):
        issues.append('owner_lifetime_unavailable')
    return issues


def read_process(proc, roots):
    """Bounded metadata/path matching only; never retain command lines or cwd."""
    if proc.stat().st_uid != os.getuid() or int(proc.name) == os.getpid():
        return None
    with (proc / 'stat').open() as stream:
        before = stream.read(16384).rpartition(') ')[2].split()
    row = {'pid': int(proc.name), 'ppid': int(before[1]), 'start_ticks': before[19],
           'name': (proc / 'comm').read_text()[:80].strip(),
           'cgroup': (proc / 'cgroup').read_text()[:4096].strip(),
           'references_owner': False, 'unreadable': False}
    try:
        cwd = os.readlink(proc / 'cwd')
        row['references_owner'] = any(cwd == r or cwd.startswith(r + '/') for r in roots)
    except PermissionError:
        row['unreadable'] = True
    try:
        with (proc / 'cmdline').open('rb') as stream:
            args = stream.read(65537)
        if len(args) > 65536:
            row['unreadable'] = True
        # Match path arguments, not arbitrary substrings or a process name.
        for arg in args.split(b'\0'):
            value = arg.split(b'=', 1)[-1]
            if any(value == r.encode() or value.startswith(r.encode() + b'/') for r in roots):
                row['references_owner'] = True
    except PermissionError:
        row['unreadable'] = True
    with (proc / 'stat').open() as stream:
        after = stream.read(16384).rpartition(') ')[2].split()
    if before[19] != after[19]:
        row.update(unreadable=True, identity_changed=True)
    return row


def classify_processes(rows, execution_ids):
    """Positive target attribution propagates through stable process ancestry."""
    known = {r['pid']: r for r in rows}
    children = collections.defaultdict(list)
    for row in rows:
        parent = known.get(row.get('ppid'))
        if parent and int(parent.get('start_ticks', 0)) <= int(row.get('start_ticks', 0)):
            children[parent['pid']].append(row['pid'])
    units = {'vk-capacity-' + uuid.UUID(e).hex + '.service' for e in execution_ids}
    owned = {r['pid'] for r in rows if r.get('references_owner') or
             any(part in units for part in r.get('cgroup', '').split('/'))}
    queue = collections.deque(owned)
    while queue:
        for child in children[queue.popleft()]:
            if child not in owned:
                owned.add(child); queue.append(child)
    relevant = sorted(owned)
    unattributed = [r for r in rows if r.get('unreadable') and r['pid'] not in owned]
    return {'process_ids': relevant[:MAX_ITEMS],
            'process_limit': len(relevant) > MAX_ITEMS,
            'unattributed_process_count': len(unattributed),
            'unattributed_processes': [{k: r[k] for k in ('pid', 'name', 'start_ticks') if k in r}
                                      for r in unattributed[:16]]}


def process_status(config, execution_ids, proc_root=Path('/proc')):
    roots = [str(Path(p).resolve(strict=True)) for p in config.get('owner_roots', [])]
    rows = []
    deadline = time.monotonic() + 2
    for proc in proc_root.iterdir():
        if not proc.name.isdecimal():
            continue
        if time.monotonic() > deadline or len(rows) >= 32768:
            raise ValueError('process_scan_limit')
        try:
            row = read_process(proc, roots)
            if row:
                rows.append(row)
        except (FileNotFoundError, ProcessLookupError):
            continue  # Exit during enumeration is not an unknown running turn.
        except (PermissionError, ValueError, IndexError):
            # No readable target attribution. Keep a diagnostic, not a host hold.
            rows.append({'pid': int(proc.name), 'unreadable': True})
    return classify_processes(rows, execution_ids)


def turn_snapshot(config):
    wid, sid = (uuid.UUID(config[k]).bytes for k in ('workspace_id', 'session_id'))
    with database(config) as db:
        sessions = db.execute('SELECT id FROM sessions WHERE workspace_id=? LIMIT 17', (wid,)).fetchall()
        if not sessions or len(sessions) > 16 or sid not in [r[0] for r in sessions]:
            raise ValueError('owner_binding_unavailable')
        active = db.execute("SELECT e.id,e.session_id,e.status,e.run_reason FROM execution_processes e JOIN sessions s ON s.id=e.session_id WHERE s.workspace_id=? AND coalesce(e.status,'unknown') NOT IN ('completed','failed','killed') AND coalesce(e.run_reason,'unknown')!='devserver' LIMIT 129", (wid,)).fetchall()
        latest = db.execute("SELECT id,status,run_reason FROM execution_processes WHERE session_id=? AND coalesce(run_reason,'unknown')!='devserver' ORDER BY CASE WHEN status='running' AND run_reason='codingagent' THEN 0 WHEN status='running' THEN 1 WHEN run_reason='codingagent' THEN 2 ELSE 3 END,created_at DESC,rowid DESC LIMIT 1", (sid,)).fetchone()
        ids = db.execute('SELECT e.id FROM execution_processes e JOIN sessions s ON s.id=e.session_id WHERE s.workspace_id=? ORDER BY e.created_at DESC LIMIT 256', (wid,)).fetchall()
    return sessions, active, latest, [str(uuid.UUID(bytes=r[0])) for r in ids]


def busy(owner):
    return owner.get('inventory_unknown', True) or any(owner.get(k) for k in
        ('coding_or_script_turns', 'independent_jobs', 'queued', 'process_ids', 'owner_uncertainties'))


def inspect(config, api_get=None, process_reader=None):
    result = {'protocol': 'watcher-owner-state-v1',
              'workspace_id': config.get('workspace_id'), 'session_id': config.get('session_id'),
              'coding_or_script_turns': [], 'independent_jobs': [], 'queued': [],
              'process_ids': [], 'inventory_unknown': False, 'owner_uncertainties': [],
              'current_turn': None, 'turn_state': 'unknown',
              'unattributed_process_count': 0, 'unattributed_processes': []}
    api_get = api_get or local_get
    def issue(component, reason, sid=None):
        if len(result['owner_uncertainties']) < 32:
            result['owner_uncertainties'].append({'component': component, 'reason': reason,
                                                   **({'session_id': sid} if sid else {})})
    try:
        sessions, active, latest, execution_ids = turn_snapshot(config)
        if len(active) > MAX_ITEMS:
            issue('turn', 'owner_turn_limit')
        for eid, sid, status, reason in active[:MAX_ITEMS]:
            if status == 'running':
                result['coding_or_script_turns'].append(str(uuid.UUID(bytes=eid)))
            else:
                issue('turn', 'unfamiliar_execution_status', str(uuid.UUID(bytes=sid)))
        if latest:
            result['current_turn'] = {'execution_id': str(uuid.UUID(bytes=latest[0])),
                                      'status': latest[1], 'run_reason': latest[2]}
        result['turn_state'] = 'running' if any(sid == uuid.UUID(config['session_id']).bytes and status == 'running' for _, sid, status, _ in active) else 'idle'
        if latest and latest[1] not in TERMINAL | {'running'}:
            result['turn_state'] = 'unknown'
        deadline = time.monotonic() + 10
        for (raw_sid,) in sessions:
            sid = str(uuid.UUID(bytes=raw_sid))
            if time.monotonic() > deadline:
                issue('target', 'owner_read_deadline'); break
            try:
                jobs = api_get('/api/execution-processes/subagents/session?session_id=' + sid)
                if not isinstance(jobs, list) or len(jobs) > MAX_ITEMS:
                    raise ValueError('job_inventory_unavailable')
                for job in jobs:
                    if not isinstance(job, dict) or job.get('session_id', sid) != sid or not isinstance(job.get('id'), str):
                        issue('jobs', 'invalid_job_binding', sid)
                    elif job.get('status') == 'running':
                        result['independent_jobs'].append(job['id'][:128])
                    elif job.get('status') not in JOB_TERMINAL:
                        issue('jobs', 'unsettled_or_unfamiliar_job', sid)
            except (OSError, ValueError, KeyError, http.client.HTTPException):
                issue('jobs', 'owner_job_inventory_unavailable', sid)
            try:
                queue = api_get('/api/sessions/' + sid + '/queue')
                if not isinstance(queue, dict) or queue.get('status') not in ('empty', 'queued'):
                    raise ValueError('queue_inventory_unavailable')
                if queue['status'] == 'queued':
                    result['queued'].append(sid)
            except (OSError, ValueError, KeyError, http.client.HTTPException):
                issue('queue', 'owner_queue_unavailable', sid)
        for reason in custody_issues(config):
            issue('lifetime', reason)
        try:
            result.update((process_reader or process_status)(config, execution_ids))
            if result.pop('process_limit', False):
                issue('process', 'owned_process_limit')
        except (OSError, ValueError, KeyError):
            issue('process', 'owner_process_metadata_unavailable')
        # Re-read after slower API/process reads. A newly arrived turn must hold.
        _, fresh, fresh_latest, _ = turn_snapshot(config)
        for eid, sid, status, _ in fresh:
            if status == 'running':
                value = str(uuid.UUID(bytes=eid))
                if value not in result['coding_or_script_turns']:
                    result['coding_or_script_turns'].append(value)
                if sid == uuid.UUID(config['session_id']).bytes:
                    result['turn_state'] = 'running'
            else:
                issue('turn', 'unfamiliar_execution_status', str(uuid.UUID(bytes=sid)))
        if len(fresh) > MAX_ITEMS:
            issue('turn', 'owner_turn_limit')
        if fresh_latest:
            result['current_turn'] = {'execution_id': str(uuid.UUID(bytes=fresh_latest[0])),
                                      'status': fresh_latest[1], 'run_reason': fresh_latest[2]}
            result['turn_state'] = 'running' if fresh_latest[1] == 'running' else 'idle' if fresh_latest[1] in TERMINAL else 'unknown'
        if {(r[0], r[2]) for r in active} != {(r[0], r[2]) for r in fresh}:
            issue('turn', 'owner_changed_during_read')
        for reason in custody_issues(config):
            if not any(r['component'] == 'lifetime' and r['reason'] == reason for r in result['owner_uncertainties']):
                issue('lifetime', reason)
    except (OSError, ValueError, KeyError, sqlite3.Error):
        issue('turn', 'assigned_owner_state_unavailable')
        result['turn_state'] = 'unknown'
    result['independent_jobs'] = result['independent_jobs'][:MAX_ITEMS]
    result['inventory_unknown'] = bool(result['owner_uncertainties'])
    result['state'] = 'busy' if any(result[k] for k in ('coding_or_script_turns', 'independent_jobs', 'process_ids')) else 'unknown' if result['inventory_unknown'] else 'queued' if result['queued'] else 'idle'
    result['observed_at'] = time.time()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    path = Path(args.config)
    if path.stat().st_mode & 0o077 or path.stat().st_size > 65536:
        raise ValueError('private_bounded_owner_config_required')
    result = inspect(json.loads(path.read_text()))
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
