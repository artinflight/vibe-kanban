import copy
import unittest

from estimates import forecast
from progress import Measurements, validate


class EstimateTests(unittest.TestCase):
    def source(self):
        return dict(schema=1, run_id="eta-test", started_at=10, updated_at=100,
                    status="running", current_step="copy", errors=[], blockers=[], steps=[
                        dict(id="copy", label="Copy", status="running",
                             metric=dict(done=20, total=100, unit="bytes", observed_at=100, elapsed_seconds=10)),
                        dict(id="verify", label="Verify", status="pending"),
                    ])

    def test_uncertain_wait_has_conditional_range_assumptions_and_fixed_checkpoint(self):
        value = self.source()
        value.update(status="blocked")
        value["steps"][0].update(status="blocked")
        before = copy.deepcopy(value)
        first = Measurements().project(value, now=100)
        later = Measurements().project(value, now=200)
        for result in [first, later]:
            estimate = result["estimate"]
            self.assertGreater(estimate["upper_seconds"], estimate["lower_seconds"])
            self.assertEqual(estimate["confidence"], "low")
            self.assertTrue(estimate["conditional"])
            self.assertTrue(any("indefinitely" in a for a in estimate["assumptions"]))
            self.assertTrue(any("not measured" in a for a in estimate["assumptions"]))
            self.assertEqual(result["percent"], first["percent"])
        self.assertEqual(first["estimate"]["recalibration"]["due_at"], 160)
        self.assertEqual(later["estimate"]["recalibration"]["due_at"], 160)
        self.assertTrue(later["estimate"]["recalibration"]["overdue"])
        self.assertEqual(before, value)  # Forecasting cannot alter producer state.

    def test_missing_total_produces_planning_forecast_without_measured_eta(self):
        value = self.source()
        value["steps"][0]["metric"]["total"] = None
        result = Measurements().project(value, now=100)
        self.assertIsNone(result["eta_seconds"])
        self.assertIsNone(result["steps"][0]["percent"])
        self.assertEqual(result["estimate"]["basis"], "planning")
        self.assertEqual(result["estimate"]["confidence"], "low")
        self.assertEqual(result["estimate"]["lower_seconds"], 240)
        self.assertEqual(result["estimate"]["upper_seconds"], 1200)

    def test_rate_and_rehearsal_forecast_is_qualified_not_measured_total(self):
        value = self.source()
        value["steps"][1]["measured_duration_seconds"] = 10
        result = Measurements().project(value, now=100)
        estimate = result["estimate"]
        self.assertEqual(estimate["confidence"], "medium")
        self.assertEqual(estimate["basis"], "evidence-based forecast")
        self.assertEqual((estimate["lower_seconds"], estimate["upper_seconds"]), (25, 100))
        self.assertTrue(any("not a statistical interval" in a for a in estimate["assumptions"]))
        self.assertTrue(any("not current measured work" in a for a in estimate["assumptions"]))

    def test_stale_metric_with_fresh_heartbeat_retains_and_widens_forecast(self):
        value = self.source()
        value["steps"][1]["measured_duration_seconds"] = 10
        fresh = Measurements().project(value, now=100)
        value["updated_at"] = 200  # Heartbeat is not a new work observation.
        old = Measurements().project(value, now=200)
        self.assertEqual(old["estimate"]["confidence"], "low")
        self.assertTrue(old["estimate"]["stale"])
        self.assertEqual(old["estimate"]["as_of"], 100)
        self.assertGreater(old["estimate"]["upper_seconds"], fresh["estimate"]["upper_seconds"])
        self.assertEqual(old["percent"], fresh["percent"])
        self.assertIsNone(old["steps"][0]["eta_seconds"])

    def test_planning_and_approximate_totals_cannot_claim_medium_confidence(self):
        value = self.source()
        result = Measurements().project(value, now=100)
        self.assertEqual(result["estimate"]["basis"], "mixed")
        self.assertEqual(result["estimate"]["confidence"], "low")
        value["steps"][1]["measured_duration_seconds"] = 10
        value["steps"][0]["metric"]["estimated_total"] = True
        self.assertEqual(Measurements().project(value, now=100)["estimate"]["confidence"], "low")

    def test_failure_requires_review_not_assumed_automatic_continuation(self):
        value = self.source()
        value.update(status="failed", errors=[dict(message="Health check failed")])
        value["steps"][0]["status"] = "failed"
        result = Measurements().project(value, now=100)
        estimate = result["estimate"]
        self.assertEqual(result["status"], "failed")
        self.assertEqual(estimate["confidence"], "low")
        self.assertIn("if authorized", estimate["scope"])
        self.assertIn("review/recovery", estimate["recalibration"]["trigger"])
        self.assertTrue(any("required authorization" in a for a in estimate["assumptions"]))

    def test_cache_source_failure_retains_forecast_and_flags_stale(self):
        value = Measurements().project(self.source(), now=100)
        expected = value["estimate"]
        value.update(source_error="Updates unavailable", stale=True)
        result = forecast(value, now=1000)
        self.assertIsNotNone(result)
        self.assertEqual(result["confidence"], "low")
        self.assertTrue(result["stale"])
        self.assertEqual(result["as_of"], expected["as_of"])
        self.assertTrue(result["recalibration"]["overdue"])

    def test_completed_and_idle_have_unambiguous_outcomes(self):
        value = self.source()
        for step in value["steps"]:
            step["status"] = "completed"
        value.update(status="completed", current_step=None)
        result = Measurements().project(value, now=100)
        self.assertEqual(result["estimate"]["basis"], "confirmed")
        self.assertFalse(result["estimate"]["conditional"])
        self.assertIsNone(result["estimate"]["recalibration"])
        self.assertEqual(result["estimate"]["upper_seconds"], 0)
        value.update(status="idle")
        self.assertIsNone(forecast(value, now=100))

    def test_invalid_planning_input_rejected(self):
        value = self.source()
        for lo, hi, assumption in [(-1, 20, "x"), (30, 20, "x"), (1, float("nan"), "x"), (0, 0, "x"), (1, 20, "")]:
            value["steps"][0]["planning_estimate"] = dict(lower_seconds=lo, upper_seconds=hi, assumption=assumption)
            with self.assertRaises(ValueError):
                validate(value)

    def test_wait_step_can_never_turn_a_past_timing_into_a_promise(self):
        value = self.source()
        value["steps"][0].update(wait_step=True, measured_duration_seconds=10)
        value["steps"][1]["measured_duration_seconds"] = 10
        result = Measurements().project(value, now=100)
        self.assertEqual(result["estimate"]["confidence"], "low")
        self.assertTrue(any("indefinitely" in a for a in result["estimate"]["assumptions"]))


if __name__ == "__main__":
    unittest.main()
