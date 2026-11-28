"""Bounded, in-memory lossless backup-format experiment; no filesystem writes.

Not an adopted archive format, production filter, or history retention policy.
All files and every byte remain in each independent manifest/object closure.
"""
import hashlib
import json
import re
import zlib
from pathlib import PurePosixPath

MAX_BYTES = 16 * 1024 * 1024
MAX_FILES = 64
MAX_BLOCKS = 65536
MAX_BLOCK = 65536
MAX_LAYOUT = 1024 * 1024
_GEAR = tuple(int.from_bytes(hashlib.sha256(bytes([n])).digest()[:8], 'big') for n in range(256))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def filename(key):
    if (not isinstance(key, str) or not key or len(key) > 1024
            or '\\' in key or '\x00' in key
            or any(p in ('', '.', '..') for p in key.split('/'))
            or PurePosixPath(key).is_absolute()):
        raise ValueError('unsafe logical filename')


def blocks(data, mode):
    if mode not in ('record', 'chunk'):
        raise ValueError('unknown experiment mode')
    start = 0
    state = 0
    for end, byte in enumerate(data, 1):
        state = ((state << 1) + _GEAR[byte]) & ((1 << 64) - 1)
        size = end - start
        boundary = (byte == 10 or size == MAX_BLOCK) if mode == 'record' else (
            size >= 2048 and ((state & 8191) == 0 or size >= 32768))
        if boundary:
            yield data[start:end]
            start = end
            state = 0
    if start < len(data):
        yield data[start:]


def pack(files, mode):
    if len(files) > MAX_FILES or sum(map(len, files.values())) > MAX_BYTES:
        raise ValueError('bounded experiment input exceeded')
    manifest = {'schema': 1, 'mode': mode, 'files': {}}
    objects = {}
    count = 0
    for key, data in files.items():
        filename(key)
        refs = []
        for block in blocks(data, mode):
            checksum = digest(block)
            objects.setdefault(checksum, zlib.compress(block, 6))
            refs.append({'sha256': checksum, 'bytes': len(block)})
            count += 1
            if count > MAX_BLOCKS:
                raise ValueError('bounded experiment reference count exceeded')
        manifest['files'][key] = {'sha256': digest(data), 'bytes': len(data), 'blocks': refs}
    return manifest, objects


def restore(manifest, objects):
    """Validate complete bounded closure before returning any recovered files."""
    if manifest.get('schema') != 1 or manifest.get('mode') not in ('record', 'chunk'):
        raise ValueError('unsupported manifest')
    files = manifest['files']
    if len(files) > MAX_FILES:
        raise ValueError('file count exceeded')
    result = {}
    total = count = 0
    for key, row in files.items():
        filename(key)
        size = row['bytes']
        if type(size) is not int or size < 0 or total + size > MAX_BYTES:
            raise ValueError('restore size exceeded')
        total += size
        output = bytearray()
        for ref in row['blocks']:
            count += 1
            checksum, length = ref['sha256'], ref['bytes']
            if (count > MAX_BLOCKS or not re.fullmatch('[0-9a-f]{64}', checksum)
                    or type(length) is not int or not 0 < length <= MAX_BLOCK
                    or len(output) + length > size):
                raise ValueError('invalid block descriptor')
            encoded = objects.get(checksum)
            if encoded is None or len(encoded) > MAX_BLOCK + 128:
                raise ValueError('missing or oversized object')
            decoder = zlib.decompressobj()
            try:
                block = decoder.decompress(encoded, length + 1)
            except zlib.error as exc:
                raise ValueError('invalid compressed object') from exc
            if (not decoder.eof or decoder.unused_data or decoder.unconsumed_tail
                    or len(block) != length or digest(block) != checksum):
                raise ValueError('object integrity failure')
            output.extend(block)
        if len(output) != size or digest(output) != row['sha256']:
            raise ValueError('file integrity failure')
        result[key] = bytes(output)
    return result


