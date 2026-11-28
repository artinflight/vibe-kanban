import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from vk_nightly_journal_store import JournalStore, canonical


class DurableJournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='nightly-durable-journal-')
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'journal.sqlite'
        self.binding = dict(instance='original-epoch', scope_sha256='a'*64,
                            plan_sha256='b'*64, observer=dict(PID=1, start_ticks=12, fd=3))

    def held(self, **kw):
        return JournalStore.held(self.path, binding=self.binding, start=10, **kw)

    def raw(self, end=12, **updates):
        return canonical(dict(instance=self.binding['instance'], scope_sha256='a'*64,
                              sequence=end, ready=True, errors=[], changed=['/source/a'],
                              events={'/source/a': 8}, **{}) | updates)

    def append(self, store, since=10, **updates):
        raw = self.raw(**updates)
        return store.append(since=since, raw=raw, expected_sha256=hashlib.sha256(raw).hexdigest())

    def test_restart_resumes_exact_cursor_without_duplicate_batch(self):
        with self.held(create=True) as s:
            self.assertFalse(self.append(s)['already_committed'])
        with self.held() as s:
            self.assertEqual(s.check(), 12)
            self.assertTrue(self.append(s)['already_committed'])
            self.assertEqual(s.connection.execute('select count(*) from batches').fetchone()[0], 1)
            self.append(s, since=12, end=14, changed=['/source/b'], events={'/source/b': 2})
            self.assertEqual(s.report(10)['changed'], ['/source/a', '/source/b'])
            self.assertEqual(s.report(12)['changed'], ['/source/b'])
            self.assertFalse(s.report(12)['baseline_accepted'])

    def test_interior_cursor_overselects_without_source_walk_stat_or_hash(self):
        with self.held(create=True) as s:
            self.append(s)
            with patch('os.walk', side_effect=AssertionError('source scan forbidden')):
                self.assertEqual(s.report(11)['changed'], ['/source/a'])

    def test_idle_reports_are_durable_but_empty_store_is_not_ready(self):
        with self.held(create=True) as s:
            self.assertFalse(s.report(10)['ready'])
            self.append(s, end=10, changed=[], events={})
            self.assertTrue(s.report(10)['ready'])

    def test_overflow_and_enrollment_errors_persist_across_clean_later_reports(self):
        for error in ({'coverage_lost': 16384}, {'watch_failed': '/source/x', 'errno': 2}):
            with tempfile.TemporaryDirectory(dir=self.tmp.name) as folder:
                self.path = Path(folder)/'j.sqlite'
                with self.held(create=True) as s:
                    self.append(s, ready=False, errors=[error])
                    self.append(s, since=12, end=14, changed=[], events={})
                    result = s.report(12)
                    self.assertFalse(result['ready']); self.assertIn(error, result['errors'])

    def test_historical_gap_not_closed_by_raw_observation_ready(self):
        with self.held(create=True) as s:
            self.append(s, coverage_gap=dict(continuity_proven=False), observation_ready=True)
            self.assertFalse(s.report(10)['ready'])

    def test_observer_epoch_scope_cursor_and_unknown_future_refused(self):
        with self.held(create=True) as s:
            self.append(s)
            for updates in (dict(instance='replacement'), dict(scope_sha256='c'*64), dict(end=11)):
                with self.assertRaises(ValueError): self.append(s, since=12, **updates)
            with self.assertRaises(ValueError): self.append(s, since=11, end=14)
            for since in (9, 13, True):
                with self.assertRaises(ValueError): s.report(since)
            self.assertEqual(s.check(), 12)

    def test_incomplete_or_unauthenticated_reports_never_advance_cursor(self):
        with self.held(create=True) as s:
            for raw in (b'{"sequence":', self.raw()):
                with self.assertRaises(ValueError): s.append(since=10, raw=raw, expected_sha256='0'*64)
            self.assertEqual(s.check(), 10)

    def test_missing_event_duplicate_path_traversal_and_negative_mask_refused(self):
        with self.held(create=True) as s:
            for kw in (dict(events={}), dict(changed=['/source/a']*2),
                       dict(changed=['/source/../a'], events={'/source/../a': 8}),
                       dict(events={'/source/a': -1}), dict(end=10)):
                with self.assertRaises(ValueError): self.append(s, **kw)
            self.assertEqual(s.check(), 10)

    def test_transaction_failure_preserves_committed_cursor_and_batches(self):
        with self.held(create=True) as s:
            self.append(s)
            s.connection.execute("create trigger fail before update on metadata begin select raise(abort,'simulated interrupted commit'); end")
            with self.assertRaises(sqlite3.IntegrityError): self.append(s, since=12, end=14)
            self.assertEqual(s.check(), 12)
            self.assertEqual(s.connection.execute('select count(*) from batches').fetchone()[0], 1)
            self.assertTrue(s.report(10)['ready'])

    def test_batch_tampering_and_missing_committed_batch_refused(self):
        with self.held(create=True) as s:
            self.append(s)
            s.connection.execute("update batches set raw=x'7b7d'")
            with self.assertRaises(ValueError): s.report(10)
            s.connection.execute('delete from batches')
            with self.assertRaises(ValueError): s.report(10)

    def test_path_substitution_and_parallel_collector_refused(self):
        with self.held(create=True) as s:
            with self.assertRaises(BlockingIOError):
                with self.held(): pass
            self.path.rename(self.path.with_suffix('.retained'))
            self.path.write_bytes(b'replacement')
            with self.assertRaises(ValueError): s.check()

    def test_create_collision_symlink_and_binding_substitution_refused(self):
        with self.held(create=True): pass
        with self.assertRaises(FileExistsError):
            with self.held(create=True): pass
        changed = copy.deepcopy(self.binding); changed['observer']['start_ticks'] += 1
        with self.assertRaises(ValueError):
            with JournalStore.held(self.path, binding=changed, start=10): pass
        link = self.path.with_suffix('.link'); link.symlink_to(self.path)
        with self.assertRaises(OSError):
            with JournalStore.held(link, binding=self.binding, start=10): pass

    def test_full_metadata_budget_keeps_prior_committed_proof(self):
        with self.held(create=True, maximum_bytes=32768) as s:
            self.append(s)
            raw = self.raw(end=14, changed=[], events={}, extra='x'*40000)
            with self.assertRaises(sqlite3.DatabaseError):
                s.append(since=12, raw=raw, expected_sha256=hashlib.sha256(raw).hexdigest())
            self.assertEqual(s.check(), 12)
            self.assertTrue(s.report(10)['ready'])


if __name__ == '__main__': unittest.main()
