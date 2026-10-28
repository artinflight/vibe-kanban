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

    def test_query_metrics_measure_roundtrips_without_recording_SQL_or_parameters(self):
        db=self.client.connect('metric-fixture',self.sha)
        try:
            self.assertEqual(db.execute('select value from point where id=?',(123456789,)).fetchall(),[])
            value=self.client.metrics()
            self.assertGreaterEqual(value['operations']['execute']['requests'],1)
            self.assertGreaterEqual(value['operations']['fetch']['requests'],1)
            self.assertGreater(value['wait_seconds'],0)
            self.assertNotIn('123456789',json.dumps(value));self.assertNotIn('select value',json.dumps(value))
        finally:db.close()

    def test_scheduled_daily_SQL_index_opens_and_reopens_through_actual_native_protocol(self):
        from vk_nightly_service import scheduled_cycle
        template=dict(cycle=dict(cycle_binding=dict(cycle_kind='incremental'),
            SQL=dict(SQL_phase_index=dict(index_name='template',checkpoint_sha256=self.sha)),finalize={}))
        value=scheduled_cycle(template,'2026-10-27','4'*64)
        ref=value['cycle']['SQL']['SQL_phase_index']
        db=self.client.connect(ref['index_name'],ref['checkpoint_sha256'])
        db.execute('insert into point values(1,?)',(b'completed fixture SQL point',));db.close()
        again=scheduled_cycle(template,'2026-10-27','4'*64)['cycle']['SQL']['SQL_phase_index']
        db=self.client.connect(again['index_name'],again['checkpoint_sha256'],readonly=True,working=True)
        self.assertEqual(db.execute('select value from point').fetchall(),[(b'completed fixture SQL point',)])
        db.close()
        later=scheduled_cycle(template,'2026-10-28','4'*64)['cycle']['SQL']['SQL_phase_index']
        db=self.client.connect(later['index_name'],later['checkpoint_sha256'])
        self.assertEqual(db.execute('select value from point').fetchall(),[]);db.close()

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
                        controls={'B_root':target['B_root'],'maximum_index_bytes':8*1024**2},maximum_B_index_bytes=8*1024**2)
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
            from vk_nightly_file_cycle import Source
            plan=self.root/'source-plan.json';plan.write_text(json.dumps({'sources':[str(source)]}));plan.chmod(0o600)
            consumer_config=self.root/'source-config.json'
            consumer_config.write_text(json.dumps(dict(plan=str(plan),plan_sha256=hashlib.sha256(plan.read_bytes()).hexdigest(),
                status=str(status),endpoint=str(endpoint),B_delivery_target=target)))
            consumer_config.chmod(0o600)
            consumer=Source(dict(config=str(consumer_config),sha256=hashlib.sha256(consumer_config.read_bytes()).hexdigest(),
                instance=instance),config['controls'],guard=lambda:None)
            # Exercise the actual new between-run wrapper over real inotify,
            # native FULL transactions, independent reopen and source ACK.
            from vk_nightly_journal_delivery import deliver
            from vk_nightly_commission import journal_qualification
            binding=dict(service_sha256='a'*64,entrypoint_sha256='b'*64,
                source_observer=consumer.reference,B_delivery_target=target,legacy_owners_sha256='c'*64)
            (source/'changed-again').write_bytes(b'second bounded fixture generation')
            with patch('vk_nightly_outbox_collector.DesktopControls',remote):
                delivery=deliver(consumer,binding=binding,guard=lambda:None)
            proof=journal_qualification(self.client,consumer,delivery,
                service_sha='a'*64,script_sha='b'*64,legacy_sha='c'*64)
            self.assertTrue(proof['actual_B_journal_reopen_verified'])
            wrong=dict(delivery,binding=dict(binding,service_sha256='d'*64))
            with self.assertRaises(ValueError):journal_qualification(self.client,consumer,wrong,
                service_sha='a'*64,script_sha='b'*64,legacy_sha='c'*64)
            result=delivery['delivery']
            self.assertTrue(consumer.report(self.client)['barrier']['kernel_drain_completed'])
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

    def seal_request(self,key,binding):
        request=dict(format='vk-nightly-B-working-checkpoint-v1',index=key,binding=binding)
        digest=hashlib.sha256(json.dumps(request,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        return dict(request_sha256=digest,binding=binding)

    def test_native_seal_independent_readback_immutable_reopen_and_lost_reply_reuse(self):
        db=self.client.connect('live-map',self.sha)
        db.execute('insert into point values(1,?)',(b'current accepted fixture point',))
        request=self.seal_request('live-map',dict(instance='epoch',sequence=123))
        first=db.request('seal-working',**request)
        self.assertEqual(first['status'],'needs_independent_readback')
        image=self.controls/(first['sha256']+'.sqlite');original_image=image.read_bytes()
        self.assertFalse(image.with_suffix('.import.json').exists())
        self.assertEqual(self.client.readback(first['sha256']),first['bytes'])
        self.client.call(op='acknowledge',sha256=first['sha256'],independent_stream_sha256=first['sha256'],Linux_metadata=first['Linux_metadata'])
        files=set(self.controls.iterdir())
        # Simulate a lost response and later working progress: same request
        # must return the original image, not silently capture a later epoch.
        db.execute('insert into point values(2,?)',(b'later point',));db.close()
        other=self.start();live=other.connect('live-map',self.sha)
        reused=live.request('seal-working',**request)
        self.assertTrue(reused['reused_completed_snapshot'])
        self.assertEqual(reused['sha256'],first['sha256']);self.assertEqual(set(self.controls.iterdir()),files)
        self.assertEqual(image.read_bytes(),original_image);live.close()
        view=other.connect('sealed-view',first['sha256'],readonly=True)
        self.assertEqual(view.execute('select id,value from point').fetchall(),[(1,b'current accepted fixture point')]);view.close()

    def test_normal_incremental_suffix_uses_real_inode_events_and_native_B_resume(self):
        from test_vk_nightly_recovery_descriptor import fixture,current_view
        from vk_nightly_inode_journal import Journal
        from vk_nightly_tracking import FORMAT as TRACKING_FORMAT,source_bindings
        from vk_nightly_namespace import replay_metadata,observe
        from vk_nightly_outbox_export import export
        from vk_nightly_incremental import advance_suffix
        from vk_prep_common import identity
        from vk_change_journal import scope
        root=self.root/'ordinary-cycle';root.mkdir()
        db,path,_,rows,body,_=fixture(root)
        source=root/'source';source.mkdir()
        (source/'note').write_bytes((body/'note').read_bytes())
        (source/'untouched').write_bytes((body/'note').read_bytes())
        plan={'sources':[str(source)]};journal=Journal(plan);self.addCleanup(journal.close)
        journal.tree(source);journal.ready=True
        def report(since):
            value=journal.report(since)
            return dict(value,format=TRACKING_FORMAT,plan_sha256=identity(plan),since=since,terminal=None,
                barrier=dict(instance=value['instance'],durable_sequence=value['sequence'],kernel_drain_completed=True))
        initial=report(0);binding=dict(instance=initial['instance'],start_sequence=initial['sequence'],
            plan_sha256=identity(plan),scope_sha256=identity(scope(plan)),required_root_bindings=source_bindings(plan))
        # The fixture's accepted member image is prepared on RAM, not a real
        # production baseline. Native import/independent stream ACK are real.
        db.execute('delete from members')
        from vk_nightly_current_map import encode_member
        prefix=str(source)[1:]
        db.execute('insert into members values(?,?,?)',(prefix,'directory',encode_member(dict(member=rows['home/state']))))
        for name in ('note','untouched'):
            db.execute('insert into members values(?,?,?)',(prefix+'/'+name,'verified-file',encode_member(dict(member=rows['home/state/note']))))
        db.execute('update namespace_reconciliation set binding=?',(json.dumps(binding),))
        db.execute('delete from namespace_replay_windows');db.execute('delete from namespace_replay_inputs')
        current_view(db,path).apply_metadata_replay(initial,replay_metadata(plan,initial,instance=initial['instance'],
            since=initial['sequence'],maximum_paths=16,checkpoint=lambda:None),checkpoint=lambda:None,maximum_paths=16)
        db.close();digest=self.import_other(path)
        native_binding=dict(initial,owner_pid=os.getpid())
        def deliver(since):
            value=report(since)
            with tracking_store(self.client,'ordinary-journal',self.sha,maximum_bytes=8*1024**2) as ledger:
                return export(native_binding,value,ledger,guard=lambda:None)
        deliver(0)
        (source/'note').write_bytes(b'actual current version')
        delivered=deliver(initial['sequence'])
        args=dict(index_name='ordinary-map',checkpoint_sha256=digest,journal_name='ordinary-journal',
            journal_checkpoint_sha256=self.sha,plan=plan,maximum_paths=16,maximum_journal_bytes=8*1024**2,guard=lambda:None)
        with patch('vk_nightly_namespace.os.walk',side_effect=AssertionError('unchanged workspace walked')),patch('vk_nightly_namespace.observe',wraps=observe) as observed:
            result=advance_suffix(self.client,**args)
            self.assertEqual([str(call.args[0]) for call in observed.call_args_list],[str(source/'note')])
        self.assertTrue(result['normal_B_metadata_reopen_verified']);self.assertEqual(result['through'],delivered['sequence'])
        self.assertEqual(result['global_namespace_audits_started'],0);self.assertEqual(result['source_body_bytes_read'],0)
        view=self.client.connect('ordinary-map',digest,readonly=True,working=True)
        self.assertEqual(view.execute('select state from members where name=?',(prefix+'/untouched',)).fetchone(),('verified-file',))
        self.assertEqual(view.execute('select state from members where name=?',(prefix+'/note',)).fetchone(),('file-needs-qualification',));view.close()
        with patch('vk_nightly_namespace.observe',side_effect=AssertionError('unchanged metadata sampled')):
            empty=advance_suffix(self.client,**args)
        self.assertEqual(empty['replayed_paths'],0)
        (source/'note').write_bytes(b'later point after retained checkpoint')
        deliver(delivered['sequence'])
        real_call=self.client.call
        def lost_reply(**query):
            answer=real_call(**query)
            if query['op']=='replay-current-map':raise TimeoutError('injected after native commit')
            return answer
        with patch.object(self.client,'call',side_effect=lost_reply):
            with self.assertRaisesRegex(TimeoutError,'after native commit'):advance_suffix(self.client,**args)
        with patch('vk_nightly_namespace.observe',side_effect=AssertionError('completed metadata replayed')):
            resumed=advance_suffix(self.client,**args)
        self.assertTrue(resumed['normal_B_metadata_reopen_verified'])
        view=self.client.connect('ordinary-map',digest,readonly=True,working=True)
        self.assertEqual(view.execute('select count(*) from members').fetchone(),(3,))
        self.assertEqual(view.execute('select count(*) from namespace_replay_history where name=?',(prefix+'/note',)).fetchone(),(2,))
        view.close()

    def test_actual_native_runtime_component_adoption_seal_and_complete_descriptor(self):
        from test_vk_nightly_recovery_descriptor import fixture,runtime_fixture
        from vk_nightly_b_controls import NativeControlError
        root=self.root/'native-runtime';root.mkdir()
        db,path,contract,_,body,_=fixture(root);db.close()
        runtime,runtime_path,expected,source,_=runtime_fixture(root,body);runtime.close()
        main_sha=self.import_other(path);component_sha=self.import_other(runtime_path)
        main=self.client.connect('runtime-main',main_sha)
        reference=dict(format='vk-nightly-current-member-map-v1',layer='nightly-controls-v1',
            selector=component_sha+'.sqlite',sha256=component_sha,bytes=runtime_path.stat().st_size)
        mutable=self.client.connect('runtime-mutable',component_sha)
        with self.assertRaisesRegex(NativeControlError,'accepted immutable runtime'):
            main.request('adopt-runtime-component',component_index=mutable.key,component_reference=reference,expected_files=expected)
        mutable.close()
        component=self.client.connect('runtime-immutable',component_sha,readonly=True)
        altered={p:dict(row,source_identity=[0]*9) for p,row in expected.items()}
        with self.assertRaisesRegex(NativeControlError,'current source pins'):
            main.request('adopt-runtime-component',component_index=component.key,component_reference=reference,expected_files=altered)
        adopted=main.request('adopt-runtime-component',component_index=component.key,component_reference=reference,expected_files=expected)
        self.assertFalse(adopted['kernel_journal_coverage_claimed']);self.assertEqual(adopted['backup_payload_bytes_copied'],0)
        sealed=self.client.seal_checkpoint(main.key,dict(runtime=adopted['always_runtime_files']));main.close();component.close()
        contract['dependencies']['nightly-controls-v1']['native_root']=str(self.controls)
        contract['always_runtime_files']=adopted['always_runtime_files']
        view=self.client.connect('runtime-descriptor',sealed['sha256'],readonly=True)
        reference=dict(format='vk-nightly-current-member-map-v1',layer='nightly-controls-v1',
            selector=sealed['sha256']+'.sqlite',sha256=sealed['sha256'],bytes=sealed['bytes'])
        descriptor=view.request('build-current-descriptor',reference=reference,consumer_contract=contract)
        self.assertEqual(descriptor['always_runtime_files'],adopted['always_runtime_files'])
        self.assertEqual(descriptor['sources'],['/home/state']);self.assertFalse(descriptor['independent_current_restore_accepted'])
        view.close()

    def test_serial_runtime_capture_normal_readback_adoption_and_completed_reuse(self):
        import vk_nightly_runtime_cycle as cycle
        import vk_nightly_typed_worker as worker
        from test_vk_nightly_recovery_descriptor import fixture,runtime_fixture
        from vk_nightly_current_map import decode_member,encode_member
        root=self.root/'runtime-cycle';root.mkdir()
        main,path,_,_,body,_=fixture(root);main.close();mainsha=self.import_other(path)
        component,cp,_,source,_=runtime_fixture(root,body)
        binding=json.loads(component.execute('select binding from metadata').fetchone()[0])
        component.execute('update metadata set binding=?',(json.dumps(binding,sort_keys=True,separators=(',',':')),))
        row=decode_member(component.execute('select row from members').fetchone()[0]);row.pop('independent_file_proof')
        row['member'].pop('segments');row['qualification']['row']=row['member'];row['qualification']['state']='qualified-pending-body'
        component.execute("update members set state='file-needs-capture',row=?",(encode_member(row),));component.close()
        componentsha=self.import_other(cp)
        self.client.connect('runtime-cycle-component',componentsha).close()
        config=dict(format='vk-nightly-typed-worker-B-v1',B_controls={},B_index_name='runtime-cycle-component',
            B_checkpoint_sha256=componentsha,map_binding=binding,status=str(self.root/'runtime-cycle-status'),
            desktop={},maximum_members=2,maximum_source_bytes=1024,chunk_bytes=4096)
        controls=dict(source_observer={},SQL_predecessor={'config':'fixture','config_sha256':'a'*64},
            maximum_predecessor_seconds=60,runtime_paths=[str(source)],component_layer='nightly-controls-v1',
            main_map=dict(index_name='runtime-cycle-main',checkpoint_sha256=mainsha))
        source_owner=SimpleNamespace(check=lambda:None,deliver=lambda:{'instance':'fixture-current'})
        @contextmanager
        def native(*_,**__):yield SimpleNamespace(client=self.client)
        code=('import sys;sys.path.insert(0,'+repr(str(Path(__file__).parent))+');from vk_nightly_objects import receive;receive('
            +repr(str(self.objects))+',sys.stdin.buffer,sys.stdout.buffer,guard=lambda n:None,maximum_object_bytes=65536)')
        process=subprocess.Popen([sys.executable,'-B','-u','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        objects=ObjectClient(process.stdout,process.stdin,guard=lambda:None,ram_root=self.root,maximum_object_bytes=65536)
        @contextmanager
        def remote(*_,**__):yield SimpleNamespace(client=objects,ready={'fixture':'normal object protocol'})
        try:
            with patch.object(cycle,'Source',return_value=source_owner),patch.object(cycle,'read_owned'),\
                 patch.object(cycle,'predecessor'),patch.object(cycle,'host_guard'),patch.object(cycle,'DesktopControls',native),\
                 patch.object(worker,'host_guard'),patch.object(worker,'DesktopControls',native),patch.object(worker,'DesktopObjects',remote):
                result=cycle.run(controls,config,report=lambda _:None)
                self.assertTrue(result['actual_independent_B_runtime_component_reopen_verified'])
                self.assertEqual(result['captured']['completed_members'],1)
                self.assertFalse(result['kernel_journal_coverage_claimed']);self.assertFalse(result['baseline_accepted'])
                sent=objects.payload_bytes_sent
                resumed=cycle.run(controls,config,report=lambda _:None)
                self.assertEqual(resumed['captured']['completed_members'],0)
                self.assertEqual(objects.payload_bytes_sent,sent)
                source.write_bytes(b'new actual source version')
                with patch.object(cycle,'run_B') as capture:
                    with self.assertRaisesRegex(ValueError,'prepared runtime point changed'):
                        cycle.run(controls,config,report=lambda _:None)
                    capture.assert_not_called()
        finally:
            process.stdin.close();self.assertEqual(process.wait(timeout=10),0);process.stdout.close();process.stderr.close()

    def test_actual_native_immutable_provider_builds_complete_descriptor_and_refuses_draft(self):
        from test_vk_nightly_recovery_descriptor import fixture
        from vk_nightly_b_controls import NativeControlError
        root=self.root/'descriptor-fixture';root.mkdir()
        db,path,contract,rows,_,_=fixture(root,SQL=True);db.close()
        digest=self.import_other(path);contract['dependencies']['nightly-controls-v1']['native_root']=str(self.controls)
        reference=dict(format='vk-nightly-current-member-map-v1',layer='nightly-controls-v1',selector=digest+'.sqlite',
            bytes=path.stat().st_size,sha256=digest)
        view=self.client.connect('descriptor-read',digest,readonly=True)
        misplaced=json.loads(json.dumps(contract));misplaced['dependencies']['nightly-controls-v1']['native_root']='/mnt/b/not-the-native-admitted-root'
        with self.assertRaisesRegex(NativeControlError,'exact admitted immutable B control reference'):
            view.request('build-current-descriptor',reference=reference,consumer_contract=misplaced)
        result=view.request('build-current-descriptor',reference=reference,consumer_contract=contract)
        self.assertEqual(result['member_count'],len(rows));self.assertFalse(result['independent_current_restore_accepted'])
        self.assertEqual(result['journal']['end'],20)
        with self.assertRaisesRegex(NativeControlError,'exact admitted immutable'):
            view.request('build-current-descriptor',reference=dict(reference,sha256='f'*64),consumer_contract=contract)
        view.close()
        draft=self.client.connect('descriptor-draft',digest)
        with self.assertRaisesRegex(NativeControlError,'accepted immutable checkpoint'):
            draft.request('build-current-descriptor',reference=reference,consumer_contract=contract)
        draft.close()

    def test_SQL_contract_discovery_requires_exact_independent_native_map_scope_and_roots(self):
        import copy
        from test_vk_nightly_recovery_descriptor import fixture
        from vk_nightly_finalize_current import bind_SQL_scope
        from vk_typed_recovery import checksum
        root=self.root/'SQL-contract';root.mkdir()
        db,path,contract,_,_,_=fixture(root,SQL=True)
        namespace=json.loads(db.execute('select binding from namespace_reconciliation').fetchone()[0]);db.close()
        digest=self.import_other(path);ref=dict(index_name='SQL-contract-map'.lower(),checkpoint_sha256=digest)
        db=self.client.connect(ref['index_name'],ref['checkpoint_sha256']);db.close()
        request=dict(binding=dict(source_instance=namespace['instance'],
            source_root_bindings=namespace['required_root_bindings'],plan_sha256=contract['plan_sha256'],
            scope_sha256=contract['scope_sha256']),SQL_scope_sources=list(contract['required_SQL']))
        request['cohort_id']=checksum(request)
        template=dict(contract,required_SQL=None,SQL_scope_authority='authenticated-current-map-and-cohort-v1')
        actual=copy.deepcopy(template)
        bind_SQL_scope(self.client,ref,actual,request,guard=lambda:None)
        self.assertEqual(actual['required_SQL'],contract['required_SQL'])
        self.assertIsNone(template['required_SQL'])
        for change in ['omission','root','epoch','digest']:
            wrong=copy.deepcopy(request)
            if change=='omission':wrong['SQL_scope_sources']=[]
            elif change=='root':wrong['binding']['source_root_bindings']={}
            elif change=='epoch':wrong['binding']['source_instance']='other'
            if change!='digest':wrong['cohort_id']=checksum({k:v for k,v in wrong.items() if k!='cohort_id'})
            else:wrong['cohort_id']='0'*64
            with self.assertRaises(ValueError):
                bind_SQL_scope(self.client,ref,copy.deepcopy(template),wrong,guard=lambda:None)
        db=self.client.connect(ref['index_name'],ref['checkpoint_sha256'])
        db.execute("insert into SQL_sources values('/home/state/unaccounted.sqlite')");db.close()
        with self.assertRaisesRegex(ValueError,'complete independently reopened'):
            bind_SQL_scope(self.client,ref,copy.deepcopy(template),request,guard=lambda:None)

    def finalization_fixture(self):
        from test_vk_nightly_recovery_descriptor import fixture
        root=self.root/'finalizer';root.mkdir()
        db,path,contract,rows,body,_=fixture(root);db.close();mapsha=self.import_other(path)
        contract['dependencies']['nightly-controls-v1']['native_root']=str(self.controls)
        catalog=self.root/'finalizer-base.sqlite'
        with sqlite3.connect(catalog) as db:
            db.execute('create table provenance(source_catalog_sha256 text,restore_proof_sha256 text)')
            db.execute('insert into provenance values(?,?)',('a'*64,'b'*64))
            db.execute('create table bodies(sha256 text,bytes integer,name text)')
            note=rows['home/state/note'];db.execute('insert into bodies values(?,?,?)',(note['sha256'],note['bytes'],'note'))
        db.close();base=self.import_other(catalog)
        settings=dict(current_map=dict(index_name='finalizer-main',checkpoint_sha256=mapsha),map_layer='nightly-controls-v1',
            contract=contract,cycle_binding=dict(source_instance='fixture-current',through=20),
            base_catalog=dict(checkpoint_sha256=base,bytes=catalog.stat().st_size),recipe_catalogs=[],guard=lambda:None)
        return settings,body,rows

    def test_actual_native_finalize_to_executable_normal_composed_restore(self):
        from datetime import datetime,timedelta,timezone
        from vk_nightly_finalize_current import finalize,consumer_packet
        from vk_nightly_composed_consumer import run
        from vk_typed_recovery import checksum
        settings,body,rows=self.finalization_fixture();progress=[]
        result=finalize(self.client,**settings,report=progress.append)
        self.assertEqual(result['content_proof']['file_points'],1)
        self.assertTrue(result['sealed_map']['independent_stream_readback_verified'])
        self.assertFalse(result['whole_baseline_accepted']);self.assertTrue(progress)
        again=finalize(self.client,**settings)
        self.assertEqual(again['descriptor_sha256'],result['descriptor_sha256'])
        self.assertTrue(again['sealed_map']['reused_completed_snapshot'])
        # Only this fixture creates the normal POSIX lease. Production must
        # supply its independently admitted existing provider leases.
        (self.controls/'RECOVERY_READ.lease').touch()
        roots={'accepted-base':str(body),'nightly-controls-v1':str(self.controls)}
        placement=dict(roots=roots,expected_uid=os.getuid(),expected_gid=os.getgid(),
            root_bindings={k:[Path(p).stat().st_dev,Path(p).stat().st_ino] for k,p in roots.items()},
            lease_paths={k:str(Path(p)/'RECOVERY_READ.lease') for k,p in roots.items()})
        packet=consumer_packet(result,provider_placement=placement,readback_sources=['/home/state/note'],
            scratch_parent=str(self.root),maximum_scratch_bytes=17*1024**2,maximum_readback_bytes=1024**2,
            remaining_seconds=30,whole_cycle_deadline_UTC=(datetime.now(timezone.utc)+timedelta(seconds=30)).isoformat(),
            Linux_resource_admission=dict(memory_floor_bytes=0,swap_floor_bytes=0))
        accepted=run(packet,checksum(packet),guard=lambda:None)
        self.assertTrue(accepted['independent_composed_restore_verified'])
        self.assertEqual(accepted['complete_file_points_verified'],1)
        self.assertEqual(accepted['actual_selected_restore_bytes'],rows['home/state/note']['bytes'])
        self.assertFalse(accepted['original_epoch_complete']);self.assertFalse(accepted['schedule_enabled'])

    def test_selected_provider_pool_finalizes_and_restores_only_actual_dependencies(self):
        from datetime import datetime,timedelta,timezone
        from vk_nightly_finalize_current import finalize,consumer_packet
        from vk_nightly_composed_consumer import run
        from vk_typed_recovery import checksum
        import copy
        settings,body,_=self.finalization_fixture()
        contract=settings['contract'];contract['dependency_selection_authority']='sealed-map-recipes-v1'
        contract['dependencies']['unused-older-archive']={'accepted_proof_sha256':'e'*64}
        before=copy.deepcopy(contract)
        result=finalize(self.client,**settings)
        self.assertEqual(contract,before) # The installed template remains immutable.
        self.assertNotIn('unused-older-archive',result['consumer_contract']['dependencies'])
        self.assertEqual(result['consumer_contract_sha256'],checksum(result['consumer_contract']))
        self.assertNotEqual(result['sealed_template_contract_sha256'],result['consumer_contract_sha256'])
        (self.controls/'RECOVERY_READ.lease').touch()
        roots={'accepted-base':str(body),'nightly-controls-v1':str(self.controls),'unused-older-archive':'/not-admitted-or-read'}
        placement=dict(roots=roots,expected_uid=os.getuid(),expected_gid=os.getgid(),
            root_bindings={k:[Path(v).stat().st_dev,Path(v).stat().st_ino] for k,v in roots.items() if k!='unused-older-archive'},
            lease_paths={k:str(Path(v)/'RECOVERY_READ.lease') for k,v in roots.items() if k!='unused-older-archive'})
        packet=consumer_packet(result,provider_placement=placement,readback_sources=['/home/state/note'],
            scratch_parent=str(self.root),maximum_scratch_bytes=17*1024**2,maximum_readback_bytes=1024**2,
            remaining_seconds=30,whole_cycle_deadline_UTC=(datetime.now(timezone.utc)+timedelta(seconds=30)).isoformat(),
            Linux_resource_admission=dict(memory_floor_bytes=0,swap_floor_bytes=0))
        self.assertNotIn('unused-older-archive',packet['provider_placement']['roots'])
        self.assertIn('unused-older-archive',placement['roots'])
        self.assertTrue(run(packet,checksum(packet),guard=lambda:None)['independent_composed_restore_verified'])
        del placement['lease_paths']['accepted-base']
        with self.assertRaisesRegex(ValueError,'selected provider lacks'):
            consumer_packet(result,provider_placement=placement,readback_sources=[],scratch_parent=str(self.root),
                maximum_scratch_bytes=1,maximum_readback_bytes=1,remaining_seconds=30,
                whole_cycle_deadline_UTC='2026-10-28T08:00:00+00:00',Linux_resource_admission={})

    def test_runtime_late_binding_reopens_actual_B_points_and_rejects_changed_scope_or_pin(self):
        import copy
        from test_vk_nightly_recovery_descriptor import runtime_fixture
        from vk_nightly_finalize_current import bind_runtime_scope
        settings,body,_=self.finalization_fixture()
        root=self.root/'runtime-binding';(root/'controls').mkdir(parents=True)
        component,path,expected,source,_=runtime_fixture(root,body)
        component.close();sha=self.import_other(path)
        reference=dict(format='vk-nightly-current-member-map-v1',layer='nightly-controls-v1',
            selector=sha+'.sqlite',sha256=sha,bytes=path.stat().st_size)
        view=self.client.connect('actual-runtime-component',sha,readonly=True)
        main=self.client.connect(settings['current_map']['index_name'],settings['current_map']['checkpoint_sha256'])
        try:
            result=main.request('adopt-runtime-component',component_index=view.key,component_reference=reference,expected_files=expected)
        finally:main.close();view.close()
        result.update(component_reference=reference,actual_independent_B_runtime_component_reopen_verified=True)
        template=dict(runtime_scope_authority='authenticated-runtime-component-v1',always_runtime_files=None,
            required_runtime_points=expected)
        contract=copy.deepcopy(template)
        bind_runtime_scope(self.client,settings['current_map'],contract,result,guard=lambda:None)
        self.assertEqual(contract['always_runtime_files'],result['always_runtime_files'])
        for mutation in ('pin','scope','component','proof','result'):
            c=copy.deepcopy(template);r=copy.deepcopy(result)
            if mutation=='pin':c['required_runtime_points'][str(source)]['sha256']='a'*64
            if mutation=='scope':c['required_runtime_points']['/another']={}
            if mutation=='component':r['component_reference']['sha256']='b'*64
            if mutation=='proof':r['actual_independent_B_runtime_component_reopen_verified']=False
            if mutation=='result':r['always_runtime_files'][str(source)]['independent_proof_sha256']='c'*64
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                bind_runtime_scope(self.client,settings['current_map'],c,r,guard=lambda:None)

    def test_finalizer_refuses_unresolved_points_before_seal_and_requires_SQL_request(self):
        from vk_nightly_finalize_current import finalize
        settings,_,_=self.finalization_fixture()
        db=self.client.connect(settings['current_map']['index_name'],settings['current_map']['checkpoint_sha256'])
        db.execute("update members set state='file-needs-capture' where name='home/state/note'");db.close()
        with patch.object(self.client,'seal_checkpoint',side_effect=AssertionError('unfinished map copied')):
            with self.assertRaisesRegex(ValueError,'unresolved required map points'):finalize(self.client,**settings)
        settings['contract']['required_SQL']=['/home/state/needed.sqlite']
        with self.assertRaisesRegex(ValueError,'current SQL request required'):finalize(self.client,**settings)

    def cycle_fixture(self):
        from datetime import datetime,timedelta,timezone
        from vk_nightly_cycle_state import CycleState
        from vk_nightly_finalize_current import finalize,consumer_packet
        from vk_nightly_composed_consumer import run
        from vk_typed_recovery import checksum
        settings,body,_=self.finalization_fixture();calls=[]
        (self.controls/'RECOVERY_READ.lease').touch()
        roots={'accepted-base':str(body),'nightly-controls-v1':str(self.controls)}
        placement=dict(roots=roots,expected_uid=os.getuid(),expected_gid=os.getgid(),
            root_bindings={k:[Path(p).stat().st_dev,Path(p).stat().st_ino] for k,p in roots.items()},
            lease_paths={k:str(Path(p)/'RECOVERY_READ.lease') for k,p in roots.items()})
        now=[datetime.now(timezone.utc)]
        binding=dict(started_UTC=now[0].isoformat(),deadline_UTC=(now[0]+timedelta(seconds=120)).isoformat(),
            previous_accepted_sha256=None,source_instance='actual-RAM-native-fixture',config_sha256='1'*64)
        store=CycleState(self.client,dict(index_name='cycle-ledger',checkpoint_sha256=self.sha),guard=lambda:None)
        def phase(name,field):
            def completed(*_):
                calls.append(name);return {field:True,'more_pending':False}
            return completed
        def candidate(results,deadline,guard):
            calls.append('candidate');value=finalize(self.client,**dict(settings,guard=guard))
            packet=consumer_packet(value,provider_placement=placement,readback_sources=['/home/state/note'],
                scratch_parent=str(self.root),maximum_scratch_bytes=17*1024**2,maximum_readback_bytes=1024**2,
                remaining_seconds=120,whole_cycle_deadline_UTC=deadline,
                Linux_resource_admission=dict(memory_floor_bytes=0,swap_floor_bytes=0))
            return dict(candidate=value,packet=packet)
        def restore(results,deadline,guard):
            calls.append('restore');packet=results['candidate']['packet']
            return run(packet,checksum(packet),guard=guard)
        adapters=dict(files=phase('files','actual_independent_B_file_cycle_receipt_reopen_verified'),
            SQL=phase('SQL','actual_independent_B_SQL_cycle_receipt_reopen_verified'),
            runtime=phase('runtime','actual_independent_B_runtime_component_reopen_verified'),
            finalize=candidate,restore=restore,guard=lambda:None,now=lambda:now[0])
        return store,binding,adapters,calls,now

    def test_controlled_body_resume_requires_exact_latest_completed_retained_input(self):
        from vk_nightly_file_cycle import retained_suffix
        from test_vk_nightly_recovery_descriptor import fixture
        from vk_nightly_b_controls import NativeControlError
        root=self.root/'resume';root.mkdir()
        db,path,contract,*_=fixture(root)
        binding=json.loads(db.execute('select binding from namespace_reconciliation where id=1').fetchone()[0])
        from vk_change_journal import scope
        from vk_prep_common import identity
        from vk_nightly_metadata_replay import load_input
        plan={'sources':contract['sources']};binding.update(plan_sha256=identity(plan),scope_sha256=identity(scope(plan)))
        old=db.execute('select sha256 from namespace_replay_windows').fetchone()[0]
        value=load_input(db,old,guard=lambda:None);value['report'].update(plan_sha256=binding['plan_sha256'],scope_sha256=binding['scope_sha256'])
        raw=json.dumps(value,sort_keys=True,separators=(',',':')).encode();sha=hashlib.sha256(raw).hexdigest()
        summary=json.loads(db.execute('select summary from namespace_replay_windows').fetchone()[0]);summary['window_sha256']=sha
        db.execute('update namespace_reconciliation set binding=?',(json.dumps(binding),))
        db.execute('update namespace_replay_windows set sha256=?,summary=?',(sha,json.dumps(summary)))
        db.execute('update namespace_replay_inputs set sha256=?,data=?',(sha,raw))
        db.close();base=self.import_other(path)
        worker=dict(B_index_name='resume-main',B_checkpoint_sha256=base)
        view=self.client.connect('resume-main',base);view.close()
        source=SimpleNamespace(reference=dict(instance=binding['instance']),plan=plan)
        result=retained_suffix(self.client,worker,source,sha,guard=lambda:None)
        self.assertTrue(result['resumed_retained_qualified_input']);self.assertEqual(result['source_body_bytes_read'],0)
        self.assertEqual(result['global_namespace_audits_started'],0)
        with self.assertRaises((ValueError,NativeControlError)):
            retained_suffix(self.client,worker,source,'0'*64,guard=lambda:None)
        source.reference['instance']='different-observer'
        with self.assertRaisesRegex(ValueError,'latest committed suffix'):
            retained_suffix(self.client,worker,source,sha,guard=lambda:None)

    def test_actual_native_cycle_interruption_reuses_recorded_phase_then_restores_and_publishes_once(self):
        from vk_nightly_cycle_state import run_cycle
        store,binding,adapters,calls,_=self.cycle_fixture()
        def interrupted(*_):raise ConnectionError('fixture Desktop offline before SQL')
        with self.assertRaisesRegex(ConnectionError,'Desktop offline'):
            run_cycle(store,binding,**dict(adapters,SQL=interrupted))
        self.assertIsNone(store.accepted());self.assertEqual(calls,['files'])
        # New normal native reader after the original control process exits.
        send(self.client.output,dict(op='bye'));self.assertEqual(recv(self.client.source),{'closed':True})
        self.assertEqual(self.children[-1].wait(timeout=10),0)
        self.client.output.close();self.client=self.start();store.client=self.client
        result=run_cycle(store,binding,**adapters)
        self.assertEqual(calls,['files','SQL','runtime','candidate','restore'])
        self.assertTrue(result['current_recoverable_set_accepted']);self.assertEqual(result['revision'],1)
        self.assertFalse(result['original_epoch']['complete']);self.assertFalse(result['schedule_enabled'])
        again=run_cycle(store,binding,**adapters)
        self.assertTrue(again['reused_completed_publication']);self.assertEqual(again['revision'],1)
        self.assertEqual(calls,['files','SQL','runtime','candidate','restore'])

    def test_actual_native_cycle_Desktop_off_calendar_retry_reopens_prefix_and_restores_once(self):
        from datetime import datetime,timedelta,timezone
        from vk_nightly_cycle_state import run_cycle
        from vk_nightly_calendar import tick,load as calendar_state
        from vk_nightly_service import failure_exit_code
        from vk_nightly_transport_diagnostics import finish
        store,binding,adapters,calls,now=self.cycle_fixture()
        now[0]=datetime(2099,1,3,3,tzinfo=timezone.utc)
        binding.update(started_UTC=now[0].isoformat(),deadline_UTC=(now[0]+timedelta(hours=2)).isoformat())
        state=self.root/'calendar-retry.json';mono=[0];attempts=[0]
        def offline(*_):
            process=SimpleNamespace(args=['ssh','desktop','fixed-existing-command'],stdin=io.BytesIO(),stdout=io.BytesIO(),
                stderr=io.BytesIO(b'ssh: connect to host 10.0.0.109 port 22: Connection refused\n'),wait=lambda **_:255)
            error=EOFError('normal B readiness stream ended');finish(process,original=error);raise error
        def runner(deadline,day):
            attempts[0]+=1
            try:run_cycle(store,binding,**(dict(adapters,SQL=offline) if attempts[0]==1 else adapters))
            except Exception as error:return failure_exit_code(error)
            return 0
        def wake():return tick(state,'a'*64,runner,lambda:True,lambda _:None,
            now=lambda:now[0],monotonic=lambda:mono[0],boot_id='same-fixture-boot')
        first=wake();self.assertEqual(first['status'],'resource_deferred');self.assertEqual(first['child_exit'],75)
        self.assertIsNone(store.accepted());self.assertEqual(calls,['files'])
        self.assertEqual(calendar_state(state)['attempts'],1)
        self.assertEqual(wake()['status'],'retry_wait');self.assertEqual(attempts[0],1)
        # Independently reopen the SAME native B fixture, not in-memory caller state.
        send(self.client.output,dict(op='bye'));self.assertEqual(recv(self.client.source),{'closed':True})
        self.assertEqual(self.children[-1].wait(timeout=10),0);self.client.output.close()
        self.client=self.start();store.client=self.client
        now[0]+=timedelta(seconds=1801);mono[0]+=1801
        self.assertEqual(wake()['status'],'completed')
        self.assertTrue(store.accepted()['current_recoverable_set_accepted'])
        self.assertEqual(store.accepted()['revision'],1)
        self.assertEqual(calls,['files','SQL','runtime','candidate','restore'])
        self.assertEqual(wake()['status'],'already_completed');self.assertEqual(attempts[0],2)
        self.assertEqual(calls.count('files'),1)

    def test_commission_gate_reopens_actual_ordinary_restore_not_initial_or_other_package(self):
        from datetime import timedelta
        from vk_nightly_cycle_state import run_cycle
        from vk_nightly_commission import qualification
        from vk_nightly_service import scheduled_cycle
        from vk_nightly_window import night
        store,binding,adapters,calls,now=self.cycle_fixture()
        template=dict(cycle=dict(cycle_binding=dict(binding,cycle_kind='incremental',
            SQL_cohort_tag='template',SQL_phase_index=dict(index_name='template-sql',checkpoint_sha256=self.sha)),
            SQL=dict(SQL_phase_index=dict(index_name='template-sql',checkpoint_sha256=self.sha)),finalize={}))
        store.initialize(binding)
        with self.assertRaisesRegex(ValueError,'baseline is missing'):
            qualification(store,template,'1'*64,guard=lambda:None)
        run_cycle(store,binding,**adapters)
        with self.assertRaisesRegex(ValueError,'not ordinary exact-package'):
            qualification(store,template,'1'*64,guard=lambda:None)
        frozen=store.scheduled_binding(scheduled_cycle(template,night(now[0]).isoformat(),'1'*64)['cycle']['cycle_binding'])
        ordinary=dict(adapters)
        real_restore=adapters['restore']
        # The RAM fixture uses the actual normal consumer, with this explicit
        # stand-in for its enclosing production B-placement/SSH wrapper only.
        ordinary['restore']=lambda *a:dict(real_restore(*a),actual_existing_B_backed_consumer_route_verified=True)
        now[0]+=timedelta(seconds=1)
        accepted=run_cycle(store,frozen,**ordinary)
        before={p.name:p.stat().st_ino for p in self.objects.iterdir()}
        with patch.object(store,'initialize',side_effect=AssertionError('commission recaptured')),             patch.object(store,'record',side_effect=AssertionError('commission rewrote phase')),             patch.object(store,'publish',side_effect=AssertionError('commission republished')):
            result=qualification(store,template,'1'*64,guard=lambda:None)
        self.assertTrue(result['actual_ordinary_incremental_and_normal_restore_verified'])
        self.assertEqual(result['restore_receipt_sha256'],accepted['restore_receipt_sha256'])
        self.assertFalse(result['schedule_enabled'])
        with self.assertRaisesRegex(ValueError,'other package'):
            qualification(store,template,'2'*64,guard=lambda:None)
        bad=dict(accepted,elapsed_seconds=accepted['elapsed_seconds']+1)
        with patch.object(store,'accepted',return_value=bad):
            with self.assertRaisesRegex(ValueError,'outside its overnight window'):
                qualification(store,template,'1'*64,guard=lambda:None)
        # A different actual native process independently reopens the same
        # accepted proof; qualification does not need a body reader or copy.
        send(self.client.output,dict(op='bye'));self.assertEqual(recv(self.client.source),{'closed':True})
        self.assertEqual(self.children[-1].wait(timeout=10),0);self.client.output.close()
        self.client=self.start();store.client=self.client
        self.assertEqual(qualification(store,template,'1'*64,guard=lambda:None),result)
        self.assertEqual({p.name:p.stat().st_ino for p in self.objects.iterdir()},before)

    def test_scheduled_binding_survives_retry_and_four_AM_stops_between_phases(self):
        from datetime import datetime,timedelta,timezone
        from vk_nightly_cycle_state import run_cycle
        from vk_nightly_window import bounds
        from vk_typed_recovery import checksum
        store,base,adapters,calls,now=self.cycle_fixture()
        accepted=run_cycle(store,base,**adapters)
        start,end=bounds(datetime(2099,1,2).date())
        binding=dict(base,cycle_kind='incremental',started_UTC=start.isoformat(),deadline_UTC=end.isoformat(),
            scheduled_night='2099-01-02',schedule_template_sha256='a'*64)
        frozen=store.scheduled_binding(binding)
        self.assertEqual(frozen['previous_accepted_sha256'],checksum(accepted))
        with patch.object(store,'accepted',side_effect=AssertionError('retry changed its original predecessor')):
            self.assertEqual(store.scheduled_binding(dict(binding,previous_accepted_sha256='f'*64)),frozen)
        now[0]=end-timedelta(seconds=2);before=list(calls)
        def expired(*_):
            calls.append('SQL');now[0]=end
            return dict(more_pending=False,actual_independent_B_SQL_cycle_receipt_reopen_verified=True)
        with self.assertRaisesRegex(TimeoutError,'original whole-cycle'):
            run_cycle(store,frozen,**dict(adapters,SQL=expired))
        self.assertEqual([p['phase'] for p in store.phases(checksum(frozen))],['files'])
        self.assertEqual(store.accepted(),accepted)
        self.assertEqual(calls[len(before):],['files','SQL'])
        with self.assertRaisesRegex(TimeoutError,'original whole-cycle'):
            run_cycle(store,frozen,**adapters)
        self.assertEqual(calls[len(before):],['files','SQL'])

    def test_failed_restore_or_expired_original_window_cannot_publish_or_reset_progress(self):
        from datetime import timedelta
        from vk_nightly_cycle_state import run_cycle
        store,binding,adapters,calls,now=self.cycle_fixture()
        def corrupt(*_):raise ValueError('fixture body readback failed')
        with self.assertRaisesRegex(ValueError,'body readback failed'):
            run_cycle(store,binding,**dict(adapters,restore=corrupt))
        self.assertIsNone(store.accepted());self.assertEqual(len(store.phases(store.initialize(binding))),4)
        now[0]+=timedelta(seconds=121)
        with self.assertRaisesRegex(TimeoutError,'original whole-cycle'):
            run_cycle(store,binding,**adapters)
        self.assertIsNone(store.accepted());self.assertNotIn('restore',calls)

    def test_whole_cycle_refuses_partial_points_and_unauthenticated_restore_before_pointer(self):
        from vk_nightly_cycle_state import run_cycle
        store,binding,adapters,_,_=self.cycle_fixture()
        with self.assertRaisesRegex(ValueError,'incomplete files'):
            run_cycle(store,binding,**dict(adapters,files=lambda *_:dict(more_pending=True)))
        self.assertIsNone(store.accepted())
        def fabricated(*_):return dict(independent_composed_restore_verified=True)
        with self.assertRaisesRegex(ValueError,'authenticated normal composed restore'):
            run_cycle(store,binding,**dict(adapters,restore=fabricated))
        self.assertIsNone(store.accepted())

    def test_cycle_receipt_tampering_and_accepted_pointer_conflict_are_not_silent_reuse(self):
        from vk_nightly_cycle_state import run_cycle
        store,binding,adapters,_,_=self.cycle_fixture();run_cycle(store,binding,**adapters)
        db=self.client.connect('cycle-ledger',self.sha)
        try:db.execute("update nightly_cycle_phases set receipt='{}' where ordinal=0")
        finally:db.close()
        with self.assertRaisesRegex(ValueError,'phase chain differs'):run_cycle(store,binding,**adapters)

    def test_native_composed_audit_requires_immutable_map_and_accepted_object_identities(self):
        from vk_nightly_current_map import FORMAT,encode_member
        from vk_nightly_b_controls import NativeControlError
        path=self.root/'proof-map.sqlite';db=sqlite3.connect(path)
        db.execute('create table members(name text primary key,state text,row blob)')
        member=dict(kind='file',mode=0o600,uid=os.getuid(),gid=os.getgid(),mtime_ns=123,xattrs={},
            bytes=len(self.raw),sha256=self.sha,segments=self.segments)
        db.execute('insert into members values(?,?,?)',('home/accepted','verified-file',encode_member(dict(member=member))))
        db.commit();db.close();mapsha=self.import_other(path)
        base=self.root/'proof-base.sqlite';db=sqlite3.connect(base)
        db.execute('create table provenance(source_catalog_sha256 text,restore_proof_sha256 text)')
        db.execute('insert into provenance values(?,?)',('a'*64,'b'*64))
        db.execute('create table bodies(sha256 text,bytes integer,name text)');db.commit();db.close();basesha=self.import_other(base)
        view=self.client.connect('proof-map',mapsha,readonly=True);catalog=self.client.connect('proof-base',basesha,readonly=True)
        reference=dict(format=FORMAT,sha256=mapsha,selector=mapsha+'.sqlite',bytes=path.stat().st_size)
        query=dict(op='audit-current-content',name=view.key,reference=reference,base_index=catalog.key,recipe_indexes=[])
        before={p.name:(p.stat().st_ino,p.stat().st_size,p.stat().st_mtime_ns) for p in self.objects.iterdir()}
        result=self.client.call(**query)
        self.assertEqual(result['file_points'],1);self.assertEqual(result['accepted_native_object_references'],1)
        self.assertEqual(result['SQL_control_bytes_read'],0);self.assertFalse(result['fresh_full_body_decode_claimed'])
        self.assertEqual(before,{p.name:(p.stat().st_ino,p.stat().st_size,p.stat().st_mtime_ns) for p in self.objects.iterdir()})
        self.assertEqual(result,self.client.call(**query))
        draft=self.client.connect('proof-draft',mapsha)
        with self.assertRaisesRegex(NativeControlError,'immutable current map'):
            self.client.call(**dict(query,name=draft.key))
        draft.close();view.close();catalog.close()
        accepted=self.objects/(self.sha+'.accepted.json');raw=accepted.read_bytes();old=json.loads(raw)
        old['identity']=[0]*5;accepted.write_text(json.dumps(old))
        view=self.client.connect('proof-map',mapsha,readonly=True);catalog=self.client.connect('proof-base',basesha,readonly=True)
        try:
            with self.assertRaisesRegex(NativeControlError,'object/identity changed'):self.client.call(**query)
        finally:view.close();catalog.close();accepted.write_bytes(raw)

    def test_sealed_current_map_consumed_by_normal_typed_reader_without_second_index(self):
        from vk_nightly_current_map import FORMAT,SealedMemberIndex,encode_member
        db=self.client.connect('ready-map',self.sha)
        db.execute('create table metadata(format text,complete integer)');db.execute('insert into metadata values(?,1)',(FORMAT,))
        db.execute('create table members(name text primary key,state text,row blob)')
        db.execute('create table SQL_sources(path text primary key)')
        member=dict(kind='file',bytes=3,sha256=hashlib.sha256(b'abc').hexdigest(),mode=0o640,uid=1000,gid=1000,mtime_ns=123,xattrs=[])
        db.execute('insert into members values(?,?,?)',('home/note','verified-file',encode_member(dict(member=member))))
        sealed=self.client.seal_checkpoint('ready-map',dict(instance='ready-epoch',sequence=42));db.close()
        self.assertTrue(sealed['independent_stream_readback_verified']);self.assertFalse(sealed['whole_baseline_accepted'])
        other=self.start();view=other.connect('ordinary-recovery',sealed['sha256'],readonly=True)
        index=SealedMemberIndex(view,lambda:view.request('check'),dict(sha256=sealed['sha256']))
        self.assertEqual(list(index.entries()),[('home/note',member)]);view.close()

    def test_native_seal_rejects_uncommitted_reader_bad_binding_and_tampered_image(self):
        from vk_nightly_b_controls import NativeControlError
        db=self.client.connect('live-map',self.sha);request=self.seal_request('live-map',dict(epoch='fixture'))
        db.execute('begin immediate')
        with self.assertRaisesRegex(NativeControlError,'committed writable'):db.request('seal-working',**request)
        db.rollback();db.execute('insert into point values(1,?)',(b'separate image from original seed',))
        with self.assertRaisesRegex(NativeControlError,'request binding'):db.request('seal-working',**dict(request,binding=dict(epoch='different')))
        first=db.request('seal-working',**request);db.close()
        read=self.client.connect('live-map',self.sha,readonly=True,working=True)
        with self.assertRaisesRegex(NativeControlError,'committed writable'):read.request('seal-working',**request)
        read.close()
        image=self.controls/(first['sha256']+'.sqlite')
        with image.open('r+b') as f:f.seek(100);f.write(b'X')
        db=self.client.connect('live-map',self.sha)
        with self.assertRaisesRegex(NativeControlError,'receipt or image differs'):db.request('seal-working',**request)
        db.close()

    def test_interrupted_native_backup_keeps_working_point_and_unaccepted_partial(self):
        import vk_nightly_objects as objects
        from vk_nightly_b_controls import Store
        store=Store(self.controls,objects,guard=lambda _:None);self.addCleanup(store.close)
        store.open(dict(name='interrupt-map',checkpoint_sha256=self.sha))
        db,path,_,_=store.handles['interrupt-map'];db.execute('insert into point values(1,zeroblob(1048576))')
        request=self.seal_request('interrupt-map',dict(epoch='interrupted'))
        calls=0
        def stop(_):
            nonlocal calls
            calls+=1
            if calls>=3:raise PermissionError('synthetic actual STOP')
        store.guard=stop
        with self.assertRaisesRegex(PermissionError,'actual STOP'):
            store.seal_working('interrupt-map',db,path,request)
        store.guard=lambda _:None
        self.assertEqual(db.execute('select length(value) from point').fetchall(),[(1048576,)])
        self.assertFalse((self.controls/('snapshot-'+request['request_sha256']+'.json')).exists())
        partials=list(self.controls.glob('snapshot-*.partial'));self.assertEqual(len(partials),1)
        done=store.seal_working('interrupt-map',db,path,request)
        self.assertEqual(done['native_integrity'],'ok');self.assertTrue(partials[0].exists())

    def test_embedded_temp_placement_preserves_python_default_and_restores_SQLite_scope(self):
        import vk_nightly_objects as objects
        from vk_nightly_b_controls import Store
        original=tempfile.gettempdir();probe=sqlite3.connect(':memory:')
        previous=probe.execute('pragma temp_store_directory').fetchone()
        store=Store(self.controls,objects,guard=lambda _:None)
        db=sqlite3.connect(':memory:')
        try:
            store.configure(db)
            self.assertEqual(tempfile.gettempdir(),original)
            self.assertEqual(Path(db.execute('pragma temp_store_directory').fetchone()[0]),self.controls/'sqlite-tmp-v1')
        finally:db.close();store.restore_temporary_scope()
        self.assertEqual(probe.execute('pragma temp_store_directory').fetchone(),previous)
        self.assertEqual(tempfile.gettempdir(),original);probe.close()

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
                ('DatabaseError','database disk image is malformed',None,NativeControlError),
                ('TimeoutExpired','required SMART query timed out',None,NativeControlError)]:
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

    def test_actual_native_status_reader_contention_retries_only_same_metadata_and_honors_STOP(self):
        from vk_nightly_b_tracker import write_health
        writer=self.client.connect('status-contention',self.sha)
        writer.execute('create table tracking_health(id integer primary key,row text not null)')
        reader=sqlite3.connect((self.controls/'status-contention.sqlite').as_uri()+'?mode=ro',uri=True,
                               isolation_level=None,check_same_thread=False)
        reader.execute('begin');reader.execute('select count(*) from tracking_health').fetchone()
        errors=[]
        def release():
            try:time.sleep(1);reader.execute('commit');reader.close()
            except BaseException as error:errors.append(error)
        thread=threading.Thread(target=release);thread.start();checks=[];mirrors=[]
        try:
            write_health(writer,self.root/'not-written',dict(sequence=17),mirror=lambda *_:mirrors.append(1),
                         guard=lambda:checks.append(1))
            self.assertGreater(len(checks),1);self.assertEqual(mirrors,[1])
            self.assertEqual(json.loads(writer.execute('select row from tracking_health').fetchone()[0]),dict(sequence=17))
            def stop():raise PermissionError('actual owner STOP')
            with self.assertRaisesRegex(PermissionError,'actual owner STOP'):
                write_health(writer,self.root/'not-written',dict(sequence=18),mirror=lambda *_:None,guard=stop)
            self.assertEqual(json.loads(writer.execute('select row from tracking_health').fetchone()[0]),dict(sequence=17))
        finally:thread.join(timeout=3);writer.close()
        self.assertFalse(errors)

    def test_service_reopens_actual_native_completion_not_merely_a_local_success_flag(self):
        from vk_nightly_service import reopen_component
        owner=SimpleNamespace(reference=dict(instance='same-real-observer'),check=lambda:None)
        root=self.root/'existing-owner';root.mkdir()
        def saved(name,value):
            p=root/name;raw=json.dumps(value).encode();p.write_bytes(raw);p.chmod(0o600)
            return str(p),hashlib.sha256(raw).hexdigest()
        control,sha=saved('controller',dict(worker_config='fixture',worker_config_sha256='1'*64))
        row=dict(phase='finite-current-file-cycle-complete',more_pending=False,
                 final_B_delivery=dict(instance='same-real-observer'),completed_members=7)
        result,_=saved('result',dict(row,at_EDT='fixture-time',actual_independent_B_file_cycle_receipt_reopen_verified=True))
        db=self.client.connect('service-existing-file',self.sha)
        db.execute('create table tracking_health(id integer primary key,row text not null)')
        db.execute('insert into tracking_health values(1,?)',(json.dumps(row),));db.close()
        worker=dict(B_index_name='service-existing-file',B_checkpoint_sha256=self.sha)
        ref=dict(config=control,config_sha256=sha,result=result,result_binding=dict(phase=row['phase']))
        with patch('vk_nightly_service.terminal',return_value=True),patch('vk_nightly_service.configuration',return_value=worker):
            value=reopen_component(self.client,ref,'files',owner,guard=lambda:None)
            self.assertEqual(value['completed_members'],7)
            db=self.client.connect('service-existing-file',self.sha)
            db.execute('update tracking_health set row=?',(json.dumps(dict(row,optional_SSD_health_mirror_error='work SSD full')),));db.close()
            value=reopen_component(self.client,ref,'files',owner,guard=lambda:None)
            self.assertEqual(value['adoption_reopen_optional_mirror_error'],'work SSD full')
            db=self.client.connect('service-existing-file',self.sha)
            db.execute('update tracking_health set row=?',(json.dumps(dict(row,completed_members=8)),));db.close()
            with self.assertRaisesRegex(ValueError,'native B completion receipt differs'):
                reopen_component(self.client,ref,'files',owner,guard=lambda:None)

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

    def test_selected_qualification_capture_and_interrupted_boundary_reuse_actual_native_state(self):
        from vk_nightly_current_map import CurrentMap
        from vk_nightly_namespace import observe
        from vk_nightly_qualification import encode_observation,qualify_file
        import vk_nightly_typed_worker as worker
        files=self.root/'selected';files.mkdir()
        unchanged=files/'unchanged';unchanged.write_bytes(b'accepted earlier body')
        changed=files/'changed';changed.write_bytes(b'new body after the accepted baseline')
        ns=sqlite3.connect(':memory:');self.addCleanup(ns.close)
        ns.execute('create table namespace(name text primary key,row blob)')
        ns.execute('create table namespace_errors(name text primary key,error blob)')
        for path in (unchanged,changed):
            ns.execute('insert into namespace values(?,?)',(str(path)[1:],encode_observation(observe(path))))
        epoch=dict(instance='live-inode-source',scope_sha256='a'*64,plan_sha256='b'*64,start_sequence=17,
            required_root_bindings={str(files):dict(resolved=str(files),literal=None)},original_epoch_repaired=False)
        ns.execute('create table gap_meta(id integer primary key,binding text,complete integer)')
        ns.execute('insert into gap_meta values(1,?,1)',(json.dumps(epoch),))
        path=self.root/'selected-map.sqlite';binding={'test':'native selected worker'}
        with CurrentMap.held(path,binding=binding,create=True) as current:
            current.compile(ns,lambda _:None,SQL_sources=[],checkpoint=lambda:None,maximum_paths=10)
            current.reconcile_namespace(ns,lambda _:None,checkpoint=lambda:None,maximum_paths=10)
        map_sha=self.import_other(path)
        path=self.root/'selected-carriers.sqlite'
        with sqlite3.connect(path) as base:
            base.execute('create table provenance(source_catalog_sha256 text,restore_proof_sha256 text)')
            base.execute('insert into provenance values(?,?)',('c'*64,'d'*64))
            base.execute('create table bodies(sha256 text,bytes integer,name text)')
            base.execute('insert into bodies values(?,?,?)',(hashlib.sha256(unchanged.read_bytes()).hexdigest(),unchanged.stat().st_size,str(unchanged)[1:]))
        base.close();base_sha=self.import_other(path)
        self.client.connect('selected-carriers',base_sha).close()
        config=dict(format='vk-nightly-typed-worker-B-v1',B_controls={'maximum_index_bytes':8*1024**2},B_index_name='selected-map',B_checkpoint_sha256=map_sha,
            map_binding=binding,status=str(self.root/'selected-status'),desktop={},maximum_members=10,
            maximum_source_bytes=1024,chunk_bytes=4096,
            qualification=dict(maximum_paths=10,maximum_source_bytes=1024,
                base=dict(index_name='selected-carriers',checkpoint_sha256=base_sha),recipes=[],attach_base_prefixes=True))
        report=dict(epoch,since=17,sequence=25,ready=True,errors=[],terminal=None,coverage_model='all-selected-inodes-v1',
            barrier=dict(instance=epoch['instance'],durable_sequence=25,kernel_drain_completed=True))
        @contextmanager
        def controls(*_,**__):yield SimpleNamespace(client=self.client)
        folder=str(Path(__file__).parent)
        code='import sys;sys.path.insert(0,'+repr(folder)+');from vk_nightly_objects import receive;receive('+repr(str(self.objects))+',sys.stdin.buffer,sys.stdout.buffer,guard=lambda n:None,maximum_object_bytes=65536)'
        body=subprocess.Popen([sys.executable,'-B','-u','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        objects=ObjectClient(body.stdout,body.stdin,guard=lambda:None,ram_root=self.root,maximum_object_bytes=65536)
        @contextmanager
        def remote(*_,**__):yield SimpleNamespace(client=objects,ready={'test':'normal native protocol'})
        def fault():raise RuntimeError('injected after committed qualification')
        try:
            with patch.object(worker,'host_guard',lambda *_:None),patch.object(worker,'DesktopControls',controls),patch.object(worker,'DesktopObjects',remote):
                with patch('vk_nightly_qualification_worker.qualify_file',wraps=qualify_file) as hashed:
                    with self.assertRaisesRegex(RuntimeError,'committed qualification'):
                        worker.run_B(config,source_report=lambda:report,at_component_boundary=fault)
                    self.assertEqual(hashed.call_count,2)
                self.assertEqual(objects.payload_bytes_sent,0,'qualification must not transfer source bodies')
                import vk_nightly_file_cycle as cycle
                events=[]
                source=SimpleNamespace(check=lambda:None,deliver=lambda:(events.append('delivery') or {'verified':True}),
                    config={'B_delivery_target':{'index_name':'fixture-journal','checkpoint_sha256':map_sha}},plan={},
                    report=lambda _:report)
                with patch('vk_nightly_qualification_worker.qualify_file',side_effect=AssertionError('accepted hash repeated')),\
                     patch.object(cycle,'Source',return_value=source),patch.object(cycle,'DesktopControls',controls),\
                     patch.object(cycle,'advance_suffix',side_effect=lambda *a,**k:(events.append('bounded-delta') or {'retained':True})),\
                     patch.object(cycle,'host_guard',lambda *_:None):
                    result=cycle.run({'source_observer':{},'maximum_delta_paths':10},config,report=lambda _:None)
                self.assertEqual(events,['delivery','bounded-delta','delivery'])
                self.assertTrue(result['actual_independent_B_file_cycle_receipt_reopen_verified'])
                self.assertFalse(result['baseline_accepted']);self.assertTrue(result['remaining_SQL_runtime_composed_restore_required'])
                self.assertEqual(result['selected_qualification']['processed'],0)
                self.assertEqual(result['completed_members'],1)
                self.assertFalse(result['more_pending'])
                self.assertEqual(result['source_bytes_read'],changed.stat().st_size)
                before={p.name:p.stat().st_ino for p in self.objects.iterdir()}
                result=worker.run_B(config,source_report=lambda:report)
                self.assertEqual(result['completed_members'],0)
                self.assertEqual({p.name:p.stat().st_ino for p in self.objects.iterdir()},before)
        finally:
            body.stdin.close();self.assertEqual(body.wait(timeout=10),0);body.stdout.close();body.stderr.close()

    def test_deferred_file_closure_preserves_original_B_receipt_and_reuses_completed_bodies(self):
        from vk_nightly_current_map import CurrentMap
        from vk_nightly_namespace import observe
        from vk_nightly_qualification import encode_observation,qualify_file
        import vk_nightly_typed_worker as worker
        files=self.root/'selected';files.mkdir()
        unchanged=files/'unchanged';unchanged.write_bytes(b'accepted earlier body')
        changed=files/'changed';changed.write_bytes(b'new body after the accepted baseline'*2048) # above bounded small-state closure
        ns=sqlite3.connect(':memory:');self.addCleanup(ns.close)
        ns.execute('create table namespace(name text primary key,row blob)')
        ns.execute('create table namespace_errors(name text primary key,error blob)')
        for path in (unchanged,changed):
            ns.execute('insert into namespace values(?,?)',(str(path)[1:],encode_observation(observe(path))))
        epoch=dict(instance='live-inode-source',scope_sha256='a'*64,plan_sha256='b'*64,start_sequence=17,
            required_root_bindings={str(files):dict(resolved=str(files),literal=None)},original_epoch_repaired=False)
        ns.execute('create table gap_meta(id integer primary key,binding text,complete integer)')
        ns.execute('insert into gap_meta values(1,?,1)',(json.dumps(epoch),))
        path=self.root/'selected-map.sqlite';binding={'test':'native selected worker'}
        with CurrentMap.held(path,binding=binding,create=True) as current:
            current.compile(ns,lambda _:None,SQL_sources=[],checkpoint=lambda:None,maximum_paths=10)
            current.reconcile_namespace(ns,lambda _:None,checkpoint=lambda:None,maximum_paths=10)
        map_sha=self.import_other(path)
        path=self.root/'selected-carriers.sqlite'
        with sqlite3.connect(path) as base:
            base.execute('create table provenance(source_catalog_sha256 text,restore_proof_sha256 text)')
            base.execute('insert into provenance values(?,?)',('c'*64,'d'*64))
            base.execute('create table bodies(sha256 text,bytes integer,name text)')
            base.execute('insert into bodies values(?,?,?)',(hashlib.sha256(unchanged.read_bytes()).hexdigest(),unchanged.stat().st_size,str(unchanged)[1:]))
        base.close();base_sha=self.import_other(path)
        self.client.connect('selected-carriers',base_sha).close()
        config=dict(format='vk-nightly-typed-worker-B-v1',B_controls={'maximum_index_bytes':8*1024**2},B_index_name='selected-map',B_checkpoint_sha256=map_sha,
            map_binding=binding,status=str(self.root/'selected-status'),desktop={},maximum_members=10,
            maximum_source_bytes=262144,chunk_bytes=4096,
            qualification=dict(maximum_paths=10,maximum_source_bytes=262144,
                base=dict(index_name='selected-carriers',checkpoint_sha256=base_sha),recipes=[],attach_base_prefixes=True))
        report=dict(epoch,since=17,sequence=25,ready=True,errors=[],terminal=None,coverage_model='all-selected-inodes-v1',
            barrier=dict(instance=epoch['instance'],durable_sequence=25,kernel_drain_completed=True))
        @contextmanager
        def controls(*_,**__):yield SimpleNamespace(client=self.client)
        folder=str(Path(__file__).parent)
        code='import sys;sys.path.insert(0,'+repr(folder)+');from vk_nightly_objects import receive;receive('+repr(str(self.objects))+',sys.stdin.buffer,sys.stdout.buffer,guard=lambda n:None,maximum_object_bytes=65536)'
        body=subprocess.Popen([sys.executable,'-B','-u','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        objects=ObjectClient(body.stdout,body.stdin,guard=lambda:None,ram_root=self.root,maximum_object_bytes=65536)
        @contextmanager
        def remote(*_,**__):yield SimpleNamespace(client=objects,ready={'test':'normal native protocol'})
        def fault():raise RuntimeError('injected after committed qualification')
        try:
            with patch.object(worker,'host_guard',lambda *_:None),patch.object(worker,'DesktopControls',controls),patch.object(worker,'DesktopObjects',remote):
                with patch('vk_nightly_qualification_worker.qualify_file',wraps=qualify_file) as hashed:
                    with self.assertRaisesRegex(RuntimeError,'committed qualification'):
                        worker.run_B(config,source_report=lambda:report,at_component_boundary=fault)
                    self.assertEqual(hashed.call_count,2)
                self.assertEqual(objects.payload_bytes_sent,0,'qualification must not transfer source bodies')
                changed.write_bytes(b'newer stable point after original qualification'*2048)
                import vk_nightly_file_cycle as cycle
                import vk_nightly_current_cycle as composed
                events=[]
                source=SimpleNamespace(guard=lambda:None,check=lambda:None,deliver=lambda:(events.append('delivery') or {'verified':True}),
                    config={'B_delivery_target':{'index_name':'fixture-journal','checkpoint_sha256':map_sha}},plan={},
                    report=lambda _:report)
                with patch('vk_nightly_qualification_worker.qualify_file',side_effect=AssertionError('accepted hash repeated')),\
                     patch.object(cycle,'Source',return_value=source),patch.object(cycle,'DesktopControls',controls),\
                     patch.object(cycle,'advance_suffix',side_effect=lambda *a,**k:(events.append('bounded-delta') or {'retained':True})),\
                     patch.object(cycle,'host_guard',lambda *_:None):
                    result=cycle.run({'source_observer':{},'maximum_delta_paths':10},config,report=lambda _:None)
                self.assertEqual(events,['delivery','bounded-delta','delivery'])
                self.assertTrue(result['actual_independent_B_file_cycle_receipt_reopen_verified'])
                self.assertFalse(result['baseline_accepted']);self.assertTrue(result['remaining_SQL_runtime_composed_restore_required'])
                self.assertEqual(result['selected_qualification']['processed'],0)
                self.assertEqual(result['completed_members'],0)
                self.assertTrue(result['more_pending']);self.assertTrue(result['requires_source_requalification'])
                db=self.client.connect('selected-map',map_sha,readonly=True,working=True)
                original_native=db.execute('select row from tracking_health where id=1').fetchone()[0];db.close()
                saved=json.dumps(result,sort_keys=True);progress=[]
                with patch.object(composed,'DesktopControls',controls):
                    # A forged caller success cannot close the still-unresolved
                    # member. The new independent native reopen rejects it.
                    with patch.object(composed,'run_B',return_value={'more_pending':False}):
                        with self.assertRaisesRegex(ValueError,'still has unresolved'):
                            composed.close_deferred_files(result,config,source,report=progress.append)
                    closed=composed.close_deferred_files(result,config,source,report=progress.append)
                    self.assertTrue(closed['normal_B_file_closure_reopen_verified'])
                    self.assertFalse(closed['more_pending'])
                    self.assertEqual(closed['original_component_receipt'],result)
                    self.assertEqual(json.dumps(result,sort_keys=True),saved)
                    self.assertEqual(closed['recorded_file_delta']['completed_members'],1)
                    self.assertEqual(closed['recorded_file_delta']['selected_qualification']['processed'],1)
                    before={p.name:p.stat().st_ino for p in self.objects.iterdir()}
                    uploaded=objects.payload_bytes_sent
                    # Interruption before the cycle-ledger commit: reopen the
                    # original unchanged receipt, skip accepted points and do
                    # not rehash or recopy the now-completed replacement.
                    with patch('vk_nightly_qualification_worker.qualify_file',side_effect=AssertionError('completed hash repeated')):
                        again=composed.close_deferred_files(result,config,source,report=progress.append)
                    self.assertFalse(again['more_pending'])
                    self.assertEqual(again['recorded_file_delta']['completed_members'],0)
                    self.assertEqual(objects.payload_bytes_sent,uploaded)
                    self.assertEqual({p.name:p.stat().st_ino for p in self.objects.iterdir()},before)
                db=self.client.connect('selected-map',map_sha,readonly=True,working=True)
                self.assertEqual(db.execute('select row from tracking_health where id=1').fetchone()[0],original_native)
                self.assertEqual(db.execute("select count(*) from members where state='verified-file'").fetchone(),(2,));db.close()
        finally:
            body.stdin.close();self.assertEqual(body.wait(timeout=10),0);body.stdout.close();body.stderr.close()

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

        # A new current cohort must qualify this same source again rather
        # than relabeling the older completed point above. Equal API bytes
        # still reuse their actual accepted CAS objects.
        import vk_nightly_sql_cycle as cycle
        import stat
        from vk_nightly_current_map import CurrentMap,decode_member
        from vk_nightly_namespace import observe
        from vk_nightly_qualification import encode_observation
        from vk_change_journal import scope
        from vk_prep_common import identity
        rootid=[self.root.stat().st_dev,self.root.stat().st_ino,stat.S_IFDIR]
        plan={'sources':[str(self.root)]};roots={str(self.root):dict(resolved=str(self.root),literal=None,identity=rootid,target_identity=rootid)}
        epoch=dict(instance='current-sql-source',plan_sha256=identity(plan),scope_sha256=identity(scope(plan)),
            start_sequence=1,required_root_bindings=roots)
        ns=sqlite3.connect(':memory:');self.addCleanup(ns.close)
        ns.execute('create table namespace(name text primary key,row blob)')
        ns.execute('insert into namespace values(?,?)',(str(self.original)[1:],encode_observation(observe(self.original))))
        ns.execute('create table namespace_errors(name text primary key,error blob)')
        ns.execute('create table gap_meta(id integer primary key,binding text,complete integer)')
        ns.execute('insert into gap_meta values(1,?,1)',(json.dumps(epoch),))
        mp=self.root/'current-sql-main.sqlite';binding={'test':'current SQL selection'}
        with CurrentMap.held(mp,binding=binding,create=True) as m:
            m.compile(ns,lambda _:None,SQL_sources=[str(self.original)],checkpoint=lambda:None,maximum_paths=10)
            m.reconcile_namespace(ns,lambda _:None,checkpoint=lambda:None,maximum_paths=10)
            # The separately tested suffix stage is the admitted fixture input
            # below; SQL adoption must still check its actual completion row.
            m.db.execute('update namespace_reconciliation set suffix_complete=1')
        map_sha=self.import_other(mp);self.client.connect('current-sql-main',map_sha).close()
        prepared=dict(config,B_index_name='current-sql-main',B_checkpoint_sha256=map_sha,
            B_controls={'maximum_index_bytes':8*1024**2})
        source=SimpleNamespace(reference={'instance':epoch['instance']},plan=plan,
            check=lambda:{'required_root_bindings':roots},deliver=lambda:{'instance':epoch['instance']},
            config={'B_delivery_target':{'index_name':'fixture-journal','checkpoint_sha256':self.sha}})
        settings=dict(source_observer={},maximum_delta_paths=10,cohort_tag='actual-current-sql-r1',
            SQL_phase_index=dict(index_name='current-sql-points',checkpoint_sha256=self.sha))
        with patch.object(worker,'DesktopControls',controls),patch.object(worker,'DesktopObjects',body),\
             patch.object(worker,'host_guard',lambda *_:None),patch.object(cycle,'host_guard',lambda *_:None),\
             patch.object(cycle,'DesktopControls',controls),patch.object(cycle,'Source',return_value=source):
            with patch.object(cycle,'advance_suffix',return_value={'actual_retained_delta':'fixture','through':1}),\
                 patch.object(worker,'capture_SQL_point',wraps=worker.capture_SQL_point) as current_API:
                result=cycle.run(settings,prepared,report=lambda _:None)
                self.assertEqual(current_API.call_count,1)
            self.assertTrue(result['actual_independent_B_SQL_cycle_receipt_reopen_verified'])
            self.assertEqual(result['completed_current_SQL_points'],1);self.assertFalse(result['more_pending'])
            with patch.object(cycle,'advance_suffix',side_effect=AssertionError('retained cohort reset')) ,\
                 patch.object(worker,'capture_SQL_point',side_effect=AssertionError('current API point recaptured')):
                resumed=cycle.run(settings,prepared,report=lambda _:None)
                with self.assertRaisesRegex(ValueError,'request binding changed'):
                    cycle.run(dict(settings,cohort_tag='a-different-current-cycle'),prepared,report=lambda _:None)
            self.assertEqual(resumed['cohort_id'],result['cohort_id'])
            later=dict(settings,cohort_tag='next-normal-night',
                SQL_phase_index=dict(index_name='current-sql-next-night',checkpoint_sha256=self.sha))
            with patch.object(cycle,'advance_suffix',return_value={'actual_retained_delta':'next empty suffix'}),\
                 patch.object(worker,'capture_SQL_point',side_effect=AssertionError('unchanged SQL source rescanned')):
                reused=cycle.run(later,prepared,report=lambda _:None)
            self.assertEqual(reused['requested_SQL_sources'],0)
            self.assertEqual(reused['unchanged_SQL_points_reused'],1)
            self.assertTrue(reused['actual_independent_B_SQL_cycle_receipt_reopen_verified'])
            self.assertFalse(reused['baseline_accepted'])
            # A copied DB header is discovered in an already-recorded namespace.
            # Close its consistent API point without invalidating/re-capturing
            # the earlier accepted source or replaying a fresh namespace.
            copied=self.root/'copied-seed.db';c=sqlite3.connect(copied)
            c.execute('create table copy_fixture(id integer)');c.execute('insert into copy_fixture values(7)');c.commit();c.close()
            from vk_nightly_current_map import classify,encode_member
            observed=observe(copied)
            state,row=classify(str(copied)[1:],observed,dict(source=str(copied),state='current-version-deferred',reason='SQLite requires its consistent snapshot API'),SQL_sources=set())
            db=self.client.connect('current-sql-main',map_sha)
            db.execute('insert into members values(?,?,?)',(str(copied)[1:],state,encode_member(row)))
            db.execute('insert into SQL_sources values(?)',(str(copied),));db.close()
            closure=dict(settings,cohort_tag='recorded-header-closure',recorded_SQL_scope_from=settings['SQL_phase_index'],
                SQL_phase_index=dict(index_name='current-sql-recorded',checkpoint_sha256=self.sha))
            with patch.object(cycle,'advance_suffix',side_effect=AssertionError('recorded namespace advanced')),\
                 patch.object(worker,'capture_SQL_point',wraps=worker.capture_SQL_point) as api:
                closed=cycle.run(closure,prepared,report=lambda _:None)
                self.assertEqual(api.call_count,1);self.assertEqual(api.call_args.args[0],str(copied))
            self.assertEqual(closed['complete_SQL_scope_sources'],2);self.assertEqual(closed['unchanged_SQL_points_reused'],1)
            self.assertTrue(closed['actual_independent_B_SQL_cycle_receipt_reopen_verified'])
            with patch.object(cycle,'advance_suffix',side_effect=AssertionError('closure replayed')),\
                 patch.object(worker,'capture_SQL_point',side_effect=AssertionError('completed closure recaptured')):
                self.assertEqual(cycle.run(closure,prepared,report=lambda _:None)['cohort_id'],closed['cohort_id'])
            db=self.client.connect('current-sql-main',map_sha)
            old_epoch=db.execute('select binding from namespace_reconciliation where id=1').fetchone()[0]
            changed=json.loads(old_epoch);changed['start_sequence']=2
            db.execute('update namespace_reconciliation set binding=?',(json.dumps(changed),));db.close()
            with self.assertRaisesRegex(ValueError,'fixed namespace'):
                cycle.recorded_namespace(self.client,settings['SQL_phase_index'],prepared,guard=lambda:None)
            db=self.client.connect('current-sql-main',map_sha)
            db.execute('update namespace_reconciliation set binding=?',(old_epoch,));db.close()
        db=self.client.connect('current-sql-main',map_sha,readonly=True,working=True)
        state,raw=db.execute('select state,row from members where name=?',(str(self.original)[1:],)).fetchone()
        row=decode_member(raw)
        self.assertEqual(row['SQL_point']['SQL_cohort_id'],result['cohort_id'])
        self.assertEqual(row['SQL_point']['new_B_encoded_payload_bytes'],0)
        self.assertEqual(db.execute('select count(*) from SQL_acceptance_history').fetchone(),(2,));db.close()
        file_root={str(self.original):dict(resolved=str(self.original),literal=None,identity=[1,2,stat.S_IFREG])}
        all_sources,pending,always,unchanged=cycle.selected_SQL([(str(self.original),state,raw)],file_root,{})
        self.assertEqual(pending,[str(self.original)]);self.assertEqual(always,pending);self.assertEqual(unchanged,0)
        self.assertEqual(cycle.selected_SQL([(str(self.original),state,raw)],roots,{'logical-alias':str(self.original)})[1],pending)
        self.assertEqual(cycle.selected_SQL([(str(self.original),state,raw)],roots,{},excluded=[str(self.root)])[1],pending)
        # Feed the actual independently restored API result, not a synthetic
        # integrity boolean, into the immutable composed content consumer.
        current=self.client.connect('current-sql-main',map_sha)
        sealed=self.client.seal_checkpoint(current.key,{'test':'actual SQL composed proof closure'});current.close()
        base=self.root/'SQL-proof-base.sqlite';db=sqlite3.connect(base)
        db.execute('create table provenance(source_catalog_sha256 text,restore_proof_sha256 text)')
        db.execute('insert into provenance values(?,?)',('a'*64,'b'*64))
        db.execute('create table bodies(sha256 text,bytes integer,name text)');db.commit();db.close()
        basesha=self.import_other(base)
        current=self.client.connect('current-sql-independent-map',sealed['sha256'],readonly=True)
        base=self.client.connect('sql-independent-base-catalog',basesha,readonly=True)
        try:
            proof=current.request('audit-current-content',reference=dict(format='vk-nightly-current-member-map-v1',
                sha256=sealed['sha256'],selector=sealed['sha256']+'.sqlite',bytes=sealed['bytes']),base_index=base.key,recipe_indexes=[])
            self.assertEqual(proof['SQL_acceptance_records_independently_decoded'],2)
            self.assertEqual(proof['file_points'],2);self.assertEqual(proof['new_backup_payload_bytes'],0)
            self.assertGreater(proof['SQL_control_bytes_read'],0)
        finally:current.close();base.close()

    def test_actual_worker_serial_boundaries_and_completed_body_recovery_before_upload(self):
        import vk_nightly_typed_worker as worker
        from vk_nightly_current_map import CurrentMap
        from vk_nightly_namespace import observe
        from vk_nightly_qualification import qualify_file,encode_observation
        source=self.root/'serial-point';source.write_bytes(b'actual serial point')
        point=qualify_file(source,maximum_bytes=1024,journal=dict(ready=True,errors=[],instance='fixture',
            sequence=1,scope_sha256='a'*64,plan_sha256='b'*64),carriers=lambda *_:[],guard=lambda:None)
        ns=sqlite3.connect(':memory:');self.addCleanup(ns.close);ns.execute('create table namespace(name text primary key,row blob)')
        member=str(source)[1:];ns.execute('insert into namespace values(?,?)',(member,encode_observation(observe(source))))
        path=self.root/'serial-map.sqlite';binding={'fixture':'serial file worker'}
        with CurrentMap.held(path,binding=binding,create=True) as m:
            m.compile(ns,lambda _:point,SQL_sources=[],checkpoint=lambda:None,maximum_paths=10)
            pending=m.db.execute('select row from members where name=?',(member,)).fetchone()[0]
        digest=self.import_other(path);folder=str(Path(__file__).parent);streaming=[False];boundaries=[]
        @contextmanager
        def body(config,*,guard):
            code='import sys;sys.path.insert(0,'+repr(folder)+');from vk_nightly_objects import receive;receive('+repr(str(self.objects))+',sys.stdin.buffer,sys.stdout.buffer,guard=lambda n:None,maximum_object_bytes=65536)'
            p=subprocess.Popen([sys.executable,'-B','-u','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            client=ObjectClient(p.stdout,p.stdin,guard=lambda:None,ram_root=self.root,maximum_object_bytes=65536)
            for name in ('ensure','verify'):
                original=getattr(client,name)
                def wrapped(*args,_original=original,**kwargs):
                    streaming[0]=True
                    try:return _original(*args,**kwargs)
                    finally:streaming[0]=False
                setattr(client,name,wrapped)
            try:yield SimpleNamespace(client=client,ready={'fixture':True})
            finally:p.stdin.close();p.wait(timeout=10);p.stdout.close();p.stderr.close()
        @contextmanager
        def controls(config,*,guard):yield SimpleNamespace(client=self.client)
        def boundary():self.assertFalse(streaming[0]);boundaries.append(True)
        config=dict(format='vk-nightly-typed-worker-B-v1',B_controls={},B_index_name='serial-map',B_checkpoint_sha256=digest,
            map_binding=binding,status=str(self.root/'serial-status'),desktop={},maximum_members=10,maximum_source_bytes=1024,chunk_bytes=64)
        with patch.object(worker,'DesktopControls',controls),patch.object(worker,'DesktopObjects',body),patch.object(worker,'host_guard',lambda *_:None):
            first=worker.run_B(config,at_component_boundary=boundary)
            self.assertEqual(first['completed_members'],1);self.assertGreaterEqual(len(boundaries),3)
            with current_map(self.client,'serial-map',digest,binding=binding) as m:
                m.db.execute("update members set state='file-needs-capture',row=? where name=?",(pending,member))
            with patch('vk_nightly_typed_capture.capture_qualified_version',side_effect=AssertionError('accepted body copied again')):
                second=worker.run_B(config,at_component_boundary=boundary)
            self.assertEqual(second['completed_members'],0);self.assertFalse(second['more_pending'])
            self.assertEqual(second['completed_file_reuse']['completed_file_points_reused'],1)
            self.assertEqual(second['completed_file_reuse']['backup_payload_bytes_copied'],0)

    def test_small_RAM_point_survives_actual_atomic_source_replacement_and_native_readback(self):
        import io
        from vk_nightly_current_map import CurrentMap
        from vk_nightly_namespace import observe
        from vk_nightly_qualification import qualify_file,encode_observation
        from vk_nightly_typed_capture import capture_pending
        from vk_typed_recovery import checksum
        source=self.root/'atomic-state.json';source.write_bytes(b'{"version":1}\n');buffer=io.BytesIO()
        point=qualify_file(source,maximum_bytes=1024,journal=dict(ready=True,errors=[],instance='fixture',sequence=1,
            scope_sha256='a'*64,plan_sha256='b'*64),carriers=lambda *_:[],guard=lambda:None,payload_sink=buffer)
        namespace=sqlite3.connect(':memory:');self.addCleanup(namespace.close)
        namespace.execute('create table namespace(name text primary key,row blob)')
        namespace.execute('insert into namespace values(?,?)',(str(source)[1:],encode_observation(observe(source))))
        path=self.root/'atomic-map.sqlite';binding={'fixture':'atomic state point'}
        with CurrentMap.held(path,binding=binding,create=True) as m:
            m.compile(namespace,lambda _:point,SQL_sources=[],checkpoint=lambda:None,maximum_paths=10)
        digest=self.import_other(path);new=self.root/'new';new.write_bytes(b'{"version":2}\n');new.replace(source)
        code='import sys;sys.path.insert(0,'+repr(str(Path(__file__).parent))+');from vk_nightly_objects import receive;receive('+repr(str(self.objects))+',sys.stdin.buffer,sys.stdout.buffer,guard=lambda n:None,maximum_object_bytes=65536)'
        p=subprocess.Popen([sys.executable,'-B','-u','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            client=ObjectClient(p.stdout,p.stdin,guard=lambda:None,ram_root=self.root,maximum_object_bytes=65536)
            with current_map(self.client,'atomic-map',digest,binding=binding) as m:
                cache={str(source)[1:]:(checksum(point),b'tampered')}
                with self.assertRaisesRegex(ValueError,'RAM qualification differs'):
                    capture_pending(m,client,guard=lambda:None,maximum_members=2,maximum_source_bytes=1024,chunk_bytes=64,qualified_snapshots=cache)
                self.assertEqual(client.payload_bytes_sent,0)
                cache[str(source)[1:]]=(checksum(point),buffer.getvalue())
                result=capture_pending(m,client,guard=lambda:None,maximum_members=2,maximum_source_bytes=1024,chunk_bytes=64,qualified_snapshots=cache)
                self.assertFalse(result['more_pending']);self.assertEqual(result['source_bytes_read'],0)
                self.assertEqual(result['qualified_RAM_bytes_transferred'],len(buffer.getvalue()))
                self.assertEqual(result['independent_object_readback_bytes'],len(buffer.getvalue()))
                self.assertEqual(source.read_bytes(),b'{"version":2}\n')
        finally:p.stdin.close();p.wait(timeout=10);p.stdout.close();p.stderr.close()

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

    def test_native_group_rollback_then_lost_reply_retains_all_completed_files_without_recopy(self):
        import copy
        from vk_nightly_current_map import CurrentMap
        from vk_nightly_namespace import observe
        from vk_nightly_qualification import qualify_file,encode_observation
        from vk_nightly_typed_capture import capture_pending
        from vk_nightly_b_controls import NativeControlError
        namespace=sqlite3.connect(':memory:');self.addCleanup(namespace.close)
        namespace.execute('create table namespace(name text primary key,row blob)');points={}
        for i in range(2):
            source=self.root/('group-source-'+str(i));source.write_bytes(bytes([i])*64)
            points[str(source)[1:]]=qualify_file(source,maximum_bytes=1024,journal=dict(ready=True,
                errors=[],instance='fixture',sequence=1,scope_sha256='a'*64,plan_sha256='b'*64),
                carriers=lambda *_:[],guard=lambda:None)
            namespace.execute('insert into namespace values(?,?)',(str(source)[1:],encode_observation(observe(source))))
        path=self.root/'group-map.sqlite';binding={'fixture':'native grouped file points'}
        with CurrentMap.held(path,binding=binding,create=True) as m:
            m.compile(namespace,points.__getitem__,SQL_sources=[],checkpoint=lambda:None,maximum_paths=10)
        digest=self.import_other(path)
        code='import sys;sys.path.insert(0,'+repr(str(Path(__file__).parent))+');from vk_nightly_objects import receive;receive('+repr(str(self.objects))+',sys.stdin.buffer,sys.stdout.buffer,guard=lambda n:None,maximum_object_bytes=65536)'
        p=subprocess.Popen([sys.executable,'-B','-u','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            body=ObjectClient(p.stdout,p.stdin,guard=lambda:None,ram_root=self.root,maximum_object_bytes=65536)
            def capture(m):return capture_pending(m,body,guard=lambda:None,maximum_members=2,
                maximum_source_bytes=1024,chunk_bytes=64,acceptance_batch_members=2)
            with current_map(self.client,'group-points',digest,binding=binding) as m:
                accept=m.accept_files
                def invalid(records,**kw):
                    wrong=copy.deepcopy(records);wrong[-1]['original_sha256']='0'*64
                    return accept(wrong,**kw)
                m.accept_files=invalid
                with self.assertRaisesRegex(NativeControlError,'version changed'):capture(m)
                self.assertEqual(m.db.execute("select count(*) from members where state='file-needs-capture'").fetchone(),(2,))
                uploaded=body.payload_bytes_sent
                def lost(records,**kw):accept(records,**kw);raise EOFError('lost grouped FULL-commit reply')
                m.accept_files=lost
                with self.assertRaisesRegex(EOFError,'grouped FULL-commit'):capture(m)
                self.assertEqual(body.payload_bytes_sent,uploaded)
            with current_map(self.client,'group-points',digest,binding=binding) as m:
                self.assertEqual(capture(m)['completed_members'],0)
                self.assertEqual(m.db.execute('select count(*) from file_acceptance_history').fetchone(),(2,))
                self.assertEqual(body.payload_bytes_sent,uploaded)
            self.assertEqual(self.client.metrics()['operations']['accept-file-points']['requests'],2)
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
        self.addCleanup(store.restore_temporary_scope)
        db=sqlite3.connect(':memory:');self.addCleanup(db.close);store.configure(db)
        with self.assertRaises(sqlite3.OperationalError):
            db.execute('with recursive n(x) as (values(1) union all select x+1 from n where x<1000000) select sum(x) from n').fetchone()
        self.assertIn('explicit owner stop',store.guard_reason)


if __name__=='__main__':unittest.main()
