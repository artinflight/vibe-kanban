"""Read-only real-chain audit, with bounded private SQLite restore verification.

No original archive is moved or removed. Completed private SQLite test copies
can be retired only after the whole Desktop stream and snapshot integrity pass.
"""
import argparse
import gzip
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import time

from vk_archive_store import Archive, reference, configure_transport
from vk_prep_common import digest, save, storage

FLOOR = 2 * 1024**3


def signature(path):
    st = Path(path).stat()
    return [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns]


def reserve(root, additional=0):
    fs = os.statvfs(root)
    free = fs.f_bavail * fs.f_frsize
    if free - additional < FLOOR:
        raise ValueError('Two-GiB SSD floor prevents additional restore scratch')
    return free


def checked_reference(row):
    local = Path(row['local'])
    descriptor = json.loads(Path(row['receipt']).read_text())
    ref = reference(descriptor)
    if (str(Path(ref['folder']) / ref['archive']) != str(local)
            or ref['sha256'] != row['sha256'] or ref.get('bytes') != row['bytes']):
        raise ValueError('Inventory and exact descriptor disagree: ' + str(local))
    archive = Archive(ref, desktop_only=True)
    if archive.remote != row['remote']:
        raise ValueError('Recorded Desktop locator differs from descriptor')
    return descriptor, archive


def audit_archive(row, root):
    descriptor, archive = checked_reference(row)
    task = root / archive.name.removesuffix('.tar.zst')
    task.mkdir(mode=0o700)
    local = Path(row['local'])
    before = signature(local)
    started = time.time()
    save(task / 'progress.json', {'phase': 'fresh-local-hash', 'archive': archive.remote, 'started': started})
    if local.is_symlink() or before[2] != row['bytes'] or digest(local) != row['sha256'] or signature(local) != before:
        raise ValueError('Local archive changed or failed its complete hash')
    save(task / 'progress.json', {'phase': 'Desktop-full-stream-and-SQLite-restore', 'archive': archive.remote})
    payloads, manifests, seen, sidecars = {}, [], set(), []
    total_files = total_bytes = sqlite_bytes = 0
    minimum = reserve(root)
    peak_scratch = 0
    with gzip.open(task / 'members.jsonl.gz', 'wt') as members, archive.contents() as contents:
        for member in contents:
            name = PurePosixPath(member.name)
            if name.is_absolute() or '..' in name.parts:
                raise ValueError('Unsafe archived member')
            members.write(json.dumps({'name': member.name, 'size': member.size, 'type': member.type.decode('ascii'),
                                      'mode': member.mode, 'link': member.linkname}) + '\n')
            if member.name == 'payload/manifest.json':
                if manifests or not member.isfile() or member.size > 32 * 1024**2:
                    raise ValueError('Invalid or duplicate manifest')
                manifests.append(json.load(contents.extractfile(member)))
            elif member.name.startswith('payload/sqlite/'):
                if member.isdir():
                    continue
                if member.isfile() and re.fullmatch(r'payload/sqlite/[a-f0-9]{64}\.sqlite-(wal|shm)', member.name):
                    if member.name in seen:
                        raise ValueError('Duplicate SQLite sidecar')
                    seen.add(member.name)
                    sidecars.append({'name': member.name, 'bytes': member.size})
                    continue
                if (not member.isfile() or not re.fullmatch(r'payload/sqlite/[a-f0-9]{64}\.sqlite', member.name)
                        or member.name in seen):
                    raise ValueError('Invalid SQLite snapshot member')
                seen.add(member.name)
                minimum = min(minimum, reserve(root, member.size))
                target = task / name.name
                with target.open('xb') as destination:
                    os.chmod(target, 0o600)
                    source = contents.extractfile(member)
                    while block := source.read(1024**2):
                        reserve(root)
                        destination.write(block)
                if target.stat().st_size != member.size:
                    raise ValueError('Short SQLite snapshot restore')
                checksum = digest(target)
                payloads[str(name.relative_to('payload'))] = {'path': str(target), 'sha256': checksum,
                                                            'bytes': member.size, 'identity': signature(target)}
                sqlite_bytes += member.size
                peak_scratch = max(peak_scratch, sqlite_bytes)
            elif member.isfile():
                total_files += 1
                total_bytes += member.size
    if len(manifests) != 1:
        raise ValueError('Missing verified archive manifest')
    manifest = manifests[0]
    for key in ('scope_sha256', 'plan_sha256', 'journal_instance', 'journal_sequence', 'parent'):
        if manifest[key] != descriptor[key]:
            raise ValueError('Archived manifest differs from retained descriptor: ' + key)
    expected = manifest['sqlite_snapshots']
    if set(payloads) != {r['path'] for r in expected.values()}:
        raise ValueError('Archived database set differs from manifest')
    for original, record in expected.items():
        row_copy = payloads[record['path']]
        if row_copy['sha256'] != record['sha256']:
            raise ValueError('Restored database checksum mismatch')
        path = Path(row_copy['path'])
        with sqlite3.connect(path.as_uri() + '?immutable=1', uri=True) as db:
            if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise ValueError('Restored database integrity failed')
        db.close()
        row_copy['original'] = original
        row_copy['integrity'] = 'ok'
    if signature(local) != before:
        raise ValueError('Local archive changed during remote audit')
    result = {'passed': True, 'started': started, 'finished': time.time(),
        'local': str(local), 'remote': archive.remote, 'sha256': archive.sha256,
        'bytes': row['bytes'], 'local_identity': before, 'descriptor': row['receipt'],
        'descriptor_sha256': digest(row['receipt']), 'manifest': manifest,
        'member_inventory_sha256': digest(task / 'members.jsonl.gz'),
        'non_database_files': total_files, 'non_database_bytes': total_bytes,
        'restored_sqlite_count': len(payloads), 'restored_sqlite_bytes': sqlite_bytes,
        'peak_snapshot_scratch_bytes': peak_scratch, 'minimum_free_bytes': min(minimum, reserve(root)),
        'snapshots': payloads, 'original_archives_retired': False, 'production_modified': False,
        'legacy_sidecars': sidecars,
        'all_non_database_payloads_materialized': False, 'full_remote_stream_hash_verified': True}
    save(task / 'result.json', result)
    # These exact files were created by this process under a new private folder;
    # all SQLite connections are closed, and the full retained remote stream passed.
    retired = []
    for copy in payloads.values():
        path = Path(copy['path'])
        if path.parent != task or path.is_symlink() or signature(path) != copy['identity']:
            raise ValueError('Private verified snapshot changed before retirement')
        path.unlink()
        retired.append(str(path))
    save(task / 'private-copy-retirement.json', {'files': retired, 'retained_original': str(local),
         'retained_remote': archive.remote, 'sha256': archive.sha256, 'archive_removed': False})
    return result


