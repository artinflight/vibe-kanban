import unittest
from windows_control_read import read_current

class ControlReads(unittest.TestCase):
    def exercise(self, outcomes, deadline=lambda: None):
        calls, sleeps = [], []
        def read(path):
            calls.append(path)
            value = outcomes.pop(0)
            if isinstance(value, BaseException): raise value
            return value
        return (lambda: read_current('control', read_once=read, sleep=sleeps.append,
                                      check_deadline=deadline), calls, sleeps)
    def error(self, code=None):
        error = PermissionError(13, 'control unavailable')
        if code is not None: error.winerror = code
        return error
    def test_current_bytes(self):
        run, calls, sleeps = self.exercise([b'{"OwnerPause":true}'])
        self.assertEqual(run(), b'{"OwnerPause":true}')
        self.assertEqual(len(calls), 1); self.assertEqual(sleeps, [])
    def test_sharing_conflict_reopens_current_path(self):
        run, calls, sleeps = self.exercise([self.error(32), self.error(33), b'new'])
        self.assertEqual(run(), b'new'); self.assertEqual(calls, ['control'] * 3)
        self.assertEqual(sleeps, [0.08, 0.08])
    def test_persistent_lock_fails_closed(self):
        run, calls, sleeps = self.exercise([self.error(32) for _ in range(4)])
        with self.assertRaises(PermissionError): run()
        self.assertEqual(len(calls), 4); self.assertEqual(len(sleeps), 3)
    def test_denial_and_unknown_errno_never_retry(self):
        for code in [5, None, 303]:
            with self.subTest(code=code):
                run, calls, sleeps = self.exercise([self.error(code)])
                with self.assertRaises(PermissionError): run()
                self.assertEqual(len(calls), 1); self.assertEqual(sleeps, [])
    def test_missing_file_never_becomes_absent_stop(self):
        run, calls, sleeps = self.exercise([FileNotFoundError()])
        with self.assertRaises(FileNotFoundError): run()
        self.assertEqual(len(calls), 1); self.assertEqual(sleeps, [])
    def test_changed_file_never_retries(self):
        run, calls, sleeps = self.exercise([ValueError('changed')])
        with self.assertRaises(ValueError): run()
        self.assertEqual(len(calls), 1); self.assertEqual(sleeps, [])
    def test_expired_deadline_blocks_read(self):
        def expired(): raise TimeoutError('expired')
        run, calls, sleeps = self.exercise([b'old'], deadline=expired)
        with self.assertRaises(TimeoutError): run()
        self.assertEqual(calls, []); self.assertEqual(sleeps, [])
if __name__ == '__main__': unittest.main()
