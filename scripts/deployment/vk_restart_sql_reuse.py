"""Read-only qualification of an authenticated, unchanged closed SQL source.

The caller must authenticate the old API point through the retained Nightly
provider first. This module neither accepts backup contents nor makes an old
image a new API epoch. Mandatory sources and every sidecar remain fresh-API
work. Any subsequent source change invalidates this qualification.
"""
import base64
import math
import os
from pathlib import Path
import stat


def fingerprint(info):
    return [info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns, info.st_uid, info.st_gid, info.st_nlink]


def attributes(path):
    return {name: base64.b64encode(os.getxattr(path, name)).decode()
            for name in os.listxattr(path)}


def qualify_closed_source(path, accepted, *, mandatory_sources, guard):
    """Return an eligibility proof only; caller retains B and journal guards."""
    path = Path(path)
    result = {'source': str(path), 'eligible_unchanged_SQL_reuse': False,
              'new_API_epoch_claimed': False, 'backup_acceptance_claimed': False,
              'source_body_bytes_copied': 0}

    def refused(reason):
        return dict(result, reason=reason)

    if str(path) in mandatory_sources:
        return refused('Externally mandatory source requires a fresh API point')
    point = accepted
    member = point.get('member', {})
    proof = point.get('independent', {})
    epoch = point.get('original_source_API_point_at')
    def digest(value):
        return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)

    if (point.get('source') != str(path)
            or point.get('status') != 'consistent_SQL_point_verified'
            or point.get('method') != 'SQLite-backup-API'
            or point.get('source_API_point_qualifies_later_epoch_not_original') is not True
            or point.get('source_changed_online') is not False
            or member.get('kind') != 'file'
            or type(point.get('bytes')) is not int or point['bytes'] <= 0
            or not digest(point.get('sha256'))
            or not digest(point.get('B_acceptance_object', {}).get('sha256'))
            or proof.get('integrity') != 'ok'
            or type(epoch) not in (int, float) or not math.isfinite(epoch) or epoch <= 0
            or any(point.get(key) != member.get(key) or proof.get(key) != member.get(key)
                   for key in ('bytes', 'sha256'))):
        return refused('Authenticated stable API point is incomplete')
    before = point.get('source_metadata_before', {})
    after = point.get('source_metadata_after', {})
    fields = ('device', 'inode', 'uid', 'gid', 'mode', 'mtime_ns', 'ctime_ns', 'xattrs')
    if any(key not in before or key not in after or before[key] != after[key] for key in fields):
        return refused('Source changed during its accepted API capture')
    expected = point.get('source_identity_before')
    if not isinstance(expected, list) or len(expected) != 9:
        return refused('Exact accepted source identity is missing')
    identity_metadata = [before['device'], before['inode'], stat.S_IFREG | before['mode'],
                         expected[3], before['mtime_ns'], before['ctime_ns'],
                         before['uid'], before['gid'], expected[8]]
    if expected != identity_metadata or any(member.get(key) != before[key]
                                            for key in ('uid', 'gid', 'mode', 'mtime_ns', 'xattrs')):
        return refused('Accepted identity and Linux metadata disagree')
    # A zero-length WAL/SHM/journal still indicates a source whose sidecar
    # lifecycle requires SQLite. Do not open it with SQLite to inspect it.
    def has_sidecars():
        return any(os.path.lexists(str(path) + suffix) for suffix in ('-wal', '-shm', '-journal'))

    try:
        guard()
        if not path.is_absolute() or path.resolve() != path or has_sidecars():
            return refused('Canonical closed source without sidecars required')
        current = path.lstat()
        if not stat.S_ISREG(current.st_mode) or fingerprint(current) != expected:
            return refused('Current source differs from the accepted API source')
        if attributes(path) != before['xattrs']:
            return refused('Current source attributes differ')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            if fingerprint(os.fstat(fd)) != expected or os.read(fd, 16) != b'SQLite format 3\0':
                return refused('Opened source/header differs')
            guard()
            if (has_sidecars() or fingerprint(os.fstat(fd)) != expected
                    or fingerprint(path.lstat()) != expected or attributes(path) != before['xattrs']):
                return refused('Source changed during qualification')
        finally:
            os.close(fd)
        guard()
    except OSError as error:
        return refused('Source qualification unavailable: ' + type(error).__name__)
    return dict(result, eligible_unchanged_SQL_reuse=True,
                source_identity=expected, xattrs=before['xattrs'],
                accepted_image_sha256=point['sha256'], accepted_image_bytes=point['bytes'],
                accepted_API_point_at=epoch,
                accepted_B_object_sha256=point['B_acceptance_object']['sha256'],
                source_header_bytes_read=16,
                fresh_journal_and_final_source_recheck_required=True)
