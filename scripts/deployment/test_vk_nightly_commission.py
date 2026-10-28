"""Pure calendar/adoption decisions; no live scheduler or Desktop work."""
import copy
from datetime import datetime,timezone
import unittest

from vk_nightly_commission import enabled_configuration,next_launch


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
