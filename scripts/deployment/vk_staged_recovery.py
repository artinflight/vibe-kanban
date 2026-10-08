"""Bounded Desktop recovery acceptance, not a partial production restore command.

All archived SQLite snapshots and selected regular files use the real restore
engine. Every compressed byte is verified, but unselected non-DB files are not
materialized. Authenticated cached manifests avoid a second full transfer; each
must match the actual streamed manifest before the result can pass.
"""
from contextlib import contextmanager
import copy
import hashlib
import io
import json
from pathlib import Path
from unittest.mock import patch

from vk_archive_store import Archive, reference
from vk_prep_common import digest, save
from vk_rolling_backup import restore_chain


class HashReader:
    def __init__(self, source, checksum):
        self.source, self.checksum = source, checksum

    def read(self, size=-1):
        block = self.source.read(size)
        self.checksum.update(block)
        return block


def staged_restore(result, destination, records, selected):
    """Records must bind cached manifest and fresh Desktop checksum evidence."""
    destination = Path(destination)
    selected = set(selected)
    if any(Path(p).is_absolute() or '..' in Path(p).parts or p.startswith('payload/') for p in selected):
        raise ValueError('Unsafe staged selection')
    ancestors = {str(parent) for p in selected for parent in Path(p).parents}
    original_contents = Archive.contents
    expected_files, expected_databases, streamed = {}, {}, []

    def record(archive):
        row = records.get(archive.key)
        if (not archive.remote or row is None or row['sha256'] != archive.sha256
                or row['verified_remote'] != {'sha256': archive.sha256, 'bytes': archive.size,
                                              'remote': archive.remote}):
            raise ValueError('Staged recovery requires fresh exact Desktop verification')
        return row

    def cached_manifest(archive):
        return copy.deepcopy(record(archive)['manifest'])

    @contextmanager
    def filtered_contents(archive):
        receipt = record(archive)
        hashes, modes = {}, {}
        manifest_body = None
        with original_contents(archive) as tar:
            class SelectedTar:
                def __iter__(self):
                    nonlocal manifest_body
                    for member in tar:
                        if member.name == 'payload/manifest.json':
                            manifest_body = tar.extractfile(member).read()
                            if json.loads(manifest_body) != receipt['manifest']:
                                raise ValueError('Cached manifest differs from Desktop stream')
                            yield member
                        elif member.name.startswith('payload/'):
                            yield member
                        elif member.name in selected:
                            if not member.isfile():
                                raise ValueError('Selected regular-file type changed; reconcile selection')
                            hashes[member.name] = hashlib.sha256()
                            modes[member.name] = member.mode
                            yield member
                        elif member.isdir() and member.name in ancestors:
                            yield member

                def extractfile(self, member):
                    if member.name == 'payload/manifest.json':
                        return io.BytesIO(manifest_body)
                    source = tar.extractfile(member)
                    return HashReader(source, hashes[member.name]) if member.name in hashes else source
            yield SelectedTar()
        if manifest_body is None:
            raise ValueError('Desktop stream lacks manifest')
        for name, checksum in hashes.items():
            expected_files[name] = {'sha256': checksum.hexdigest(), 'mode': modes[name]}
        for raw in receipt['manifest']['absent_paths']:
            name = raw.lstrip('/').rstrip('/')
            for mapping in (expected_files, expected_databases):
                for key in list(mapping):
                    if key == name or key.startswith(name + '/'):
                        del mapping[key]
        for raw, row in receipt['manifest']['sqlite_snapshots'].items():
            expected_databases[raw.lstrip('/')] = row['sha256']
        streamed.append({'remote': archive.remote, 'sha256': archive.sha256,
                         'bytes': archive.size, 'complete_stream_verified': True})

    with patch.object(Archive, 'manifest', cached_manifest), patch.object(Archive, 'contents', filtered_contents):
        restored = restore_chain(result, destination, desktop_only=True, retire_verified_snapshots=True)
    for name, row in expected_files.items():
        path = destination / 'files' / name
        if digest(path) != row['sha256'] or path.stat().st_mode & 0o777 != row['mode']:
            raise ValueError('Staged regular file hash/mode mismatch')
    for name, checksum in expected_databases.items():
        if digest(destination / 'files' / name) != checksum:
            raise ValueError('Staged latest database hash mismatch')
    required = {raw.lstrip('/') for raw in result['databases']}
    if not required.issubset(expected_databases):
        raise ValueError('Missing required database in staged recovery')
    proof = {'passed': True, 'provider': 'Desktop B only', 'restore': restored,
             'streamed_archives': streamed, 'regular_files_verified': expected_files,
             'latest_database_hashes': expected_databases, 'required_database_count': len(required),
             'all_required_databases_restored': True, 'full_non_database_tree_materialized': False,
             'unselected_payloads_covered_by_complete_archive_hash': True,
             'compressed_archives_downloaded': False, 'production_modified': False}
    save(destination / 'staged-recovery.json', proof)
    return proof
