import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from vk_restart_no_progress import supervise, NoProgress

class IndependentWatchdog(unittest.TestCase):
    def test_real_blocked_worker_is_terminated(self):
        with tempfile.TemporaryDirectory(dir='/dev/shm') as d:
            start=time.monotonic()
            with self.assertRaises(NoProgress):
                supervise([sys.executable,'-c','import time; time.sleep(60)'],Path(d)/'progress',idle_seconds=.15,interval=.02,grace_seconds=.1)
            self.assertLess(time.monotonic()-start,2)

    def test_real_progress_can_continue_beyond_idle_budget(self):
        with tempfile.TemporaryDirectory(dir='/dev/shm') as d:
            p=Path(d)/'progress'
            program='import json,time,pathlib; p=pathlib.Path('+repr(str(p))+');\nfor i in range(10):\n q=p.with_suffix(".next");q.write_text(json.dumps({"sequence":i}));q.replace(p);time.sleep(.04)\n'
            start=time.monotonic()
            self.assertEqual(supervise([sys.executable,'-c',program],p,idle_seconds=.2,interval=.01),0)
            self.assertGreater(time.monotonic()-start,.2)

    def test_child_failure_is_not_mistaken_for_success(self):
        import subprocess
        with tempfile.TemporaryDirectory(dir='/dev/shm') as d:
            with self.assertRaises(subprocess.CalledProcessError):
                supervise([sys.executable,'-c','raise SystemExit(7)'],Path(d)/'progress',idle_seconds=1,interval=.01)

if __name__=='__main__':unittest.main()
