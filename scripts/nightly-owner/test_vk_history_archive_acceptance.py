import copy
import json
from pathlib import Path
import tempfile
import unittest

import vk_history_archive_acceptance as archive
import vk_history_compaction_probe as codec


class WholeSessionArchive(unittest.TestCase):
    def test_paginated_mode_rejects_rollout_only_even_with_pinned_manifest(self):
        files = {'sessions/rollout.jsonl': b'complete rollout'}
        required = {'native_rollout': 'sessions/rollout.jsonl'}
        with self.assertRaisesRegex(ValueError, 'consistent history database'):
            archive.seal(files, session_id='fixture', required=required, history_mode='paginated')
        raw, objects = archive.seal(files, session_id='fixture', required=required, history_mode='legacy')
        manifest = json.loads(raw)
        manifest['session']['history_mode'] = 'paginated'
        raw = archive.encoded(manifest)
        with self.assertRaisesRegex(ValueError, 'consistent history database'):
            archive.recover(raw, objects, expected_sha256=codec.digest(raw), session_id='fixture')

    def setUp(self):
        self.files = {'sessions/old/rollout.jsonl': b'old complete session\n',
                      'sessions/active/rollout.jsonl': b'first\nlast incomplete',
                      'vibe/process.jsonl': b'{"Stdout":"hello"}\n'}
        self.required = {'closed': 'sessions/old/rollout.jsonl', 'active': 'sessions/active/rollout.jsonl',
                         'process': 'vibe/process.jsonl'}
        self.raw, self.objects = archive.seal(self.files, session_id='fixture', required=self.required)
        self.pin = codec.digest(self.raw)

    def test_reader_only_after_complete_exact_restore_and_no_date_loss(self):
        with tempfile.TemporaryDirectory(prefix='vk-session-') as temp:
            def reader(home):
                for key, value in self.files.items():
                    self.assertEqual((home / key).read_bytes(), value)
                return 'existing reader consumed entire files'
            self.assertEqual(archive.hydrate(self.raw, self.objects, Path(temp) / 'new',
                expected_sha256=self.pin, session_id='fixture', reader=reader),
                'existing reader consumed entire files')

    def test_missing_corrupt_manifest_wrong_identity_never_calls_reader(self):
        with tempfile.TemporaryDirectory(prefix='vk-session-') as temp:
            destination = Path(temp) / 'new'
            def forbidden(_):
                self.fail('reader ran without a complete archive')
            bad_objects = dict(self.objects)
            bad_objects[next(iter(bad_objects))] = b'corrupt'
            for raw, objects, pin, session in (
                (self.raw, {}, self.pin, 'fixture'),
                (self.raw, bad_objects, self.pin, 'fixture'),
                (self.raw + b' ', self.objects, self.pin, 'fixture'),
                (self.raw, self.objects, self.pin, 'wrong')):
                with self.assertRaises(ValueError):
                    archive.hydrate(raw, objects, destination, expected_sha256=pin,
                                    session_id=session, reader=forbidden)
                self.assertFalse(destination.exists())

    def test_missing_reference_even_with_new_manifest_hash_rejected(self):
        row = json.loads(self.raw)
        row['session']['required']['missing'] = 'absent'
        raw = archive.encoded(row)
        with self.assertRaisesRegex(ValueError, 'reference'):
            archive.recover(raw, self.objects, expected_sha256=codec.digest(raw), session_id='fixture')

    def test_no_overwrite_symlink_ancestor_or_traversal(self):
        with tempfile.TemporaryDirectory(prefix='vk-session-') as temp:
            parent = Path(temp)
            (parent / 'existing').mkdir()
            (parent / 'alias').symlink_to(parent, target_is_directory=True)
            for dest in (parent / 'existing', parent / 'alias/new'):
                with self.assertRaises(OSError):
                    archive.hydrate(self.raw, self.objects, dest, expected_sha256=self.pin,
                                    session_id='fixture', reader=lambda _: self.fail('unsafe reader'))
            bad = json.loads(self.raw)
            bad['files']['../escape'] = bad['files'].pop('vibe/process.jsonl')
            raw = archive.encoded(bad)
            with self.assertRaises(ValueError):
                archive.hydrate(raw, self.objects, parent / 'new', expected_sha256=codec.digest(raw),
                                session_id='fixture', reader=lambda _: self.fail('unsafe reader'))
            self.assertFalse((parent / 'new').exists())

    def test_latest_closure_and_incremental_accounting_are_independent(self):
        versions = [copy.deepcopy(self.files)]
        for index in range(2):
            files = copy.deepcopy(versions[-1])
            files['sessions/active/rollout.jsonl'] += ('\nnew' + str(index)).encode()
            versions.append(files)
        measured = archive.compare(versions, session_id='fixture', required=self.required)
        self.assertEqual(measured['all_manifest_and_unique_object_zlib6_bytes'],
                         sum(r['new_transfer_with_manifest_bytes'] for r in measured['generations']))
        raw, objects = archive.seal(versions[-1], session_id='fixture', required=self.required)
        versions.clear()
        self.assertEqual(archive.recover(raw, objects, expected_sha256=codec.digest(raw), session_id='fixture')
                         ['sessions/old/rollout.jsonl'], b'old complete session\n')
        self.assertTrue(all(not r['parent_manifest_required'] for r in measured['generations']))


if __name__ == '__main__':
    unittest.main()
