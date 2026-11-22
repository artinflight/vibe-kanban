import copy
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from legacy import LegacySource, safe_reason
from progress import Measurements, Reporter, atomic_json, read_json, validate
from server import Monitor, handler


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR"))
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / "progress.json"
        self.reporter = Reporter(self.path, "attempt-1")
        self.reporter.start("Restart test", [dict(id="backup", label="Backup"), dict(id="verify", label="Verify")])

    def source(self, at=100, done=20, status="running"):
        value = read_json(self.path)
        value.update(started_at=0, updated_at=at, current_step="backup", status=status)
        value["steps"][0].update(status=status, metric=dict(done=done, total=100, unit="bytes", observed_at=at))
        return value

    def test_reporter_durable_identity_terminal_and_errors(self):
        self.reporter.update("backup", "running", "Copying", metric=dict(done=20, total=100, unit="bytes"))
        self.assertEqual(read_json(self.path)["steps"][0]["metric"]["done"], 20)
        with self.assertRaises(ValueError):
            Reporter(self.path, "different-run").update()
        with self.assertRaises(ValueError):
            self.reporter.start("Overwrite", [dict(id="x", label="X")])
        self.reporter.update("backup", "completed")
        self.reporter.update("verify", "failed", "Health check failed")
        self.assertEqual(read_json(self.path)["status"], "failed")
        self.assertEqual(read_json(self.path)["errors"][0]["message"], "Health check failed")
        with self.assertRaises(ValueError):
            self.reporter.update("verify", "completed")

    def test_success_requires_all_steps(self):
        self.reporter.update("backup", "completed")
        self.assertEqual(read_json(self.path)["status"], "running")
        self.reporter.update("verify", "completed")
        value = read_json(self.path)
        self.assertEqual(value["status"], "completed")
        self.assertIsNone(value["current_step"])

    def test_measured_rate_partial_eta_and_no_clock_progress(self):
        measured = Measurements()
        first = measured.project(self.source(), now=100)
        self.assertIsNone(first["eta_seconds"])
        next_value = self.source(at=110, done=40)
        result = measured.project(next_value, now=110)
        self.assertEqual(result["steps"][0]["eta_seconds"], 30)
        self.assertEqual(result["percent"], 20)
        self.assertIsNone(result["eta_seconds"])  # Unknown later verification.
        later = measured.project(next_value, now=120)
        self.assertEqual(later["percent"], result["percent"])
        self.assertEqual(later["steps"][0]["eta_seconds"], 30)
        next_value["steps"][1]["measured_duration_seconds"] = 8
        self.assertEqual(measured.project(next_value, now=120)["eta_seconds"], 38)

    def test_stale_blocked_and_counter_reset_pause_estimates(self):
        measured = Measurements()
        measured.project(self.source(), now=100)
        result = measured.project(self.source(at=110, done=40), now=141)
        self.assertTrue(result["stale"])
        self.assertIsNone(result["steps"][0]["eta_seconds"])
        result = measured.project(self.source(at=120, done=60, status="blocked"), now=120)
        self.assertIsNone(result["steps"][0]["eta_seconds"])
        result = measured.project(self.source(at=130, done=2), now=130)
        self.assertIsNone(result["steps"][0]["eta_seconds"])

    def test_unknown_totals_and_invalid_counters(self):
        value = self.source()
        value["steps"][0]["metric"]["total"] = None
        result = Measurements().project(value, now=100)
        self.assertIsNone(result["steps"][0]["percent"])
        self.assertIsNone(result["steps"][0]["eta_seconds"])
        for count in [-1, float("nan"), float("inf"), True]:
            value["steps"][0]["metric"]["done"] = count
            with self.assertRaises(ValueError):
                validate(value)

    def test_completed_is_never_inferred_from_counters(self):
        value = self.source(done=100)
        result = Measurements().project(value, now=100)
        self.assertEqual(result["status"], "running")
        self.assertLess(result["steps"][0]["percent"], 100)
        value["status"] = "completed"
        with self.assertRaises(ValueError):
            validate(value)
        value["status"] = "running"
        value["steps"][1]["status"] = "completed"
        self.assertLess(Measurements().project(value, now=100)["percent"], 100)

    def legacy(self):
        actor, backup = self.root / "actor", self.root / "backup"
        actor.mkdir(); backup.mkdir()
        atomic_json(actor / "actor-state.safe.json", dict(phase="measured-Desktop-B-restore-online-no-service-effects"))
        atomic_json(backup / "BACKUP_PROGRESS.safe.json", dict(passed=True, receipt=dict(desktop_verified=True), files=1000, databases=5, seconds=45))
        atomic_json(backup / "restore-verification/PROGRESS.safe.json", dict(counts=dict(members=100, restored_databases=5), seconds=10))
        return LegacySource(dict(actor_directory=str(actor), backup_directory=str(backup), run_id="legacy-1", started_at=1))

    def test_legacy_projects_receipts_without_private_fields_or_mutation(self):
        legacy = self.legacy()
        atomic_json(legacy.actor / "prepared-pins.safe.json", dict(secret="private-canary"))
        before = {p: p.read_bytes() for p in self.root.rglob("*.json")}
        value = Measurements().project(legacy.snapshot())
        self.assertEqual(value["completed_steps"], 1)
        self.assertEqual(value["current_step"], "restore")
        self.assertEqual(value["steps"][1]["metric"]["total"], 1006)
        self.assertIsNotNone(value["steps"][1]["eta_seconds"])
        self.assertNotIn("private-canary", json.dumps(value))
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content)

    def test_legacy_unknown_phase_rollback_and_failure_never_claim_success(self):
        legacy = self.legacy()
        for phase in ["a-new-stage", "compatible-rollback-serving-latest-data", "failed-or-safely-recovered"]:
            atomic_json(legacy.actor / "actor-state.safe.json", dict(phase=phase))
            value = legacy.snapshot()
            self.assertEqual(value["status"], "blocked")
            self.assertTrue(value["blockers"])
        atomic_json(legacy.actor / "actor-state.safe.json", dict(phase="verified-published"))
        self.assertNotEqual(legacy.snapshot()["status"], "completed")
        atomic_json(legacy.actor / "PUBLICATION_READY.safe.json", dict(published_at="now"))
        self.assertEqual(legacy.snapshot()["status"], "completed")
        atomic_json(legacy.actor / "failure.safe.json", dict(reason="Failed /private/history.json token=abc", failed_phase="candidate-trusted-HTTPS-acceptance"))
        value = legacy.snapshot()
        self.assertNotEqual(value["status"], "completed")
        self.assertNotIn("history.json", json.dumps(value))
        self.assertNotIn("abc", json.dumps(value))

    def test_source_failure_and_monitor_restart_preserve_last_observation(self):
        config = dict(source="file", progress_file=str(self.path), run_id="attempt-1")
        cache = self.root / "cache.json"
        monitor = Monitor(config, cache)
        monitor.poll()
        expected = monitor.response()["percent"]
        checkpoint = monitor.response()["estimate"]["recalibration"]["due_at"]
        self.path.write_text("{partial write")
        restarted = Monitor(config, cache)
        restarted.poll()
        result = restarted.response()
        self.assertEqual(result["percent"], expected)
        self.assertTrue(result["source_error"])
        self.assertTrue(result["stale"])
        self.assertIsNotNone(result["estimate"])
        self.assertEqual(result["estimate"]["confidence"], "low")
        self.assertTrue(result["estimate"]["stale"])
        self.assertEqual(result["estimate"]["recalibration"]["due_at"], checkpoint)
        wrong = Monitor(dict(config, run_id="another-attempt"), cache)
        self.assertIsNone(wrong.latest)

    def test_estimate_policy_upgrade_refreshes_cache_without_controller_write(self):
        cache = self.root / "cache.json"
        old = read_json(self.path)
        old.update(percent=0, completed_steps=0, remaining_steps=2, skipped_steps=0)
        atomic_json(cache, old)
        before = self.path.read_bytes()
        monitor = Monitor(dict(source="file", progress_file=str(self.path), run_id="attempt-1"), cache)
        monitor.poll()
        saved = read_json(cache)
        self.assertEqual(saved["estimate_policy"], 1)
        self.assertTrue(saved["estimate"]["assumptions"])
        self.assertEqual(saved["updated_at"], old["updated_at"])
        self.assertEqual(self.path.read_bytes(), before)

    def test_http_available_without_vibe_and_no_write_or_path_api(self):
        monitor = Monitor(dict(source="file", progress_file=str(self.path), run_id="attempt-1"), self.root / "cache.json")
        monitor.poll()
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler(monitor))
        self.addCleanup(server.server_close)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        base = f"http://127.0.0.1:{server.server_port}"
        for route in ["/", "/app.js", "/style.css", "/healthz", "/api/status"]:
            with urlopen(base + route) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
        for route in ["/../progress.json", "/progress.json", "/api/status?file=/etc/passwd"]:
            try:
                with urlopen(base + route) as response:
                    self.assertNotIn(b"root:", response.read())
            except HTTPError as error:
                self.assertEqual(error.code, 404)
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(base + "/api/status", data=b"restart", method="POST"))
        self.assertEqual(error.exception.code, 501)


if __name__ == "__main__":
    unittest.main()