def validate_heads(heads, results):
    chains = []
    for head in heads:
        descriptor_path = Path(head['descriptor'])
        descriptor = json.loads(descriptor_path.read_text())
        current = str(Path(descriptor['folder']) / descriptor['archive'])
        if current not in results or results[current]['sha256'] != reference(descriptor)['sha256']:
            raise ValueError('Current head receipt checksum differs from audited archive')
        visited = []
        while current:
            if current in visited or current not in results:
                raise ValueError('Cycle or unaudited parent in required real chain')
            row = results[current]
            if not row['passed']:
                raise ValueError('Unverified member in real chain')
            manifest = row['manifest']
            if any(manifest[k] != descriptor[k] for k in ('scope_sha256', 'plan_sha256')):
                raise ValueError('Real-chain plan/scope mismatch')
            visited.append(current)
            parent = manifest['parent']
            if parent:
                next_path = str(Path(parent['folder']) / parent['archive'])
                if next_path not in results or results[next_path]['sha256'] != parent['sha256']:
                    raise ValueError('Real-chain parent hash mismatch')
                current = next_path
            else:
                current = None
        if visited != head['chain']:
            raise ValueError('Current chain differs from inventoried dependency graph')
        chains.append({'descriptor': str(descriptor_path), 'descriptor_sha256': digest(descriptor_path),
                       'archives': visited, 'passed': True})
    return chains


def reuse_audit(row, prior, root):
    result = json.loads((prior / 'result.json').read_text())
    _, archive = checked_reference(row)
    if (result.get('passed') is not True or result.get('full_remote_stream_hash_verified') is not True
            or result['sha256'] != row['sha256'] or result['remote'] != row['remote']
            or signature(row['local']) != result['local_identity'] or digest(row['local']) != row['sha256']
            or digest(row['receipt']) != result['descriptor_sha256']
            or digest(prior / 'members.jsonl.gz') != result['member_inventory_sha256']):
        raise ValueError('Prior completed audit no longer matches retained archive')
    archive.verify()
    result = dict(result, reused_from=str(prior), renewed_at=time.time(),
                  prior_receipt_sha256=digest(prior / 'result.json'))
    target = root / prior.name; target.mkdir(mode=0o700)
    shutil.copy2(prior / 'members.jsonl.gz', target / 'members.jsonl.gz')
    save(target / 'result.json', result)
    save(target / 'reuse.json', {'from': str(prior), 'full_fresh_remote_hash': True,
                                'no_original_archive_removed': True})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--resume-from', type=Path)
    parser.add_argument('--desktop-hostname')
    parser.add_argument('--desktop-host-key-alias')
    args = parser.parse_args()
    configure_transport(args.desktop_hostname, args.desktop_host_key_alias)
    os.umask(0o077)
    root = storage(args.root)
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    inventory = json.loads(args.inventory.read_text())
    results = {}
    for row in sorted(inventory['archive_files'], key=lambda r: r['bytes']):
        prior = args.resume_from / row['local'].split('/')[-1].removesuffix('.tar.zst') if args.resume_from else None
        if prior and (prior / 'result.json').is_file() and (prior / 'private-copy-retirement.json').is_file():
            # Revalidate the complete retained Desktop bytes; identical bytes keep
            # the earlier full-stream parsing and SQLite assertions valid.
            result = reuse_audit(row, prior, root)
        else:
            result = audit_archive(row, root)
        results[row['local']] = result
        save(root / 'progress.json', {'verified_archives': len(results), 'expected_archives': len(inventory['archive_files']),
             'verified_compressed_bytes': sum(r['bytes'] for r in results.values()), 'last_remote': result['remote'],
             'free_bytes': reserve(root), 'archives_retired': 0})
        print(json.dumps({'verified': len(results), 'remote': result['remote'], 'sqlite': result['restored_sqlite_count']}), flush=True)
    chains = validate_heads(inventory['backup_chain_heads'], results)
    save(root / 'chain-audit.json', {'passed': True, 'chains': chains,
         'archive_results': {k: {key: row[key] for key in ('remote', 'sha256', 'bytes', 'local_identity',
                              'restored_sqlite_count', 'descriptor', 'descriptor_sha256')} for k, row in results.items()},
         'retirement_authorized': False, 'consumer_migration_complete': False,
         'full_filesystem_restore_complete': False, 'production_modified': False,
         'inventory_sha256': digest(args.inventory), 'finished': time.time()})


if __name__ == '__main__':
    main()
