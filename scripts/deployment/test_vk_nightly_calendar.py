"""Toronto calendar and real tiny lock fixtures; no backup/cron installation."""
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from vk_nightly_calendar import (ZONE, MAX_ATTEMPTS, RETRY_SECONDS, decision,
                                finish, held, checkpoint, load, tick, scheduled, run_bounded)
from vk_nightly_capture_adapter import mcp_lease


def at(value):return datetime.fromisoformat(value).astimezone(timezone.utc)


class Calendar(unittest.TestCase):
    def choose(self, value, state=None, mono=0, boot='boot-a'):
        return decision(at(value),state,monotonic=mono,boot_id=boot)

    def test_winter_and_summer_start_at_local_22(self):
        self.assertEqual(scheduled(at('2026-01-02T12:00:00Z').date()),at('2026-01-03T03:00:00Z'))
        self.assertEqual(scheduled(at('2026-07-02T12:00:00Z').date()),at('2026-07-03T02:00:00Z'))

    def test_midnight_and_repeated_DST_hour_share_the_evening(self):
        for date in ('2026-03-08T06:59:00Z','2026-03-08T07:00:00Z',
                     '2026-11-01T05:30:00Z','2026-11-01T06:30:00Z'):
            answer,state=self.choose(date)
            self.assertEqual(answer['status'],'due')
            evening=at(date).astimezone(ZONE).date()-timedelta(days=1)
            self.assertEqual(answer['day'],evening.isoformat())
            state=finish(state,0,at(date),monotonic=1,boot_id='boot-a')
            self.assertEqual(self.choose(date,state)[0]['status'],'already_completed')

    def test_spring_and_fall_end_at_actual_local_four(self):
        for stamp,hours in [('2026-03-08T03:00:00Z',5),('2026-11-01T02:00:00Z',7),
                            ('2026-10-28T02:00:00Z',6)]:
            result,_=self.choose(stamp)
            self.assertEqual((at(result['hard_deadline_utc'])-at(result['scheduled_utc'])).total_seconds(),hours*3600)
            end=at(result['hard_deadline_utc'])
            self.assertEqual(self.choose(end.isoformat())[0]['status'],'not_due')
            self.assertEqual(end.astimezone(ZONE).hour,4)

    def test_retry_limit_releases_next_evening_without_replaying_old_nights(self):
        state={'day':'2026-10-09','attempts':MAX_ATTEMPTS,'status':'resource_deferred'}
        self.assertEqual(self.choose('2026-10-10T07:00:00Z',state)[0]['status'],'retry_exhausted')
        answer,value=self.choose('2026-10-11T02:00:00Z',state)
        self.assertEqual(answer['status'],'due');self.assertEqual(value['day'],'2026-10-10')
        self.assertEqual(value['attempts'],0)
        answer,value=self.choose('2026-10-13T07:15:00Z',state)
        self.assertEqual(value['day'],'2026-10-12')

    def test_daytime_and_exact_hard_stop_never_start_backup(self):
        for stamp in ('2026-10-10T08:00:00Z','2026-10-10T14:00:00Z','2026-10-11T01:59:59Z'):
            self.assertEqual(self.choose(stamp)[0]['status'],'not_due')
        self.assertEqual(self.choose('2026-10-11T02:00:00Z')[0]['status'],'due')

    def test_monotonic_cooldown_and_reboot_still_bounded(self):
        _,state=self.choose('2026-10-10T02:00:00Z')
        state=finish(state,75,at('2026-10-10T02:00:00Z'),monotonic=100,boot_id='boot-a')
        self.assertEqual(self.choose('2026-10-10T04:00:00Z',state,mono=101)[0]['status'],'retry_wait')
        self.assertEqual(self.choose('2026-10-10T04:00:00Z',state,mono=1900)[0]['status'],'due')
        answer,state=self.choose('2026-10-10T02:00:00Z',state,mono=2,boot='new-boot')
        self.assertEqual(answer['retry_in_seconds'],RETRY_SECONDS)
        self.assertEqual(self.choose('2026-10-10T02:00:00Z',state,mono=1802,boot='new-boot')[0]['status'],'due')

    def test_backward_day_and_failure_are_not_replayed(self):
        state={'day':'2026-10-11','attempts':1,'status':'completed'}
        self.assertEqual(self.choose('2026-10-10T07:00:00Z',state)[0]['status'],'clock_before_recorded_day')
        _,state=self.choose('2026-10-10T07:00:00Z')
        state=finish(state,1,at('2026-10-10T07:01:00Z'),monotonic=100,boot_id='boot-a')
        self.assertEqual(self.choose('2026-10-11T07:00:00Z',state)[0]['status'],'needs_review')

    def test_late_success_is_preserved_but_never_accepted(self):
        _,state=self.choose('2026-10-10T07:00:00Z')
        value=finish(state,0,at('2026-10-10T08:00:00Z'),monotonic=1,boot_id='boot-a')
        self.assertEqual(value['status'],'window_stopped');self.assertTrue(value['completed_B_work_preserved'])

    def test_naive_clock_rejected(self):
        with self.assertRaises(ValueError):decision(datetime(2026,1,1),None,monotonic=0,boot_id='boot-a')


