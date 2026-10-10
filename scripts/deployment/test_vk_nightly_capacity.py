"""Tiny transport tests; no SSH, production reads or scheduling."""
import io
import unittest
from unittest.mock import patch

from vk_nightly_capture_adapter import Resident


class CapacityTransport(unittest.TestCase):
    def resident(self, budget, *, initial):
        config={'job_timeout_seconds':10,'initial_job_timeout_seconds':20,
                'capture_limit_bytes':32,'initial_capture_limit_bytes':64,
                'transport':'content-delta-v1'}
        ready={'event':'capture_ready','binding':{'fixture':True},
               'baseline':None if initial else {'fixture':True},
               'capture_budget_bytes':budget}
        with patch('vk_nightly_capture_adapter.subprocess.Popen') as popen, \
                patch.object(Resident,'response',return_value=ready):
            process=popen.return_value
            process.stdin=io.BytesIO();process.stdout=io.BytesIO()
            return Resident(config)

    def test_cold_shared_budget_is_bound_below_initial_ceiling(self):
        resident=self.resident(12,initial=True)
        self.assertEqual(resident.config['capture_limit_bytes'],12)
        self.assertEqual(resident.timeout,20);resident.close()

    def test_delta_shared_budget_is_bound_below_routine_ceiling(self):
        resident=self.resident(10,initial=False)
        self.assertEqual(resident.config['capture_limit_bytes'],10)
        self.assertEqual(resident.timeout,10);resident.close()

    def test_missing_boolean_negative_or_expanded_budget_is_rejected(self):
        for budget in (None,True,-1,0,65):
            with self.subTest(budget=budget),self.assertRaises(ValueError):
                self.resident(budget,initial=True)
        with self.assertRaises(ValueError):self.resident(33,initial=False)


if __name__=='__main__':unittest.main()
