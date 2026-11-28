#!/usr/bin/env python3
"""Scoped repair of legacy empty-admission and relocated-workspace observations.

Plan first, then apply the exact SHA-bound plan at a genuine idle boundary. This
uses historical native repo-state records, never today's HEAD. It grants no
publication permission and cannot mark Git coverage verified. No source/index,
Git refs, execution, input, summary or service is modified.
"""
import argparse
from contextlib import closing
import base64
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
import uuid

from turn_git import Blocked, atomic_json, digest, git, read_json, require

FAULT = 'affected repository inventory differs from admitted turn'
NO_POLICY = 'repository has no approved publication policy'
COMPLETED_SCOPE = 'legacy-completion-observation-only'
FAILED_SCOPE = 'legacy-failed-owner-observation-only'
RELOCATED_SCOPE = 'relocated-workspace-observation-only'
OBLIGATION_FAULT = 'completion observation has no matching original obligation'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def instant(value):
    parsed = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
    return parsed.replace(tzinfo=parsed.tzinfo or datetime.timezone.utc).timestamp()


def connect(path, writable=False):
    connection = sqlite3.connect(Path(path).resolve().as_uri() +
                                 ('?mode=rw' if writable else '?mode=ro'), uri=True, timeout=0.5)
    connection.row_factory = sqlite3.Row
    if not writable:
        connection.execute('PRAGMA query_only=ON')
    return connection


def idle(connection, workspace):
    key = uuid.UUID(workspace).bytes
    require(not connection.execute("SELECT 1 FROM execution_processes e JOIN sessions s ON s.id=e.session_id WHERE s.workspace_id=? AND e.status='running' LIMIT 1", (key,)).fetchone(),
            'workspace is running; no repair performed')
    require(not connection.execute("SELECT 1 FROM turn_github_sync_incoming WHERE workspace_id=? AND state='received' LIMIT 1", (key,)).fetchone() and
            not connection.execute('SELECT 1 FROM turn_github_sync_user_queue WHERE workspace_id=? LIMIT 1', (key,)).fetchone(),
            'incoming or queued user work has priority')


def jobs(connection, workspace):
    return [dict(row) for row in connection.execute(
        'SELECT j.execution_process_id,j.request,j.state,j.observation_state,j.observation_report,j.retry_at,e.status execution_status,e.created_at execution_created_at,e.completed_at,e.dropped FROM turn_github_sync j JOIN execution_processes e ON e.id=j.execution_process_id JOIN sessions s ON s.id=e.session_id WHERE j.workspace_id=? AND s.workspace_id=j.workspace_id ORDER BY j.created_at,j.rowid',
        (uuid.UUID(workspace).bytes,))]


def native_states(connection, job):
    rows = [dict(row) for row in connection.execute(
        'SELECT repo_id,before_head_commit,after_head_commit,updated_at FROM execution_process_repo_states WHERE execution_process_id=? ORDER BY repo_id',
        (job['execution_process_id'],))]
    require(rows, 'execution-time repository state is missing')
    result = []
    for row in rows:
        require(row['before_head_commit'] and row['after_head_commit'] and
                0 <= instant(row['updated_at']) - instant(job['completed_at']) <= 5,
                'terminal HEAD lacks contemporaneous execution-time provenance')
        row['repo_id'] = str(uuid.UUID(bytes=row['repo_id']))
        result.append(row)
    start = instant(job['execution_created_at'])
    last_capture = max(instant(row['updated_at']) for row in result)
    workspace = uuid.UUID(json.loads(job['request'])['workspace']).bytes
    for other in connection.execute(
            'SELECT e.created_at,e.completed_at FROM execution_processes e JOIN sessions s ON s.id=e.session_id WHERE s.workspace_id=? AND e.id!=?',
            (workspace, job['execution_process_id'])):
        require(instant(other['created_at']) > last_capture or
                (other['completed_at'] is not None and instant(other['completed_at']) <= start),
                'another execution overlaps the terminal capture; provenance is ambiguous')
    return result


