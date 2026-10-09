"""Real archive replay with derived-index fixtures; no SSH or production access."""
import hashlib
import json
import unittest

from test_vk_candidate_direct_b import ContractTests
from vk_candidate_generation import Blocked, digest
from vk_candidate_verified_checkpoint import VerifiedCheckpointProvider


class CachedCheckpointTests(ContractTests):
    def checkpoint(self):
        descriptor, _ = self.capture('cached')
        proof = self.provider.verify('cached')
        path = self.root / 'verified-index.json'
        raw = json.dumps(proof).encode()
        path.write_bytes(raw)
        receipt = {'desktop_verified': True, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        return descriptor, proof, path, receipt

    def reader(self, descriptor, proof, path, receipt):
        return VerifiedCheckpointProvider(descriptor, path, receipt, proof['manifest_sha256'],
            fixture_only=True, archive_factory=self.factory, source_prefix=str(self.inc))

    def test_cached_checkpoint_replays_canonical_hardlinks_and_SQLite(self):
        descriptor, proof, path, receipt = self.checkpoint()
        reader = self.reader(descriptor, proof, path, receipt)
        self.assertEqual(reader.verify('cached')['manifest_sha256'], digest(proof['entries']))
        wanted = {name for name, row in proof['entries'].items() if row['kind'] == 'file'}
        found = {}
        with reader.file_members('cached', wanted) as members:
            for name, stream in members:
                found[name] = hashlib.file_digest(stream, 'sha256').hexdigest()
        self.assertEqual(found, {name: proof['entries'][name]['sha256'] for name in wanted})

    def test_cached_index_tamper_or_missing_preservation_blocks(self):
        descriptor, proof, path, receipt = self.checkpoint()
        with self.assertRaisesRegex(Blocked, 'preserved on B'):
            self.reader(descriptor, proof, path, {**receipt, 'desktop_verified': False})
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaisesRegex(Blocked, 'bytes differ'):
            self.reader(descriptor, proof, path, receipt)

    def test_cached_proof_never_authenticates_a_new_capture_or_changed_archive(self):
        descriptor, proof, path, receipt = self.checkpoint()
        reader = self.reader(descriptor, proof, path, receipt)
        with self.assertRaisesRegex(Blocked, 'another generation'):
            reader.verify('final')
        archive = self.store / descriptor['archive']
        with archive.open('ab') as out:
            out.write(b'changed archived evidence fixture')
        with self.assertRaises(ValueError):
            reader.verify('cached')
        with self.assertRaises(ValueError):
            with reader.file_members('cached', set()) as members:
                list(members)

    def test_delta_or_nonfixture_local_reader_cannot_use_checkpoint_cache(self):
        descriptor, proof, path, receipt = self.checkpoint()
        with self.assertRaisesRegex(Blocked, 'complete accepted checkpoint'):
            self.reader({**descriptor, 'parent': {}}, proof, path, receipt)
        with self.assertRaisesRegex(Blocked, 'fixture mode'):
            VerifiedCheckpointProvider(descriptor, path, receipt, proof['manifest_sha256'],
                archive_factory=self.factory)


if __name__ == '__main__':
    names = ('test_cached_checkpoint_replays_canonical_hardlinks_and_SQLite',
             'test_cached_index_tamper_or_missing_preservation_blocks',
             'test_cached_proof_never_authenticates_a_new_capture_or_changed_archive',
             'test_delta_or_nonfixture_local_reader_cannot_use_checkpoint_cache')
    result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(CachedCheckpointTests(n) for n in names))
    raise SystemExit(not result.wasSuccessful())
