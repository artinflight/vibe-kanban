"""Finite exact-file recovery through the existing held normal-B owner.

This module never acquires another owner, schedules backups, publishes archives,
or retries a capture. An intent without verified completion requires reconciliation.
"""
from pathlib import Path
import hashlib
import json
import os
import re

LIMIT = 48 * 1024**2


def batches(rows, maximum=LIMIT):
    if type(maximum) is not int or not 1 <= maximum <= 64 * 1024**2:
        raise ValueError('Bounded checkpoint size required')
    seen, pending, size = set(), [], 0
    for row in rows:
        if (row['path'] in seen or type(row['bytes']) is not int
                or not 0 <= row['bytes'] <= maximum):
            raise ValueError('Unique bounded exact files required')
        seen.add(row['path'])
        if pending and (len(pending) == 64 or size + row['bytes'] > maximum):
            yield pending
            pending, size = [], 0
        pending.append(row)
        size += row['bytes']
    if pending:
        yield pending


def verify_scope(receipt, rows):
    expected = {r['path']: (r['bytes'], r['sha256']) for r in rows}
    points = receipt['manifest']['files']
    actual = {r['source']: (r['member']['bytes'], r['member']['sha256']) for r in points}
    if len(expected) != len(rows) or len(actual) != len(points) or actual != expected:
        raise ValueError('Normal B checkpoint differs from exact selected files')


def write_new(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(value, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def checkpoint_once(folder, name, rows, *, guard, capture, restore, progress):
    """Persist intent, capture and restore separately; never replay uncertain work."""
    folder = Path(folder)
    if not re.fullmatch(r'[A-Z][A-Z0-9_-]{0,79}', name):
        raise ValueError('Exact bounded checkpoint name required')
    if len(list(batches(rows))) != 1:
        raise ValueError('Exactly one bounded checkpoint required')
    paths = [folder / (name + suffix + '.private.json')
             for suffix in ('_INTENT', '_CAPTURE', '_VERIFIED')]
    if any(p.exists() or p.is_symlink() for p in paths):
        raise FileExistsError('Existing intent or receipt must be reconciled, never replayed')
    guard()
    for row in rows:
        path = Path(row['path'])
        if not path.is_absolute() or path.resolve(strict=True) != path or not path.is_file():
            raise ValueError('Canonical regular source required')
        with path.open('rb') as source:
            before = os.fstat(source.fileno())
            if before.st_size != row['bytes'] or hashlib.file_digest(source, 'sha256').hexdigest() != row['sha256']:
                raise ValueError('Selected recovery source changed')
    write_new(paths[0], dict(files=rows, replay_allowed=False))
    receipt = capture([r['path'] for r in rows], max(1, sum(r['bytes'] for r in rows)))
    write_new(paths[1], receipt)
    verify_scope(receipt, rows)
    verified = restore(receipt)
    proof = verified['actual_independent_normal_restore']
    if (not proof['independent_owner_controls_restore_verified']
            or proof['files'] != len(rows)
            or proof['raw_bytes'] != sum(r['bytes'] for r in rows)):
        raise ValueError('Actual independent normal B restoration is incomplete')
    guard()
    write_new(paths[2], verified)
    progress(name, len(rows), sum(r['bytes'] for r in rows))
    return verified
