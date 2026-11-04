#!/usr/bin/env python3
"""Lossless log deduplication. No command overwrites or removes a source file."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

MAGIC = b'VKLOGCAS1\n'
MIN_CHUNK = 16 * 1024
MAX_CHUNK = 256 * 1024
MAX_MANIFEST = 16 * 1024 * 1024
MAX_CHUNKS = 100_000
UUID = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'


class ArchiveError(ValueError):
    """Only controlled, payload-free operator diagnostics."""


LOG_PATH = re.compile(rf'([0-9a-f]{{2}})/({UUID})/processes/({UUID})\.jsonl')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def version(st):
    return [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns]


def regular(path):
    st = path.lstat()
    if not stat.S_ISREG(st.st_mode):
        raise ArchiveError('Expected regular file, refused symlink or special file')
    return st


def safe_path(root, relative):
    match = LOG_PATH.fullmatch(relative)
    if not match or match[1] != match[2][:2]:
        raise ArchiveError('Expected a session-relative process JSONL path')
    path = root / relative
    for parent in [root, *list(path.parents)[:3]]:
        if not stat.S_ISDIR(parent.lstat().st_mode):
            raise ArchiveError('Refused symlink or non-directory in source path')
    regular(path)
    return path


def chunks(stream):
    """Content-defined cuts at escaped newlines, independent of pipe records.

    Hash local content at newline candidates to resynchronise repeated text
    after insertions. Bound memory and CPU even without newline candidates.
    """
    pending = bytearray()
    eof = False
    while True:
        while len(pending) < MAX_CHUNK and not eof:
            block = stream.read(MAX_CHUNK - len(pending))
            if not block:
                eof = True
            pending.extend(block)
        if not pending:
            break
        end = len(pending)
        offset = MIN_CHUNK
        while offset < len(pending):
            found = pending.find(b'\\n', offset)
            if found < 0:
                break
            cut = found + 2
            if hashlib.sha256(pending[cut - 64:cut]).digest()[0] & 15 == 0:
                end = cut
                break
            offset = cut
        yield bytes(pending[:end])
        del pending[:end]


def encode(manifest):
    data = MAGIC + json.dumps(manifest, separators=(',', ':')).encode() + b'\n'
    if len(data) - len(MAGIC) > MAX_MANIFEST:
        raise ArchiveError('Manifest exceeds reader bound')
    return data


def manifest_for(path, objects, output=None):
    before = regular(path)
    digest = hashlib.sha256()
    records = []
    with path.open('rb') as source:
        if source.read(len(MAGIC)) == MAGIC:
            raise ArchiveError('Source is already archived; use verify or restore')
        source.seek(0)
        if version(os.fstat(source.fileno())) != version(before):
            raise ArchiveError('Source identity changed during open')
        for block in chunks(source):
            digest.update(block)
            key = sha(block)
            records.append({'sha256': key, 'bytes': len(block)})
            if len(records) > MAX_CHUNKS:
                raise ArchiveError('Chunk count exceeds reader bound')
            if key not in objects:
                compressed = gzip.compress(block, compresslevel=6, mtime=0)
                objects[key] = [len(block), len(compressed)]
                if output is not None:
                    target = output / (key + '.gz')
                    write_new(target, compressed)
            elif objects[key][0] != len(block):
                raise ArchiveError('Object collision')
        if version(os.fstat(source.fileno())) != version(before):
            raise ArchiveError('Source changed during scan')
    if version(regular(path)) != version(before):
        raise ArchiveError('Source changed during scan')
    manifest = {'version': 1, 'raw_bytes': before.st_size,
                'sha256': digest.hexdigest(), 'chunks': records}
    return manifest, before


def write_new(path, data):
    with path.open('xb') as target:
        os.chmod(path, 0o600)
        target.write(data)
        target.flush()
        os.fsync(target.fileno())


def sidecars(path):
    result = []
    for extension in ('capture.json', 'recovered-final.json'):
        sidecar = path.with_suffix('.' + extension)
        if sidecar.exists() or sidecar.is_symlink():
            before = regular(sidecar)
            data = sidecar.read_bytes()
            if version(regular(sidecar)) != version(before):
                raise ArchiveError('Sidecar changed during read')
            result.append((extension, data, version(before)))
    return result


def scan(root, relatives):
    stores = {}
    files = []
    for relative in relatives:
        path = safe_path(root, relative)
        objects = stores.setdefault(str(path.parent), {})
        manifest, st = manifest_for(path, objects)
        companions = sidecars(path)
        files.append({'path': relative, 'identity': version(st),
                      'sha256': manifest['sha256'], 'raw_bytes': st.st_size,
                      'allocated_bytes': st.st_blocks * 512,
                      'manifest_bytes': len(encode(manifest)),
                      'sidecars': [{'extension': ext, 'sha256': sha(data),
                                    'identity': identity}
                                   for ext, data, identity in companions]})
    raw = sum(f['raw_bytes'] for f in files)
    unique = sum(v[0] for store in stores.values() for v in store.values())
    compressed = sum(v[1] for store in stores.values() for v in store.values())
    manifests = sum(f['manifest_bytes'] for f in files)
    # Conservative data-block estimate; directory/index metadata is extra.
    rounded = sum(((v[1] + 4095) // 4096) * 4096
                  for store in stores.values() for v in store.values())
    rounded += sum(((f['manifest_bytes'] + 4095) // 4096) * 4096 for f in files)
    allocated = sum(f['allocated_bytes'] for f in files)
    return {'version': 1, 'source_root': str(root), 'files': files,
            'metrics': {'files': len(files), 'raw_bytes': raw,
                        'source_allocated_bytes': allocated,
                        'unique_chunk_bytes': unique,
                        'duplicate_chunk_bytes': raw - unique,
                        'compressed_unique_bytes': compressed,
                        'manifest_bytes': manifests,
                        'archive_payload_bytes': compressed + manifests,
                        'estimated_archive_allocated_bytes': rounded,
                        'estimated_recoverable_bytes': allocated - rounded,
                        'directory_metadata_excluded': True}}


def load_manifest(path):
    regular(path)
    with path.open('rb') as source:
        if source.read(len(MAGIC)) != MAGIC:
            raise ArchiveError('Not a log archive')
        data = source.read(MAX_MANIFEST + 1)
    if len(data) > MAX_MANIFEST:
        raise ArchiveError('Oversized manifest')
    value = json.loads(data)
    if (set(value) != {'version', 'raw_bytes', 'sha256', 'chunks'}
            or value['version'] != 1 or not valid_hash(value['sha256'])
            or type(value['raw_bytes']) is not int or value['raw_bytes'] < 0
            or len(value['chunks']) > MAX_CHUNKS):
        raise ArchiveError('Invalid manifest')
    total = 0
    for chunk in value['chunks']:
        if (set(chunk) != {'sha256', 'bytes'} or not valid_hash(chunk['sha256'])
                or type(chunk['bytes']) is not int or not 0 < chunk['bytes'] <= MAX_CHUNK):
            raise ArchiveError('Invalid chunk')
        total += chunk['bytes']
    if total != value['raw_bytes']:
        raise ArchiveError('Invalid manifest length')
    return value


def valid_hash(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def reconstruct(path, target=None):
    manifest = load_manifest(path)
    digest = hashlib.sha256()
    directory = path.parent / '.log-objects'
    if not stat.S_ISDIR(directory.lstat().st_mode):
        raise ArchiveError('Object directory must not be a symlink')
    for chunk in manifest['chunks']:
        obj = directory / (chunk['sha256'] + '.gz')
        if regular(obj).st_size > MAX_CHUNK + 1024:
            raise ArchiveError('Oversized object')
        with gzip.open(obj, 'rb') as stream:
            data = stream.read(chunk['bytes'] + 1)
        if len(data) != chunk['bytes'] or sha(data) != chunk['sha256']:
            raise ArchiveError('Object hash/length mismatch')
        digest.update(data)
        if target is not None:
            target.write(data)
    if digest.hexdigest() != manifest['sha256']:
        raise ArchiveError('Archive hash mismatch')
    return manifest


def create_destination(destination, root):
    # Reject an ancestor/descendant of source, including paths through symlinks.
    destination = destination.resolve()
    if destination == root or destination in root.parents or root in destination.parents:
        raise ArchiveError('Destination must be disjoint from source')
    destination.mkdir(mode=0o700)  # An existing destination is never reused.
    return destination


def pack(plan, destination):
    root = Path(plan['source_root']).resolve()
    relatives = [entry['path'] for entry in plan['files']]
    if scan(root, relatives) != plan:
        raise ArchiveError('Plan stale; no output written')
    destination = create_destination(destination, root)
    stores = {}
    for entry in plan['files']:
        source = safe_path(root, entry['path'])
        companions = sidecars(source)
        for ext, data, _ in companions:
            if ext == 'capture.json':
                state = json.loads(data)
                if not isinstance(state, dict) or state.get('capture_state') != 'closed':
                    raise ArchiveError('Refused pending/incomplete capture')
        target = destination / entry['path']
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        store = target.parent / '.log-objects'
        store.mkdir(exist_ok=True, mode=0o700)
        objects = stores.setdefault(str(target.parent), {})
        manifest, before = manifest_for(source, objects, store)
        if version(before) != entry['identity'] or manifest['sha256'] != entry['sha256']:
            raise ArchiveError('Source changed since plan')
        write_new(target, encode(manifest))
        reconstruct(target)  # Independently reopen every reference before success.
        for ext, data, _ in companions:
            write_new(target.with_suffix('.' + ext), data)
    # Recheck the complete frozen set after building it, not just per-file.
    if scan(root, relatives) != plan:
        raise ArchiveError('Source changed while packing; output is unsealed')
    # Make the complete object graph durable before publishing the seal.
    sync_directories(destination)
    write_new(destination / 'receipt.json', json.dumps(plan, indent=2).encode() + b'\n')
    sync_directories(destination)
    return {'verified': True, 'files': len(relatives), 'source_changed': False}


def sync_directories(root):
    for directory, _, _ in os.walk(root, topdown=False):
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def verify_or_restore(root, destination=None):
    plan = json.loads((root / 'receipt.json').read_text())
    if destination is not None:
        destination = create_destination(destination, root)
    for entry in plan['files']:
        path = safe_path(root, entry['path'])
        if destination is None:
            manifest = reconstruct(path)
        else:
            target = destination / entry['path']
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with target.open('xb') as output:
                os.chmod(target, 0o600)
                manifest = reconstruct(path, output)
                output.flush()
                os.fsync(output.fileno())
        if manifest['sha256'] != entry['sha256'] or manifest['raw_bytes'] != entry['raw_bytes']:
            raise ArchiveError('Receipt mismatch')
        for companion in entry['sidecars']:
            sidecar = path.with_suffix('.' + companion['extension'])
            regular(sidecar)
            data = sidecar.read_bytes()
            if sha(data) != companion['sha256']:
                raise ArchiveError('Sidecar hash mismatch')
            if destination is not None:
                write_new(target.with_suffix('.' + companion['extension']), data)
    if destination is not None:
        sync_directories(destination)
    return {'verified': True, 'files': len(plan['files'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    measure = commands.add_parser('plan', help='Read-only measurement on an exact JSON path list')
    measure.add_argument('--root', type=Path, required=True)
    measure.add_argument('--files', type=Path, required=True)
    build = commands.add_parser('pack', help='Create a new verified archive tree; never replace source')
    build.add_argument('--plan', type=Path, required=True)
    build.add_argument('--destination', type=Path, required=True)
    for command in ('verify', 'restore'):
        sub = commands.add_parser(command)
        sub.add_argument('--root', type=Path, required=True)
        if command == 'restore':
            sub.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'plan':
        relatives = json.loads(args.files.read_text())
        if (not isinstance(relatives, list) or not relatives
                or not all(isinstance(item, str) for item in relatives)
                or len(set(relatives)) != len(relatives)):
            raise ArchiveError('Expected a nonempty unique list of relative paths')
        result = scan(args.root.resolve(), relatives)
    elif args.command == 'pack':
        result = pack(json.loads(args.plan.read_text()), args.destination)
    else:
        result = verify_or_restore(args.root.resolve(), getattr(args, 'destination', None))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, EOFError) as error:
        # Never include source text, JSON fragments or transcript payloads.
        message = str(error) if isinstance(error, ArchiveError) else type(error).__name__
        print('Log archive failed: ' + message, file=sys.stderr)
        sys.exit(1)
