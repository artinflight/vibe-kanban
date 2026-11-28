"""Bound peak disk demand before packing each closed-log batch.

Use a gzip expansion bound plus full filesystem blocks for objects and directory
entries, both staging/publication copies, and complete raw rollback. Recompute
available space after each yielded batch; do not skip a large eligible source or
spend the reserve. This is capacity admission, not writer or backup authority.
"""
import os
from pathlib import Path

import log_dedup as logs

CONTROL_ALLOWANCE = 16 * 1024**2
MAX_BATCH_BYTES = 512 * 1024**2


def bound(raw_bytes, sidecar_bytes, *, fragment=4096):
    if (type(raw_bytes) is not int or raw_bytes < 0 or type(fragment) is not int
            or fragment < 512 or any(type(n) is not int or n < 0 for n in sidecar_bytes)):
        raise ValueError('Nonnegative exact sizes and filesystem fragment required')
    chunks = (raw_bytes + logs.MIN_CHUNK - 1) // logs.MIN_CHUNK
    rounded = lambda n: ((n + fragment - 1) // fragment) * fragment
    # Existing readers cap each gzip object at MAX_CHUNK+1024. Deflate overhead
    # is below this per-chunk allowance, including the gzip header/trailer.
    objects = raw_bytes + chunks * (1024 + fragment - 1)
    # At most one complete directory block per object. Manifest records use
    # fewer than 128 bytes each, including the largest allowed chunk length.
    directories = (chunks + 8) * fragment
    manifest = rounded(256 + chunks * 128)
    sidecars = sum(rounded(n) for n in sidecar_bytes)
    archive = objects + directories + manifest + sidecars
    return dict(raw_bytes=raw_bytes, maximum_chunks=chunks,
                archive_upper_bytes=archive,
                peak_extra_bytes=2 * archive + rounded(raw_bytes))


def selection(observation, exclude):
    if not observation.get('complete'):
        raise ValueError('Complete closed-log observation required')
    root = Path(observation['root'])
    selected, tiny = [], []
    for name in observation['eligible_closed_inactive_files']:
        if name in exclude:
            continue
        row = observation['files'][name]
        if row['allocated_bytes'] <= 4096:
            tiny.append(name)
            continue
        source = logs.safe_path(root, name)
        if logs.version(logs.regular(source)) != row['identity']:
            raise ValueError('Selected closed log changed')
        sidecars = []
        for extension in ('capture.json', 'recovered-final.json'):
            path = source.with_suffix('.' + extension)
            if path.exists() or path.is_symlink():
                sidecars.append(logs.regular(path).st_size)
        selected.append(dict(path=name, raw_bytes=row['raw_bytes'], sidecar_bytes=sidecars))
    selected.sort(key=lambda row: (row['raw_bytes'], row['path']))
    return dict(sources=selected, preserved_nonbeneficial_tiny=tiny,
                control_allowance_bytes=CONTROL_ALLOWANCE,
                order='ascending_source_bytes', admission='worst_case_before_every_pack')


def batches(selection, *, available, reserve_bytes, fragment=4096, record=lambda value: None):
    if type(reserve_bytes) is not int or reserve_bytes < 0:
        raise ValueError('Explicit unchanged reserve required')
    pending = list(selection['sources'])
    while pending:
        free = available()
        if type(free) is not int or free < 0:
            raise ValueError('Actual available filesystem bytes required')
        budget = free - reserve_bytes - CONTROL_ALLOWANCE
        names, demand, raw, bodies = [], 0, 0, 0
        for row in pending:
            size = row['raw_bytes'] + sum(row['sidecar_bytes'])
            count = 1 + len(row['sidecar_bytes'])
            peak = bound(row['raw_bytes'], row['sidecar_bytes'], fragment=fragment)['peak_extra_bytes']
            if size > MAX_BATCH_BYTES or count > 32:
                raise ValueError('One source exceeds supported recovery envelope')
            if len(names) >= 16 or bodies + count > 32 or raw + size > MAX_BATCH_BYTES or demand + peak > budget:
                break
            names.append(row['path'])
            demand += peak
            raw += size
            bodies += count
        if not names:
            raise ValueError('Insufficient staging/publication/rollback headroom; preserve remaining sources')
        record(dict(files=len(names), source_and_sidecar_bytes=raw,
                    peak_extra_bytes=demand, control_allowance_bytes=CONTROL_ALLOWANCE,
                    available_bytes=free, reserve_bytes=reserve_bytes))
        yield names
        del pending[:len(names)]


def filesystem_available(root):
    value = os.statvfs(root)
    return value.f_bavail * value.f_frsize
