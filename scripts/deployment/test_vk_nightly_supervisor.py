"""Tiny resource/actual-process checks, no real backup, Desktop job or service."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock
from unittest.mock import patch

from vk_nightly_supervisor import host_admission, MEMORY_FLOOR, SWAP_FLOOR, supervise, main, exit_code


class Supervisor(unittest.TestCase):
    def test_resource_lifetime_abort_is_retryable_but_job_failure_is_not(self):
        for status in ('resource_deferred','guard_aborted','observation_blocked'):
            self.assertEqual(exit_code({'passed':False,'status':status}),75)
        self.assertEqual(exit_code({'passed':False,'status':'job_timeout'}),1)
        self.assertEqual(exit_code({'passed':False,'status':'job_completed'}),1)
        self.assertEqual(exit_code({'passed':True,'status':'job_completed'}),0)
    def test_actual_low_swap_is_not_excused_by_available_memory(self):
        self.assertIsNotNone(host_admission({'MemAvailable': 8*1024**3, 'SwapFree': 76*1024**2}, 3))
        self.assertIsNone(host_admission({'MemAvailable': MEMORY_FLOOR, 'SwapFree': SWAP_FLOOR}, 7))

    def test_interactive_lane_is_reserved(self):
        for count in (8, True, -1, None):
            self.assertIsNotNone(host_admission({'MemAvailable': MEMORY_FLOOR, 'SwapFree': SWAP_FLOOR}, count))

    def test_failed_preflight_never_launches(self):
        launch=Mock();records=[]
        result=supervise(launch,lambda:{'reason':'host memory/swap floor'},records.append,timeout_seconds=1)
        launch.assert_not_called();self.assertFalse(result['job_started'])

    def test_entrypoint_defers_before_expensive_validation_or_capture(self):
        from contextlib import redirect_stdout
        import io
        with patch('sys.argv',['nightly','--config','/fixture/config','--config-sha256','a'*64]), \
             patch('vk_nightly_supervisor.os.getuid',return_value=1000), \
             patch('vk_nightly_supervisor.checksum',return_value='a'*64), \
             patch.object(Path,'read_text',return_value='{"adoption_authorized":true,"retention_adopted":true}'), \
             patch('vk_nightly_supervisor.observe',return_value={'reason':'floor'}), \
             patch('vk_nightly_supervisor.validate') as validation, \
             patch('vk_nightly_supervisor.subprocess.Popen') as launch,redirect_stdout(io.StringIO()):
            self.assertEqual(main(),75);validation.assert_not_called();launch.assert_not_called()

    def test_observation_failure_never_launches(self):
        launch=Mock()
        def unavailable():raise OSError('fixture unreadable')
        result=supervise(launch,unavailable,lambda value:None,timeout_seconds=1)
        launch.assert_not_called();self.assertEqual(result['status'],'observation_blocked')

    def test_two_bad_lifetime_samples_stop_only_actual_owned_process_group(self):
        with tempfile.TemporaryDirectory(dir='/mnt/vk-storage',prefix='nightly-guard-fixture-') as raw:
            marker=Path(raw)/'child.pid'
            source="import subprocess,sys,time,pathlib\np=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);pathlib.Path(sys.argv[1]).write_text(str(p.pid));time.sleep(60)"
            child=None;records=[]
            def launch():
                nonlocal child
                child=subprocess.Popen([sys.executable,'-B','-S','-c',source,str(marker)],start_new_session=True)
                until=time.monotonic()+2
                while not marker.exists() and time.monotonic()<until:time.sleep(.01)
                self.assertTrue(marker.exists());return child
            samples=iter([{'reason':None},{'reason':'floor'},{'reason':'floor'}])
            unrelated=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])
            try:
                result=supervise(launch,lambda:next(samples),records.append,timeout_seconds=3,interval=.01)
                self.assertEqual(result['status'],'guard_aborted');self.assertIsNotNone(child.poll())
                self.assertIsNone(unrelated.poll())
                grandchild=int(marker.read_text());until=time.monotonic()+2
                while time.monotonic()<until:
                    stat=Path('/proc')/str(grandchild)/'stat'
                    try:
                        if stat.read_text().split(') ',1)[1].split()[0]=='Z':break
                    except (FileNotFoundError,ProcessLookupError):break
                    time.sleep(.01)
                else:self.fail('owned producer survived group termination')
                self.assertIn('kernel leases',result['termination']['producer_quiescence'])
            finally:
                unrelated.terminate();unrelated.wait()
                if child is not None and child.poll() is None:os.killpg(child.pid,15);child.wait()

    def test_deadline_stops_actual_owned_job(self):
        process=None
        def launch():
            nonlocal process
            process=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],start_new_session=True)
            return process
        result=supervise(launch,lambda:{'reason':None},lambda value:None,timeout_seconds=.04,interval=.01)
        self.assertEqual(result['status'],'job_timeout');self.assertIsNotNone(process.poll())

    def test_one_transient_bad_sample_does_not_waive_later_failure(self):
        process=None;samples=iter([None,'floor',None,'floor','floor'])
        def launch():
            nonlocal process
            process=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],start_new_session=True)
            return process
        result=supervise(launch,lambda:{'reason':next(samples)},lambda value:None,timeout_seconds=2,interval=.01)
        self.assertEqual(result['status'],'guard_aborted');self.assertIsNotNone(process.poll())


if __name__=='__main__':unittest.main()
