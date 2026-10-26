"""One strictly stable online file version for a later, explicit recovery layer.

The controller supplies a direct-to-B sink and existing admission/STOP callback.
No local payload, global inventory, silent retry, source lock or writer pause.
A moving file leaves an unaccepted partial at the controller's existing sink;
completed components are unaffected. Source epoch/identity and Linux metadata
are explicit, not relabeled as the failed selector's original snapshot.
"""
import base64
import datetime
import hashlib
import os
from pathlib import Path
import stat


def fingerprint(st):
    return [st.st_dev, st.st_ino, st.st_mode, st.st_size, st.st_mtime_ns,
            st.st_ctime_ns, st.st_uid, st.st_gid, st.st_nlink]


def stream_hash(stream):
    """Bounded Python3.9-compatible independent readback on native Desktop."""
    h = hashlib.sha256()
    while block := stream.read(64*1024):
        h.update(block)
    return h.hexdigest()


def attributes(path):
    return {name: base64.b64encode(os.getxattr(path, name, follow_symlinks=False)).decode()
            for name in sorted(os.listxattr(path, follow_symlinks=False))}


def capture_version(path, sink, *, maximum_bytes, guard, clock=None):
    """Return a seal only after an unchanged open-fstat/path/attribute bracket."""
    clock = clock or (lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    path = Path(path)
    if not path.is_absolute() or path.resolve() != path:
        raise ValueError('exact canonical non-symlink file version required')
    if type(maximum_bytes) is not int or maximum_bytes <= 0:
        raise ValueError('measured finite single-file budget required')
    guard(); before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > maximum_bytes:
        raise ValueError('source is not an admitted regular file')
    attrs = attributes(path); started = clock(); h = hashlib.sha256(); total = 0
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(fd, 'rb', buffering=0) as source:
        if fingerprint(os.fstat(source.fileno())) != fingerprint(before):
            raise ValueError('file version changed before open')
        while block := source.read(min(64*1024, before.st_size-total+1)):
            guard()
            if total == 0 and block.startswith(b'SQLite format 3\x00'):
                raise ValueError('SQLite requires its consistent snapshot API')
            total += len(block)
            if total > before.st_size:
                raise ValueError('file version grew during stream; preserve unaccepted partial')
            h.update(block)
            view = memoryview(block)
            while view:
                written = sink.write(view)
                if type(written) is not int or not 0 < written <= len(view):
                    raise OSError('backup sink stopped accepting complete source bytes')
                view = view[written:]
        if total != before.st_size or fingerprint(os.fstat(source.fileno())) != fingerprint(before):
            raise ValueError('file version changed during stream; preserve unaccepted partial')
    if fingerprint(path.lstat()) != fingerprint(before) or attributes(path) != attrs:
        raise ValueError('file path/metadata changed during stream; preserve partial')
    guard()
    return {'format': 'vk-nightly-stable-file-version-v1', 'source': str(path),
            'source_identity': fingerprint(before), 'bytes': total, 'sha256': h.hexdigest(),
            'metadata': {'mode': stat.S_IMODE(before.st_mode), 'uid': before.st_uid, 'gid': before.st_gid,
                         'mtime_ns': before.st_mtime_ns, 'atime_ns_before_read': before.st_atime_ns,
                         'xattrs': attrs}, 'started_at': started, 'completed_at': clock(),
            'consistency': 'stable open/fstat and pathname/attribute bracket',
            'later_epoch_supplement': True, 'original_failed_epoch_repaired': False,
            'live_writer_fenced': False, 'current_set_accepted': False}
