"""Nightly cold selection on real SQLite/custody, with explicitly fixture B."""
from contextlib import closing
import json
from pathlib import Path
import shutil
import unittest
import uuid

from catalog import Conflict, identity
from custody import Busy, Custody
from nightly_selection import Selection, SnapshotCatalog, records, verify_recovery
from lifecycle import digest
import test_lifecycle as lifecycle_fixtures


class NightlySelectionTests(unittest.TestCase):
    def setUp(self):
        self.f = lifecycle_fixtures.LifecycleTests(methodName='test_real_move_restore_preserves_history_code_empty_symlink_and_exact_input')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.f.c.db.execute('PRAGMA journal_mode=WAL')
        self.f.b.describes = 0
        def describe(locator, expected):
            self.f.b.describes += 1
            with self.f.b.recall(locator, expected) as reader:
                return reader.manifest
        self.f.b.describe = describe
        self.required = self.f.root / 'shared-attachment'
        self.required.write_bytes(b'shared retained attachment')
        self.manifest = self.f.prepare()
        self.f.life.retire()
        self.f.custody.close()

    def select(self, **kwargs):
        return Selection(self.f.c.db.execute('PRAGMA database_list').fetchone()[2],
            self.f.root / 'locks', self.f.b, self.f.authority,
            required_sources=kwargs.get('required_sources', [str(self.required)]))

    def snapshot(self, selection):
        return selection.snapshot_sql(self.f.root / 'nightly.sqlite', maximum_bytes=1024**2, reserve_bytes=0)

    def test_current_sql_cold_reference_and_shared_payload_are_one_selection(self):
        with self.select() as selection:
            point = self.snapshot(selection)
            descriptor = selection.descriptor()
            included, cold = selection.partition([str(self.required), str(self.f.root), self.f.roots[0] + '/log'])
            self.assertEqual(included, [str(self.required), str(self.f.root)])
            self.assertEqual(cold, [self.f.roots[0] + '/log'])
            self.assertEqual(len(descriptor['cold_generations']), 1)
            self.assertEqual(descriptor['cold_generations'][0]['manifest'], self.manifest)
            self.assertEqual(self.f.b.captures, 1)
            self.assertEqual(self.f.b.describes, 1)
            with closing(SnapshotCatalog(point['image'])) as copied:
                self.assertEqual(records(copied), descriptor['cold_generations'])
            self.assertTrue(self.required.exists())
        with self.assertRaises(Conflict): selection.include(str(self.required))

    def test_independent_recovery_requires_sql_cold_catalog_and_external_shared_scope(self):
        with self.select() as selection:
            point = self.snapshot(selection)
            descriptor = selection.descriptor()
        restored = self.f.root / 'independently-restored.sqlite'
        shutil.copyfile(point['image'], restored)
        required = descriptor['required_active_sources']
        result = verify_recovery(descriptor, digest(descriptor), restored, self.f.b,
                                 required_sources=required, included_sources=required)
        self.assertEqual(result['cold_generations'], 1)
        self.assertEqual(result['body_bytes_recaptured'], 0)
        with self.assertRaisesRegex(ValueError, 'shared dependencies'):
            verify_recovery(descriptor, digest(descriptor), restored, self.f.b,
                            required_sources=required, included_sources=[point['source']])
        wrong = json.loads(json.dumps(descriptor))
        wrong['excluded_roots'] = {}
        with self.assertRaisesRegex(Conflict, 'omissions differ'):
            verify_recovery(wrong, digest(wrong), restored, self.f.b,
                            required_sources=required, included_sources=required)
        with self.assertRaisesRegex(ValueError, 'descriptor'):
            verify_recovery(descriptor, '0' * 64, restored, self.f.b,
                            required_sources=required, included_sources=required)
        self.assertEqual(self.f.b.captures, 1)

    def test_message_invalidates_exclusion_while_restore_waits_for_custody(self):
        with self.select() as selection:
            self.snapshot(selection)
            request = self.f.retain()
            with self.assertRaises(Conflict): selection.descriptor()
            with self.assertRaises(Conflict): selection.include(self.f.roots[0] + '/log')
            with self.assertRaises(Busy): Custody(self.f.root / 'locks', self.f.w, exclusive=True)
            row = self.f.c.db.execute('SELECT payload FROM workspace_archive_inputs WHERE request_id=?',
                                     (identity(request),)).fetchone()
            self.assertEqual(json.loads(row[0]), self.f.payload)
        with Custody(self.f.root / 'locks', self.f.w, exclusive=True):
            pass
        with self.select() as next_selection:
            self.assertEqual(next_selection.references, [])
            self.assertTrue(next_selection.include(self.f.roots[0] + '/log'))

    def test_history_read_intent_invalidates_exclusion_before_physical_restore(self):
        with self.select() as selection:
            self.f.c.db.execute('INSERT INTO workspace_archive_reads(workspace_id) VALUES(?)', (identity(self.f.w),))
            with self.assertRaises(Conflict): selection.check()

    def test_reappeared_source_or_alias_is_not_skipped(self):
        with self.select() as selection:
            Path(self.f.roots[0]).mkdir()
            with self.assertRaises(Conflict): selection.include(self.f.roots[0] + '/new-log')

    def test_generation_change_during_sql_capture_leaves_image_but_no_accepted_selection(self):
        with self.select() as selection:
            original = selection.check
            count = 0
            def interrupt():
                nonlocal count
                count += 1
                if count == 2:
                    self.f.retain()
                return original()
            selection.check = interrupt
            with self.assertRaises(Conflict): self.snapshot(selection)
            self.assertTrue((self.f.root / 'nightly.sqlite').exists())
            self.assertIsNone(selection.sql)

    def test_normal_b_metadata_reopen_does_not_hold_live_sql_transaction(self):
        self.f.c.db.execute('PRAGMA journal_mode=DELETE')
        describe = self.f.b.describe
        def concurrent_write(locator, expected):
            # A held read transaction would block this commit even with no
            # archive-generation change. B I/O must run outside that transaction.
            self.f.c.db.execute('CREATE TABLE fixture_concurrent_progress(value INTEGER)')
            self.f.c.db.execute('INSERT INTO fixture_concurrent_progress VALUES(1)')
            return describe(locator, expected)
        self.f.b.describe = concurrent_write
        with self.select() as selection:
            self.assertEqual(len(selection.references), 1)
        self.assertEqual(self.f.c.db.execute('SELECT value FROM fixture_concurrent_progress').fetchone()[0], 1)

    def test_b_offline_preserves_existing_recovery_and_never_grants_exclusion(self):
        self.f.b.offline = True
        with self.assertRaises(OSError):
            with self.select(): pass
        self.assertEqual(self.f.c.state(self.f.w)['phase'], 'cold')
        self.assertEqual(self.f.b.captures, 1)
        with Custody(self.f.root / 'locks', self.f.w, exclusive=True): pass

    def test_sql_and_required_shared_sources_cannot_be_excluded(self):
        with self.assertRaises(Conflict):
            with self.select(required_sources=[self.f.roots[0] + '/required']): pass

    def test_sql_bound_and_existing_destination_are_preserved(self):
        with self.select() as selection:
            target = self.f.root / 'nightly.sqlite'
            with self.assertRaises(OSError):
                selection.snapshot_sql(target, maximum_bytes=1, reserve_bytes=0)
            target.write_bytes(b'preserve interrupted result')
            with self.assertRaises(FileExistsError): self.snapshot(selection)
            self.assertEqual(target.read_bytes(), b'preserve interrupted result')

    def test_same_length_sql_mutation_invalidates_descriptor(self):
        with self.select() as selection:
            self.snapshot(selection)
            target = self.f.root / 'nightly.sqlite'
            with target.open('r+b') as stream:
                stream.write(b'corrupt header!!')
            with self.assertRaises(Conflict): selection.descriptor()

    def test_noncurrent_archived_generation_is_captured_normally(self):
        self.f.c.db.execute('UPDATE workspace_archive_requests SET request_version=request_version+1')
        with self.select() as selection:
            self.assertEqual(selection.references, [])
            self.assertTrue(selection.include(self.f.roots[0] + '/log'))
            self.assertEqual(self.f.b.describes, 0)


if __name__ == '__main__': unittest.main()