def check_original(repo, oid):
    require(isinstance(oid, str) and re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', oid),
            'original must be a full commit ID')
    require(git(repo, 'rev-parse', '--verify', oid + '^{commit}').decode().strip() == oid,
            'original commit object is missing')


def eligible_job(job, failed_owner=False, relocated=False):
    expected = 'failed' if failed_owner else 'completed'
    require(job['state'] != 'verified' and job['observation_state'] == 'failed' and
            json.loads(job['observation_report'] or '{}').get('reason') in
            ([FAULT, OBLIGATION_FAULT] if relocated else [FAULT]) and
            job['execution_status'] == expected and not job['dropped'],
            'only the exact ' + expected + ' legacy inventory fault can be reconciled')


def failed_execution_evidence(connection, job):
    row = connection.execute(
        'SELECT session_id,status,exit_code,created_at,completed_at,dropped FROM execution_processes WHERE id=?',
        (job['execution_process_id'],)).fetchone()
    require(row and row['status'] == 'failed' and row['exit_code'] is not None and
            row['completed_at'] and not row['dropped'],
            'failed owner requires its exact terminal native failure evidence')
    return dict(session=str(uuid.UUID(bytes=row['session_id'])), status=row['status'],
                exit_code=row['exit_code'], created_at=row['created_at'],
                completed_at=row['completed_at'], dropped=bool(row['dropped']))


def relocation_binding(connection, workspace, old_root, new_root):
    """Bind an explicit move to native ownership and the live Git worktree backlink.

    This is observation repair authority only, never remote coverage. The old
    path must be absent: a second extant checkout is ambiguous, even at equal HEAD.
    """
    old_root, new_root = Path(old_root), Path(new_root)
    require(old_root.is_absolute() and new_root.is_absolute() and
            not old_root.exists() and not old_root.is_symlink() and new_root.is_dir(),
            'relocation requires an absent old root and an existing absolute destination')
    old_root, new_root = old_root.resolve(), new_root.resolve()
    key = uuid.UUID(workspace).bytes
    row = connection.execute('SELECT container_ref FROM workspaces WHERE id=?', (key,)).fetchone()
    require(row and Path(row[0]).resolve() == new_root,
            'relocation destination is not the native workspace root')
    repos = list(connection.execute('SELECT r.id,r.name,r.path FROM repos r JOIN workspace_repos wr ON wr.repo_id=r.id WHERE wr.workspace_id=? ORDER BY r.id', (key,)))
    require(repos, 'relocation native repository inventory is missing')
    entries = {}
    for repo in repos:
        ident = str(uuid.UUID(bytes=repo[0]))
        name = repo[1]
        require(name and Path(name).name == name and name not in ('.', '..'),
                'invalid native repository name')
        current = new_root / name
        common = Path(git(current, 'rev-parse', '--path-format=absolute', '--git-common-dir').decode().strip()).resolve()
        original_common = Path(git(repo[2], 'rev-parse', '--path-format=absolute', '--git-common-dir').decode().strip()).resolve()
        admin = Path(git(current, 'rev-parse', '--path-format=absolute', '--git-dir').decode().strip()).resolve()
        require(common == original_common and admin.parent == common / 'worktrees' and
                (current / '.git').is_file() and
                Path((admin / 'gitdir').read_text().strip()).resolve() == current / '.git',
                'relocation Git worktree identity or backlink differs from native ownership')
        entries[ident] = dict(old_path=str(old_root / name), path=str(current),
                             common_dir=str(common), git_dir=str(admin))
    return dict(old_root=str(old_root), new_root=str(new_root), repositories=entries)


def capture_inventory(request, relocation=None):
    inventory = {i['id']: str(Path(i['path']).resolve()) for i in request['repositories']}
    require(inventory and len(inventory) == len(request['repositories']), 'duplicate or empty repository inventory')
    if relocation:
        require(set(inventory) == set(relocation['repositories']),
                'relocation repository inventory differs from native ownership')
        for ident, path in inventory.items():
            binding = relocation['repositories'][ident]
            require(path in (binding['old_path'], binding['path']),
                    'request path is outside the exact relocation')
            inventory[ident] = binding['path']
    return inventory


