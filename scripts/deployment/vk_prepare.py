#!/usr/bin/env python3
"""Repeatable pre-cutover preparation; never authorizes or performs a cutover."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
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
    python = ["python3", "--version"]
    node = [["node", "--version"], ["pnpm", "--version"]]
    rust = [["cargo", "--version"], ["rustc", "-vV"]]
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
    if kind == "backend-cutover":
        steps.extend([
            {"id": "release-build", "command": ["cargo", "build", "--release", "-j", "3", "-p", "server", "-p", "capacity-guard",
                                                   "--bin", "server", "--bin", "vk-capacity-guard"],
             "outputs": ["/mnt/vk-storage/cargo-target/release/server", "/mnt/vk-storage/cargo-target/release/vk-capacity-guard"],
             "tools": rust, "inputs": inputs, "context_files": context, "cacheable": True,
             "depends_on": ["frontend-build"], "materialize_source_outputs": ["frontend-build"]},
            {"id": "non-tauri-tests", "command": ["cargo", "test", "--workspace", "--exclude", "vibe-kanban-tauri", "-j", "3", "--offline"],
             "tools": rust, "inputs": inputs, "context_files": context, "cacheable": True},
        ])
    return {"schema": 1, "deployment_kind": kind, "cache_directory": "/mnt/vk-storage/vk-preparation-cache",
            "environment": {"CARGO_TARGET_DIR": "/mnt/vk-storage/cargo-target", "CARGO_INCREMENTAL": "0",
                            "SQLX_OFFLINE": "true", "NODE_OPTIONS": "--max-old-space-size=8192",
                            "PYTHONDONTWRITEBYTECODE": "1"},
            "steps": steps, "excluded_validation": ["Tauri/remote aggregate suites are not represented by this local-web/backend recipe"],
            "remaining_gates": ["Issue reconciliation and release-specific functional QA", "Exact runtime/account/home and fresh model proof",
                                "Latest-data backup and restore verification", "Fresh active/queued work and writer inventory",
                                "Installed capacity configuration, ownership/cutback rehearsal and explicit cutover approval"]}


def read_only_queues(origin, sessions, workers=8, timeout=10):
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
    with ThreadPoolExecutor(max_workers=workers) as pool:
        queued = [row for row in pool.map(fetch, sessions) if row is not None]
    return {"checked": len(sessions), "queued": queued, "workers": workers,
            "seconds": time.monotonic() - started, "fresh": True}


def database_sessions(database):
    with sqlite3.connect(Path(database).resolve().as_uri() + "?mode=ro", uri=True) as db:
        return [str(uuid.UUID(bytes=row[0])) for row in db.execute("SELECT id FROM sessions")]


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
        source = git(self.source, "ls-tree", "-r", "HEAD", "--", *step.get("inputs", ["."])).decode()
        files = {}
        for raw in step.get("context_files", []):
            path = Path(raw)
            path = path if path.is_absolute() else self.source / path
            key = "source:" + str(path.relative_to(self.source)) if path.is_relative_to(self.source) else str(path)
            files[key] = digest(path) if path.exists() else None
        return identity({"schema": 1, "source": source, "step": step, "dependencies": dependencies,
                         "environment": self.environment, "tools": tools, "context_files": files,
                         "runner_sha256": digest(__file__),
                         "helpers_sha256": digest(Path(__file__).with_name("vk_prep_common.py"))})

    def run(self):
        with (self.cache / ".preparation.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            return self.run_locked()

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
        tree = clean_tree(self.source)
        clock = self.root / "preparation-clock.json"
        if not clock.exists():
            save(clock, {"started_at": time.time()})
        steps = self.plan.get("steps", [])
        names = [step["id"] for step in steps]
        if len(set(names)) != len(names) or any(not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name) for name in names):
            raise ValueError("Preparation step IDs must be unique safe names")
        results = {}
        passed = False
        try:
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
                        previous = json.loads(cached.read_text())
                        try:
                            valid = (previous["passed"] is True and previous["fingerprint"] == fingerprint
                                     and output_hashes(previous["outputs"]) == previous["outputs"]
                                     and digest(previous["log"]) == previous["log_sha256"])
                        except (OSError, ValueError, KeyError):
                            valid = False
                        if valid:
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
                    if clean_tree(self.source) != tree:
                        raise ValueError("Preparation changed candidate source; invalidate evidence")
                    if self.fingerprint(step, dependencies) != fingerprint:
                        raise ValueError("Preparation inputs changed while the check was running")
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
            passed = True
        finally:
            report = {"schema": 1, "passed": passed, "source_tree": tree, "steps": results,
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
    queues.add_argument("--workers", type=int, default=8)
    queues.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    if args.action == "start":
        clock = storage(args.root) / "preparation-clock.json"
        if clock.exists():
            raise ValueError("Existing preparation clock must not be reset")
        result = {"started_at": time.time(), "cutover_authorized": False}
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
    else:
        result = read_only_queues(args.origin, database_sessions(args.database), args.workers)
        save(storage(args.out), result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
