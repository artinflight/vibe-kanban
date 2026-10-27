import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import tempfile
import unittest

from vk_nightly_current_map import CurrentMap, SealedMemberIndex, classify, encode_member, decode_member
from vk_nightly_qualification import encode_observation,decode_observation


class CurrentMapTests(unittest.TestCase):
    def later_namespace(self):
        later=sqlite3.connect(':memory:');self.addCleanup(later.close)
        later.execute('create table namespace(name text primary key,row blob)')
        later.execute('create table namespace_errors(name text primary key,error blob)')
        later.execute('create table gap_meta(id integer primary key,binding text,complete integer)')
        later.execute('insert into gap_meta values(1,?,1)',(json.dumps(dict(instance='new-epoch',plan_sha256='a'*64,
            scope_sha256='b'*64,start_sequence=17,original_epoch_repaired=False)),))
        return later

    def test_later_gap_namespace_reuses_only_exact_version_identity_and_retains_absences(self):
        later=self.later_namespace();rewritten=dict(self.observation,identity=list(self.observation['identity']))
        rewritten['identity'][5]+=1
        later.executemany('insert into namespace values(?,?)',[(n,encode_observation(o)) for n,o in
            [('home/a',self.observation),('home/b',rewritten)]])
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            self.ns.execute('insert into namespace values(?,?)',('home/gone',encode_observation(self.observation)))
            self.compile(m)
            def q(name):return dict(self.version,source='/'+name)
            first=m.reconcile_namespace(later,q,checkpoint=lambda:None,maximum_paths=1)
            self.assertTrue(first['more_names'])
            self.assertFalse(m.db.execute('select complete from metadata').fetchone()[0])
            final=m.reconcile_namespace(later,q,checkpoint=lambda:None,maximum_paths=10)
            self.assertFalse(final['more_names']);self.assertTrue(final['journal_suffix_required'])
            self.assertEqual(final['member_states'],{'verified-file':1,'file-needs-qualification':1})
            point=decode_member(m.db.execute("select row from members where name='home/a'").fetchone()[0])['qualification']
            self.assertEqual(point['journal']['instance'],'new-epoch')
            self.assertTrue(point['metadata_handover']['exact_source_identity_and_xattrs_reobserved'])
            self.assertEqual(m.db.execute('select name,disposition from namespace_absent').fetchall(),
                             [('home/gone','later-gap-absence-needs-journal-suffix')])
            with self.assertRaisesRegex(ValueError,'durable journal suffix'):
                SealedMemberIndex(m.db,m.check,{'consistent_SQL_sidecars':{}})

    def test_gap_namespace_xattr_change_cannot_reuse_an_old_body_qualification(self):
        later=self.later_namespace();changed=dict(self.observation,xattrs={'user.changed':'eA=='})
        later.execute('insert into namespace values(?,?)',('home/a',encode_observation(changed)))
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            self.compile(m)
            final=m.reconcile_namespace(later,lambda n:self.version,checkpoint=lambda:None,maximum_paths=10)
            self.assertEqual(final['member_states'],{'file-needs-qualification':1})

    def test_native_batch_lookup_keeps_exact_checks_without_per_file_index_switches(self):
        later=self.later_namespace()
        later.executemany('insert into namespace values(?,?)',[(name,encode_observation(self.observation)) for name in ('home/a','home/b')])
        calls=[]
        def qualified(_):raise AssertionError('per-file qualifier lookup should not run')
        def many(names):calls.append(names);return {'home/a':self.version}
        qualified.many=many
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            self.compile(m)
            result=m.reconcile_namespace(later,qualified,checkpoint=lambda:None,maximum_paths=10)
            self.assertEqual(calls,[['home/a','home/b']])
            self.assertEqual(result['member_states'],{'verified-file':1,'file-needs-qualification':1})

    def test_namespace_error_cannot_be_mislabeled_as_an_absent_old_member(self):
        later=self.later_namespace();later.execute('insert into namespace_errors values(?,?)',('home/a',b'permission denied'))
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            self.compile(m)
            with self.assertRaisesRegex(ValueError,'targeted replay before absence adoption'):
                m.reconcile_namespace(later,lambda name:None,checkpoint=lambda:None,maximum_paths=10)
            self.assertEqual(m.db.execute('select count(*) from members').fetchone()[0],2)

    def test_explicit_successor_retains_old_unaccepted_gap_and_absences_atomically(self):
        first=self.later_namespace();first.execute('insert into namespace values(?,?)',('home/a',encode_observation(self.observation)))
        second=self.later_namespace();binding=json.loads(second.execute('select binding from gap_meta').fetchone()[0])
        binding['instance']='next-epoch';second.execute('update gap_meta set binding=?',(json.dumps(binding),))
        second.executemany('insert into namespace values(?,?)',[(name,encode_observation(self.observation)) for name in ('home/a','home/new')])
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            self.compile(m)
            m.reconcile_namespace(first,lambda n:self.version,checkpoint=lambda:None,maximum_paths=10)
            old_absences=m.db.execute('select * from namespace_absent').fetchall()
            with self.assertRaisesRegex(ValueError,'binding changed'):
                m.reconcile_namespace(second,lambda n:None,checkpoint=lambda:None,maximum_paths=10)
            def failed_commit():raise OSError('synthetic successor commit failure')
            with self.assertRaisesRegex(OSError,'successor commit'):
                m.reconcile_namespace(second,lambda n:None,checkpoint=failed_commit,maximum_paths=10,allow_unaccepted_epoch_successor=True)
            self.assertEqual(m.db.execute('select * from namespace_absent').fetchall(),old_absences)
            self.assertEqual(m.db.execute('select count(*) from namespace_reconciliation_history').fetchone(),(0,))
            result=m.reconcile_namespace(second,lambda n:None,checkpoint=lambda:None,maximum_paths=10,allow_unaccepted_epoch_successor=True)
            self.assertFalse(result['more_names']);self.assertTrue(result['journal_suffix_required'])
            self.assertEqual(m.db.execute('select name,old_state,row,disposition from namespace_absent_history').fetchall(),old_absences)
            history=m.db.execute('select binding,complete,suffix_complete from namespace_reconciliation_history').fetchone()
            self.assertEqual(json.loads(history[0])['instance'],'new-epoch');self.assertEqual(history[1:],(1,0))
            self.assertEqual(decode_member(m.db.execute("select row from members where name='home/a'").fetchone()[0])['qualification']['journal']['instance'],'next-epoch')
            self.assertEqual(result['member_states'],{'verified-file':1,'file-needs-qualification':1})
            with self.assertRaisesRegex(ValueError,'durable journal suffix'):SealedMemberIndex(m.db,m.check,{'consistent_SQL_sidecars':{}})

    def additive_namespace_fixture(self):
        import copy
        old=self.later_namespace();old_binding=json.loads(old.execute('select binding from gap_meta').fetchone()[0])
        roots={'/home':dict(identity=[1,99,stat.S_IFDIR],resolved='/home',target_identity=[1,99,stat.S_IFDIR],literal=None)}
        old_binding['required_root_bindings']=roots
        old.execute('update gap_meta set binding=?',(json.dumps(old_binding),))
        alias=dict(self.observation,kind='symlink',target='/outside/sql',identity=[1,80,stat.S_IFLNK,3,123,456,os.getuid(),os.getgid(),1])
        old.executemany('insert into namespace values(?,?)',[(n,encode_observation(row)) for n,row in [('home/a',self.observation),('home/sql',alias)]])
        new=self.later_namespace();binding=copy.deepcopy(old_binding)
        binding.update(instance='full-inodes',plan_sha256='c'*64,scope_sha256='d'*64,start_sequence=30)
        binding['required_root_bindings'].update({
            '/home/sql':dict(identity=[1,80,stat.S_IFLNK],resolved='/outside/sql',target_identity=[1,2,stat.S_IFREG],literal='/outside/sql'),
            '/outside/sql':dict(identity=[1,2,stat.S_IFREG],resolved='/outside/sql',target_identity=[1,2,stat.S_IFREG],literal=None)})
        new.execute('update gap_meta set binding=?',(json.dumps(binding),))
        new.executemany('insert into namespace values(?,?)',[(n,encode_observation(row)) for n,row in [('home/a',self.observation),('home/sql',alias),('outside/sql',self.observation)]])
        def report(b,instance,seq,full):
            return dict(plan_sha256=b['plan_sha256'],scope_sha256=b['scope_sha256'],instance=instance,
                        since=0,sequence=seq,ready=True,errors=[],terminal=None,
                        coverage_model='all-selected-inodes-v1' if full else 'directory-namespace-only-v1',
                        barrier=dict(kernel_drain_completed=True,durable_sequence=seq,instance=instance))
        proof=dict(format='vk-nightly-additive-full-inode-overlap-v1',baseline_accepted=False,
                   old_hardlink_and_alias_gap_repaired=False,full_gap_metadata_reconciliation_required=True,
                   old_required_root_bindings=roots,new_required_root_bindings=binding['required_root_bindings'],
                   added_roots=['/home/sql','/outside/sql'],old_namespace=report(old_binding,'old-v7',10,False),
                   new_before=report(binding,'full-inodes',20,True),new_after=report(binding,'full-inodes',25,True))
        return old,new,proof

    def test_additive_scope_requires_verified_overlap_and_preserves_SQL_alias_transaction(self):
        old,new,proof=self.additive_namespace_fixture()
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            self.compile(m);m.db.execute('insert into SQL_sources values(?)',('/home/sql',))
            m.reconcile_namespace(old,lambda n:self.version,checkpoint=lambda:None,maximum_paths=10)
            with self.assertRaises(ValueError):
                m.reconcile_namespace(new,lambda n:self.version,checkpoint=lambda:None,maximum_paths=10,allow_unaccepted_epoch_successor=True)
            def fail():raise OSError('synthetic extension commit failure')
            with self.assertRaisesRegex(OSError,'extension commit'):
                m.reconcile_namespace(new,lambda n:self.version,checkpoint=fail,maximum_paths=10,
                    allow_unaccepted_epoch_successor=True,source_scope_extension=proof)
            self.assertIsNone(m.db.execute('select path from SQL_sources where path=?',('/outside/sql',)).fetchone())
            self.assertEqual(m.db.execute('select count(*) from namespace_scope_extensions').fetchone(),(0,))
            result=m.reconcile_namespace(new,lambda n:self.version,checkpoint=lambda:None,maximum_paths=10,
                allow_unaccepted_epoch_successor=True,source_scope_extension=proof)
            self.assertFalse(result['more_names']);self.assertTrue(result['journal_suffix_required'])
            self.assertEqual(m.db.execute('select path from SQL_sources order by path').fetchall(),[('/home/sql',),('/outside/sql',)])
            self.assertEqual(m.db.execute('select state from members where name=?',('outside/sql',)).fetchone(),('SQLite-needs-image',))
            self.assertEqual(m.db.execute('select state from members where name=?',('home/sql',)).fetchone(),('symlink',))
            self.assertEqual(m.db.execute('select count(*) from namespace_scope_extensions').fetchone(),(1,))
            with self.assertRaisesRegex(ValueError,'durable journal suffix'):SealedMemberIndex(m.db,m.check,{'consistent_SQL_sidecars':{}})

    def test_additive_scope_rejects_omissions_bad_barriers_and_unready_inode_epoch(self):
        import copy
        old,new,good=self.additive_namespace_fixture()
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            self.compile(m);m.db.execute('insert into SQL_sources values(?)',('/home/sql',))
            m.reconcile_namespace(old,lambda n:self.version,checkpoint=lambda:None,maximum_paths=10)
            variants=[]
            for key,val in [('coverage_model','directory-namespace-only-v1'),('ready',False),('errors',[{'coverage_lost':16384}]),('barrier',True),('since',False)]:
                bad=copy.deepcopy(good);bad['new_after'][key]=val;variants.append(bad)
            bad=copy.deepcopy(good);bad['old_required_root_bindings']={};variants.append(bad)
            bad=copy.deepcopy(good);bad['added_roots']=['/outside/sql'];variants.append(bad)
            bad=copy.deepcopy(good);bad['new_after']['scope_sha256']='e'*64;variants.append(bad)
            for bad in variants:
                with self.subTest(proof=bad),self.assertRaises(ValueError):
                    m.reconcile_namespace(new,lambda n:self.version,checkpoint=lambda:None,maximum_paths=10,
                        allow_unaccepted_epoch_successor=True,source_scope_extension=bad)
            self.assertIsNone(m.db.execute("select name from sqlite_master where name='namespace_reconciliation_history'").fetchone())
            self.assertIsNone(m.db.execute('select path from SQL_sources where path=?',('/outside/sql',)).fetchone())

    def test_relocated_pointer_fails_closed_with_provider_instruction_before_SQLite_open(self):
        with tempfile.TemporaryDirectory(dir='/dev/shm') as root:
            p=Path(root)/'moved.sqlite';p.write_bytes(b'VK_NIGHTLY_B_CONTROL_POINTER_V1\n{}\n');p.chmod(0o400)
            with self.assertRaisesRegex(ValueError,'relocated.*native-B'):
                with CurrentMap.held(p,binding={}):pass

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'map.sqlite';self.binding={'namespace_proof':'a'*64,'qualifier_owner':123}
        self.metadata=dict(mode=0o600,uid=os.getuid(),gid=os.getgid(),mtime_ns=123,xattrs={})
        self.observation=dict(self.metadata,kind='file',identity=[1,2,stat.S_IFREG|0o600,3,123,456,os.getuid(),os.getgid(),1],bytes=3)
        self.version=dict(source='/home/a',state='qualified-retained-body',source_identity=self.observation['identity'],
                          row=dict(self.metadata,kind='file',bytes=3,sha256=hashlib.sha256(b'abc').hexdigest(),segments=[
                              dict(layer='accepted-base',selector='old/a',bytes=3,sha256=hashlib.sha256(b'abc').hexdigest())]))
        self.ns=sqlite3.connect(':memory:');self.addCleanup(self.ns.close)
        self.ns.execute('create table namespace(name text primary key,row blob) without rowid')
        self.ns.executemany('insert into namespace values(?,?)',[(n,encode_observation(self.observation)) for n in ['home/a','home/b']])

    def compile(self,handle,qualified=None,maximum_paths=100,checkpoint=lambda:None,**kwargs):
        return handle.compile(self.ns,qualified or (lambda name:self.version if name=='home/a' else None),
                              SQL_sources=[],checkpoint=checkpoint,maximum_paths=maximum_paths,**kwargs)

    def test_complete_draft_reuses_carrier_and_keeps_unknown_explicit(self):
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            result=self.compile(m)
            self.assertEqual(result['member_states'],{'file-needs-qualification':1,'verified-file':1})
            self.assertTrue(result['namespace_composed']);self.assertFalse(result['current_baseline_accepted'])
            self.assertEqual(result['source_payload_bytes_read'],0)
            def forbidden(name):raise AssertionError('completed map replayed')
            result=self.compile(m,forbidden)
            self.assertTrue(result['already_complete']);self.assertEqual(result['processed'],0)

    def test_bounded_keyset_reopen_never_replays_completed_name(self):
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            self.assertTrue(self.compile(m,maximum_paths=1)['more_members'])
        with CurrentMap.held(self.path,binding=self.binding) as m:
            seen=[]
            self.compile(m,qualified=lambda name:seen.append(name))
            self.assertEqual(seen,['home/b'])
            self.assertEqual(m.db.execute('select count(*) from members').fetchone()[0],2)

    def test_interrupted_batch_keeps_no_uncommitted_cursor_or_duplicate_rows(self):
        calls=0
        def fail():
            nonlocal calls
            calls+=1
            if calls==2:raise OSError('injected control guard/commit failure')
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            with self.assertRaises(OSError):self.compile(m,checkpoint=fail)
            self.assertEqual(m.db.execute('select last_name from metadata').fetchone()[0],'')
            self.assertEqual(m.db.execute('select count(*) from members').fetchone()[0],0)
            self.assertTrue(self.compile(m)['namespace_composed'])

    def test_source_mismatch_or_unsealed_segments_refuse_acceptance(self):
        wrong=dict(self.version,source='/outside')
        with self.assertRaisesRegex(ValueError,'source/name differs'):
            classify('home/a',self.observation,wrong,SQL_sources=[])
        pending=dict(self.version,state='qualified-pending-body')
        with self.assertRaisesRegex(ValueError,'pending body'):
            classify('home/a',self.observation,pending,SQL_sources=[])

    def test_pending_body_point_keeps_exact_qualification_for_capture(self):
        row=dict(self.version['row']);del row['segments']
        pending=dict(self.version,state='qualified-pending-body',row=row)
        state,result=classify('home/a',self.observation,pending,SQL_sources=[])
        self.assertEqual(state,'file-needs-capture');self.assertEqual(result['qualification'],pending)

    def test_SQL_header_discovery_and_sidecar_require_consistent_API(self):
        q=dict(source='/home/a',state='current-version-deferred',reason='SQLite requires its consistent snapshot API')
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            self.ns.execute('insert into namespace values(?,?)',('home/a-wal',encode_observation(self.observation)))
            result=self.compile(m,qualified=lambda name:q if name=='home/a' else None)
            self.assertEqual(result['member_states']['SQLite-needs-image'],1)
            self.assertEqual(result['member_states']['SQLite-sidecar'],1)
            self.assertEqual(m.db.execute('select path from SQL_sources').fetchall(),[('/home/a',)])

    def test_separately_verified_component_wins_without_mutating_original_observation(self):
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            result=self.compile(m,qualified=lambda name:None,special_versions={'home/a':self.version})
            self.assertEqual(result['member_states']['verified-file'],1)

    def test_binding_change_and_competing_owner_are_refused(self):
        with CurrentMap.held(self.path,binding=self.binding,create=True):
            with self.assertRaises(BlockingIOError):
                with CurrentMap.held(self.path,binding=self.binding):pass
        with self.assertRaisesRegex(ValueError,'binding differs'):
            with CurrentMap.held(self.path,binding={'namespace_proof':'b'*64}):pass

    def test_lossless_control_reencoding_preserves_compile_cursor_and_resumes_its_own_cursor(self):
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            self.compile(m,maximum_paths=1)
            original=m.db.execute('select name,state,row from members').fetchone()
            self.assertFalse(m.reencode(checkpoint=lambda:None,maximum_paths=1)['complete'])
        with CurrentMap.held(self.path,binding=self.binding) as m:
            result=m.reencode(checkpoint=lambda:None,maximum_paths=10)
            self.assertTrue(result['complete'])
            name,state,raw=m.db.execute('select name,state,row from members').fetchone()
            self.assertEqual((name,state),(original[0],original[1]))
            self.assertEqual(decode_member(raw),decode_member(original[2]))
            self.assertEqual(m.db.execute('select last_name from metadata').fetchone()[0],'home/a')
            self.assertTrue(self.compile(m)['namespace_composed'])

    def test_control_encoding_roundtrip_legacy_compatibility_and_corruption_refusal(self):
        value={'qualification':self.version,'member':self.version['row']}
        self.assertEqual(decode_member(encode_member(value)),value)
        self.assertEqual(decode_member(encode_observation(value)),value)
        for raw in (encode_member(value)[:-1],encode_member(value)+b'extra'):
            with self.assertRaises(ValueError):decode_member(raw)

    def test_refresh_only_unresolved_keys_and_resume_past_still_unknown_names(self):
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            self.compile(m,qualified=lambda name:None)
            first=m.refresh_unresolved(lambda name:None,checkpoint=lambda:None,maximum_paths=1)
            self.assertTrue(first['more_names']);self.assertEqual(first['last_name'],'home/a')
            newer=dict(self.version,source='/home/b')
            seen=[]
            def qualified(name):seen.append(name);return newer
            final=m.refresh_unresolved(qualified,checkpoint=lambda:None,maximum_paths=10,after=first['last_name'])
            self.assertEqual(seen,['home/b']);self.assertFalse(final['more_names'])
            self.assertEqual(final['member_states'],{'file-needs-qualification':1,'verified-file':1})

    def test_sealed_reader_refuses_unresolved_maps_and_reads_complete_typed_members_without_copy(self):
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            self.compile(m)
        db=sqlite3.connect(self.path);self.addCleanup(db.close)
        index=SealedMemberIndex(db,lambda:None,{'format':'vk-nightly-current-member-map-v1'})
        self.assertEqual(index.entry('home/a'),self.version['row'])
        with self.assertRaisesRegex(ValueError,'unresolved'):list(index.entries())

    def test_SQL_sidecar_requires_exact_consistent_image_binding(self):
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            self.ns.execute('delete from namespace where name=?',('home/b',))
            self.compile(m)
            m.db.execute('insert into members values(?,?,?)',('home/a-wal','SQLite-sidecar',encode_member({'required_SQL_source':'/home/a'})))
        db=sqlite3.connect(self.path);self.addCleanup(db.close)
        with self.assertRaisesRegex(ValueError,'disposition'):SealedMemberIndex(db,lambda:None,{})
        reference={'consistent_SQL_sidecars':{'home/a-wal':{'source':'/home/a','snapshot_sha256':self.version['row']['sha256']}}}
        reader=SealedMemberIndex(db,lambda:None,reference)
        self.assertEqual(list(reader.entries()),[('home/a',self.version['row'])])
        with self.assertRaises(KeyError):reader.entry('home/a-wal')

    def test_SQL_alias_cannot_hide_a_required_target_outside_the_current_map(self):
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            self.compile(m)
            m.db.execute('insert into SQL_sources values(?)',('/home/live.sqlite',))
            m.db.execute('insert into members values(?,?,?)',('home/live.sqlite','symlink',
                encode_member(dict(member=dict(kind='symlink',target='/separate/live.sqlite')))))
        db=sqlite3.connect(self.path);self.addCleanup(db.close)
        with self.assertRaisesRegex(ValueError,'alias dependency'):SealedMemberIndex(db,lambda:None,{})
        reference={'consistent_SQL_aliases':{'home/live.sqlite':dict(source='/separate/live.sqlite',snapshot_sha256='a'*64)}}
        with self.assertRaisesRegex(ValueError,'actual captured target'):SealedMemberIndex(db,lambda:None,reference)


if __name__=='__main__':unittest.main()
