#!/usr/bin/env python3
"""Exact-turn, idle-boundary inspection. No repair or acknowledgement authority.

Reads native preservation metadata and Git identities, not app/transcript contents.
The result is deliberately incompatible with reconcile_observation.apply_plan.
"""
import argparse
from contextlib import closing
import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid

import reconcile_observation as repair
from turn_git import Blocked, atomic_json, digest, inventory_identity, line, read_json, require


def inspect_turn(database, config_path, workspace, turn):
    workspace, turn = str(uuid.UUID(workspace)), str(uuid.UUID(turn))
    config = read_json(Path(config_path))
    state_root = Path(config['state_root']).resolve()
    mount = Path(config['storage_mount']).resolve()
    require(mount.is_mount() and state_root.is_relative_to(mount), 'inspection storage unavailable')
    blockers = []

    def blocked(code, reason, action):
        blockers.append(dict(code=code, reason=reason, action=action))

    with closing(repair.connect(database)) as connection:
        connection.execute('BEGIN')
        repair.idle(connection, workspace)
        selected = [j for j in repair.jobs(connection, workspace)
                    if str(uuid.UUID(bytes=j['execution_process_id'])) == turn]
        require(len(selected) == 1, 'selected turn is not a checkpoint owner in this workspace')
        job = selected[0]
        prior = json.loads(job['observation_report'] or '{}')
        require(job['observation_state'] == 'failed' and prior.get('reason') == repair.FAULT,
                'inspection requires the exact retained inventory observation fault')
        execution = connection.execute(
            'SELECT session_id,status,exit_code,completed_at,dropped FROM execution_processes WHERE id=?',
            (uuid.UUID(turn).bytes,)).fetchone()
        request = json.loads(job['request'])
        require(request['workspace'] == workspace and request['turn'] == turn,
                'durable request owner mismatch')
        ledger_path = state_root / workspace / (turn + '.json')
        ledger_raw = ledger_path.read_bytes()
        record = json.loads(ledger_raw)
        require(record.get('version') == 2 and record['workspace'] == workspace and record['turn'] == turn,
                'ledger owner or version mismatch')
        if record.get('config') != digest(config):
            blocked('policy_identity_changed', 'policy differs from original ledger', 'review_exact_policy_identity')
        if job['execution_status'] != 'completed' or job['dropped']:
            blocked('execution_outcome_unsupported',
                    'completed-only maintenance cannot acknowledge this native execution outcome',
                    'review_separate_exact_failed_owner_authority')
        raw_states = [dict(r) for r in connection.execute(
            'SELECT repo_id,before_head_commit,after_head_commit,updated_at FROM execution_process_repo_states WHERE execution_process_id=? ORDER BY repo_id',
            (uuid.UUID(turn).bytes,))]
        for state in raw_states:
            state['repo_id'] = str(uuid.UUID(bytes=state['repo_id']))
            try:
                state['capture_delay_seconds'] = repair.instant(state['updated_at']) - repair.instant(job['completed_at'])
            except (TypeError, ValueError, AttributeError):
                state['capture_delay_seconds'] = None
        provenance_passed = False
        try:
            repair.native_states(connection, job)  # Reuse the unchanged <=5-second/no-overlap guards.
            provenance_passed = True
        except (Blocked, TypeError, ValueError, AttributeError) as error:
            reason = str(error) if isinstance(error, Blocked) else 'native terminal capture is incomplete or malformed'
            blocked('terminal_provenance_unproven', reason, 'obtain_independent_exact_interval_provenance')
        owner = connection.execute('SELECT branch,container_ref FROM workspaces WHERE id=?',
                                   (uuid.UUID(workspace).bytes,)).fetchone()
        require(owner and owner['container_ref'], 'current workspace path binding unavailable')
        root = Path(owner['container_ref']).resolve(strict=True)
        current = [dict(id=str(uuid.UUID(bytes=r['repo_id'])), path=str(root / r['name']))
                   for r in connection.execute(
                       'SELECT wr.repo_id,r.name FROM workspace_repos wr JOIN repos r ON r.id=wr.repo_id WHERE wr.workspace_id=?',
                       (uuid.UUID(workspace).bytes,))]
        requested = inventory_identity(request['repositories'])
        current = inventory_identity(current)
        admitted = [dict(id=e['id'], path=e['path']) for e in record['repositories']]
        if current != requested:
            blocked('current_inventory_changed', 'current repository binding differs from the durable request',
                    'review_exact_repository_identity')
        if (admitted or record.get('observation_inventory') or
                {e['id'] for e in requested} != set(record.get('obligations', {})) or
                {e['id'] for e in requested} != {s['repo_id'] for s in raw_states}):
            blocked('legacy_evidence_inconsistent', 'record is not the supported empty-admission shape',
                    'retain_fault_and_review_exact_evidence')
        identities = []
        for entry in requested:
            # These commands read Git identities only, never historic file blobs.
            path = Path(entry['path'])
            require(not state_root.is_relative_to(path), 'ledger must remain outside repository')
            original = record.get('obligations', {}).get(entry['id'], {})
            if original.get('path') != str(path) or original.get('unverifiable'):
                blocked('original_identity_unproven', 'retained original path/provenance is inconsistent',
                        'retain_original_uncertainty')
            identity = dict(entry, head=line(path, 'rev-parse', '--verify', 'HEAD^{commit}'),
                            branch=line(path, 'symbolic-ref', '--short', 'HEAD'),
                            common_dir=line(path, 'rev-parse', '--path-format=absolute', '--git-common-dir'),
                            publication_policy_present=entry['id'] in config.get('repositories', {}),
                            retained_originals=original.get('commits', []))
            identities.append(identity)
        require(ledger_path.read_bytes() == ledger_raw, 'ledger changed during inspection; inspect again')
    # No apply authority is produced, including when the completed-owner guards pass.
    return dict(version=1, scope='legacy-observation-read-only-inspection',
                state='blocked' if blockers else 'inspected', workspace=workspace, turn=turn,
                session=str(uuid.UUID(bytes=execution['session_id'])),
                native_execution=dict(status=execution['status'], exit_code=execution['exit_code'],
                                      completed_at=execution['completed_at'], dropped=bool(execution['dropped'])),
                inspected_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                prior_observation_report=prior, ledger_sha256=hashlib.sha256(ledger_raw).hexdigest(),
                admitted_inventory=admitted, requested_inventory=requested, current_inventory=current,
                original_admission_failure=record.get('admission_failure'),
                retained_ledger_reason=record.get('reason'), native_states=raw_states,
                terminal_provenance_passed=provenance_passed, repositories=identities,
                blockers=blockers, next_action=('review_exact_blockers' if blockers else 'request_exact_completed_turn_plan'),
                historical_file_snapshot='not_inferred', coverage_verified=False,
                publication_permission=False, apply_supported=False, observation_state_changed=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['database', 'config', 'workspace', 'turn', 'output']:
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    try:
        config = read_json(Path(args.config))
        output = Path(args.output).resolve()
        mount = Path(config['storage_mount']).resolve()
        require(mount.is_mount() and output.is_relative_to(mount) and not output.exists(),
                'inspection needs a new report on mounted storage')
        report = inspect_turn(args.database, args.config, args.workspace, args.turn)
        roots = [Path(entry['path']) for entry in report['requested_inventory'] + report['current_inventory']]
        require(not any(output.is_relative_to(root) for root in roots) and
                not output.is_relative_to(Path(config['state_root']).resolve()),
                'inspection output must be outside repositories and the live ledger')
        atomic_json(output, report)
        print(json.dumps(dict(state=report['state'], report=str(output),
                              sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                              blockers=report['blockers'], apply_supported=False, coverage_verified=False)))
        return 2 if report['blockers'] else 0
    except (Blocked, OSError, ValueError, KeyError, TypeError, RuntimeError, sqlite3.Error) as error:
        print(json.dumps(dict(state='blocked', coverage_verified=False, apply_supported=False,
                              reason=str(error) if isinstance(error, Blocked) else 'inspection IO/contract failure')))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
