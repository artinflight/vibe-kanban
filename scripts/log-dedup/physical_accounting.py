"""Measure allocated inodes, including directories, without following links."""
import os
from pathlib import Path
import stat


def measure(roots, *, guard=lambda: None):
    seen, counts = set(), dict(files=0, directories=0, symlinks=0, allocated_bytes=0)
    pending = [Path(p) for p in roots]
    while pending:
        path = pending.pop()
        value = path.lstat()
        identity = (value.st_dev, value.st_ino)
        if identity in seen:
            continue
        seen.add(identity)
        counts['allocated_bytes'] += value.st_blocks * 512
        if stat.S_ISDIR(value.st_mode):
            counts['directories'] += 1
            with os.scandir(path) as entries:
                pending.extend(Path(entry.path) for entry in entries)
        elif stat.S_ISREG(value.st_mode):
            counts['files'] += 1
        elif stat.S_ISLNK(value.st_mode):
            counts['symlinks'] += 1
        else:
            raise ValueError('Unexpected special file in measured artifact tree')
        if len(seen) % 1024 == 0:
            guard()
    guard()
    return dict(counts, unique_inodes=len(seen), directory_blocks_included=True,
                symlinks_followed=False, roots=[str(p) for p in roots])
