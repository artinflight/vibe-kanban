import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import incremental_watch as subject


class WatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.folder = self.root/'runs'/'abc'
        self.folder.mkdir(parents=True)
        self.config = dict(operation='abc', operation_root=str(self.folder),
            incremental_state_root=str(self.root), controller_unit='test',
            controller_pid=10, controller_invocation='birth')
        self.state = dict(operation='abc', folder=str(self.folder), started_at=100,
            phase='batch_in_progress', total_batches=1, selected_files=1,
            completed_batches=0, converted_files=0, excluded_files=0)
        self.write(self.root/'ACTIVE.private.json', self.state)
        self.write(self.folder/'SELECTION.private.json', [{'rows':[{'path':'log'}]}])
        self.service = lambda name:dict(ActiveState='active', MainPID='10', InvocationID='birth')
    def tearDown(self):
        self.tmp.cleanup()
    def write(self, path, value):
        path.write_text(json.dumps(value))
    def test_running_is_not_success(self):
        v = subject.snapshot(self.config, 110, self.service)
        self.assertEqual(v['state'], 'running')
        self.assertFalse(v['needs_attention'])
    def test_dead_or_reused_process_requires_attention(self):
        v = subject.snapshot(self.config, 110, lambda _:dict(ActiveState='active', MainPID='10', InvocationID='other'))
        self.assertEqual(v['state'], 'controller_stopped')
        self.assertTrue(v['needs_attention'])
    def test_no_progress_becomes_stalled(self):
        self.assertEqual(subject.snapshot(self.config, 701, self.service)['state'], 'stalled')
    def test_success_requires_all_committed_independent_receipts(self):
        batchdir = self.folder/'batch-0000'
        batchdir.mkdir()
        result = dict(complete=True, normal_B_original_and_graph_verified=True,
                      raw_bytes=100, allocated_release_including_objects_and_directories=90)
        target = batchdir/'RESULT.private.json'
        self.write(target, result)
        batch = dict(independent_recovery_verified=True, converted_files=1, nonbeneficial=[],
            result=dict(path=str(target), sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
        self.write(self.folder/'BATCH-0000.private.json', batch)
        self.state.update(phase='complete', completed_batches=1, converted_files=1,
                          selected_scope_resolved=True)
        (self.root/'ACTIVE.private.json').unlink()
        self.write(self.folder/'RESULT.private.json', self.state)
        self.assertEqual(subject.snapshot(self.config, 110, self.service)['state'], 'success')
        target.write_text('{}')
        with self.assertRaises(ValueError):
            subject.snapshot(self.config, 110, self.service)
    def test_success_flag_cannot_replace_missing_batches(self):
        self.state.update(phase='complete', selected_scope_resolved=True)
        self.write(self.root/'ACTIVE.private.json',self.state)
        with self.assertRaisesRegex(ValueError,'complete committed selection'):
            subject.snapshot(self.config,110,self.service)

    def test_wrong_selection_rejected(self):
        self.write(self.folder/'SELECTION.private.json', [])
        with self.assertRaises(ValueError):
            subject.snapshot(self.config, 110, self.service)
    def test_hud_keeps_historical_savings(self):
        old = self.root/'old'
        old.mkdir()
        v=dict(operation='old', completed_files=2,resolved_files=3,total_files=3,
               completed_batches=1,total_batches=1,completed_raw_bytes=100,
               canary_live_log_allocated_recovery=5,batches=[{'allocated_release':75}])
        self.write(old/'COMMITTED.private.json',v)
        self.config.update(historical_operation_root=str(old),historical_operation='old')
        row=subject.snapshot(self.config,110,self.service)
        payload=subject.cumulative_payload(self.config,{'at':110,'source':row})
        self.assertEqual(payload['reclaimed_bytes'],80)
        self.assertEqual(payload['total_files'],4)
        self.assertEqual(payload['state'],'running')
        mixed=dict(row,phase='actual_production_reader_full_EOF_verified')
        self.assertEqual(subject.cumulative_payload(self.config,{'at':110,'source':mixed})['phase'],
                         'actual_production_reader_full_eof_verified')
        self.config['historically_resolved_paths']=['log']
        row=subject.snapshot(self.config,110,self.service)
        payload=subject.cumulative_payload(self.config,{'at':110,'source':row})
        self.assertEqual(payload['total_files'],3)
        self.assertEqual(payload['resolved_files'],3)

    def test_terminal_only_snapshot_ignores_a_later_active_run(self):
        self.write(self.folder/'RESULT.private.json',self.state)
        self.write(self.root/'ACTIVE.private.json',dict(self.state,operation='later'))
        row=subject.snapshot(dict(self.config,terminal_only=True),110,self.service)
        self.assertEqual(row['operation'],'abc')


if __name__=='__main__':
    unittest.main()
