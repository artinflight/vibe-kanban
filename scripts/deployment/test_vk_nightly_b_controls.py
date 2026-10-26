import hashlib
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from vk_nightly_b_controls import Client,send,recv,packed,current_map,tracking_store,seed
from vk_nightly_objects import ObjectClient
from vk_b_disk_snapshot import metadata


class BControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir='/dev/shm');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.objects=self.root/'objects-v1';self.objects.mkdir()
        self.controls=self.root/'controls-v1';self.controls.mkdir()
        self.original=self.root/'original.sqlite'
        with sqlite3.connect(self.original) as db:db.execute('create table point(id integer primary key,value blob)')
        db.close()  # A SQLite context commits; it does not close the reader FD.
        self.metadata=metadata(self.original);self.raw=self.original.read_bytes();self.sha=hashlib.sha256(self.raw).hexdigest()
        self.children=[];self.addCleanup(self.close)
        folder=str(Path(__file__).parent)
        code='import sys;sys.path.insert(0,'+repr(folder)+');from vk_nightly_objects import receive;receive('+repr(str(self.objects))+',sys.stdin.buffer,sys.stdout.buffer,guard=lambda n:None,maximum_object_bytes=65536)'
        p=subprocess.Popen([sys.executable,'-B','-u','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        client=ObjectClient(p.stdout,p.stdin,guard=lambda:None,ram_root=self.root,maximum_object_bytes=65536)
        self.segments=[client.ensure(self.raw)]
        p.stdin.close();self.assertEqual(p.wait(timeout=10),0);p.stdout.close();p.stderr.close()
        self.client=self.start()
        result=self.client.call(op='import',sha256=self.sha,bytes=len(self.raw),segments=self.segments,Linux_metadata=self.metadata)
        self.assertEqual(result['status'],'needs_independent_readback')
        self.assertEqual(self.client.readback(self.sha),len(self.raw))
        self.receipt=self.client.call(op='acknowledge',sha256=self.sha,independent_stream_sha256=self.sha,Linux_metadata=self.metadata)

    def start(self):
        code=('import sys;sys.path.insert(0,'+repr(str(Path(__file__).parent))+');import vk_nightly_objects as objects;'
            'from vk_nightly_b_controls import serve;serve('+repr(str(self.controls))+
            ',sys.stdin.buffer,sys.stdout.buffer,objects=objects,guard=lambda n:None,maximum_index_bytes=8388608)')
        p=subprocess.Popen([sys.executable,'-B','-u','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.children.append(p);return Client(p.stdout,p.stdin)

    def close(self):
        for p in self.children:
            if not p.stdin.closed:p.stdin.close()
            if p.poll() is None:p.wait(timeout=10)
            p.stdout.close();p.stderr.close()

    def test_native_transactions_roundtrip_binary_and_reopen_without_recopy(self):
        db=self.client.connect('working',self.sha)
        db.execute('begin immediate');db.executemany('insert into point values(?,?)',[(1,b'\x00\xff'),(2,b'kept')]);db.execute('commit')
        self.assertEqual(db.execute('update point set value=? where id=2',(b'kept',)).rowcount,1)
        self.assertEqual(db.execute('select * from point order by id').fetchall(),[(1,b'\x00\xff'),(2,b'kept')])
        db.close();db=self.start().connect('working',self.sha)
        self.assertEqual(db.execute('select count(*) from point').fetchone(),(2,));db.close()
        self.assertEqual(self.original.read_bytes(),self.raw)
        self.assertEqual(self.receipt['Linux_metadata'],self.metadata)

    def test_interruption_rolls_back_only_uncommitted_transaction(self):
        db=self.client.connect('resume',self.sha);db.execute('insert into point values(1,?)',(b'accepted',))
        db.execute('begin immediate');db.execute('insert into point values(2,?)',(b'uncommitted',))
        first=self.children[0];first.stdin.close();self.assertEqual(first.wait(timeout=10),0)
        db=self.start().connect('resume',self.sha)
        self.assertEqual(db.execute('select id from point').fetchall(),[(1,)]);db.close()

    def test_commit_acknowledgement_loss_keeps_single_completed_row(self):
        db=self.client.connect('ackloss',self.sha);db.execute('begin immediate');db.execute('insert into point values(1,?)',(b'once',))
        send(self.client.output,dict(op='execute',name='ackloss',sql='commit',parameters=[]))
        # Server completed a FULL commit; drop its acknowledgement at the client.
        recv(self.client.source)
        p=self.children[0];p.stdin.close();self.assertEqual(p.wait(timeout=10),0)
        db=self.start().connect('ackloss',self.sha)
        self.assertEqual(db.execute('select id from point').fetchall(),[(1,)]);db.close()

    def test_competing_same_index_owner_refused_but_other_index_can_open(self):
        first=self.client.connect('shared',self.sha);other=self.start()
        with self.assertRaisesRegex(ValueError,'BlockingIOError'):other.connect('shared',self.sha)
        second=other.connect('independent',self.sha);second.close();first.close()

    def test_no_database_path_escape_or_disk_temporary_directory(self):
        db=self.client.connect('safe',self.sha)
        for sql in ["attach database '/tmp/not-allowed.sqlite' as outside","pragma temp_store_directory='/tmp'","pragma journal_mode=OFF"]:
            with self.assertRaises(ValueError):db.execute(sql)
        db.close()
        with self.assertRaises(ValueError):self.client.connect('../escape',self.sha)

    def test_unverified_or_substituted_checkpoint_refused(self):
        path=self.controls/(self.sha+'.sqlite');path.write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError,'checkpoint required'):self.client.connect('changed',self.sha)
        self.assertEqual(self.original.read_bytes(),self.raw)

    def test_repeated_short_queries_release_cursors_and_responses_are_bounded(self):
        db=self.client.connect('queries',self.sha)
        for _ in range(300):self.assertEqual(db.execute('select 1').fetchone(),(1,))
        db.close()
        with self.assertRaisesRegex(ValueError,'frame exceeded'):packed({'large':b'x'*(4*1024**2)})

    def test_control_transactions_do_not_require_work_SSD(self):
        # The whole real protocol runs with only these RAM fixture paths. No
        # SSD path or free-space condition exists in native SQLite operations.
        from unittest.mock import patch
        with patch('os.statvfs',side_effect=AssertionError('SSD dependency')):
            db=self.client.connect('low-ssd',self.sha);db.execute('insert into point values(1,?)',(b'kept',))
            self.assertEqual(db.execute('select value from point').fetchone(),(b'kept',));db.close()

    def test_B_tracking_commit_and_health_survive_full_SSD_mirror(self):
        import errno,json
        from vk_nightly_b_tracker import write_health
        from vk_nightly_tracking import FORMAT
        with tracking_store(self.client,'tracking',self.sha,maximum_bytes=1024**2) as store:
            store.start(dict(format=FORMAT,instance='B-one',plan_sha256='b'*64,scope_sha256='a'*64,owner_pid=os.getpid()))
            store.commit(dict(instance='B-one',sequence=4,scope_sha256='a'*64,ready=True,
                changed=['/source/changed'],events={'/source/changed':8},errors=[]))
            store.db.execute('create table tracking_health(id integer primary key,row text not null)')
            def full(*_):raise OSError(errno.ENOSPC,'simulated work SSD full')
            write_health(store.db,self.root/'not-created',dict(ready=True,sequence=4),mirror=full)
            value=json.loads(store.db.execute('select row from tracking_health').fetchone()[0])
            self.assertTrue(value['ready']);self.assertIn('optional_SSD_health_mirror_error',value)
            self.assertFalse((self.root/'not-created').exists())
        with tracking_store(self.start(),'tracking',self.sha,maximum_bytes=1024**2) as store:
            self.assertEqual(store.report('B-one',0)['changed'],['/source/changed'])
            store.start(dict(format=FORMAT,instance='B-two',plan_sha256='b'*64,scope_sha256='a'*64,owner_pid=os.getpid()))
            self.assertFalse(store.report('B-one',0)['ready'])

    def test_new_native_B_state_seed_needs_no_SSD_source_or_hydration(self):
        digest=seed(self.client);db=self.client.connect('new-seed',digest)
        self.assertEqual(db.execute('select version from nightly_control_seed').fetchone(),(1,));db.close()

    def test_large_binary_rows_are_paginated_without_truncation_or_frame_overflow(self):
        db=self.client.connect('large-rows',self.sha);rows=[(i,bytes([i])*600000) for i in range(6)]
        db.executemany('insert into point values(?,?)',rows[:3]);db.executemany('insert into point values(?,?)',rows[3:])
        self.assertEqual(db.execute('select * from point order by id').fetchall(),rows);db.close()

    def import_other(self,path):
        folder=str(Path(__file__).parent)
        code='import sys;sys.path.insert(0,'+repr(folder)+');from vk_nightly_objects import receive;receive('+repr(str(self.objects))+',sys.stdin.buffer,sys.stdout.buffer,guard=lambda n:None,maximum_object_bytes=65536)'
        p=subprocess.Popen([sys.executable,'-B','-u','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest();meta=metadata(path)
            obj=ObjectClient(p.stdout,p.stdin,guard=lambda:None,ram_root=self.root,maximum_object_bytes=65536)
            segments=[obj.ensure(raw)]
        finally:p.stdin.close();p.wait(timeout=10);p.stdout.close();p.stderr.close()
        self.client.call(op='import',sha256=digest,bytes=len(raw),segments=segments,Linux_metadata=meta)
        self.client.readback(digest)
        self.client.call(op='acknowledge',sha256=digest,independent_stream_sha256=digest,Linux_metadata=meta)
        return digest

    def test_actual_current_map_compiles_and_refreshes_on_B_using_same_classifier(self):
        import stat
        from vk_nightly_current_map import CurrentMap
        from vk_nightly_qualification import encode_observation
        source=self.root/'map.sqlite';binding={'namespace':'fixture'}
        ns=sqlite3.connect(':memory:');self.addCleanup(ns.close)
        ns.execute('create table namespace(name text primary key,row blob)')
        meta=dict(uid=os.getuid(),gid=os.getgid(),mode=0o600,mtime_ns=123,xattrs={})
        obs=dict(meta,kind='file',bytes=3,identity=[1,2,stat.S_IFREG|0o600,3,123,456,os.getuid(),os.getgid(),1])
        ns.execute('insert into namespace values(?,?)',('home/source',encode_observation(obs)))
        with CurrentMap.held(source,binding=binding,create=True) as draft:
            draft.compile(ns,lambda name:None,SQL_sources=[],checkpoint=lambda:None,maximum_paths=4)
        digest=self.import_other(source)
        qualified=self.root/'q.sqlite';q=sqlite3.connect(qualified)
        q.execute('create table versions(name text primary key,row blob)')
        version=dict(source='/home/source',state='qualified-retained-body',source_identity=obs['identity'],
            row=dict(meta,kind='file',bytes=3,sha256='a'*64,segments=[dict(layer='old',selector='old/source',bytes=3,sha256='a'*64)]))
        q.execute('insert into versions values(?,?)',('home/source',encode_observation(version)));q.commit();q.close()
        qdigest=self.import_other(qualified)
        qdb=self.client.connect('qualified',qdigest,readonly=True)
        with current_map(self.client,'map',digest,binding=binding) as draft:
            result=self.client.call(op='refresh-current-map',name='map',qualifier='qualified',maximum_paths=8)
            self.assertEqual(result['member_states'],{'verified-file':1})
            self.assertEqual(result['source_payload_bytes_read'],0)
            self.assertFalse(result['current_baseline_accepted'])
        qdb.close()

    def test_prepared_SQL_worker_keeps_state_on_B_and_reuses_completed_API_point(self):
        import json
        from contextlib import contextmanager
        from types import SimpleNamespace
        from unittest.mock import patch
        import vk_nightly_typed_worker as worker
        folder=str(Path(__file__).parent)
        @contextmanager
        def body(config,*,guard):
            code='import sys;sys.path.insert(0,'+repr(folder)+');from vk_nightly_objects import receive;receive('+repr(str(self.objects))+',sys.stdin.buffer,sys.stdout.buffer,guard=lambda n:None,maximum_object_bytes=65536)'
            p=subprocess.Popen([sys.executable,'-B','-u','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                client=ObjectClient(p.stdout,p.stdin,guard=lambda:None,ram_root=self.root,maximum_object_bytes=65536)
                yield SimpleNamespace(client=client,ready={'fixture':True})
            finally:p.stdin.close();p.wait(timeout=10);p.stdout.close();p.stderr.close()
        @contextmanager
        def controls(config,*,guard):yield SimpleNamespace(client=self.client)
        catalog=self.root/'catalog.json';catalog.write_text(json.dumps({'sql_images':{}}))
        config=dict(format='vk-nightly-typed-worker-B-v1',phase_kind='SQL-points',B_controls={},
            B_index_name='sql-cohort-test',B_checkpoint_sha256=self.sha,
            SQL_sources=[str(self.original)],SQL_catalog=str(catalog),SQL_catalog_sha256=hashlib.sha256(catalog.read_bytes()).hexdigest(),
            status=str(self.root/'health.json'),desktop={'B_root':'fixture'},root_floor_bytes=2*1024**3,
            control_margin_bytes=1024**2,memory_floor_bytes=4*1024**3,swap_floor_bytes=1024**3,
            timeout_seconds=60,SQL_image_timeout_seconds=30,maximum_SQL_image_bytes=1024**2,chunk_bytes=4096)
        with patch.object(worker,'DesktopControls',controls),patch.object(worker,'DesktopObjects',body),\
             patch.object(worker,'host_guard',side_effect=lambda *args:None):
            first=worker.run_B(config);self.assertEqual(first['completed_members'],1)
            with patch.object(worker,'capture_SQL_point',side_effect=AssertionError('completed API point recaptured')):
                second=worker.run_B(config)
        self.assertEqual(second['completed_members'],1);self.assertFalse(second['more_pending'])
        self.assertFalse((self.root/'SQL_STATE.private.json').exists());self.assertFalse((self.root/'SQL_PHASE.lease').exists())

    def relocation(self):
        from vk_nightly_file_version import fingerprint
        result=dict(source=str(self.original),sha256=self.sha,bytes=len(self.raw),
            original_identity=fingerprint(self.original.stat()),Linux_metadata=self.metadata,B_checkpoint=self.receipt)
        proof=dict(checkpoint_sha256=self.sha,B_root='B:/vk-backups/fixture/controls-v1',B_working_name='adopted')
        return result,proof

    def test_verified_SSD_replica_replaced_by_small_pointer_and_RAM_recall_preserves_bytes_metadata(self):
        from vk_nightly_control_relocation import retire_replica,reference,recall,MAGIC
        result,proof=self.relocation()
        moved=retire_replica(result,allowed_root=self.root,B_root=proof['B_root'],index_name='adopted',consumer_proof=proof,guard=lambda:None)
        self.assertTrue(self.original.read_bytes().startswith(MAGIC))
        note=reference(self.original,expected_sha256=moved['pointer_sha256'])
        restored=recall(self.client,note,destination=self.root/'nightly-index-recall-proof.sqlite',guard=lambda:None)
        before=metadata(restored)
        for key in ('uid','gid','mode','mtime_ns','atime_ns','xattrs'):self.assertEqual(before[key],self.metadata[key])
        self.assertEqual(restored.read_bytes(),self.raw)
        self.assertTrue((self.controls/(self.sha+'.sqlite')).exists())

    def test_active_original_reader_or_missing_consumer_acceptance_preserves_raw_replica(self):
        from vk_nightly_control_relocation import retire_replica
        result,proof=self.relocation()
        reader=subprocess.Popen([sys.executable,'-B','-u','-c',
            'import sys;f=open(sys.argv[1],"rb");print("ready",flush=True);sys.stdin.read()',str(self.original)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            self.assertEqual(reader.stdout.readline(),b'ready\n')
            with self.assertRaises(BlockingIOError):
                retire_replica(result,allowed_root=self.root,B_root=proof['B_root'],index_name='adopted',consumer_proof=proof,guard=lambda:None)
        finally:reader.stdin.close();reader.wait(timeout=10);reader.stdout.close();reader.stderr.close()
        self.assertEqual(self.original.read_bytes(),self.raw)
        with self.assertRaisesRegex(ValueError,'consumer binding'):
            retire_replica(result,allowed_root=self.root,B_root=proof['B_root'],index_name='adopted',consumer_proof={},guard=lambda:None)
        self.assertEqual(self.original.read_bytes(),self.raw)

    def test_native_readonly_working_health_uses_committed_state_without_taking_writer_owner_lease(self):
        writer=self.client.connect('concurrent-health',self.sha)
        writer.execute('insert into point values(1,?)',(b'committed',))
        other=self.start();reader=other.connect('concurrent-health',self.sha,readonly=True,working=True)
        writer.execute('begin immediate');writer.execute('insert into point values(2,?)',(b'not yet',))
        self.assertEqual(reader.execute('select count(*) from point').fetchone(),(1,))
        with self.assertRaises(ValueError):reader.execute('insert into point values(3,?)',(b'denied',))
        writer.execute('commit');self.assertEqual(reader.execute('select count(*) from point').fetchone(),(2,))
        reader.close();writer.close()

    def test_native_coarse_namespace_batches_resume_without_source_body_or_SSD_index(self):
        from vk_nightly_gap_namespace import initialize,advance_B
        from vk_prep_common import identity
        from vk_change_journal import scope
        source=self.root/'namespace-source';source.mkdir();(source/'sub').mkdir();(source/'sub'/'file').write_text('fixture')
        plan={'sources':[str(source)]};anchor=dict(ready=True,errors=[],terminal=None,instance='one',sequence=1,
            plan_sha256=identity(plan),scope_sha256=identity(scope(plan)))
        db=self.client.connect('gap-state',self.sha);binding=initialize(db,plan,anchor)
        first=advance_B(self.client,'gap-state',plan,binding,guard=lambda:None,maximum_directories=1,maximum_paths=100)
        self.assertFalse(first['enumeration_complete'])
        final=advance_B(self.client,'gap-state',plan,binding,guard=lambda:None,maximum_directories=100,maximum_paths=100)
        self.assertTrue(final['enumeration_complete']);self.assertEqual(final['unique_paths'],3)
        self.assertEqual(final['source_body_bytes_read'],0);self.assertEqual(final['work_SSD_index_bytes'],0)
        db.close()

    def test_long_native_queries_keep_the_real_guard_and_report_its_stop_reason(self):
        import vk_nightly_objects as objects
        from vk_nightly_b_controls import Store
        calls=0
        def stop(_):
            nonlocal calls
            calls+=1
            if calls>=3:raise ValueError('synthetic explicit owner stop')
        store=Store(self.controls,objects,guard=stop)
        db=sqlite3.connect(':memory:');self.addCleanup(db.close);store.configure(db)
        with self.assertRaises(sqlite3.OperationalError):
            db.execute('with recursive n(x) as (values(1) union all select x+1 from n where x<1000000) select sum(x) from n').fetchone()
        self.assertIn('explicit owner stop',store.guard_reason)


if __name__=='__main__':unittest.main()
