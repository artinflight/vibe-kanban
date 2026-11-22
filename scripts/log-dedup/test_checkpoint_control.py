import errno
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from unittest.mock import patch

import checkpoint_control as cc
import controlled_conversion as driver
import boundary_handoff as handoff

OP='a'*32


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir='/dev/shm');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.controls=cc.Controls(self.root,OP)
    def request(self,action):return self.controls.request(action,str(uuid.uuid4()),'Operator request')
    def test_defaults_to_pause_without_starting_any_worker(self):
        status=self.controls.status();self.assertEqual(status['command']['action'],'pause')
        self.assertIsNone(status['worker']);self.assertFalse(status['worker_identity_live'])
    def test_same_request_is_idempotent_and_cannot_replay_over_newer_command(self):
        first=self.request('pause');self.request('resume')
        self.controls.request('pause',first['request_id'],'Operator request')
        self.assertEqual(self.controls.command()['action'],'resume')
        with self.assertRaises(ValueError):self.controls.request('resume',first['request_id'],'Operator request')
    def test_request_published_after_interrupted_command_pointer_write(self):
        request_id=str(uuid.uuid4());real=cc.atomic
        def interrupted(path,value):
            if path.name=='command.json':raise OSError('simulated interruption')
            return real(path,value)
        with patch.object(cc,'atomic',interrupted):
            with self.assertRaises(OSError):self.controls.request('resume',request_id,'Requested')
        self.assertEqual(self.controls.command()['action'],'pause')
        self.controls.request('resume',request_id,'Requested')
        self.assertEqual(self.controls.command()['action'],'resume')
    def test_bad_operation_missing_receipt_and_symlink_fail_closed(self):
        command=self.request('resume');command['operation']='b'*32;cc.atomic(self.root/'command.json',command)
        with self.assertRaises(ValueError):self.controls.command()
        (self.root/'command.json').unlink();(self.root/'command.json').symlink_to('/etc/passwd')
        with self.assertRaises(OSError):self.controls.command()
    def test_pause_is_effective_only_at_verified_boundary(self):
        self.request('pause');events=[]
        def sleep(_):
            self.assertEqual(cc.read(self.root/'status.json')['state'],'paused')
            events.append('paused');self.request('resume')
        self.controls.boundary({'next_batch':3},attempt='controlled1',verify_released=lambda:events.append('released'),
            identity_check=lambda:events.append('identity'),sleep=sleep)
        self.assertEqual(events,['released','identity','released','paused','identity'])
        self.assertEqual(cc.read(self.root/'status.json')['state'],'ready')
    def test_boundary_cannot_claim_paused_with_open_backup_lease(self):
        lease=self.root/'backup.lock';lease.touch(mode=0o600)
        with lease.open() as stream:
            fcntl.flock(stream,fcntl.LOCK_EX)
            with self.assertRaisesRegex(ValueError,'descriptor still open'):
                self.controls.boundary({},attempt='x',verify_released=lambda:driver.assert_leases_closed([lease],[os.getpid()]),identity_check=lambda:None)
        driver.assert_leases_closed([lease],[os.getpid()])
    def test_changed_owner_or_directory_stops_control_wait(self):
        with self.assertRaisesRegex(ValueError,'changed reader'):
            self.controls.boundary({},attempt='x',verify_released=lambda:None,identity_check=lambda:(_ for _ in ()).throw(ValueError('changed reader')))
        old=self.root/'original';old.mkdir(mode=0o700);other=cc.Controls(old,OP);old.rename(self.root/'moved');old.mkdir()
        with self.assertRaisesRegex(ValueError,'replaced'):other.command()
    def test_status_binds_live_process_and_does_not_dump_checkpoint_catalog(self):
        self.controls.publish('paused',{'pins':[{'secret':'no'}],'next_batch':7},attempt='x')
        value=self.controls.status();self.assertTrue(value['worker_identity_live'])
        self.assertNotIn('pins',value['worker']['checkpoint'])
    def test_initial_flock_contention_only_is_retryable(self):
        source=self.root/'vk_nightly_desktop_objects.py'
        source.write_text('import fcntl\nclass DesktopObjects:\n def __enter__(self):\n  fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB)\n')
        spec=importlib.util.spec_from_file_location('fixture_lock',source);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        lease=self.root/'lease';lease.touch(mode=0o600)
        with lease.open() as held,lease.open() as wanted:
            fcntl.flock(held,fcntl.LOCK_EX);obj=m.DesktopObjects();obj.fd=wanted.fileno()
            try:obj.__enter__()
            except BlockingIOError as error:self.assertTrue(driver.lease_busy_before_capture(error,self.root))
        try:raise BlockingIOError(errno.EAGAIN,'uncertain downstream IO')
        except BlockingIOError as error:self.assertFalse(driver.lease_busy_before_capture(error,self.root))
        try:raise PermissionError('access denied')
        except PermissionError as error:self.assertFalse(driver.lease_busy_before_capture(error,self.root))


class NaturalHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir='/dev/shm');self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
    def test_real_process_releases_at_boundary_then_refuses_next_admission(self):
        lock=self.root/'lane';lock.touch(mode=0o600)
        code='''import fcntl,os,sys,time
from pathlib import Path
p=Path(sys.argv[1]);f=p.open('r+');fcntl.flock(f,fcntl.LOCK_EX);print('writing',flush=True)
sys.stdin.readline();(p.parent/'durable-batch').write_text('complete');f.close();print('closed',flush=True)
sys.stdin.readline();f=p.open('r+')
try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:print('admission-held-no-next-write',flush=True);sys.exit(0)
raise RuntimeError('test handoff failed to acquire')
'''
        process=subprocess.Popen([sys.executable,'-c',code,str(lock)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
        self.addCleanup(lambda:process.kill() if process.poll() is None else None)
        self.assertEqual(process.stdout.readline().strip(),'writing');identity=cc.process_identity(process.pid)
        observations=[]
        def delay(_):
            self.assertFalse((self.root/'durable-batch').exists())
            process.stdin.write('finish\n');process.stdin.flush()
            self.assertEqual(process.stdout.readline().strip(),'closed')
        with handoff.acquire_naturally(lock,identity,deadline=time.time()+10,observe=observations.append,sleep=delay):
            self.assertEqual((self.root/'durable-batch').read_text(),'complete')
            process.stdin.write('next\n');process.stdin.flush()
            self.assertEqual(process.stdout.readline().strip(),'admission-held-no-next-write')
            process.wait(timeout=5)
        process.stdin.close();process.stdout.close()
        self.assertEqual(process.returncode,0)
        self.assertEqual(observations,['waiting_for_natural_release','normal_admission_lock_acquired'])
        with lock.open() as free:fcntl.flock(free,fcntl.LOCK_EX|fcntl.LOCK_NB)
    def test_timeout_does_not_release_another_owners_lock(self):
        path=self.root/'lane';path.touch(mode=0o600)
        with path.open() as existing:
            fcntl.flock(existing,fcntl.LOCK_EX)
            with self.assertRaisesRegex(ValueError,'deadline'):
                with handoff.acquire_naturally(path,cc.process_identity(os.getpid()),deadline=time.time()-1):self.fail('entered')
            with path.open() as another:
                with self.assertRaises(BlockingIOError):fcntl.flock(another,fcntl.LOCK_EX|fcntl.LOCK_NB)
    def test_wrong_termination_never_qualifies_for_resume(self):
        cc.atomic(self.root/'FAILURE.private.json',dict(operation=OP,attempt='resume3',at=time.time(),type='OSError',error='unknown failure'))
        request=dict(operation=OP,old_attempt='resume3',requested_at=0,old_process={'pid':999999999,'start_ticks':0,'boot_id':'none'})
        with self.assertRaisesRegex(ValueError,'expected pre-capture'):handoff.verify_exit(self.root,request)


if __name__=='__main__':unittest.main()

class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir='/dev/shm');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.folder=self.root/'batch-0000';self.folder.mkdir()
        (self.folder/'journal').mkdir();(self.folder/'graph-recovery').mkdir()
        (self.root/'canary').mkdir();cc.atomic(self.root/'canary/RESULT.private.json',dict(complete=True,normal_B_original_and_graph_verified=True))
        self.source=self.root/'source';self.source.mkdir();self.manifest=self.source/'log';self.manifest.write_bytes(b'VKLOGCAS1\n{}')
        info=self.manifest.stat();self.row=dict(batch=0,files=1,raw_bytes=100,result=str(self.folder/'RESULT.private.json'))
        cc.atomic(self.root/'FINITE_BATCHES.private.json',dict(operation=OP,files=2,batches=[dict(names=['log']),dict(names=['next'])]))
        self.committed=dict(operation=OP,batches=[self.row],skipped=[],completed_batches=1,completed_files=2,
                            resolved_files=2,total_files=3,total_batches=2)
        cc.atomic(self.root/'COMMITTED.private.json',self.committed)
        cc.atomic(self.folder/'PLAN.private.json',dict(source_root=str(self.source),files=[dict(path='log')]))
        cc.atomic(self.folder/'NONBENEFICIAL.private.json',[])
        cc.atomic(self.folder/'RESULT.private.json',dict(complete=True,normal_B_original_and_graph_verified=True,files=1,raw_bytes=100))
        cc.atomic(self.folder/'journal/state.json',dict(complete=True,outcome='installed',files={'log':dict(state='installed',
            installed_identity=[info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns],manifest_sha256=driver.sha(self.manifest))}))
        cc.atomic(self.folder/'CARRIER_RETIREMENT_RESULT.private.json',dict(complete=True,primary_objects_and_all_B_epochs_preserved=True))
        cc.atomic(self.folder/'DYNAMIC_RECOVERY.private.json',dict(actual_independent_normal_restore=dict(independent_owner_controls_restore_verified=True)))
    def test_complete_prefix_is_adopted_without_replaying_it(self):
        cp=driver.checkpoint(self.root,True);self.assertEqual(cp['next_batch'],1)
        self.assertEqual(driver.checkpoint(self.root,trusted_prefix=cp)['checkpoint_sha256'],cp['checkpoint_sha256'])
    def test_partial_next_install_or_backup_is_not_adopted(self):
        folder=self.root/'batch-0001';folder.mkdir();(folder/'journal').mkdir()
        with self.assertRaisesRegex(ValueError,'unreconciled'):driver.checkpoint(self.root)
        (folder/'journal').rmdir();(folder/'graph-recovery').mkdir()
        cc.atomic(folder/'graph-recovery/graph-checkpoint-0.json',{})
        with self.assertRaisesRegex(ValueError,'unreconciled'):driver.checkpoint(self.root)
    def test_changed_installed_bytes_or_incomplete_proof_refused(self):
        self.manifest.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'manifest changed'):driver.checkpoint(self.root,True)
        cc.atomic(self.folder/'DYNAMIC_RECOVERY.private.json',dict(actual_independent_normal_restore=dict(independent_owner_controls_restore_verified=False)))
        with self.assertRaisesRegex(ValueError,'incomplete recovery'):driver.checkpoint(self.root)
    def test_changed_committed_prefix_cannot_be_hidden_by_cached_validation(self):
        cp=driver.checkpoint(self.root);self.committed['batches'][0]['raw_bytes']=1
        cc.atomic(self.root/'COMMITTED.private.json',self.committed)
        with self.assertRaisesRegex(ValueError,'prefix was rewritten'):driver.checkpoint(self.root,trusted_prefix=cp)
    def test_missing_final_retirement_or_foreign_operation_refused(self):
        cc.atomic(self.folder/'CARRIER_RETIREMENT_RESULT.private.json',dict(complete=False,primary_objects_and_all_B_epochs_preserved=True))
        with self.assertRaisesRegex(ValueError,'incomplete recovery'):driver.checkpoint(self.root)
        self.committed['operation']='b'*32;cc.atomic(self.root/'COMMITTED.private.json',self.committed)
        with self.assertRaisesRegex(ValueError,'foreign'):driver.checkpoint(self.root)
    def test_natural_admission_exit_qualifies_only_exact_complete_prefix(self):
        failure=dict(operation=OP,attempt='resume3',at=time.time(),type='BlockingIOError',completed_batches=1,
                     error='MCP producer lease still held by parent or inherited owned child; defer B reconciliation')
        cc.atomic(self.root/'FAILURE.private.json',failure)
        request=dict(operation=OP,old_attempt='resume3',requested_at=0,old_process={'pid':999999999,'start_ticks':0,'boot_id':'none'})
        result=handoff.verify_exit(self.root,request);self.assertTrue(result['verified'])
        self.assertEqual(result['checkpoint']['next_batch'],1)

class MonitorControlTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir='/dev/shm');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.controls=cc.Controls(self.root,OP)
        self.controls.publish('paused',{'next_batch':2},attempt='controlled1')
        cc.atomic(self.root/'CONTROLLER_SEAL.private.json',dict(operation=OP,attempt='controlled1',backup_leases=[]))
        self.row=dict(operation=OP,attempt='controlled1',state='stalled',needs_attention=True,progress_at=10)
        self.service=dict(ActiveState='active',MainPID=str(os.getpid()))
    def test_live_verified_pause_does_not_fake_progress(self):
        import control_observation as monitor
        result=monitor.supplement(self.row,{'checkpoint_controls':str(self.root)},self.service,time.time())
        self.assertEqual(result['state'],'paused');self.assertFalse(result['needs_attention']);self.assertEqual(result['progress_at'],10)
    def test_failure_or_dead_stale_wrong_owner_still_alerts(self):
        import control_observation as monitor
        for row,service,at in [(dict(self.row,state='failure_recovery_pending'),self.service,time.time()),
                (self.row,dict(self.service,MainPID='999999999'),time.time()),
                (self.row,self.service,time.time()+61),
                (dict(self.row,attempt='other'),self.service,time.time())]:
            self.assertEqual(monitor.supplement(row,{'checkpoint_controls':str(self.root)},service,at),row)
    def test_requested_pause_is_visible_without_claiming_a_released_boundary(self):
        import control_observation as monitor
        self.controls.publish('running',{'next_batch':2},attempt='controlled1')
        self.controls.request('pause',str(uuid.uuid4()),'Operator request')
        result=monitor.supplement(self.row,{'checkpoint_controls':str(self.root)},self.service,time.time())
        self.assertEqual(result['state'],'stalled');self.assertTrue(result['needs_attention'])
        self.assertEqual(result['control_request'],'pause');self.assertEqual(result['progress_at'],10)
    def test_open_backup_lease_prevents_false_pause_report(self):
        import control_observation as monitor
        path=self.root/'lane';path.touch(mode=0o600)
        cc.atomic(self.root/'CONTROLLER_SEAL.private.json',dict(operation=OP,attempt='controlled1',backup_leases=[str(path)]))
        with path.open():
            self.assertEqual(monitor.supplement(self.row,{'checkpoint_controls':str(self.root)},self.service,time.time()),self.row)

