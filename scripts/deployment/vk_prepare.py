#!/usr/bin/env python3
"""Repeatable pre-cutover preparation; never authorizes or performs a cutover."""

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import datetime
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import subprocess
import time
import urllib.parse
import urllib.request
import uuid

from vk_prep_common import digest, identity, measured, save, storage

BUILD_ENVIRONMENT = ("PATH", "HOME", "LANG", "LC_ALL", "SSL_CERT_FILE", "RUSTUP_HOME",
                     "CARGO_HOME", "PNPM_HOME", "CC", "CXX", "RUSTC_WRAPPER", "RUSTFLAGS",
                     "CARGO_TARGET_DIR", "CARGO_INCREMENTAL", "SQLX_OFFLINE", "NODE_OPTIONS",
                     "NODE_ENV", "CI")


def git(source, *args):
    return subprocess.check_output(["git", "-C", str(source), *args])


def clean_tree(source):
    if git(source, "status", "--porcelain").strip():
        raise ValueError("Candidate source is dirty; do not reuse release evidence")
    return git(source, "rev-parse", "HEAD^{tree}").decode().strip()


def deployment_kind(source, deployed):
    names = git(source, "diff", "--name-only", "-z", deployed, "HEAD").decode().split("\0")
    names = [name for name in names if name]
    if not names:
        return "unchanged"
    if all(name.endswith((".md", ".mdx")) for name in names):
        return "docs-only"
    if all(name.startswith(("scripts/deployment/", "scripts/test-")) or name.endswith((".md", ".mdx")) for name in names):
        return "preparation-only"
    if all(name.startswith(("packages/local-web/", "packages/web-core/", "packages/ui/", "packages/public/"))
           or name.endswith((".md", ".mdx")) for name in names):
        return "frontend-only"
    return "backend-cutover"


def output_hashes(paths):
    result = {}
    for raw in paths:
        root = Path(raw)
        if root.is_symlink():
            raise ValueError("Release output root must not be a symlink: " + str(root))
        if not root.exists():
            raise ValueError("Required output is absent: " + str(root))
        files = sorted(root.rglob("*")) if root.is_dir() else [root]
        if root.is_dir() and not files:
            raise ValueError("Required output directory is empty: " + str(root))
        for path in files:
            if path.is_symlink():
                raise ValueError("Release outputs must not depend on mutable external symlinks: " + str(path))
            if path.is_file():
                result[str(path)] = {"sha256": digest(path), "mode": path.stat().st_mode & 0o777}
    return result


def default_plan(source, root, deployed):
    kind = deployment_kind(source, deployed)
    if kind == "backend-cutover":
        raise ValueError("Backend preparation requires an explicit approved isolated build plan")
    python = ["python3", "--version"]
    node = [["node", "--version"], ["pnpm", "--version"]]
    inputs = [".cargo", "Cargo.toml", "Cargo.lock", "rust-toolchain.toml", "rustfmt.toml", "crates",
              "packages", "shared", "assets", ".sqlx", "package.json", "pnpm-lock.yaml",
              "pnpm-workspace.yaml", "scripts"]
    context = [str(Path(source) / prefix / name) for prefix in ("", "packages/local-web")
               for name in (".env", ".env.local", ".env.production", ".env.production.local")]
    context.extend(str(Path(source) / name) for name in (".cargo/config", ".cargo/config.toml", ".npmrc"))
    steps = [
        {"id": "preparation-tests", "command": ["python3", "-m", "unittest", "discover", "-s", "scripts/deployment", "-p", "test_vk_*.py"],
         "tools": [python], "cacheable": True},
        {"id": "ops", "command": ["pnpm", "run", "ops:check"], "tools": node, "cacheable": True},
        {"id": "diff", "command": ["git", "diff", "--check"], "cacheable": False},
    ]
    if kind in ("frontend-only", "backend-cutover"):
        for name in ("local-web:check", "web-core:check", "ui:check", "local-web:lint", "ui:lint"):
            steps.append({"id": name.replace(":", "-"), "command": ["pnpm", "run", name], "tools": node,
                          "inputs": inputs, "context_files": context, "cacheable": True})
        steps.append({"id": "frontend-build", "command": ["pnpm", "--filter", "@vibe/local-web", "run", "build"],
                      "outputs": ["packages/local-web/dist"], "tools": node, "inputs": inputs,
                      "context_files": context, "cacheable": True})
    return {"schema": 1, "deployment_kind": kind, "cache_directory": "/mnt/vk-storage/vk-preparation-cache",
            "environment": {"CARGO_TARGET_DIR": "/mnt/vk-storage/cargo-target", "CARGO_INCREMENTAL": "0",
                            "SQLX_OFFLINE": "true", "NODE_OPTIONS": "--max-old-space-size=8192",
                            "PYTHONDONTWRITEBYTECODE": "1"},
            "steps": steps, "excluded_validation": ["Tauri/remote aggregate suites are not represented by this local-web/backend recipe"],
            "remaining_gates": ["Issue reconciliation and release-specific functional QA", "Exact runtime/account/home and fresh model proof",
                                "Latest-data backup and restore verification", "Fresh active/queued work and writer inventory",
                                "Installed capacity configuration, ownership/cutback rehearsal and explicit cutover approval"]}


