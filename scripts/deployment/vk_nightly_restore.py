"""Independent, unprivileged recovery into a new private Linux directory.

The trusted caller holds the generation lease and authenticates B/manifest.
No archive commands, live paths, existing destination, privilege escalation,
source links, cleanup, deployment or journal adoption are accepted here.
"""
import base64
import hashlib
import os
from pathlib import Path
import sqlite3
import stat

from vk_nightly_archive_index import validate_backup_entries
from vk_nightly_generation import object_blocks, regular


def restore_generation(folder, manifest, destination, *, checkpoint=lambda value: None,
                       write_limiter=lambda size: None):
    entries = manifest['entries']
    validate_backup_entries(entries)
    folder, destination = Path(folder), Path(destination)
    if destination.parent.resolve() != destination.parent or destination.parent.is_symlink():
        raise ValueError('restore parent must be an existing canonical private directory')
    parent = destination.parent.stat()
    if parent.st_uid != os.getuid() or stat.S_IMODE(parent.st_mode) & 0o077:
        raise ValueError('restore parent must be private and owned by the executing user')
    destination.mkdir(mode=0o700)  # Never reuse even an empty destination.
    root = destination.stat()
    objects = folder / 'objects'
    counts = {kind: 0 for kind in ('file', 'directory', 'symlink', 'hardlink')}
    logical = 0

    def report(phase, index):
        now = destination.lstat()
        if (now.st_dev, now.st_ino) != (root.st_dev, root.st_ino) or not stat.S_ISDIR(now.st_mode):
            raise ValueError('private restore root changed')
        checkpoint({'phase': phase, 'completed_entries': index, 'entries': len(entries),
                    'regular_bytes_written': logical})

    # All parents precede payloads. validate_backup_entries rejects traversal
    # through any archived link; unselected ancestor metadata stays unspecified.
    for key in entries:
        (destination / key).parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    for key, row in entries.items():
        if row['kind'] == 'directory':
            (destination / key).mkdir(mode=0o700, exist_ok=True)
    for index, (key, row) in enumerate(entries.items()):
        path = destination / key
        counts[row['kind']] += 1
        if row['kind'] == 'file':
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as sink:
                for block in object_blocks(objects / row['sha256'], row['sha256'], row['bytes'],
                                           manifest.get('object_encoding')):
                    write_limiter(len(block))
                    sink.write(block)
                sink.flush()
                os.fsync(sink.fileno())
                info = os.fstat(sink.fileno())
            # A destination must be an independently allocated file, never an
            # object-store hardlink/reflink supplied as a recovery shortcut.
            if info.st_nlink != 1 or info.st_dev != root.st_dev:
                raise ValueError('restore file is not independent on the destination filesystem')
            original = (objects / row['sha256']).stat()
            if (original.st_dev, original.st_ino) == (info.st_dev, info.st_ino):
                raise ValueError('restore aliases an object')
            logical += row['bytes']
        if index % 256 == 0:
            report('materialize', index)
    for key, row in entries.items():
        path = destination / key
        if row['kind'] == 'hardlink':
            os.link(destination / row['target'], path, follow_symlinks=False)
        elif row['kind'] == 'symlink':
            os.symlink(row['target'], path)

    # Reopen independent output and read every byte. No source/object hashes
    # are substituted for destination verification.
    databases = {v['key']: v for v in (manifest.get('capture_context') or {}).get(
        'restart_capture', {}).get('databases', {}).values()}
    sqlite_checked = 0
    for index, (key, row) in enumerate(entries.items()):
        path = destination / key
        if row['kind'] in ('file', 'hardlink'):
            with regular(path) as source:
                before = os.fstat(source.fileno())
                checksum = hashlib.file_digest(source, 'sha256').hexdigest()
                after = os.fstat(source.fileno())
            if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                    after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
                raise ValueError('restored file changed during independent readback')
            if after.st_size != row['bytes'] or checksum != row['sha256']:
                raise ValueError('independent restored content differs: ' + key)
            if row['kind'] == 'hardlink':
                other = (destination / row['target']).lstat()
                if (after.st_dev, after.st_ino) != (other.st_dev, other.st_ino):
                    raise ValueError('restored hardlink relationship differs')
            if key in databases:
                expected = databases[key]
                if expected['sha256'] != checksum or expected['bytes'] != after.st_size:
                    raise ValueError('restart database binding differs')
                with sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True) as db:
                    if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                        raise ValueError('independent restored SQLite integrity failed: ' + key)
                sqlite_checked += 1
        elif row['kind'] == 'symlink' and os.readlink(path) != row['target']:
            raise ValueError('restored symlink literal differs')
        if index % 256 == 0:
            report('independent_readback', index)
    if sqlite_checked != len(databases):
        raise ValueError('not all bound databases were independently restored')

    # Apply only recorded metadata, children before directories. Inaccessible
    # numeric ownership/xattrs fail honestly; the helper never invokes sudo.
    restored_regular_allocation = selected_directory_allocation = 0
    for key in sorted(entries, key=lambda k: k.count('/'), reverse=True):
        row = entries[key]
        path = destination / key
        info = path.lstat()
        if (info.st_uid, info.st_gid) != (row['uid'], row['gid']):
            try:
                os.chown(path, row['uid'], row['gid'], follow_symlinks=False)
            except PermissionError as error:
                raise PermissionError('restore ownership requires uid=%s gid=%s for %s' % (
                    row['uid'], row['gid'], key)) from error
        for field, value in row['xattrs'].items():
            decoded = base64.b64decode(value, validate=True)
            if field not in os.listxattr(path, follow_symlinks=False) or os.getxattr(
                    path, field, follow_symlinks=False) != decoded:
                os.setxattr(path, field, decoded, follow_symlinks=False)
        if row['kind'] != 'symlink':
            os.chmod(path, row['mode'], follow_symlinks=False)
        os.utime(path, ns=(row['mtime_ns'], row['mtime_ns']), follow_symlinks=False)
        info = path.lstat()
        if (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode), info.st_mtime_ns) != (
                row['uid'], row['gid'], row['mode'], row['mtime_ns']):
            raise ValueError('restored numeric metadata differs: ' + key)
        if set(os.listxattr(path, follow_symlinks=False)) != set(row['xattrs']):
            raise ValueError('restored xattr names differ: ' + key)
        for field, value in row['xattrs'].items():
            if os.getxattr(path, field, follow_symlinks=False) != base64.b64decode(value, validate=True):
                raise ValueError('restored xattr differs: ' + key)
        if row['kind'] == 'file':
            restored_regular_allocation += info.st_blocks * 512
        elif row['kind'] == 'directory':
            selected_directory_allocation += info.st_blocks * 512
    report('complete', len(entries))
    return {'passed': True, 'independent_restore_verified': True, 'entries': len(entries),
            'kinds': counts, 'regular_bytes_written': logical, 'sqlite_integrity_checks': sqlite_checked,
            'restored_regular_allocated_bytes': restored_regular_allocation,
            'selected_directory_allocated_bytes': selected_directory_allocation,
            'filesystem_inode_and_unselected_scaffold_overhead_included': False,
            'recorded_metadata_verified': True, 'unselected_parent_metadata_specified': False,
            'deployment_or_journal_adoption': False}
