#!/usr/bin/env python3
"""Emit a Unix runtime identity receipt from explicitly selected, reviewed paths.

This tool reads metadata, the SQLite header and the intrinsic dataset token.
It never creates a database/workspace, writes dataset contents or enrolls a service.
The caller must establish which dataset/root is authoritative before using it.
"""
import argparse
import os
from pathlib import Path
import stat
import sqlite3


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
    with sqlite3.connect(database.as_uri() + '?mode=ro') as connection:
        ids = connection.execute('SELECT dataset_id FROM vk_runtime_identity WHERE singleton = 1').fetchall()
    if len(ids) != 1 or not isinstance(ids[0][0], str) or len(ids[0][0]) != 32 or any(c not in '0123456789abcdef' for c in ids[0][0]):
        raise ValueError('dataset identity is missing or invalid; enrollment is a separate reviewed action')
    dataset_id = ids[0][0]
    return (f'vk-runtime-identity-v1\ndatabase={database}\ndatabase_id={db.st_dev}:{db.st_ino}\n'
            f'workspace_root={workspace_root}\nworkspace_root_id={root.st_dev}:{root.st_ino}\ndataset_id={dataset_id}\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True, type=Path)
    parser.add_argument('--workspace-root', required=True, type=Path)
    args = parser.parse_args()
    print(receipt(args.database, args.workspace_root), end='')


if __name__ == '__main__':
    main()
