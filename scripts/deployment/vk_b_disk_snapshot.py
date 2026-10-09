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
