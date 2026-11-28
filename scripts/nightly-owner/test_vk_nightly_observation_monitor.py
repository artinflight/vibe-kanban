import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import vk_nightly_observation_monitor as m


class MonitorTests(unittest.TestCase):
    def test_change_and_heartbeat(self):
        a = {'release': 'a'}
        self.assertEqual(m.event_kind(None, a, 0, 0), 'initial')
        self.assertIsNone(m.event_kind(a, a, 300, 0))
        self.assertEqual(m.event_kind(a, {'release': 'b'}, 300, 0), 'change')
        self.assertEqual(m.event_kind(a, a, 3600, 0), 'heartbeat')

    def test_rotation_bounded_and_parseable(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            for i in range(50):
                m.append_event(p, dict(sequence=i, value='x' * 20), maximum=150)
            logs = list(p.glob('*.jsonl'))
            self.assertEqual(len(logs), 2)
            self.assertLessEqual(sum(x.stat().st_size for x in logs), 300)
            for log in logs:
                for line in log.read_text().splitlines():
                    json.loads(line)

    def test_log_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp); target = p / 'preserved'; target.write_text('original')
            (p / 'events.jsonl').symlink_to(target)
            with self.assertRaises(ValueError):
                m.append_event(p, {'event': 'test'})
            self.assertEqual(target.read_text(), 'original')

    def test_expired_run_does_not_observe_or_write(self):
        with patch('sys.argv', ['monitor', '--directory', '/mnt/vk-storage/unused',
                               '--until', '2000-01-01T00:00:00+00:00',
                               '--observer-unit-sha256', '0' * 64]), patch.object(m, 'snapshot') as observe:
            self.assertEqual(m.main(), 0)
            observe.assert_not_called()

    def test_new_unit_does_not_read_old_health(self):
        with patch.object(m, 'bounded_read', return_value=b'changed unit') as read:
            r = m.snapshot('0' * 64)
            self.assertFalse(r['observer_health']['status_binding_current'])
            self.assertEqual(read.call_count, 1)

    def test_unmounted_storage_rejected(self):
        with patch.object(m.os.path, 'ismount', return_value=False):
            self.assertFalse(m.storage_ready(Path('/mnt/vk-storage/missing')))


if __name__ == '__main__':
    unittest.main()
