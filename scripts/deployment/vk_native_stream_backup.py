"""Bounded SQLite API images streamed to an independently verified object store.

No service controls, production writes, credential reads or disk payload staging.
The caller owns its source allowlist, object-store authorization, memory/cgroup
limits, receipt custody and final physical writer fence. Online images are old
points, never evidence of a new final capture. Reuse requires the sealed receipt,
unchanged DB/WAL/journal identities and another real object-store verification.
"""
import hashlib
from pathlib import Path
import sqlite3
import stat
import time


def identity(path):
    path = Path(path)
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('Unique regular SQLite source/sidecar required')
    return [info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns, info.st_uid, info.st_gid]


def generation(source):
    return {suffix: identity(str(source) + suffix) for suffix in ('', '-wal', '-journal')}


class HashSink:
    def __init__(self):
        self.hash = hashlib.sha256()
        self.size = 0

    def write(self, raw):
        self.hash.update(raw)
        self.size += len(raw)
        return len(raw)


def capture_sqlite(source, client, *, maximum_image_bytes, chunk_bytes, guard, progress=lambda **_: None):
    source = Path(source)
    if not source.is_absolute() or source.resolve(strict=True) != source:
        raise ValueError('Explicit resolved source required')
    if not 0 < chunk_bytes <= 64 * 1024**2 or maximum_image_bytes <= 0:
        raise ValueError('Explicit positive image bound and bounded object size required')
    guard(0)
    with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True, timeout=2) as original:
        original.execute('PRAGMA query_only=ON')
        original.execute('BEGIN')
        page_size = original.execute('PRAGMA page_size').fetchone()[0]
        expected = original.execute('PRAGMA page_count').fetchone()[0] * page_size
        if expected > maximum_image_bytes:
            raise ValueError('SQLite image exceeds admitted memory bound')
        before = generation(source)
        guard(expected * 2)
        copied = -1
        with sqlite3.connect(':memory:') as image:
            image.execute('PRAGMA temp_store=MEMORY')
            def pages(status, remaining, total):
                nonlocal copied
                if total * page_size > maximum_image_bytes:
                    raise ValueError('Growing SQLite image exceeds memory bound')
                guard(32 * 1024**2)
                if total - remaining > copied:
                    copied = total - remaining
                    progress(phase='SQLite_API_pages', completed_pages=copied, total_pages=total)
            original.backup(image, pages=4096, progress=pages)
            if image.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise ValueError('SQLite API image failed integrity')
            guard(expected)
            payload = image.serialize()
        # sqlite3's context manager handles transactions, not connection closure.
        image.close()
        if len(payload) > maximum_image_bytes or generation(source) != before:
            raise ValueError('Source changed during API capture; image is not reusable')
    original.close()
    # SQLite explicitly requires rollback-format header bytes for deserialize:
    # https://www.sqlite.org/c3ref/deserialize.html . Normalize ONLY the detached
    # API image, never the source DB/WAL, after the API has incorporated WAL pages.
    header = list(payload[18:20])
    if header not in ([1, 1], [2, 2]):
        raise ValueError('Unsupported serialized SQLite journal header')
    if header == [2, 2]:
        guard(len(payload))
        detached = bytearray(payload)
        del payload
        detached[18:20] = b"\x01\x01"
        payload = detached
    # Reopen the serialization independently before accepting its bytes.
    guard(len(payload))
    reopened = sqlite3.connect(':memory:')
    try:
        reopened.deserialize(payload)
        reopened.execute('PRAGMA temp_store=MEMORY')
        if reopened.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise ValueError('Serialized SQLite image failed independent reopen')
    finally:
        reopened.close()
    expected_hash = hashlib.sha256(payload).hexdigest()
    restored, segments = HashSink(), []
    for offset in range(0, len(payload), chunk_bytes):
        guard(chunk_bytes * 2)
        segments.append(client.ensure(bytes(memoryview(payload)[offset:offset + chunk_bytes]), readback_sink=restored))
        progress(phase='Desktop_B_readback', verified_bytes=restored.size, total_bytes=len(payload))
    if restored.size != len(payload) or restored.hash.hexdigest() != expected_hash:
        raise ValueError('Independent object-store restore differs from SQLite image')
    return dict(schema=1, source=str(source), method='SQLite-backup-API-memory-serialize',
                original_source_API_point_at=time.time(), source_generation=before,
                bytes=len(payload), sha256=expected_hash, segments=segments,
                sqlite_integrity='ok', independently_reopened_sqlite=True,
                detached_header_before=header, detached_header_after=[1, 1],
                independent_native_readback_verified=True, disk_payload_bytes_written=0,
                new_final_epoch_claimed=False)


def verify_unchanged(row, client, *, guard, progress=lambda **_: None):
    """Caller must authenticate row custody and hold the actual final writer fence."""
    source = Path(row['source'])
    if (row.get('schema') != 1 or row.get('method') != 'SQLite-backup-API-memory-serialize'
            or row.get('independently_reopened_sqlite') is not True
            or row.get('independent_native_readback_verified') is not True
            or row.get('new_final_epoch_claimed') is not False
            or source.resolve(strict=True) != source or generation(source) != row['source_generation']):
        raise ValueError('Fresh SQLite API capture required')
    restored = HashSink()
    for segment in row['segments']:
        guard(0)
        client.verify(segment, restored)
        progress(phase='Desktop_B_reverification', verified_bytes=restored.size, total_bytes=row['bytes'])
    if (restored.size != row['bytes'] or restored.hash.hexdigest() != row['sha256']
            or generation(source) != row['source_generation']):
        raise ValueError('Changed source or independent B restore; no final reuse')
    return dict(source=str(source), original_source_API_point_at=row['original_source_API_point_at'],
                unchanged_image_reverified=True, new_final_epoch_claimed=False,
                sha256=row['sha256'], bytes=row['bytes'])