def read_only_queues(origin, sessions, workers=4, timeout=5):
    url = urllib.parse.urlsplit(origin)
    if (url.scheme != "http" or url.hostname not in ("127.0.0.1", "localhost", "::1")
            or url.path not in ("", "/") or url.query or url.fragment or url.username or url.password):
        raise ValueError("Queue checks require the direct loopback backend")
    if not 1 <= workers <= 32 or timeout <= 0:
        raise ValueError("Invalid queue concurrency or timeout")
    sessions = sorted({str(uuid.UUID(value)) for value in sessions})

    def fetch(session):
        request = urllib.request.Request(origin.rstrip("/") + "/api/sessions/" + session + "/queue")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            value = json.load(response)
        if value.get("success") is not True or not isinstance(value.get("data"), dict):
            raise ValueError("Queue check failed for " + session)
        queue = value["data"]
        if queue.get("status") not in ("empty", "queued"):
            raise ValueError("Unknown queue status for " + session)
        return {"session": session, "queue": queue} if queue["status"] != "empty" else None

    started = time.monotonic()
    queued = []
    remaining = iter(sessions)
    pool = ThreadPoolExecutor(max_workers=workers)
    pending = set()
    try:
        for session in remaining:
            pending.add(pool.submit(fetch, session))
            if len(pending) == workers:
                break
        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            # Resolve the completed batch before submitting anything else. A
            # refusal stops the scan; do not wait for thousands of queued GETs.
            rows = [future.result() for future in done]
            pending.difference_update(done)
            queued.extend(row for row in rows if row is not None)
            while len(pending) < workers:
                session = next(remaining, None)
                if session is None:
                    break
                pending.add(pool.submit(fetch, session))
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
    queued.sort(key=lambda row: row["session"])
    return {"checked": len(sessions), "queued": queued, "workers": workers,
            "seconds": time.monotonic() - started, "fresh": True}


def pending_sessions(origin, sessions, workers=4, timeout=5):
    """Fresh observation only: never clears prompts or establishes a writer fence."""
    result = read_only_queues(origin, sessions, workers, timeout)
    return {"checked": result["checked"],
            "pending_sessions": [row["session"] for row in result["queued"]],
            "workers": result["workers"], "seconds": result["seconds"],
            "fresh_observation_only": True, "writer_fence_established": False,
            "cutover_authorized": False}


def database_sessions(database):
    with sqlite3.connect(Path(database).resolve().as_uri() + "?mode=ro", uri=True) as db:
        return [str(uuid.UUID(bytes=row[0])) for row in db.execute("SELECT id FROM sessions")]


