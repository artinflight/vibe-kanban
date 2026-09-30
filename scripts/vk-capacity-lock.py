#!/usr/bin/env python3
"""Read-only capacity ownership barrier. Never release another process's lock."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import stat


def check_available(root):
    root = Path(root)
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise ValueError('Expected an existing absolute real controller directory')
    path = root / 'controller.lock'
    # No O_CREAT: readiness must not manufacture a new unlocked inode.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError('Controller lock must be a regular file')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('Capacity controller is still owned. Pausing retains this lock; '
                             'do not start the candidate or replace the lock file.') from error
        try:
            after = path.lstat()
            if (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino):
                raise ValueError('Controller lock changed during inspection')
            return {'available': True, 'path': str(path), 'device': before.st_dev,
                    'inode': before.st_ino, 'state_modified': False,
                    'scope': 'Momentary lock availability, not authority to stop services or proof of full cutover readiness'}
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(check_available(args.state_dir)))
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
