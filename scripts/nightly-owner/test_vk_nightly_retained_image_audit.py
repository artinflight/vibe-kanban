import errno
import fcntl
import mmap
import os
from pathlib import Path
import shutil
import signal
import tempfile
import unittest
from unittest.mock import patch

from vk_nightly_retained_image_audit import Inconclusive, scan_consumers


def process_stat(base):
    fields = (base / 'stat').read_text().rpartition(') ')[2].split()
    if len(fields) < 20:
        raise ValueError('malformed stat')
    return fields[19], fields[0], int(fields[6])


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.proc = self.root / 'proc'
        self.proc.mkdir()
        self.image = self.root / 'image'
        self.image.write_bytes(b'fixture')
        self.other = self.root / 'other'
        self.other.write_bytes(b'other')
        s = self.image.stat()
        self.key = (s.st_dev, s.st_ino)
        self.make('10', consumer=True)

    def make(self, pid, consumer=False, start='100'):
        base = self.proc / pid / 'task' / pid
        base.mkdir(parents=True)
        fields = ['S'] + ['0'] * 19
        fields[19] = start
        for p in [self.proc / pid, base]:
            (p / 'stat').write_text(pid + ' (fixture) ' + ' '.join(fields))
        (base / 'fd').mkdir()
        (base / 'maps').write_text('')
        for k in ['exe', 'cwd', 'root']:
            (base / k).symlink_to(self.other)
        if consumer:
            (base / 'fd/9').symlink_to(self.image)
        return base

    def run_scan(self, **kw):
        return scan_consumers({self.key}, process_stat=process_stat,
                              boundary=lambda: None, owner_pid=10,
                              guards={self.key}, proc=self.proc, **kw)

    def test_clean(self):
        self.assertEqual(self.run_scan()['final_live_tasks'], 1)

    def test_initial_vanished_process(self):
        original = os.listdir
        def listing(p):
            return original(p) + (['99'] if Path(p) == self.proc else [])
        with patch.object(os, 'listdir', listing):
            self.assertEqual(self.run_scan()['proven_exits'], 1)

    def test_missing_live_stat_blocks(self):
        (self.proc / '99').mkdir()
        with self.assertRaisesRegex(Inconclusive, 'live process'):
            self.run_scan()

    def test_task_exits_during_scan(self):
        base = self.make('99')
        original = Path.open
        def opening(p, *args, **kw):
            if p == base / 'maps':
                shutil.rmtree(self.proc / '99')
            return original(p, *args, **kw)
        with patch.object(Path, 'open', opening):
            self.assertEqual(self.run_scan()['proven_exits'], 1)

    def test_missing_maps_live_blocks(self):
        (self.make('99') / 'maps').unlink()
        with self.assertRaisesRegex(Inconclusive, 'incomplete live'):
            self.run_scan()

    def test_missing_live_reference_blocks(self):
        (self.make('99') / 'exe').unlink()
        with self.assertRaisesRegex(Inconclusive, 'missing live task reference'):
            self.run_scan()

    def test_denied_blocks(self):
        base = self.make('99')
        original = os.listdir
        def listing(p):
            if Path(p) == base / 'fd':
                raise PermissionError('denied')
            return original(p)
        with patch.object(os, 'listdir', listing), self.assertRaises(PermissionError):
            self.run_scan()

    def test_fd_consumer_blocks(self):
        self.make('99', consumer=True)
        with self.assertRaisesRegex(Inconclusive, 'has a consumer'):
            self.run_scan()

    def test_mapping_consumer_blocks(self):
        base = self.make('99')
        dev, ino = self.key
        (base / 'maps').write_text(f'1000-2000 r--p 0000 {os.major(dev):02x}:{os.minor(dev):02x} {ino}\n')
        with self.assertRaisesRegex(Inconclusive, 'has a consumer'):
            self.run_scan()

    def test_missing_guard_blocks(self):
        (self.proc / '10/task/10/fd/9').unlink()
        with self.assertRaisesRegex(Inconclusive, 'guard not observed'):
            self.run_scan()

    def test_new_task_must_be_inspected(self):
        self.new_task_case(False)

    def test_new_consumer_blocks(self):
        self.new_task_case(True)

    def new_task_case(self, consumer):
        original = os.listdir
        calls = 0
        def listing(p):
            nonlocal calls
            if Path(p) == self.proc:
                calls += 1
                if calls == 2:
                    self.make('99', consumer=consumer)
            return original(p)
        with patch.object(os, 'listdir', listing):
            if consumer:
                with self.assertRaisesRegex(Inconclusive, 'has a consumer'):
                    self.run_scan()
            else:
                r = self.run_scan()
                self.assertEqual((r['rounds'], r['final_live_tasks']), (2, 2))

    def test_pid_reuse_during_scan_blocks(self):
        original = process_stat
        calls = 0
        def changed(p):
            nonlocal calls
            if p == self.proc / '10/task/10':
                calls += 1
                if calls > 1:
                    return ('999', 'S', 0)
            return original(p)
        with self.assertRaisesRegex(Inconclusive, 'identity changed'):
            scan_consumers({self.key}, process_stat=changed, boundary=lambda: None,
                           owner_pid=10, guards={self.key}, proc=self.proc)

    def test_deadline_blocks(self):
        values = iter([0, 61])
        with self.assertRaisesRegex(Inconclusive, 'deadline'):
            self.run_scan(clock=lambda: next(values))

    def test_nonconvergence_blocks(self):
        original = os.listdir
        calls = 0
        def listing(p):
            nonlocal calls
            if Path(p) == self.proc:
                calls += 1
                self.make(str(100 + calls))
            return original(p)
        with patch.object(os, 'listdir', listing), self.assertRaisesRegex(Inconclusive, 'converge'):
            self.run_scan(maximum_rounds=3)

    def test_boundary_failure_blocks(self):
        def failed():
            raise RuntimeError('lease broken')
        with self.assertRaisesRegex(RuntimeError, 'lease broken'):
            scan_consumers({self.key}, process_stat=process_stat, boundary=failed,
                           owner_pid=10, guards={self.key}, proc=self.proc)


