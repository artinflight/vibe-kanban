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

from vk_prepare import Preparation, default_plan, deployment_kind, read_only_queues, pending_sessions, record_publication, verify_artifacts


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

    def test_dependency_error_is_found_before_any_step_runs(self):
        self.plan["steps"].append({"id": "late", "command": [sys.executable, "--version"],
                                   "depends_on": ["unknown-step"]})
        with self.assertRaisesRegex(ValueError, "dependencies must precede"):
            self.run_plan()
        self.assertFalse(self.counter.exists())
        self.assertFalse(json.loads((self.cache / "latest-result.json").read_text())["passed"])

    def test_missing_required_file_is_found_before_build(self):
        self.plan["required_files"] = [{"path": str(self.root / "private-overlay"), "sha256": "0" * 64}]
        with self.assertRaisesRegex(ValueError, "input missing or changed"):
            self.run_plan()
        self.assertFalse(self.counter.exists())

    def test_changed_required_file_blocks_reuse_and_build(self):
        import hashlib
        path = self.root / "private-overlay"
        path.write_bytes(b"reviewed")
        self.plan["required_files"] = [{"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}]
        self.run_plan()
        path.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "input missing or changed"):
            self.run_plan()
        self.assertEqual(self.counter.read_text(), "1")

    def test_required_file_mutation_during_build_refuses_evidence(self):
        import hashlib
        path = self.root / "private-overlay"
        path.write_bytes(b"reviewed")
        self.plan["required_files"] = [{"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}]
        self.plan["steps"][0]["command"] = [sys.executable, "-c", "from pathlib import Path; Path(" + repr(str(path)) + ").write_bytes(b'changed')"]
        with self.assertRaisesRegex(ValueError, "input missing or changed"):
            self.run_plan()

    def test_bad_receipt_reruns_only_corrupt_step(self):
        self.run_plan()
        receipt = next((self.cache / "cache/evidence").glob("*.json"))
        receipt.write_text("{truncated")
        self.assertFalse(self.run_plan()["steps"]["build"]["reused"])
        self.assertEqual(self.counter.read_text(), "2")

    def test_active_cache_owner_refuses_duplicate_without_waiting(self):
        import fcntl
        plan = copy.deepcopy(self.plan)
        plan["cache_directory"] = str(self.root / "persistent-cache")
        owner = Preparation(self.source, self.cache, plan)
        with (owner.cache / ".preparation.lock").open("a") as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(RuntimeError, "already has an owner"):
                owner.run()
        self.assertFalse(self.counter.exists())

    def test_volatile_step_cannot_be_mislabelled_cacheable(self):
        self.plan["steps"][0]["volatile"] = True
        with self.assertRaisesRegex(ValueError, "Volatile acceptance cannot be cached"):
            self.run_plan()
        self.assertFalse(self.counter.exists())

    def test_invalid_timeout_blocks_before_build(self):
        self.plan["steps"].append({"id": "late", "command": [sys.executable, "--version"],
                                  "timeout_seconds": float("inf")})
        with self.assertRaisesRegex(ValueError, "finite positive timeouts"):
            self.run_plan()
        self.assertFalse(self.counter.exists())

    def test_generic_backend_build_recipe_is_not_generated(self):
        baseline = self.git("rev-parse", "HEAD").decode().strip()
        (self.source / "Cargo.toml").write_text("backend change")
        self.commit()
        with self.assertRaisesRegex(ValueError, "explicit approved isolated build plan"):
            default_plan(self.source, self.cache, baseline)

    def test_frontend_scope_reuses_validation_after_backend_only_change(self):
        frontend = self.source / "packages"
        frontend.mkdir()
        (frontend / "view.tsx").write_text("UI")
        self.commit()
        self.plan["steps"][0]["inputs"] = ["packages"]
        self.run_plan()
        (self.source / "backend.rs").write_text("backend change")
        self.commit()
        self.assertTrue(self.run_plan()["steps"]["build"]["reused"])
        (frontend / "view.tsx").write_text("changed UI")
        self.commit()
        self.assertFalse(self.run_plan()["steps"]["build"]["reused"])

    def test_missing_command_is_found_before_any_build(self):
        self.plan["steps"].append({"id": "late", "command": ["vk-fixture-no-such-command"]})
        with self.assertRaisesRegex(ValueError, "Missing preparation command"):
            self.run_plan()
        self.assertFalse(self.counter.exists())

    def publication_fixture(self, basis="fix-ready", elapsed=610):
        import datetime
        import hashlib
        prepared = self.run_plan()
        clock = self.cache / "preparation-clock.json"
        clock.write_text(json.dumps({"started_at": time.time() - elapsed, "basis": basis}))
        artifact = next(iter(prepared["steps"]["build"]["outputs"].values()))["sha256"]
        receipt = {"published_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   "source_tree": prepared["source_tree"], "server_sha256": artifact,
                   "current_data_reused": True, "exact18_once_only": True,
                   "live": {"trusted_https": True},
                   "statuses": [{"http": 200, "protocol": 1, "once_only": True}] * 18}
        path = self.root / "mock-publication.json"
        path.write_text(json.dumps(receipt))
        return path, receipt, hashlib.sha256(path.read_bytes()).hexdigest()

    def test_pipeline_time_includes_prebuild_wait_and_build(self):
        path, _, sha = self.publication_fixture(elapsed=610)
        result = record_publication(self.cache, path, sha)
        self.assertGreaterEqual(result["fix_ready_to_work_resumed_seconds"], 610)
        self.assertFalse(result["ten_minute_target_met"])
        self.assertFalse(result["live_reverified_by_this_tool"])

    def test_preparation_clock_alone_cannot_prove_ten_minute_target(self):
        path, _, sha = self.publication_fixture(basis="preparation-started", elapsed=10)
        result = record_publication(self.cache, path, sha)
        self.assertIsNone(result["fix_ready_to_work_resumed_seconds"])
        self.assertFalse(result["ten_minute_target_met"])

    def test_receipt_mismatch_does_not_create_completion(self):
        path, _, _ = self.publication_fixture()
        with self.assertRaisesRegex(ValueError, "receipt identity changed"):
            record_publication(self.cache, path, "0" * 64)
        self.assertFalse((self.cache / "pipeline-result.json").exists())

    def test_wrong_artifact_does_not_create_completion(self):
        import hashlib
        path, receipt, _ = self.publication_fixture()
        receipt["server_sha256"] = "0" * 64
        path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, "artifact does not match"):
            record_publication(self.cache, path, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_recovery_failure_does_not_create_completion(self):
        import hashlib
        path, receipt, _ = self.publication_fixture()
        receipt["statuses"][-1] = {"http": 500, "protocol": 1, "once_only": False}
        path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, "lacks required"):
            record_publication(self.cache, path, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_existing_pipeline_completion_is_idempotent(self):
        path, _, sha = self.publication_fixture(elapsed=10)
        first = record_publication(self.cache, path, sha)
        self.assertEqual(record_publication(self.cache, path, sha), first)
        self.assertTrue(first["ten_minute_target_met"])

    def test_artifact_verification_avoids_rebuild_and_copy(self):
        import hashlib
        self.artifact.write_bytes(b"accepted binary")
        manifest = {"source": {"combined_source_tree": "reviewed"}, "artifacts": {
            name: {"path": str(self.artifact), "bytes": self.artifact.stat().st_size,
                   "sha256": hashlib.sha256(self.artifact.read_bytes()).hexdigest()}
            for name in ("candidate", "rollback")}}
        path = self.root / "accepted-manifest.json"
        path.write_text(json.dumps(manifest))
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        result = verify_artifacts(path, sha, "reviewed")
        self.assertFalse(result["compiler_invoked"])
        self.assertEqual(result["copied_payload_bytes"], 0)
        self.assertFalse(self.counter.exists())
        self.artifact.write_bytes(b"corrupt artifact")
        with self.assertRaisesRegex(ValueError, "artifact changed"):
            verify_artifacts(path, sha, "reviewed")

    def test_artifact_manifest_different_source_is_rejected(self):
        import hashlib
        path = self.root / "accepted-manifest.json"
        path.write_text(json.dumps({"source": {"combined_source_tree": "other"}}))
        with self.assertRaisesRegex(ValueError, "different source content"):
            verify_artifacts(path, hashlib.sha256(path.read_bytes()).hexdigest(), "reviewed")

    def test_accepted_artifacts_bind_without_cache_payload_copy(self):
        import datetime
        import hashlib
        tree = self.git("rev-parse", "HEAD^{tree}").decode().strip()
        self.artifact.write_bytes(b"accepted binary")
        sha = hashlib.sha256(self.artifact.read_bytes()).hexdigest()
        manifest = self.root / "accepted.json"
        manifest.write_text(json.dumps({"source": {"combined_source_tree": tree}, "artifacts": {
            name: {"path": str(self.artifact), "sha256": sha, "bytes": self.artifact.stat().st_size}
            for name in ("candidate", "rollback")}}))
        self.plan["accepted_artifact_manifest"] = {"path": str(manifest), "sha256": hashlib.sha256(manifest.read_bytes()).hexdigest()}
        self.plan["steps"] = [{"id": "fresh", "command": [sys.executable, "--version"],
                               "volatile": True, "cacheable": False}]
        result = self.run_plan()
        self.assertTrue(result["passed"])
        self.assertFalse((self.cache / "cache/artifacts").exists())
        published = self.root / "mock-publication.json"
        published.write_text(json.dumps({"source_tree": tree, "server_sha256": sha,
            "published_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "current_data_reused": True, "exact18_once_only": True,
            "live": {"trusted_https": True},
            "statuses": [{"http": 200, "protocol": 1, "once_only": True}] * 18}))
        completion = record_publication(self.cache, published, hashlib.sha256(published.read_bytes()).hexdigest())
        self.assertEqual(completion["server_sha256"], sha)
        self.assertFalse(completion["live_reverified_by_this_tool"])
        self.artifact.write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "artifact changed"):
            self.run_plan()

    def test_accepted_artifact_source_mismatch_blocks_before_build(self):
        import hashlib
        manifest = self.root / "accepted.json"
        manifest.write_text(json.dumps({"source": {"combined_source_tree": "wrong"}}))
        self.plan["accepted_artifact_manifest"] = {"path": str(manifest), "sha256": hashlib.sha256(manifest.read_bytes()).hexdigest()}
        with self.assertRaisesRegex(ValueError, "different source content"):
            self.run_plan()
        self.assertFalse(self.counter.exists())

    def test_missing_rollback_is_rejected_before_artifact_reads(self):
        import hashlib
        path = self.root / "accepted-manifest.json"
        path.write_text(json.dumps({"source": {"combined_source_tree": "reviewed"}, "artifacts": {"candidate": {}}}))
        with self.assertRaisesRegex(ValueError, "rollback are both required"):
            verify_artifacts(path, hashlib.sha256(path.read_bytes()).hexdigest(), "reviewed")

    def snapshot_fixture(self):
        import hashlib
        source = self.root / "sealed-source"
        source.mkdir()
        member = source / "unit.rs"
        member.write_bytes(b"reviewed private source")
        (source / "link.rs").symlink_to("unit.rs")
        manifest = self.root / "source-manifest.json"
        manifest.write_text(json.dumps({"source": "c" * 40, "tracked": {
            "unit.rs": {"kind": "file", "sha256": hashlib.sha256(member.read_bytes()).hexdigest()},
            "link.rs": {"kind": "symlink", "target": "unit.rs"}}}))
        self.plan["source_snapshot"] = {"manifest": str(manifest),
            "sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
            "source_commit": "c" * 40, "source_tree": "f" * 40}
        return source, member, manifest

    def test_sealed_source_without_git_supports_verified_reuse(self):
        source, _, _ = self.snapshot_fixture()
        first = Preparation(source, self.cache, self.plan).run()
        second = Preparation(source, self.cache, self.plan).run()
        self.assertEqual(first["source_tree"], "f" * 40)
        self.assertTrue(second["steps"]["build"]["reused"])
        self.assertEqual(self.counter.read_text(), "1")

    def test_sealed_member_mutation_blocks_cached_pass(self):
        source, member, _ = self.snapshot_fixture()
        Preparation(source, self.cache, self.plan).run()
        member.write_bytes(b"changed private source")
        with self.assertRaisesRegex(ValueError, "source content changed"):
            Preparation(source, self.cache, self.plan).run()
        self.assertEqual(self.counter.read_text(), "1")

    def test_sealed_manifest_mutation_blocks_before_build(self):
        source, _, manifest = self.snapshot_fixture()
        manifest.write_text("{}")
        with self.assertRaisesRegex(ValueError, "source manifest changed"):
            Preparation(source, self.cache, self.plan).run()
        self.assertFalse(self.counter.exists())

    def test_sealed_source_credential_addition_blocks_before_build(self):
        source, _, _ = self.snapshot_fixture()
        (source / ".env").write_text("fixture only")
        with self.assertRaisesRegex(ValueError, "must not acquire credentials"):
            Preparation(source, self.cache, self.plan).run()
        self.assertFalse(self.counter.exists())


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

    def test_pending_summary_does_not_expose_or_clear_prompt(self):
        self.queued.add(self.sessions[0])
        result = pending_sessions(self.origin, self.sessions)
        self.assertEqual(result["pending_sessions"], [self.sessions[0]])
        self.assertNotIn("preserve me", json.dumps(result))
        self.assertFalse(result["writer_fence_established"])
        self.assertFalse(result["cutover_authorized"])
        self.assertEqual(set(self.methods), {"GET"})

    def test_failed_inventory_does_not_drain_thousands_of_future_gets(self):
        self.sessions = [str(uuid.uuid4()) for _ in range(1139)]
        self.fail.update(self.sessions)
        with self.assertRaisesRegex(ValueError, "Queue check failed"):
            read_only_queues(self.origin, self.sessions, workers=4)
        self.assertLessEqual(len(self.methods), 4)


if __name__ == "__main__":
    unittest.main()
