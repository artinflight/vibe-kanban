"""Bounded SQLite backup onto an independently verified, existing-access B mount.

This preserves an additional online snapshot, not a whole-state checkpoint or
writer-fenced cutover receipt. Failed outputs stay retained and unaccepted.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import time
import uuid


def checked_mount(root):
    root = Path(root).absolute()
    data = json.loads(subprocess.check_output(['findmnt', '-J', '-T', str(root)]))['filesystems'][0]
    if (data['target'] != str(root) or data['fstype'] != 'fuse.sshfs'
            or data['source'] != 'desktop:/B:/vk-backups/vk-safe-release-20261009'):
        raise ValueError('Snapshot destination is not the exact established Desktop B mount')
    return root


def metadata(path):
    st = path.stat()
    return {'uid': st.st_uid, 'gid': st.st_gid, 'mode': st.st_mode & 0o7777,
            'mtime_ns': st.st_mtime_ns, 'atime_ns': st.st_atime_ns,
            'ctime_ns': st.st_ctime_ns, 'device': st.st_dev, 'inode': st.st_ino,
            'xattrs': {name: base64.b64encode(os.getxattr(path, name)).decode()
                       for name in os.listxattr(path)}}


def snapshot(source, root, allowed_sources, *, destination_verifier):
    """Caller must independently verify physical B bytes, integrity and free space.

Require a private new name; retain rejected files. Never serialize the DB into
RAM, alter source modes, set immutable=1 or copy live main-file bytes alone.
"""
    root = checked_mount(root)
    source = Path(source).absolute()
    if source.is_symlink() or str(source) not in allowed_sources or not source.is_file():
        raise ValueError('SQLite source is not an explicit regular-file scope member')
    before = metadata(source)
    started = time.monotonic()
    name = 'sqlite-consistent-' + uuid.uuid4().hex + '.sqlite'
    target = root / name
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    src = dst = None
    try:
        src = sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)
        src.execute('PRAGMA temp_store=MEMORY')
        src.execute('PRAGMA cache_size=-8192')
        src.execute('PRAGMA mmap_size=0')
        version = src.execute('PRAGMA data_version').fetchone()[0]
        src.execute('BEGIN')
        src.execute('SELECT name FROM sqlite_master LIMIT 1').fetchone()
        dst = sqlite3.connect(target)
        dst.execute('PRAGMA temp_store=MEMORY')
        dst.execute('PRAGMA cache_size=-8192')
        dst.execute('PRAGMA mmap_size=0')
        src.backup(dst, pages=4096)
        if dst.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise ValueError('Direct-B SQLite snapshot integrity failed')
        dst.close()
        dst = None
        src.rollback()
        changed = src.execute('PRAGMA data_version').fetchone()[0] != version
        src.close()
        src = None
        with target.open('rb') as stream:
            checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
        with target.open('rb') as stream:
            os.fsync(stream.fileno())
        remote = destination_verifier(name, checksum, target.stat().st_size)
        if (remote.get('physical_b_verified') is not True or remote.get('sha256') != checksum
                or remote.get('bytes') != target.stat().st_size or remote.get('integrity') != 'ok'):
            raise ValueError('Physical B snapshot readback is not independently verified')
        result = {'schema': 1, 'source': str(source), 'snapshot': name,
                  'sha256': checksum, 'bytes': target.stat().st_size,
                  'source_metadata_before': before, 'source_metadata_after': metadata(source),
                  'sqlite_source_changed_online': changed, 'backup_api_consistent_image': True,
                  'physical_b_verified': True, 'integrity': 'ok',
                  'seconds': time.monotonic() - started, 'online_preparation_only': True,
                  'writer_fenced': False, 'whole_state_verified': False,
                  'cutover_authorized': False, 'local_snapshot_payload_bytes': 0}
        receipt = root / (name + '.receipt.json')
        with receipt.open('x') as output:
            json.dump(result, output, sort_keys=True, indent=2)
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())
        return result
    finally:
        if dst is not None:
            dst.close()
        if src is not None:
            src.close()


def fenced_snapshot(source, root, allowed_sources, *, verify_fence, destination_verifier):
    """Stream a private image only under a positive, unchanged held writer fence.

    Do not open the source with SQLite or create WAL bookkeeping. The independently
    verified private B file may be read immutable for integrity validation.
    """
    root = checked_mount(root)
    source = Path(source).absolute()
    if source.is_symlink() or str(source) not in allowed_sources or not source.is_file():
        raise ValueError('Fenced SQLite source is outside explicit regular-file scope')
    fence = verify_fence()
    if (not isinstance(fence, dict) or fence.get('verified') is not True
            or fence.get('all_writers_stopped_verified') is not True
            or not all(fence.get(k) for k in ('capture_id', 'scope', 'lease'))):
        raise ValueError('Actual stopped writers and held fence are required')
    if any(os.path.lexists(str(source) + suffix) for suffix in ('-wal', '-shm', '-journal')):
        raise ValueError('Fenced source has SQLite sidecars; checkpoint proof is required')
    before = metadata(source)
    before_size = source.stat().st_size
    name = 'sqlite-consistent-' + uuid.uuid4().hex + '.sqlite'
    target = root / name
    checksum = hashlib.sha256()
    with source.open('rb') as src, target.open('xb') as dst:
        if src.read(16) != b'SQLite format 3\0':
            raise ValueError('Fenced source is not SQLite')
        src.seek(0)
        for block in iter(lambda: src.read(1024 * 1024), b''):
            dst.write(block)
            checksum.update(block)
        dst.flush()
        os.fsync(dst.fileno())
    after = metadata(source)
    fields = ('uid', 'gid', 'mode', 'mtime_ns', 'ctime_ns', 'device', 'inode', 'xattrs')
    if (any(after[k] != before[k] for k in fields) or source.stat().st_size != before_size
            or target.stat().st_size != before_size or verify_fence() != fence
            or any(os.path.lexists(str(source) + s) for s in ('-wal', '-shm', '-journal'))):
        raise ValueError('Fenced SQLite source or writer protection changed during copy')
    checked_mount(root)
    remote = destination_verifier(name, checksum.hexdigest(), before_size)
    if (remote.get('physical_b_verified') is not True or remote.get('private_immutable_read') is not True
            or remote.get('integrity') != 'ok' or remote.get('sha256') != checksum.hexdigest()
            or remote.get('bytes') != before_size or verify_fence() != fence):
        raise ValueError('Fenced private B image has no independent immutable integrity/readback proof')
    return {'source': str(source), 'snapshot': name, 'sha256': checksum.hexdigest(),
            'bytes': before_size, 'source_metadata_before': before, 'source_metadata_after': after,
            'physical_b_verified': True, 'integrity': 'ok', 'writer_fenced': True,
            'consistent_held_fence_raw_image': True, 'backup_api_consistent_image': False,
            'online_preparation_only': False, 'writer_fence': fence,
            'local_snapshot_payload_bytes': 0, 'whole_state_verified': False,
            'cutover_authorized': False}