def verify_artifacts(manifest_path, expected_sha256, expected_tree):
    """Verify a pinned accepted bundle without rebuilding or duplicating its files."""
    raw = Path(manifest_path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Accepted artifact manifest changed")
    manifest = json.loads(raw)
    if manifest["source"]["combined_source_tree"] != expected_tree:
        raise ValueError("Accepted artifacts belong to different source content")
    artifacts = manifest["artifacts"]
    if not artifacts or not {"candidate", "rollback"} <= artifacts.keys():
        raise ValueError("Accepted candidate and compatible rollback are both required")
    checked = {}
    for name, item in artifacts.items():
        path = Path(item["path"])
        if path.is_symlink() or not path.is_file():
            raise ValueError("Accepted artifact must be a direct regular file")
        before = path.stat()
        actual = digest(path)
        after = path.stat()
        fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
        if (any(getattr(before, key) != getattr(after, key) for key in fields)
                or actual != item["sha256"] or after.st_size != item["bytes"]):
            raise ValueError("Accepted artifact changed: " + name)
        checked[name] = {"sha256": actual, "bytes": after.st_size}
    return {"passed": True, "source_tree": expected_tree,
            "manifest_sha256": expected_sha256, "artifacts": checked,
            "compiler_invoked": False, "copied_payload_bytes": 0,
            "behavior_retested": False, "fresh_data_and_runtime_acceptance_required": True,
            "cutover_authorized": False}


def record_publication(root, receipt_path, expected_sha256):
    """Bind measured completion to an already verified actor receipt; no live effects."""
    root = storage(root)
    raw = Path(receipt_path).read_bytes()
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256) or hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Publication receipt identity changed")
    receipt = json.loads(raw)
    result = json.loads((root / "latest-result.json").read_text())
    clock = json.loads((root / "preparation-clock.json").read_text())
    if result.get("passed") is not True or result["source_tree"] != receipt.get("source_tree"):
        raise ValueError("Publication source does not match completed preparation")
    accepted = result.get("accepted_artifact_manifest")
    if accepted:
        bound = verify_artifacts(accepted["path"], accepted["sha256"], result["source_tree"])
        if receipt.get("server_sha256") != bound["artifacts"]["candidate"]["sha256"]:
            raise ValueError("Publication artifact does not match the accepted candidate")
    else:
        outputs = {path: value for step in result["steps"].values() for path, value in step["outputs"].items()}
        if output_hashes(outputs) != outputs or receipt.get("server_sha256") not in {v["sha256"] for v in outputs.values()}:
            raise ValueError("Publication artifact does not match verified preparation outputs")
    statuses = receipt.get("statuses", [])
    if (receipt.get("current_data_reused") is not True or receipt.get("exact18_once_only") is not True
            or receipt.get("live", {}).get("trusted_https") is not True or len(statuses) != 18
            or any(row.get("http") != 200 or row.get("protocol") != 1 or row.get("once_only") is not True for row in statuses)):
        raise ValueError("Publication lacks required accepted data/HTTPS/recovery evidence")
    published = datetime.datetime.fromisoformat(receipt["published_at"])
    if published.tzinfo is None:
        raise ValueError("Publication time must include timezone")
    elapsed = published.timestamp() - clock["started_at"]
    if elapsed < 0 or published.timestamp() > time.time():
        raise ValueError("Publication time is outside this preparation interval")
    fix_ready = clock.get("basis") == "fix-ready"
    resumed_seconds = None
    resume = receipt.get("queued_work_resume")
    if resume is not None:
        # This is a bound actor receipt, not a second live verifier. Publication
        # alone cannot prove that queued production work actually started.
        if (not isinstance(resume, dict) or resume.get("verified") is not True
                or not isinstance(resume.get("session_id"), str)
                or not isinstance(resume.get("execution_id"), str)
                or not isinstance(resume.get("started_at"), str)):
            raise ValueError("Queued-work resume evidence is incomplete")
        uuid.UUID(resume["session_id"]);uuid.UUID(resume["execution_id"])
        resumed = datetime.datetime.fromisoformat(resume["started_at"])
        if (resumed.tzinfo is None or resumed < published or resumed.timestamp() > time.time()):
            raise ValueError("Queued-work start time is outside publication/resume interval")
        resumed_seconds = resumed.timestamp() - clock["started_at"]
    report = {"publication_receipt_sha256": expected_sha256,
              "source_tree": result["source_tree"], "server_sha256": receipt["server_sha256"],
              "preparation_to_publication_seconds": elapsed,
              "fix_ready_to_publication_seconds": elapsed if fix_ready else None,
              "preparation_to_work_resumed_seconds": resumed_seconds,
              "fix_ready_to_work_resumed_seconds": resumed_seconds if fix_ready else None,
              "queued_work_resume_receipt_present": resume is not None,
              "ten_minute_target_met": fix_ready and resumed_seconds is not None and resumed_seconds <= 600,
              "includes_build_validation_quiet_wait_and_switch": True,
              "live_reverified_by_this_tool": False, "receipt_only": True,
              "cutover_authorized": False}
    previous = root / "pipeline-result.json"
    if previous.exists() and json.loads(previous.read_text()) != report:
        raise ValueError("Existing completed pipeline must not be overwritten")
    save(root / "pipeline-result.json", report)
    return report


