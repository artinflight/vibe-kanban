"""Isolated preparation regression tests; no production writes or model calls."""

import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import uuid

from vk_prepare import Preparation, default_plan, deployment_kind, read_only_queues


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"])
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        subprocess.run(["git", "init", "-q", str(self.source)], check=True)
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Preparation fixture")
        (self.source / "source.txt").write_text("first")
        self.commit()
        self.cache = self.root / "cache"
        self.artifact = self.root / "server"
        self.counter = self.root / "calls"
        code = ("from pathlib import Path; p=Path(" + repr(str(self.counter)) + "); "
                "p.write_text(str(int(p.read_text())+1) if p.exists() else '1'); "
                "Path(" + repr(str(self.artifact)) + ").write_text('verified artifact')")
        self.plan = {"environment": {}, "steps": [{"id": "build", "command": [sys.executable, "-c", code],
                      "outputs": [str(self.artifact)], "tools": [[sys.executable, "--version"]], "cacheable": True}]}

    def tearDown(self):
        self.temporary.cleanup()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.source), *args])

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")

    def run_plan(self, plan=None):
        return Preparation(self.source, self.cache, plan or self.plan).run()

    def test_second_run_reuses_verified_artifact(self):
        self.assertFalse(self.run_plan()["steps"]["build"]["reused"])
        self.assertTrue(self.run_plan()["steps"]["build"]["reused"])
        self.assertEqual(self.counter.read_text(), "1")

    def test_identical_tree_new_commit_reuses_evidence(self):
        self.run_plan()
        self.git("commit", "--allow-empty", "-qm", "promotion metadata")
        self.assertTrue(self.run_plan()["steps"]["build"]["reused"])

    def test_changed_source_invalidates_reuse(self):
        self.run_plan()
        (self.source / "source.txt").write_text("new behavior")
        self.commit()
        self.assertFalse(self.run_plan()["steps"]["build"]["reused"])

    def test_changed_environment_invalidates_reuse(self):
        self.run_plan()
        plan = copy.deepcopy(self.plan)
        plan["environment"]["RUSTFLAGS"] = "changed"
        self.assertFalse(self.run_plan(plan)["steps"]["build"]["reused"])

    def test_context_change_invalidates_reuse(self):
        context = self.root / "launcher"
        context.write_text("first")
        self.plan["steps"][0]["context_files"] = [str(context)]
        self.run_plan()
        context.write_text("new runtime")
        self.assertFalse(self.run_plan()["steps"]["build"]["reused"])

    def test_new_ignored_configuration_invalidates_reuse(self):
        context = self.root / "previously-absent-config"
        self.plan["steps"][0]["context_files"] = [str(context)]
        self.run_plan()
        context.write_text("new configuration")
        self.assertFalse(self.run_plan()["steps"]["build"]["reused"])

    def test_corrupt_or_missing_artifact_rebuilds(self):
        first = self.run_plan()
        cached = Path(next(iter(first["steps"]["build"]["outputs"])))
        cached.write_text("tampered")
        self.assertFalse(self.run_plan()["steps"]["build"]["reused"])
        second = self.run_plan()
        Path(next(iter(second["steps"]["build"]["outputs"]))).unlink()
        self.assertFalse(self.run_plan()["steps"]["build"]["reused"])
        self.assertEqual(self.counter.read_text(), "3")

    def test_volatile_checks_are_never_cached(self):
        self.plan["steps"][0]["cacheable"] = False
        self.run_plan()
        self.run_plan()
        self.assertEqual(self.counter.read_text(), "2")

    def test_failure_is_not_cached_as_pass(self):
        self.plan["steps"][0]["command"] = [sys.executable, "-c", "raise SystemExit(4)"]
        with self.assertRaisesRegex(RuntimeError, "failed"):
            self.run_plan()
        report = json.loads((self.cache / "latest-result.json").read_text())
        self.assertFalse(report["passed"])
        self.assertFalse(report["cutover_authorized"])
        self.assertEqual(list((self.cache / "cache/evidence").glob("*")), [])

    def test_missing_prerequisite_stops_before_any_build(self):
        self.plan["steps"].append({"id": "qa", "command": [sys.executable, "--version"],
                                  "tools": [["vk-fixture-no-such-tool", "--version"]]})
        with self.assertRaisesRegex(ValueError, "Missing preparation tool"):
            self.run_plan()
        self.assertFalse(self.counter.exists())

    def test_dirty_source_refuses_reuse(self):
        self.run_plan()
        (self.source / "source.txt").write_text("uncommitted")
        with self.assertRaisesRegex(ValueError, "dirty"):
            self.run_plan()
        self.assertFalse(json.loads((self.cache / "latest-result.json").read_text())["passed"])

    def test_source_mutating_check_refuses_evidence(self):
        self.plan["steps"][0]["command"] = [sys.executable, "-c", "from pathlib import Path; Path('source.txt').write_text('changed')"]
        with self.assertRaisesRegex(ValueError, "dirty"):
            self.run_plan()
        self.assertFalse(json.loads((self.cache / "latest-result.json").read_text())["passed"])

    def test_build_tool_identity_change_invalidates_reuse(self):
        self.run_plan()
        with patch.object(Preparation, "tool", return_value={"response_sha256": "different", "executable_sha256": "different"}):
            self.assertFalse(self.run_plan()["steps"]["build"]["reused"])

    def test_dependency_outputs_invalidate_child(self):
        self.plan["steps"][0]["cacheable"] = False
        self.plan["steps"][0]["command"] = [sys.executable, "-c", "from pathlib import Path; Path(" + repr(str(self.artifact)) + ").write_text(str(__import__('time').time_ns()))"]
        self.plan["steps"].append({"id": "check", "command": [sys.executable, "--version"],
                                  "depends_on": ["build"], "cacheable": True})
        self.run_plan()
        self.assertFalse(self.run_plan()["steps"]["check"]["reused"])

    def test_frontend_only_does_not_require_backend_cutover(self):
        baseline = self.git("rev-parse", "HEAD").decode().strip()
        directory = self.source / "packages/local-web"
        directory.mkdir(parents=True)
        (directory / "app.tsx").write_text("UI only")
        self.commit()
        self.assertEqual(deployment_kind(self.source, baseline), "frontend-only")
        (self.source / "Cargo.toml").write_text("backend input")
        self.commit()
        self.assertEqual(deployment_kind(self.source, baseline), "backend-cutover")

    def test_mutable_build_output_does_not_replace_verified_artifact(self):
        first = self.run_plan()
        self.artifact.write_text("other agent built a different release")
        second = self.run_plan()
        self.assertTrue(second["steps"]["build"]["reused"])
        stored = Path(next(iter(second["steps"]["build"]["outputs"])))
        self.assertEqual(stored.read_text(), "verified artifact")
        self.assertEqual(self.artifact.read_text(), "other agent built a different release")

    def test_output_mutating_during_copy_refuses_evidence(self):
        original_copy = shutil.copy2

        def racing_copy(source, destination, **kwargs):
            if Path(source) == self.artifact:
                self.artifact.write_text("concurrent build replaced output")
            return original_copy(source, destination, **kwargs)

        with patch("vk_prepare.shutil.copy2", side_effect=racing_copy):
            with self.assertRaisesRegex(ValueError, "output changed"):
                self.run_plan()
        self.assertFalse(json.loads((self.cache / "latest-result.json").read_text())["passed"])

    def test_other_preparation_directory_reuses_same_verified_cache(self):
        plan = copy.deepcopy(self.plan)
        plan["cache_directory"] = str(self.root / "persistent-cache")
        self.run_plan(plan)
        second = Preparation(self.source, self.root / "next-deployment", plan).run()
        self.assertTrue(second["steps"]["build"]["reused"])

    def test_elapsed_preparation_includes_time_before_build(self):
        self.cache.mkdir()
        (self.cache / "preparation-clock.json").write_text(json.dumps({"started_at": time.time() - 3600}))
        result = self.run_plan()
        self.assertGreater(result["elapsed_since_preparation_started_seconds"], 3600)
        self.assertLess(result["total_preparation_seconds"], 10)

    def test_generated_frontend_plan_contains_no_backend_build(self):
        baseline = self.git("rev-parse", "HEAD").decode().strip()
        directory = self.source / "packages/local-web"
        directory.mkdir(parents=True)
        (directory / "app.tsx").write_text("UI only")
        self.commit()
        plan = default_plan(self.source, self.cache, baseline)
        self.assertEqual(plan["deployment_kind"], "frontend-only")
        self.assertNotIn("release-build", [step["id"] for step in plan["steps"]])
        self.assertTrue(plan["remaining_gates"])

    def test_missing_cached_validation_log_requires_new_check(self):
        first = self.run_plan()
        Path(first["steps"]["build"]["log"]).unlink()
        self.assertFalse(self.run_plan()["steps"]["build"]["reused"])

    def test_context_mutation_during_build_refuses_evidence(self):
        context = self.root / "launcher"
        context.write_text("before")
        self.plan["steps"][0]["context_files"] = [str(context)]
        self.plan["steps"][0]["command"] = [sys.executable, "-c", "from pathlib import Path; Path(" + repr(str(context)) + ").write_text('after')"]
        with self.assertRaisesRegex(ValueError, "inputs changed"):
            self.run_plan()


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.sessions = [str(uuid.uuid4()) for _ in range(80)]
        self.queued = set()
        self.fail = set()
        self.methods = []
        test = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                test.methods.append(self.command)
                session = self.path.split("/")[-2]
                time.sleep(.004)
                queue = {"status": "queued", "message": {"text": "preserve me"}} if session in test.queued else {"status": "empty"}
                body = json.dumps({"success": session not in test.fail, "data": queue}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.origin = "http://127.0.0.1:" + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_concurrent_checks_keep_every_queue_and_are_get_only(self):
        self.queued.add(self.sessions[-1])
        result = read_only_queues(self.origin, self.sessions, workers=8)
        self.assertEqual(result["checked"], len(self.sessions))
        self.assertEqual([row["session"] for row in result["queued"]], [self.sessions[-1]])
        self.assertEqual(set(self.methods), {"GET"})

    def test_new_queue_is_seen_on_next_check(self):
        self.assertEqual(read_only_queues(self.origin, self.sessions[:1])["queued"], [])
        self.queued.add(self.sessions[0])
        self.assertEqual(len(read_only_queues(self.origin, self.sessions[:1])["queued"]), 1)

    def test_any_failed_request_blocks_the_inventory(self):
        self.fail.add(self.sessions[-1])
        with self.assertRaisesRegex(ValueError, "Queue check failed"):
            read_only_queues(self.origin, self.sessions)

    def test_non_loopback_or_invalid_limits_refused(self):
        for origin in ("https://vibe.local", "http://127.0.0.1/api", "http://127.0.0.1?query=x"):
            with self.assertRaises(ValueError):
                read_only_queues(origin, self.sessions)
        with self.assertRaises(ValueError):
            read_only_queues(self.origin, self.sessions, workers=0)


if __name__ == "__main__":
    unittest.main()