class ControlledDriverTests(unittest.TestCase):
    setUp=CheckpointTests.setUp
    def test_real_driver_pauses_between_batches_then_resumes_without_replay(self):
        from types import SimpleNamespace
        control=self.root/'checkpoint-controls-fixture';control.mkdir(mode=0o700);controls=cc.Controls(control,OP)
        selection=cc.read(self.root/'FINITE_BATCHES.private.json');selection['files']=3
        selection['batches'].append(dict(names=['last']))
        for row in selection['batches']:row['workspace']='fixture'
        cc.atomic(self.root/'FINITE_BATCHES.private.json',selection)
        self.committed.update(total_files=4,total_batches=3);cc.atomic(self.root/'COMMITTED.private.json',self.committed)
        override=None;old_staging=None
        if getattr(self,'isolated_staging',False):
            parent=control/'isolated-preparations';parent.mkdir(mode=0o700)
            override=dict(batch=1,path=str(parent/'batch-0001'))
            old_staging=self.root/'batch-0001';old_staging.mkdir()
            (old_staging/'unrelated-consumer').write_text('must remain unchanged')
            handle=os.open(old_staging,os.O_RDONLY|os.O_DIRECTORY);self.addCleanup(os.close,handle)
        for number,name in [] if override else [(1,'next')]:
            folder=self.root/('batch-'+str(number).zfill(4));folder.mkdir();cc.atomic(folder/'PREPARATION_COMPLETE.private.json',{'complete':True})
        failure=dict(operation=OP,type='BlockingIOError');cc.atomic(self.root/'FAILURE.private.json',failure)
        cp=driver.checkpoint(self.root,True,batch_override=override)
        handoff_path=control/'HANDOFF.private.json';cc.atomic(handoff_path,dict(verified=True,operation=OP,
            old_process={'pid':999999999,'start_ticks':0,'boot_id':'none'},checkpoint=cp,batch_override=override,failure_sha256=driver.sha(self.root/'FAILURE.private.json')))
        if getattr(self,'clean_handoff',False):
            clean=cc.read(handoff_path)
            clean['clean_paused_boundary']=True
            clean['pause_status']={'state':'paused','process':clean['old_process'],'checkpoint':cp}
            clean.pop('failure_sha256');(self.root/'FAILURE.private.json').unlink()
            cc.atomic(handoff_path,clean)
        lease=self.root/'backup.lock';lease.touch(mode=0o600)
        seal=control/'seal.json';cc.atomic(seal,dict(sources=[],handoff=str(handoff_path),operation=OP,attempt='controlled1',backup_leases=[str(lease)]))
        seen=[];base=SimpleNamespace(operation=OP,selection=selection)
        original_progress=dict(at=10,phase='finite_batch_committed');cc.atomic(self.root/'PROGRESS.private.json',original_progress)
        busy_calls=[]
        gate=self.root/'vk_nightly_desktop_objects.py'
        gate.write_text('import fcntl\nclass DesktopObjects:\n def __enter__(self):\n  fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB)\n')
        spec=importlib.util.spec_from_file_location('driver_fixture_gate',gate);gate_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate_module)
        def metadata():return dict(operation=OP,batches=base.committed,skipped=base.skipped,
            completed_batches=len(base.committed),completed_files=1+sum(r['files']for r in base.committed),
            resolved_files=1+sum(r['files']for r in base.committed),total_files=4,total_batches=3)
        base.metadata=metadata
        def convert(folder,next_batch=None):
            if getattr(self,'simulate_busy',False) and not busy_calls:
                busy_calls.append(True);cc.atomic(self.root/'PROGRESS.private.json',dict(at=time.time(),phase='normal_B_graph_backup_and_restore_started'))
                with lease.open() as held,lease.open() as wanted:
                    fcntl.flock(held,fcntl.LOCK_EX);gate_object=gate_module.DesktopObjects();gate_object.fd=wanted.fileno();gate_object.__enter__()
            number=int(folder.name[-4:]);seen.append(number)
            self.assertEqual(cc.read(control/'status.json')['state'],'running')
            with lease.open() as f:
                fcntl.flock(f,fcntl.LOCK_EX)
                controls.request('pause',str(uuid.uuid4()),'Exercise checkpoint pause')
                self.assertEqual(cc.read(control/'status.json')['state'],'running')
                name=selection['batches'][number]['names'][0];path=self.source/name;path.write_bytes(b'VKLOGCAS1\n{}');info=path.stat()
                (folder/'journal').mkdir();(folder/'graph-recovery').mkdir()
                cc.atomic(folder/'PLAN.private.json',dict(source_root=str(self.source),files=[dict(path=name)]))
                cc.atomic(folder/'NONBENEFICIAL.private.json',[])
                cc.atomic(folder/'journal/state.json',dict(complete=True,outcome='installed',files={name:dict(state='installed',
                    installed_identity=[info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns],manifest_sha256=driver.sha(path))}))
                cc.atomic(folder/'DYNAMIC_RECOVERY.private.json',dict(actual_independent_normal_restore=dict(independent_owner_controls_restore_verified=True)))
                cc.atomic(folder/'RESULT.private.json',dict(complete=True,normal_B_original_and_graph_verified=True,
                    files=1,raw_bytes=100,allocated_release_including_objects_and_directories=20))
                if next_batch is not None:
                    next_folder=next_batch[0];next_folder.mkdir();cc.atomic(next_folder/'PREPARATION_COMPLETE.private.json',{'complete':True})
        def retire(folder):cc.atomic(folder/'CARRIER_RETIREMENT_RESULT.private.json',dict(complete=True,primary_objects_and_all_B_epochs_preserved=True))
        base.retire_carriers=retire
        worker=SimpleNamespace(C={'source_root':str(self.source),'nightly':{'folder':str(self.root)}},
            readers=SimpleNamespace(check_identities=lambda:None,check=lambda:None),convert=convert,
            save=cc.atomic,progress=lambda *a:None,physical_accounting=SimpleNamespace(measure=lambda *a,**k:{'fixture':True}))
        def prepare(folder,names,workspace):
            self.assertEqual(folder,Path(override['path']));self.assertFalse(folder.exists())
            folder.mkdir();cc.atomic(folder/'PREPARATION_COMPLETE.private.json',{'complete':True})
        worker.prepare=prepare
        base.w=worker
        real_boundary=cc.Controls.boundary;pauses=[]
        def boundary(instance,checkpoint,**kw):
            def wake(_):
                value=cc.read(control/'status.json');self.assertEqual(value['state'],'paused')
                with lease.open() as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
                pauses.append(value['checkpoint']['next_batch']);controls.request('resume',str(uuid.uuid4()),'Fixture owner release')
            kw['sleep']=wake
            return real_boundary(instance,checkpoint,**kw)
        def busy_sleep(_):
            self.assertEqual(cc.read(self.root/'PROGRESS.private.json'),original_progress)
            self.assertEqual(cc.read(control/'status.json')['state'],'waiting_for_backup')
        real_locked=cc.locked
        original_exists=Path.exists
        def exists(path):
            return True if path==self.root.parents[1]/'production-owner.lock' else original_exists(path)
        with patch.object(driver.time,'sleep',busy_sleep),patch.object(Path,'exists',exists),patch.object(driver,'load_legacy',return_value=base),patch.object(driver,'locked',side_effect=lambda *a,**k:real_locked(self.root/'owner.lock',**k)),\
             patch.object(driver,'context_pids',return_value=[os.getpid()]),patch.object(cc.Controls,'boundary',boundary):
            driver.run(self.root,control,seal)
        self.assertEqual(seen,[1,2]);self.assertEqual(pauses,[1,2])
        self.assertEqual(cc.read(control/'status.json')['state'],'complete')
        result=cc.read(self.root/'RESULT.private.json');self.assertTrue(result['finite_conversion_complete'])
        self.assertFalse(result['full_objective_verified']);self.assertEqual(result['completed_files'],4)
        self.assertEqual((control/'LEGACY_BOUNDARY_EXIT.private.json').exists(),not getattr(self,'clean_handoff',False))
        if old_staging is not None:
            self.assertEqual(old_staging.stat().st_ino,os.fstat(handle).st_ino)
            self.assertEqual((old_staging/'unrelated-consumer').read_text(),'must remain unchanged')
            self.assertEqual(sorted(p.name for p in old_staging.iterdir()),['unrelated-consumer'])

    def test_clean_paused_handoff_preserves_prefix_without_fabricating_failure(self):
        self.clean_handoff=True
        self.test_real_driver_pauses_between_batches_then_resumes_without_replay()

    def test_isolated_batch_uses_new_path_and_leaves_live_old_consumer_untouched(self):
        self.isolated_staging=True
        self.test_real_driver_pauses_between_batches_then_resumes_without_replay()

    def test_initial_backup_contention_waits_without_replay_or_fake_progress(self):
        self.simulate_busy=True
        self.test_real_driver_pauses_between_batches_then_resumes_without_replay()