class Preparation:
    def __init__(self, source, root, plan):
        self.source = Path(source).resolve()
        self.root = storage(root)
        self.plan = plan
        self.cache = storage(plan.get("cache_directory", self.root / "cache"))
        self.cache.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.timings = {}
        self.tool_results = {}
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        inherited = (*BUILD_ENVIRONMENT, *plan.get("inherit_environment", []))
        self.environment = {name: os.environ[name] for name in inherited if name in os.environ}
        self.environment.update(plan.get("environment", {}))
        self.environment["TMPDIR"] = str(self.cache / "tmp")
        Path(self.environment["TMPDIR"]).mkdir(exist_ok=True)
        self.run_root = self.root / ("run-" + uuid.uuid4().hex)
        self.run_root.mkdir(mode=0o700)

    def snapshot(self):
        binding = self.plan["source_snapshot"]
        raw = Path(binding["manifest"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != binding["sha256"]:
            raise ValueError("Sealed source manifest changed")
        value = json.loads(raw)
        if (value["source"] != binding["source_commit"] or not value.get("tracked")
                or not re.fullmatch(r"[0-9a-f]{40}", binding["source_tree"])):
            raise ValueError("Sealed source identity is incomplete or mismatched")
        return value

    def source_tree(self):
        if "source_snapshot" not in self.plan:
            return clean_tree(self.source)
        manifest = self.snapshot()
        if (self.source / ".env").exists() or (self.source / ".git").exists():
            raise ValueError("Sealed build source must not acquire credentials or Git state")
        for name, item in manifest["tracked"].items():
            relative = Path(name)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Sealed source path escapes its root")
            path = self.source / relative
            if not path.parent.resolve().is_relative_to(self.source):
                raise ValueError("Sealed source parent escapes its root")
            info = path.lstat()
            if item["kind"] == "symlink":
                if not path.is_symlink() or os.readlink(path) != item["target"]:
                    raise ValueError("Sealed source link changed: " + name)
            elif item["kind"] == "file":
                if not stat.S_ISREG(info.st_mode) or digest(path) != item["sha256"]:
                    raise ValueError("Sealed source content changed: " + name)
            else:
                raise ValueError("Unsupported sealed source member: " + name)
        return self.plan["source_snapshot"]["source_tree"]

    def tool(self, command):
        key = tuple(command)
        if key in self.tool_results:
            executable = shutil.which(command[0], path=self.environment.get("PATH"))
            if executable is None or digest(Path(executable).resolve()) != self.tool_results[key]["executable_sha256"]:
                self.tool_results.pop(key)
        if key not in self.tool_results:
            if not command or shutil.which(command[0], path=self.environment.get("PATH")) is None:
                raise ValueError("Missing preparation tool: " + (command[0] if command else "empty command"))
            value = subprocess.check_output(command, cwd=self.source, env=self.environment,
                                            stderr=subprocess.STDOUT, timeout=30)
            executable = shutil.which(command[0], path=self.environment.get("PATH"))
            self.tool_results[key] = {"response_sha256": identity(value.decode(errors="replace")),
                                     "executable_sha256": digest(Path(executable).resolve())}
        return self.tool_results[key]

    def fingerprint(self, step, dependencies):
        tools = {identity(command): self.tool(command) for command in step.get("tools", [])}
        # Entire tree by default: a newly added input cannot silently escape reuse guards.
        if "source_snapshot" in self.plan:
            source = self.snapshot()["tracked"]
        else:
            source = git(self.source, "ls-tree", "-r", "HEAD", "--", *step.get("inputs", ["."])).decode()
        files = {}
        for raw in step.get("context_files", []):
            path = Path(raw)
            path = path if path.is_absolute() else self.source / path
            key = "source:" + str(path.relative_to(self.source)) if path.is_relative_to(self.source) else str(path)
            files[key] = digest(path) if path.exists() else None
        return identity({"schema": 1, "source": source, "step": step, "dependencies": dependencies,
                         "environment": self.environment, "tools": tools, "context_files": files,
                         "required_files": self.plan.get("required_files", []),
                         "source_snapshot": self.plan.get("source_snapshot"),
                         "accepted_artifact_manifest": self.plan.get("accepted_artifact_manifest"),
                         "runner_sha256": digest(__file__),
                         "helpers_sha256": digest(Path(__file__).with_name("vk_prep_common.py"))})

    def run(self):
        with (self.cache / ".preparation.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise RuntimeError("Preparation cache already has an owner; do not launch duplicate work") from error
            return self.run_locked()

    def validate_plan(self):
        steps = self.plan.get("steps", [])
        names = [step["id"] for step in steps]
        if (not steps or len(set(names)) != len(names)
                or any(not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name) for name in names)):
            raise ValueError("Preparation step IDs must be nonempty unique safe names")
        available = set()
        for step in steps:
            command = step.get("command")
            if not isinstance(command, list) or not command or any(not isinstance(arg, str) for arg in command):
                raise ValueError("Preparation commands must be explicit nonempty argument lists")
            if shutil.which(command[0], path=self.environment.get("PATH")) is None:
                raise ValueError("Missing preparation command: " + command[0])
            timeout = step.get("timeout_seconds", 1800)
            if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
                raise ValueError("Preparation commands need finite positive timeouts")
            dependencies = set(step.get("depends_on", []))
            if not dependencies <= available:
                raise ValueError("Preparation dependencies must precede their consumers: " + step["id"])
            if not set(step.get("materialize_source_outputs", [])) <= dependencies:
                raise ValueError("Materialized outputs must be declared dependencies")
            if step.get("volatile", False) and step.get("cacheable", False):
                raise ValueError("Volatile acceptance cannot be cached")
            available.add(step["id"])
        for item in self.plan.get("required_files", []):
            path = Path(item["path"])
            path = path if path.is_absolute() else self.source / path
            expected = item["sha256"]
            if not re.fullmatch(r"[0-9a-f]{64}", expected) or not path.is_file() or digest(path) != expected:
                raise ValueError("Required preparation input missing or changed: " + str(path))

    def artifacts(self, step):
        outputs = [Path(raw) if Path(raw).is_absolute() else self.source / raw for raw in step.get("outputs", [])]
        original_hashes = output_hashes(outputs)
        if not outputs:
            return {}, []
        folder = self.cache / "artifacts" / uuid.uuid4().hex
        folder.mkdir(parents=True, mode=0o700)
        copied = []
        for index, source in enumerate(outputs):
            target = folder / str(index) / source.name
            target.parent.mkdir()
            if source.is_dir():
                shutil.copytree(source, target, symlinks=True)
            else:
                shutil.copy2(source, target)
            copied_hashes = output_hashes([target])
            expected = {str(target / Path(raw).relative_to(source)) if source.is_dir() else str(target): value
                        for raw, value in original_hashes.items()
                        if Path(raw) == source or Path(raw).is_relative_to(source)}
            if copied_hashes != expected:
                raise ValueError("Build output changed while copying; refuse release evidence")
            copied.append(target)
        if output_hashes(outputs) != original_hashes:
            raise ValueError("Build output changed while copying; refuse release evidence")
        roots = [{"path": str(target), "original": str(raw)} for target, raw in zip(copied, step["outputs"])]
        return output_hashes(copied), roots

    def materialize(self, dependencies, results):
        for name in dependencies:
            for output in results[name]["artifact_roots"]:
                raw = Path(output["original"])
                if raw.is_absolute() or ".." in raw.parts:
                    raise ValueError("Only isolated candidate-relative outputs may be materialized")
                target = self.source / raw
                if not target.resolve().is_relative_to(self.source) or target.is_symlink():
                    raise ValueError("Candidate output path escapes isolated source")
                source = Path(output["path"])
                if source.is_dir():
                    temporary = target.with_name(target.name + "." + uuid.uuid4().hex + ".new")
                    temporary.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(source, temporary)
                    if target.exists():
                        target.replace(target.with_name(target.name + "." + uuid.uuid4().hex + ".previous"))
                    temporary.replace(target)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)

    def run_locked(self):
        started = time.monotonic()
        save(self.root / "latest-result.json", {"passed": False, "state": "running-or-interrupted",
                                               "cutover_authorized": False, "run": str(self.run_root)})
        clock = self.root / "preparation-clock.json"
        if not clock.exists():
            save(clock, {"started_at": time.time()})
        steps = self.plan.get("steps", [])
        tree = None
        results = {}
        passed = False
        try:
            tree = self.source_tree()
            self.validate_plan()
            accepted = self.plan.get("accepted_artifact_manifest")
            if accepted:
                verify_artifacts(accepted["path"], accepted["sha256"], tree)
            # Discover missing prerequisites before a long build, not afterwards.
            with measured(self.timings, "prerequisites"):
                for step in steps:
                    for command in step.get("tools", []):
                        self.tool(command)
            for step in steps:
                name = step["id"]
                dependencies = {key: {"fingerprint": results[key]["fingerprint"], "outputs": results[key]["outputs"]}
                                for key in step.get("depends_on", [])}
                fingerprint = self.fingerprint(step, dependencies)
                cached = self.cache / "evidence" / (fingerprint + ".json")
                reusable = step.get("cacheable", False)
                with measured(self.timings, name):
                    if reusable and cached.exists():
                        try:
                            previous = json.loads(cached.read_text())
                            valid = (previous["passed"] is True and previous["fingerprint"] == fingerprint
                                     and output_hashes(previous["outputs"]) == previous["outputs"]
                                     and digest(previous["log"]) == previous["log_sha256"])
                        except (OSError, ValueError, KeyError, TypeError):
                            valid = False
                        if valid:
                            if self.source_tree() != tree or self.fingerprint(step, dependencies) != fingerprint:
                                raise ValueError("Preparation inputs changed while reusing evidence")
                            self.validate_plan()
                            results[name] = {**previous, "reused": True}
                            continue
                    log = self.run_root / (name + ".log")
                    self.materialize(step.get("materialize_source_outputs", []), results)
                    with log.open("wb") as output:
                        completed = subprocess.run(step["command"], cwd=self.source, env=self.environment,
                                                   stdout=output, stderr=subprocess.STDOUT,
                                                   timeout=step.get("timeout_seconds", 1800))
                    if completed.returncode:
                        raise RuntimeError("Preparation step failed: " + name + " (see " + str(log) + ")")
                    if self.source_tree() != tree:
                        raise ValueError("Preparation changed candidate source; invalidate evidence")
                    if self.fingerprint(step, dependencies) != fingerprint:
                        raise ValueError("Preparation inputs changed while the check was running")
                    self.validate_plan()
                    outputs, artifact_roots = self.artifacts(step)
                    stored_log = self.cache / "logs" / (uuid.uuid4().hex + ".log")
                    stored_log.parent.mkdir(exist_ok=True)
                    shutil.copy2(log, stored_log)
                    result = {"passed": True, "fingerprint": fingerprint, "reused": False,
                              "outputs": outputs, "artifact_roots": artifact_roots,
                              "log": str(stored_log), "log_sha256": digest(stored_log)}
                    results[name] = result
                    if reusable:
                        save(cached, result)
            if accepted:
                verify_artifacts(accepted["path"], accepted["sha256"], tree)
            passed = True
        finally:
            report = {"schema": 1, "passed": passed, "source_tree": tree, "steps": results,
                      "accepted_artifact_manifest": self.plan.get("accepted_artifact_manifest"),
                      "timings": self.timings, "total_preparation_seconds": time.monotonic() - started,
                      "elapsed_since_preparation_started_seconds": time.time() - json.loads(clock.read_text())["started_at"],
                      "runner_service_actions": [], "cutover_authorized": False,
                      "functional_readiness": "Separate release QA, backups and volatile preflight remain required"}
            save(self.run_root / "result.json", report)
            save(self.root / "latest-result.json", report)
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    start = commands.add_parser("start")
    start.add_argument("--root", required=True, type=Path)
    start.add_argument("--fix-ready-at", help="Actual timezone-qualified fix-ready time, before build/validation")
    init = commands.add_parser("init")
    init.add_argument("--source", required=True, type=Path)
    init.add_argument("--root", required=True, type=Path)
    init.add_argument("--deployed", required=True)
    run = commands.add_parser("run")
    run.add_argument("--source", required=True, type=Path)
    run.add_argument("--root", required=True, type=Path)
    run.add_argument("--plan", required=True, type=Path)
    kind = commands.add_parser("classify")
    kind.add_argument("--source", required=True, type=Path)
    kind.add_argument("--deployed", required=True)
    queues = commands.add_parser("queues")
    queues.add_argument("--origin", required=True)
    queues.add_argument("--database", required=True, type=Path)
    queues.add_argument("--workers", type=int, default=4)
    queues.add_argument("--out", required=True, type=Path)
    finish = commands.add_parser("finish")
    finish.add_argument("--root", required=True, type=Path)
    finish.add_argument("--publication-receipt", required=True, type=Path)
    finish.add_argument("--publication-receipt-sha256", required=True)
    verify = commands.add_parser("verify-artifacts")
    verify.add_argument("--manifest", required=True, type=Path)
    verify.add_argument("--manifest-sha256", required=True)
    verify.add_argument("--source-tree", required=True)
    args = parser.parse_args()
    os.umask(0o077)
    if args.action == "start":
        clock = storage(args.root) / "preparation-clock.json"
        if clock.exists():
            raise ValueError("Existing preparation clock must not be reset")
        now = time.time()
        result = {"started_at": now, "basis": "preparation-started", "cutover_authorized": False}
        if args.fix_ready_at:
            fixed = datetime.datetime.fromisoformat(args.fix_ready_at)
            if fixed.tzinfo is None or fixed.timestamp() > now:
                raise ValueError("Fix-ready time must include timezone and cannot be in the future")
            result.update(started_at=fixed.timestamp(), basis="fix-ready")
        save(clock, result)
    elif args.action == "init":
        clean_tree(args.source)
        result = default_plan(args.source, args.root, args.deployed)
        target = storage(args.root) / "plan.json"
        if target.exists():
            raise ValueError("Existing preparation plan must not be replaced")
        save(target, result)
    elif args.action == "run":
        result = Preparation(args.source, args.root, json.loads(args.plan.read_text())).run()
    elif args.action == "classify":
        clean_tree(args.source)
        result = {"deployment_kind": deployment_kind(args.source, args.deployed), "cutover_authorized": False}
    elif args.action == "finish":
        result = record_publication(args.root, args.publication_receipt, args.publication_receipt_sha256)
    elif args.action == "verify-artifacts":
        result = verify_artifacts(args.manifest, args.manifest_sha256, args.source_tree)
    else:
        result = pending_sessions(args.origin, database_sessions(args.database), args.workers)
        save(storage(args.out), result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
