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


if __name__=='__main__':unittest.main()
