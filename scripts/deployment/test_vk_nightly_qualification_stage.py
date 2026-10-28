import copy
import json
import sqlite3
import unittest
from vk_nightly_qualification import decode_observation
from vk_nightly_qualification_worker import stage_records


class StageTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:',isolation_level=None);self.addCleanup(self.db.close)
        self.db.execute('create table versions(name text primary key,row blob)')
        self.db.execute('insert into versions values(?,?)',('source/a','{"old":"kept"}'))
        self.epoch=dict(instance='full-inodes',plan_sha256='a'*64,scope_sha256='b'*64,start_sequence=5)
        self.row=dict(kind='file',bytes=3,sha256='c'*64,mode=0o600,uid=1000,gid=1000,mtime_ns=1,xattrs={})
        self.point=dict(source='/source/a',source_identity=[1,2,0o100600,3,1,2,1000,1000,1],state='qualified-pending-body',row=self.row,
            source_payload_bytes_hashed=3,journal=dict(self.epoch,sequence=6))
        self.records=[dict(name='source/a',original_sha256='d'*64,version=self.point,source_read_upper_bound=3)]
        self.carrier=dict(self.row,segments=[dict(layer='old',selector='old/a',bytes=3,sha256='c'*64)])

    def stage(self,guard=lambda:None,carriers=None):
        return stage_records(self.db,self.records,carriers or (lambda *_:[]),expected_epoch=self.epoch,job='qualification',guard=guard)

    def test_original_retained_global_hash_match_and_exact_lost_reply(self):
        result=self.stage(carriers=lambda *_:[self.carrier]);self.assertEqual(result['retained_body_matches'],1)
        point=decode_observation(self.db.execute('select row from versions').fetchone()[0])
        self.assertEqual(point['state'],'qualified-retained-body');self.assertEqual(point['row']['segments'],self.carrier['segments'])
        self.assertEqual(self.db.execute('select row from staged_qualification_history').fetchone()[0],'{"old":"kept"}')
        self.assertTrue(self.stage(carriers=lambda *_:self.fail('already staged source repeated'))['already_staged'])
        self.assertEqual(self.db.execute('select count(*) from staged_qualification_batches').fetchone(),(1,))

    def test_interrupted_commit_keeps_prior_source_row_and_cursor_then_resumes(self):
        calls=0
        def fail():
            nonlocal calls
            calls+=1
            if calls==2:raise OSError('actual resource guard')
        with self.assertRaises(OSError):self.stage(guard=fail)
        self.assertEqual(self.db.execute('select row from versions').fetchone()[0],'{"old":"kept"}')
        self.assertEqual(self.db.execute('select count(*) from staged_qualification_progress').fetchone(),(0,))
        self.assertEqual(self.stage()['qualified_pending_bodies'],1)
        self.assertFalse(self.stage()['main_map_mutated'])

    def test_wrong_epoch_or_carrier_refuses_without_overwriting_source_history(self):
        self.records[0]['version']=copy.deepcopy(self.point);self.records[0]['version']['journal']['instance']='old'
        with self.assertRaises(ValueError):self.stage()
        self.records[0]['version']=self.point
        with self.assertRaises(ValueError):self.stage(carriers=lambda *_:[dict(self.carrier,sha256='f'*64)])
        self.assertEqual(self.db.execute('select row from versions').fetchone()[0],'{"old":"kept"}')

    def test_SQL_and_absence_are_staged_as_explicit_deferred_not_raw_acceptance(self):
        self.records[0]['version']=dict(source='/source/a',state='current-version-deferred',reason='SQLite requires its consistent snapshot API',journal=dict(self.epoch,sequence=6))
        result=self.stage();self.assertEqual(result['SQL_API_sources_discovered'],1);self.assertEqual(result['retained_body_matches'],0)
        self.assertEqual(decode_observation(self.db.execute('select row from versions').fetchone()[0])['state'],'current-version-deferred')


if __name__=='__main__':unittest.main()
