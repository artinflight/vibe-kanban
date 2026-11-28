"""Actual Linux cross-filesystem publication; small disposable fixture data only."""
import os
from pathlib import Path
import tempfile
import unittest

import payloads
import test_lifecycle as lifecycle_fixtures


class CrossFilesystemTests(unittest.TestCase):
    def setUp(self):
        if not Path('/dev/shm').is_dir(): self.skipTest('Linux second filesystem required')
        self.f = lifecycle_fixtures.LifecycleTests(methodName='test_real_move_restore_preserves_history_code_empty_symlink_and_exact_input')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        second = tempfile.TemporaryDirectory(prefix='vk-cross-publication-', dir='/dev/shm')
        self.addCleanup(second.cleanup)
        self.other = Path(second.name)
        if self.other.stat().st_dev == self.f.root.stat().st_dev: self.skipTest('Distinct devices required')
        self.destination = self.other / 'history'
        self.destination.mkdir(mode=0o750)
        (self.destination / 'a').write_bytes(b'closed history\n' * 40)
        (self.destination / 'empty').touch()
        os.symlink('a', self.destination / 'link')
        self.f.roots[0] = str(self.destination)
        self.manifest = self.f.prepare()
        self.f.life.retire()
        self.f.retain()

    def test_actual_cross_device_restore_preserves_bytes_metadata_and_exact_input(self):
        self.f.life.restore()
        payloads.verify(self.manifest['payloads'])
        self.assertEqual(self.f.c.state(self.f.w)['phase'], 'active')
        journal = self.f.c.io(self.f.w)['journal']
        self.assertEqual(journal['copy_publications'], [0])
        self.assertTrue(journal['publication_verified'])
        self.assertFalse(Path(journal['publication'][0]).exists())
        self.assertEqual(self.f.c.db.execute('SELECT state FROM workspace_archive_inputs').fetchone()[0], 'ready')

    def test_crash_after_copy_intent_and_complete_root_resumes_without_overwrite(self):
        self.f.interrupt('copy_publication_intent')
        with self.assertRaises(InterruptedError): self.f.life.restore()
        self.assertFalse(self.destination.exists())
        self.f.interrupt('root_revived')
        with self.assertRaises(InterruptedError): self.f.life.restore()
        before = (self.destination / 'a').stat().st_ino
        self.f.hook = None
        self.f.life.restore()
        self.assertEqual((self.destination / 'a').stat().st_ino, before)
        payloads.verify(self.manifest['payloads'])

    def test_crash_during_copy_cleanup_resumes_from_verified_publication(self):
        self.f.interrupt('publication_verified')
        with self.assertRaises(InterruptedError): self.f.life.restore()
        journal = self.f.c.io(self.f.w)['journal']
        # Emulate the exact first completed unlink before the previous process
        # lost its receipt. The next attempt must not re-verify an incomplete
        # temporary source instead of its already verified active destination.
        staged = Path(journal['publication'][0])
        (staged / 'a').unlink()
        self.f.hook = None
        self.f.life.restore()
        self.assertEqual(self.f.c.state(self.f.w)['phase'], 'active')
        payloads.verify(self.manifest['payloads'])

    def test_foreign_member_after_copy_intent_is_preserved(self):
        self.f.interrupt('copy_publication_intent')
        with self.assertRaises(InterruptedError): self.f.life.restore()
        self.destination.mkdir(mode=0o700)
        (self.destination / 'a').write_text('newer foreign data')
        self.f.hook = None
        with self.assertRaises(ValueError): self.f.life.restore()
        self.assertEqual((self.destination / 'a').read_text(), 'newer foreign data')
        self.assertEqual(self.f.c.state(self.f.w)['phase'], 'restoring')
        self.assertEqual(self.f.c.db.execute('SELECT state FROM workspace_archive_inputs').fetchone()[0], 'waiting_restore')

    def test_target_filesystem_resource_hold_preserves_input_and_source(self):
        def refuse(*args):
            raise OSError('fixture final active filesystem reserve unavailable')
        original = self.f.authority.reserve_publication
        self.f.authority.reserve_publication = refuse
        with self.assertRaises(OSError): self.f.life.restore()
        self.assertFalse(self.destination.exists())
        self.assertEqual(self.f.c.state(self.f.w)['phase'], 'restoring')
        self.assertEqual(self.f.c.db.execute('SELECT state FROM workspace_archive_inputs').fetchone()[0], 'waiting_restore')
        self.f.authority.reserve_publication = original
        self.f.life.restore()
        payloads.verify(self.manifest['payloads'])

    def test_interrupted_file_copy_never_exposes_named_partial(self):
        self.f.interrupt('copy_publication_intent')
        with self.assertRaises(InterruptedError): self.f.life.restore()
        journal = self.f.c.io(self.f.w)['journal']
        stage = Path(journal['publication'][0])
        saw_complete_anonymous_inode = False
        def fail():
            nonlocal saw_complete_anonymous_inode
            for name in os.listdir('/proc/self/fd'):
                try:
                    st = os.fstat(int(name))
                except OSError:
                    continue
                if st.st_dev == self.other.stat().st_dev and st.st_nlink == 0 and st.st_size > 0:
                    saw_complete_anonymous_inode = True
                    raise InterruptedError('complete anonymous file before publication')
        with self.assertRaises(InterruptedError):
            payloads.publish_root(self.manifest['payloads'], 0, stage, self.destination, guard=fail)
        self.assertTrue(saw_complete_anonymous_inode)
        self.assertEqual(list(self.destination.iterdir()), [])
        self.f.hook = None
        self.f.life.restore()
        payloads.verify(self.manifest['payloads'])


if __name__ == '__main__': unittest.main()
