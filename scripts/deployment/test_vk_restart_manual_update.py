"""Unarmed admission/phase ordering tests; native IO is never mocked as proof.

Optional exact-profile integration uses STAGING_MANUAL_UPDATE_PLAN and
STAGING_NIGHTLY_SOURCE. Actual native SQL and normal-reader receipts are separate.
"""
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone, timedelta
import copy
import hashlib
import importlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import vk_restart_manual_update as update


class Admission(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir='/dev/shm', prefix='vk-update-admission-')
        self.root = Path(self.temp.name)
        source = self.root/'vk_fixture.py'; source.write_text('pass\n')
        source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
        current = dict(index_name='staging-current-map-v12-20261028', checkpoint_sha256='6471650c53e0d66a22de43bacc643940b27c8b7bf6c760f09d4b13cbf31e5371')
        ref = dict(instance='44aadc4a21ed47359009272db6c11c95')
        serving = json.dumps(dict(mode='blue', port=5640, authoritativePort=5621, epoch=1))
        maintenance = json.dumps(dict(mode='maintenance', port=5640, authoritativePort=5621, epoch=2))
        pin = dict(kind='file', bytes=len(maintenance), sha256=hashlib.sha256(maintenance.encode()).hexdigest())
        self.plan = dict(format='vk-staging-manual-update-plan-v1', armed=False,
            accepted_current_pointer_mutation=False, maximum_update_seconds=2700, evidence={},
            source_sha256={'vk_fixture.py':source_sha}, current_map=current, source_observer=ref,
            phases=dict(files=dict(source_observer=ref), SQL=dict(source_observer=ref), runtime=dict(main_map=current)),
            finalize=dict(current_map=current, contract=dict(required_SQL=None, required_pins={'route':pin}, required_runtime_points={'route':pin})),
            route=dict(path='route',serving_bytes=serving,maintenance_bytes=maintenance))
        self.plan['workers'] = {role:dict(source_sha256=self.plan['source_sha256'],
            B_controls={}, desktop={}, B_index_name=current['index_name'], B_checkpoint_sha256=current['checkpoint_sha256'])
            for role in ('files','SQL','runtime')}
        self.now = datetime.now(timezone.utc)
        self.instruction = dict(operator='Seamus', pause_confirmed=True, instruction_reference='test-only',
            deadline_UTC=(self.now+timedelta(seconds=2700)).isoformat(),
            plan_sha256=update.authenticate(self.plan,folder=self.root))

    def tearDown(self): self.temp.cleanup()

    def test_sealed_unarmed_plan_does_not_supply_authorization(self):
        with self.assertRaises(PermissionError): update.admit(self.plan,{},folder=self.root)

    def test_other_owner_wrong_plan_or_absent_instruction_refuse(self):
        for change in (dict(operator='agent'),dict(pause_confirmed=False),dict(plan_sha256='0'*64),dict(instruction_reference='')):
            with self.subTest(change=change), self.assertRaises(PermissionError):
                update.admit(self.plan,dict(self.instruction,**change),folder=self.root,now=self.now)

    def test_old_or_extended_calendar_admission_refuses(self):
        for delta in (-1,2701):
            with self.subTest(delta=delta),self.assertRaises(ValueError):
                update.admit(self.plan,dict(self.instruction,deadline_UTC=(self.now+timedelta(seconds=delta)).isoformat()),folder=self.root,now=self.now)

    def test_new_fifty_minute_data_budget_keeps_ten_minute_service_recovery(self):
        plan=copy.deepcopy(self.plan)
        plan.update(maximum_update_seconds=3000,switch_smoke_recovery_seconds=600,
                    maximum_interruption_seconds=3600)
        sha=update.authenticate(plan,folder=self.root)
        instruction=dict(self.instruction,plan_sha256=sha,
                         deadline_UTC=(self.now+timedelta(seconds=3000)).isoformat())
        self.assertEqual(update.admit(plan,instruction,folder=self.root,now=self.now)[0],sha)
        with self.assertRaises(PermissionError):
            update.admit(plan,self.instruction,folder=self.root,now=self.now)
        with self.assertRaises(ValueError):
            update.admit(plan,dict(instruction,deadline_UTC=(self.now+timedelta(seconds=3001)).isoformat()),folder=self.root,now=self.now)

    def test_measured_seventy_five_minute_data_budget_is_fresh_and_finite(self):
        plan=copy.deepcopy(self.plan)
        plan.update(maximum_update_seconds=4500,switch_smoke_recovery_seconds=900,
                    maximum_interruption_seconds=5400)
        sha=update.authenticate(plan,folder=self.root)
        instruction=dict(self.instruction,plan_sha256=sha,
                         deadline_UTC=(self.now+timedelta(seconds=4500)).isoformat())
        self.assertEqual(update.admit(plan,instruction,folder=self.root,now=self.now)[0],sha)
        with self.assertRaises(PermissionError):
            update.admit(plan,self.instruction,folder=self.root,now=self.now)
        with self.assertRaises(ValueError):
            update.admit(plan,dict(instruction,deadline_UTC=(self.now+timedelta(seconds=4501)).isoformat()),folder=self.root,now=self.now)
        for change in [dict(maximum_interruption_seconds=3600),
                       dict(maximum_update_seconds=4501,maximum_interruption_seconds=5401),
                       dict(switch_smoke_recovery_seconds=899,maximum_interruption_seconds=5399)]:
            with self.subTest(change=change),self.assertRaises(ValueError):
                update.authenticate(dict(plan,**change),folder=self.root)

    def test_data_budget_cannot_remove_or_exceed_the_total_recovery_allowance(self):
        for data,recovery,total in [(3000,900,3600),(3000,599,3600),(3001,599,3600),
                                    (3000,600,3601),(3600,0,3600),(True,600,3600)]:
            plan=copy.deepcopy(self.plan)
            plan.update(maximum_update_seconds=data,switch_smoke_recovery_seconds=recovery,
                        maximum_interruption_seconds=total)
            with self.subTest(data=data,recovery=recovery,total=total),self.assertRaises(ValueError):
                update.authenticate(plan,folder=self.root)

    def test_explicit_completion_policy_has_no_overall_deadline(self):
        plan=copy.deepcopy(self.plan)
        plan.update(completion_policy='until-verified-or-real-safety-failure-v1',
                    maximum_update_seconds=None,switch_smoke_recovery_seconds=None,
                    maximum_interruption_seconds=None)
        sha=update.authenticate(plan,folder=self.root)
        instruction=dict(self.instruction,plan_sha256=sha,deadline_UTC=None,
                         completion_policy=plan['completion_policy'])
        self.assertEqual(update.admit(plan,instruction,folder=self.root),(sha,None))
        with self.assertRaises(ValueError):
            update.admit(plan,dict(instruction,deadline_UTC=self.instruction['deadline_UTC']),folder=self.root)
        with self.assertRaises(ValueError):
            update.authenticate(dict(plan,maximum_update_seconds=4500),folder=self.root)
        with self.assertRaises(PermissionError):update.admit(plan,{},folder=self.root)

    def test_missing_producer_stale_map_or_source_refuses(self):
        changes = []
        p=copy.deepcopy(self.plan);del p['workers']['runtime'];changes.append(p)
        p=copy.deepcopy(self.plan);p['current_map']['checkpoint_sha256']='0'*64;changes.append(p)
        p=copy.deepcopy(self.plan);p['source_observer']['instance']='old-stopped-epoch';changes.append(p)
        for value in changes:
            with self.assertRaises(ValueError): update.authenticate(value,folder=self.root)

    def test_controlled_maintenance_cannot_hide_source_pin_change(self):
        for field in ('required_pins','required_runtime_points'):
            p=copy.deepcopy(self.plan);p['finalize']['contract'][field]['route']['sha256']='0'*64
            with self.assertRaises(ValueError):update.authenticate(p,folder=self.root)
        p=copy.deepcopy(self.plan);r=json.loads(p['route']['maintenance_bytes']);r['port']=5621;p['route']['maintenance_bytes']=json.dumps(r)
        with self.assertRaises(ValueError):update.authenticate(p,folder=self.root)

    def test_changed_source_or_evidence_refuses(self):
        (self.root/'vk_fixture.py').write_text('changed\n')
        with self.assertRaises(ValueError):update.authenticate(self.plan,folder=self.root)

    def test_final_files_cannot_reuse_stale_fixed_suffix(self):
        self.plan['phases']['files']['resume_qualified_input_sha256']='0'*64
        with self.assertRaises(ValueError):update.authenticate(self.plan,folder=self.root)

    def test_refuses_before_importing_or_invoking_any_live_phase(self):
        with patch.object(update,'fenced_phase_guards') as guards:
            with self.assertRaises(PermissionError):update.run(self.plan,{},folder=self.root,verify_fence=lambda:None)
            guards.assert_not_called()


