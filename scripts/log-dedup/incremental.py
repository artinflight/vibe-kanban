"""Bounded recurring closed-log conversion using one pinned deployment adapter.

A durable in-progress record is a review hold, never permission to replay a
partially published batch. Existing production custody and B recovery stay in
the adapter. This runner never starts model workers or changes user settings.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import time
import uuid


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    path = Path(path)
    if path.stat().st_size > 16 * 1024**2:
        raise ValueError('bounded control required')
    return json.loads(path.read_bytes())


def save(path, value):
    path = Path(path)
    temporary = path.with_name('.' + path.name + '-' + uuid.uuid4().hex)
    with temporary.open('xb') as stream:
        stream.write((json.dumps(value, sort_keys=True) + '\n').encode())
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    fd = os.open(path.parent, os.O_DIRECTORY | os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def source(reference):
    path = Path(reference['path'])
    before = path.lstat()
    if (path.resolve() != path or not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.getuid() or before.st_nlink != 1
            or before.st_mode & 0o022):
        raise ValueError('canonical owned pinned source required')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != reference['sha256']:
        raise ValueError('source pin mismatch')
    after = path.lstat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise ValueError('source changed during read')
    return raw


def batches(rows, *, maximum_files, maximum_bytes):
    if not 1 <= maximum_files <= 32 or not 1 <= maximum_bytes <= 512 * 1024**2:
        raise ValueError('bounded batch policy required')
    result = []
    for row in sorted(rows, key=lambda r: (r['workspace'], r['path'])):
        if row['bytes'] > maximum_bytes:
            raise ValueError('eligible log exceeds qualified single-batch budget')
        if (not result or result[-1]['workspace'] != row['workspace']
                or len(result[-1]['rows']) >= maximum_files
                or result[-1]['bytes'] + row['bytes'] > maximum_bytes):
            result.append(dict(workspace=row['workspace'], rows=[], bytes=0))
        result[-1]['rows'].append(row)
        result[-1]['bytes'] += row['bytes']
    return result


def execute(config, adapter, *, clock=time.time):
    root = Path(config['state_root'])
    active = root / 'ACTIVE.private.json'
    if active.exists():
        raise ValueError('Existing active run requires exact journal reconciliation; no replay')
    excluded_path = root / 'NONBENEFICIAL.private.json'
    excluded = read(excluded_path) if excluded_path.exists() else {}
    snapshot = adapter.inventory()
    rows = [r for r in snapshot['files'] if r['reason'] == 'eligible_closed'
            and excluded.get(r['path']) != r['fingerprint']]
    if len({r['path'] for r in rows}) != len(rows):
        raise ValueError('duplicate inventory path')
    if len(rows) > config['maximum_run_files'] or sum(r['bytes'] for r in rows) > config['maximum_run_bytes']:
        raise ValueError('current backlog exceeds admitted finite run; explicit review required')
    selection = batches(rows, maximum_files=config['maximum_batch_files'], maximum_bytes=config['maximum_batch_bytes'])
    if not selection:
        state = dict(phase='idle', at=clock(), selected_files=0, converted_files=0,
                     selected_scope_resolved=True, backup_payload_bytes=0)
        save(root / 'LATEST.private.json', state)
        return state
    identifier = uuid.uuid4().hex
    folder = root / 'runs' / identifier
    folder.mkdir(mode=0o700)
    save(folder / 'INVENTORY.private.json', snapshot)
    save(folder / 'SELECTION.private.json', selection)
    started = clock()
    state = dict(operation=identifier, folder=str(folder), started_at=started,
                 phase='selected', completed_batches=0, converted_files=0,
                 excluded_files=0, selected_files=len(rows), total_batches=len(selection))
    save(active, state)
    try:
        adapter.begin(folder, identifier)
        for number, batch in enumerate(selection):
            if clock() - started > config['maximum_run_seconds']:
                state['budget_boundary_reached'] = True
                break
            state.update(phase='batch_in_progress', batch=number)
            save(active, state)
            outcome = adapter.convert(folder / ('batch-%04d' % number), batch)
            if outcome.get('independent_recovery_verified') is not True:
                raise ValueError('independently verified terminal batch required')
            if outcome['converted_files'] + len(outcome['nonbeneficial']) != len(batch['rows']):
                raise ValueError('batch did not resolve its complete selection')
            originals = {r['path']: r for r in batch['rows']}
            if not set(outcome['nonbeneficial']).issubset(originals):
                raise ValueError('foreign exclusion')
            for name in outcome['nonbeneficial']:
                excluded[name] = originals[name]['fingerprint']
            save(excluded_path, excluded)
            save(folder / ('BATCH-%04d.private.json' % number), outcome)
            state.update(phase='batch_committed', completed_batches=number + 1,
                         converted_files=state['converted_files'] + outcome['converted_files'],
                         excluded_files=state['excluded_files'] + len(outcome['nonbeneficial']))
            save(active, state)
        adapter.finish(folder, state)
        state.update(phase='complete', finished_at=clock(),
                     selected_scope_resolved=state['completed_batches'] == len(selection))
        save(folder / 'RESULT.private.json', state)
        save(root / 'LATEST.private.json', state)
        active.unlink()
        fd = os.open(root, os.O_DIRECTORY | os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return state
    except BaseException as error:
        state.update(phase='needs_review', error_type=type(error).__name__, error=str(error), failed_at=clock())
        save(active, state)
        save(folder / 'FAILURE.private.json', state)
        save(root / 'LATEST.private.json', state)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    args = parser.parse_args()
    config = json.loads(source(dict(path=str(args.config), sha256=args.sha256)))
    if config['format'] != 'vk-incremental-log-conversion-v1' or not os.path.ismount('/mnt/vk-storage'):
        raise ValueError('qualified configuration and mounted SSD required')
    if digest(__file__) != config['runner_sha256']:
        raise ValueError('runner differs from qualified source')
    root = Path(config['state_root'])
    if root.resolve() != root or not root.is_relative_to('/mnt/vk-storage/vk-log-dedup-20261103-0815/production-20261117'):
        raise ValueError('canonical dedicated production task root required')
    for reference in config['sources']:
        source(reference)
    # Use the existing converter ownership inode; do not replace it or compete.
    fd = os.open(config['production_lock'], os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        if info.st_uid != os.getuid() or info.st_nlink != 1 or info.st_mode & 0o022:
            raise ValueError('production owner lock changed')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        raw = source(config['adapter'])
        module = importlib.util.module_from_spec(importlib.util.spec_from_loader('incremental_owner', loader=None))
        module.__file__ = config['adapter']['path']
        exec(compile(raw, module.__file__, 'exec'), module.__dict__)
        print(json.dumps(execute(config, module.Adapter(config)), sort_keys=True))
    finally:
        os.close(fd)


if __name__ == '__main__':
    main()
