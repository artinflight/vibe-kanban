#!/usr/bin/env python3
"""Read-only bounded metadata inventory and future-growth comparison.

No log bodies, backup mutation, queue writes, scheduling or process controls.
A metadata observation is never a physical writer fence.
"""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import time
import uuid

import log_dedup as logs


def inventory(root, database, *, maximum_files=200_000, seconds=60):
    root = Path(root).resolve(strict=True)
    database = Path(database).resolve(strict=True)
    start = database.stat()
    deadline = time.monotonic() + seconds
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, timeout=2)) as conn:
        conn.execute('PRAGMA query_only=ON')
        conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 10_000)
        conn.execute('BEGIN')
        processes = {}
        active_sessions = set()
        for process, session, status, completed in conn.execute(
                'SELECT id, session_id, status, completed_at FROM execution_processes'):
            if time.monotonic() > deadline:
                raise logs.ArchiveError('Process inventory exceeded admitted time')
            process_id, session_id = str(uuid.UUID(bytes=process)), str(uuid.UUID(bytes=session))
            processes[process_id] = (session_id, status, completed)
            if status == 'running':
                active_sessions.add(session_id)
    files = {}
    reasons = {}
    eligible = []
    payload_inodes = set()
    unique_payload_allocation = 0
    totals = {'raw_bytes': 0, 'allocated_bytes': 0, 'archived_files': 0,
              'raw_files': 0, 'unbound_files': 0, 'active_session_files': 0}
    for path in root.glob('*/*/processes/*.jsonl'):
        if len(files) >= maximum_files or time.monotonic() > deadline:
            raise logs.ArchiveError('File inventory bound exceeded; observation incomplete')
        relative = str(path.relative_to(root))
        path = logs.safe_path(root, relative)
        before = logs.regular(path)
        match = logs.LOG_PATH.fullmatch(relative)
        session, execution = match[2], match[3]
        with path.open('rb') as source:
            archived = source.read(len(logs.MAGIC)) == logs.MAGIC
        if archived:
            raw_bytes = logs.load_manifest(path)['raw_bytes']
            totals['archived_files'] += 1
        else:
            raw_bytes = before.st_size
            totals['raw_files'] += 1
        current = processes.get(execution)
        inode = (before.st_dev, before.st_ino)
        if inode not in payload_inodes:
            unique_payload_allocation += before.st_blocks * 512
            payload_inodes.add(inode)
        reason = None
        if current is None or current[0] != session:
            reason = 'unbound_execution_or_session'
            totals['unbound_files'] += 1
        elif before.st_nlink != 1:
            reason = 'shared_original_inode_requires_owner_review'
        elif session in active_sessions:
            reason = 'session_has_running_execution'
            totals['active_session_files'] += 1
        elif current[1] not in ('completed', 'failed', 'killed') or current[2] is None:
            reason = 'execution_not_terminal'
        elif archived:
            reason = 'already_archived'
        else:
            closure = path.with_suffix('.capture.json')
            if not closure.exists():
                reason = 'legacy_capture_requires_explicit_owner_review'
            else:
                logs.regular(closure)
                if closure.stat().st_size > 4096:
                    reason = 'capture_metadata_invalid'
                else:
                    try:
                        value = json.loads(closure.read_bytes())
                    except (ValueError, UnicodeError):
                        reason = 'capture_metadata_invalid'
                    else:
                        if not isinstance(value, dict) or value.get('capture_state') != 'closed':
                            reason = 'capture_not_closed'
        if logs.version(logs.regular(path)) != logs.version(before):
            raise logs.ArchiveError('Log changed during metadata observation')
        if reason:
            reasons[relative] = reason
        else:
            eligible.append(relative)
        files[relative] = {'identity': logs.version(before), 'raw_bytes': raw_bytes,
                           'allocated_bytes': before.st_blocks * 512, 'archived': archived}
        totals['raw_bytes'] += raw_bytes
        totals['allocated_bytes'] += before.st_blocks * 512
    # Account for shared objects separately; never add decoded size to allocation.
    object_allocated = 0
    object_count = 0
    for directory in root.glob('*/*/processes/.log-objects'):
        if directory.is_symlink() or not directory.is_dir():
            raise logs.ArchiveError('Object store is an alias')
        for obj in directory.iterdir():
            if object_count >= maximum_files * 10 or time.monotonic() > deadline:
                raise logs.ArchiveError('Object inventory bound exceeded; observation incomplete')
            st = logs.regular(obj)
            object_allocated += st.st_blocks * 512
            inode = (st.st_dev, st.st_ino)
            if inode not in payload_inodes:
                unique_payload_allocation += st.st_blocks * 512
                payload_inodes.add(inode)
            object_count += 1
    end = database.stat()
    if (start.st_dev, start.st_ino) != (end.st_dev, end.st_ino):
        raise logs.ArchiveError('Database identity changed during observation')
    totals.update(object_allocated_bytes=object_allocated, object_files=object_count,
                  total_payload_allocated_bytes=unique_payload_allocation)
    return {'version': 1, 'accounting': 'unique-log-and-object-inodes-v1', 'observed_at': time.time(), 'root': str(root),
            'database_identity': [start.st_dev, start.st_ino], 'complete': True,
            'read_only': True, 'writer_fence_established': False,
            'active_sessions': sorted(active_sessions), 'files': files, 'totals': totals,
            'eligible_closed_inactive_files': sorted(eligible), 'exclusions': reasons,
            'allocation_excludes_directory_metadata': True,
            'allocation_excludes_sidecars_and_external_staging': True}


