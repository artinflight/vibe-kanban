"""Bounded availability check before ONE existing recovery-context acquisition.

No context/capture retry, owner interruption, lock deletion or new lock inode.
The real recovery constructor must still acquire and retain its own same lease.
A contender racing this check is allowed to win; construction then fails safely.
"""
import fcntl
import os
from pathlib import Path
import stat
import time


def wait_available(path, *, guard, maximum_seconds=300, observe=lambda value:None,
                   clock=time.monotonic, sleep=time.sleep):
    path=Path(path)
    if (not path.is_absolute() or path.resolve(strict=True)!=path
            or type(maximum_seconds)is not int or not 0<=maximum_seconds<=300):
        raise ValueError('Existing canonical lease and bounded wait required')
    before=path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_uid!=os.getuid() or before.st_nlink!=1:
        raise ValueError('Existing unique owned lease required')
    identity=(before.st_dev,before.st_ino)
    began=clock();observations=0
    while True:
        guard()
        named=path.lstat()
        if (named.st_dev,named.st_ino)!=identity or not stat.S_ISREG(named.st_mode):
            raise ValueError('Lease inode changed during availability wait')
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
        try:
            opened=os.fstat(fd)
            if(opened.st_dev,opened.st_ino)!=identity:
                raise ValueError('Lease inode changed during open')
            try:
                fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:
                observations+=1
                observe(dict(state='existing_owner_busy',elapsed_seconds=clock()-began,
                             observations=observations,identity=list(identity)))
            else:
                return dict(state='available_at_preflight',elapsed_seconds=clock()-began,
                            observations=observations,identity=list(identity),recovery_context_opened=False)
        finally:
            os.close(fd)
        elapsed=clock()-began
        if elapsed>=maximum_seconds:
            raise BlockingIOError('Existing backup owner did not release within the bounded wait')
        sleep(min(5,maximum_seconds-elapsed))
