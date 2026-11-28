from datetime import datetime, timezone, timedelta
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from vk_restart_cutover_host import final_deadlines, validate_final_backup, verify_references


class CutoverAdmission(unittest.TestCase):
    def test_full_data_budget_always_leaves_ten_minutes_before_owner_deadline(self):
        start=datetime(2026,10,28,21,30,tzinfo=timezone.utc)
        data,end=final_deadlines(start,start+timedelta(hours=3))
        self.assertEqual((data-start).total_seconds(),3000)
        self.assertEqual((end-data).total_seconds(),600)
        self.assertEqual((end-start).total_seconds(),3600)

    def test_exact_latest_start_fits_but_one_second_late_refuses(self):
        end=datetime(2026,10,29,0,30,tzinfo=timezone.utc)
        self.assertEqual(final_deadlines(end-timedelta(hours=1),end)[1],end)
        with self.assertRaises(ValueError):final_deadlines(end-timedelta(seconds=3599),end)

    def test_measured_budget_keeps_full_fifteen_minute_recovery_margin(self):
        start=datetime.now(timezone.utc);end=start+timedelta(seconds=5400)
        data,total=final_deadlines(start,end,data_seconds=4500,recovery_seconds=900)
        self.assertEqual((data-start).total_seconds(),4500)
        self.assertEqual((total-data).total_seconds(),900)
        self.assertEqual(total,end)
        with self.assertRaises(ValueError):
            final_deadlines(start,end-timedelta(seconds=1),data_seconds=4500,recovery_seconds=900)

    def test_unreviewed_budget_cannot_consume_recovery_margin(self):
        start=datetime.now(timezone.utc)
        for data,recovery in [(3001,599),(3600,0),(3000,0),(2700,900)]:
            with self.subTest(data=data,recovery=recovery),self.assertRaises(ValueError):
                final_deadlines(start,start+timedelta(hours=3),data_seconds=data,recovery_seconds=recovery)

    def receipt(self):
        return dict(format='vk-staging-final-update-result-v1',plan_sha256='a'*64,
            release_backup_accepted=True,accepted_current_pointer_modified=False,
            cutover_performed=False,independent_restore=dict(
                independent_composed_restore_verified=True,
                normal_leased_consumer_entrypoint_verified=True,
                actual_existing_B_backed_consumer_route_verified=True))

    def test_actual_final_restore_receipt_is_required_before_stop(self):
        value=self.receipt();self.assertIs(validate_final_backup(value,'a'*64),value)
        for change in [dict(format='preparation-component-only'),dict(plan_sha256='b'*64),
                       dict(release_backup_accepted=False),dict(accepted_current_pointer_modified=True),
                       dict(cutover_performed=True),dict(independent_restore={})]:
            with self.subTest(change=change),self.assertRaises(ValueError):
                validate_final_backup(dict(value,**change),'a'*64)

    def test_each_native_consumer_acceptance_is_independently_required(self):
        for key in self.receipt()['independent_restore']:
            value=self.receipt();value['independent_restore'][key]=False
            with self.subTest(key=key),self.assertRaises(ValueError):validate_final_backup(value,'a'*64)

    def test_old_normal_restore_is_not_new_final_backup(self):
        value=self.receipt();value['normal_restore']=value.pop('independent_restore')
        with self.assertRaises(ValueError):validate_final_backup(value,'a'*64)

    def test_changed_service_source_or_evidence_refuses(self):
        with tempfile.TemporaryDirectory(dir='/dev/shm') as folder:
            path=Path(folder)/'source.py';path.write_bytes(b'original')
            refs={'host':dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())}
            verify_references(refs);path.write_bytes(b'changed')
            with self.assertRaises(ValueError):verify_references(refs)


# Cross-interface checks use the actual prepared profile. Native B receipts and
# physical writer-fence tests remain separate; these doubles prove host wiring.
import os
import sys
import types
from unittest.mock import Mock,patch

