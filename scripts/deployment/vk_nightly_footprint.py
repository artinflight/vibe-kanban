"""Streaming read-only measurement of the already bound nightly source plan.

No global file list, inode set, content cache, capture, publication or cleanup.
Only source roots, at most 1024 SQLite identities and 128 sample locators live
in memory. Compression samples are estimates, never exact allocation proof.
"""
import ctypes
import hashlib
import heapq
import json
import os
from pathlib import Path
import stat
import time
import zlib
from collections import deque
from concurrent.futures import ThreadPoolExecutor

from vk_rolling_backup import Exclusions


MAX_DATABASES = 1024
MAX_DEPTH = 256
SAMPLES = 128
SAMPLE_BYTES = 65536


def roots(plan):
    """Match scan's explicit root-symlink coverage without a whole-path set."""
    candidates = set(plan['sources'])
    for raw in plan['sources']:
        if Path(raw).is_symlink():
            candidates.add(str(Path(raw).resolve(strict=True)))
    minimal = []
    for raw in sorted(candidates, key=lambda x: (len(Path(x).parts), x)):
        if not any(Path(raw).is_relative_to(parent) for parent in minimal):
            minimal.append(raw)
    return minimal


def _walk_records(plan):
    """Depth-bounded scandir iterators, no per-directory lists; no child links."""
    exclusions = Exclusions(plan)
    for raw in roots(plan):
        if exclusions(raw):
            raise ValueError('declared source root is excluded')
        info = os.lstat(raw)
        yield raw, info, None, raw
        if not stat.S_ISDIR(info.st_mode):
            continue
        fd = os.open(raw, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            os.close(fd)
            raise ValueError('source directory substituted')
        stack = [(fd, os.scandir(fd), raw)]
        try:
            while stack:
                try:
                    entry = next(stack[-1][1])
                except StopIteration:
                    parent_fd, iterator, _ = stack.pop()
                    iterator.close()
                    os.close(parent_fd)
                    continue
                parent_fd, _, parent = stack[-1]
                raw = os.path.join(parent, entry.name)
                if exclusions(raw):
                    continue
                try:
                    info = entry.stat(follow_symlinks=False)
                except FileNotFoundError:
                    # The caller can distinguish an online vanished name from
                    # a declared required root/database disappearing.
                    yield raw, None, parent_fd, entry.name
                    continue
                yield raw, info, parent_fd, entry.name
                if stat.S_ISDIR(info.st_mode):
                    if len(stack) >= MAX_DEPTH:
                        raise ValueError('source directory depth bound exceeded')
                    child_fd = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
                    opened = os.fstat(child_fd)
                    if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                        os.close(child_fd)
                        raise ValueError('source directory substituted')
                    stack.append((child_fd, os.scandir(child_fd), raw))
        finally:
            for fd, iterator, _ in stack:
                iterator.close()
                os.close(fd)
    exclusions.validate()


def walk(plan):
    for raw, info, _, _ in _walk_records(plan):
        yield raw, info


def regular_header(raw, expected, *, parent_fd=None, name=None):
    fd = os.open(name if parent_fd is not None else raw,
                 os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_fd)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or (before.st_dev, before.st_ino) != (expected.st_dev, expected.st_ino):
            raise ValueError('inventory file identity/type changed')
        header = os.read(fd, 16)
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
            raise ValueError('inventory file identity changed during header read')
        return header
    finally:
        os.close(fd)


class Samples:
    def __init__(self, maximum=SAMPLES):
        self.maximum = maximum
        self.heap = []

    def add(self, raw, size):
        if size <= 0:
            return
        uniform = (int.from_bytes(hashlib.sha256(os.fsencode(raw)).digest()[:8], 'big') + 1) / (2**64 + 1)
        row = (size / uniform, raw, size)
        if len(self.heap) < self.maximum + 1:
            heapq.heappush(self.heap, row)
        elif row > self.heap[0]:
            heapq.heapreplace(self.heap, row)

    def selected(self):
        ordered = sorted(self.heap, reverse=True)
        threshold = ordered[-1][0] if len(ordered) > self.maximum else 0
        return [(raw, size, max(size, threshold)) for _, raw, size in ordered[:self.maximum]]


def header_records(plan, workers):
    if type(workers) is not int or not 1 <= workers <= 8:
        raise ValueError('inventory header worker bound is one to eight')
    if workers == 1:
        for raw, info, parent, name in _walk_records(plan):
            try:
                header=regular_header(raw,info,parent_fd=parent,name=name) if info and stat.S_ISREG(info.st_mode) else None
            except FileNotFoundError:info=None;header=None
            yield raw,info,header
        return
    def read(raw,info,parent,name):
        try:
            return regular_header(raw,info,parent_fd=parent,name=name)
        finally:
            if parent is not None:os.close(parent)
    def complete(item):
        raw,info,future=item
        try:return raw,info,future.result()
        except FileNotFoundError:return raw,None,None
    pending=deque()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for raw,info,parent,name in _walk_records(plan):
            if info and stat.S_ISREG(info.st_mode):
                duplicate=os.dup(parent) if parent is not None else None
                try:future=pool.submit(read,raw,info,duplicate,name)
                except BaseException:
                    if duplicate is not None:os.close(duplicate)
                    raise
                pending.append((raw,info,future))
                if len(pending)>=64:yield complete(pending.popleft())
            else:yield raw,info,None
        while pending:yield complete(pending.popleft())


def inventory(plan, *, socket_exclusions=(), progress=None, workers=1):
    started = time.monotonic()
    required = set(plan.get('sqlite_snapshots', ())) | set(plan.get('critical_sqlite', ()))
    databases = {}
    samples = Samples()
    result = {'paths': 0, 'files': 0, 'logical_bytes': 0, 'allocated_bytes': 0,
              'directories': 0, 'symlinks': 0, 'vanished': 0, 'socket_omissions': 0,
              'JSONL_bytes': 0, 'read_only': True, 'content_hashed': False}
    allowed_sockets = set(socket_exclusions)
    for raw, info, header in header_records(plan,workers):
        result['paths'] += 1
        if info is None:
            if raw in required:
                raise ValueError('required database disappeared')
            result['vanished'] += 1
            continue
        mode = info.st_mode
        if stat.S_ISREG(mode):
            result['files'] += 1
            result['logical_bytes'] += info.st_size
            result['allocated_bytes'] += info.st_blocks * 512
            if raw.endswith('.jsonl'):
                result['JSONL_bytes'] += info.st_size
            if header == b'SQLite format 3\0':
                databases[str(Path(raw).resolve())] = {'bytes': info.st_size,
                    'identity': [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns]}
                if len(databases) > MAX_DATABASES:
                    raise ValueError('SQLite inventory metadata bound exceeded')
            samples.add(raw, info.st_size)
        elif stat.S_ISDIR(mode):
            result['directories'] += 1
        elif stat.S_ISLNK(mode):
            result['symlinks'] += 1
        elif stat.S_ISSOCK(mode) and raw in allowed_sockets:
            result['socket_omissions'] += 1
        else:
            raise ValueError('unapproved special source member: ' + raw)
        if progress and result['paths'] % 4096 == 0:
            progress(dict(result, seconds=time.monotonic()-started))
    if required - databases.keys():
        raise ValueError('required SQLite database absent or invalid')
    result.update(databases=databases, database_bytes=sum(r['bytes'] for r in databases.values()),
                  maximum_database_bytes=max((r['bytes'] for r in databases.values()), default=0),
                  seconds=time.monotonic()-started,
                  consistency='online metadata measurement, not a coherent snapshot',
                  sample_locators=samples.selected())
    return result


def compression_samples(locators, logical_bytes):
    library = ctypes.CDLL('libzstd.so.1')
    library.ZSTD_compressBound.argtypes = [ctypes.c_size_t]
    library.ZSTD_compressBound.restype = ctypes.c_size_t
    library.ZSTD_compress.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
    library.ZSTD_compress.restype = ctypes.c_size_t
    library.ZSTD_isError.argtypes = [ctypes.c_size_t]
    library.ZSTD_isError.restype = ctypes.c_uint
    weight = object_estimate = archive_estimate = sampled = 0
    for raw, expected_size, adjusted in locators:
        fd = os.open(raw, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_size != expected_size:
                raise ValueError('compression sample source changed')
            span = max(1, expected_size-SAMPLE_BYTES+1)
            offset = int.from_bytes(hashlib.sha256(os.fsencode(raw)+b'offset').digest()[:8], 'big') % span
            data = os.pread(fd, min(SAMPLE_BYTES, expected_size), offset)
            after = os.fstat(fd)
            if not data or (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
                raise ValueError('compression sample changed while reading')
        finally:
            os.close(fd)
        target = ctypes.create_string_buffer(library.ZSTD_compressBound(len(data)))
        length = library.ZSTD_compress(target, len(target), data, len(data), 3)
        if library.ZSTD_isError(length):
            raise ValueError('bounded zstd sample failed')
        weight += adjusted
        object_estimate += adjusted * len(zlib.compress(data, 1))/len(data)
        archive_estimate += adjusted * length/len(data)
        sampled += len(data)
    if not weight:
        return {'samples': 0, 'sampled_bytes': 0, 'estimated_objects': 0, 'estimated_archive': 0, 'exact': False}
    return {'samples': len(locators), 'sampled_bytes': sampled,
            'estimated_objects': round(logical_bytes*object_estimate/weight),
            'estimated_archive': round(logical_bytes*archive_estimate/weight), 'exact': False,
            'method': 'bounded deterministic priority sample; ratios are not a worst-case capacity guarantee'}
