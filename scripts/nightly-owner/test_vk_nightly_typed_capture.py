import hashlib
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from vk_nightly_current_map import CurrentMap,decode_member,encode_member
from vk_nightly_namespace import observe
from vk_nightly_qualification import qualify_file,encode_observation
from vk_nightly_objects import ObjectClient
from vk_nightly_typed_capture import capture_pending


class TypedCaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir='/dev/shm');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.source=self.root/'source';self.source.write_bytes(b'a'*4096+b'b'*4096+b'a'*4096)
        self.store=self.root/'objects';self.store.mkdir();self.path=self.root/'map.sqlite'
        self.binding={'test':'independently guarded RAM fixture'}
        journal=dict(ready=True,errors=[],instance='one',sequence=1,scope_sha256='a'*64,plan_sha256='b'*64)
        self.point=qualify_file(self.source,maximum_bytes=16384,journal=journal,carriers=lambda sha,size:[],guard=lambda:None)
        self.name=str(self.source)[1:]
        self.ns=sqlite3.connect(':memory:');self.addCleanup(self.ns.close)
        self.ns.execute('create table namespace(name text primary key,row blob)')
        self.ns.execute('insert into namespace values(?,?)',(self.name,encode_observation(observe(self.source))))
        code='import sys;sys.path.insert(0,'+repr(str(Path(__file__).parent))+');from vk_nightly_objects import receive;receive('+repr(str(self.store))+',sys.stdin.buffer,sys.stdout.buffer,guard=lambda n:None,maximum_object_bytes=4096)'
        self.p=subprocess.Popen([sys.executable,'-B','-u','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.addCleanup(self.close)
        self.client=ObjectClient(self.p.stdout,self.p.stdin,guard=lambda:None,ram_root=self.root,maximum_object_bytes=4096)

    def close(self):
        if not self.p.stdin.closed:self.p.stdin.close()
        if self.p.poll() is None:self.p.wait(timeout=5)
        self.p.stdout.close();self.p.stderr.close()

    def prepare(self,m):
        m.compile(self.ns,lambda name:self.point,SQL_sources=[],checkpoint=lambda:None,maximum_paths=10)

    def run_batch(self,m,guard=lambda:None,**limits):
        return capture_pending(m,self.client,guard=guard,maximum_members=1,
                               maximum_source_bytes=limits.get('maximum_source_bytes',16384),chunk_bytes=4096)

    def prepare_group(self,m):
        points={self.name:self.point}
        journal=dict(ready=True,errors=[],instance='one',sequence=1,scope_sha256='a'*64,plan_sha256='b'*64)
        for i in range(3):
            p=self.source.with_name('source-'+str(i));p.write_bytes(bytes([i])*4096);name=str(p)[1:]
            points[name]=qualify_file(p,maximum_bytes=16384,journal=journal,carriers=lambda sha,size:[],guard=lambda:None)
            self.ns.execute('insert into namespace values(?,?)',(name,encode_observation(observe(p))))
        m.compile(self.ns,points.__getitem__,SQL_sources=[],checkpoint=lambda:None,maximum_paths=10)

    def grouped(self,m,guard=lambda:None,progress=lambda _:None):
        return capture_pending(m,self.client,guard=guard,maximum_members=4,
            maximum_source_bytes=65536,chunk_bytes=4096,acceptance_batch_members=4,on_progress=progress)

    def test_grouped_independent_readbacks_commit_once_and_report_only_after_commit(self):
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            self.prepare_group(m);statements=[];m.db.set_trace_callback(statements.append);reports=[]
            def report(v):
                self.assertFalse(m.db.in_transaction)
                self.assertEqual(m.db.execute("select count(*) from members where state='verified-file'").fetchone()[0],v['completed_members'])
                reports.append(v)
            value=self.grouped(m,progress=report)
            self.assertEqual(value['completed_members'],4);self.assertFalse(value['more_pending'])
            self.assertEqual(sum(s.lower()=='commit' for s in statements),1)
            self.assertEqual([r['completed_members'] for r in reports],[4])
            uploaded=self.client.payload_bytes_sent
            self.assertEqual(self.grouped(m)['completed_members'],0)
            self.assertEqual(self.client.payload_bytes_sent,uploaded)

    def test_group_guard_failure_rolls_back_every_row_and_resume_reuses_native_objects(self):
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            self.prepare_group(m);reports=[]
            def stop():
                if m.db.in_transaction and m.db.execute("select 1 from members where state='verified-file' limit 1").fetchone():
                    raise OSError('actual STOP during atomic group')
            with self.assertRaisesRegex(OSError,'STOP during'):
                self.grouped(m,guard=stop,progress=reports.append)
            self.assertEqual(reports,[])
            self.assertEqual(m.db.execute("select count(*) from members where state='file-needs-capture'").fetchone(),(4,))
            self.assertEqual(m.db.execute('select count(*) from file_acceptance').fetchone(),(0,))
            uploaded=self.client.payload_bytes_sent;self.assertEqual(self.grouped(m)['completed_members'],4)
            self.assertEqual(self.client.payload_bytes_sent,uploaded)

    def test_group_acknowledgement_loss_replays_identical_versions_without_duplicate_history(self):
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            self.prepare_group(m);accept=m.accept_files;retained=[]
            def lost(records,**kw):
                retained.extend(records);accept(records,**kw);raise TimeoutError('lost group reply after FULL commit')
            m.accept_files=lost
            with self.assertRaisesRegex(TimeoutError,'lost group reply'):self.grouped(m)
            m.accept_files=accept;uploaded=self.client.payload_bytes_sent
            self.assertEqual(self.grouped(m)['completed_members'],0)
            self.assertEqual(self.client.payload_bytes_sent,uploaded)
            self.assertEqual(accept(retained,checkpoint=lambda:None),[dict(already_accepted=True)]*4)
            self.assertEqual(m.db.execute('select count(*) from file_acceptance_history').fetchone(),(4,))

    def test_actual_chunked_capture_ordered_readback_and_no_recopy_of_completed_file(self):
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            self.prepare(m);result=self.run_batch(m)
            self.assertEqual(result['completed_members'],1);self.assertFalse(result['more_pending'])
            self.assertEqual(result['independent_object_readbacks'],3)
            self.assertEqual(result['independent_object_readback_bytes'],12288)
            row=decode_member(m.db.execute('select row from members').fetchone()[0])
            self.assertEqual(row['independent_file_proof']['independent_ordered_B_readback_sha256'],self.point['row']['sha256'])
            uploaded=self.client.payload_bytes_sent;self.assertEqual(self.run_batch(m)['completed_members'],0)
            self.assertEqual(self.client.payload_bytes_sent,uploaded)

    def test_interrupted_file_commit_reuses_completed_objects_and_original_pending_row(self):
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            self.prepare(m)
            # Last guard is inside the metadata transaction, after all actual
            # independent readbacks. Trigger only there, not during streaming.
            def fail_commit():
                if m.db.in_transaction:raise RuntimeError('injected metadata commit interruption')
            with self.assertRaises(RuntimeError):self.run_batch(m,guard=fail_commit)
            self.assertEqual(m.db.execute('select state from members').fetchone()[0],'file-needs-capture')
            self.assertEqual(m.db.execute('select count(*) from file_acceptance').fetchone()[0],0)
            uploaded=self.client.payload_bytes_sent;result=self.run_batch(m)
            self.assertEqual(result['completed_members'],1);self.assertEqual(self.client.payload_bytes_sent,uploaded)
            self.assertEqual(result['native_receipts_reused'],3)

    def test_native_read_contention_retries_only_verified_acceptance_without_recopy(self):
        from vk_nightly_b_controls import NativeControlDeferred
        from unittest.mock import patch
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            self.prepare(m);original=m.accept_file;calls=[];uploaded=[]
            def accept(*args,**kwargs):
                calls.append(True);uploaded.append(self.client.payload_bytes_sent)
                if len(calls)==1:raise NativeControlDeferred(dict(error_type='OperationalError',error='database is locked'))
                return original(*args,**kwargs)
            m.accept_file=accept
            with patch.object(self.client,'verify',wraps=self.client.verify) as verify:
                result=self.run_batch(m)
            self.assertEqual(len(calls),2);self.assertEqual(uploaded[0],uploaded[1])
            # Two new chunks feed their already-independent acceptance reads
            # directly; only the repeated accepted first chunk needs a recall.
            self.assertEqual(verify.call_count,1);self.assertEqual(result['source_bytes_read'],12288)
            self.assertEqual(result['completed_members'],1)
            self.assertEqual(m.db.execute('select count(*) from file_acceptance').fetchone(),(1,))

    def test_changed_source_and_insufficient_phase_keep_original_point_unaccepted(self):
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            self.prepare(m)
            self.assertEqual(self.run_batch(m,maximum_source_bytes=1)['next_point_bytes'],12288)
            self.assertEqual(self.client.payload_bytes_sent,0)
            self.source.write_bytes(b'c'*12288)
            result=self.run_batch(m)
            self.assertTrue(result['requires_source_requalification']);self.assertTrue(result['more_pending'])
            self.assertEqual(result['deferred_source_points'],1)
            self.assertEqual(m.db.execute('select state from members').fetchone()[0],'current-namespace-replay-required')
            self.assertEqual(m.db.execute('select count(*) from file_transfer_deferred').fetchone()[0],1)
            self.assertEqual(m.db.execute('select count(*) from file_acceptance').fetchone()[0],0)

    def test_one_rewritten_point_does_not_block_other_valid_files_or_weaken_real_guard_failures(self):
        other=self.source.with_name('source-z');other.write_bytes(b'valid other')
        journal=dict(ready=True,errors=[],instance='one',sequence=2,scope_sha256='a'*64,plan_sha256='b'*64)
        point=qualify_file(other,maximum_bytes=16384,journal=journal,carriers=lambda sha,size:[],guard=lambda:None)
        self.ns.execute('insert into namespace values(?,?)',(str(other)[1:],encode_observation(observe(other))))
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            m.compile(self.ns,lambda name:self.point if name==self.name else point,SQL_sources=[],checkpoint=lambda:None,maximum_paths=10)
            def actual_stop():raise ValueError('explicit B stop fixture')
            with self.assertRaisesRegex(ValueError,'explicit B stop'):self.run_batch(m,guard=actual_stop)
            self.assertIsNone(m.db.execute("select 1 from sqlite_master where name='file_transfer_deferred'").fetchone())
            self.source.write_bytes(b'c'*12288)
            result=capture_pending(m,self.client,guard=lambda:None,maximum_members=2,maximum_source_bytes=32768,chunk_bytes=4096)
            self.assertEqual(result['completed_members'],1);self.assertEqual(result['deferred_source_points'],1)
            self.assertTrue(result['requires_source_requalification'])
            self.assertEqual(m.db.execute('select state from members where name=?',(str(other)[1:],)).fetchone()[0],'verified-file')

    def test_new_point_same_name_preserves_both_accepted_versions_and_exact_duplicate_replay(self):
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            self.prepare(m);pending=m.db.execute('select row from members').fetchone()[0];self.run_batch(m)
            accepted=decode_member(m.db.execute('select row from members').fetchone()[0]);proof=accepted['independent_file_proof']
            replay=m.accept_file(self.name,hashlib.sha256(pending).hexdigest(),accepted,proof,checkpoint=lambda:None)
            self.assertTrue(replay['already_accepted'])
            self.source.write_bytes(b'new point')
            q=qualify_file(self.source,maximum_bytes=16384,journal=dict(ready=True,errors=[],instance='one',sequence=3,scope_sha256='a'*64,plan_sha256='b'*64),carriers=lambda sha,size:[],guard=lambda:None)
            m.db.execute("update members set state='file-needs-capture',row=?",(encode_member(dict(member=q['row'],qualification=q)),))
            self.run_batch(m)
            self.assertEqual(m.db.execute('select count(*) from file_acceptance_history where accepted_row is not null').fetchone()[0],2)

    def prefix(self,m,raw):
        prefix=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),independent_proof_sha256='a'*64,
            segments=[dict(layer='accepted-base',selector='old/history',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())])
        row=decode_member(m.db.execute('select row from members').fetchone()[0]);row['candidate_accepted_prefix']=prefix
        m.db.execute('update members set row=?',(encode_member(row),));return prefix

    def test_accepted_prefix_is_not_uploaded_and_full_composed_readback_matches(self):
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            self.prepare(m);prefix=self.prefix(m,b'a'*4096)
            def reader(proposal,sink):
                self.assertEqual(proposal,prefix);sink.write(b'a'*4096)
            result=capture_pending(m,self.client,guard=lambda:None,maximum_members=1,maximum_source_bytes=16384,
                                   chunk_bytes=4096,read_prefix=reader)
            proof=decode_member(m.db.execute('select proof from file_acceptance').fetchone()[0])
            self.assertEqual(proof['accepted_prefix_bytes_reused'],4096)
            self.assertEqual(proof['transfer']['copied_bytes'],8192)
            self.assertEqual(proof['independent_ordered_B_readback_sha256'],self.point['row']['sha256'])

    def test_incompatible_prefix_falls_back_only_before_any_output_and_counts_extra_source_read(self):
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            self.prepare(m);self.prefix(m,b'c'*4096)
            def forbidden(prefix,sink):self.fail('incompatible prior prefix must not be read as accepted')
            result=capture_pending(m,self.client,guard=lambda:None,maximum_members=1,maximum_source_bytes=16384,
                                   chunk_bytes=4096,read_prefix=forbidden)
            self.assertEqual(result['source_bytes_read'],16384)
            proof=decode_member(m.db.execute('select proof from file_acceptance').fetchone()[0])
            self.assertEqual(proof['accepted_prefix_bytes_reused'],0)
            self.assertEqual(proof['prefix_retry_source_bytes'],4096)

    def test_missing_authenticated_prefix_reader_never_causes_full_duplicate_upload(self):
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            self.prepare(m);self.prefix(m,b'a'*4096)
            with self.assertRaisesRegex(ValueError,'authenticated B reader'):self.run_batch(m)
            self.assertEqual(self.client.payload_bytes_sent,0)


if __name__=='__main__':unittest.main()
