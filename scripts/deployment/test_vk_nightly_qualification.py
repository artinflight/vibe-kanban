import copy
import hashlib
import os
from pathlib import Path
import tempfile
import unittest

from vk_nightly_qualification import (qualify_file,still_covered,encode_observation,decode_observation,
                                     index_accepted_base,accepted_base_carrier)


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


if __name__=='__main__':unittest.main()
