#!/usr/bin/env python3
"""Add immutable objects before maintenance; never replace logs or sidecars.

These unreferenced additions do not establish backup, reader or writer custody.
The unchanged guarded controller must independently admit every manifest switch.
No object cleanup, service control, scheduling or source-log write occurs here.
"""
import argparse
import json
import os
from pathlib import Path
import resource
import shutil
import stat
import tempfile
import time

import log_dedup as logs
from reclaim import object_bytes, sync_directory, terminal_process, verify_sidecars


RESERVE = 3 * 1024**3


def stage(plan, archive, database, guard, *, reserve_bytes=RESERVE):
    if (not callable(guard) or type(reserve_bytes) is not int or reserve_bytes < 0
            or not 1 <= len(plan['files']) <= 64
            or len({row['path'] for row in plan['files']}) != len(plan['files'])
            or sum(row['raw_bytes'] for row in plan['files']) > 2 * 1024**3):
        raise logs.ArchiveError('Bounded unique batch and resource guard required')
    root = Path(plan['source_root'])
    archive = Path(archive).resolve(strict=True)
    if (not root.is_absolute() or root.resolve(strict=True) != root
            or archive == root or root in archive.parents or archive in root.parents):
        raise logs.ArchiveError('Literal source root and disjoint archive required')
    guard()
    receipt = json.loads((archive / 'receipt.json').read_bytes())
    packed = {row['path']: row for row in receipt['files']}
    if (receipt['version'] != plan['version'] or receipt['source_root'] != str(root)
            or any(packed.get(row['path']) != row for row in plan['files'])):
        raise logs.ArchiveError('Packed receipt differs from exact selected sources')

    def check():
        guard()
        for row in plan['files']:
            source = logs.safe_path(root, row['path'])
            info = logs.regular(source)
            if (logs.version(info) != row['identity'] or info.st_uid != os.getuid()
                    or info.st_nlink != 1):
                raise logs.ArchiveError('Selected original identity/ownership changed')
            terminal_process(database, row)
            verify_sidecars(root, row)
            for sidecar in row['sidecars']:
                if logs.version(logs.regular(source.with_suffix('.' + sidecar['extension']))) != sidecar['identity']:
                    raise logs.ArchiveError('Selected sidecar identity changed')

    def capacity(additional=0):
        if shutil.disk_usage(root).free < reserve_bytes + sum(row['raw_bytes'] for row in plan['files']) + additional:
            raise logs.ArchiveError('Original reconstruction/publication reserve unavailable')

    class VerifySink:
        def write(self, block):
            guard()
            return len(block)

    check()
    capacity()
    # Authenticate selected packed log bodies before any live addition.
    for row in plan['files']:
        manifest = logs.reconstruct(logs.safe_path(archive, row['path']), VerifySink())
        if manifest['sha256'] != row['sha256'] or manifest['raw_bytes'] != row['raw_bytes']:
            raise logs.ArchiveError('Packed original content differs')
    check()
    created = reused = references = 0
    seen = set()
    stores = set()
    for row in plan['files']:
        manifest = logs.load_manifest(archive / row['path'])
        store = (root / row['path']).parent / '.log-objects'
        if store.is_symlink():
            raise logs.ArchiveError('Refused aliased object store')
        capacity(os.statvfs(root).f_frsize or 4096)
        store.mkdir(mode=0o700, exist_ok=True)
        info = store.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
            raise logs.ArchiveError('Owned non-writable object directory required')
        stores.add(store)
        for chunk in manifest['chunks']:
            references += 1
            if references % 64 == 0:
                check()
                capacity()
            target = store / (chunk['sha256'] + '.gz')
            if target in seen:
                continue
            seen.add(target)
            if target.exists() or target.is_symlink():
                object_bytes(target, chunk)
                reused += 1
                continue
            source = (archive / row['path']).parent / '.log-objects' / target.name
            before = logs.regular(source)
            object_bytes(source, chunk)
            fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, 'rb') as packed_input:
                if logs.version(os.fstat(packed_input.fileno())) != logs.version(before):
                    raise logs.ArchiveError('Packed object changed before copying')
                raw = packed_input.read(logs.MAX_CHUNK + 1025)
                if (len(raw) > logs.MAX_CHUNK + 1024
                        or logs.version(os.fstat(packed_input.fileno())) != logs.version(before)
                        or logs.version(logs.regular(source)) != logs.version(before)):
                    raise logs.ArchiveError('Packed object changed while copying')
            fragment = os.statvfs(root).f_frsize or 4096
            capacity(((len(raw) + fragment - 1) // fragment + 1) * fragment)
            fd, temporary = tempfile.mkstemp(prefix='.new-', dir=store)
            temporary = Path(temporary)
            owned = os.fstat(fd)
            try:
                with os.fdopen(fd, 'wb') as output:
                    output.write(raw)
                    output.flush()
                    os.fsync(output.fileno())
                named = logs.regular(temporary)
                if (named.st_dev, named.st_ino) != (owned.st_dev, owned.st_ino):
                    raise logs.ArchiveError('Foreign object staging inode; preserve it')
                try:
                    os.link(temporary, target, follow_symlinks=False)
                    created += 1
                except FileExistsError:
                    reused += 1
                object_bytes(target, chunk)
            finally:
                if temporary.exists() or temporary.is_symlink():
                    named = temporary.lstat()
                    if (named.st_dev, named.st_ino) == (owned.st_dev, owned.st_ino):
                        temporary.unlink()
    for store in stores:
        sync_directory(store)
        sync_directory(store.parent)
    check()
    capacity()
    return {'objects_created': created, 'objects_reused': reused,
            'raw_files_unchanged': True, 'manifest_replacements': 0,
            'production_reclaimed_bytes': 0,
            'note': 'Unreferenced objects retained. Full B/reader/WriterFence admission remains mandatory.'}


def host_observation():
    values = {line.split(':')[0]: int(line.split()[1]) * 1024
              for line in Path('/proc/meminfo').read_text().splitlines()}
    full = next(line for line in Path('/proc/pressure/memory').read_text().splitlines()
                if line.startswith('full '))
    avg = float(dict(token.split('=') for token in full.split()[1:])['avg10'])
    return {'MemAvailable_bytes': values['MemAvailable'],
            'SwapFree_bytes': values['SwapFree'], 'full_PSI_avg10': avg}


def wait_for_resources(deadline):
    """Pause additive I/O during shared pressure; never admit below the floor."""
    waiting = False
    while True:
        if ((deadline is not None and time.monotonic() > deadline)
                or not os.path.ismount('/mnt/vk-storage')):
            raise logs.ArchiveError('Preparation budget or SSD mount unavailable')
        observed = host_observation()
        if (observed['MemAvailable_bytes'] >= RESERVE
                and observed['SwapFree_bytes'] >= 1024**3
                and observed['full_PSI_avg10'] <= .10):
            if waiting:
                print(json.dumps(dict(observed, phase='resource-admission-resumed')), flush=True)
            return
        if not waiting:
            print(json.dumps(dict(observed, phase='waiting-for-resource-admission',
                                  source_log_writes=0)), flush=True)
            waiting = True
        time.sleep(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('plan', 'archive', 'database'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--seconds', type=int, help='Optional operator-specified elapsed-time budget')
    args = parser.parse_args()
    if args.seconds is not None and args.seconds < 1:
        raise logs.ArchiveError('Explicit preparation budget must be positive')
    resource.setrlimit(resource.RLIMIT_AS, (768 * 1024**2, 768 * 1024**2))
    os.nice(15)
    deadline = None if args.seconds is None else time.monotonic() + args.seconds

    def guard():
        wait_for_resources(deadline)
    print(json.dumps(stage(json.loads(args.plan.read_bytes()), args.archive, args.database, guard), indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        message = str(error) if isinstance(error, logs.ArchiveError) else type(error).__name__
        raise SystemExit('Create-only object preparation failed: ' + message)
