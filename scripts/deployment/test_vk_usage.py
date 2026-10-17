"""Measured calls and unchanged acceptance for the existing runner, no model calls."""
import os
from pathlib import Path
import tempfile
import unittest

from benchmark_vk_usage import benchmark


class UsageTests(unittest.TestCase):
    def test_same_acceptance_fresh_checks_and_changed_input(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as root:
            result = benchmark(Path(root))
        before = result["modes"]["always_rerun"]
        after = result["modes"]["fingerprinted_reuse"]
        self.assertEqual(before["step_launches"], 9)
        self.assertEqual(after["step_launches"], 7)
        self.assertEqual(before["fresh_checks"], 3)
        self.assertEqual(after["fresh_checks"], 3)
        self.assertEqual(after["requests"][1]["reused"], ["validate", "build"])
        self.assertEqual(after["requests"][2]["reused"], [])
        self.assertFalse(result["native_model_savings_proved"])


if __name__ == "__main__":
    unittest.main()
