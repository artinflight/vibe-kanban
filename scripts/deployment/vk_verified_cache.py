"""Restore a verified immutable SQLite cache before an explicitly admitted reader.

This module never captures sources, fetches B data, retires a cache or creates
owner leases. Compression/retirement belongs to the cache owner. Historical
consumers can keep their byte-pinned source when called through run_consumer.
"""
from contextlib import contextmanager
from decimal import Decimal
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import tarfile
import uuid
import zlib


BLOCK = 65536


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def regular(path):
    info = Path(path).lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('Cache dependency must be an exact single-link regular file')
    return info


def file_digest(path, admit, remaining=0):
    before = regular(path)
    h = hashlib.sha256()
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NOATIME)
    with os.fdopen(fd, 'rb') as stream:
        if identity(os.fstat(stream.fileno())) != identity(before):
            raise ValueError('Cache dependency changed before read')
        while block := stream.read(BLOCK):
            require_admission(admit, remaining)
            h.update(block)
        if identity(os.fstat(stream.fileno())) != identity(before):
            raise ValueError('Cache dependency changed during read')
    if identity(Path(path).lstat()) != identity(before):
        raise ValueError('Cache dependency path replaced')
    return h.hexdigest(), before.st_size


def require_admission(admit, remaining):
    if admit(remaining) is not True:
        raise RuntimeError('Current cache scratch/resource admission refused')


def ssd_admission(*, future_bytes, health_check, floor_bytes, stop_bytes):
    """Caller supplies current once-charged future demand and genuine guards.

    No PSI number, released owner balance, old total quota or RAM substitution
    is introduced here. Remaining scratch decreases as the new file becomes
    resident. The existing archive/raw bytes are already reflected in df.
    """
    def admit(remaining):
        if not os.path.ismount('/mnt/vk-storage'):
            raise RuntimeError('Required SSD is not mounted')
        future = future_bytes()
        if type(future) is not int or future < 0 or remaining < 0:
            raise ValueError('Fresh once-charged future demand required')
        if health_check() is not True:
            raise RuntimeError('Actual owner health/access admission refused')
        usage = os.statvfs('/mnt/vk-storage')
        if usage.f_bavail * usage.f_frsize <= floor_bytes + future + remaining + stop_bytes:
            raise RuntimeError('Hydration scratch plus unchanged real floor does not fit')
        return True
    return admit


def metadata(path):
    info = Path(path).lstat()
    return dict(mode=stat.S_IMODE(info.st_mode), uid=info.st_uid, gid=info.st_gid,
                atime_ns=info.st_atime_ns, mtime_ns=info.st_mtime_ns,
                xattrs={name: base64.b64encode(os.getxattr(path, name)).decode()
                        for name in os.listxattr(path)})


def apply_metadata(path, expected):
    os.chown(path, expected['uid'], expected['gid'])
    for name in os.listxattr(path):
        if name not in expected['xattrs']:
            os.removexattr(path, name)
    for name, value in expected['xattrs'].items():
        os.setxattr(path, name, base64.b64decode(value, validate=True))
    os.chmod(path, expected['mode'])
    os.utime(path, ns=(expected['atime_ns'], expected['mtime_ns']))
    if metadata(path) != expected:
        raise ValueError('Hydrated Linux metadata differs')


def tar_zstd_body(source, dest, temporary, spec, admit, scratch):
    """Read only the exact ordinary member; never extract archive paths."""
    process = subprocess.Popen(['zstd', '-d', '-q', '-c'], stdin=source,
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    count, h, members = 0, hashlib.sha256(), 0
    try:
        with tarfile.open(fileobj=process.stdout, mode='r|') as archive:
            for member in archive:
                expected = spec['metadata']
                if (members or not member.isfile() or member.name != Path(spec['raw_path']).name
                        or member.size != spec['raw_bytes'] or member.issparse()
                        or (member.uid, member.gid, member.mode) !=
                        (expected['uid'], expected['gid'], expected['mode'])
                        or int(Decimal(member.pax_headers.get('mtime', str(member.mtime))) * 10**9)
                        != expected['mtime_ns']
                        or int(Decimal(member.pax_headers['atime']) * 10**9) != expected['atime_ns']
                        or expected['xattrs']):
                    raise ValueError('Exact single PAX ordinary-member metadata required')
                members += 1
                with archive.extractfile(member) as body:
                    while block := body.read(BLOCK):
                        require_admission(admit, max(0, scratch - temporary.stat().st_blocks * 512))
                        count += len(block)
                        if count > spec['raw_bytes']:
                            raise ValueError('PAX member exceeds exact bound')
                        h.update(block)
                        dest.write(block)
            # Tar's first zero header ends iteration. Reject hidden later members
            # or nonzero data after that terminator, rather than extracting it.
            while padding := archive.fileobj.read(BLOCK):
                require_admission(admit, max(0, scratch - temporary.stat().st_blocks * 512))
                if padding.strip(b'\0'):
                    raise ValueError('Unexpected data after single tar member')
        if process.wait(timeout=15) != 0 or members != 1:
            raise ValueError('Zstd stream or single-member PAX archive incomplete')
        return count, h.hexdigest()
    finally:
        process.stdout.close()
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=15)


