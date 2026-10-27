import hashlib
import ast
import base64
import json
from pathlib import Path
import tempfile
import unittest
import time
import io
import subprocess
from unittest.mock import patch
from types import SimpleNamespace

import vk_nightly_typed_worker as worker
from vk_nightly_desktop_objects import DesktopObjects,NATIVE


class TypedWorkerTests(unittest.TestCase):
    def config(self):
        folder=Path(worker.__file__).parent
        return dict(format='vk-nightly-typed-file-worker-v1',
            source_sha256={name:worker.checksum(folder/name) for name in worker.source_closure(folder)},
            map='/mnt/vk-storage/nightly-test-map.sqlite',status='/mnt/vk-storage/nightly-test-status.json',
            map_binding={'test':True},maximum_map_bytes=1024**2,maximum_members=2,maximum_source_bytes=65536,
            chunk_bytes=4096,timeout_seconds=60,ssd_floor_bytes=2*1024**3,root_floor_bytes=2*1024**3,
            control_margin_bytes=1024**2,memory_floor_bytes=4*1024**3,swap_floor_bytes=1024**3,
            baseline_accepted=False,schedule_enabled=False,
            desktop=dict(B_root='B:/vk-backups/nightly-fixture',maximum_object_bytes=8192,protected_B_bytes=8*1024**3,
                volume_device=2360624474,object_module_sha256=worker.checksum(folder/'vk_nightly_objects.py'),
                identity_ps='reviewed probe',identity_probe_sha256=hashlib.sha256(b'reviewed probe').hexdigest()))

    def test_installed_config_authenticates_complete_code_closure_and_never_enables_calendar(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'config.json';config=self.config();p.write_text(json.dumps(config));p.chmod(0o600)
            self.assertFalse(worker.configuration(p,worker.checksum(p))['schedule_enabled'])
            del config['source_sha256']['vk_typed_recovery.py'];p.write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError,'binding incomplete'):worker.configuration(p,worker.checksum(p))
            config=self.config();config['schedule_enabled']=True;p.write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError,'whole-cycle'):worker.configuration(p,worker.checksum(p))

    def test_mismatched_MM_source_refuses_before_writer_or_SSH(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'guard.py';p.write_text('not the reviewed guard')
            config=self.config()['desktop'];config.update(MM_source=str(p),MM_sha256='0'*64)
            with patch('vk_nightly_desktop_objects.subprocess.Popen') as start:
                with self.assertRaisesRegex(ValueError,'MM code changed'):
                    with DesktopObjects(config,guard=lambda:None):pass
                start.assert_not_called()

    def test_separate_health_cadence_requires_explicit_interval_and_kernel_continuity(self):
        from vk_nightly_desktop_objects import validate
        config=self.config()['desktop'];objects=Path(worker.__file__).with_name('vk_nightly_objects.py').read_text()
        config['native_health_poll_seconds']=60
        with self.assertRaisesRegex(ValueError,'kernel identity continuity'):validate(config,objects)
        config.update(native_identity_mode='admission-plus-kernel-continuity-v1',identity_admission_timeout_seconds=45)
        validate(config,objects)
        for invalid in (0,True,3600):
            config['native_health_poll_seconds']=invalid
            with self.assertRaisesRegex(ValueError,'polling interval'):validate(config,objects)

    def test_selected_qualification_without_authenticated_source_refuses_before_B_access(self):
        with patch.object(worker,'DesktopControls') as remote:
            with self.assertRaisesRegex(ValueError,'authenticated current source'):
                worker.run_B(dict(qualification={}))
            remote.assert_not_called()

    def test_current_SQL_cohort_cannot_blindly_inherit_prior_completed_points(self):
        config=dict(self.config(),SQL_sources=[],SQL_catalog_sha256='a'*64,current_SQL_cohort_id='b'*64,
            SQL_reuse_controls=[dict(index_name='older',checkpoint_sha256='c'*64)])
        with patch.object(worker,'DesktopObjects') as remote:
            with self.assertRaisesRegex(ValueError,'blindly inherit'):worker.run_SQL(config)
            remote.assert_not_called()

    def test_unresolved_SQL_template_cannot_execute_an_empty_successful_capture(self):
        config=dict(self.config(),SQL_sources=[],SQL_catalog_sha256='a'*64,SQL_sources_from_current_map=True)
        with patch.object(worker,'DesktopObjects') as remote:
            with self.assertRaisesRegex(ValueError,'resolved current SQL cohort'):worker.run_SQL(config)
            remote.assert_not_called()
        with patch.object(worker,'DesktopControls') as remote:
            with self.assertRaisesRegex(ValueError,'resolved current SQL cohort'):worker.run_B(config)
            remote.assert_not_called()

    def test_native_receiver_source_is_syntactically_valid(self):compile(NATIVE,'native','exec')

    def test_actual_native_health_record_preserves_MM_temperature_and_hardware_fields(self):
        nodes=[n for n in ast.parse(NATIVE).body if isinstance(n,ast.FunctionDef) and n.name in ('control_identity','actual_guard')]
        code='\n'.join(ast.get_source_segment(NATIVE,node) for node in nodes)
        hardware=dict(serial_number='verified',smart_status={'passed':True},temperature={'current':31},
            ata_smart_attributes={'table':[{'id':5,'raw':{'value':0}}]},sata_phy_event_counters={'table':[{'id':1,'value':0}]})
        identity={'disk_number':3,'partition_number':2,'volume_guid':'fixture'};records=[]
        mm=SimpleNamespace(STOP_PATH='stop',STATE_PATH='state',parse=lambda s:{'Drives':[]},
            bounded_read=lambda s:'{}',pause=lambda r:None,b_outside_monitor_scope=lambda a,b:True,
            check_identity=lambda r:None,check_health=lambda r:records.append(r))
        class Job:
            def __truediv__(self,name):return self
            def stat(self):raise FileNotFoundError('no own STOP')
        class Child:
            def __init__(self,value):self.stdout=json.dumps(value).encode()
            def check_returncode(self):pass
        answers=iter([Child(identity),Child(hardware),Child(identity)])
        namespace=dict(mm=mm,job=Job(),baseline={'NativeSerial':'verified','Attributes':[{'id':5,'raw':{'value':0}}],
            'Phy':[{'id':1,'value':0}]},CONFIG={'identity_ps':'probe','volume_device':123,'protected_B_bytes':100},
            subprocess=SimpleNamespace(run=lambda *a,**k:next(answers),TimeoutExpired=subprocess.TimeoutExpired),base64=base64,json=json,
            os=SimpleNamespace(stat=lambda p:SimpleNamespace(st_dev=123)),
            shutil=SimpleNamespace(disk_usage=lambda p:SimpleNamespace(free=10000000)),
            datetime=__import__('datetime'),time=__import__('time'),sys=SimpleNamespace(stderr=__import__('io').StringIO()),
            health_observations=0,health_query_seconds=0.0)
        namespace['health_timeout_used']=False;namespace['admitted_identity']=None
        namespace['health_gate']=__import__('contextlib').nullcontext
        exec(code,namespace);namespace['actual_guard'](1024)
        self.assertEqual(records[0]['temperature'],31);self.assertTrue(records[0]['smart_passed'])
        self.assertEqual(records[0]['attributes'],{'5':0})
        # Full MM identity admission is retained; later checks use live kernel
        # disk/partition/GUID plus actual SMART/STOP checks, not repeated CIM.
        namespace['CONFIG'].update(native_identity_mode='admission-plus-kernel-continuity-v1',identity_admission_timeout_seconds=45)
        namespace['admitted_identity']=None;namespace['kernel_identity']=lambda:dict(identity)
        calls=[];answers=iter([Child(identity),Child(hardware),Child(hardware)])
        namespace['subprocess']=SimpleNamespace(run=lambda *a,**k:(calls.append((a,k)) or next(answers)),TimeoutExpired=subprocess.TimeoutExpired)
        mm.check_identity=lambda value: self.assertEqual(value,identity)
        namespace['actual_guard'](1024);namespace['actual_guard'](1024)
        self.assertEqual(len(calls),3)
        self.assertEqual(calls[0][1]['timeout'],45)
        final=next(n for n in ast.parse(NATIVE).body if isinstance(n,ast.FunctionDef) and n.name=='final_guard')
        exec(ast.get_source_segment(NATIVE,final),namespace)
        answers=iter([Child(identity),Child(hardware)])
        namespace['final_guard'](1024)
        self.assertEqual(len(calls),5,'final acceptance must repeat full fresh identity admission')
        namespace['kernel_identity']=lambda:dict(identity,disk_number=4)
        with self.assertRaises(AssertionError):namespace['actual_guard'](1024)
        self.assertEqual(len(calls),5,'changed identity must fail before another operation')
        mm.bounded_read=lambda _:(_ for _ in ()).throw(PermissionError('STOP unreadable'))
        with self.assertRaisesRegex(PermissionError,'STOP unreadable'):namespace['actual_guard'](1024)
        self.assertEqual(len(calls),5,'denied controls must never be bypassed')

    def test_actual_space_floor_and_deadline_defer_without_other_process_changes(self):
        config=self.config()
        with patch.object(worker.os.path,'ismount',return_value=True),patch.object(worker.os,'statvfs') as fs:
            fs.return_value.f_bavail=0;fs.return_value.f_frsize=4096
            with self.assertRaisesRegex(worker.ResourceDeferred,'free space'):worker.host_guard(config,0)

    def test_native_B_control_worker_does_not_require_unused_SSD_write_headroom(self):
        config=self.config();config['format']='vk-nightly-typed-worker-B-v1';seen=[]
        def statvfs(path):
            seen.append(path)
            if path=='/mnt/vk-storage':raise AssertionError('B control worker should not allocate an SSD index/temp journal')
            return SimpleNamespace(f_bavail=100000000,f_frsize=4096)
        with patch.object(worker.os.path,'ismount',return_value=True),patch.object(worker.os,'statvfs',side_effect=statvfs),\
             patch.object(worker.Path,'read_text',return_value='MemAvailable: 16777216 kB\nSwapFree: 8388608 kB\n'):
            worker.host_guard(config,time.monotonic())
        self.assertEqual(seen,['/'])

    def test_SQL_serial_boundary_fault_retains_completed_point_and_resume_never_recaptures(self):
        import sqlite3,subprocess,sys
        from contextlib import contextmanager
        from vk_nightly_objects import ObjectClient
        with tempfile.TemporaryDirectory(dir='/dev/shm') as tmp:
            root=Path(tmp);source=root/'source.sqlite';objects=root/'objects';objects.mkdir()
            with sqlite3.connect(source) as db:
                db.execute('create table saved(value)');db.execute("insert into saved values('current')")
            catalog=root/'catalog.json';catalog.write_text(json.dumps(dict(sql_images={})))
            config=dict(self.config(),SQL_sources=[str(source)],SQL_catalog=str(catalog),
                SQL_catalog_sha256=worker.checksum(catalog),maximum_SQL_image_bytes=1024**2,
                SQL_image_timeout_seconds=15,status=str(root/'status.json'),current_SQL_cohort_id='a'*64)
            ledger=sqlite3.connect(root/'ledger.sqlite');self.addCleanup(ledger.close)
            ledger.execute('create table state(row text)');ledger.commit()
            class Backend:
                def load(self,default):
                    row=ledger.execute('select row from state').fetchone()
                    return json.loads(row[0]) if row else default
                def save(self,state,status):
                    ledger.execute('delete from state')
                    ledger.execute('insert into state values(?)',(json.dumps(state),));ledger.commit()
            backend=Backend();folder=str(Path(worker.__file__).parent)
            code='import sys;sys.path.insert(0,'+repr(folder)+');from vk_nightly_objects import receive;receive('+repr(str(objects))+',sys.stdin.buffer,sys.stdout.buffer,guard=lambda n:None,maximum_object_bytes=65536)'
            child=subprocess.Popen([sys.executable,'-B','-u','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            client=ObjectClient(child.stdout,child.stdin,guard=lambda:None,ram_root=root,maximum_object_bytes=65536)
            @contextmanager
            def remote(*_,**__):yield SimpleNamespace(client=client)
            def deliver():
                state=backend.load({})
                if state.get('completed'):raise RuntimeError('injected serial delivery failure')
            try:
                with patch.object(worker,'host_guard',lambda *_:None),patch.object(worker,'DesktopObjects',remote):
                    with self.assertRaisesRegex(RuntimeError,'serial delivery'):
                        worker.run_SQL(config,backend=backend,at_component_boundary=deliver)
                    state=backend.load({});point=state['completed'][str(source)]
                    self.assertEqual(point['independent']['integrity'],'ok')
                    self.assertEqual(point['SQL_cohort_id'],'a'*64)
                    before={p.name:p.stat().st_ino for p in objects.iterdir()}
                    called=[]
                    with patch.object(worker,'capture_SQL_point',side_effect=AssertionError('completed point recaptured')):
                        result=worker.run_SQL(config,backend=backend,at_component_boundary=lambda:called.append(True))
                    self.assertFalse(result['more_pending']);self.assertTrue(called)
                    self.assertEqual(backend.load({})['completed'][str(source)],point)
                    self.assertEqual({p.name:p.stat().st_ino for p in objects.iterdir()},before)
                    with self.assertRaisesRegex(ValueError,'input binding changed'):
                        worker.run_SQL(dict(config,current_SQL_cohort_id='b'*64),backend=backend)
            finally:
                child.stdin.close();child.wait(timeout=5);child.stdout.close();child.stderr.close()

    def test_B_native_SQL_path_passes_the_same_serial_boundary_without_background_work(self):
        import sqlite3
        from contextlib import contextmanager
        database=sqlite3.connect(':memory:');self.addCleanup(database.close)
        @contextmanager
        def remote(*_,**__):yield SimpleNamespace(client=SimpleNamespace(connect=lambda *_:database))
        boundary=lambda:None
        config=dict(self.config(),phase_kind='SQL-points',B_controls={},B_index_name='fixture',B_checkpoint_sha256='a'*64)
        with patch.object(worker,'host_guard',lambda *_:None),patch.object(worker,'DesktopControls',remote),patch.object(worker,'run_SQL',return_value={'completed':True}) as run:
            self.assertEqual(worker.run_B(config,at_component_boundary=boundary),{'completed':True})
        self.assertIs(run.call_args.kwargs['at_component_boundary'],boundary)

    def test_owned_readback_pipe_is_closed_before_wait_on_aborted_session(self):
        class Pipe:
            closed=False
            def close(self):self.closed=True
        output=Pipe()
        def wait(timeout):
            self.assertTrue(output.closed,'full readback pipe would prevent terminal wait')
            return 0
        session=DesktopObjects({},guard=lambda:None)
        session.process=SimpleNamespace(stdin=Pipe(),stdout=output,stderr=io.BytesIO(),wait=wait)
        session.lease=Pipe();session.__exit__(RuntimeError,RuntimeError('own guard stop'),None)
        self.assertTrue(session.lease.closed)


if __name__=='__main__':unittest.main()
