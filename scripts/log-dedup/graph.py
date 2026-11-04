#!/usr/bin/env python3
"""Export exact physical backup dependencies for a selected archived batch.

Physical gzip/manifest hashes differ from the reconstructed conversation hash.
Every listed object is shared only within its original session directory.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import log_dedup as logs
from reclaim import file_hash


def inventory(root, plan):
    root = Path(root).resolve(strict=True)
    members = {}
    logical = {}
    if not 1 <= len(plan['files']) <= 64:
        raise logs.ArchiveError('Bounded exact archive selection required')
    for entry in plan['files']:
        path = logs.safe_path(root, entry['path'])
        manifest = logs.reconstruct(path)
        if manifest['sha256'] != entry['sha256'] or manifest['raw_bytes'] != entry['raw_bytes']:
            raise logs.ArchiveError('Logical archive does not match selected original')
        selected = [(path, 'manifest')]
        selected += [(path.parent / '.log-objects' / (chunk['sha256'] + '.gz'), 'object')
                     for chunk in manifest['chunks']]
        selected += [(path.with_suffix('.' + sidecar['extension']), 'sidecar')
                     for sidecar in entry['sidecars']]
        for member, kind in selected:
            relative = str(member.relative_to(root))
            if relative not in members:
                before = logs.regular(member)
                digest = file_hash(member)
                if kind == 'sidecar':
                    expected = next(row['sha256'] for row in entry['sidecars']
                                    if member == path.with_suffix('.' + row['extension']))
                    if digest != expected:
                        raise logs.ArchiveError('Archive sidecar does not match original')
                members[relative] = {'path': relative, 'sha256': digest,
                                     'bytes': before.st_size, 'kind': kind}
        logical[entry['path']] = {'sha256': manifest['sha256'], 'bytes': manifest['raw_bytes']}
    return {'version': 1, 'root': str(root), 'members': sorted(members.values(), key=lambda row: row['path']),
            'logical_originals': logical, 'physical_members': len(members),
            'physical_bytes': sum(row['bytes'] for row in members.values()),
            'independent_backup_verified': False,
            'note': 'Export is a dependency contract, not a Desktop B recovery receipt.'}


def verify_provider(graph, provider, guard):
    """Owner adapter reopens each physical member through its normal B reader.

    Provider open_member(relative, sha256) must preserve the original namespace;
    successful verification requires actual streamed bytes, never a ready flag.
    """
    if not provider.location.startswith('desktop:B:/vk-backups/'):
        raise logs.ArchiveError('Canonical B provider required')
    if (graph['version'] != 1 or not graph['logical_originals']
            or graph['physical_members'] != len(graph['members'])
            or len({row['path'] for row in graph['members']}) != len(graph['members'])):
        raise logs.ArchiveError('Complete nonempty unique archive graph required')
    members = {row['path']: row for row in graph['members']}
    manifests = {}
    base = rf'[0-9a-f]{{2}}/{logs.UUID}/processes/'
    patterns = {'manifest': base + logs.UUID + r'\.jsonl',
                'sidecar': base + logs.UUID + r'\.(capture|recovered-final)\.json',
                'object': base + r'\.log-objects/[0-9a-f]{64}\.gz'}
    for member in graph['members']:
        path = Path(member['path'])
        if (member['kind'] not in patterns or not re.fullmatch(patterns[member['kind']], member['path'])
                or path.parts[0] != path.parts[1][:2] or not logs.valid_hash(member['sha256'])
                or type(member['bytes']) is not int or member['bytes'] < 0):
            raise logs.ArchiveError('Invalid archive backup member reference')
        if member['kind'] == 'manifest' and member['bytes'] > logs.MAX_MANIFEST + len(logs.MAGIC):
            raise logs.ArchiveError('Manifest backup body exceeds bound')
        guard()
        total = 0
        digest = hashlib.sha256()
        manifest_body = bytearray()
        with provider.open_member(member['path'], member['sha256']) as source:
            while chunk := source.read(1024 * 1024):
                total += len(chunk)
                if total > member['bytes']:
                    raise logs.ArchiveError('B archive graph member exceeds expected size')
                digest.update(chunk)
                if member['kind'] == 'manifest':
                    manifest_body.extend(chunk)
        if total != member['bytes'] or digest.hexdigest() != member['sha256']:
            raise logs.ArchiveError('B archive graph member mismatch')
        if member['kind'] == 'manifest':
            if not manifest_body.startswith(logs.MAGIC):
                raise logs.ArchiveError('B member is not an archive manifest')
            manifests[member['path']] = json.loads(manifest_body[len(logs.MAGIC):])
    if set(manifests) != set(graph['logical_originals']):
        raise logs.ArchiveError('B graph omits a selected manifest')
    for relative, manifest in manifests.items():
        expected = graph['logical_originals'][relative]
        if manifest['sha256'] != expected['sha256'] or manifest['raw_bytes'] != expected['bytes']:
            raise logs.ArchiveError('B manifest differs from selected logical original')
        for chunk in manifest['chunks']:
            if not logs.valid_hash(chunk['sha256']):
                raise logs.ArchiveError('Invalid B manifest object reference')
            reference = str(Path(relative).parent / '.log-objects' / (chunk['sha256'] + '.gz'))
            if reference not in members or members[reference]['kind'] != 'object':
                raise logs.ArchiveError('B graph omits a referenced object')
    return {'independent_backup_verified': True, 'physical_members': len(graph['members']),
            'verification_scope': 'Physical members and reference closure; normal restore and Linux metadata require owner acceptance.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(inventory(args.root, json.loads(args.plan.read_bytes())), indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        message = str(error) if isinstance(error, logs.ArchiveError) else type(error).__name__
        print('Archive graph failed: ' + message, file=sys.stderr)
        sys.exit(1)
