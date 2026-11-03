import copy
import importlib.util
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('log_dedup', Path(__file__).with_name('log_dedup.py'))
dedup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dedup)


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='vk-log-dedup-test-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / 'source'
        self.source.mkdir()
        self.session = '12/12345678-1234-1234-1234-123456789abc/processes/'
        self.paths = [self.session + name + '.jsonl' for name in (
            '12345678-0000-0000-0000-000000000001',
            '12345678-0000-0000-0000-000000000002')]
        rng = random.Random(10)
        text = ''.join(rng.choice('abcdef0123456789 .') for _ in range(400_000))
        self.raw = (json.dumps({'Stdout': 'history — ✓\n' + text}) + '\n').encode()
        for relative in self.paths:
            path = self.source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(self.raw)
            path.with_suffix('.capture.json').write_text('{"capture_state":"closed"}\n')
        self.plan = dedup.scan(self.source, self.paths)
        self.archive = self.base / 'archive'

    def pack(self):
        dedup.pack(self.plan, self.archive)
        return self.archive / self.paths[0]

    def test_dedup_restore_exact_bytes_sidecars_and_source_identity(self):
        self.pack()
        self.assertTrue(dedup.verify_or_restore(self.archive)['verified'])
        restored = self.base / 'restored'
        dedup.verify_or_restore(self.archive, restored)
        for relative in self.paths:
            self.assertEqual((restored / relative).read_bytes(), self.raw)
            self.assertEqual((restored / relative).with_suffix('.capture.json').read_bytes(),
                             (self.source / relative).with_suffix('.capture.json').read_bytes())
        self.assertEqual(dedup.scan(self.source, self.paths), self.plan)
        self.assertGreaterEqual(self.plan['metrics']['duplicate_chunk_bytes'], len(self.raw))
        self.assertLess(self.plan['metrics']['archive_payload_bytes'], len(self.raw))

    def test_stale_plan_and_existing_destination_refused(self):
        path = self.source / self.paths[0]
        path.write_bytes(self.raw + b'new')
        with self.assertRaises(ValueError):
            dedup.pack(self.plan, self.archive)
        self.assertFalse(self.archive.exists())
        self.plan = dedup.scan(self.source, self.paths)
        self.archive.mkdir()
        with self.assertRaises(FileExistsError):
            dedup.pack(self.plan, self.archive)

    def test_pending_capture_never_sealed(self):
        (self.source / self.paths[0]).with_suffix('.capture.json').write_text('{"capture_state":"pending"}')
        self.plan = dedup.scan(self.source, self.paths)
        with self.assertRaises(ValueError):
            dedup.pack(self.plan, self.archive)
        self.assertFalse((self.archive / 'receipt.json').exists())

    def test_corruption_missing_object_and_sidecar_fail(self):
        path = self.pack()
        obj = next((path.parent / '.log-objects').iterdir())
        original = obj.read_bytes()
        obj.write_bytes(b'damaged')
        with self.assertRaises((OSError, ValueError)):
            dedup.verify_or_restore(self.archive)
        obj.unlink()
        with self.assertRaises(OSError):
            dedup.verify_or_restore(self.archive)
        obj.write_bytes(original)
        path.with_suffix('.capture.json').write_text('{}')
        with self.assertRaises(ValueError):
            dedup.verify_or_restore(self.archive)

    def test_truncated_gzip_cli_fails_without_payload_or_traceback(self):
        path = self.pack()
        obj = next((path.parent / '.log-objects').iterdir())
        obj.write_bytes(obj.read_bytes()[:-4])
        result = subprocess.run([sys.executable, str(Path(__file__).with_name('log_dedup.py')),
                                 'verify', '--root', str(self.archive)], capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b'')
        self.assertNotIn(b'Traceback', result.stderr)
        self.assertNotIn(self.raw[:20], result.stderr)

    def test_bad_references_oversized_chunks_and_bad_full_hash(self):
        path = self.pack()
        data = dedup.load_manifest(path)
        for value in ('../outside', '0' * 64):
            changed = copy.deepcopy(data)
            changed['chunks'][0]['sha256'] = value
            path.write_bytes(dedup.encode(changed))
            with self.assertRaises((OSError, ValueError)):
                dedup.reconstruct(path)
        changed = copy.deepcopy(data)
        changed['sha256'] = '0' * 64
        path.write_bytes(dedup.encode(changed))
        with self.assertRaises(ValueError):
            dedup.reconstruct(path)
        changed['chunks'][0]['bytes'] = dedup.MAX_CHUNK + 1
        path.write_bytes(dedup.encode(changed))
        with self.assertRaises(ValueError):
            dedup.reconstruct(path)

    def test_symlinks_traversal_and_overlapping_destinations_refused(self):
        path = self.source / self.paths[0]
        elsewhere = self.base / 'elsewhere'
        path.rename(elsewhere)
        path.symlink_to(elsewhere)
        with self.assertRaises(ValueError):
            dedup.scan(self.source, self.paths)
        with self.assertRaises(ValueError):
            dedup.safe_path(self.source, '../elsewhere')
        with self.assertRaises(ValueError):
            dedup.create_destination(self.source / 'nested', self.source)
        with self.assertRaises(ValueError):
            dedup.create_destination(self.base, self.source)

    def test_empty_truncated_utf8_and_duplicate_records_are_preserved(self):
        # Storage never repairs a broken historical capture or removes intentional repetition.
        for data in (b'', b'{"Stdout":"partial', b'\xe2\x9c', b'{}\n{}\n'):
            with self.subTest(data=data):
                path = self.source / self.paths[0]
                path.write_bytes(data)
                plan = dedup.scan(self.source, [self.paths[0]])
                target = self.base / ('output-' + str(len(data)))
                dedup.pack(plan, target)
                restored = self.base / ('restore-' + str(len(data)))
                dedup.verify_or_restore(target, restored)
                self.assertEqual((restored / self.paths[0]).read_bytes(), data)

    def test_mid_pack_change_has_no_sealed_receipt(self):
        original = dedup.manifest_for
        calls = 0
        def changed(path, objects, output=None):
            nonlocal calls
            result = original(path, objects, output)
            if output is not None:
                calls += 1
                if calls == 1:
                    path.write_bytes(self.raw + b'new delta')
            return result
        with patch.object(dedup, 'manifest_for', changed):
            with self.assertRaises(ValueError):
                dedup.pack(self.plan, self.archive)
        self.assertFalse((self.archive / 'receipt.json').exists())

    def test_no_cross_session_object_dependency(self):
        second = self.paths[0].replace('12345678-1234', '12345679-1234')
        target = self.source / second
        target.parent.mkdir(parents=True)
        target.write_bytes(self.raw)
        result = dedup.scan(self.source, [self.paths[0], second])
        self.assertEqual(result['metrics']['duplicate_chunk_bytes'], 0)


if __name__ == '__main__':
    unittest.main()
