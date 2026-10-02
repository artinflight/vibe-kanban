#!/usr/bin/env python3
"""Capture review flags and their identities before production-affecting work."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import urllib.request
import uuid

SSD = Path('/mnt/vk-storage')
FIELDS = {
    'projects': 'id name remote_project_id archived created_at updated_at',
    'tasks': 'id project_id title status parent_workspace_id created_at updated_at',
    'workspaces': 'id task_id name branch container_ref archived pinned worktree_deleted created_at updated_at',
    'sessions': 'id workspace_id name executor agent_working_dir created_at updated_at',
    'execution_processes': 'id session_id status dropped run_reason started_at completed_at created_at updated_at',
    'coding_agent_turns': 'id execution_process_id agent_session_id seen created_at updated_at',
    'repos': 'id name display_name path default_target_branch',
    'workspace_repos': 'id workspace_id repo_id target_branch',
    'project_repos': 'id project_id repo_id',
}
MIGRATION = Path(__file__).resolve().parents[1] / 'crates/db/migrations/20261002000000_add_workspace_review_journal.sql'


def json_value(value):
    if isinstance(value, bytes):
        return str(uuid.UUID(bytes=value)) if len(value) == 16 else value.hex()
    return value


def capture(database, reason):
    database = Path(database).resolve(strict=True)
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, timeout=15)) as db:
        db.row_factory = sqlite3.Row
        db.execute('BEGIN')
        tables = {}
        for table, names in FIELDS.items():
            available = {row['name'] for row in db.execute(f'PRAGMA table_info("{table}")')}
            selected = [name for name in names.split() if name in available]
            if not selected:
                continue
            columns = ','.join(f'"{name}"' for name in selected)
            tables[table] = [{key: json_value(value) for key, value in dict(row).items()}
                             for row in db.execute(f'SELECT {columns} FROM "{table}" ORDER BY id')]
        if 'coding_agent_turns' not in tables or 'workspaces' not in tables:
            raise ValueError('Not a VK database with review flags and workspaces')
        journal = db.execute("SELECT name FROM sqlite_master WHERE name='workspace_review_events'").fetchone()
        triggers = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
        enabled = bool(journal) and {'workspace_review_insert', 'workspace_review_update', 'workspace_review_delete'} <= triggers
        head = db.execute('SELECT max(sequence) FROM workspace_review_events').fetchone()[0] if journal else None
        db.commit()
    return {'schema': 1, 'captured_at': datetime.now(timezone.utc).isoformat(),
            'reason': reason, 'source_database': str(database),
            'source_device': database.stat().st_dev, 'source_inode': database.stat().st_ino,
            'review_journal_head': head, 'review_journal_enabled': enabled, 'tables': tables,
            'scope': 'Review/issue/project/workspace/session/repository metadata; no prompts, secrets or drafts'}


def api_state(base):
    def get(path, data=None):
        request = urllib.request.Request(base.rstrip('/') + path,
            data=json.dumps(data).encode() if data is not None else None,
            headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.load(response)
        if not result.get('success'):
            raise ValueError('Live VK metadata request failed')
        return result['data']
    return {'observed_at': datetime.now(timezone.utc).isoformat(), 'base': base,
            'workspaces': get('/api/workspaces'),
            'summaries': get('/api/workspaces/summaries', {'archived': False})['summaries']}


def verify_api_identity(snapshot, live):
    tables = snapshot['tables']
    workspaces = {row['id']: row for row in tables['workspaces']}
    executions = {row['id']: row for row in tables.get('execution_processes', [])}
    sessions = {row['id']: row for row in tables.get('sessions', [])}
    unseen = set()
    for row in tables['coding_agent_turns']:
        execution = executions.get(row['execution_process_id'])
        session = sessions.get(execution['session_id']) if execution else None
        if not row['seen'] and session:
            unseen.add(session['workspace_id'])
    for row in live['workspaces']:
        if row['id'] not in workspaces:
            raise ValueError('API workspaces do not match the selected database')
    for row in live['summaries']:
        if row['workspace_id'] not in workspaces or row['has_unseen_turns'] != (row['workspace_id'] in unseen):
            raise ValueError('API review flags differ from snapshot; reconcile identity or concurrent work')


def verify_destination(output, ssd=SSD):
    if not ssd.is_mount():
        raise ValueError('Secondary SSD is not mounted; no system-disk fallback')
    resolved = Path(output).resolve()
    if not resolved.is_relative_to(ssd.resolve()):
        raise ValueError('Review snapshots must be written on the mounted SSD')
    return resolved


def mirror(path, host, directory, options):
    if not re.fullmatch(r'B:/vk-backups/[A-Za-z0-9_./-]+', directory) or '..' in directory.split('/'):
        raise ValueError('Desktop destination must be under B:/vk-backups')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', path.name):
        raise ValueError('Unsafe snapshot filename')
    ssh_options = ['-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', '-o', 'StrictHostKeyChecking=yes']
    for value in options:
        ssh_options.extend(['-o', value])
    def remote(command):
        return subprocess.check_output(['ssh', *ssh_options, host, command], text=True, timeout=120).strip()
    remote('powershell -NoProfile -Command "New-Item -ItemType Directory -Force -Path \'' + directory + '\' | Out-Null"')
    subprocess.run(['scp', *ssh_options, str(path), host + ':' + directory + '/'], check=True, timeout=180)
    remote_hash = remote('powershell -NoProfile -Command "(Get-FileHash -Algorithm SHA256 -LiteralPath \'' +
                         directory + '/' + path.name + '\').Hash"').lower()
    local_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    if remote_hash != local_hash:
        raise ValueError('Desktop snapshot checksum mismatch')
    return {'desktop_verified': True, 'desktop_path': host + ':' + directory + '/' + path.name,
            'sha256': local_hash, 'bytes': path.stat().st_size}


def install_journal(database):
    with closing(sqlite3.connect(str(database), timeout=15)) as db:
        db.executescript('BEGIN IMMEDIATE;\n' + MIGRATION.read_text() + '\nCOMMIT;')
        triggers = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
        if not {'workspace_review_insert', 'workspace_review_update', 'workspace_review_delete'} <= triggers:
            raise ValueError('Review event journal is incomplete')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reason', required=True)
    parser.add_argument('--api-url', required=True)
    parser.add_argument('--desktop-host', default='desktop')
    parser.add_argument('--desktop-directory', default='B:/vk-backups/workspace-review-snapshots')
    parser.add_argument('--ssh-option', action='append', default=[])
    parser.add_argument('--install-journal', action='store_true')
    parser.add_argument('--require-journal', action='store_true')
    args = parser.parse_args()
    output = verify_destination(args.output)
    if output.exists():
        raise ValueError('Snapshot path already exists; use a new operation name')
    live = api_state(args.api_url)
    snapshot = capture(args.database, args.reason)
    if args.require_journal and not snapshot['review_journal_enabled']:
        raise ValueError('Review journal is missing; bootstrap it after a verified current backup')
    verify_api_identity(snapshot, live)
    snapshot['live'] = live
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as handle:
        os.chmod(output, 0o600)
        json.dump(snapshot, handle, indent=2)
        handle.write('\n')
    receipt = mirror(output, args.desktop_host, args.desktop_directory, args.ssh_option)
    receipt.update(snapshot=str(output), captured_at=snapshot['captured_at'],
                   turn_flags=len(snapshot['tables']['coding_agent_turns']))
    with Path(str(output) + '.receipt.json').open('x') as handle:
        os.chmod(handle.name, 0o600)
        json.dump(receipt, handle, indent=2)
        handle.write('\n')
    if args.install_journal:
        install_journal(args.database)
        receipt['journal_installed'] = True
        Path(str(output) + '.receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
