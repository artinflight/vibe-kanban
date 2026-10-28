"""Opt-in disposable user-manager check; never installs the nightly job/timer."""
import configparser
import os
import subprocess
import sys
import time
import unittest
import uuid

from vk_nightly_generation import render_schedule


class UserServiceTimeout(unittest.TestCase):
    def test_only_digest_bound_hard_stop_calendar_is_rendered_with_timezone_neutral_pulse(self):
        value=render_schedule('/owned/vk_nightly_calendar.py','/owned/config.json',configuration_sha256='a'*64)
        settings=configparser.ConfigParser(interpolation=None);settings.read_string(value['service'])
        service=settings['Service']
        self.assertEqual(service['TimeoutStartSec'],'25200')
        self.assertEqual(service['TimeoutStopSec'],'5')
        self.assertIn('--config-sha256 '+'a'*64,service['ExecStart'])
        settings=configparser.ConfigParser(interpolation=None);settings.read_string(value['timer'])
        self.assertEqual(settings['Timer']['OnCalendar'],'*-*-* *:0/15:00 UTC')
        self.assertFalse(value['enabled'])
        for job,sha in [('/owned/job.py','a'*64),('/owned/vk_nightly_supervisor.py','a'*64),
                        ('/owned/vk_nightly_calendar.py','truncated')]:
            with self.assertRaises(ValueError):render_schedule(job,'/owned/config.json',configuration_sha256=sha)

    @unittest.skipUnless(os.environ.get('VK_TEST_USER_SERVICE_TIMEOUT') == '1',
                         'disposable user-service validation is opt-in')
    def test_oneshot_timeout_and_finite_shutdown_grace(self):
        settings = configparser.ConfigParser(interpolation=None)
        settings.read_string(render_schedule('/owned/vk_nightly_calendar.py', '/owned/config.json',
                                            configuration_sha256='a'*64)['service'])
        service = settings['Service']
        self.assertEqual(service['TimeoutStartSec'], '25200')
        self.assertEqual(service['TimeoutStopSec'], '5')
        # Exercise the rendered settings with shortened deadlines, on only an
        # owned sleeper that ignores SIGTERM so shutdown escalation is observed.
        unit = 'vk-nightly-timeout-test-' + uuid.uuid4().hex + '.service'
        program = 'import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(60)'
        started = time.monotonic()
        try:
            result = subprocess.run([
                'systemd-run', '--user', '--quiet', '--wait', '--unit=' + unit,
                '--property=Type=' + service['Type'],
                '--property=NoNewPrivileges=' + service['NoNewPrivileges'],
                '--property=TimeoutStartSec=1', '--property=TimeoutStopSec=1',
                sys.executable, '-B', '-S', '-c', program,
            ], capture_output=True, text=True, timeout=15)
            elapsed = time.monotonic() - started
            properties = subprocess.run([
                'systemctl', '--user', 'show', unit, '--property=Result',
                '--property=ExecMainCode', '--property=ExecMainStatus',
                '--property=TimeoutStartUSec', '--property=TimeoutStopUSec',
                '--property=ActiveState',
            ], capture_output=True, text=True, check=True, timeout=5)
            observed = dict(line.split('=', 1) for line in properties.stdout.splitlines())
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(observed['Result'], 'timeout')
            self.assertEqual(observed['ActiveState'], 'failed')
            self.assertEqual(observed['ExecMainCode'], '2')  # CLD_KILLED
            self.assertEqual(observed['ExecMainStatus'], '9')  # SIGKILL after grace
            self.assertEqual(observed['TimeoutStartUSec'], '1s')
            self.assertEqual(observed['TimeoutStopUSec'], '1s')
            self.assertGreaterEqual(elapsed, 1.8)
            self.assertLess(elapsed, 10)
            print('Disposable oneshot: start=1s stop=1s Result=timeout '
                  'SIGKILL elapsed=%.3fs' % elapsed)
        finally:
            # Stop/reset only this unique transient fixture; no persistent files,
            # timers, production services, backup payloads or schedules touched.
            subprocess.run(['systemctl', '--user', 'stop', unit], capture_output=True, timeout=5)
            subprocess.run(['systemctl', '--user', 'reset-failed', unit], capture_output=True, timeout=5)


if __name__ == '__main__':
    unittest.main()