class CalendarFixtures(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory(dir='/dev/shm',prefix='nightly-calendar-fixture-')
        self.addCleanup(self.folder.cleanup);self.root=Path(self.folder.name)
        self.state=self.root/'state.json';self.reports=[];self.calls=0
    def run_tick(self, code=0, available=True, instant='2026-10-10T07:00:00Z', mono=0):
        def run(deadline,evening):
            self.assertEqual(at(deadline).astimezone(ZONE).hour,4)
            self.calls+=1;return code
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
            result=tick(self.state,'a'*64,lambda *_:self.fail('overlap launched'),available,self.reports.append,
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
        checkpoint(self.state,{'day':'2026-10-09','attempts':1,'status':'running','configuration_sha256':'a'*64})
        self.assertEqual(self.run_tick(available=False)['status'],'active_backup_deferred')
        self.assertEqual(self.calls,0)
        self.assertEqual(self.run_tick()['status'],'completed')
        self.assertTrue(next(r for r in self.reports if r['status']=='running')['interrupted_previous_attempt'])

    def test_changed_config_malformed_and_symlink_state_are_rejected(self):
        checkpoint(self.state,{'day':'2026-10-09','attempts':1,'status':'completed','configuration_sha256':'b'*64})
        with self.assertRaises(ValueError):self.run_tick()
        self.state.write_text('{"day":"2026-10-10","attempts":true,"status":"pending"}')
        with self.assertRaises(ValueError):load(self.state)
        self.state.unlink();self.state.symlink_to(self.root/'missing')
        with self.assertRaises(OSError):load(self.state)

    def test_launch_error_is_durable_review_status_not_automatic_retry(self):
        def failure(*_):raise OSError('fixture launch failed')
        result=tick(self.state,'a'*64,failure,lambda:True,self.reports.append,
                    now=lambda:at('2026-10-10T07:00:00Z'),monotonic=lambda:0,boot_id='boot-a')
        self.assertEqual(result['status'],'needs_review')
        self.assertIn('fixture launch failed',result['reason'])
        self.assertEqual(self.run_tick()['status'],'needs_review')
        self.assertEqual(self.calls,0)

    def test_real_owned_child_is_stopped_at_deadline_without_erasing_completed_output(self):
        receipt=self.root/'completed-receipt';receipt.write_bytes(b'accepted prior component')
        code="import pathlib,time;pathlib.Path(%r).write_text('started');time.sleep(30)" % str(self.root/'started')
        foreign=subprocess.Popen([sys.executable,'-B','-S','-c','import time;time.sleep(30)'])
        try:
            deadline=(datetime.now(timezone.utc)+timedelta(seconds=.4)).isoformat()
            self.assertEqual(run_bounded([sys.executable,'-B','-S','-c',code],deadline),75)
            self.assertTrue((self.root/'started').exists())
            self.assertEqual(receipt.read_bytes(),b'accepted prior component')
            self.assertIsNone(foreign.poll())
        finally:foreign.terminate();foreign.wait(timeout=5)

    def test_expired_start_never_launches_and_backward_wall_time_cannot_extend(self):
        from unittest.mock import patch
        with patch('vk_nightly_calendar.subprocess.Popen') as spawn:
            with self.assertRaises(TimeoutError):
                run_bounded(['unused'],'2000-01-01T00:00:00+00:00')
            spawn.assert_not_called()
        first=at('2026-10-28T07:59:59+00:00');times=iter([0,0,2])
        deadline='2026-10-28T08:00:00+00:00'
        self.assertEqual(run_bounded([sys.executable,'-B','-S','-c','import time;time.sleep(30)'],deadline,
            now=lambda:first,clock=lambda:next(times)),75)

    def test_inherited_calendar_lease_outlives_parents_context(self):
        with held(self.root/'lease') as fd:
            process=subprocess.Popen([sys.executable,'-B','-S','-c','import time;time.sleep(30)'],pass_fds=(fd,))
        try:
            with self.assertRaises(BlockingIOError):
                with held(self.root/'lease'):pass
        finally:process.terminate();process.wait()
        with held(self.root/'lease'):pass


if __name__=='__main__':unittest.main()
