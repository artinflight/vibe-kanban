"""Offline packed-object qualification. Never modifies or retires live sources."""
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import zlib

import log_dedup as logs

MAGIC = b'VKLOGCAS2\n'
PACK_MAGIC = b'VKLOGPACK1\n'
MAX_PACK = 64 * 1024**2
MAX_PACKS = 1024
# Fits the existing 24 MiB recovery carrier without new transport or fragmentation.
DEFAULT_PACK = 16 * 1024**2


def encode(manifest):
    raw = json.dumps(manifest, separators=(',', ':')).encode() + b'\n'
    if len(raw) > logs.MAX_MANIFEST:
        raise logs.ArchiveError('Packed manifest exceeds reader bound')
    return MAGIC + raw


def load_manifest(path):
    logs.regular(path)
    with Path(path).open('rb') as stream:
        if stream.read(len(MAGIC)) != MAGIC:
            raise logs.ArchiveError('Not a packed archive')
        raw = stream.read(logs.MAX_MANIFEST + 1)
    if len(raw) > logs.MAX_MANIFEST:
        raise logs.ArchiveError('Packed manifest exceeds reader bound')
    return validate_manifest(json.loads(raw))


def validate_manifest(m):
    if (not isinstance(m, dict) or set(m) != {'version', 'raw_bytes', 'sha256', 'packs', 'chunks'} or type(m['version']) is not int or m['version'] != 2
            or type(m['raw_bytes']) is not int or m['raw_bytes'] < 0 or not logs.valid_hash(m['sha256'])
            or not isinstance(m['packs'], list) or len(m['packs']) > MAX_PACKS
            or any(not logs.valid_hash(p) for p in m['packs']) or len(set(m['packs'])) != len(m['packs'])
            or not isinstance(m['chunks'], list) or len(m['chunks']) > logs.MAX_CHUNKS):
        raise logs.ArchiveError('Invalid packed manifest')
    total = 0
    for c in m['chunks']:
        if (not isinstance(c, dict) or set(c) != {'sha256', 'bytes', 'pack', 'offset', 'encoded_bytes'}
                or not logs.valid_hash(c['sha256'])
                or any(type(c[k]) is not int for k in ('bytes', 'pack', 'offset', 'encoded_bytes'))
                or not 0 < c['bytes'] <= logs.MAX_CHUNK or not 0 <= c['pack'] < len(m['packs'])
                or not len(PACK_MAGIC) <= c['offset'] < MAX_PACK
                or not 0 < c['encoded_bytes'] <= logs.MAX_CHUNK + 1024
                or c['offset'] + c['encoded_bytes'] > MAX_PACK):
            raise logs.ArchiveError('Invalid packed reference')
        total += c['bytes']
    if total != m['raw_bytes']:
        raise logs.ArchiveError('Packed manifest length differs')
    return m


def decode(encoded, chunk):
    # Bound expansion and require exactly one complete gzip member, including CRC.
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        body = decoder.decompress(encoded, chunk['bytes'] + 1)
    except zlib.error as error:
        raise logs.ArchiveError('Invalid packed gzip') from error
    if (not decoder.eof or decoder.unused_data or decoder.unconsumed_tail
            or len(body) != chunk['bytes'] or logs.sha(body) != chunk['sha256']):
        raise logs.ArchiveError('Packed object hash/length/frame differs')
    return body


class Reader(io.RawIOBase):
    """Bounded streaming reader with four open pack descriptors at most."""
    def __init__(self, path):
        super().__init__()
        self.manifest = load_manifest(path)
        self.directory = Path(path).parent / '.log-packs'
        if not stat.S_ISDIR(self.directory.lstat().st_mode):
            raise logs.ArchiveError('Pack directory must not be a symlink')
        self.handles = {}
        self.cursor = 0
        self.pending = io.BytesIO()
        self.digest = hashlib.sha256()
        self.remaining = self.manifest['raw_bytes']
        self.verified = False
        self.pack_opens = 0

    def readable(self):
        return True

    def close(self):
        for stream in self.handles.values():
            stream.close()
        self.handles.clear()
        super().close()

    def readinto(self, output):
        if self.closed:
            raise ValueError('Reader is closed')
        if not output:
            return 0
        while True:
            n = self.pending.readinto(output)
            if n:
                return n
            if self.cursor == len(self.manifest['chunks']):
                if self.remaining or self.digest.hexdigest() != self.manifest['sha256']:
                    raise logs.ArchiveError('Packed archive full EOF differs')
                self.verified = True
                return 0
            chunk = self.manifest['chunks'][self.cursor]
            key = self.manifest['packs'][chunk['pack']]
            stream = self.handles.pop(key, None)
            if stream is None:
                if len(self.handles) == 4:
                    oldest = next(iter(self.handles))
                    self.handles.pop(oldest).close()
                path = self.directory / (key + '.pack')
                before = logs.regular(path)
                if not len(PACK_MAGIC) <= before.st_size <= MAX_PACK:
                    raise logs.ArchiveError('Pack size exceeds bound')
                stream = path.open('rb')
                if logs.version(os.fstat(stream.fileno())) != logs.version(before) or stream.read(len(PACK_MAGIC)) != PACK_MAGIC:
                    stream.close()
                    raise logs.ArchiveError('Pack identity/header differs')
                self.pack_opens += 1
            self.handles[key] = stream
            if chunk['offset'] + chunk['encoded_bytes'] > os.fstat(stream.fileno()).st_size:
                raise logs.ArchiveError('Pack reference exceeds actual file')
            stream.seek(chunk['offset'])
            body = decode(stream.read(chunk['encoded_bytes']), chunk)
            self.digest.update(body)
            self.remaining -= len(body)
            self.pending = io.BytesIO(body)
            self.cursor += 1


