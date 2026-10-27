import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from vk_nightly_current_map import CurrentMap
from vk_nightly_namespace import observe
from vk_nightly_qualification import encode_observation
from vk_nightly_qualification_worker import qualify_selected


class SelectedQualificationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'source';self.source.write_bytes(b'current bytes')
        self.name=str(self.source)[1:];self.path=self.root/'map.sqlite';self.binding={'test':'selected qualifier'}
        self.observation=observe(self.source)
        ns=sqlite3.connect(':memory:');self.addCleanup(ns.close)
        ns.execute('create table namespace(name text primary key,row blob)');ns.execute('create table namespace_errors(name text primary key,error blob)')
        ns.execute('insert into namespace values(?,?)',(self.name,encode_observation(self.observation)))
        ns.execute('create table gap_meta(id integer primary key,binding text,complete integer)')
        epoch=dict(instance='inode-source',scope_sha256='a'*64,plan_sha256='b'*64,start_sequence=17,
            required_root_bindings={str(self.root):dict(resolved=str(self.root),literal=None)},original_epoch_repaired=False)
        ns.execute('insert into gap_meta values(1,?,1)',(json.dumps(epoch),))
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            m.compile(ns,lambda _:None,SQL_sources=[],checkpoint=lambda:None,maximum_paths=10)
            m.reconcile_namespace(ns,lambda _:None,checkpoint=lambda:None,maximum_paths=10)
        self.report=dict(instance='inode-source',scope_sha256='a'*64,plan_sha256='b'*64,since=17,sequence=25,
            ready=True,errors=[],terminal=None,coverage_model='all-selected-inodes-v1',
            barrier=dict(instance='inode-source',durable_sequence=25,kernel_drain_completed=True))

    def run_phase(self,m,**kwargs):
        return qualify_selected(m,journal=lambda:self.report,
            adopt=lambda records:m.adopt_qualifications(records,lambda *_:[],checkpoint=lambda:None),
            guard=lambda:None,maximum_paths=10,maximum_source_bytes=1024,**kwargs)

    def test_real_stable_hash_adopts_point_and_unchanged_ready_names_are_not_rehashed(self):
        with CurrentMap.held(self.path,binding=self.binding) as m:
            result=self.run_phase(m)
            self.assertEqual(result['qualified_pending_bodies'],1);self.assertEqual(result['completed_source_hash_bytes'],13)
            self.assertFalse(result['more_names']);self.assertEqual(result['backup_payload_bytes_copied'],0)
            with patch('vk_nightly_qualification_worker.qualify_file',side_effect=AssertionError('completed point reread')):
                self.assertEqual(self.run_phase(m)['processed'],0)

    def test_byte_limit_stops_before_source_read_and_retains_pending_point(self):
        with CurrentMap.held(self.path,binding=self.binding) as m:
            with patch('vk_nightly_qualification_worker.qualify_file',side_effect=AssertionError('over-budget hash')):
                result=qualify_selected(m,journal=lambda:self.report,adopt=lambda _:self.fail('unexpected adoption'),
                    guard=lambda:None,maximum_paths=10,maximum_source_bytes=1)
            self.assertEqual(result['processed'],0);self.assertTrue(result['more_names'])

    def test_SQL_header_promotes_to_API_and_does_not_capture_raw_SQL(self):
        self.source.write_bytes(b'SQLite format 3\0' + b'not a database')
        with CurrentMap.held(self.path,binding=self.binding) as m:
            result=self.run_phase(m)
            self.assertEqual(result['SQL_API_sources_discovered'],1)
            self.assertEqual(m.db.execute('select state from members').fetchone(),('SQLite-needs-image',))

    def test_source_absence_is_explicit_deferred_not_silent_deletion(self):
        self.source.unlink()
        with CurrentMap.held(self.path,binding=self.binding) as m:
            result=self.run_phase(m)
            self.assertEqual(result['deferred_points'],1)
            self.assertEqual(m.db.execute('select state from members').fetchone(),('current-namespace-replay-required',))

    def test_actual_resource_or_access_failure_propagates_without_adoption(self):
        with CurrentMap.held(self.path,binding=self.binding) as m:
            with patch('vk_nightly_qualification_worker.qualify_file',side_effect=PermissionError('source access denied')):
                with self.assertRaises(PermissionError):self.run_phase(m)
            self.assertEqual(m.db.execute('select state from members').fetchone(),('file-needs-qualification',))

    def test_incomplete_inode_coverage_refuses_before_any_source_hash(self):
        self.report['errors']=[{'coverage_lost':16384}]
        with CurrentMap.held(self.path,binding=self.binding) as m:
            with patch('vk_nightly_qualification_worker.qualify_file',side_effect=AssertionError('faulted source hashed')):
                with self.assertRaisesRegex(ValueError,'complete inode'):self.run_phase(m)


if __name__=='__main__':unittest.main()