@unittest.skipUnless(os.environ.get('STAGING_CUTOVER_MANIFEST'),'Exact prepared host manifest required')
class PreparedHostWiring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg=json.loads(Path(os.environ['STAGING_CUTOVER_MANIFEST']).read_text())
        sys.path.insert(0,cls.cfg['host_folder'])
        import host_cutover_controls,cutover_transaction
        cls.base=host_cutover_controls;cls.transaction=cutover_transaction

    def setUp(self):
        self.cfg=copy.deepcopy(self.cfg)
        import vk_restart_cutover_host as host
        self.host=host
        self.ops=host.build_ops(self.cfg,self.base,self.transaction)
        self.ops.record=Mock()

    def test_host_uses_exact_plan_budget_for_both_deadlines(self):
        self.assertEqual(self.ops.prepare()['plan_sha256'],self.cfg['plan_canonical_sha256'])
        with patch.object(self.base,'atomic_bytes'):
            self.ops.route_maintenance()
        plan=json.loads(Path(self.cfg['plan']['path']).read_text())
        if plan.get('completion_policy')=='until-verified-or-real-safety-failure-v1':
            self.assertIsNone(self.ops.total_end);self.assertIsNone(self.ops.data_end)
            self.assertIsNone(self.ops.instruction['deadline_UTC'])
            self.assertEqual(self.ops.instruction['completion_policy'],plan['completion_policy']);return
        self.assertEqual((self.ops.total_end-self.ops.data_end).total_seconds(),plan['switch_smoke_recovery_seconds'])
        self.assertEqual(self.ops.instruction['deadline_UTC'],self.ops.data_end.isoformat())
        self.assertGreater((self.ops.data_end-datetime.now(timezone.utc)).total_seconds(),plan['maximum_update_seconds']-2)

    def test_service_stop_preserves_the_plan_recovery_allowance(self):
        plan=json.loads(Path(self.cfg['plan']['path']).read_text())
        self.ops.total_end=None if plan.get('completion_policy') else datetime.now(timezone.utc)+timedelta(seconds=plan['switch_smoke_recovery_seconds']-1)
        self.ops.h=types.SimpleNamespace(ctl=Mock());self.ops.thaw_if_frozen=Mock()
        if plan.get('completion_policy'):
            self.ops.stop_incumbent();self.ops.thaw_if_frozen.assert_called_once()
            self.ops.h.ctl.assert_called_once_with('stop',self.base.UNIT)
        else:
            with self.assertRaises(ValueError):self.ops.stop_incumbent()
            self.ops.h.ctl.assert_not_called();self.ops.thaw_if_frozen.assert_not_called()

    def test_release_retains_full_RPC_receipt_for_actual_physical_fence(self):
        state=dict(version=1,epoch='real-format-fixture',revision=1,goals={},issuedIds=[])
        released=dict(owned=False,protocolVersion=1,state=state)
        rpc=Mock(side_effect=[dict(owned=True,state=state),released])
        self.ops.h=types.SimpleNamespace(ownership=rpc)
        self.assertIs(self.ops.release_ownership(),state)
        self.assertIs(self.ops.released_response,released)
        self.assertEqual(rpc.call_count,2)

    def test_live_grant_refuses_before_any_release_RPC(self):
        rpc=Mock(return_value=dict(owned=True,state=dict(goals={'other':dict(grant={'id':'live'})})))
        self.ops.h=types.SimpleNamespace(ownership=rpc)
        with self.assertRaises(ValueError):self.ops.release_ownership()
        self.assertEqual(rpc.call_count,1)

    def test_final_driver_receives_actual_quiet_boundary_and_full_release(self):
        boundary={'complete':True,'active':[]}
        released=dict(owned=False,protocolVersion=1,state={'epoch':'fixture'})
        self.ops.released_response=released;self.ops.instruction={'operator':'Seamus'}
        self.ops.verify_frozen_boundary=Mock()
        value=CutoverAdmission().receipt();value['plan_sha256']=self.cfg['plan_canonical_sha256']
        fake=Mock(return_value=value)
        # build_ops captures the public function; patch before building the subject.
        import vk_restart_manual_sql_reuse as adapter
        with patch.object(adapter,'run_after_pause',fake):
            ops=self.host.build_ops(self.cfg,self.base,self.transaction)
        ops.released_response=released;ops.instruction={'operator':'Seamus'}
        ops.verify_frozen_boundary=Mock();ops.record=Mock()
        ops.seal_final_recovery_control=Mock(return_value={'independent_native_reopen_verified':True})
        self.assertIs(ops.final_current_backup(boundary,released['state'],{}),value)
        ops.seal_final_recovery_control.assert_called_once_with(value,boundary)
        self.assertIs(fake.call_args.kwargs['released_ownership'],released)
        self.assertIs(fake.call_args.kwargs['quiet_inventory'],boundary)
        self.assertEqual(fake.call_args.kwargs['folder'],Path(json.loads(Path(self.cfg['plan']['path']).read_text())['source_folder']))

    def test_recovery_margin_refuses_before_thaw_or_stop(self):
        self.ops.total_end=datetime.now(timezone.utc)+timedelta(seconds=599)
        self.ops.thaw_if_frozen=Mock();self.ops.h=types.SimpleNamespace(ctl=Mock())
        if self.cfg.get('completion_policy'):
            self.ops.total_end=None;self.ops.stop_incumbent()
            self.ops.h.ctl.assert_called_once_with('stop',self.base.UNIT);return
        with self.assertRaises(ValueError):self.ops.stop_incumbent()
        self.ops.thaw_if_frozen.assert_not_called();self.ops.h.ctl.assert_not_called()

    def test_owned_start_hold_is_released_before_idempotent_consumer_start(self):
        import vk_restart_ingress_hold
        events=[];states={name:dict(MainPID='0',ActiveState='inactive',InvocationID='') for name in self.cfg['owned_writers']}
        def release(rows):
            self.assertEqual(rows,[{'fixture':True}]);events.append(('release','holds'))
            for name in states:states[name]=dict(MainPID='12345',ActiveState='active',InvocationID='desired-start')
        import vk_restart_writer_fence
        with patch.object(vk_restart_ingress_hold,'release',side_effect=release),patch.object(vk_restart_writer_fence,'unit_state',side_effect=lambda name:states[name]):
            ops=self.host.build_ops(self.cfg,self.base,self.transaction);ops.record=Mock()
            ops.owned_stops=list(self.cfg['owned_writers']);ops.owned_start_holds=[{'fixture':True}]
            ops.h=types.SimpleNamespace(ctl=lambda action,name:events.append((action,name)))
            ops.resume_owned_consumers(False)
        self.assertEqual(events[0],('release','holds'));self.assertEqual(ops.owned_stops,[])

    def test_companion_support_modules_precede_facade_commit(self):
        with tempfile.TemporaryDirectory(dir='/dev/shm') as folder:
            root=Path(folder);previous={};forward={};hashes={}
            for name in ['adapter.py','issue_workflow.py','steering.py']:
                target=root/name;source=root/('new-'+name);target.write_text('old');source.write_text('new')
                previous[str(target)]=dict(sha256=hashlib.sha256(target.read_bytes()).hexdigest(),mode=0o600)
                forward[str(target)]=str(source);hashes[str(target)]=hashlib.sha256(source.read_bytes()).hexdigest()
            self.cfg.update(companion_previous=previous,companion_forward=forward,companion_forward_sha256=hashes)
            calls=[]
            original=self.base.atomic_bytes
            def commit(path,raw):calls.append(path.name);original(path,raw)
            with patch.object(self.base,'atomic_bytes',side_effect=commit):self.ops.install_companion()
            self.assertEqual(calls[-1],'adapter.py');self.assertEqual(set(calls[:-1]),{'issue_workflow.py','steering.py'})
            self.assertTrue(self.ops.companion_installed)

    def test_companion_source_change_refuses_before_any_commit(self):
        self.cfg['companion_forward_sha256'][next(iter(self.cfg['companion_forward_sha256']))]='0'*64
        with patch.object(self.base,'atomic_bytes') as writes:
            with self.assertRaises(ValueError):self.ops.install_companion()
            writes.assert_not_called()

    def test_public_browser_checks_current_review_after_prepublication_preservation(self):
        with tempfile.TemporaryDirectory(dir='/dev/shm') as folder:
            output=Path(folder)/'browser.json'
            self.cfg['browser_output_candidate']=str(output)
            self.cfg['browser_smoke']=dict(path=__file__,sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
            self.ops.semantic_before={'fixture':'original'}
            self.ops.verify_semantics=Mock()
            self.ops.verify_public_review=Mock()
            def checked(*args,**kwargs):
                self.assertTrue(kwargs['check']);self.assertEqual(kwargs['timeout'],90)
                output.write_text(json.dumps(dict(passed=True,results=[dict(width=1440),dict(width=390)])))
            with patch.object(self.base.HostControls,'https_acceptance'),patch.object(self.host.subprocess,'run',side_effect=checked):
                self.ops.https_acceptance('candidate',{})
            self.ops.verify_semantics.assert_not_called()
            self.ops.verify_public_review.assert_called_once_with()

    def test_browser_failure_propagates_to_the_transaction(self):
        import subprocess
        self.cfg['browser_smoke']=dict(path=__file__,sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        self.cfg['browser_output_candidate']='/dev/shm/unused-browser-failure-receipt'
        self.ops.verify_semantics=Mock()
        with patch.object(self.base.HostControls,'https_acceptance'),patch.object(self.host.subprocess,'run',side_effect=subprocess.CalledProcessError(1,['node'])):
            with self.assertRaises(subprocess.CalledProcessError):self.ops.https_acceptance('candidate',{})
        self.ops.verify_semantics.assert_not_called()

import contextlib
import fcntl
import subprocess
import time
from vk_restart_cutover_host import wait_metadata_lane,metadata_lock_owner

class KnownMetadataAdmission(unittest.TestCase):
    def holder(self,path):
        code="import fcntl,sys;f=open(sys.argv[1],'r');fcntl.flock(f,fcntl.LOCK_EX);print('held',flush=True);sys.stdin.read(1)"
        child=subprocess.Popen([sys.executable,'-c',code,str(path)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
        self.assertEqual(child.stdout.readline().strip(),'held')
        def close():
            if child.poll() is None:child.kill()
            child.wait(timeout=3)
            child.stdin.close();child.stdout.close()
        self.addCleanup(close)
        return child

    @contextlib.contextmanager
    def original(self,path):
        with open(path,'r') as f:
            fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
            yield

    def test_actual_known_lock_waits_before_entry_without_retrying_body(self):
        with tempfile.TemporaryDirectory(dir='/dev/shm') as folder:
            path=Path(folder)/'lane';path.write_text('');path.chmod(0o600);child=self.holder(path)
            self.assertEqual(metadata_lock_owner(path),child.pid)
            expected=dict(unit='synthetic-known-owner',pid=child.pid,invocation='fixture')
            reports=[];entered=[]
            def release(_):child.stdin.write('x');child.stdin.flush();child.wait(timeout=3)
            with wait_metadata_lane(path,self.original,expected,guard=lambda:None,report=reports.append,
                inspect=lambda _:dict(MainPID=str(child.pid),InvocationID='fixture'),sleep=release):entered.append(True)
            self.assertEqual(entered,[True]);self.assertEqual(len(reports),1)

    def test_unknown_actual_lock_owner_is_preserved(self):
        with tempfile.TemporaryDirectory(dir='/dev/shm') as folder:
            path=Path(folder)/'lane';path.write_text('');child=self.holder(path)
            with self.assertRaises(ValueError):
                with wait_metadata_lane(path,self.original,dict(unit='other',pid=os.getpid(),invocation='fixture'),
                    guard=lambda:None,inspect=lambda _:dict(MainPID=str(os.getpid()),InvocationID='fixture')):
                    self.fail('Unknown lease must not be entered')
            self.assertIsNone(child.poll())
            child.stdin.write('x');child.stdin.flush();child.wait(timeout=3)

    def test_body_error_is_never_retried(self):
        with tempfile.TemporaryDirectory(dir='/dev/shm') as folder:
            path=Path(folder)/'lane';path.write_text('');calls=[]
            with self.assertRaises(BlockingIOError):
                with wait_metadata_lane(path,self.original,{},guard=lambda:None):
                    calls.append(True);raise BlockingIOError('body failure')
            self.assertEqual(calls,[True])


if __name__=='__main__':unittest.main()
