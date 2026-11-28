"""Bounded journal control decisions, actual RAM flock exclusion, no live B."""
import copy
from pathlib import Path
import tempfile
import unittest

from vk_nightly_capture_adapter import mcp_lease
from vk_nightly_journal_delivery import deliver,serial_delivery,cron_line,checked_delivery


class Source:
    def __init__(self):self.sequence=7;self.calls=0;self.fail=False
    def check(self):return dict(instance='epoch',sequence=self.sequence)
    def deliver(self):
        self.calls+=1
        if self.fail:raise PermissionError('actual denied control stays denied')
        return dict(instance='epoch',sequence=self.sequence,actual_native_B_reopen_verified=True,
                    local_acknowledged=self.sequence,local_changes_pruned=True)


class DeliveryTests(unittest.TestCase):
    def test_tracking_only_definition_cannot_claim_baseline_or_accept_changed_code(self):
        from unittest.mock import patch
        from vk_nightly_journal_delivery import load_delivery
        import hashlib
        folder=Path(__file__).parent
        value=dict(format='vk-nightly-journal-binding-v1',baseline_accepted=False,schedule_enabled=False,
            journal_resource_policy='actual-enforced-unused-cgroup-budget-v1',controller_lease='/mnt/vk-storage/fixture.lock',
            source_sha256={'vk_nightly_journal_delivery.py':hashlib.sha256((folder/'vk_nightly_journal_delivery.py').read_bytes()).hexdigest()},
            worker_config='/fixed/worker',worker_config_sha256='a'*64,source_observer={'instance':'new'})
        with patch('vk_nightly_journal_delivery.read_owned',return_value=value), \
             patch('vk_nightly_journal_delivery.source_closure',return_value={'vk_nightly_journal_delivery.py'}), \
             patch('vk_nightly_journal_delivery.configuration',return_value={'worker':'verified'})as config:
            self.assertEqual(load_delivery('/fixed/config','b'*64),(value,{'worker':'verified'},{'instance':'new'}))
            self.assertTrue(config.call_args.kwargs['authenticate_only'])
            value['baseline_accepted']=True
            with self.assertRaises(ValueError):load_delivery('/fixed/config','b'*64)
            value['baseline_accepted']=False;value['source_sha256']['vk_nightly_journal_delivery.py']='0'*64
            with self.assertRaises(ValueError):load_delivery('/fixed/config','b'*64)

    def test_metadata_guard_uses_enforced_budget_without_changing_capture_floors(self):
        from unittest.mock import patch
        from vk_nightly_journal_delivery import journal_guard
        from vk_nightly_metadata_admission import MetadataDeferred
        from vk_nightly_typed_worker import ResourceDeferred
        worker=dict(memory_floor_bytes=4*1024**3,swap_floor_bytes=1024**3,root_floor_bytes=2*1024**3)
        original=dict(worker)
        with patch('vk_nightly_journal_delivery.host_guard')as host,patch('vk_nightly_metadata_admission.check')as check:
            guard=journal_guard(worker,10,'actual-enforced-unused-cgroup-budget-v1');guard()
            check.assert_called_once_with(maximum_memory_bytes=256*1024**2,maximum_frame_bytes=4*1024**2,metadata_only=True)
            self.assertEqual(host.call_args.args[0],dict(worker,memory_floor_bytes=0,swap_floor_bytes=0))
            self.assertEqual(worker,original)
            check.side_effect=MetadataDeferred('budget exhausted')
            with self.assertRaises(ResourceDeferred):guard()
            check.side_effect=ValueError('actual cgroup OOM')
            with self.assertRaises(ValueError):guard()
        with self.assertRaises(ValueError):journal_guard(worker,10,'unknown')

    def test_only_actual_delivery_can_advance_and_unchanged_has_no_B_poll(self):
        source=Source();binding={'service':'exact'}
        first=deliver(source,binding=binding,guard=lambda:None)
        self.assertEqual(source.calls,1);self.assertFalse(first['whole_baseline_accepted'])
        saved=copy.deepcopy(first)
        result=deliver(source,binding=binding,previous=first,guard=lambda:None)
        self.assertEqual(result['phase'],'unchanged-source-no-B-query');self.assertEqual(source.calls,1)
        source.sequence+=1;source.fail=True
        with self.assertRaises(PermissionError):deliver(source,binding=binding,previous=first,guard=lambda:None)
        self.assertEqual(first,saved)
        source.fail=False
        second=deliver(source,binding=binding,previous=first,guard=lambda:None)
        self.assertEqual(second['delivery']['sequence'],8)
        source.sequence=6
        self.assertFalse(deliver(source,binding=binding,previous=second,guard=lambda:None)['B_probed'])
        with self.assertRaises(ValueError):deliver(source,binding={'service':'other'},previous=first,guard=lambda:None)

    def test_real_held_RAM_lane_and_legacy_birth_skip_without_action(self):
        with tempfile.TemporaryDirectory(dir='/dev/shm') as folder:
            paths=[Path(folder)/'controller',Path(folder)/'body'];calls=[]
            action=lambda:calls.append('delivered') or dict(phase='done')
            with mcp_lease(paths[0]):
                value=serial_delivery(paths,[],action)
                self.assertEqual(value['phase'],'existing-backup-owns-delivery')
            with mcp_lease(paths[1]):
                value=serial_delivery(paths,[],action)
                self.assertEqual(value['phase'],'existing-backup-owns-delivery')
            value=serial_delivery(paths,[{'owner_pid':1}],action,present=lambda ref:True)
            self.assertEqual(value['phase'],'existing-legacy-component-owns-delivery');self.assertEqual(calls,[])
            self.assertEqual(serial_delivery(paths,[],action)['phase'],'done');self.assertEqual(calls,['delivered'])

    def test_denial_latches_review_but_admission_defer_retains_retry(self):
        from vk_nightly_typed_worker import ResourceDeferred
        with tempfile.TemporaryDirectory(dir='/dev/shm') as folder:
            review=Path(folder)/'review';calls=[]
            def denied():calls.append('denied');raise PermissionError('access denied')
            with self.assertRaises(PermissionError):checked_delivery(denied,review,binding={'exact':True})
            self.assertTrue(review.exists())
            with self.assertRaises(ValueError):checked_delivery(denied,review,binding={'exact':True})
            self.assertEqual(calls,['denied'])
            other=Path(folder)/'deferred'
            def deferred():raise ResourceDeferred('actual capacity unavailable')
            with self.assertRaises(ResourceDeferred):checked_delivery(deferred,other,binding={})
            self.assertFalse(other.exists())


    def test_cron_is_bounded_pinned_and_has_no_backup_command(self):
        import subprocess
        line=cron_line('/fixed/journal.py','a'*64,'/fixed/worker','/fixed/service','b'*64,
            '/fixed/receipt','/fixed/legacy','c'*64,'/fixed/log')
        self.assertEqual(line.count('\n'),1)
        self.assertIn('--signal=TERM --kill-after=5 55',line)
        self.assertIn('CPUQuota=25\\%',line);self.assertIn('MemorySwapMax=0',line)
        self.assertIn('tail -c 65536 > /fixed/log',line);self.assertNotIn('>>',line)
        command=line.split(' ',5)[5].replace('\\%','%')
        self.assertEqual(subprocess.run(['/bin/sh','-n','-c',command]).returncode,0)
        with self.assertRaises(ValueError):
            cron_line('/bad;path','a'*64,'/fixed/worker','/fixed/service','b'*64,
                '/fixed/receipt','/fixed/legacy','c'*64,'/fixed/log')


    def test_false_readback_does_not_become_accepted_receipt(self):
        source=Source();source.deliver=lambda:dict(instance='epoch',sequence=7,actual_native_B_reopen_verified=False)
        with self.assertRaises(ValueError):deliver(source,binding={},guard=lambda:None)
        with self.assertRaises(TimeoutError):deliver(Source(),binding={},guard=lambda:(_ for _ in ()).throw(TimeoutError()))


if __name__=='__main__':unittest.main()