class TerminalRecoveryTests(unittest.TestCase):
    setUp=CheckpointTests.setUp
    def candidate(self):
        import terminal_checkpoint_recovery as recovery
        self.committed.update(batches=[],completed_batches=0,completed_files=1,resolved_files=1)
        cc.atomic(self.root/'COMMITTED.private.json',self.committed)
        (self.folder/'CARRIER_RETIREMENT_RESULT.private.json').unlink()
        cc.atomic(self.folder/'PLAN.private.json',dict(source_root=str(self.source),files=[dict(path='log',raw_bytes=100,sidecars=[])]))
        result=cc.read(self.folder/'RESULT.private.json');result.update(staging_retirement=dict(all_primary_objects_preserved=True),allocated_release_including_objects_and_directories=20)
        cc.atomic(self.folder/'RESULT.private.json',result)
        cc.atomic(self.folder/'CONVERSION.private.json',dict(complete=True,outcome='installed'))
        (self.root/'batch-0001').mkdir()
        cc.atomic(self.root/'FAILURE.private.json',dict(operation=OP,attempt='resume3',type='CalledProcessError',error=recovery.ERROR,completed_batches=0))
        return recovery,driver.sha(self.root/'FAILURE.private.json')
    def test_complete_batch_before_empty_prefetch_can_be_reconciled(self):
        recovery,digest=self.candidate();value=recovery.inspect(self.root,digest)
        self.assertEqual(value['batch'],0);self.assertEqual(value['validated_installs'],1)
    def test_nonempty_next_preparation_or_other_failure_is_refused(self):
        recovery,digest=self.candidate();cc.atomic(self.root/'batch-0001/B_REQUEST.private.json',{})
        with self.assertRaisesRegex(ValueError,'empty unpublished'):recovery.inspect(self.root,digest)
        failure=cc.read(self.root/'FAILURE.private.json');failure['error']='unknown system failure';cc.atomic(self.root/'FAILURE.private.json',failure)
        with self.assertRaisesRegex(ValueError,'different terminal'):recovery.inspect(self.root,driver.sha(self.root/'FAILURE.private.json'))
    def test_no_incomplete_or_changed_install_can_be_adopted(self):
        recovery,digest=self.candidate();self.manifest.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'manifest differs'):recovery.inspect(self.root,digest)
    def test_reconcile_finalizes_once_and_preserves_empty_directory_and_failure(self):
        from types import SimpleNamespace
        recovery,digest=self.candidate();control=self.root/'controls';control.mkdir(mode=0o700)
        base=SimpleNamespace()
        base.retire_carriers=lambda folder:cc.atomic(folder/'CARRIER_RETIREMENT_RESULT.private.json',dict(complete=True,primary_objects_and_all_B_epochs_preserved=True))
        base.metadata=lambda:dict(self.committed,batches=base.committed,completed_batches=1,completed_files=2,resolved_files=2)
        base.w=SimpleNamespace(save=cc.atomic,progress=lambda *a:None)
        prep=dict(old_process={'pid':999999999,'start_ticks':0,'boot_id':'none'},sources=[],terminal_failure_sha256=digest)
        real_exists=Path.exists
        with patch.object(Path,'exists',lambda p: True if p==self.root.parents[1]/'production-owner.lock' else real_exists(p)),\
             patch.object(recovery,'locked',side_effect=lambda *a,**k:cc.locked(self.root/'owner.lock',**k)),\
             patch.object(recovery,'load_legacy',return_value=base),patch.object(recovery,'no_consumers'):
            proof=recovery.reconcile(self.root,control,prep)
        self.assertTrue(proof['verified']);self.assertEqual(proof['checkpoint']['next_batch'],1)
        self.assertTrue((control/'preserved-empty-next-batch').is_dir());self.assertFalse((self.root/'batch-0001').exists())
        self.assertEqual(driver.sha(self.root/'FAILURE.private.json'),digest)
        self.assertTrue((control/'TERMINAL_RECOVERY_ATTEMPT').exists())