def hydrate(spec, admit):
    """Called only with the owner's exclusive lease. Failed partials survive."""
    target, archive = Path(spec['raw_path']), Path(spec['archive_path'])
    archive_info = regular(archive)
    if archive_info.st_size != spec['archive_bytes']:
        raise ValueError('Archive size differs')
    remaining = max(((spec['raw_bytes'] + 4095) // 4096) * 4096,
                    spec['raw_allocated_bytes'])
    require_admission(admit, remaining)
    temporary = target.with_name(target.name + '.hydrate-' + uuid.uuid4().hex)
    encoded_hash, raw_hash = hashlib.sha256(), hashlib.sha256()
    tar_mode = spec['encoding'] == 'tar-zstd'
    archive_hash = file_digest(archive, admit, remaining)[0] if tar_mode else None
    if tar_mode and archive_hash != spec['archive_sha256']:
        raise ValueError('Archive checksum differs')
    decoder = None if tar_mode else zlib.decompressobj({'zlib': 15, 'gzip': 31}[spec['encoding']])
    count = 0
    fd = os.open(archive, os.O_RDONLY | os.O_NOFOLLOW | os.O_NOATIME)
    with os.fdopen(fd, 'rb') as source, temporary.open('xb') as dest:
        os.chmod(temporary, 0o600)
        if identity(os.fstat(source.fileno())) != identity(archive_info):
            raise ValueError('Archive changed before hydration')
        if tar_mode:
            count, raw_digest = tar_zstd_body(source, dest, temporary, spec, admit, remaining)
        while not tar_mode and (block := source.read(BLOCK)):
            encoded_hash.update(block)
            while block:
                value = decoder.decompress(block, BLOCK)
                block = decoder.unconsumed_tail
                count += len(value)
                if count > spec['raw_bytes'] or decoder.unused_data:
                    raise ValueError('Archive exceeds exact single-member bounds')
                require_admission(admit, max(0, remaining - temporary.stat().st_blocks * 512))
                raw_hash.update(value)
                dest.write(value)
        dest.flush()
        os.fsync(dest.fileno())
        if (identity(os.fstat(source.fileno())) != identity(archive_info)
                or identity(archive.lstat()) != identity(archive_info)
                or (not tar_mode and (not decoder.eof or decoder.unused_data or decoder.unconsumed_tail))
                or count != spec['raw_bytes']
                or (raw_digest if tar_mode else raw_hash.hexdigest()) != spec['raw_sha256']
                or (archive_hash if tar_mode else encoded_hash.hexdigest()) != spec['archive_sha256']):
            raise ValueError('Archive identity, checksum or complete decode differs')
    if file_digest(temporary, admit) != (spec['raw_sha256'], spec['raw_bytes']):
        raise ValueError('Independent hydrated-file readback differs')
    apply_metadata(temporary, spec['metadata'])
    # No replacement of a concurrent raw file; retain all originals/partials.
    os.link(temporary, target, follow_symlinks=False)
    temporary.unlink()  # Only the duplicate link to this successfully read-back file.
    fd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


@contextmanager
def held_cache(spec, expected_spec_sha256, *, admit):
    if hashlib.sha256(canonical(spec)).hexdigest() != expected_spec_sha256:
        raise ValueError('Authenticated cache manifest differs')
    target, archive, lease = (Path(spec[k]) for k in ['raw_path', 'archive_path', 'lease_path'])
    if (spec.get('format') != 'vk-verified-sqlite-cache-v1'
            or spec.get('encoding') not in ('zlib', 'gzip', 'tar-zstd')
            or len({target, archive, lease}) != 3
            or any(not p.is_absolute() or p.parent.resolve() != p.parent
                   for p in [target, archive, lease])):
        raise ValueError('Invalid exact cache dependency paths/format')
    require_admission(admit, 0)
    regular(lease)
    fd = os.open(lease, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        lease_id = identity(os.fstat(fd))
        if list(lease_id[:2]) != spec['lease_identity']:
            raise ValueError('Authenticated owner cache lease differs')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Even with raw resident, invalid/missing archive is not silently ignored.
        resident = target.exists() or target.is_symlink()
        if resident:
            if file_digest(archive, admit) != (spec['archive_sha256'], spec['archive_bytes']):
                raise ValueError('Archive checksum differs')
        else:
            hydrate(spec, admit)
        actual_meta = metadata(target)
        # Hydration restores atime exactly. Subsequent SQLite readers can advance
        # it normally; atime alone is not evidence of changed cache content.
        if resident:
            actual_meta['atime_ns'] = spec['metadata']['atime_ns']
        if (file_digest(target, admit) != (spec['raw_sha256'], spec['raw_bytes'])
                or actual_meta != spec['metadata']):
            raise ValueError('Raw cache bytes/Linux metadata differ')
        fcntl.flock(fd, fcntl.LOCK_SH)
        if identity(lease.lstat()) != lease_id:
            raise ValueError('Owner cache lease replaced')
        yield target
        require_admission(admit, 0)
        if identity(lease.lstat()) != lease_id:
            raise ValueError('Owner cache lease replaced')
    finally:
        os.close(fd)


@contextmanager
def open_immutable(spec, expected_spec_sha256, *, admit):
    with held_cache(spec, expected_spec_sha256, admit=admit) as target:
        connection = sqlite3.connect(target.as_uri() + '?mode=ro&immutable=1', uri=True)
        try:
            yield connection
        finally:
            connection.close()


def run_consumer(script, expected_script_sha256, spec, expected_spec_sha256, *, admit, argv=()):
    """Normal entrypoint for historical byte-pinned helpers; no helper edits.

    Caller still admits the actual consumer workload and supplies its original
    resource/source guards. This function does not launch that workload itself
    unless explicitly called; it has no command-line auto-run or retries.
    """
    script = Path(script)
    source = script.read_bytes()
    if (spec.get('consumers', {}).get(str(script)) != expected_script_sha256
            or hashlib.sha256(source).hexdigest() != expected_script_sha256):
        raise ValueError('Prepared consumer source differs')
    with held_cache(spec, expected_spec_sha256, admit=admit):
        previous = sys.argv
        try:
            sys.argv = [str(script), *argv]
            exec(compile(source, str(script), 'exec'),
                 {'__name__': '__main__', '__file__': str(script)})
        finally:
            sys.argv = previous
