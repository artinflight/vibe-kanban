"""Lossless workspace payload inventory and create-only restoration primitives.

Bodies are streamed through the caller's existing normal recovery reader. This
module supplies no new transport, source retirement, arbitrary extraction or
recovery fallback. The caller holds exclusive workspace custody, validates the
ownership/dependency closure and records operation intent before publication.
"""
import base64
import ctypes
import errno
import hashlib
import os
from pathlib import Path, PurePosixPath
import stat

CHUNK = 1024 * 1024


def signature(st):
    return [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns,
            st.st_mode, st.st_uid, st.st_gid, st.st_nlink]


def directory_sync(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def parent_safe(path):
    if not path.is_absolute() or '..' in path.parts or path.parent.resolve(strict=True) != path.parent:
        raise ValueError('Canonical payload parent required')


def metadata(path, st):
    if st.st_uid != os.getuid():
        raise ValueError('Foreign-owned workspace payload is protected')
    return dict(uid=st.st_uid, gid=st.st_gid, mode=stat.S_IMODE(st.st_mode),
                mtime_ns=st.st_mtime_ns, atime_ns=st.st_atime_ns,
                xattrs={name: base64.b64encode(os.getxattr(path, name, follow_symlinks=False)).decode()
                        for name in sorted(os.listxattr(path, follow_symlinks=False))})


def read_file(path, before, guard):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        if signature(os.fstat(fd)) != before:
            raise ValueError('Workspace payload changed during open')
        with os.fdopen(fd, 'rb', closefd=False) as source:
            while True:
                guard()
                block = source.read(CHUNK)
                if not block:
                    break
                yield block
        if signature(os.fstat(fd)) != before or signature(path.lstat()) != before:
            raise ValueError('Workspace payload changed during read')
    finally:
        os.close(fd)


def snapshot(roots, guard=lambda: None):
    roots = [Path(p) for p in roots]
    if not roots or len(set(roots)) != len(roots):
        raise ValueError('Explicit unique workspace payload roots required')
    for root in roots:
        parent_safe(root)
        if root == Path('/') or root.is_symlink():
            raise ValueError('Payload root cannot be a filesystem root or alias')
        if any(other in root.parents for other in roots):
            raise ValueError('Overlapping workspace payload roots')
    entries = []
    for index, root in enumerate(roots):
        device = root.lstat().st_dev
        pending = [(root, '.')]
        directories = []
        while pending:
            guard()
            path, relative = pending.pop()
            st = path.lstat()
            if st.st_dev != device:
                raise ValueError('Nested mounts require separate ownership qualification')
            row = dict(root=index, relative=relative, version=signature(st), metadata=metadata(path, st))
            if stat.S_ISDIR(st.st_mode):
                row['kind'] = 'directory'
                names = sorted(os.listdir(path))
                directories.append((path, row['version'], names))
                for name in reversed(names):
                    pending.append((path / name, name if relative == '.' else relative + '/' + name))
            elif stat.S_ISREG(st.st_mode):
                if st.st_nlink != 1:
                    raise ValueError('Hard-linked payload requires explicit shared ownership')
                digest = hashlib.sha256()
                size = 0
                for block in read_file(path, row['version'], guard):
                    digest.update(block)
                    size += len(block)
                if size != st.st_size:
                    raise ValueError('Payload length changed')
                row.update(kind='file', bytes=size, sha256=digest.hexdigest())
            elif stat.S_ISLNK(st.st_mode):
                row.update(kind='symlink', target=os.readlink(path))
                if signature(path.lstat()) != row['version']:
                    raise ValueError('Payload symlink changed')
            else:
                raise ValueError('Special workspace payload is protected')
            entries.append(row)
        for path, before, names in directories:
            guard()
            if signature(path.lstat()) != before or sorted(os.listdir(path)) != names:
                raise ValueError('Payload directory changed during inventory')
    result = dict(format='vk-workspace-payloads-v1', roots=[str(p) for p in roots], entries=entries)
    validate(result)
    return result


def validate(manifest):
    if manifest.get('format') != 'vk-workspace-payloads-v1':
        raise ValueError('Unknown workspace payload format')
    roots = manifest['roots']
    if not roots or len(set(roots)) != len(roots):
        raise ValueError('Unique payload roots required')
    paths = [Path(p) for p in roots]
    if any(not p.is_absolute() or str(p) != raw or p == Path('/') or '..' in p.parts
           or any(other in p.parents for other in paths) for p, raw in zip(paths, roots)):
        raise ValueError('Canonical nonoverlapping payload roots required')
    seen = {}
    for row in manifest['entries']:
        root, relative = row['root'], row['relative']
        p = PurePosixPath(relative)
        if (type(root) is not int or not 0 <= root < len(roots) or p.is_absolute()
                or '..' in p.parts or str(p) != relative or '\0' in relative
                or row['kind'] not in ('file', 'directory', 'symlink')
                or (root, relative) in seen):
            raise ValueError('Invalid or duplicate workspace payload member')
        if relative != '.' and seen.get((root, str(p.parent))) != 'directory':
            raise ValueError('Payload parent must be an earlier real directory')
        if row['metadata']['uid'] != os.getuid():
            raise ValueError('Recovery ownership differs')
        if row['kind'] == 'file':
            digest = row['sha256']
            if (type(row['bytes']) is not int or row['bytes'] < 0 or not isinstance(digest, str)
                    or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest)):
                raise ValueError('Exact file digest and length required')
        if row['kind'] == 'symlink' and (not isinstance(row['target'], str) or '\0' in row['target']):
            raise ValueError('Invalid symlink metadata')
        seen[(root, relative)] = row['kind']
    if any((n, '.') not in seen for n in range(len(roots))):
        raise ValueError('Payload root is missing from manifest')