class IsolatedCheckpointTests(unittest.TestCase):
    setUp=CheckpointTests.setUp
    def test_mapping_is_bounded_and_partial_isolated_work_is_refused(self):
        parent=self.root/'checkpoint-controls-fixture'/'isolated-preparations';parent.mkdir(parents=True)
        override=dict(batch=1,path=str(parent/'batch-0001'))
        driver.checkpoint(self.root,True,batch_override=override)
        bad=dict(override,path=str(self.root/'batch-0001'))
        with self.assertRaisesRegex(ValueError,'invalid isolated'):driver.checkpoint(self.root,batch_override=bad)
        folder=Path(override['path']);folder.mkdir();(folder/'journal').mkdir()
        with self.assertRaisesRegex(ValueError,'unreconciled'):driver.checkpoint(self.root,batch_override=override)
    def test_cached_prefix_cannot_change_mapping(self):
        parent=self.root/'checkpoint-controls-fixture'/'isolated-preparations';parent.mkdir(parents=True)
        override=dict(batch=1,path=str(parent/'batch-0001'))
        cp=driver.checkpoint(self.root,batch_override=override)
        with self.assertRaisesRegex(ValueError,'mapping changed'):driver.checkpoint(self.root,trusted_prefix=cp)

class IsolatedRecoveryTests(unittest.TestCase):
    setUp=CheckpointTests.setUp
    candidate=TerminalRecoveryTests.candidate
    def test_recovery_keeps_original_inode_and_open_consumer_and_uses_fresh_path(self):
        from types import SimpleNamespace
        import isolated_checkpoint_recovery as recovery
        _,digest=self.candidate();control=self.root/'checkpoint-controls-fixture';control.mkdir(mode=0o700)
        original=self.root/'batch-0001';descriptor=os.open(original,os.O_RDONLY|os.O_DIRECTORY)
        self.addCleanup(os.close,descriptor);before=original.stat();base=SimpleNamespace()
        base.retire_carriers=lambda folder:cc.atomic(folder/'CARRIER_RETIREMENT_RESULT.private.json',dict(complete=True,primary_objects_and_all_B_epochs_preserved=True))
        base.metadata=lambda:dict(self.committed,batches=base.committed,completed_batches=1,completed_files=2,resolved_files=2)
        base.w=SimpleNamespace(save=cc.atomic,progress=lambda *a:None)
        prep=dict(old_process={'pid':999999999,'start_ticks':0,'boot_id':'none'},sources=[],terminal_failure_sha256=digest)
        real_exists=Path.exists
        with patch.object(Path,'exists',lambda p:True if p==self.root.parents[1]/'production-owner.lock' else real_exists(p)),             patch.object(recovery,'locked',side_effect=lambda *a,**k:cc.locked(self.root/'owner.lock',**k)),             patch.object(recovery,'load_legacy',return_value=base):
            proof=recovery.reconcile(self.root,control,prep)
        self.assertTrue(proof['verified']);self.assertEqual(proof['checkpoint']['next_batch'],1)
        self.assertEqual(original.stat().st_ino,os.fstat(descriptor).st_ino)
        self.assertEqual(original.stat().st_mtime_ns,before.st_mtime_ns);self.assertEqual(list(original.iterdir()),[])
        self.assertNotEqual(proof['batch_override']['path'],str(original))
        self.assertFalse(Path(proof['batch_override']['path']).exists())
        self.assertEqual(driver.sha(self.root/'FAILURE.private.json'),digest)