def verify(path, target=None):
    with Reader(path) as reader:
        buffer = bytearray(256 * 1024)
        while n := reader.readinto(buffer):
            if target is not None:
                target.write(memoryview(buffer)[:n])
        return dict(raw_bytes=reader.manifest['raw_bytes'], sha256=reader.manifest['sha256'],
                    pack_opens=reader.pack_opens, full_EOF_verified=reader.verified)


def prepare(paths, destination, *, maximum_pack_bytes=DEFAULT_PACK):
    """One session, fresh disjoint output; preserve compressed bytes and sharing."""
    paths = [Path(p) for p in paths]
    if (not paths or len({p.parent.resolve() for p in paths}) != 1
            or len({p.name for p in paths}) != len(paths)
            or not len(PACK_MAGIC) + logs.MAX_CHUNK + 1024 <= maximum_pack_bytes <= MAX_PACK):
        raise logs.ArchiveError('Bounded single-session qualification required')
    parent = paths[0].parent.resolve()
    old_store = parent / '.log-objects'
    if not stat.S_ISDIR(old_store.lstat().st_mode):
        raise logs.ArchiveError('Object directory must not be a symlink')
    manifests = [(p, logs.version(logs.regular(p)), logs.load_manifest(p)) for p in paths]
    if any(m['version'] != 1 for _, _, m in manifests):
        raise logs.ArchiveError('Preparation requires loose archives; never repack an uncertain output')
    destination = logs.create_destination(Path(destination), parent)
    store = destination / '.log-packs'
    store.mkdir(mode=0o700)
    refs, packs = {}, []
    stream = None
    digest = None
    size = 0

    def finish():
        nonlocal stream
        stream.flush()
        os.fsync(stream.fileno())
        stream.close()
        key = digest.hexdigest()
        os.rename(store / ('partial-' + str(len(packs))), store / (key + '.pack'))
        packs.append(key)
        stream = None

    try:
        for _, _, manifest in manifests:
            for chunk in manifest['chunks']:
                key = chunk['sha256']
                if key in refs:
                    if refs[key]['bytes'] != chunk['bytes']:
                        raise logs.ArchiveError('Shared object length collision')
                    continue
                path = old_store / (key + '.gz')
                before = logs.regular(path)
                if before.st_size > logs.MAX_CHUNK + 1024:
                    raise logs.ArchiveError('Oversized loose object')
                with path.open('rb') as source:
                    if logs.version(os.fstat(source.fileno())) != logs.version(before):
                        raise logs.ArchiveError('Loose object identity changed')
                    encoded = source.read(logs.MAX_CHUNK + 1025)
                if logs.version(logs.regular(path)) != logs.version(before):
                    raise logs.ArchiveError('Loose object changed while reading')
                decode(encoded, chunk)
                if stream and size + len(encoded) > maximum_pack_bytes:
                    finish()
                if stream is None:
                    if len(packs) == MAX_PACKS:
                        raise logs.ArchiveError('Session pack count exceeds bound')
                    stream = (store / ('partial-' + str(len(packs)))).open('xb')
                    os.fchmod(stream.fileno(), 0o600)
                    stream.write(PACK_MAGIC)
                    digest = hashlib.sha256(PACK_MAGIC)
                    size = len(PACK_MAGIC)
                refs[key] = dict(chunk, pack=len(packs), offset=size, encoded_bytes=len(encoded))
                stream.write(encoded)
                digest.update(encoded)
                size += len(encoded)
        if stream:
            finish()
        for key in packs:
            with (store / (key + '.pack')).open('rb') as body:
                if hashlib.file_digest(body, 'sha256').hexdigest() != key:
                    raise logs.ArchiveError('Full pack verification failed')
        for path, version, manifest in manifests:
            if logs.version(logs.regular(path)) != version:
                raise logs.ArchiveError('Source manifest changed')
            selected = sorted({refs[c['sha256']]['pack'] for c in manifest['chunks']})
            indices = {old: new for new, old in enumerate(selected)}
            packed = dict(manifest, version=2, packs=[packs[i] for i in selected],
                          chunks=[dict(refs[c['sha256']], pack=indices[refs[c['sha256']]['pack']])
                                  for c in manifest['chunks']])
            target = destination / path.name
            logs.write_new(target, encode(packed))
            verify(target)
        for directory in (store, destination):
            fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        return dict(manifests=len(manifests), unique_objects=len(refs), packs=len(packs),
                    physical_files=len(manifests) + len(packs), full_pack_and_log_hashes_verified=True,
                    source_mutations=False, live_application_supported=False)
    finally:
        if stream:
            stream.close()  # Failed preparation stays isolated; never reused or deleted here.