def comparable(manifest, *, versions=False):
    validate(manifest)
    rows = []
    for row in manifest['entries']:
        copy = {k: v for k, v in row.items() if versions or k != 'version'}
        copy['metadata'] = {k: v for k, v in copy['metadata'].items() if k != 'atime_ns'}
        rows.append(copy)
    return rows


def verify(manifest, roots=None, *, versions=False, guard=lambda: None):
    current = snapshot(roots or manifest['roots'], guard)
    if comparable(manifest, versions=versions) != comparable(current, versions=versions):
        raise ValueError('Workspace payload bytes, entries or Linux metadata differ')
    return current


def apply_metadata(path, row):
    value = row['metadata']
    os.chown(path, value['uid'], value['gid'], follow_symlinks=False)
    if row['kind'] != 'symlink':
        os.chmod(path, value['mode'], follow_symlinks=False)
    elif stat.S_IMODE(path.lstat().st_mode) != value['mode']:
        raise ValueError('Symlink permissions cannot be preserved')
    for name in os.listxattr(path, follow_symlinks=False):
        if name not in value['xattrs']:
            os.removexattr(path, name, follow_symlinks=False)
    for name, raw in value['xattrs'].items():
        os.setxattr(path, name, base64.b64decode(raw, validate=True), follow_symlinks=False)
    os.utime(path, ns=(value['atime_ns'], value['mtime_ns']), follow_symlinks=False)


def restore(manifest, destination, open_body, *, guard=lambda: None):
    """Create a fresh private verification tree from independent normal B bodies.

    open_body(row) is a context manager yielding a bounded-read binary stream.
    Corruption/interruption leaves the owned partial tree for reconciliation;
    it never replaces an active workspace or deletes source/backup evidence.
    """
    validate(manifest)
    destination = Path(destination)
    parent_safe(destination)
    destination.mkdir(mode=0o700)  # Existing/uncertain staging is never reused.
    directory_sync(destination.parent)
    directories = []
    staged_roots = [destination / str(n) for n in range(len(manifest['roots']))]
    for row in manifest['entries']:
        guard()
        path = staged_roots[row['root']] / row['relative']
        parent_safe(path)
        if row['kind'] == 'directory':
            path.mkdir(mode=0o700)
            directories.append((path, row))
        elif row['kind'] == 'symlink':
            os.symlink(row['target'], path)
            apply_metadata(path, row)
        else:
            size, digest = 0, hashlib.sha256()
            with path.open('xb') as output, open_body(row) as source:
                while True:
                    guard()
                    block = source.read(CHUNK)
                    if not block:
                        break
                    if not isinstance(block, bytes) or len(block) > CHUNK:
                        raise ValueError('Bounded recovery byte stream required')
                    size += len(block)
                    if size > row['bytes']:
                        raise ValueError('Recovered payload exceeds expected size')
                    digest.update(block)
                    output.write(block)
                if size != row['bytes'] or digest.hexdigest() != row['sha256']:
                    raise ValueError('Recovered workspace payload is corrupt or incomplete')
                output.flush()
                apply_metadata(path, row)
                os.fsync(output.fileno())
        directory_sync(path.parent)
    for path, row in reversed(directories):
        apply_metadata(path, row)
        directory_sync(path)
    verify(manifest, staged_roots, guard=guard)
    directory_sync(destination)
    return staged_roots


