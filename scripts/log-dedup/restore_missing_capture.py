"""Create-only restoration of an exact missing original under writer protocol 1.

The caller must qualify the complete writer/reader roster and provide a guard
that binds the terminal execution, current SQL, recovery record and authorization.
No successful-capture marker is created; an incomplete original stays incomplete.
"""
from contextlib import ExitStack
import fcntl
import hashlib
import os
from pathlib import Path
import stat
import uuid

import log_dedup as logs


def restore_missing(root, relative, source, expected_hash, expected_bytes, guard):
    root, source = Path(root), Path(source)
    match = logs.LOG_PATH.fullmatch(relative)
    if (not match or match[1] != match[2][:2] or not callable(guard)
            or not logs.valid_hash(expected_hash) or type(expected_bytes) is not int
            or not 0 <= expected_bytes <= 16 * 1024**2
            or root.resolve(strict=True) != root):
        raise ValueError('Exact bounded recovery binding required')
    guard()
    parts = Path(relative).parts
    with ExitStack() as stack:
        def opened(path, flags, mode=0o600, dir_fd=None):
            fd = os.open(path, flags | os.O_NOFOLLOW | os.O_CLOEXEC, mode, dir_fd=dir_fd)
            stack.callback(os.close, fd)
            return fd
        directory = opened(root, os.O_RDONLY | os.O_DIRECTORY)
        for part in parts[:-1]:
            directory = opened(part, os.O_RDONLY | os.O_DIRECTORY, dir_fd=directory)
        parent = root.joinpath(*parts[:-1])
        directory_id = (os.fstat(directory).st_dev, os.fstat(directory).st_ino)
        name = parts[-1]
        lock_name = str(Path(name).with_suffix('.mutation.lock'))
        lock = opened(lock_name, os.O_CREAT | os.O_RDWR | os.O_NONBLOCK, dir_fd=directory)
        lock_id = (os.fstat(lock).st_dev, os.fstat(lock).st_ino)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)

        def check():
            guard()
            named = parent.lstat()
            if not stat.S_ISDIR(named.st_mode) or (named.st_dev, named.st_ino) != directory_id:
                raise ValueError('Recovery parent changed')
            named = os.stat(lock_name, dir_fd=directory, follow_symlinks=False)
            held = os.fstat(lock)
            if (not stat.S_ISREG(named.st_mode) or (named.st_dev, named.st_ino) != lock_id
                    or held.st_nlink != 1 or held.st_uid != os.getuid() or held.st_mode & 0o022):
                raise ValueError('Recovery mutation lock changed or is unsafe')
        check()
        # Refuse even a matching existing target; uncertain publication needs review.
        try:
            os.stat(name, dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise FileExistsError('Capture already exists; preserve and reconcile it')
        source_fd = opened(source, os.O_RDONLY)
        before = os.fstat(source_fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_size != expected_bytes
                or before.st_uid != os.getuid() or before.st_mode & 0o022):
            raise ValueError('Original recovery source is unsafe or has changed')
        temp = '.' + name + '.restore-' + uuid.uuid4().hex
        target = opened(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, dir_fd=directory)
        temporary_id = (os.fstat(target).st_dev, os.fstat(target).st_ino)
        try:
            digest = hashlib.sha256()
            count = 0
            while chunk := os.read(source_fd, 256 * 1024):
                count += len(chunk)
                if count > expected_bytes:
                    raise ValueError('Original grew during recovery')
                digest.update(chunk)
                view = memoryview(chunk)
                while view:
                    n = os.write(target, view)
                    if n <= 0:
                        raise OSError('Short recovery write')
                    view = view[n:]
            if (count != expected_bytes or digest.hexdigest() != expected_hash
                    or logs.version(os.fstat(source_fd)) != logs.version(before)
                    or logs.version(source.lstat()) != logs.version(before)):
                raise ValueError('Original recovery bytes or identity differ')
            os.fchmod(target, stat.S_IMODE(before.st_mode))
            os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))
            os.fsync(target)
            check()
            # link is atomic and fails if any other owner supplied a destination.
            os.link(temp, name, src_dir_fd=directory, dst_dir_fd=directory,
                    follow_symlinks=False)
            os.fsync(directory)
            final = os.stat(name, dir_fd=directory, follow_symlinks=False)
            if (final.st_dev, final.st_ino) != temporary_id:
                raise ValueError('Published recovery inode differs')
            return dict(path=str(root / relative), sha256=expected_hash, bytes=count,
                        allocated_bytes=final.st_blocks * 512,
                        inode=[final.st_dev, final.st_ino], restored=True)
        finally:
            named = os.stat(temp, dir_fd=directory, follow_symlinks=False)
            if (named.st_dev, named.st_ino) == temporary_id:
                os.unlink(temp, dir_fd=directory)
                os.fsync(directory)
