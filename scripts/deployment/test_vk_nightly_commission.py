"""Pure calendar/adoption decisions; no live scheduler or Desktop work."""
import copy
from datetime import datetime,timezone
import unittest

from vk_nightly_commission import enabled_configuration,next_launch,adopt_completed_night


class CommissionTests(unittest.TestCase):
    def test_enabling_preserves_exact_service_sources_resources_and_template(self):
        disabled=dict(schedule=dict(enabled=False,timezone='America/Toronto',hour=22,minute=0,
            poll_minutes=15,retry_minutes=30,max_attempts_per_day=16,window_end_hour=4,hard_stop=True),
            adoption_authorized=False,retention_adopted=False,current_service={'sha256':'a'*64},
            source_sha256={'pinned':'b'*64},worker_resource_limits={'memory_max_bytes':8*1024**3})
        original=copy.deepcopy(disabled);enabled=enabled_configuration(disabled)
        self.assertEqual(disabled,original);self.assertTrue(enabled['schedule']['enabled'])
        self.assertTrue(enabled['adoption_authorized']);self.assertTrue(enabled['retention_adopted'])
        self.assertEqual(enabled['current_service'],disabled['current_service'])
        self.assertEqual(enabled['worker_resource_limits'],disabled['worker_resource_limits'])
        for key in ['adoption_authorized','retention_adopted']:
            with self.assertRaises(ValueError):enabled_configuration(dict(disabled,**{key:True}))
        with self.assertRaises(ValueError):enabled_configuration(enabled)

    def test_actual_adopted_night_prevents_first_cron_duplicate_and_survives_retry(self):
        import tempfile
        from pathlib import Path
        from vk_nightly_calendar import checkpoint,load,tick
        evidence=dict(actual_ordinary_incremental_and_normal_restore_verified=True,
            scheduled_night='2026-10-27',completed_UTC='2026-10-28T05:00:00+00:00',
            accepted_cycle_id='a'*64,accepted_baseline_sha256='b'*64)
        state=adopt_completed_night(None,evidence,'c'*64)
        self.assertEqual(state['attempts'],0)
        self.assertEqual(adopt_completed_night(state,evidence,'c'*64),state)
        with tempfile.TemporaryDirectory(dir='/dev/shm') as root:
            path=Path(root)/'state';checkpoint(path,state)
            self.assertEqual(load(path),state)
            def unexpected(*args):self.fail('accepted night was copied again')
            result=tick(path,'c'*64,unexpected,lambda:True,lambda _:None,
                now=lambda:datetime.fromisoformat('2026-10-28T05:15:00+00:00'),monotonic=lambda:1,boot_id='fixture')
            self.assertEqual(result['status'],'already_completed')
            answer,next_run=next_launch(datetime.fromisoformat('2026-10-28T05:15:00+00:00'),load(path),
                monotonic=2,boot_id='fixture')
            self.assertEqual(next_run.isoformat(),'2026-10-29T02:00:00+00:00')
        for wrong in [dict(state,blocked=True),dict(state,status='running'),dict(state,configuration_sha256='d'*64)]:
            with self.assertRaises(ValueError):adopt_completed_night(wrong,evidence,'c'*64)
        with self.assertRaises(ValueError):adopt_completed_night(None,dict(evidence,
            actual_ordinary_incremental_and_normal_restore_verified=False),'c'*64)
        with self.assertRaises(ValueError):adopt_completed_night(None,dict(evidence,
            completed_UTC='2026-10-28T08:00:00+00:00'),'c'*64)


    def test_next_pulse_respects_current_window_and_hard_four_end(self):
        def launch(iso,state=None):return next_launch(datetime.fromisoformat(iso),state,monotonic=10,boot_id='test')[1].isoformat()
        self.assertEqual(launch('2026-10-28T02:44:00+00:00'),'2026-10-28T02:45:00+00:00')
        self.assertEqual(launch('2026-10-28T07:59:00+00:00'),'2026-10-29T02:00:00+00:00')
        self.assertEqual(launch('2026-10-28T08:00:00+00:00'),'2026-10-29T02:00:00+00:00')
        self.assertEqual(launch('2026-11-01T08:59:00+00:00'),'2026-11-02T03:00:00+00:00')
        completed=dict(day='2026-10-27',attempts=1,status='completed')
        self.assertEqual(launch('2026-10-28T02:44:00+00:00',completed),'2026-10-29T02:00:00+00:00')
        with self.assertRaises(ValueError):launch('2026-10-28T02:44:00+00:00',dict(completed,blocked=True))


if __name__=='__main__':unittest.main()
