"""Toronto calendar and real tiny lock fixtures; no backup/cron installation."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from vk_nightly_calendar import (ZONE, MAX_ATTEMPTS, RETRY_SECONDS, decision,
                                finish, held, checkpoint, load, tick, scheduled)
from vk_nightly_capture_adapter import mcp_lease


def at(value):return datetime.fromisoformat(value).astimezone(timezone.utc)


class Calendar(unittest.TestCase):
    def choose(self, value, state=None, mono=0, boot='boot-a'):
        return decision(at(value),state,monotonic=mono,boot_id=boot)

    def test_winter_and_summer_are_local_two_not_fixed_utc(self):
        self.assertEqual(scheduled(at('2026-01-02T12:00:00Z').date()).hour,7)
        self.assertEqual(scheduled(at('2026-07-02T12:00:00Z').date()).hour,6)

    def test_spring_missing_two_runs_first_valid_three(self):
        self.assertEqual(self.choose('2026-03-08T06:59:00Z')[0]['status'],'not_due')
        answer,_=self.choose('2026-03-08T07:00:00Z')
        self.assertEqual(answer['status'],'due')
        self.assertEqual(at(answer['scheduled_utc']).astimezone(ZONE).hour,3)

    def test_fall_repeated_one_is_not_due_and_two_runs_once(self):
        for value in ('2026-11-01T05:30:00Z','2026-11-01T06:30:00Z'):
            self.assertEqual(self.choose(value)[0]['status'],'not_due')
        answer,state=self.choose('2026-11-01T07:00:00Z')
        self.assertEqual(answer['status'],'due')
        state=finish(state,0,at('2026-11-01T07:01:00Z'),monotonic=1,boot_id='boot-a')
        self.assertEqual(self.choose('2026-11-01T07:15:00Z',state)[0]['status'],'already_completed')

    def test_retry_limit_does_not_permanently_disable_next_day(self):
        state={'day':'2026-10-10','attempts':MAX_ATTEMPTS,'status':'resource_deferred'}
        self.assertEqual(self.choose('2026-10-10T13:00:00Z',state)[0]['status'],'retry_exhausted')
        answer,value=self.choose('2026-10-11T06:00:00Z',state)
        self.assertEqual(answer['status'],'due');self.assertEqual(value['attempts'],0)

    def test_window_expiry_and_missed_boot_do_not_queue_historical_captures(self):
        self.assertEqual(self.choose('2026-10-10T14:00:00Z')[0]['status'],'window_expired')
        answer,value=self.choose('2026-10-13T07:15:00Z',{'day':'2026-10-10','attempts':1,'status':'completed'})
        self.assertEqual(answer['status'],'due');self.assertEqual(value['day'],'2026-10-13')

    def test_forward_clock_does_not_retry_before_monotonic_cooldown(self):
        _,state=self.choose('2026-10-10T06:00:00Z')
        state=finish(state,75,at('2026-10-10T06:00:00Z'),monotonic=100,boot_id='boot-a')
        self.assertEqual(self.choose('2026-10-10T08:00:00Z',state,mono=101)[0]['status'],'retry_wait')
        self.assertEqual(self.choose('2026-10-10T08:00:00Z',state,mono=1900)[0]['status'],'due')

    def test_backward_clock_and_reboot_wait_are_bounded(self):
        _,state=self.choose('2026-10-10T07:00:00Z')
        state=finish(state,75,at('2026-10-10T07:00:00Z'),monotonic=100,boot_id='boot-a')
        answer,state=self.choose('2026-10-10T06:00:00Z',state,mono=2,boot='new-boot')
        self.assertEqual(answer['retry_in_seconds'],RETRY_SECONDS)
        self.assertEqual(self.choose('2026-10-10T06:00:00Z',state,mono=1802,boot='new-boot')[0]['status'],'due')

    def test_completed_day_is_not_replayed_after_backward_date(self):
        state={'day':'2026-10-11','attempts':1,'status':'completed'}
        self.assertEqual(self.choose('2026-10-10T07:00:00Z',state)[0]['status'],'clock_before_recorded_day')

    def test_capture_failure_requires_review_instead_of_blind_repeat(self):
        _,state=self.choose('2026-10-10T07:00:00Z')
        state=finish(state,1,at('2026-10-10T07:01:00Z'),monotonic=100,boot_id='boot-a')
        self.assertEqual(self.choose('2026-10-11T07:00:00Z',state)[0]['status'],'needs_review')

    def test_naive_clock_rejected(self):
        with self.assertRaises(ValueError):decision(datetime(2026,1,1),None,monotonic=0,boot_id='boot-a')


class CalendarFixtures(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory(dir='/mnt/vk-storage',prefix='nightly-calendar-fixture-')
        self.addCleanup(self.folder.cleanup);self.root=Path(self.folder.name)
        self.state=self.root/'state.json';self.reports=[];self.calls=0
    def run_tick(self, code=0, available=True, instant='2026-10-10T07:00:00Z', mono=0):
        def run():self.calls+=1;return code
        return tick(self.state,'a'*64,run,lambda:available,self.reports.append,
                    now=lambda:at(instant),monotonic=lambda:mono,boot_id='boot-a')

    def test_serial_duplicate_invocation_launches_only_once(self):
        self.assertEqual(self.run_tick()['status'],'completed')
        self.assertEqual(self.run_tick()['status'],'already_completed')
        self.assertEqual(self.calls,1)

    def test_active_producer_does_not_consume_attempt_or_claim_quiescence(self):
        with mcp_lease(self.root/'producer.lock'):
            def available():
                try:
                    with mcp_lease(self.root/'producer.lock'):pass
                    return True
                except BlockingIOError:return False
            result=tick(self.state,'a'*64,lambda:self.fail('overlap launched'),available,self.reports.append,
                        now=lambda:at('2026-10-10T07:00:00Z'),monotonic=lambda:0,boot_id='boot-a')
        self.assertEqual(result['status'],'active_backup_deferred')
        self.assertEqual(load(self.state)['attempts'],0)
        self.assertEqual(self.run_tick()['status'],'completed')

    def test_resource_retry_survives_reload_and_waits_thirty_minutes(self):
        self.assertEqual(self.run_tick(75)['status'],'resource_deferred')
        self.assertEqual(self.run_tick(mono=100)['status'],'retry_wait')
        self.assertEqual(self.run_tick(mono=1800)['status'],'completed')
        self.assertEqual(self.calls,2)

    def test_interrupted_checkpoint_needs_real_producer_clearance_then_owned_recovery(self):
        checkpoint(self.state,{'day':'2026-10-10','attempts':1,'status':'running','configuration_sha256':'a'*64})
        self.assertEqual(self.run_tick(available=False)['status'],'active_backup_deferred')
        self.assertEqual(self.calls,0)
        self.assertEqual(self.run_tick()['status'],'completed')
        self.assertTrue(next(r for r in self.reports if r['status']=='running')['interrupted_previous_attempt'])

    def test_changed_config_malformed_and_symlink_state_are_rejected(self):
        checkpoint(self.state,{'day':'2026-10-10','attempts':1,'status':'completed','configuration_sha256':'b'*64})
        with self.assertRaises(ValueError):self.run_tick()
        self.state.write_text('{"day":"2026-10-10","attempts":true,"status":"pending"}')
        with self.assertRaises(ValueError):load(self.state)
        self.state.unlink();self.state.symlink_to(self.root/'missing')
        with self.assertRaises(OSError):load(self.state)

    def test_launch_error_is_durable_review_status_not_automatic_retry(self):
        def failure():raise OSError('fixture launch failed')
        result=tick(self.state,'a'*64,failure,lambda:True,self.reports.append,
                    now=lambda:at('2026-10-10T07:00:00Z'),monotonic=lambda:0,boot_id='boot-a')
        self.assertEqual(result['status'],'needs_review')
        self.assertIn('fixture launch failed',result['reason'])
        self.assertEqual(self.run_tick()['status'],'needs_review')
        self.assertEqual(self.calls,0)

    def test_inherited_calendar_lease_outlives_parents_context(self):
        with held(self.root/'lease') as fd:
            process=subprocess.Popen([sys.executable,'-B','-S','-c','import time;time.sleep(30)'],pass_fds=(fd,))
        try:
            with self.assertRaises(BlockingIOError):
                with held(self.root/'lease'):pass
        finally:process.terminate();process.wait()
        with held(self.root/'lease'):pass


if __name__=='__main__':unittest.main()