@unittest.skipUnless(os.environ.get('STAGING_MANUAL_UPDATE_PLAN') and os.environ.get('STAGING_NIGHTLY_SOURCE'), 'Requires exact private unarmed profiles and prepared Nightly closure')
class ExactIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=Path(os.environ['STAGING_NIGHTLY_SOURCE']);sys.path.insert(0,str(cls.folder))
        cls.plan=json.loads(Path(os.environ['STAGING_MANUAL_UPDATE_PLAN']).read_text())

    def test_actual_all_three_worker_configs_authenticate_against_prepared_closure(self):
        from vk_nightly_typed_worker import configuration
        with tempfile.TemporaryDirectory(dir='/dev/shm') as temp:
            for role,worker in self.plan['workers'].items():
                path=Path(temp)/(role+'.json');raw=json.dumps(worker).encode();path.write_bytes(raw);path.chmod(0o600)
                configuration(path,hashlib.sha256(raw).hexdigest(),folder=self.folder,authenticate_only=True)
        update.authenticate(self.plan,folder=self.folder)

    def test_real_runtime_source_bracket_creates_pending_points_without_fake_journal(self):
        import vk_nightly_b_controls as b
        from vk_nightly_current_map import decode_member
        with tempfile.TemporaryDirectory(dir='/dev/shm') as temp:
            root=Path(temp);source=root/'fixture-route';source.write_text('synthetic maintenance bytes')
            database=sqlite3.connect(':memory:',isolation_level=None)
            class Connection:
                @property
                def in_transaction(self):return database.in_transaction
                def execute(self,*a):return database.execute(*a)
                def executemany(self,*a):return database.executemany(*a)
                def close(self):pass
            client=types.SimpleNamespace(connect=lambda *_:Connection())
            p=copy.deepcopy(self.plan);p['phases']['runtime']['runtime_paths']=[str(source)]
            p['workers']['runtime']['map_binding']['source_paths']=[str(source)]
            p['finalize']['contract']['required_runtime_points']={str(source):dict(kind='file',bytes=source.stat().st_size,sha256=hashlib.sha256(source.read_bytes()).hexdigest())}
            with patch.object(b,'seed',return_value=p['workers']['runtime']['B_checkpoint_sha256']):
                update.prepare_runtime(client,p,guard=lambda:None)
            state,raw=database.execute('select state,row from members').fetchone();point=decode_member(raw)['qualification']
            self.assertEqual(state,'file-needs-capture');self.assertFalse(point['kernel_journal_coverage_claimed']);self.assertNotIn('journal',point)
            self.assertEqual(point['row']['sha256'],hashlib.sha256(source.read_bytes()).hexdigest())
            with patch.object(b,'seed',return_value=p['workers']['runtime']['B_checkpoint_sha256']):
                with self.assertRaisesRegex(ValueError,'namespace exists'):update.prepare_runtime(client,p,guard=lambda:None)
            database.close()

    def test_serial_phase_order_normal_consumer_and_no_global_pointer(self):
        self.exercise()

    def test_recorded_sql_discovery_uses_fixed_predecessor_without_new_suffix(self):
        self.exercise(new_sql=True)

    def test_failed_file_or_sql_or_fence_never_reaches_restore_acceptance(self):
        for failure in ('files','SQL','fence'):
            with self.subTest(failure=failure):self.exercise(failure=failure)

    def exercise(self,new_sql=False,failure=None):
        import vk_nightly_current_cycle as cc
        import vk_nightly_file_cycle as fc
        import vk_nightly_sql_cycle as sc
        import vk_nightly_runtime_cycle as rc
        import vk_nightly_finalize_current as fin
        import vk_nightly_desktop_controls as dc
        import vk_nightly_desktop_objects as do
        import vk_nightly_typed_worker as tw
        import vk_nightly_remote_consumer as con
        import vk_restart_tracking_client as tracking
        order=[]
        p=copy.deepcopy(self.plan);route=Path('/dev/shm/vk-manual-route-test-'+str(os.getpid()))
        try:
            route.write_text(p['route']['maintenance_bytes']);p['route']['path']=str(route)
            worker=p['workers']['files'];health=dict(instance=p['source_observer']['instance'],owner_pid=os.getpid(),owner_start_ticks=1)
            owner=types.SimpleNamespace(check=lambda:health,config=dict(endpoint='/unused'),reference=p['source_observer'])
            class DB:
                def execute(self,sql):return types.SimpleNamespace(fetchone=lambda:(None if 'limit 1' in sql else (222+(1 if new_sql else 0),)))
                def close(self):pass
                def request(self,*a):pass
            class Remote:
                def __enter__(self):self.client=types.SimpleNamespace(connect=lambda *a,**kw:DB());return self
                def __exit__(self,*a):pass
            def phase(name,result):
                def call(*a,**kw):
                    order.append(name)
                    if name==failure:raise ValueError('fixture phase failure')
                    return copy.deepcopy(result)
                return call
            def sql(config,*a,**kw):
                name='SQL_closure' if config.get('recorded_SQL_scope_from') else 'SQL';order.append(name)
                if failure=='SQL':raise ValueError('fixture SQL failure')
                if name=='SQL_closure':self.assertEqual(config['recorded_SQL_scope_from'],p['phases']['SQL']['SQL_phase_index'])
                return dict(complete_SQL_scope_sources=222,more_pending=False,deferred_SQL={})
            def fence():
                order.append('fence')
                if failure=='fence':raise ValueError('actual owner unknown fixture')
            @contextmanager
            def installed(*_):yield
            candidate=dict(descriptor=dict(indexes=[dict(sha256='1'*64)]),expected_catalogs=dict(base=dict(sha256='2'*64),recipes=[]))
            packet=dict(candidate)
            patches=[patch.object(update,'admit',return_value=('a'*64,datetime.now(timezone.utc)+timedelta(seconds=2000))),
                patch.object(fc,'Source',return_value=owner),patch.object(fc,'run',side_effect=phase('files',dict(more_pending=False))),
                patch.object(cc,'close_deferred_files',side_effect=lambda value,*a,**kw:value),
                patch.object(sc,'run',side_effect=sql),patch.object(update,'prepare_runtime',side_effect=phase('runtime_prepare',{})),
                patch.object(rc,'capture_component',side_effect=phase('runtime',{})),
                patch.object(cc,'recorded_file_tail',side_effect=phase('tail',dict(more_pending=False))),
                patch.object(fin,'finalize',side_effect=phase('finalize',candidate)),
                patch.object(fin,'consumer_packet',side_effect=phase('packet',packet)),
                patch.object(dc,'DesktopControls',side_effect=lambda *a,**kw:Remote()),
                patch.object(do,'DesktopObjects',side_effect=lambda *a,**kw:Remote()),
                patch.object(tw,'host_guard'),patch.object(tracking,'TrackingClient'),patch.object(tracking,'installed',installed),
                patch.object(tracking,'deliver_when_ready',side_effect=phase('deliver',{})),
                patch.object(con,'run',side_effect=phase('restore',dict(independent_composed_restore_verified=True)))]
            with ExitStack() as stack:
                for item in patches:stack.enter_context(item)
                if failure:
                    with self.assertRaises(ValueError):update._run(p,{},folder=self.folder,verify_fence=fence)
                    self.assertNotIn('restore',order);self.assertNotIn('finalize',order);return
                result=update._run(p,{},folder=self.folder,verify_fence=fence)
            observed=[v for v in order if v!='fence']
            self.assertEqual(observed,['deliver','files','SQL','runtime_prepare','runtime','tail']+(['SQL_closure'] if new_sql else [])+['finalize','packet','restore'])
            self.assertFalse(result['accepted_current_pointer_modified']);self.assertFalse(result['cutover_performed'])
            self.assertGreaterEqual(order.count('fence'),5)
        finally:
            if route.exists():route.unlink()


if __name__=='__main__':unittest.main()
