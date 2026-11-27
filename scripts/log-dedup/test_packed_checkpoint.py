from pathlib import Path
import hashlib
import tempfile
import unittest

import packed_recovery as recovery


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        source = self.root / 'source'
        source.write_bytes(b'preserved history')
        self.row = dict(path=str(source), bytes=source.stat().st_size,
                        sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        self.calls = []

    def capture(self, paths, size):
        self.calls.append('capture')
        return dict(manifest=dict(files=[dict(source=paths[0], member=dict(
            bytes=size, sha256=self.row['sha256']))]))

    def restore(self, receipt):
        self.calls.append('restore')
        return dict(checkpoint=receipt, actual_independent_normal_restore=dict(
            independent_owner_controls_restore_verified=True, files=1,
            raw_bytes=self.row['bytes']))

    def run_checkpoint(self, **overrides):
        args = dict(guard=lambda: None, capture=self.capture, restore=self.restore,
                    progress=lambda *args: self.calls.append('progress'))
        args.update(overrides)
        return recovery.checkpoint_once(self.root, 'PACK_0', [self.row], **args)

    def test_invalid_name_refuses_before_any_side_effect(self):
        with self.assertRaisesRegex(ValueError, 'checkpoint name'):
            recovery.checkpoint_once(
                self.root, 'SOFTWARE_main_0', [self.row],
                guard=lambda: self.calls.append('guard'), capture=self.capture,
                restore=self.restore, progress=lambda *args: None)
        self.assertEqual(self.calls, [])
        self.assertEqual([p.name for p in self.root.iterdir()], ['source'])

    def test_software_part_names_pass_preflight(self):
        for variant in ('main', 'fallback', 'protected'):
            for offset in (0, 16 * 1024**2, 128 * 1024**2):
                name = f'SOFTWARE_{variant.upper()}_{offset}'
                self.assertEqual(recovery.validate_checkpoint_name(name), name)
        for invalid in ('lowercase', 'X' * 81, '../FILE', None):
            with self.assertRaises(ValueError):
                recovery.validate_checkpoint_name(invalid)

    def test_exact_restore_and_no_repeat(self):
        self.run_checkpoint()
        self.assertEqual(self.calls, ['capture', 'restore', 'progress'])
        with self.assertRaises(FileExistsError): self.run_checkpoint()
        self.assertEqual(self.calls.count('capture'), 1)
        self.assertEqual(Path(self.row['path']).read_bytes(), b'preserved history')

    def test_uncertain_capture_retains_intent_and_cannot_retry(self):
        def uncertain(*args):
            self.calls.append('capture')
            raise TimeoutError('uncertain remote capture')
        with self.assertRaises(TimeoutError): self.run_checkpoint(capture=uncertain)
        self.assertTrue((self.root / 'PACK_0_INTENT.private.json').exists())
        with self.assertRaises(FileExistsError): self.run_checkpoint()
        self.assertEqual(self.calls, ['capture'])

    def test_failed_restore_retains_captured_checkpoint(self):
        def failed(*args): raise ValueError('restore refused')
        with self.assertRaises(ValueError): self.run_checkpoint(restore=failed)
        self.assertTrue((self.root / 'PACK_0_CAPTURE.private.json').exists())
        self.assertFalse((self.root / 'PACK_0_VERIFIED.private.json').exists())
        with self.assertRaises(FileExistsError): self.run_checkpoint()

    def test_wrong_member_refused_before_restore(self):
        def wrong(paths, size):
            result = self.capture(paths, size)
            result['manifest']['files'][0]['member']['sha256'] = '0' * 64
            return result
        with self.assertRaises(ValueError): self.run_checkpoint(capture=wrong)
        self.assertEqual(self.calls, ['capture'])

    def test_changed_source_refused_before_intent(self):
        Path(self.row['path']).write_bytes(b'new history')
        with self.assertRaises(ValueError): self.run_checkpoint()
        self.assertEqual(self.calls, [])
        self.assertFalse((self.root / 'PACK_0_INTENT.private.json').exists())

    def test_bounds_and_duplicate_members(self):
        rows = [dict(path=str(i), bytes=3) for i in range(70)]
        self.assertEqual([len(x) for x in recovery.batches(rows, maximum=6)], [2] * 35)
        self.assertEqual([len(x) for x in recovery.batches(rows)], [64, 6])
        with self.assertRaises(ValueError): list(recovery.batches([rows[0], rows[0]]))
        with self.assertRaises(ValueError): list(recovery.batches([dict(path='x', bytes=7)], maximum=6))
        receipt = self.capture([self.row['path']], self.row['bytes'])
        receipt['manifest']['files'] *= 2
        with self.assertRaises(ValueError): recovery.verify_scope(receipt, [self.row])


if __name__ == '__main__':
    unittest.main()
