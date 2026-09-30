#!/usr/bin/env python3
"""Real kernel locks; only disposable child processes and SSD test files."""
import importlib.util
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('capacity_lock', Path(__file__).with_name('vk-capacity-lock.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CapacityLockTests(unittest.TestCase):
    def setUp(self):
        if not os.path.ismount('/mnt/vk-storage'):
            self.fail('Mounted SSD required')
        self.temporary = tempfile.TemporaryDirectory(prefix='vk-capacity-lock-test-', dir='/mnt/vk-storage')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.lock = self.root / 'controller.lock'
        self.lock.touch(mode=0o600)

    def test_unowned_lock_is_available_without_replacing_file(self):
        inode = self.lock.stat().st_ino
        self.assertTrue(module.check_available(self.root)['available'])
        self.assertEqual(self.lock.stat().st_ino, inode)
        self.assertEqual(self.lock.read_bytes(), b'')

    def test_frozen_owner_still_blocks_candidate_until_owner_exits(self):
        worker = subprocess.Popen([sys.executable, '-c',
            'import fcntl,sys,time; f=open(sys.argv[1],"rb"); '
            'fcntl.flock(f,fcntl.LOCK_EX); print("locked",flush=True); time.sleep(60)',
            str(self.lock)], stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(worker.stdout.readline().strip(), 'locked')
            with self.assertRaisesRegex(ValueError, 'still owned'):
                module.check_available(self.root)
            os.kill(worker.pid, signal.SIGSTOP)
            os.waitpid(worker.pid, os.WUNTRACED)
            with self.assertRaisesRegex(ValueError, 'Pausing retains'):
                module.check_available(self.root)
            os.kill(worker.pid, signal.SIGCONT)
            worker.terminate()
            worker.wait(timeout=5)
            self.assertTrue(module.check_available(self.root)['available'])
        finally:
            if worker.poll() is None:
                os.kill(worker.pid, signal.SIGCONT)
                worker.kill()
                worker.wait()
            worker.stdout.close()

    def test_missing_lock_fails_without_creating_file(self):
        self.lock.unlink()
        with self.assertRaises(FileNotFoundError):
            module.check_available(self.root)
        self.assertFalse(self.lock.exists())

    def test_symlink_lock_and_root_rejected(self):
        target = self.root / 'other'
        self.lock.rename(target)
        self.lock.symlink_to(target)
        with self.assertRaises(OSError):
            module.check_available(self.root)
        alias = self.root / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            module.check_available(alias)

    def test_directory_lock_rejected(self):
        self.lock.unlink()
        self.lock.mkdir()
        with self.assertRaisesRegex(ValueError, 'regular file'):
            module.check_available(self.root)


if __name__ == '__main__':
    unittest.main()