def original_path_matches(ident, original, inventory, relocation=None):
    expected = relocation['repositories'][ident]['old_path'] if relocation else inventory[ident]
    return original['path'] == expected


def capture_authority(record, relocation=None):
    if not relocation:
        return not record.get('observation_inventory')
    inventory = record.get('observation_inventory')
    return (record.get('admission_failure') in (None, 'original repository identity changed', NO_POLICY)
            and (not inventory or capture_inventory(dict(repositories=inventory), relocation) ==
                 {i: r['path'] for i, r in relocation['repositories'].items()}))


def create_plan(database, config_path, workspace, output, turn=None, failed_owner=False, relocation=None):
    workspace = str(uuid.UUID(workspace))
    selected_turn = None if turn is None else str(uuid.UUID(turn))
    require(not failed_owner or selected_turn is not None, 'failed-owner planning requires one exact --turn')
    require(not (failed_owner and relocation), 'relocation repair requires completed owners')
    config = read_json(Path(config_path))
    mount = Path(config['storage_mount']).resolve()
    state_root = Path(config['state_root']).resolve()
    output = Path(output).resolve()
    require(mount.is_mount() and output.is_relative_to(mount) and
            state_root.is_relative_to(mount), 'repair evidence requires approved mounted storage')
    require(not output.exists(), 'plan exists; preserve its original evidence')
    with closing(connect(database)) as connection:
        connection.execute('BEGIN')
        idle(connection, workspace)
        relocation = (relocation_binding(connection, workspace, *relocation) if relocation else None)
        selected = jobs(connection, workspace)
        require(selected, 'no scoped checkpoint rows')
        owner_inventory = sorted(str(uuid.UUID(bytes=j['execution_process_id'])) for j in selected)
        if selected_turn is not None:
            selected = [j for j in selected if str(uuid.UUID(bytes=j['execution_process_id'])) == selected_turn]
            require(len(selected) == 1, 'selected turn is not a checkpoint owner in this workspace')
        entries = []
        originals = {}
        for job in selected:
            eligible_job(job, failed_owner, relocation is not None)
            failure_evidence = failed_execution_evidence(connection, job) if failed_owner else None
            request = json.loads(job['request'])
            turn = str(uuid.UUID(bytes=job['execution_process_id']))
            require(request['workspace'] == workspace and request['turn'] == turn,
                    'durable request owner mismatch')
            ledger_path = state_root / workspace / (turn + '.json')
            raw = ledger_path.read_bytes()
            record = json.loads(raw)
            require(record.get('version') == 2 and record['workspace'] == workspace and
                    record['turn'] == turn and record.get('config') == digest(config) and
                    record['repositories'] == [] and capture_authority(record, relocation),
                    'legacy partial admission/config identity mismatch')
            states = native_states(connection, job)
            inventory = capture_inventory(request, relocation)
            require(len(inventory) == len(request['repositories']) and inventory and
                    set(inventory) == {s['repo_id'] for s in states} == set(record['obligations']),
                    'original/request/native repository inventories differ')
            for state in states:
                ident = state['repo_id']
                require(ident not in config.get('repositories', {}),
                        'repair is restricted to the proven missing-policy admission fault')
                repo = Path(inventory[ident])
                require(not output.is_relative_to(repo) and not state_root.is_relative_to(repo),
                        'repair evidence must be outside the source worktree')
                obligation = record['obligations'][ident]
                require(original_path_matches(ident, obligation, inventory, relocation) and not obligation.get('unverifiable') and
                        state['before_head_commit'] in obligation['commits'],
                        'original admission HEAD/provenance mismatch')
                known = originals.setdefault(ident, dict(path=str(repo), commits=[]))
                require(known['path'] == str(repo), 'repository path changed between owners')
                known['commits'] = sorted(set(known['commits'] + obligation['commits'] +
                                             [state['before_head_commit'], state['after_head_commit']]))
            entries.append(dict(turn=turn, request=job['request'],
                                old_observation_report=job['observation_report'],
                                native_states=states, ledger=str(ledger_path),
                                ledger_before_base64=base64.b64encode(raw).decode(),
                                ledger_before_sha256=sha(raw)))
            if failed_owner:
                entries[-1]['failed_execution_evidence'] = failure_evidence
    for original in originals.values():
        for oid in original['commits']:
            check_original(Path(original['path']), oid)
    plan = dict(version=1, scope=RELOCATED_SCOPE if relocation else FAILED_SCOPE if failed_owner else COMPLETED_SCOPE,
                database=str(Path(database).resolve()), config=str(Path(config_path).resolve()),
                config_digest=digest(config), workspace=workspace, originals=originals,
                entries=entries, publication_permission=False, coverage_verified=False)
    if relocation:
        plan['relocation'] = relocation
    if selected_turn is not None:
        plan.update(selected_turn=selected_turn, workspace_owner_inventory=owner_inventory)
    atomic_json(output, plan)
    return dict(state='planned', plan=str(output), sha256=sha(output.read_bytes()),
                turns=len(entries), originals=originals, coverage_verified=False)


