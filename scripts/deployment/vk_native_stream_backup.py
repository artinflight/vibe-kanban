"""Bounded SQLite API images on verified RAM, streamed to an independently verified object store.

No service controls, production writes, credential reads or disk payload staging.
The caller owns its source allowlist, object-store authorization, memory/cgroup
limits, receipt custody and final physical writer fence. Online images are old
points, never evidence of a new final capture. Reuse requires the sealed receipt,
unchanged DB/WAL/journal identities and another real object-store verification.
"""
import hashlib
import os
import tempfile
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
    # Python/SQLite serialize cannot allocate the 3.1 GB native history image.
    # Use the same explicitly verified tmpfs class as native B object readback;
    # no payload is staged on /, /tmp, /home or an unverified filesystem.
    if not any(line.split()[4] == '/dev/shm' and ' - tmpfs ' in line
               for line in Path('/proc/self/mountinfo').read_text().splitlines()):
        raise ValueError('Verified /dev/shm RAM filesystem required')
    guard(0)
    original = sqlite3.connect(source.as_uri() + '?mode=ro', uri=True, timeout=2)
    try:
        original.execute('PRAGMA query_only=ON')
        original.execute('BEGIN')
        page_size = original.execute('PRAGMA page_size').fetchone()[0]
        expected = original.execute('PRAGMA page_count').fetchone()[0] * page_size
        if expected > maximum_image_bytes:
            raise ValueError('SQLite image exceeds admitted memory bound')
        ram = os.statvfs('/dev/shm')
        if ram.f_bavail * ram.f_frsize < expected + 1024**3:
            raise ValueError('Insufficient RAM filesystem reserve')
        guard(expected + 256 * 1024**2)
        before = generation(source)
        copied = -1
        with tempfile.TemporaryDirectory(prefix='vk-owned-sqlite-stream-', dir='/dev/shm') as folder:
            path = Path(folder) / 'image.sqlite'
            image = sqlite3.connect(path)
            try:
                image.execute('PRAGMA journal_mode=MEMORY')
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
                # Only the detached RAM copy is converted to standalone rollback
                # mode using SQLite's API. Never edit source headers or WAL.
                if image.execute('PRAGMA journal_mode=DELETE').fetchone() != ('delete',):
                    raise ValueError('Standalone SQLite image conversion failed')
                captured_at = time.time()
            finally:
                image.close()
            if path.stat().st_size > maximum_image_bytes or generation(source) != before:
                raise ValueError('Source changed during API capture; image is not reusable')
            original.close()
            reopened = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
            try:
                reopened.execute('PRAGMA temp_store=MEMORY')
                if reopened.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                    raise ValueError('SQLite image failed independent reopen')
            finally:
                reopened.close()
            expected_hash, restored, segments = hashlib.sha256(), HashSink(), []
            with path.open('rb') as stream:
                while raw := stream.read(chunk_bytes):
                    guard(chunk_bytes * 2)
                    expected_hash.update(raw)
                    segments.append(client.ensure(raw, readback_sink=restored))
                    progress(phase='Desktop_B_readback', verified_bytes=restored.size, total_bytes=path.stat().st_size)
            if restored.size != path.stat().st_size or restored.hash.hexdigest() != expected_hash.hexdigest():
                raise ValueError('Independent object-store restore differs from SQLite image')
            return dict(schema=1, source=str(source), method='SQLite-backup-API-RAM-file',
                        original_source_API_point_at=captured_at, source_generation=before,
                        bytes=restored.size, sha256=expected_hash.hexdigest(), segments=segments,
                        sqlite_integrity='ok', independently_reopened_sqlite=True,
                        independent_native_readback_verified=True, disk_payload_bytes_written=0,
                        ram_payload_bytes=restored.size, new_final_epoch_claimed=False)
    finally:
        original.close()


def verify_unchanged(row, client, *, guard, progress=lambda **_: None):
    """Caller must authenticate row custody and hold the actual final writer fence."""
    source = Path(row['source'])
    if (row.get('schema') != 1 or row.get('method') != 'SQLite-backup-API-RAM-file'
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
