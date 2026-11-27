"""Per-workspace Linux flock protocol shared by readers, launches and the mover.

Permanent lock inodes are never unlinked. Shared readers/launch admission may
coexist; exclusive archive/restore custody never blocks an unrelated workspace.
The caller must also verify current application/native/process ownership.
"""
import fcntl
import os
from pathlib import Path
import stat
import uuid

PROTOCOL = 1


class Busy(RuntimeError):
    pass


class Custody:
    def __init__(self, root, workspace, *, exclusive):
        root = Path(root)
        if not root.is_absolute() or root.resolve(strict=True) != root:
            raise ValueError('Canonical existing custody root required')
        st = root.lstat()
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
            raise ValueError('Private owned custody root required')
        self.root_identity = (st.st_dev, st.st_ino)
        self.root = root
        self.path = root / (str(uuid.UUID(workspace)) + '.lock')
        self.fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        self.exclusive = exclusive
        try:
            self.check()
            try:
                fcntl.flock(self.fd, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise Busy('Workspace payloads are in use') from error
            self.check()
        except BaseException:
            self.close()
            raise

    def check(self):
        root = self.root.lstat()
        named = self.path.lstat()
        opened = os.fstat(self.fd)
        if (self.root.resolve(strict=True) != self.root
                or (root.st_dev, root.st_ino) != self.root_identity
                or not stat.S_ISDIR(root.st_mode) or root.st_uid != os.getuid() or root.st_mode & 0o077
                or not stat.S_ISREG(opened.st_mode) or not stat.S_ISREG(named.st_mode)
                or (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino)
                or opened.st_nlink != 1 or opened.st_uid != os.getuid() or opened.st_mode & 0o077):
            raise ValueError('Workspace custody identity or permissions changed')

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
