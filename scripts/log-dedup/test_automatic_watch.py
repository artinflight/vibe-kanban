import hashlib
from pathlib import Path
import tempfile
import unittest
from incremental import save
import automatic_watch as subject


class WatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.config=dict(incremental_state_root=str(self.root),historically_resolved_paths=[],
            initial_operation='a'*32,initial_controller=dict(controller_unit='initial',controller_pid=7,controller_invocation='birth'),
            automatic_controller_unit='automatic',automatic_activation_id='b'*32)
        self.service=lambda _:dict(ActiveState='inactive',MainPID='0',InvocationID='',Result='success')
    def tearDown(self):self.tmp.cleanup()
    def test_normal_daily_success_does_not_start_model_continuations(self):
        save(self.root/'ROLLUP.private.json',dict(runs=[],resolved_paths=[]))
        save(self.root/'AUTOMATIC_STATUS.private.json',dict(phase='idle',at=100,
            rollup_sha256=hashlib.sha256((self.root/'ROLLUP.private.json').read_bytes()).hexdigest()))
        row=subject.snapshot(self.config,110,self.service)
        self.assertEqual(row['state'],'idle');self.assertFalse(row['needs_attention'])
    def test_unit_preflight_failure_has_one_stable_deployment_identity(self):
        service=lambda _:dict(ActiveState='failed',MainPID='0',InvocationID='new-each-day',Result='exit-code')
        row=subject.snapshot(self.config,110,service)
        self.assertEqual(row['operation'],'b'*32);self.assertTrue(row['needs_attention'])
    def test_retained_hold_reports_original_attempt(self):
        save(self.root/'AUTOMATIC_HOLD.private.json',dict(phase='needs_review',operation='c'*32,at=100))
        row=subject.snapshot(self.config,110,self.service)
        self.assertEqual(row['operation'],'c'*32);self.assertEqual(row['state'],'failure_recovery_pending')
    def test_dead_wrapper_does_not_report_idle_success(self):
        save(self.root/'AUTOMATIC_STATUS.private.json',dict(phase='starting',operation='c'*32,at=100,started_at=100,
            controller_pid=8,controller_invocation='birth',controller_unit='automatic'))
        row=subject.snapshot(self.config,110,self.service)
        self.assertEqual(row['state'],'controller_stopped');self.assertTrue(row['needs_attention'])
    def test_rollup_race_omits_totals_instead_of_double_counting(self):
        row=subject.snapshot(self.config,110,self.service)
        save(self.root/'ROLLUP.private.json',dict(runs=[],resolved_paths=[]))
        self.assertEqual(subject.payload(self.config,dict(at=110,source=row))['state'],'unavailable')

    def test_foreign_active_folder_is_rejected(self):
        save(self.root/'ACTIVE.private.json',dict(operation='d'*32,folder='/somewhere'))
        with self.assertRaises(ValueError):subject.snapshot(self.config,110,self.service)

    def test_initial_success_remains_fresh_during_new_automatic_run(self):
        folder=self.root/'runs'/self.config['initial_operation'];folder.mkdir(parents=True)
        save(folder/'RESULT.private.json',{})
        observations=[]
        def reader(config,now):
            self.assertTrue(config['terminal_only'])
            self.assertEqual(config['attempt_label'],'catchup-r2')
            return dict(operation=config['operation'],state='success')
        def observe(store,registry,row,now,activated):
            observations.append(row['operation']);return row
        current=dict(operation='d'*32,state='running')
        self.assertEqual(subject.observe_with_initial(self.config,observe,None,None,current,110,0,reader),current)
        self.assertEqual(observations,['a'*32,'d'*32])
    def test_same_finite_operation_is_not_observed_twice(self):
        observations=[];current=dict(operation='a'*32,state='running')
        def observe(*args):observations.append(args[2]);return args[2]
        subject.observe_with_initial(self.config,observe,None,None,current,110,0)
        self.assertEqual(observations,[current])
    def test_public_page_and_hud_use_the_same_cumulative_counts(self):
        values=dict(version=1,observed=110,state='idle',completed_files=3600,
                    resolved_files=3700,total_files=3700,reclaimed_bytes=1024**3)
        page=subject.public_html(values,{})
        self.assertIn('3700 / 3700',page);self.assertIn('resolved_files=3700',page)
        self.assertIn('1.00 GiB',page);self.assertIn('checks',page)
        with self.assertRaises(ValueError):subject.public_html(dict(values,completed_files=4000),{})

    def test_idle_feed_remains_compatible_with_installed_rainmeter(self):
        old=self.root/'old';old.mkdir()
        save(old/'COMMITTED.private.json',dict(operation='old',completed_files=2,resolved_files=3,
             total_files=3,completed_batches=1,total_batches=1,completed_raw_bytes=100,batches=[]))
        self.config.update(historical_operation='old',historical_operation_root=str(old))
        row=subject.snapshot(self.config,110,self.service)
        values=subject.payload(self.config,dict(at=110,source=row))
        self.assertEqual(values['state'],'waiting_for_current_turn')
        self.assertEqual(values['resolved_files'],3)


if __name__=='__main__':unittest.main()
