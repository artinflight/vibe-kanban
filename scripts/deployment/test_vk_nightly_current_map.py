import hashlib
import os
from pathlib import Path
import sqlite3
import stat
import tempfile
import unittest

from vk_nightly_current_map import CurrentMap, SealedMemberIndex, classify, encode_member, decode_member
from vk_nightly_qualification import encode_observation,decode_observation


class CurrentMapTests(unittest.TestCase):
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


if __name__=='__main__':unittest.main()
