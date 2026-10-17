"""Bounded archive/read-boundary fixtures; no production capture or adoption.

Restore only into a newly created directory. The caller pins the complete
manifest independently; a same-account checksum is not a security boundary.
"""
import json
import os
from pathlib import Path
import re
import zlib

import vk_history_compaction_probe as codec


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def native_references(mode, required):
    if mode not in ('fixture', 'legacy', 'paginated'):
        raise ValueError('unknown native history format')
    if mode == 'paginated' and required.get('native_thread_history') != 'thread_history_1.sqlite':
        # Preserve the existing registered database scope. Injected-message
        # fixtures do not certify regeneration of populated real turn history.
        raise ValueError('paginated native history requires its consistent history database')


def seal(files, *, session_id, required, history_mode='fixture'):
    if not re.fullmatch('[a-zA-Z0-9_-]{1,128}', session_id):
        raise ValueError('invalid fixture session identity')
    if not required or any(key not in files for key in required.values()):
        raise ValueError('required session reference missing')
    native_references(history_mode, required)
    manifest, objects = codec.pack(files, 'chunk')
    manifest['session'] = {'id': session_id, 'required': required, 'history_mode': history_mode}
    raw = encoded(manifest)
    if len(raw) > codec.MAX_LAYOUT:
        raise ValueError('bounded manifest exceeded')
    return raw, objects


def recover(raw, objects, *, expected_sha256, session_id):
    if len(raw) > codec.MAX_LAYOUT or codec.digest(raw) != expected_sha256:
        raise ValueError('pinned manifest differs')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate manifest key')
            result[key] = value
        return result
    manifest = json.loads(raw, object_pairs_hook=unique)
    session = manifest['session']
    if session['id'] != session_id or not session['required']:
        raise ValueError('session identity differs')
    native_references(session['history_mode'], session['required'])
    files = codec.restore(manifest, objects)
    if any(key not in files for key in session['required'].values()):
        raise ValueError('required session reference missing')
    return files


def directory_fd(path):
    """Pin every absolute ancestor with no-follow descriptors."""
    path = Path(path).absolute()
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
        return fd
    except BaseException:
        os.close(fd)
        raise


def hydrate(raw, objects, destination, *, expected_sha256, session_id, reader):
    """Validate every byte/reference before creating the fresh fixture home.

    The synchronous reader runs only after full restoration, fsync and identity
    recheck. Failed partial fixtures remain for inspection; never clean recursively
    or merge/overwrite an existing home. This is not a production writer fence.
    """
    files = recover(raw, objects, expected_sha256=expected_sha256, session_id=session_id)
    destination = Path(destination).absolute()
    parent = directory_fd(destination.parent)
    root = None
    try:
        os.mkdir(destination.name, 0o700, dir_fd=parent)
        root = os.open(destination.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        identity = os.fstat(root)
        for key, data in sorted(files.items()):
            parts = key.split('/')
            codec.filename(key)
            current = os.dup(root)
            try:
                for part in parts[:-1]:
                    try:
                        os.mkdir(part, 0o700, dir_fd=current)
                        os.fsync(current)
                    except FileExistsError:
                        pass
                    nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
                    os.close(current)
                    current = nxt
                fd = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=current)
                try:
                    view = memoryview(data)
                    while view:
                        written = os.write(fd, view)
                        if written <= 0:
                            raise OSError('short restore write')
                        view = view[written:]
                    os.fsync(fd)
                finally:
                    os.close(fd)
                os.fsync(current)
            finally:
                os.close(current)
        os.fsync(root)
        os.fsync(parent)
        check = directory_fd(destination)
        try:
            actual = os.fstat(check)
            if (identity.st_dev, identity.st_ino) != (actual.st_dev, actual.st_ino):
                raise ValueError('restored home substituted')
        finally:
            os.close(check)
        # Fixture parents must remain caller-controlled throughout the reader.
        return reader(destination)
    finally:
        if root is not None:
            os.close(root)
        os.close(parent)


def compare(versions, *, session_id, required, history_mode='fixture'):
    """Per-generation closure, new transfer and cumulative retention separately."""
    if not 1 <= len(versions) <= 4:
        raise ValueError('bounded version count required')
    pool = {}
    rows = []
    manifests = []
    for files in versions:
        raw, objects = seal(files, session_id=session_id, required=required, history_mode=history_mode)
        assert recover(raw, objects, expected_sha256=codec.digest(raw), session_id=session_id) == files
        fresh = {key: value for key, value in objects.items() if key not in pool}
        pool.update(objects)
        manifests.append(raw)
        metadata_bytes = len(zlib.compress(raw, 6))
        rows.append({'source_bytes': sum(map(len, files.values())),
                     'complete_file_zlib6_bytes': sum(len(zlib.compress(data, 6)) for data in files.values()),
                     'independent_closure_zlib6_bytes': sum(map(len, objects.values())) + metadata_bytes,
                     'new_object_zlib6_bytes': sum(map(len, fresh.values())),
                     'manifest_zlib6_bytes': metadata_bytes,
                     'new_transfer_with_manifest_bytes': sum(map(len, fresh.values())) + metadata_bytes,
                     'blocks': len(objects), 'new_blocks': len(fresh),
                     'parent_manifest_required': False})
    return {'generations': rows,
            'repeated_complete_file_zlib6_bytes': sum(r['complete_file_zlib6_bytes'] for r in rows),
            'all_manifest_and_unique_object_zlib6_bytes': sum(map(len, pool.values())) + sum(len(zlib.compress(raw, 6)) for raw in manifests),
            'latest_independent_closure_zlib6_bytes': rows[-1]['independent_closure_zlib6_bytes'],
            'cumulative_figures_are_not_normal_one_current_retention': True}