def measure(files, mode):
    manifest, objects = pack(files, mode)
    if restore(manifest, objects) != files:
        raise ValueError('exact restoration failed')
    rows = list(manifest['files'].values())
    refs = [r for row in rows for r in row['blocks']]
    sizes = {r['sha256']: r['bytes'] for r in refs}
    metadata = json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()
    return {
        'mode': mode, 'input_bytes': sum(map(len, files.values())),
        'references': len(refs), 'unique_blocks': len(objects),
        'unique_raw_bytes': sum(sizes.values()),
        'objects_zlib6_bytes': sum(map(len, objects.values())),
        'manifest_bytes': len(metadata),
        'manifest_zlib6_bytes': len(zlib.compress(metadata, 6)),
        'independent_file_zlib6_bytes': sum(len(zlib.compress(v, 6)) for v in files.values()),
        'all_files_zlib6_bytes': len(zlib.compress(b''.join(files.values()), 6)),
        'byte_exact_restore': True,
    }


def project_stdout(files):
    """Reversible framing experiment, NOT a reduced history representation.

    Extract only byte-for-byte canonical Stdout JSONL records. Noncanonical,
    partial, binary and oversized records stay raw. Preserve all fragment lengths
    and original file hashes. This lets chunk boundaries cross stdout wrappers.
    """
    if len(files) > MAX_FILES // 3 or sum(map(len, files.values())) > MAX_BYTES:
        raise ValueError('projection budget exceeded')
    layout = {}
    projected = {}
    count = 0
    for index, (key, data) in enumerate(files.items()):
        filename(key)
        stdout, raw = bytearray(), bytearray()
        recipe = []
        for line in blocks(data, 'record'):
            count += 1
            if count > MAX_BLOCKS:
                raise ValueError('projection recipe budget exceeded')
            value = None
            try:
                row = json.loads(line)
                if isinstance(row, dict) and set(row) == {'Stdout'} and isinstance(row['Stdout'], str):
                    candidate = row['Stdout']
                    canonical = json.dumps({'Stdout': candidate}, ensure_ascii=False, separators=(',', ':')).encode() + b'\n'
                    if canonical == line:
                        value = candidate.encode()
            except (ValueError, UnicodeError):
                pass
            kind = 'raw' if value is None else 'stdout'
            payload = line if value is None else value
            (raw if value is None else stdout).extend(payload)
            recipe.append([kind, len(payload)])
        prefix = f'projection/{index}'
        projected[prefix + '/raw'] = bytes(raw)
        projected[prefix + '/stdout'] = bytes(stdout)
        layout[key] = {'prefix': prefix, 'recipe': recipe, 'bytes': len(data), 'sha256': digest(data)}
    projected['projection/layout.json'] = json.dumps(layout, separators=(',', ':')).encode()
    if (len(projected['projection/layout.json']) > MAX_LAYOUT
            or sum(map(len, projected.values())) > MAX_BYTES):
        raise ValueError('projected budget exceeded')
    return projected


def restore_stdout(projected):
    if sum(map(len, projected.values())) > MAX_BYTES:
        raise ValueError('projected restore budget exceeded')
    if len(projected['projection/layout.json']) > MAX_LAYOUT:
        raise ValueError('projection layout exceeded')
    layout = json.loads(projected['projection/layout.json'])
    if len(layout) > MAX_FILES // 3:
        raise ValueError('projection file count exceeded')
    result = {}
    total = count = 0
    for key, row in layout.items():
        filename(key)
        if not re.fullmatch('projection/[0-9]+', row['prefix']):
            raise ValueError('invalid projection stream identity')
        size = row['bytes']
        if type(size) is not int or size < 0 or total + size > MAX_BYTES:
            raise ValueError('projection expansion exceeded')
        total += size
        offsets = {'raw': 0, 'stdout': 0}
        output = bytearray()
        for kind, length in row['recipe']:
            count += 1
            if (count > MAX_BLOCKS or kind not in offsets
                    or type(length) is not int or not 0 <= length <= MAX_BLOCK):
                raise ValueError('invalid projection recipe')
            stream = projected[row['prefix'] + '/' + kind]
            start = offsets[kind]
            payload = stream[start:start + length]
            if len(payload) != length:
                raise ValueError('projection stream truncated')
            offsets[kind] += length
            if kind == 'stdout':
                payload = json.dumps({'Stdout': payload.decode()}, ensure_ascii=False, separators=(',', ':')).encode() + b'\n'
            if len(output) + len(payload) > size:
                raise ValueError('projection output exceeded')
            output.extend(payload)
        if any(offset != len(projected[row['prefix'] + '/' + kind]) for kind, offset in offsets.items()):
            raise ValueError('unconsumed projection data')
        if len(output) != size or digest(output) != row['sha256']:
            raise ValueError('projection original identity mismatch')
        result[key] = bytes(output)
    return result
