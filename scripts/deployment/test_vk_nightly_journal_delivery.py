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
        self.assertIn('CPUQuota=5\\%',line);self.assertIn('MemorySwapMax=0',line)
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
