"""Audit expected first-start bookkeeping in a detached current-data rehearsal.

This reads copies only. Call once for the existing reader's initial startup;
subsequent candidate/fallback phases must preserve every table exactly.
"""
from datetime import datetime
from pathlib import Path
import sqlite3


def verify_rows(before, after, started_at, finished_at):
    if not started_at <= finished_at:
        raise ValueError('Invalid startup interval')
    if before.keys() != after.keys():
        raise ValueError('Execution identities added or removed')
    changed = []
    for identifier, original in before.items():
        observed = after[identifier]
        if original['status'] != 'running':
            if observed != original:
                raise ValueError('Non-running execution changed')
            continue
        if original['completed_at'] is not None or original['exit_code'] is not None:
            raise ValueError('Running execution has unexpected completion metadata')
        if observed.get('status') != 'failed' or observed.get('exit_code') is not None:
            raise ValueError('Detached orphan was not marked failed without an exit code')
        try:
            completion = datetime.fromisoformat(observed['completed_at'])
            if completion.utcoffset() is None:
                raise ValueError('Completion lacks timezone')
            timestamp = completion.timestamp()
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError('Invalid orphan completion timestamp') from error
        if not started_at <= timestamp <= finished_at:
            raise ValueError('Orphan completion is outside this startup interval')
        expected = dict(original, status='failed', completed_at=observed['completed_at'])
        if observed != expected:
            raise ValueError('Other execution fields changed')
        changed.append(identifier.hex() if isinstance(identifier, bytes) else str(identifier))
    return {'detached_orphans': len(changed), 'execution_ids': sorted(changed),
            'allowed_columns': ['status', 'completed_at'],
            'all_other_execution_fields_preserved': True}


def _read(path):
    with sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        schema = [tuple(row) for row in db.execute('PRAGMA table_info(execution_processes)')]
        rows = {row['id']: dict(row) for row in db.execute('SELECT * FROM execution_processes')}
    return schema, rows


def verify_first_start(before, after, snapshot, working, started_at, finished_at):
    if before.keys() != after.keys():
        raise ValueError('Audit fields changed')
    for name in before:
        if name != 'tables' and before[name] != after[name]:
            raise ValueError('Dataset or migration records changed')
    if before['tables'].keys() != after['tables'].keys():
        raise ValueError('Database tables added or removed')
    for name, value in before['tables'].items():
        if name != 'execution_processes' and after['tables'][name] != value:
            raise ValueError('Unrelated database table changed: ' + name)
    old_schema, old_rows = _read(snapshot)
    new_schema, new_rows = _read(working)
    if old_schema != new_schema:
        raise ValueError('Execution schema changed')
    return verify_rows(old_rows, new_rows, started_at, finished_at)
