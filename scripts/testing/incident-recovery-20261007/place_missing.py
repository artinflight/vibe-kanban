"""Exact no-replace recovery, only authenticated missing worktree/admin paths."""
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import shutil
import uuid

ROOT = Path(__file__).resolve().parent
PRIVATE = Path('/mnt/vk-storage/vk-runtime-backup-20261007/backups/incident-private-recovery-2316')
LIBC = ctypes.CDLL(None, use_errno=True)
LIBC.renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def save(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, indent=2)


def allowed(path):
    return (path.startswith('mnt/vk-storage/worktrees/') or
            path.startswith('home/mcp/') and '/.git/worktrees/' in path)


def parent_fd(target):
    assert target.is_absolute() and '..' not in target.parts
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in target.parts[1:-1]:
            try:
                next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            except FileNotFoundError:
                os.mkdir(component, 0o700, dir_fd=fd)
                next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd
    except BaseException:
        os.close(fd)
        raise


def move_no_replace(source, target):
    fd = parent_fd(target)
    try:
        rc = LIBC.renameat2(-100, os.fsencode(source), fd, os.fsencode(target.name), 1)
        if rc:
            code = ctypes.get_errno()
            if code == errno.EEXIST:
                return False
            if code == errno.EXDEV:
                return copy_admin_no_replace(source, target, fd)
            raise OSError(code, os.strerror(code), str(target))
        os.fsync(fd)
        return True
    finally:
        os.close(fd)


def copy_admin_no_replace(source, target, fd):
    # Only small original Git registration metadata may cross to its original
    # filesystem. No worktree payload or archive can use this path.
    assert '/.git/worktrees/' in str(target) and str(target).startswith('/home/mcp/')
    is_directory = source.is_dir() and not source.is_symlink()
    contents = ([p for p in source.rglob('*') if p.is_file() and not p.is_symlink()]
                if is_directory else [] if source.is_symlink() else [source])
    assert sum(p.stat().st_size for p in contents) < 64 * 1024**2
    name = '.vk-recovery-' + uuid.uuid4().hex
    staging = Path('/proc/self/fd') / str(fd) / name
    if is_directory:
        shutil.copytree(source, staging, symlinks=True)
    elif source.is_symlink():
        os.symlink(os.readlink(source), staging)
    else:
        shutil.copy2(source, staging, follow_symlinks=False)
    for path in contents:
        copied = staging / path.relative_to(source) if is_directory else staging
        assert sha(path) == sha(copied)
        with copied.open('rb') as f:
            os.fsync(f.fileno())
    for path in source.rglob('*') if is_directory else [source]:
        if path.is_symlink():
            copied = staging / path.relative_to(source) if is_directory else staging
            assert os.readlink(path) == os.readlink(copied)
    rc = LIBC.renameat2(fd, os.fsencode(name), fd, os.fsencode(target.name), 1)
    if rc:
        code = ctypes.get_errno()
        if code == errno.EEXIST:
            return False
        raise OSError(code, os.strerror(code), str(target))
    os.fsync(fd)
    return True


def main():
    assert sys.argv[1:] in (['plan'], ['apply'])
    assert os.path.ismount('/mnt/vk-storage') and not Path('/proc/2670802').exists()
    os.umask(0o077)
    proof = json.loads((ROOT / 'private-recovery-result.json').read_text())
    assert proof['passed'] and not proof['production_placement']
    files = PRIVATE / 'files'
    expected = proof['files']
    links = json.loads((PRIVATE / 'link-metadata.json').read_text())
    for name, row in expected.items():
        assert allowed(name) and sha(files / name) == row['sha256']
    # Links are materialized only after authenticated file extraction, never
    # used as extraction or traversal routes. Absolute targets are unchanged.
    for name, row in links.items():
        assert allowed(name) and '..' not in Path(name).parts
        target = files / name
        if row['hardlink']:
            assert target.is_file() and not target.is_symlink()
        elif os.path.lexists(target):
            assert target.is_symlink() and os.readlink(target) == row['target']
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(row['target'], target)
    roots = sorted({p.split('/')[3] for p in expected if p.startswith('mnt/vk-storage/worktrees/')})
    admin = set()
    for name in expected:
        if '/.git/worktrees/' in name and name.startswith('home/mcp/'):
            prefix, tail = name.split('/.git/worktrees/', 1)
            admin.add(prefix + '/.git/worktrees/' + tail.split('/')[0])
    operations, conflicts = [], []

    def plan(source, target):
        relative = str(source.relative_to(files))
        assert allowed(relative)
        if not os.path.lexists(target):
            operations.append({'source': str(source), 'target': str(target),
                               'directory': source.is_dir() and not source.is_symlink()})
        elif source.is_dir() and not source.is_symlink() and target.is_dir() and not target.is_symlink():
            for child in sorted(source.iterdir()):
                plan(child, target / child.name)
        else:
            conflicts.append({'source': str(source), 'target': str(target), 'action': 'retain-current-without-overwrite'})

    for relative in ['mnt/vk-storage/worktrees/' + name for name in roots] + sorted(admin):
        source = files / relative
        if source.exists():
            plan(source, Path('/') / relative)
    binding = {'operations': operations, 'existing_paths_retained': conflicts,
               'source_receipt_sha256': sha(ROOT / 'private-recovery-result.json'),
               'never_replace': True, 'database_restore': False}
    if sys.argv[1] == 'plan':
        save(ROOT / 'placement-plan.json', binding)
        print(json.dumps({'operations': len(operations), 'existing_paths_retained': len(conflicts)}))
        return
    assert json.loads((ROOT / 'placement-plan.json').read_text()) == binding
    outcomes = []
    try:
        for row in operations:
            source, target = Path(row['source']), Path(row['target'])
            try:
                placed = move_no_replace(source, target)
                outcomes.append({**row, 'placed': placed, 'collision_preserved': not placed})
            except OSError as error:
                outcomes.append({**row, 'placed': False, 'error': str(error)})
                raise
    finally:
        save(ROOT / 'placement-result.json', {'outcomes': outcomes, 'never_replaced': True,
             'completed': len(outcomes) == len(operations) and all(r['placed'] for r in outcomes)})
    print(json.dumps({'placed_operations': len(outcomes), 'no_existing_file_replaced': True}))


if __name__ == '__main__':
    main()