def rename_new(source, destination):
    """Atomic Linux no-replace move, including directories; never check+replace."""
    source, destination = Path(source), Path(destination)
    parent_safe(source)
    parent_safe(destination)
    libc = ctypes.CDLL(None, use_errno=True)
    call = libc.renameat2
    call.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    call.restype = ctypes.c_int
    if call(-100, os.fsencode(source), -100, os.fsencode(destination), 1) != 0:
        code = ctypes.get_errno()
        if code == errno.EEXIST:
            raise FileExistsError('Workspace destination already exists')
        raise OSError(code, os.strerror(code))
    directory_sync(source.parent)
    if source.parent != destination.parent:
        directory_sync(destination.parent)


def remove_verified(manifest, roots, *, guard=lambda: None):
    """Remove only the exact retired/verification members, resumable after unlink.

    Callers bind these roots to their durable operation journal, outside the
    active namespace. New entries, changed bodies or aliases stop retirement.
    Missing known members are allowed because a prior unlink may have committed
    before its caller recorded success. No recursive generic cleanup is used.
    """
    validate(manifest)
    roots = [Path(p) for p in roots]
    if len(roots) != len(manifest['roots']) or len(set(roots)) != len(roots):
        raise ValueError('Exact operation-owned retirement roots required')
    if set(map(str, roots)) & set(manifest['roots']):
        raise ValueError('Active payload paths cannot be purged')
    children = {}
    for row in manifest['entries']:
        p = PurePosixPath(row['relative'])
        if row['relative'] != '.':
            children.setdefault((row['root'], str(p.parent)), set()).add(p.name)
    for row in reversed(manifest['entries']):
        guard()
        path = roots[row['root']] / row['relative']
        # A removed ancestor is legitimate only when it is actually absent;
        # resolve(strict=True) still rejects any surviving parent aliases.
        if not os.path.lexists(path):
            continue
        parent_safe(path)
        st = path.lstat()
        meta = metadata(path, st)
        fields = ('uid', 'gid', 'mode', 'xattrs')
        if row['kind'] != 'directory':
            fields += ('mtime_ns',)
        if any(meta[k] != row['metadata'][k] for k in fields):
            raise ValueError('Retired payload metadata changed; preserve it')
        if row['kind'] == 'directory':
            if not stat.S_ISDIR(st.st_mode):
                raise ValueError('Retired directory was replaced')
            names = set(os.listdir(path))
            if names - children.get((row['root'], row['relative']), set()):
                raise ValueError('Unexpected retired payload entries are protected')
            if names:
                raise ValueError('Retired children remain; preserve them')
            os.rmdir(path)
        elif row['kind'] == 'file':
            if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
                raise ValueError('Retired file was replaced or shared')
            hashed, size = hashlib.sha256(), 0
            for block in read_file(path, signature(st), guard):
                hashed.update(block)
                size += len(block)
            if size != row['bytes'] or hashed.hexdigest() != row['sha256']:
                raise ValueError('Retired file differs; preserve it')
            guard()
            if signature(path.lstat()) != signature(st):
                raise ValueError('Retired file changed before removal')
            path.unlink()
        else:
            if not stat.S_ISLNK(st.st_mode) or os.readlink(path) != row['target']:
                raise ValueError('Retired symlink differs')
            path.unlink()
        directory_sync(path.parent)