def compare(before, after):
    if (before.get('accounting') != after.get('accounting')
            or before['root'] != after['root'] or before['database_identity'] != after['database_identity']
            or not before['complete'] or not after['complete']):
        raise logs.ArchiveError('Comparable complete observations of the same dataset required')
    elapsed = after['observed_at'] - before['observed_at']
    if elapsed <= 0:
        raise logs.ArchiveError('Positive observation interval required')
    previous, current = before['files'], after['files']
    new = set(current) - set(previous)
    gone = set(previous) - set(current)
    delta = after['totals']['total_payload_allocated_bytes'] - before['totals']['total_payload_allocated_bytes']
    return {'seconds': elapsed, 'allocated_delta_bytes': delta,
            'new_files': len(new), 'missing_files': len(gone),
            'new_logical_bytes': sum(current[key]['raw_bytes'] for key in new),
            'existing_logical_delta_bytes': sum(current[key]['raw_bytes'] - previous[key]['raw_bytes']
                                                for key in set(current) & set(previous)),
            'raw_to_archive_files': sum(not previous[key]['archived'] and current[key]['archived']
                                        for key in set(current) & set(previous)),
            'archive_to_raw_files': sum(previous[key]['archived'] and not current[key]['archived']
                                        for key in set(current) & set(previous)),
            'observed_allocated_bytes_per_day': delta * 86400 / elapsed,
            'forecast': False, 'matched_workload_verified': False,
            'note': 'Record workload/execution counts and conversion activity; rate is an observation, not a forecast.'}


def readiness(observation, *, reader_qualification, backup_verification, custody_adapter,
              ssd_free_bytes, build_floor_bytes=3 * 1024**3):
    """Planning report only: paths are missing/available, never boolean authority."""
    blockers = []
    if not observation['eligible_closed_inactive_files']:
        blockers.append('No closed inactive source set is eligible for selection')
    for label, path in [('all-reader qualification', reader_qualification),
                        ('current-version independently recalled B recovery', backup_verification),
                        ('owner-bound physical custody adapter', custody_adapter)]:
        if path is None:
            blockers.append('Missing ' + label)
        else:
            logs.regular(Path(path))
    if ssd_free_bytes < build_floor_bytes:
        blockers.append('SSD free space below backend build floor; OS log reclamation cannot clear that floor')
    return {'production_run_ready': False, 'planning_inputs_present': not blockers,
            'blockers': blockers,
            'note': 'Even complete planning requires current owner evidence validation and the held physical fence in the deployment controller.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--maximum-files', type=int, default=200_000)
    parser.add_argument('--seconds', type=int, default=60)
    args = parser.parse_args()
    if not 1 <= args.maximum_files <= 200_000 or not 1 <= args.seconds <= 120:
        raise logs.ArchiveError('Finite positive inventory bounds required')
    value = inventory(args.root, args.database, maximum_files=args.maximum_files, seconds=args.seconds)
    if args.previous:
        value['growth'] = compare(json.loads(args.previous.read_bytes()), value)
    print(json.dumps(value, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, sqlite3.Error, TypeError, KeyError) as error:
        message = str(error) if isinstance(error, logs.ArchiveError) else type(error).__name__
        print('Log audit failed: ' + message, file=sys.stderr)
        sys.exit(1)
