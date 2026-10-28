import copy
import hashlib
import os
from pathlib import Path
import tempfile
import unittest

from vk_nightly_qualification import (qualify_file,still_covered,encode_observation,decode_observation,
                                     index_accepted_base,accepted_base_carrier,reanchor_unchanged)


class QualificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'file';self.path.write_bytes(b'accepted bytes')
        self.journal=dict(ready=True,errors=[],terminal=None,instance='one',sequence=12,
                          scope_sha256='a'*64,plan_sha256='b'*64)
        sha=hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.carrier=dict(kind='file',bytes=14,sha256=sha,mode=0o600,
                          segments=[dict(layer='old-accepted-epoch',selector='retained',bytes=14,sha256=sha)])

    def qualify(self,carriers=None,guard=lambda:None):
        return qualify_file(self.path,maximum_bytes=1024,journal=self.journal,
                            carriers=carriers or (lambda sha,size:[self.carrier]),guard=guard)

    def test_equal_verified_bytes_reuse_old_body_and_current_metadata_without_copy(self):
        self.path.chmod(0o644);value=self.qualify()
        self.assertEqual(value['state'],'qualified-retained-body')
        self.assertEqual(value['row']['mode'],0o644)
        self.assertEqual(value['row']['segments'][0]['layer'],'old-accepted-epoch')
        self.assertEqual(value['backup_payload_bytes_copied'],0)
        self.assertFalse(value['namespace_or_whole_baseline_accepted'])

    def test_new_bytes_become_explicit_pending_body_never_implicit_restore(self):
        value=self.qualify(lambda sha,size:[])
        self.assertEqual(value['state'],'qualified-pending-body');self.assertNotIn('segments',value['row'])

    def test_JSONL_append_point_is_double_hashed_and_transferred_as_exact_recorded_prefix(self):
        from vk_nightly_file_version import capture_qualified_version
        import io
        self.path=self.path.with_suffix('.jsonl');body=b'{"event":1}\n';self.path.write_bytes(body)
        calls=[0]
        def append():
            calls[0]+=1
            if calls[0]==2:
                with self.path.open('ab') as f:f.write(b'{"later":2}\n')
        value=self.qualify(lambda *_:[],guard=append)
        self.assertEqual(value['row']['bytes'],len(body))
        self.assertEqual(value['JSONL_point_qualification']['source_actual_read_bytes'],2*len(body))
        sink=io.BytesIO();proof=capture_qualified_version(value,sink,guard=lambda:None)
        self.assertEqual(sink.getvalue(),body);self.assertTrue(proof['source_bytes_after_observation_not_claimed_backed_up'])

    def test_JSONL_rewrite_metadata_change_incomplete_record_and_SQLite_refuse(self):
        self.path=self.path.with_suffix('.jsonl');self.path.write_bytes(b'{"event":1}\n')
        calls=[0]
        def rewrite():
            calls[0]+=1
            if calls[0]==3:self.path.write_bytes(b'{"event":2}\n')
        with self.assertRaisesRegex(ValueError,'hashes differ'):self.qualify(lambda *_:[],guard=rewrite)
        self.path.write_bytes(b'{"incomplete":')
        self.assertNotIn('JSONL_point_qualification',self.qualify(lambda *_:[]))
        self.path.write_bytes(b'SQLite format 3\x00\n')
        with self.assertRaisesRegex(ValueError,'snapshot API'):self.qualify(lambda *_:[])

    def test_mismatched_carrier_cannot_resolve_request(self):
        self.carrier['sha256']='f'*64
        with self.assertRaises(ValueError):self.qualify()

    def test_epoch_gap_or_later_file_ancestor_change_requires_requalification(self):
        value=self.qualify();report=dict(self.journal,since=12,sequence=13,changed=[])
        self.assertTrue(still_covered(value,report))
        self.assertTrue(still_covered(value,dict(report,since=11)))
        for update in (dict(instance='new'),dict(ready=False),dict(changed=[str(self.path.parent)]),dict(since=13)):
            self.assertFalse(still_covered(value,dict(report,**update)))

    def test_moving_source_cannot_become_accepted_old_carrier(self):
        calls=[0]
        def mutate():
            calls[0]+=1
            if calls[0]==2:self.path.write_bytes(b'new version!!')
        with self.assertRaises(ValueError):self.qualify(guard=mutate)

    def test_SQLite_is_not_backed_up_as_an_ordinary_hash_only_file(self):
        self.path.write_bytes(b'SQLite format 3\x00'+b'x'*30)
        with self.assertRaisesRegex(ValueError,'snapshot API'):self.qualify()

    def test_control_compression_preserves_existing_JSON_and_refuses_bad_streams(self):
        import json,zlib
        value=self.qualify();encoded=encode_observation(value)
        self.assertEqual(decode_observation(encoded),value)
        self.assertEqual(decode_observation(json.dumps(value)),value)
        for bad in (encoded[:-1],encoded+b'extra',b'VKQ1\0'+zlib.compress(b'x'*(1024**2+1))):
            with self.assertRaises(ValueError):decode_observation(bad)

    def test_cross_path_reuse_preserves_accepted_epoch_and_never_indexes_original_gaps(self):
        import sqlite3
        source=sqlite3.connect(':memory:');output=sqlite3.connect(':memory:',isolation_level=None)
        self.addCleanup(source.close);self.addCleanup(output.close)
        source.execute('create table current(name text,old_sha256 text,old_bytes integer)')
        source.executemany('insert into current values(?,?,?)',[('old/a','a'*64,7),('old/alias','a'*64,7),('original-gap',None,None)])
        result=index_accepted_base(source,output,source_catalog_sha256='b'*64,restore_proof_sha256='c'*64)
        self.assertEqual(result['unique_verified_content_bodies'],1)
        self.assertEqual(accepted_base_carrier(output,'a'*64,7)['segments'][0]['selector'],'old/a')
        self.assertIsNone(accepted_base_carrier(output,'f'*64,7))
        self.assertFalse(result['original_epoch_gaps_repaired'])

    def test_interrupted_base_index_does_not_commit_a_partial_carrier_catalog(self):
        import sqlite3
        source=sqlite3.connect(':memory:');output=sqlite3.connect(':memory:',isolation_level=None)
        self.addCleanup(source.close);self.addCleanup(output.close)
        source.execute('create table current(name text,old_sha256 text,old_bytes integer)')
        source.execute('insert into current values(?,?,?)',('old/a','a'*64,7))
        def fail():raise RuntimeError('interrupted metadata derivation')
        with self.assertRaises(RuntimeError):index_accepted_base(source,output,source_catalog_sha256='b'*64,restore_proof_sha256='c'*64,checkpoint=fail)
        self.assertEqual(output.execute("select name from sqlite_master where type='table'").fetchall(),[])

    def test_new_ready_observer_reuses_exact_hashed_identity_without_repairing_old_gap(self):
        version=self.qualify()
        report=dict(self.journal,instance='new',since=0,changed=[],sequence=6)
        adopted=reanchor_unchanged(version,report,guard=lambda:None)
        self.assertEqual(adopted['row'],version['row'])
        self.assertEqual(version['journal']['instance'],'one')
        self.assertEqual(adopted['journal']['instance'],'new')
        self.assertEqual(adopted['observer_handover']['source_payload_bytes_reread'],0)
        self.assertFalse(adopted['observer_handover']['original_journal_gap_repaired'])

    def test_handover_refuses_gap_scope_change_changed_ancestor_and_restored_mtime_rewrite(self):
        version=self.qualify();report=dict(self.journal,instance='new',since=0,changed=[],sequence=6)
        for update in [dict(ready=False),dict(errors=[{'overflow':True}]),dict(since=1),
                       dict(scope_sha256='c'*64),dict(changed=[str(self.path.parent)])]:
            with self.assertRaises(ValueError):reanchor_unchanged(version,dict(report,**update),guard=lambda:None)
        # Ensure the fixture rewrite is on a later filesystem timestamp tick.
        import time
        before=self.path.stat();time.sleep(0.03);self.path.write_bytes(b'changed bytes!')
        os.utime(self.path,ns=(before.st_atime_ns,before.st_mtime_ns))
        with self.assertRaisesRegex(ValueError,'identity changed'):
            reanchor_unchanged(version,report,guard=lambda:None)


if __name__=='__main__':unittest.main()
