"""Prepare closed raw logs directly into packs, reusing current session chunks.

Offline preparation only. Publication uses PackedBatch and its actual custody /
recovery gates. No loose-object fanout is created, including in staging.
"""
import gzip
import hashlib
import os
from pathlib import Path

import log_dedup as logs
import packed_objects as packed
import reclaim


def prepare(plan, destination, *, reuse=(), maximum_pack_bytes=packed.DEFAULT_PACK):
    rows = plan['files']
    root = Path(plan['source_root'])
    if (not 1 <= len(rows) <= 64 or len({r['path'] for r in rows}) != len(rows)
            or sum(r['raw_bytes'] for r in rows) > 2 * 1024**3
            or len({str(Path(r['path']).parent) for r in rows}) != 1
            or not len(packed.PACK_MAGIC) + logs.MAX_CHUNK + 1024 <= maximum_pack_bytes <= packed.MAX_PACK):
        raise logs.ArchiveError('Bounded single-session raw selection required')
    parent = logs.safe_path(root, rows[0]['path']).parent
    destination = logs.create_destination(Path(destination), parent)
    store = destination / '.log-packs'; store.mkdir(mode=0o700)
    refs, pack_paths, pending, manifests = {}, {}, {}, []
    for source in reuse:
        source = Path(source)
        if source.parent != parent:
            raise logs.ArchiveError('Reuse must stay in the exact session')
        packed.verify(source)
        manifest = packed.load_manifest(source)
        for key in manifest['packs']:
            path = parent / '.log-packs' / (key + '.pack')
            if reclaim.file_hash(path) != key:
                raise logs.ArchiveError('Existing pack hash differs')
            pack_paths[key] = path
        for chunk in manifest['chunks']:
            key = chunk['sha256']; pack_key = manifest['packs'][chunk['pack']]
            value = dict(chunk, pack=pack_key)
            if key in refs and refs[key]['bytes'] != chunk['bytes']:
                raise logs.ArchiveError('Shared chunk length collision')
            refs.setdefault(key, value)
    stream, digest, size, serial = None, None, 0, 0

    def finish():
        nonlocal stream, serial
        stream.flush(); os.fsync(stream.fileno()); stream.close()
        key = digest.hexdigest()
        path = store / (key + '.pack')
        os.link(store / f'partial-{serial}', path)
        (store / f'partial-{serial}').unlink()
        for chunk_key in pending:
            refs[chunk_key]['pack'] = key
        pending.clear(); pack_paths[key] = path
        stream = None; serial += 1

    try:
        for row in rows:
            source = logs.safe_path(root, row['path'])
            if logs.version(logs.regular(source)) != row['identity']:
                raise logs.ArchiveError('Selected raw source changed')
            digest_raw, count, chunks = hashlib.sha256(), 0, []
            with source.open('rb') as raw:
                if logs.version(os.fstat(raw.fileno())) != row['identity']:
                    raise logs.ArchiveError('Raw inode changed during open')
                if logs.is_archive_header(raw.read(len(logs.MAGIC))):
                    raise logs.ArchiveError('Forward input must be raw')
                raw.seek(0)
                for body in logs.chunks(raw):
                    count += len(body)
                    if count > row['raw_bytes']:
                        raise logs.ArchiveError('Raw input grew beyond selection')
                    digest_raw.update(body); key = logs.sha(body)
                    if key not in refs:
                        encoded = gzip.compress(body, mtime=0)
                        if stream and size + len(encoded) > maximum_pack_bytes:
                            finish()
                        if stream is None:
                            stream = (store / f'partial-{serial}').open('xb')
                            os.fchmod(stream.fileno(), 0o600)
                            stream.write(packed.PACK_MAGIC)
                            digest = hashlib.sha256(packed.PACK_MAGIC); size = len(packed.PACK_MAGIC)
                        refs[key] = dict(sha256=key, bytes=len(body), pack=None,
                                         offset=size, encoded_bytes=len(encoded))
                        pending[key] = True
                        stream.write(encoded); digest.update(encoded); size += len(encoded)
                    elif refs[key]['bytes'] != len(body):
                        raise logs.ArchiveError('Chunk length collision')
                    chunks.append(key)
            if count != row['raw_bytes'] or digest_raw.hexdigest() != row['sha256']:
                raise logs.ArchiveError('Raw history differs from selection')
            if logs.version(logs.regular(source)) != row['identity']:
                raise logs.ArchiveError('Raw history changed during preparation')
            manifests.append((source.name, row, chunks))
        if stream:
            finish()
        used = {refs[key]['pack'] for _, _, keys in manifests for key in keys}
        for key in used:
            source, target = pack_paths[key], store / (key + '.pack')
            if source != target:
                # Copy only packs actually referenced. Create-only and bounded;
                # no external hard links into live data or old backup epochs.
                with source.open('rb') as inp, target.open('xb') as out:
                    os.fchmod(out.fileno(), 0o600)
                    while block := inp.read(1024 * 1024):out.write(block)
                    out.flush(); os.fsync(out.fileno())
            if reclaim.file_hash(target) != key:
                raise logs.ArchiveError('Prepared pack hash differs')
        for name, row, keys in manifests:
            pack_keys = sorted({refs[key]['pack'] for key in keys})
            indices = {key: i for i, key in enumerate(pack_keys)}
            value = dict(version=2, raw_bytes=row['raw_bytes'], sha256=row['sha256'], packs=pack_keys,
                         chunks=[dict(refs[key], pack=indices[refs[key]['pack']]) for key in keys])
            target = destination / name
            logs.write_new(target, packed.encode(value)); packed.verify(target)
        reclaim.sync_directory(store); reclaim.sync_directory(destination)
        return dict(manifests=len(rows), packs=len(used), new_packs=serial,
                    loose_objects_created=0, source_mutations=False)
    finally:
        if stream:stream.close()
