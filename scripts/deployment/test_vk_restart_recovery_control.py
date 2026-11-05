import unittest
from vk_restart_recovery_control import records,MAX_RECORD_BYTES,MAX_TOTAL_BYTES

class RecoveryControl(unittest.TestCase):
    def test_exact_bytes_and_stable_names_are_bound(self):
        rows=records({'packet.json':b'{}','source.py':b'pass\n'})
        self.assertEqual([r[0] for r in rows],['packet.json','source.py'])
        self.assertEqual(rows[1][2],b'pass\n');self.assertEqual(len(rows[1][1]),64)
    def test_paths_and_nonbytes_are_not_exportable_records(self):
        for value in [{'..':b'x'},{'../secret':b'x'},{'/absolute':b'x'},{'credential field':'not bytes'},{}]:
            with self.assertRaises(ValueError):records(value)
    def test_record_count_and_working_bytes_are_bounded(self):
        with self.assertRaises(ValueError):records({str(n):b'x' for n in range(129)})
        with self.assertRaises(ValueError):records({'too-large':b'x'*(MAX_RECORD_BYTES+1)})
        with self.assertRaises(ValueError):records({str(n):b'x'*MAX_RECORD_BYTES for n in range(5)})
