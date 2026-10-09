"""Reuse an authenticated full-checkpoint index; always recheck actual B bytes.

Only an independently B-preserved, hash-pinned index from a verified candidate
tool package is accepted. This does not create a journal, accept a delta, grant
operational acceptance or waive metadata checks. Replay hashes every selected
file and drains the unchanged complete archive before accepting materialization.
"""
import copy
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess

from vk_archive_store import Archive, reference, SSH, remote_code
from vk_candidate_generation import (require, digest, relative, validate_manifest,
                                     capture_link_exceptions, atime_binding, open_regular)
from vk_candidate_package import verify as verify_package


class VerifiedCheckpointProvider:
    def __init__(self, descriptor, index_path, index_receipt, manifest_sha256, *,
                 verifier_package=None, verifier_source=None, fixture_only=False, archive_factory=Archive,
                 source_prefix='/'):
        require(archive_factory is Archive or fixture_only, 'custom checkpoint reader requires fixture mode')
        require(descriptor.get('parent') is None and descriptor.get('passed') is True,
                'verified index reuse only supports a complete accepted checkpoint')
        require(index_receipt.get('desktop_verified') is True,
                'derived index must be independently preserved on B')
        if not fixture_only:
            require(source_prefix == '/', 'operational cached checkpoint requires unchanged absolute namespace')
            package = verify_package(verifier_package, expected_source=verifier_source)
            require(package['source_commit'] == verifier_source and package['fixture_only'] is False,
                    'checkpoint verifier source is not pinned/nonfixture')
            require(index_receipt.get('desktop_directory', '').startswith('B:/vk-backups/'),
                    'derived index has no authoritative B locator')
            require(descriptor.get('scope_sha256'), 'checkpoint scope is missing')
        path = Path(index_path)
        require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 256 * 1024**2,
                'derived index missing/aliased/over budget')
        require(path.resolve() == path, 'derived index has a parent path alias')
        with open_regular(path.parent, path.name) as stream:
            before = os.fstat(stream.fileno())
            raw = stream.read(256 * 1024**2 + 1)
            after = os.fstat(stream.fileno())
            signature = lambda st: (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
            require(signature(before) == signature(after) == signature(path.stat()),
                    'derived index changed during authentication')
            require(len(raw) <= 256 * 1024**2 and hashlib.sha256(raw).hexdigest() == index_receipt.get('sha256'),
                    'derived index bytes differ from B-preserved proof')
            proof = json.loads(raw)
        require(path.stat().st_size == index_receipt.get('bytes'), 'derived index size differs')
        require(proof.get('fixture_only') is fixture_only and proof.get('full_current_state') is True
                and proof.get('provider') == 'desktop-B', 'checkpoint index provenance differs')
        require(proof['manifest_sha256'] == manifest_sha256 == digest(proof['entries']),
                'derived manifest differs from actual verifier result')
        if not fixture_only:
            require(proof['scope_sha256'] == descriptor['scope_sha256']
                    and proof['capture_id'].endswith(Path(descriptor['folder']).name),
                    'derived checkpoint generation/scope differs from retained descriptor')
        validate_manifest(proof['entries'], recorded_link_exceptions=capture_link_exceptions(proof))
        if not fixture_only:
            require(proof.get('restore_archived_atime') is True and atime_binding(
                manifest_sha256, proof['archived_atime_ns']) == proof['archived_atime_sha256'],
                'derived timestamp proof differs')
        self.proof, self.descriptor = proof, copy.deepcopy(descriptor)
        self.fixture_only, self.index_receipt = fixture_only, dict(index_receipt)
        self.index_remote = index_receipt.get('desktop_directory', '').rstrip('/') + '/' + path.name
        if not fixture_only:
            require(index_receipt.get('name') == path.name and re.fullmatch(
                r'B:/vk-backups/[A-Za-z0-9_./-]+', self.index_remote)
                and '..' not in PurePosixPath(self.index_remote).parts, 'unsafe B index locator')
        self.archive = archive_factory(reference(descriptor), desktop_only=True)
        self.prefix = PurePosixPath(source_prefix)
        self.snapshots = {'payload/' + row['path']: self.mapped(raw)
                          for raw, row in descriptor['sqlite_snapshots'].items()}
        self.capture = proof['capture_id']

    def verify(self, capture):
        require(capture == self.capture, 'cached checkpoint cannot authenticate another generation')
        if not self.fixture_only:
            result = subprocess.run(SSH, input=remote_code(self.index_remote,
                self.index_receipt['sha256'], self.index_receipt['bytes'], False), text=True,
                capture_output=True, timeout=1800)
            require(result.returncode == 0, 'B-preserved index readback failed; no alternate reader')
            require(json.loads(result.stdout) == {'sha256': self.index_receipt['sha256'],
                'bytes': self.index_receipt['bytes'], 'remote': self.index_remote},
                'B index readback receipt differs')
        self.archive.verify()  # Fresh complete B hash, never host/local payload fallback.
        return copy.deepcopy(self.proof)

    def mapped(self, raw):
        path = PurePosixPath('/' + raw.lstrip('/'))
        require('..' not in path.parts and path.is_relative_to(self.prefix), 'checkpoint path escapes namespace')
        return str(relative(path.relative_to(self.prefix).as_posix()))

    @contextmanager
    def file_members(self, capture, selected):
        require(capture == self.capture, 'checkpoint replay generation differs')
        rows = self.proof['entries']
        require(all(rows.get(name, {}).get('kind') == 'file' for name in selected),
                'checkpoint replay selector is not a canonical file')

        def members():
            seen = set()
            with self.archive.contents() as tar:
                for member in tar:
                    if not member.isfile() or member.name == 'payload/manifest.json':
                        continue
                    name = self.snapshots.get(member.name)
                    if name is None:
                        require(not member.name.startswith('payload/'), 'unknown checkpoint payload')
                        name = self.mapped(member.name)
                    require(name in rows, 'checkpoint member absent from authenticated index')
                    row = rows[name]
                    name = row['target'] if row['kind'] == 'hardlink' else name
                    if name in selected:
                        require(name not in seen and member.size == rows[name]['bytes'],
                                'checkpoint replay duplicate/size mismatch')
                        with tar.extractfile(member) as stream:
                            yield name, stream
                        seen.add(name)
            require(seen == set(selected), 'checkpoint omitted selected canonical files')

        iterator = members()
        try:
            yield iterator
            for _ in iterator:
                pass  # EOF authenticates the entire actual archive, even on partial consumption.
        finally:
            iterator.close()