class KernelLeaseTests(unittest.TestCase):
    def test_actual_tmpfs_conflicts_and_break(self):
        fd, name = tempfile.mkstemp(prefix='nightly-lease-fixture-', dir='/dev/shm')
        os.write(fd, b'0' * 4096)
        os.close(fd)
        self.addCleanup(os.unlink, name)
        owner = os.open(name, os.O_RDONLY)
        self.addCleanup(os.close, owner)
        events = []
        old = signal.signal(signal.SIGIO, lambda *_: events.append(True))
        self.addCleanup(signal.signal, signal.SIGIO, old)
        for mode in [os.O_RDONLY, os.O_RDWR]:
            other = os.open(name, mode)
            try:
                with self.assertRaises(OSError) as error:
                    fcntl.fcntl(owner, fcntl.F_SETLEASE, fcntl.F_WRLCK)
                self.assertEqual(error.exception.errno, errno.EAGAIN)
            finally:
                os.close(other)
        other = os.open(name, os.O_RDONLY)
        mapping = mmap.mmap(other, 0, access=mmap.ACCESS_READ)
        os.close(other)
        try:
            with self.assertRaises(OSError):
                fcntl.fcntl(owner, fcntl.F_SETLEASE, fcntl.F_WRLCK)
        finally:
            mapping.close()
        # O_PATH deliberately demonstrates why the full root audit is mandatory.
        other = os.open(name, os.O_PATH)
        try:
            fcntl.fcntl(owner, fcntl.F_SETLEASE, fcntl.F_WRLCK)
            self.assertEqual(fcntl.fcntl(owner, fcntl.F_GETLEASE), fcntl.F_WRLCK)
            with self.assertRaises(OSError) as error:
                os.open(name, os.O_RDONLY | os.O_NONBLOCK)
            self.assertEqual(error.exception.errno, errno.EAGAIN)
            self.assertTrue(events)
            self.assertNotEqual(fcntl.fcntl(owner, fcntl.F_GETLEASE), fcntl.F_WRLCK)
        finally:
            fcntl.fcntl(owner, fcntl.F_SETLEASE, fcntl.F_UNLCK)
            os.close(other)


if __name__ == '__main__':
    unittest.main()
