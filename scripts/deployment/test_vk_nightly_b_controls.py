import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import io
import threading
import time
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

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

    def start(self,maximum_index_bytes=8388608):
        code=('import sys;sys.path.insert(0,'+repr(str(Path(__file__).parent))+');import vk_nightly_objects as objects;'
            'from vk_nightly_b_controls import serve;serve('+repr(str(self.controls))+
            ',sys.stdin.buffer,sys.stdout.buffer,objects=objects,guard=lambda n:None,maximum_index_bytes='+repr(maximum_index_bytes)+')')
        p=subprocess.Popen([sys.executable,'-B','-u','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.children.append(p);return Client(p.stdout,p.stdin)

    def close(self):
        for p in self.children:
            if not p.stdin.closed:p.stdin.close()
            if p.poll() is None:p.wait(timeout=10)
            p.stdout.close();p.stderr.close()

    def test_actual_inotify_to_native_protocol_ack_and_B_prefix_after_Desktop_failure(self):
        from vk_nightly_bounded_spool import held
        from vk_nightly_tracking import serve,request
        from vk_nightly_outbox_collector import copy_once
        from vk_nightly_outbox_export import retained_prefix_report
        from vk_nightly_inode_journal import Journal as InodeJournal
        from vk_nightly_tracked_delta import select
        source=self.root/'source';source.mkdir();endpoint=self.root/'source.sock';status=self.root/'source-status'
        stop=threading.Event();errors=[]
        target=dict(B_root='B:/vk-backups/test/controls-v1',index_name='outbox',checkpoint_sha256=self.sha)
        @contextmanager
        def factory():
            with held(self.root/'bounded.sqlite',maximum_bytes=256*1024,guard=lambda:None,replica=target) as store:yield store
        def observe():
            try:serve({'sources':[str(source)]},None,endpoint,guard=lambda:None,status_path=status,stop=stop,store_factory=factory,journal_factory=InodeJournal)
            except BaseException as error:errors.append(error)
        thread=threading.Thread(target=observe);thread.start()
        try:
            end=time.monotonic()+10
            while not endpoint.exists():
                if errors:raise errors[0]
                if time.monotonic()>end:self.fail('tiny observer failed to enroll')
                time.sleep(.01)
            config=dict(source_health=str(status),endpoint=str(endpoint),B_delivery_target=target,
                        controls={'B_root':target['B_root']},maximum_B_index_bytes=8*1024**2)
            # Real empty fixture namespace is the accepted starting point;
            # this never labels the production backup as accepted.
            initial=request(endpoint,json.loads(status.read_text())['instance'],0,barrier=True)
            self.assertEqual(list(source.iterdir()),[])
            anchor=dict(baseline_accepted=True,instance=initial['instance'],sequence=initial['sequence'],
                plan_sha256=initial['plan_sha256'],scope_sha256=initial['scope_sha256'],sources=[str(source)])
            (source/'changed').write_bytes(b'fixture')
            with patch('vk_nightly_outbox_collector.DesktopControls',side_effect=ConnectionError('Desktop offline')):
                with self.assertRaises(ConnectionError):copy_once(config,guard=lambda:None)
            instance=json.loads(status.read_text())['instance']
            self.assertTrue(request(endpoint,instance,0,barrier=True)['ready'])
            @contextmanager
            def remote(*_,**__):yield SimpleNamespace(client=self.client)
            with patch('vk_nightly_outbox_collector.DesktopControls',remote):
                result=copy_once(config,guard=lambda:None)
            self.assertTrue(result['actual_native_B_reopen_verified']);self.assertFalse(result['whole_baseline_accepted'])
            self.assertTrue(result['local_changes_pruned']);self.assertEqual(result['local_changes_pruned_through'],result['sequence'])
            from vk_nightly_tracking import RetainedPrefixRequired
            with self.assertRaises(RetainedPrefixRequired) as compacted:request(endpoint,instance,0)
            self.assertEqual(compacted.exception.through,result['sequence'])
            with tracking_store(self.client,'outbox',self.sha,maximum_bytes=8*1024**2) as store:
                combined=retained_prefix_report(store,endpoint,instance,0,guard=lambda:None)
                self.assertIn(str(source/'changed'),combined['changed']);self.assertEqual(combined['source_paths_scanned'],0)
                self.assertEqual(combined['since'],anchor['sequence'])
                selected=select(anchor,combined,required_sql=[],maximum_paths=16,
                    enumerate_subtree=lambda _:self.fail('unchanged fixture workspace scanned'))
                self.assertIn(str(source/'changed'),selected['paths'])
                self.assertEqual(selected['unchanged_paths_scanned'],0)
                self.assertFalse(selected['writer_fence_verified'])
        finally:
            stop.set();thread.join(timeout=5)
        self.assertFalse(thread.is_alive());self.assertEqual(errors,[])

    def test_existing_larger_index_is_rejected_before_a_misleading_SQLITE_FULL(self):
        from vk_nightly_b_controls import NativeControlError
        db=self.client.connect('grown',self.sha)
        db.execute('create table larger(body blob)');db.execute('insert into larger values(zeroblob(65536))');db.close()
        smaller=self.start(maximum_index_bytes=16384)
        with self.assertRaisesRegex(NativeControlError,'existing native B index exceeds') as caught:
            smaller.connect('grown',self.sha)
        self.assertEqual(caught.exception.native_context['operation'],'open')
        # A metadata reader may inspect it without claiming a writable budget.
        view=smaller.connect('grown',self.sha,readonly=True,working=True)
        self.assertEqual(view.execute('select length(body) from larger').fetchone(),(65536,));view.close()
        # Restore the previously measured bound on the same normal provider.
        db=self.client.connect('grown',self.sha)
        state=self.client.call(op='storage-status',name='grown')
        self.assertGreater(state['max_page_count'],state['page_count'])
        self.assertEqual(Path(state['temporary_directory']),self.controls/'sqlite-tmp-v1')
        self.assertEqual(Path(state['sqlite_temp_directory']),self.controls/'sqlite-tmp-v1')
        db.execute('insert into larger values(zeroblob(4096))');db.close()

    def test_native_transactions_roundtrip_binary_and_reopen_without_recopy(self):
        db=self.client.connect('working',self.sha)
        db.execute('begin immediate');db.executemany('insert into point values(?,?)',[(1,b'\x00\xff'),(2,b'kept')]);db.execute('commit')
        self.assertEqual(db.execute('update point set value=? where id=2',(b'kept',)).rowcount,1)
        self.assertEqual(db.execute('select * from point order by id').fetchall(),[(1,b'\x00\xff'),(2,b'kept')])
        db.close();db=self.start().connect('working',self.sha)
        self.assertEqual(db.execute('select count(*) from point').fetchone(),(2,));db.close()
        self.assertEqual(self.original.read_bytes(),self.raw)
        self.assertEqual(self.receipt['Linux_metadata'],self.metadata)

    def test_native_busy_is_deferred_but_access_STOP_and_integrity_errors_are_not(self):
        from vk_nightly_b_controls import NativeControlDeferred,NativeControlError
        for kind,message,reason,expected in [
                ('BlockingIOError','another own-index writer',None,NativeControlDeferred),
                ('OperationalError','database is locked',None,NativeControlDeferred),
                ('PermissionError','STOP access denied',None,NativeControlError),
                ('Blocked','OWNER_PAUSE_OR_MALFORMED',None,NativeControlError),
                ('OperationalError','database is locked','real guard failure',NativeControlError),
                ('DatabaseError','database disk image is malformed',None,NativeControlError)]:
            with self.subTest(kind=kind,message=message,reason=reason):
                source=io.BytesIO();send(source,dict(error_type=kind,error=message,guard_reason=reason));source.seek(0)
                client=Client(source,io.BytesIO())
                with self.assertRaises(expected) as caught:client.call(op='check',name='owned')
                self.assertIs(type(caught.exception),expected)
                self.assertEqual(caught.exception.native_error_type,kind)

    def test_native_busy_retry_keeps_real_guards_access_and_owner_failures(self):
        from vk_nightly_b_controls import retry_native_busy,NativeControlDeferred,NativeControlError
        for failure in [NativeControlError(dict(error_type='PermissionError',error='access denied')),
                        NativeControlError(dict(error_type='Blocked',error='OWNER_PAUSE')),
                        NativeControlDeferred(dict(error_type='BlockingIOError',error='other owner'))]:
            calls=[]
            def denied():calls.append(True);raise failure
            with self.assertRaises(type(failure)):retry_native_busy(denied,guard=lambda:None,sleep=lambda _:None)
            self.assertEqual(len(calls),1)
        busy=NativeControlDeferred(dict(error_type='OperationalError',error='database is locked'))
        def locked():raise busy
        ticks=iter([0,11])
        with self.assertRaises(NativeControlDeferred):retry_native_busy(locked,guard=lambda:None,clock=lambda:next(ticks),sleep=lambda _:None)
        calls=[]
        def guard():
            calls.append(True)
            if len(calls)==2:raise OSError('real memory floor')
        with self.assertRaisesRegex(OSError,'real memory floor'):
            retry_native_busy(locked,guard=guard,sleep=lambda _:None)

    def test_actual_consistent_API_point_is_adopted_once_only_from_exact_B_acceptance(self):
        from vk_nightly_current_map import CurrentMap
        from vk_nightly_namespace import observe
        from vk_nightly_qualification import encode_observation
        from vk_nightly_sql_point import capture_SQL_point
        source=self.root/'selected.sqlite'
        with sqlite3.connect(source) as db:db.execute('create table actual(value)');db.execute("insert into actual values('retained')")
        db.close()
        code=('import sys;sys.path.insert(0,'+repr(str(Path(__file__).parent))+');from vk_nightly_objects import receive;receive('
              +repr(str(self.objects))+',sys.stdin.buffer,sys.stdout.buffer,guard=lambda n:None,maximum_object_bytes=65536)')
        body=subprocess.Popen([sys.executable,'-B','-u','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.children.append(body);client=ObjectClient(body.stdout,body.stdin,guard=lambda:None,ram_root=self.root,maximum_object_bytes=65536)
        record=capture_SQL_point(source,client,allowed_sources={str(source)},guard=lambda:None,retained_by_sha=lambda *_:None,
            ram_root=self.root,maximum_image_bytes=1024**2,chunk_bytes=4096,timeout_seconds=30)
        namespace=sqlite3.connect(':memory:')
        namespace.execute('create table namespace(name text primary key,row blob)')
        namespace.execute('insert into namespace values(?,?)',(str(source)[1:],encode_observation(observe(source))))
        original=self.root/'current-SQL-map.sqlite'
        try:
            with CurrentMap.held(original,binding={'fixture':'SQL'},create=True) as current:
                current.compile(namespace,lambda _:None,SQL_sources=[str(source)],checkpoint=lambda:None,maximum_paths=10)
        finally:namespace.close()
        raw=original.read_bytes();sha=hashlib.sha256(raw).hexdigest();meta=metadata(original);segments=[client.ensure(raw)]
        self.client.call(op='import',sha256=sha,bytes=len(raw),segments=segments,Linux_metadata=meta)
        self.client.readback(sha);self.client.call(op='acknowledge',sha256=sha,independent_stream_sha256=sha,Linux_metadata=meta)
        index=self.client.connect('sql-member-map',sha)
        try:
            altered=dict(record,status='not an actual API point')
            with self.assertRaisesRegex(ValueError,'actual B object'):
                self.client.call(op='accept-SQL-point',name='sql-member-map',record=altered)
            self.assertEqual(index.execute('select state from members').fetchone(),('SQLite-needs-image',))
            self.assertFalse(self.client.call(op='accept-SQL-point',name='sql-member-map',record=record)['already_accepted'])
            self.assertTrue(self.client.call(op='accept-SQL-point',name='sql-member-map',record=record)['already_accepted'])
            self.assertEqual(index.execute('select state from members').fetchone(),('verified-file',))
            self.assertEqual(index.execute('select count(*) from SQL_acceptance_history').fetchone(),(1,))
            # Consume the accepted point through the normal sealed member
            # view, then independently restore exactly that selected recipe.
            # A verified SQL flag alone must not stand in for usable content.
            from vk_nightly_current_map import SealedMemberIndex,encode_member
            alias=self.root/'logical.sqlite';alias.symlink_to(source)
            link=observe(alias);row={k:link[k] for k in ('kind','target','uid','gid','mode','mtime_ns','xattrs')}
            index.execute('insert into SQL_sources values(?)',(str(alias),))
            index.execute('insert into members values(?,?,?)',(str(alias)[1:],'symlink',encode_member(dict(member=row))))
            with self.assertRaisesRegex(ValueError,'alias dependency'):
                SealedMemberIndex(index,lambda:None,{'consistent_SQL_sidecars':{}})
            proofs={str(alias)[1:]:dict(source=str(source),snapshot_sha256=record['sha256'])}
            reader=SealedMemberIndex(index,lambda:None,{'consistent_SQL_sidecars':{},'consistent_SQL_aliases':proofs})
            self.assertEqual(reader.entry(str(alias)[1:])['target'],str(source))
            member=reader.entry(str(source)[1:]);restored=io.BytesIO()
            for segment in member['segments']:client.verify(segment,restored)
            raw=restored.getvalue()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),member['sha256'])
            self.assertEqual(len(raw),member['bytes'])
            with sqlite3.connect(':memory:') as reopened:
                reopened.deserialize(raw)
                self.assertEqual(reopened.execute('pragma integrity_check').fetchall(),[('ok',)])
                self.assertEqual(reopened.execute('select value from actual').fetchall(),[('retained',)])
            reopened.close()
            for key in ('uid','gid','mode','mtime_ns','xattrs'):
                self.assertEqual(member[key],record['source_metadata_before'][key])
        finally:index.close()

    def test_inode_demand_deduplicates_aliases_from_retained_metadata_only(self):
        from vk_nightly_qualification import encode_observation
        db=self.client.connect('inode-demand',self.sha)
        try:
            db.execute('create table namespace(name text primary key,row blob)')
            for name,kind,inode,links in [('a','file',1,2),('b','file',1,2),('c','file',2,1),('d','directory',3,1),('e','symlink',4,1)]:
                db.execute('insert into namespace values(?,?)',(name,encode_observation(dict(kind=kind,identity=[10,inode,0,0,0,0,1000,1000,links]))))
            result=self.client.call(op='namespace-inode-demand',name='inode-demand',maximum_paths=10)
            self.assertEqual(result['unique_regular_inodes'],2);self.assertEqual(result['all_inode_watch_demand'],4)
            self.assertEqual(result['symlink_paths'],1);self.assertEqual(result['unique_symlink_inodes'],1)
            self.assertEqual(result['hardlinked_paths'],2);self.assertEqual(result['unique_hardlinked_inodes'],1)
            self.assertEqual(result['source_paths_scanned'],0);self.assertEqual(result['source_body_bytes_read'],0)
            with self.assertRaises(ValueError):self.client.call(op='namespace-inode-demand',name='inode-demand',maximum_paths=1)
            self.assertEqual(db.execute('select count(*) from namespace').fetchone(),(5,))
        finally:db.close()

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

    def test_partial_SSD_health_write_is_bounded_and_next_commit_recovers_without_stale_temp_collision(self):
        import errno
        from unittest.mock import patch
        from vk_nightly_b_tracker import write_health
        db=self.client.connect('health-recovery',self.sha)
        db.execute('create table tracking_health(id integer primary key,row text not null)')
        path=self.root/'status.json';original=os.write;calls=0
        def partial(fd,raw):
            nonlocal calls
            calls+=1
            if calls==1:return original(fd,raw[:16])
            raise OSError(errno.ENOSPC,'synthetic actual partial write, then SSD full')
        with patch('vk_nightly_b_tracker.os.write',side_effect=partial):write_health(db,path,dict(ready=True,sequence=1))
        value=json.loads(db.execute('select row from tracking_health').fetchone()[0])
        self.assertTrue(value['ready']);self.assertIn('optional_SSD_health_mirror_error',value)
        self.assertFalse(path.exists());self.assertEqual(list(self.root.glob('*.mirror.new')),[])
        write_health(db,path,dict(ready=True,sequence=2))
        self.assertEqual(json.loads(path.read_text())['sequence'],2)
        self.assertEqual(list(self.root.glob('*.mirror.new')),[])
        stale=path.with_name(path.name+'.mirror.new');stale.write_bytes(b'preserve unknown stale inode')
        write_health(db,path,dict(ready=True,sequence=3))
        self.assertEqual(stale.read_bytes(),b'preserve unknown stale inode')
        self.assertEqual(json.loads(db.execute('select row from tracking_health').fetchone()[0])['sequence'],3)
        db.close()

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

    def test_native_metadata_suffix_requires_actual_B_journal_and_preserves_interrupted_input(self):
        import stat
        from vk_nightly_current_map import CurrentMap
        from vk_nightly_tracking import TrackingStore
        from vk_nightly_outbox_export import export
        from vk_nightly_namespace import replay_metadata
        from vk_nightly_gap_namespace import initialize
        source=self.root/'source';source.mkdir();(source/'a').write_bytes(b'abc')
        from vk_prep_common import identity
        from vk_change_journal import scope
        from vk_nightly_tracking import source_bindings
        plan={'sources':[str(source)]};bindings=source_bindings(plan)
        report=dict(instance='inode-fixture',plan_sha256=identity(plan),scope_sha256=identity(scope(plan)),
            since=0,sequence=1,ready=True,errors=[],terminal=None,coverage_model='all-selected-inodes-v1',
            changed=[str(source/'a')],events={str(source/'a'):2},
            barrier=dict(kernel_drain_completed=True,durable_sequence=1,instance='inode-fixture'))
        anchor=dict(report,sequence=0)
        namespace=sqlite3.connect(':memory:');self.addCleanup(namespace.close)
        initialize(namespace,plan,anchor);namespace.execute('update gap_meta set complete=1');namespace.commit()
        path=self.root/'replay-map.sqlite'
        with CurrentMap.held(path,binding={'test':'replay'},create=True) as m:
            m.compile(namespace,lambda n:None,SQL_sources=[],checkpoint=lambda:None,maximum_paths=10)
            m.reconcile_namespace(namespace,lambda n:None,checkpoint=lambda:None,maximum_paths=10)
        digest=self.import_other(path)
        replay=replay_metadata(plan,report,instance='inode-fixture',since=0,maximum_paths=10,checkpoint=lambda:None)
        from vk_nightly_metadata_replay import stage_input,durable_report
        db=self.client.connect('replay-map',digest)
        sha=stage_input(db,report,replay,guard=lambda:None)
        self.assertEqual(stage_input(db,report,replay,guard=lambda:None),sha)
        journal=self.client.connect('replay-ledger',self.sha)
        TrackingStore.initialize(journal)
        class Ledger(TrackingStore):
            def check(self):journal.request('check')
        ledger=Ledger();ledger.db=journal
        binding=dict(format='vk-nightly-tracking-v1',instance='inode-fixture',plan_sha256=identity(plan),scope_sha256=identity(scope(plan)),
            coverage_model='all-selected-inodes-v1',required_root_bindings=bindings,owner_pid=os.getpid(),owner_start_ticks=123)
        proof=export(binding,report,ledger,guard=lambda:None)
        self.assertEqual(durable_report(ledger,'inode-fixture',0,guard=lambda:None)['events'],report['events'])
        with self.assertRaisesRegex(ValueError,'exact retained replay input'):
            self.client.call(op='replay-current-map',name='replay-map',journal_index='replay-ledger',input_sha256='f'*64,maximum_paths=10)
        journal.execute("update epochs set ready=0 where instance='inode-fixture'")
        with self.assertRaisesRegex(ValueError,'cursor/health'):
            self.client.call(op='replay-current-map',name='replay-map',journal_index='replay-ledger',input_sha256=sha,maximum_paths=10)
        journal.execute("update epochs set ready=1 where instance='inode-fixture'")
        value=self.client.call(op='replay-current-map',name='replay-map',journal_index='replay-ledger',input_sha256=sha,maximum_paths=10)
        self.assertEqual(value['through'],1);self.assertFalse(value['baseline_accepted'])
        self.assertEqual(db.execute('select suffix_complete from namespace_reconciliation').fetchone(),(1,))
        self.assertTrue(self.client.call(op='replay-current-map',name='replay-map',journal_index='replay-ledger',input_sha256=sha,maximum_paths=10)['already_complete'])
        self.assertEqual(db.execute('select count(*) from namespace_replay_windows').fetchone(),(1,))
        journal.execute("update epochs set cursor=2,ready=0 where instance='inode-fixture'")
        self.assertTrue(self.client.call(op='replay-current-map',name='replay-map',journal_index='replay-ledger',input_sha256=sha,maximum_paths=10)['already_complete'])
        db.close();journal.close()

    def test_native_terminal_gap_adoption_requires_exact_independently_retained_proof(self):
        from vk_nightly_current_map import CurrentMap
        from vk_nightly_gap_namespace import initialize
        from vk_prep_common import identity
        from vk_change_journal import scope
        source=self.root/'source';source.mkdir();plan={'sources':[str(source)]}
        def namespace(path,instance):
            db=sqlite3.connect(path)
            initialize(db,plan,dict(instance=instance,ready=True,errors=[],sequence=17,
                plan_sha256=identity(plan),scope_sha256=identity(scope(plan))))
            db.execute('update gap_meta set complete=1');db.commit()
            binding=json.loads(db.execute('select binding from gap_meta').fetchone()[0]);db.close();return binding
        first=self.root/'old-ns.sqlite';old=namespace(first,'old-inodes')
        path=self.root/'map.sqlite';ns=sqlite3.connect(first)
        with CurrentMap.held(path,binding={'test':'terminal-gap'},create=True) as m:
            m.compile(ns,lambda n:None,SQL_sources=[],checkpoint=lambda:None,maximum_paths=10)
            m.reconcile_namespace(ns,lambda n:None,checkpoint=lambda:None,maximum_paths=10)
            m.db.execute('update namespace_reconciliation set suffix_complete=1')
        ns.close();mapsha=self.import_other(path)
        second=self.root/'new-ns.sqlite';new=namespace(second,'new-inodes');nssha=self.import_other(second)
        mapped=self.client.connect('terminal-map',mapsha);newns=self.client.connect('terminal-ns',nssha)
        q=self.client.connect('terminal-q',self.sha);q.execute('create table versions(name text primary key,row blob)')
        proofs=self.client.connect('terminal-proofs',self.sha);proofs.execute('create table source_terminal_gaps(sha256 text primary key,row text not null) without rowid')
        args=dict(op='reconcile-current-map',name='terminal-map',namespace='terminal-ns',qualifier='terminal-q',maximum_paths=10,allow_unaccepted_epoch_successor=True)
        with self.assertRaisesRegex(ValueError,'terminal gap'):self.client.call(**args)
        proof=dict(format='vk-nightly-closed-source-epoch-gap-v1',old_instance=old['instance'],new_instance=new['instance'],
            **{k:old[k] for k in ('plan_sha256','scope_sha256','required_root_bindings')},old_owner_verified_terminal=True,old_MainPID=0,
            old_committed_sequence=20,old_B_delivered_sequence=18,old_gap_continuity_proven=False,original_epoch_repaired=False,
            current_baseline_accepted=False,complete_later_metadata_required=True,reason='retained source queue fault',old_source_database_sha256='a'*64)
        raw=json.dumps(proof,sort_keys=True,separators=(',',':'));sha=hashlib.sha256(raw.encode()).hexdigest()
        args.update(terminal_epoch_gap_index='terminal-proofs',terminal_epoch_gap_sha256=sha)
        with self.assertRaisesRegex(ValueError,'missing or changed'):self.client.call(**args)
        proofs.execute('insert into source_terminal_gaps values(?,?)',(sha,raw))
        result=self.client.call(**args)
        self.assertFalse(result['current_baseline_accepted']);self.assertTrue(result['journal_suffix_required'])
        self.assertEqual(mapped.execute('select suffix_complete from namespace_reconciliation_history').fetchone(),(1,))
        self.assertEqual(mapped.execute('select suffix_complete from namespace_reconciliation').fetchone(),(0,))
        self.assertTrue(self.client.call(**args)['already_complete'])
        for db in (mapped,newns,q,proofs):db.close()

    def test_native_prefix_attachment_uses_the_retained_base_without_copy_or_acceptance(self):
        import stat
        from vk_nightly_current_map import CurrentMap,decode_member
        from vk_nightly_qualification import encode_observation
        source=self.root/'pending-map.sqlite';ns=sqlite3.connect(':memory:');self.addCleanup(ns.close)
        ns.execute('create table namespace(name text primary key,row blob)')
        meta=dict(mode=0o600,uid=1000,gid=1000,mtime_ns=123,xattrs={})
        obs=dict(meta,kind='file',bytes=3,identity=[1,2,stat.S_IFREG|0o600,3,123,456,1000,1000,1])
        ns.execute('insert into namespace values(?,?)',('home/a',encode_observation(obs)))
        point=dict(source='/home/a',source_identity=obs['identity'],state='qualified-pending-body',row=dict(meta,kind='file',bytes=3,sha256='a'*64))
        ns.execute('create table namespace_errors(name text primary key,error blob)')
        ns.execute('create table gap_meta(id integer primary key,binding text,complete integer)')
        epoch=dict(instance='source-inodes',plan_sha256='b'*64,scope_sha256='c'*64,start_sequence=17,
                   required_root_bindings={'/home':dict(resolved='/home',literal=None)},original_epoch_repaired=False)
        ns.execute('insert into gap_meta values(1,?,1)',(json.dumps(epoch),))
        with CurrentMap.held(source,binding={'test':'prefix'},create=True) as m:
            m.compile(ns,lambda n:point,SQL_sources=[],checkpoint=lambda:None,maximum_paths=10)
            m.reconcile_namespace(ns,lambda n:point,checkpoint=lambda:None,maximum_paths=10)
        digest=self.import_other(source)
        bp=self.root/'base.sqlite';base=sqlite3.connect(bp)
        base.execute('create table provenance(source_catalog_sha256 text,restore_proof_sha256 text)')
        base.execute('insert into provenance values(?,?)',('b'*64,'c'*64))
        base.execute('create table bodies(sha256 text,bytes integer,name text)')
        base.executemany('insert into bodies values(?,?,?)',[('d'*64,2,'home/a'),('a'*64,3,'home/a')]);base.commit();base.close()
        bdigest=self.import_other(bp);base=self.client.connect('base-prefixes',bdigest,readonly=True)
        db=self.client.connect('pending-map',digest)
        reusable=self.client.connect('carrier-reuse-map',digest)
        reused=self.client.call(op='reuse-current-file-carriers',name='carrier-reuse-map',base_index='base-prefixes',recipe_indexes=[],maximum_paths=10)
        self.assertEqual(reused['retained_file_points_reused'],1)
        self.assertEqual(reused['retained_file_bytes_reused'],3)
        self.assertEqual(reused['source_payload_bytes_read'],0);self.assertEqual(reused['backup_payload_bytes_copied'],0)
        self.assertEqual(reusable.execute('select state from members').fetchone(),('verified-file',))
        self.assertEqual(self.client.call(op='reuse-current-file-carriers',name='carrier-reuse-map',base_index='base-prefixes',recipe_indexes=[],maximum_paths=10)['retained_file_points_reused'],0)
        reusable.close()
        result=self.client.call(op='attach-base-prefixes',name='pending-map',base_index='base-prefixes',maximum_paths=128)
        self.assertEqual(result['candidate_prefix_bytes'],2);self.assertEqual(result['backup_payload_bytes_copied'],0)
        state,raw=db.execute('select state,row from members').fetchone()
        self.assertEqual(state,'file-needs-capture');self.assertEqual(decode_member(raw)['candidate_accepted_prefix']['independent_proof_sha256'],'c'*64)
        from vk_nightly_current_map import encode_member
        original=encode_member(dict(source='/home/a',namespace=obs))
        db.execute("update members set state='file-needs-qualification',row=? where name='home/a'",(original,))
        point.update(source_payload_bytes_hashed=3,journal={k:epoch[k] for k in ('instance','plan_sha256','scope_sha256')})
        point['journal']['sequence']=17
        records=[dict(name='home/a',original_sha256=hashlib.sha256(original).hexdigest(),version=point)]
        adopted=self.client.call(op='adopt-qualifications',name='pending-map',base_index='base-prefixes',recipe_indexes=[],records=records)
        self.assertEqual(adopted['retained_body_matches'],1)
        self.assertEqual(self.client.call(op='adopt-qualifications',name='pending-map',base_index='base-prefixes',recipe_indexes=[],records=records)['already_adopted'],1)
        self.assertEqual(db.execute("select state from members where name='home/a'").fetchone(),('verified-file',))
        db.close();base.close()

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

    def test_native_file_acceptance_lost_reply_reopens_without_duplicate_completed_copy(self):
        from vk_nightly_current_map import CurrentMap
        from vk_nightly_namespace import observe
        from vk_nightly_qualification import qualify_file,encode_observation
        from vk_nightly_typed_capture import capture_pending
        source=self.root/'new-point';source.write_bytes(b'actual new point')
        point=qualify_file(source,maximum_bytes=1024,journal=dict(ready=True,errors=[],instance='fixture',
            sequence=1,scope_sha256='a'*64,plan_sha256='b'*64),carriers=lambda *_:[],guard=lambda:None)
        namespace=sqlite3.connect(':memory:');self.addCleanup(namespace.close)
        namespace.execute('create table namespace(name text primary key,row blob)')
        namespace.execute('insert into namespace values(?,?)',(str(source)[1:],encode_observation(observe(source))))
        path=self.root/'pending-map.sqlite';binding={'fixture':'native file point'}
        with CurrentMap.held(path,binding=binding,create=True) as m:
            m.compile(namespace,lambda _:point,SQL_sources=[],checkpoint=lambda:None,maximum_paths=10)
        digest=self.import_other(path)
        folder=str(Path(__file__).parent)
        code='import sys;sys.path.insert(0,'+repr(folder)+');from vk_nightly_objects import receive;receive('+repr(str(self.objects))+',sys.stdin.buffer,sys.stdout.buffer,guard=lambda n:None,maximum_object_bytes=65536)'
        p=subprocess.Popen([sys.executable,'-B','-u','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            body=ObjectClient(p.stdout,p.stdin,guard=lambda:None,ram_root=self.root,maximum_object_bytes=65536)
            with current_map(self.client,'file-point',digest,binding=binding) as m:
                accept=m.accept_file
                def lost(*args,**kwargs):
                    accept(*args,**kwargs);raise EOFError('synthetic lost reply after native atomic commit')
                m.accept_file=lost
                with self.assertRaisesRegex(EOFError,'lost reply'):
                    capture_pending(m,body,guard=lambda:None,maximum_members=2,maximum_source_bytes=1024,chunk_bytes=64)
            uploaded=body.payload_bytes_sent
            with current_map(self.client,'file-point',digest,binding=binding) as m:
                result=capture_pending(m,body,guard=lambda:None,maximum_members=2,maximum_source_bytes=1024,chunk_bytes=64)
                self.assertEqual(result['completed_members'],0);self.assertFalse(result['more_pending'])
                self.assertEqual(m.db.execute('select count(*) from file_acceptance_history').fetchone()[0],1)
            self.assertEqual(body.payload_bytes_sent,uploaded)
        finally:p.stdin.close();p.wait(timeout=10);p.stdout.close();p.stderr.close()

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

    def test_working_inspection_does_not_open_SQL_or_block_an_exclusive_writer(self):
        writer=self.client.connect('inspect-busy',self.sha);writer.execute('begin exclusive')
        other=self.start();value=other.call(op='inspect-working',name='inspect-busy',checkpoint_sha256=self.sha)
        self.assertEqual(value['working_bytes'],len(self.raw));self.assertTrue(value['metadata_only'])
        self.assertFalse(value['content_or_SQL_acceptance']);self.assertGreater(value['allocated_bytes'],0)
        writer.execute('rollback');writer.close()

    def test_native_coarse_namespace_batches_resume_without_source_body_or_SSD_index(self):
        from vk_nightly_gap_namespace import initialize,advance_B
        from vk_prep_common import identity
        from vk_change_journal import scope
        source=self.root/'namespace-source';source.mkdir();(source/'sub').mkdir();(source/'sub'/'file').write_text('fixture')
        for i in range(200):(source/'sub'/('small-'+str(i))).write_text('x')
        plan={'sources':[str(source)]};anchor=dict(ready=True,errors=[],terminal=None,instance='one',sequence=1,
            plan_sha256=identity(plan),scope_sha256=identity(scope(plan)))
        db=self.client.connect('gap-state',self.sha);binding=initialize(db,plan,anchor)
        first=advance_B(self.client,'gap-state',plan,binding,guard=lambda:None,maximum_directories=1,maximum_paths=100)
        self.assertFalse(first['enumeration_complete'])
        final=advance_B(self.client,'gap-state',plan,binding,guard=lambda:None,maximum_directories=100,maximum_paths=1000)
        self.assertTrue(final['enumeration_complete']);self.assertEqual(final['unique_paths'],203)
        self.assertEqual(final['source_body_bytes_read'],0);self.assertEqual(final['work_SSD_index_bytes'],0)
        from vk_nightly_current_map import FORMAT
        current=self.client.connect('map-after-gap',self.sha)
        current.execute('create table metadata(format text,binding text,last_name text,complete integer)')
        current.execute('insert into metadata values(?,?,?,1)',(FORMAT,'{}',''))
        current.execute('create table members(name text primary key,state text,row blob)')
        current.execute('create table SQL_sources(path text primary key)')
        qualifier=self.client.connect('gap-qualified',self.sha)
        qualifier.execute('create table versions(name text primary key,row blob)')
        reconciled=self.client.call(op='reconcile-current-map',name='map-after-gap',namespace='gap-state',
            qualifier='gap-qualified',maximum_paths=1000)
        self.assertEqual(reconciled['member_states'],{'directory':2,'file-needs-qualification':201})
        self.assertTrue(reconciled['journal_suffix_required'])
        # Explicitly expanding scope needs an actual hash-authenticated row
        # in the leased native proof index; a caller flag is insufficient.
        outside=self.root/'new-source';outside.write_bytes(b'x')
        expanded=dict(sources=[str(source),str(outside)])
        newanchor=dict(anchor,instance='two',sequence=10,plan_sha256=identity(expanded),scope_sha256=identity(scope(expanded)))
        later=self.client.connect('gap-expanded',self.sha);later_binding=initialize(later,expanded,newanchor)
        advance_B(self.client,'gap-expanded',expanded,later_binding,guard=lambda:None,maximum_directories=100,maximum_paths=1000)
        def window(b,instance,seq,full):
            return dict(plan_sha256=b['plan_sha256'],scope_sha256=b['scope_sha256'],instance=instance,
                        since=0,sequence=seq,ready=True,errors=[],terminal=None,
                        coverage_model='all-selected-inodes-v1' if full else 'directory-namespace-only-v1',
                        barrier=dict(kernel_drain_completed=True,durable_sequence=seq,instance=instance))
        proof=dict(format='vk-nightly-additive-full-inode-overlap-v1',baseline_accepted=False,
                   old_hardlink_and_alias_gap_repaired=False,full_gap_metadata_reconciliation_required=True,
                   old_required_root_bindings=binding['required_root_bindings'],new_required_root_bindings=later_binding['required_root_bindings'],
                   added_roots=[str(outside)],old_namespace=window(binding,'one',2,False),
                   new_before=window(later_binding,'two',3,True),new_after=window(later_binding,'two',4,True))
        raw=json.dumps(proof,sort_keys=True,separators=(',',':'));digest=hashlib.sha256(raw.encode()).hexdigest()
        proofs=self.client.connect('scope-proof',self.sha)
        proofs.execute('create table source_outbox_handovers_inodes_v9(sha256 text primary key,row text)')
        proofs.execute('insert into source_outbox_handovers_inodes_v9 values(?,?)',('0'*64,raw))
        args=dict(op='reconcile-current-map',name='map-after-gap',namespace='gap-expanded',qualifier='gap-qualified',
                  maximum_paths=1000,allow_unaccepted_epoch_successor=True,source_scope_extension_index='scope-proof')
        with self.assertRaisesRegex(ValueError,'scope-extension proof missing or changed'):
            self.client.call(**args,source_scope_extension_proof_sha256='0'*64)
        proofs.execute('insert into source_outbox_handovers_inodes_v9 values(?,?)',(digest,raw))
        result=self.client.call(**args,source_scope_extension_proof_sha256=digest)
        self.assertEqual(result['member_states'],{'directory':2,'file-needs-qualification':202})
        self.assertEqual(current.execute('select sha256 from namespace_scope_extensions').fetchall(),[(digest,)])
        self.assertTrue(result['journal_suffix_required']);self.assertFalse(result['current_baseline_accepted'])
        later.close();proofs.close();current.close();qualifier.close();db.close()

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
