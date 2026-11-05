"""Adapter order/refusals over real prepared modules; no live service traffic."""
from contextlib import ExitStack
import hashlib
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import vk_restart_manual_sql_reuse as reuse
import test_vk_restart_manual_update as original_tests


class AdmissionBoundary(unittest.TestCase):
    def test_missing_instruction_refuses_before_new_checkpoint_or_adapter(self):
        fixture=original_tests.Admission('test_sealed_unarmed_plan_does_not_supply_authorization');fixture.setUp()
        try:
            with patch.object(reuse,'load_checkpoint') as load,patch.object(reuse,'installed') as install:
                with self.assertRaises(PermissionError):reuse.run_after_pause(fixture.plan,{},folder=fixture.root,quiet_inventory=None,released_ownership=None)
                load.assert_not_called();install.assert_not_called()
        finally:fixture.tearDown()

    def test_unqualified_timing_refuses_before_adapter_or_native_work(self):
        plan=dict(preparation_blockers=['Measured verification does not fit admitted duration'])
        with patch.object(reuse.original_update,'admit') as admit,patch.object(reuse,'authenticate') as authenticate,patch.object(reuse,'installed') as install:
            with self.assertRaisesRegex(PermissionError,'Unresolved preparation blockers'):
                reuse.run_after_pause(plan,{'operator':'fixture'},folder=Path('/fixture'),quiet_inventory=None,released_ownership=None)
            admit.assert_called_once();authenticate.assert_called_once();install.assert_not_called()

    def test_current_source_helper_hash_and_cohort_are_required(self):
        fixture=original_tests.Admission('test_sealed_unarmed_plan_does_not_supply_authorization');fixture.setUp()
        try:
            plan=fixture.plan;plan['phases']['SQL']['maximum_delta_paths']=100000
            plan['SQL_epoch_reuse']=dict(helper_sha256={name:hashlib.sha256((Path(reuse.__file__).parent/name).read_bytes()).hexdigest() for name in reuse.HELPERS},
                new_API_epoch_claimed=False,maximum_delta_paths=100000,accepted_checkpoint=dict(path='fixture',sha256='a'*64),expected_SQL_cohort_id='b'*64)
            request=dict(cohort_id='b'*64,binding=dict(source_instance=plan['source_observer']['instance'],map_index=plan['current_map']['index_name'],map_checkpoint_sha256=plan['current_map']['checkpoint_sha256']))
            with patch.object(reuse,'load_checkpoint',return_value=dict(candidate=dict(consumer_contract=dict(current_SQL_request=request)))):
                reuse.authenticate(plan,folder=fixture.root)
                plan['SQL_epoch_reuse']['expected_SQL_cohort_id']='c'*64
                with self.assertRaises(ValueError):reuse.authenticate(plan,folder=fixture.root)
                plan['SQL_epoch_reuse']['expected_SQL_cohort_id']='b'*64
                plan['SQL_epoch_reuse']['helper_sha256']['vk_restart_sql_adoption.py']='0'*64
                with self.assertRaises(ValueError):reuse.authenticate(plan,folder=fixture.root)
        finally:fixture.tearDown()


@unittest.skipUnless(os.environ.get('STAGING_NIGHTLY_SOURCE'),'Requires exact prepared Nightly modules')
class SerialAdapter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0,os.environ['STAGING_NIGHTLY_SOURCE'])
        import vk_nightly_sql_cycle as sql
        import vk_nightly_file_cycle as files
        import vk_nightly_desktop_controls as controls
        cls.sql=sql;cls.files=files;cls.controls=controls

    def exercise(self,*,recorded=False,fail_guard=False,fail_adoption=False,tamper=False):
        order=[]
        def old(config,worker,*,report):order.append('original-SQL');return dict(original=True)
        def guard(*_):
            order.append('physical-fence-guard')
            if fail_guard:raise PermissionError('actual fence refused')
        def source(*_,**__):order.append('source');return 'source-fixture'
        class Remote:
            client='native-client-fixture'
            def __enter__(self):order.append('native-control');return self
            def __exit__(self,*_):order.append('native-close')
        def adopt(*args,**kwargs):
            self.assertEqual(args[:2],('native-client-fixture',{'fixture':True}))
            order.append('reuse')
            if fail_adoption:raise RuntimeError('changed source')
            return dict(adopted_SQL_points=2)
        config=dict(source_observer='exact-source')
        if recorded:config['recorded_SQL_scope_from']={'exact':'predecessor'}
        with ExitStack() as stack:
            stack.enter_context(patch.object(self.sql,'run',old));stack.enter_context(patch.object(self.sql,'host_guard',guard))
            stack.enter_context(patch.object(self.files,'Source',source));stack.enter_context(patch.object(self.controls,'DesktopControls',lambda *_,**__:Remote()))
            stack.enter_context(patch.object(reuse,'adopt_unchanged_SQL',adopt))
            with reuse.installed(dict(SQL_epoch_reuse={'fixture':True})):
                if tamper:self.sql.run=lambda *_:None
                else:
                    value=self.sql.run(config,dict(B_controls={}),report=lambda _:None)
                    self.assertTrue(value['original'])
                    if not recorded:self.assertEqual(value['unchanged_API_epoch_reuse']['adopted_SQL_points'],2)
            self.assertIs(self.sql.run,old)
        return order

    def test_actual_module_guard_and_reuse_precede_original_SQL_selector(self):
        self.assertEqual(self.exercise(),['physical-fence-guard','source','native-control','reuse','native-close','original-SQL'])

    def test_recorded_SQL_closure_keeps_fixed_scope_without_new_suffix(self):
        self.assertEqual(self.exercise(recorded=True),['original-SQL'])

    def test_guard_failure_precedes_source_or_native_calls(self):
        before=self.sql.run
        with self.assertRaises(PermissionError):self.exercise(fail_guard=True)
        self.assertIs(self.sql.run,before)

    def test_source_failure_restores_module_and_does_not_run_original_SQL(self):
        before=self.sql.run
        with self.assertRaises(RuntimeError):self.exercise(fail_adoption=True)
        self.assertIs(self.sql.run,before)

    def test_concurrent_module_replacement_forbids_acceptance_and_restores(self):
        before=self.sql.run
        with self.assertRaisesRegex(ValueError,'Concurrent'):self.exercise(tamper=True)
        self.assertIs(self.sql.run,before)


if __name__=='__main__':unittest.main()
