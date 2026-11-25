from pathlib import Path
import fcntl
import tempfile
import unittest

from lease_preflight import wait_available


class LeaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'owner.lock';self.path.write_bytes(b'preserve owner record')

    def test_existing_holder_is_preserved_and_can_release_naturally(self):
        owner=self.path.open('rb');self.addCleanup(owner.close);fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
        ticks=[0];observed=[]
        def sleep(seconds):ticks[0]+=seconds;owner.close()
        proof=wait_available(self.path,guard=lambda:None,maximum_seconds=5,
                             clock=lambda:ticks[0],sleep=sleep,observe=observed.append)
        self.assertEqual(proof['observations'],1);self.assertEqual(observed[0]['state'],'existing_owner_busy')
        self.assertFalse(proof['recovery_context_opened']);self.assertEqual(self.path.read_bytes(),b'preserve owner record')
        with self.path.open('rb')as fd:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)

    def test_busy_timeout_does_not_unlock_or_delete_foreign_owner(self):
        with self.path.open('rb')as owner:
            fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):wait_available(self.path,guard=lambda:None,maximum_seconds=0)
            with self.path.open('rb')as second:
                with self.assertRaises(BlockingIOError):fcntl.flock(second,fcntl.LOCK_EX|fcntl.LOCK_NB)
        self.assertTrue(self.path.exists())

    def test_replaced_lease_refuses_without_touching_new_inode(self):
        ticks=[0]
        with self.path.open('rb')as owner:
            fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
            def sleep(seconds):
                ticks[0]+=seconds;p=self.path.with_suffix('.other');p.write_bytes(b'new owner');p.replace(self.path)
            with self.assertRaisesRegex(ValueError,'inode changed'):
                wait_available(self.path,guard=lambda:None,maximum_seconds=5,clock=lambda:ticks[0],sleep=sleep)
        self.assertEqual(self.path.read_bytes(),b'new owner')

    def test_failed_admission_does_not_attempt_recovery(self):
        def refuse():raise ValueError('admission held')
        with self.assertRaisesRegex(ValueError,'admission held'):wait_available(self.path,guard=refuse)


if __name__=='__main__':unittest.main()
