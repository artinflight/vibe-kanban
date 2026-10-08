#!/usr/bin/env python3
"""Emit a Unix runtime identity receipt from explicitly selected, reviewed paths.

This tool reads metadata and the SQLite header only. It never creates a database,
creates a workspace, modifies the selected paths, or enrolls a running service.
The caller must establish which dataset/root is authoritative before using it.
"""
import argparse
import os
from pathlib import Path
import stat


def receipt(database, workspace_root):
    database = Path(database).resolve(strict=True)
    workspace_root = Path(workspace_root).resolve(strict=True)
    db = database.stat(); root = workspace_root.stat()
    if os.name != 'posix' or not stat.S_ISREG(db.st_mode) or db.st_size < 512 or not stat.S_ISDIR(root.st_mode):
        raise ValueError('existing SQLite file and Unix workspace directory required')
    with database.open('rb') as source:
        if source.read(16) != b'SQLite format 3\0':
            raise ValueError('not a SQLite database')
    if any('\n' in str(path) or '\r' in str(path) for path in (database, workspace_root)):
        raise ValueError('identity paths cannot contain line breaks')
    return (f'vk-runtime-identity-v1\ndatabase={database}\ndatabase_id={db.st_dev}:{db.st_ino}\n'
            f'workspace_root={workspace_root}\nworkspace_root_id={root.st_dev}:{root.st_ino}\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True, type=Path)
    parser.add_argument('--workspace-root', required=True, type=Path)
    args = parser.parse_args()
    print(receipt(args.database, args.workspace_root), end='')


if __name__ == '__main__':
    main()
