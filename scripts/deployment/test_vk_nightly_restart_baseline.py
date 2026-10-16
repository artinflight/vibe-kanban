"""Tiny real SQLite/object/restore fixtures; no live B or controller effects."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from vk_change_journal import scope
from vk_nightly_generation import NightlyStore, encoded, object_blocks
from vk_nightly_restart_baseline import capture_binding, capture_journal, held_baseline, FORMAT
from vk_prep_common import identity


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='vk-nightly-contract-')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name);self.root = self.base / 'nightly';self.root.mkdir()
        self.plan = {'sources': ['/fixture'], 'sqlite_snapshots': ['/fixture/db.sqlite']}
        self.store = NightlyStore(self.root, identity(scope(self.plan)), lambda: self.base,
            independent_readback=self.readback, object_encoding='zlib-1-v1')
        self.store.enroll_empty();self.restores = [];self.capture_no = 0
        self.result = {'schema': 1, 'passed': True, 'parent': None, 'online_preparation': True,
            'plan_sha256': identity(self.plan), 'scope_sha256': identity(scope(self.plan)),
            'journal_instance': 'original-owner-instance', 'journal_sequence': 12,
            'databases': ['/fixture/db.sqlite']}

    def image(self, text):
        source = self.base / ('source-' + str(self.capture_no) + '.sqlite')
        self.capture_no += 1
        with sqlite3.connect(source) as db:
            db.execute('CREATE TABLE work(value TEXT)');db.execute('INSERT INTO work VALUES(?)', [text])
        target = self.base / ('snapshot-' + str(self.capture_no) + '.sqlite')
        with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:src.backup(dst)
        return target.read_bytes()

    def file(self, data):
        return {'kind': 'file', 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                'mode': 0o600, 'uid': os.getuid(), 'gid': os.getgid(), 'mtime_ns': 123, 'xattrs': {}}

    def readback(self, folder, manifest):
        # Actually restore and read every object and check SQLite in this tiny
        # isolated filesystem. The label models the separate native B callback;
        # this is not claimed as a host whole-plan physical B acceptance.
        target = self.base / ('restore-' + str(len(self.restores)));target.mkdir()
        for key, row in manifest['entries'].items():
            if row['kind'] != 'file':continue
            output = target / key;output.parent.mkdir(parents=True, exist_ok=True)
            with output.open('xb') as sink:
                for b in object_blocks(folder / 'objects' / row['sha256'], row['sha256'], row['bytes'], manifest.get('object_encoding')):sink.write(b)
            self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(), row['sha256'])
        with sqlite3.connect((target / 'fixture/db.sqlite').as_uri() + '?mode=ro&immutable=1', uri=True) as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchall(), [('ok',)])
        self.restores.append(target)
        return {'physical_b_verified': True, 'generation': manifest['generation'],
                'scope_sha256': manifest['scope_sha256'], 'manifest_sha256': hashlib.sha256(encoded(manifest)).hexdigest()}

    def advance(self, text='before', previous=None):
        image = self.image(text);note = b'unchanged user work'
        rows = {'fixture/db.sqlite': self.file(image), 'fixture/note': self.file(note)}
        self.result['sqlite_snapshots'] = {'/fixture/db.sqlite': {'path': 'sqlite/image', 'sha256': rows['fixture/db.sqlite']['sha256']}}
        proof = {'full_current_state': True, 'entries': rows}
        binding = capture_binding(self.result, self.plan, '/', proof)
        changes = [('fixture/db.sqlite', rows['fixture/db.sqlite'], io.BytesIO(image)),
                   ('fixture/note', rows['fixture/note'], None if previous else io.BytesIO(note))]
        return self.store.advance(changes, (), expected_previous=previous, reserve_bytes=1024**2,
            retention_adopted=previous is not None, capture_context={'restart_capture': binding})

    def open(self, **kwargs):
        m = self.store.current()
        return held_baseline(self.store, self.plan, generation=m['generation'],
            manifest_sha256=hashlib.sha256(encoded(m)).hexdigest(), physical_readback=kwargs.get('readback', self.readback))

    def journal(self, since):
        self.assertEqual(since, 12)
        return {'ready': True, 'errors': [], 'scope_sha256': identity(scope(self.plan)),
                'instance': 'original-owner-instance', 'sequence': 15, 'changed': ['/fixture/changed-during-capture']}

    def test_physical_restore_and_start_sequence_catchup_under_real_lease(self):
        self.advance()
        with self.open() as handle:
            value = handle.catchup(self.journal)
            self.assertEqual(value['format'], FORMAT)
            self.assertEqual(value['watched']['changed'], ['/fixture/changed-during-capture'])
            self.assertFalse(value['writer_fence_verified']);self.assertFalse(value['activation_authorized'])
            self.assertFalse(value['snapshot_reuse_allowed'])
            self.assertTrue(value['whole_plan_restore_acceptance_required'])
            self.assertEqual(b''.join(handle.blocks('fixture/note')), b'unchanged user work')
            with self.assertRaises(BlockingIOError):self.advance('blocked', handle.manifest['generation'])
        with self.assertRaisesRegex(ValueError, 'lease has ended'):handle.catchup(self.journal)

    def test_second_current_physically_recovers_without_retired_first(self):
        first = self.advance();self.advance('latest', first['generation'])
        self.assertFalse((self.root / first['generation']).exists())
        with self.open() as handle:handle.catchup(self.journal)
        with sqlite3.connect(self.restores[-1] / 'fixture/db.sqlite') as db:
            self.assertEqual(db.execute('SELECT value FROM work').fetchall(), [('latest',)])
        self.assertEqual(len(list(self.root.glob('generation-*'))), 1)

    def test_new_instance_overflow_wrong_scope_and_backwards_sequence_fail(self):
        self.advance()
        changes = [{'instance': 'new'}, {'errors': [{'overflow': 16384}]}, {'scope_sha256': '0'*64},
                   {'sequence': 11}, {'sequence': True}, {'ready': False}]
        with self.open() as handle:
            for fields in changes:
                with self.subTest(fields=fields), self.assertRaisesRegex(ValueError, 'reconciliation required'):
                    handle.catchup(lambda since: {**self.journal(since), **fields})
        self.assertIsNotNone(self.store.current())

    def test_wrong_physical_receipt_is_rejected(self):
        self.advance()
        with self.assertRaisesRegex(ValueError, 'physical readback'), self.open(readback=lambda *_: {'physical_b_verified': True}):pass

    def test_unknown_or_dependent_manifest_and_changed_plan_fail(self):
        self.advance()
        for changes in [{'parent': {'archive': 'retained-full.tar.zst'}}, {'producer': 'unknown'},
                        {'capture_context': {}}]:
            original = self.store.current();changed = {**original, **changes}
            with patch.object(self.store, 'current', return_value=changed):
                with self.assertRaises(ValueError), self.open():pass
        self.plan['sources'].append('/other')
        with self.assertRaises(ValueError), self.open():pass

    def test_pinned_generation_and_digest_cannot_be_substituted(self):
        self.advance();m = self.store.current()
        for generation, digest in [('generation-'+'f'*32, hashlib.sha256(encoded(m)).hexdigest()),
                                   (m['generation'], '0'*64)]:
            with self.assertRaises(ValueError), held_baseline(self.store, self.plan,
                generation=generation, manifest_sha256=digest, physical_readback=self.readback):pass

    def test_corrupt_current_object_fails_before_handoff(self):
        self.advance();m = self.store.current();row = m['entries']['fixture/note']
        (self.root / m['generation'] / 'objects' / row['sha256']).write_bytes(b'corrupt')
        with self.assertRaises((ValueError, __import__('zlib').error)), self.open():pass

    def test_capture_requires_complete_consistent_images_not_partial_chain(self):
        self.advance();m = self.store.current();proof = {'full_current_state': True, 'entries': m['entries']}
        for changes in [{'parent': {'archive': 'full'}}, {'schema': 2}, {'passed': False},
                        {'sqlite_snapshots': {}}, {'journal_sequence': True}, {'plan_sha256': '0'*64}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                capture_binding({**self.result, **changes}, self.plan, '/', proof)

    def test_external_journal_lifecycle_stays_with_owner(self):
        calls = []
        def reader(n):calls.append(n);return self.journal(12)
        with capture_journal(self.plan, reader) as actual:self.assertIs(actual, reader)
        self.assertEqual(calls, [0])

    def test_private_watcher_closes_on_capture_error_without_closing_external_reader(self):
        with patch('vk_change_journal.Journal') as constructor:
            owned = constructor.return_value;owned.report.return_value = self.journal(12)
            with self.assertRaisesRegex(RuntimeError, 'capture failure'):
                with capture_journal(self.plan):raise RuntimeError('capture failure')
            owned.close.assert_called_once()
        with patch('vk_change_journal.Journal') as constructor:
            reader = __import__('unittest.mock', fromlist=['Mock']).Mock(return_value=self.journal(12))
            with self.assertRaisesRegex(RuntimeError, 'capture failure'):
                with capture_journal(self.plan, reader):raise RuntimeError('capture failure')
            reader.close.assert_not_called();constructor.assert_not_called()

    def test_invalid_external_journal_never_starts_an_owned_watcher(self):
        with patch('vk_change_journal.Journal') as constructor:
            with self.assertRaises(ValueError), capture_journal(self.plan, lambda _: {'ready': False}):pass
            constructor.assert_not_called()


# Real existing direct-capture -> archive-index -> nightly -> restart contract.
# All effects are confined to the established tiny contract-test directory.
import test_vk_candidate_direct_b as archive_fixtures
from vk_nightly_archive_index import NightlyArchiveProvider
from vk_nightly_generation import advance_verified_capture


class ArchiveBridge(archive_fixtures.ContractTests):
    def test_actual_archive_capture_preserves_restart_anchor_and_physical_sqlite(self):
        result, journal = self.capture('restart-baseline')
        plan = {'sources': [str(self.inc)], 'sqlite_snapshots': [str(self.db)],
                'excluded_rebuildable_directories': []}
        provider = NightlyArchiveProvider(self.scope, ['home/state/state.sqlite'],
                                         archive_factory=self.factory, fixture_only=True)
        provider.register('nightly', result, identity(plan), identity(scope(plan)), self.inc,
                          origin_root_binding='nightly-fixture')
        proof = provider.verify('nightly')
        proof['restart_capture'] = capture_binding(result, plan, str(self.inc), proof)
        root = self.root / 'restart-nightly';root.mkdir()
        def physical(folder, manifest):
            output = self.root / ('recovered-' + str(len(list(self.root.glob('recovered-*')))))
            output.mkdir()
            for key, row in manifest['entries'].items():
                if row['kind'] != 'file':continue
                target = output / key;target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as sink:
                    for block in object_blocks(folder / 'objects' / row['sha256'], row['sha256'], row['bytes']):sink.write(block)
            with sqlite3.connect(output / 'home/state/state.sqlite') as db:
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchall(), [('ok',)])
                self.assertEqual(db.execute('SELECT value FROM retained').fetchall(), [('before',)])
            return {'physical_b_verified': True, 'generation': manifest['generation'],
                    'scope_sha256': manifest['scope_sha256'], 'manifest_sha256': hashlib.sha256(encoded(manifest)).hexdigest()}
        store = NightlyStore(root, self.scope, lambda: self.root, independent_readback=physical)
        store.enroll_empty()
        advance_verified_capture(store, provider, 'nightly', reserve_bytes=1024**2, verified_proof=proof)
        current = store.current()
        (self.inc / 'home/state/note').write_bytes(b'work after nightly capture')
        with held_baseline(store, plan, generation=current['generation'],
                manifest_sha256=hashlib.sha256(encoded(current)).hexdigest(), physical_readback=physical) as handle:
            catchup = handle.catchup(journal.report)
            self.assertIn(str(self.inc / 'home/state/note'), catchup['watched']['changed'])
            self.assertEqual(catchup['journal_sequence'], result['journal_sequence'])
            self.assertEqual(b''.join(handle.blocks('home/state/note')), b'original dirty work')


for inherited in dir(ArchiveBridge):
    if inherited.startswith('test_') and inherited not in ArchiveBridge.__dict__:
        setattr(ArchiveBridge, inherited, None)


if __name__ == '__main__':unittest.main()
