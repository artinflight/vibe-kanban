import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import stat
import tempfile
import unittest
from unittest.mock import patch

from vk_nightly_current_map import CurrentMap,decode_member,encode_member
from vk_nightly_qualification import encode_observation


class MetadataReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'map.sqlite';self.binding={'test':'metadata-replay'}
        self.obs=dict(kind='file',identity=[1,2,stat.S_IFREG|0o600,3,123,456,1000,1000,1],
                      mode=0o600,uid=1000,gid=1000,mtime_ns=123,bytes=3,xattrs={})
        self.version=dict(source='/home/a',source_identity=self.obs['identity'],state='qualified-retained-body',
            row=dict(kind='file',mode=0o600,uid=1000,gid=1000,mtime_ns=123,bytes=3,xattrs={},sha256='a'*64,
                     segments=[dict(layer='accepted-base',selector='old/a',bytes=3,sha256='a'*64)]))
        self.epoch=dict(instance='inode-epoch',plan_sha256='a'*64,scope_sha256='b'*64,start_sequence=17,
            required_root_bindings={'/home':dict(resolved='/home',literal=None,identity=[1,99,stat.S_IFDIR])},original_epoch_repaired=False)
        ns=sqlite3.connect(':memory:');self.addCleanup(ns.close)
        ns.execute('create table namespace(name text primary key,row blob)')
        ns.execute('create table namespace_errors(name text primary key,error blob)')
        ns.execute('create table gap_meta(id integer primary key,binding text,complete integer)')
        ns.execute('insert into gap_meta values(1,?,1)',(json.dumps(self.epoch),))
        ns.executemany('insert into namespace values(?,?)',[(n,encode_observation(self.obs)) for n in ['home/a','home/old','home/old/child']])
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            m.compile(ns,lambda n:dict(self.version,source='/'+n),SQL_sources=[],checkpoint=lambda:None,maximum_paths=100)
            m.reconcile_namespace(ns,lambda n:dict(self.version,source='/'+n),checkpoint=lambda:None,maximum_paths=100)

    def inputs(self,events=None,**updates):
        events={} if events is None else events
        report=dict(instance=self.epoch['instance'],plan_sha256='a'*64,scope_sha256='b'*64,since=17,sequence=25,
            ready=True,errors=[],terminal=None,coverage_model='all-selected-inodes-v1',changed=sorted(events),events=events,
            barrier=dict(kernel_drain_completed=True,instance=self.epoch['instance'],durable_sequence=25))
        replay=dict(instance=self.epoch['instance'],plan_sha256='a'*64,scope_sha256='b'*64,since=17,through=25,
            observations={p:copy.deepcopy(self.obs) for p in events},absent_observations=[],excluded_observations=[],
            absent_subtrees=[],expanded_subtrees=[],required_root_bindings=self.epoch['required_root_bindings'],
            unchanged_paths_scanned=0,source_payload_bytes_read=0,backup_payload_bytes_copied=0,
            baseline_accepted=False,subsequent_changes_replayed=False)
        replay.update(updates);return report,replay

    def apply(self,m,pair,checkpoint=lambda:None):
        return m.apply_metadata_replay(*pair,checkpoint=checkpoint,maximum_paths=1000)

    def test_exact_unchanged_version_reused_and_deleted_subtree_retained(self):
        pair=self.inputs({'/home/a':4,'/home/old':0x40000200},observations={'/home/a':self.obs},
                         absent_observations=['/home/old'],absent_subtrees=['/home/old'])
        with CurrentMap.held(self.path,binding=self.binding) as m:
            result=self.apply(m,pair)
            self.assertEqual(m.db.execute('select name,state from members').fetchall(),[('home/a','verified-file')])
            self.assertEqual(m.db.execute('select name from namespace_replay_history order by name').fetchall(),
                             [('home/a',),('home/old',),('home/old/child',)])
            self.assertEqual(m.db.execute('select suffix_complete from namespace_reconciliation').fetchone(),(1,))
            self.assertFalse(result['baseline_accepted']);self.assertFalse(result['original_epoch_repaired'])
            self.assertTrue(self.apply(m,pair)['already_complete'])
            self.assertEqual(m.db.execute('select count(*) from namespace_replay_windows').fetchone(),(1,))

    def test_new_version_requires_qualification_and_parent_replacement_removes_descendants(self):
        changed=copy.deepcopy(self.obs);changed['identity'][5]+=1
        pair=self.inputs({'/home/a':2,'/home/old':2},observations={'/home/a':changed,'/home/old':self.obs})
        with CurrentMap.held(self.path,binding=self.binding) as m:
            self.apply(m,pair)
            self.assertEqual(m.db.execute("select state from members where name='home/a'").fetchone(),('file-needs-qualification',))
            self.assertIsNone(m.db.execute("select 1 from members where name='home/old/child'").fetchone())

    def test_metadata_only_empty_suffix_never_looks_up_unchanged_members(self):
        with CurrentMap.held(self.path,binding=self.binding) as m:
            with patch('vk_nightly_current_map.classify',side_effect=AssertionError('unchanged path reclassified')):
                result=self.apply(m,self.inputs())
            self.assertEqual(result['replayed_paths'],0);self.assertEqual(result['unchanged_paths_scanned'],0)
            self.assertEqual(m.db.execute('select count(*) from members').fetchone(),(3,))

    def test_partial_commit_resumes_exact_input_without_duplicate_history(self):
        pair=self.inputs({'/home/new'+str(i).zfill(3):2 for i in range(130)})
        calls=0
        def fail():
            nonlocal calls
            calls+=1
            if calls==4:raise OSError('synthetic later batch failure')
        with CurrentMap.held(self.path,binding=self.binding) as m:
            with self.assertRaisesRegex(OSError,'later batch'):self.apply(m,pair,fail)
            self.assertEqual(m.db.execute('select complete from namespace_replay_windows').fetchone(),(0,))
            self.assertEqual(m.db.execute('select suffix_complete from namespace_reconciliation').fetchone(),(0,))
            other=copy.deepcopy(pair);other[1]['observations']['/home/new129']['identity'][5]+=1
            with self.assertRaisesRegex(ValueError,'exact retained unfinished'):self.apply(m,other)
            self.apply(m,pair)
            self.assertEqual(m.db.execute('select count(*) from members').fetchone(),(133,))
            self.assertTrue(self.apply(m,pair)['already_complete'])

    def test_actual_WAL_event_requires_new_API_point_and_retains_old_proof(self):
        pair=self.inputs({'/home/a-wal':2})
        with CurrentMap.held(self.path,binding=self.binding) as m:
            m.db.execute('insert into SQL_sources values(?)',('/home/a',))
            m.db.execute("update members set row=? where name='home/a'",(encode_member(dict(member=self.version['row'],SQL_point={'source':'/home/a','retained':'old API proof'})),))
            self.apply(m,pair)
            state,raw=m.db.execute("select state,row from members where name='home/a'").fetchone()
            self.assertEqual(state,'SQLite-needs-image')
            self.assertEqual(decode_member(raw)['previous_SQL_point']['retained'],'old API proof')
            self.assertEqual(m.db.execute("select state from members where name='home/a-wal'").fetchone(),('SQLite-sidecar',))

    def test_rejects_wrong_epoch_fault_missing_names_extra_paths_and_fake_expansion(self):
        good=self.inputs({'/home/a':2});variants=[]
        for key,value in [('ready',False),('coverage_model','directory-namespace-only-v1'),('errors',[{'overflow':16384}]),('since',16)]:
            bad=copy.deepcopy(good);bad[0][key]=value;variants.append(bad)
        bad=copy.deepcopy(good);bad[0]['barrier']['durable_sequence']=24;variants.append(bad)
        bad=copy.deepcopy(good);bad[1]['observations']={};variants.append(bad)
        bad=copy.deepcopy(good);bad[1]['observations']['/home/extra']=self.obs;variants.append(bad)
        bad=copy.deepcopy(good);bad[1]['expanded_subtrees']=['/home/a'];variants.append(bad)
        bad=copy.deepcopy(good);bad[1]['required_root_bindings']={};variants.append(bad)
        with CurrentMap.held(self.path,binding=self.binding) as m:
            for bad in variants:
                with self.subTest(bad=bad),self.assertRaises(ValueError):self.apply(m,bad)
            self.assertEqual(m.db.execute('select suffix_complete from namespace_reconciliation').fetchone(),(0,))

    def test_new_partial_suffix_clears_old_readiness_until_commit(self):
        with CurrentMap.held(self.path,binding=self.binding) as m:
            self.apply(m,self.inputs())
            pair=self.inputs({'/home/a':2});pair[0]['since']=25;pair[1]['since']=25
            pair[0]['sequence']=30;pair[0]['barrier']['durable_sequence']=30;pair[1]['through']=30
            def failed():raise OSError('synthetic next suffix stop')
            with self.assertRaisesRegex(OSError,'next suffix stop'):self.apply(m,pair,failed)
            self.assertEqual(m.db.execute('select suffix_complete from namespace_reconciliation').fetchone(),(0,))
            self.apply(m,pair)
            self.assertEqual(m.db.execute('select suffix_complete from namespace_reconciliation').fetchone(),(1,))

    def test_next_suffix_requires_previous_exact_cursor(self):
        with CurrentMap.held(self.path,binding=self.binding) as m:
            self.apply(m,self.inputs())
            pair=self.inputs();pair[0]['sequence']=30;pair[0]['barrier']['durable_sequence']=30;pair[1]['through']=30
            with self.assertRaisesRegex(ValueError,'cursor gap or rewind'):self.apply(m,pair)
            pair[0]['since']=25;pair[1]['since']=25
            self.assertEqual(self.apply(m,pair)['through'],30)


if __name__=='__main__':unittest.main()