def expected_ledger(entry, plan, plan_sha):
    record = json.loads(base64.b64decode(entry['ledger_before_base64']))
    for ident, original in plan['originals'].items():
        record['obligations'][ident]['commits'] = list(original['commits'])
        if plan['scope'] == RELOCATED_SCOPE:
            record['obligations'][ident]['path'] = original['path']
    if plan['scope'] == FAILED_SCOPE:
        record['failed_owner_observation_resolution'] = dict(
            native_failure=entry['failed_execution_evidence'],
            prior_ledger_reason=record.get('reason'),
            prior_observation_report=json.loads(entry['old_observation_report']),
            task_success_proven=False, coverage_verified=False)
    if plan['scope'] == RELOCATED_SCOPE:
        record['observation_inventory'] = [dict(id=i, path=r['path']) for i, r in sorted(plan['originals'].items())]
    record.update(observation_complete=True, admission_failure=NO_POLICY,
                  state='blocked', reason=NO_POLICY,
                  reconciled_observation_inventory=[dict(id=i, path=r['path']) for i, r in sorted(plan['originals'].items())],
                  observation_reconciliation=dict(source='execution_process_repo_states',
                                                  plan_sha256=plan_sha,
                                                  native_states=entry['native_states']))
    return record


def apply_plan(plan_path, expected_sha):
    plan_path = Path(plan_path).resolve()
    raw = plan_path.read_bytes()
    require(sha(raw) == expected_sha, 'repair plan SHA-256 differs from reviewed plan')
    plan = json.loads(raw)
    require(plan.get('version') == 1 and plan.get('scope') in [COMPLETED_SCOPE, FAILED_SCOPE, RELOCATED_SCOPE] and
            plan.get('coverage_verified') is False and plan.get('publication_permission') is False,
            'unsupported repair authority')
    config = read_json(Path(plan['config']))
    require(digest(config) == plan['config_digest'], 'policy changed after planning')
    mount = Path(config['storage_mount']).resolve()
    require(mount.is_mount() and plan_path.is_relative_to(mount), 'repair storage unavailable')
    journal = plan_path.with_name(plan_path.name + '.apply.json')
    with plan_path.with_name(plan_path.name + '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        connection = connect(plan['database'], writable=True)
        try:
            # The write transaction fences native launch/input enqueue writes for
            # this bounded metadata operation; never stop a running execution.
            connection.execute('BEGIN IMMEDIATE')
            idle(connection, plan['workspace'])
            relocation = plan.get('relocation')
            require((plan['scope'] == RELOCATED_SCOPE) == bool(relocation), 'relocation scope binding missing')
            if relocation:
                require(relocation_binding(connection, plan['workspace'], relocation['old_root'], relocation['new_root']) == relocation,
                        'relocation identity changed after planning')
            current = jobs(connection, plan['workspace'])
            if 'selected_turn' in plan:
                require(sorted(str(uuid.UUID(bytes=j['execution_process_id'])) for j in current) ==
                        plan['workspace_owner_inventory'], 'owner inventory changed after planning')
                require([e['turn'] for e in plan['entries']] == [plan['selected_turn']],
                        'selected turn differs from repair entries')
                current = [j for j in current if str(uuid.UUID(bytes=j['execution_process_id'])) ==
                           plan['selected_turn']]
            require({str(uuid.UUID(bytes=j['execution_process_id'])) for j in current} ==
                    {e['turn'] for e in plan['entries']}, 'owner inventory changed after planning')
            by_turn = {str(uuid.UUID(bytes=j['execution_process_id'])): j for j in current}
            failed_owner = plan['scope'] == FAILED_SCOPE
            if failed_owner:
                require(plan.get('selected_turn') and len(plan['entries']) == 1 and
                        plan['entries'][0]['turn'] == plan['selected_turn'],
                        'failed-owner authority requires one exact selected turn')
                for entry in plan['entries']:
                    require(failed_execution_evidence(connection, by_turn[entry['turn']]) ==
                            entry.get('failed_execution_evidence'),
                            'native failure evidence changed after planning')
                    require(native_states(connection, by_turn[entry['turn']]) == entry['native_states'],
                            'failed-owner terminal capture changed after planning')
            if all(j['observation_state'] == 'observed' and
                   json.loads(j['observation_report'] or '{}').get('reconciliation_plan_sha256') == expected_sha
                   for j in current):
                for entry in plan['entries']:
                    record = read_json(Path(entry['ledger']))
                    require(record.get('observation_reconciliation', {}).get('plan_sha256') == expected_sha and
                            all(record.get('obligations', {}).get(ident, {}).get('path') == original['path'] and
                                set(original['commits']).issubset(record['obligations'][ident]['commits'])
                                for ident, original in plan['originals'].items()),
                            'reconciled original ledger is missing or changed')
                return dict(state='reconciled', turns=len(current), already_applied=True,
                            coverage_verified=False, publication_permission=False)
            prepared = []
            retained = {}
            for entry in plan['entries']:
                job = by_turn[entry['turn']]
                eligible_job(job, failed_owner, relocation is not None)
                require(job['request'] == entry['request'] and
                        job['observation_report'] == entry['old_observation_report'] and
                        native_states(connection, job) == entry['native_states'],
                        'historical capture changed after planning')
                # A legacy helper does not share this maintenance lock. Only
                # operate when its persisted retry window proves it cannot start
                # a CP job during this short transaction. Never retime a job.
                require(job['retry_at'] > time.time() + 30,
                        'checkpoint worker retry is due; wait for its natural backoff')
                path = Path(entry['ledger'])
                require(path == Path(config['state_root']).resolve() / plan['workspace'] /
                        (entry['turn'] + '.json'), 'ledger path differs from scoped identity')
                require(sha(base64.b64decode(entry['ledger_before_base64'])) ==
                        entry['ledger_before_sha256'], 'plan original ledger was changed')
                old = json.loads(base64.b64decode(entry['ledger_before_base64']))
                inventory = capture_inventory(json.loads(job['request']), relocation)
                require(old.get('version') == 2 and old['workspace'] == plan['workspace'] and
                        old['turn'] == entry['turn'] and old.get('config') == digest(config) and
                        old['repositories'] == [] and capture_authority(old, relocation) and
                        set(inventory) == set(old['obligations']) == set(plan['originals']) ==
                        {s['repo_id'] for s in entry['native_states']},
                        'plan omitted or changed original capture authority')
                for state in entry['native_states']:
                    ident = state['repo_id']
                    original = old['obligations'][ident]
                    require(ident not in config.get('repositories', {}) and
                            original_path_matches(ident, original, inventory, relocation) and not original.get('unverifiable') and
                            state['before_head_commit'] in original['commits'] and
                            not plan_path.is_relative_to(Path(original['path'])),
                            'plan changed admission provenance')
                    known = retained.setdefault(ident, dict(path=inventory[ident], commits=[]))
                    require(known['path'] == inventory[ident], 'original path changed')
                    known['commits'] = sorted(set(known['commits'] + original['commits'] +
                                                 [state['before_head_commit'], state['after_head_commit']]))
                record = expected_ledger(entry, plan, expected_sha)
                encoded = json.dumps(record, sort_keys=True).encode()
                require(sha(path.read_bytes()) in [entry['ledger_before_sha256'], sha(encoded)],
                        'helper ledger changed; no uncertain overwrite allowed')
                prepared.append((entry, record, encoded))
            require(retained == plan['originals'], 'plan dropped or invented original commits')
            # Check immutable objects before exposing a successful observation.
            for original in plan['originals'].values():
                for oid in original['commits']:
                    check_original(Path(original['path']), oid)
            require(all(j['retry_at'] > time.time() + 15 for j in current),
                    'repair no longer fits within the natural retry boundary')
            atomic_json(journal, dict(state='prepared', plan_sha256=expected_sha,
                                     scope=plan['scope'], coverage_verified=False))
            for entry, record, encoded in prepared:
                atomic_json(Path(entry['ledger']), record)
                require(Path(entry['ledger']).read_bytes() == encoded,
                        'helper ledger changed during repair')
                ack = dict(version=2, state='pending', observation_complete=True,
                           workspace=plan['workspace'], turn=entry['turn'],
                           reason='original heads reconciled from contemporaneous execution records; publication unverified',
                           admission_failure=NO_POLICY, reconciliation_plan_sha256=expected_sha,
                           previous_observation_report=json.loads(entry['old_observation_report']))
                if failed_owner:
                    ack.update(native_execution=entry['failed_execution_evidence'],
                               task_success_proven=False, coverage_verified=False)
                report = dict(version=2, state='blocked', workspace=plan['workspace'],
                              turn=entry['turn'], reason=NO_POLICY)
                changed = connection.execute(
                    "UPDATE turn_github_sync SET observation_state='observed',observation_report=?,report=?,updated_at=strftime('%Y-%m-%d %H:%M:%f','now') WHERE execution_process_id=? AND observation_state='failed' AND observation_report=? AND request=? AND state!='verified'",
                    (json.dumps(ack, sort_keys=True), json.dumps(report, sort_keys=True),
                     uuid.UUID(entry['turn']).bytes, entry['old_observation_report'], entry['request'])).rowcount
                require(changed == 1, 'observation compare-and-swap failed')
            require(all(Path(e['ledger']).read_bytes() == encoded for e, _, encoded in prepared),
                    'ledger changed before observation commit')
            connection.commit()
            atomic_json(journal, dict(state='committed', plan_sha256=expected_sha,
                                     turns=len(prepared), coverage_verified=False))
            return dict(state='reconciled', turns=len(prepared), coverage_verified=False,
                        publication_permission=False, audit=str(journal))
        finally:
            connection.close()  # On error rollback leaves every DB gate intact.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database')
    parser.add_argument('--config')
    parser.add_argument('--workspace')
    parser.add_argument('--turn', help='Plan only this exact owner; retain every other observation gate')
    parser.add_argument('--failed-owner', action='store_true',
                        help='Plan one exact failed owner with unchanged terminal-provenance guards')
    parser.add_argument('--relocated-from', help='Exact absent previous workspace root')
    parser.add_argument('--relocated-to', help='Exact current native workspace root')
    parser.add_argument('--plan')
    parser.add_argument('--apply')
    parser.add_argument('--sha256')
    args = parser.parse_args()
    try:
        if args.apply:
            require(not args.failed_owner, '--failed-owner selects planning only; apply uses reviewed plan scope')
            require(bool(args.sha256), 'apply requires the exact reviewed plan SHA-256')
            result = apply_plan(args.apply, args.sha256)
        else:
            require(all([args.database, args.config, args.workspace, args.plan]), 'incomplete plan arguments')
            require(bool(args.relocated_from) == bool(args.relocated_to), 'relocation requires both exact roots')
            relocation = (args.relocated_from, args.relocated_to) if args.relocated_from else None
            result = create_plan(args.database, args.config, args.workspace, args.plan, args.turn, args.failed_owner, relocation)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (Blocked, OSError, ValueError, KeyError, sqlite3.Error) as error:
        print(json.dumps(dict(state='blocked', coverage_verified=False,
                              reason=str(error) if isinstance(error, Blocked) else 'repair IO/contract failure')))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
