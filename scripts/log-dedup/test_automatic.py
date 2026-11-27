import json
from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from zoneinfo import ZoneInfo
import automatic as subject
from incremental import save


class AutomaticTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.config=dict(state_root=str(self.root),initial_operation='first',controller_unit='unit')
        self.noop=lambda *_:None
        self.now=lambda:datetime(2026,11,24,5,tzinfo=ZoneInfo('America/Toronto')).timestamp()
    def tearDown(self):self.tmp.cleanup()
    def run_once(self,invoke):
        return subject.execute(self.config,invoke,now=self.now,initial_check=self.noop,summarize=self.summary)
    def summary(self,config):
        value=dict(converted_files=2);save(self.root/'ROLLUP.private.json',value);return value
    def test_uncertain_run_latches_and_never_replays(self):
        calls=[]
        def invoke():calls.append(1);return 1
        with self.assertRaises(RuntimeError):self.run_once(invoke)
        with self.assertRaisesRegex(ValueError,'no replay'):self.run_once(invoke)
        self.assertEqual(len(calls),1)
    def test_existing_active_is_not_overwritten(self):
        save(self.root/'ACTIVE.private.json',{'operation':'owned'})
        with self.assertRaisesRegex(ValueError,'custody'):self.run_once(lambda:self.fail('must not invoke'))
        self.assertEqual(json.loads((self.root/'ACTIVE.private.json').read_text())['operation'],'owned')
    def test_idle_is_success_without_fabricated_conversion(self):
        def invoke():save(self.root/'LATEST.private.json',dict(phase='idle',selected_scope_resolved=True));return 0
        result=self.run_once(invoke);self.assertEqual(result['phase'],'idle')
        self.assertFalse((self.root/'AUTOMATIC_HOLD.private.json').exists())
    def test_partial_selection_holds_even_after_exit_zero(self):
        def invoke():save(self.root/'LATEST.private.json',dict(phase='complete',selected_scope_resolved=False));return 0
        with self.assertRaises(ValueError):self.run_once(invoke)
        self.assertTrue((self.root/'AUTOMATIC_HOLD.private.json').exists())
    def test_persistent_late_start_does_not_enter_nightly_window(self):
        self.now=lambda:datetime(2026,11,24,22,tzinfo=ZoneInfo('America/Toronto')).timestamp()
        result=self.run_once(lambda:self.fail('must not invoke'))
        self.assertEqual(result['phase'],'waiting_for_daytime_window')
    def test_daytime_window_handles_daylight_savings(self):
        for month in (1,7):
            for hour,allowed in [(4,False),(5,True),(16,True),(17,False),(22,False)]:
                now=datetime(2026,month,12,hour,tzinfo=ZoneInfo('America/Toronto')).timestamp()
                self.assertEqual(subject.allowed_window(now),allowed)


class RunProofTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.folder=self.root/'runs'/('a'*32);self.folder.mkdir(parents=True)
        save(self.folder/'INVENTORY.private.json',dict(files=[]))
        save(self.folder/'SELECTION.private.json',[dict(rows=[dict(path='same')])])
        save(self.folder/'BATCH-0000.private.json',dict(converted_files=0,nonbeneficial=['same'],independent_recovery_verified=True))
        self.state=dict(operation=self.folder.name,folder=str(self.folder),phase='complete',total_batches=1,
            selected_files=1,completed_batches=1,converted_files=0,excluded_files=1,selected_scope_resolved=True)
        save(self.folder/'RESULT.private.json',self.state)
        names=['INVENTORY.private.json','SELECTION.private.json','BATCH-0000.private.json']
        self.receipt=dict(actual_independent_normal_restore=dict(independent_owner_controls_restore_verified=True),
            checkpoint=dict(manifest=dict(files=[dict(source=str(self.folder/n),member=dict(sha256=subject.digest(self.folder/n))) for n in names])))
        save(self.folder/'RUN_INDEX_0000.private.json',self.receipt)
    def tearDown(self):self.tmp.cleanup()
    def test_complete_run_requires_every_control_in_independent_restore(self):
        self.assertEqual(subject.verify_run(self.folder)['resolved_paths'],['same'])
        self.receipt['checkpoint']['manifest']['files'].pop()
        save(self.folder/'RUN_INDEX_0000.private.json',self.receipt)
        with self.assertRaisesRegex(ValueError,'every control'):subject.verify_run(self.folder)
    def test_changed_batch_cannot_reuse_old_restore_proof(self):
        batch=json.loads((self.folder/'BATCH-0000.private.json').read_text());batch['extra']='changed'
        save(self.folder/'BATCH-0000.private.json',batch)
        with self.assertRaisesRegex(ValueError,'source binding'):subject.verify_run(self.folder)
    def test_old_resolved_exclusion_is_not_counted_twice(self):
        result=subject.rollup(dict(state_root=str(self.root),historically_resolved_paths=['same']))
        self.assertEqual(result['resolved_files'],0);self.assertEqual(result['converted_files'],0)
        self.assertEqual(len(result['runs']),1)


if __name__=='__main__':unittest.main()
