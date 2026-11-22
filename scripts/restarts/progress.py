"""Durable, measured restart progress for controllers running outside Vibe.

Controllers own their steps and report observations; this module never restarts
services. See VK_RESTART_PROGRESS.md for the producer contract.
"""

import contextlib
import fcntl
import json
import math
import os
from pathlib import Path
import tempfile
import time

from estimates import forecast

STATES = {"pending", "running", "completed", "blocked", "failed", "skipped"}
TERMINAL = {"completed", "failed"}


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix=".progress-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def read_json(path):
    with Path(path).open() as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError("Progress must be an object")
    return value


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def validate(value):
    if value.get("schema") != 1 or not isinstance(value.get("run_id"), str):
        raise ValueError("Unknown progress protocol")
    if value.get("status") not in {"idle", "running", "blocked", "failed", "completed"}:
        raise ValueError("Unknown run status")
    if not number(value.get("updated_at")) or not number(value.get("started_at")):
        raise ValueError("Missing observation time")
    if not number(value.get("stale_after_seconds", 30)) or not 0 < value.get("stale_after_seconds", 30) <= 3600:
        raise ValueError("Invalid observation cadence")
    steps = value.get("steps")
    if not isinstance(steps, list) or not steps or len(steps) > 100:
        raise ValueError("A bounded step plan is required")
    ids = set()
    for step in steps:
        if not isinstance(step.get("id"), str) or step["id"] in ids:
            raise ValueError("Duplicate or absent step ID")
        ids.add(step["id"])
        if not isinstance(step.get("label"), str) or step.get("status") not in STATES:
            raise ValueError("Invalid step")
        metric = step.get("metric")
        if metric is not None:
            if not number(metric.get("done")) or not isinstance(metric.get("unit"), str):
                raise ValueError("Invalid measured progress")
            total = metric.get("total")
            if total is not None and (not number(total) or total <= 0 or metric["done"] > total):
                raise ValueError("Invalid measured total")
            for key in ("observed_at", "elapsed_seconds"):
                if key in metric and not number(metric[key]):
                    raise ValueError("Invalid observation time")
        for key in ("duration_seconds", "measured_duration_seconds"):
            if key in step and not number(step[key]):
                raise ValueError("Invalid measured duration")
        prior = step.get("planning_estimate")
        if prior is not None:
            if not isinstance(prior, dict) or not number(prior.get("lower_seconds")) or not number(prior.get("upper_seconds")):
                raise ValueError("Invalid planning range")
            if prior["lower_seconds"] > prior["upper_seconds"] or prior["upper_seconds"] <= 0:
                raise ValueError("Invalid planning range")
            if not isinstance(prior.get("assumption"), str) or not prior["assumption"].strip():
                raise ValueError("A planning estimate needs an assumption")
            if "recalibrate_on" in prior and not isinstance(prior["recalibrate_on"], str):
                raise ValueError("Invalid recalibration checkpoint")
    if value.get("current_step") is not None and value["current_step"] not in ids:
        raise ValueError("Unknown current step")
    if value["status"] == "completed" and any(s["status"] not in {"completed", "skipped"} for s in steps):
        raise ValueError("Success requires every step to finish")
    return value


class Reporter:
    """One controller owns one run; file locking makes concurrent heartbeats safe."""

    def __init__(self, path, run_id):
        self.path, self.run_id = Path(path), run_id

    @contextlib.contextmanager
    def locked(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.path.with_suffix(".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def start(self, title, steps):
        with self.locked():
            if self.path.exists():
                raise ValueError("Use a new progress file for a new attempt")
            now = time.time()
            value = dict(schema=1, run_id=self.run_id, title=title, status="running",
                         started_at=now, updated_at=now, current_step=steps[0]["id"],
                         steps=[dict(s, status="pending") for s in steps], events=[], errors=[], blockers=[])
            atomic_json(self.path, validate(value))

    def update(self, step_id=None, status=None, message=None, metric=None, **fields):
        with self.locked():
            value = validate(read_json(self.path))
            if value["run_id"] != self.run_id or value["status"] in TERMINAL:
                raise ValueError("Run identity changed or attempt is terminal")
            now = time.time()
            if step_id is not None:
                step = next(s for s in value["steps"] if s["id"] == step_id)
                if status is not None:
                    step["status"] = status
                if metric is not None:
                    step["metric"] = dict(metric, observed_at=now)
                if message is not None:
                    step["detail"] = message
                step.update(fields)
                if status in {"running", "blocked", "failed"}:
                    value["current_step"] = step_id
                    step.setdefault("started_at", now)
                if status == "completed" and "started_at" in step:
                    step["duration_seconds"] = now - step["started_at"]
                value["status"] = status if status in {"blocked", "failed"} else "running"
                if status == "failed":
                    value["errors"] = [dict(kind="Controller error", message=message or "Restart step failed.")]
                elif status == "blocked":
                    value["blockers"] = [message or "Restart step is blocked."]
                elif status in {"running", "completed", "skipped"}:
                    value["blockers"] = []
            if message:
                value["events"] = (value["events"] + [dict(at=now, message=message)])[-30:]
            if all(s["status"] in {"completed", "skipped"} for s in value["steps"]):
                value.update(status="completed", current_step=None)
            value["updated_at"] = now
            atomic_json(self.path, validate(value))


class Measurements:
    def __init__(self):
        self.samples = {}

    def project(self, source, now=None):
        value = json.loads(json.dumps(validate(source)))
        now = time.time() if now is None else now
        cadence = value.get("stale_after_seconds", 30)
        fresh = now - value["updated_at"] <= cadence
        value.update(stale=not fresh and value["status"] not in TERMINAL,
                     served_at=now, elapsed_seconds=max(0, now - value["started_at"]))
        done = sum(s["status"] == "completed" for s in value["steps"])
        skipped = sum(s["status"] == "skipped" for s in value["steps"])
        fractions, estimates = [], []
        for step in value["steps"]:
            terminal = step["status"] in {"completed", "skipped"}
            fraction, eta, rate = (1 if terminal else 0), None, None
            metric = step.get("metric")
            if metric and not terminal:
                count, total = metric["done"], metric.get("total")
                observed = metric.get("observed_at", value["updated_at"])
                key = (value["run_id"], step["id"], metric["unit"], total)
                samples = self.samples.setdefault(key, [])
                if samples and (count < samples[-1][1] or observed < samples[-1][0]):
                    samples.clear()
                if not samples or observed > samples[-1][0]:
                    samples.append((observed, count))
                samples[:] = samples[-60:]
                if len(samples) > 1 and observed > samples[0][0]:
                    rate = (count - samples[0][1]) / (observed - samples[0][0])
                elif metric.get("elapsed_seconds", 0) > 0:
                    rate = count / metric["elapsed_seconds"]
                if total:
                    fraction = min(count / total, .999)
                    if rate and rate > 0 and now - observed <= cadence and fresh and step["status"] == "running" and value["status"] == "running":
                        eta = max(0, (total - count) / rate)
            step["percent"] = round(100 * fraction, 1) if terminal or (metric and metric.get("total")) else None
            step["eta_seconds"] = eta
            step["rate_per_second"] = rate if eta is not None else None
            step["observed_rate_per_second"] = rate if rate and rate > 0 else None
            if not terminal:
                estimates.append(eta if step["status"] == "running" else step.get("measured_duration_seconds"))
            fractions.append(fraction)
        percent = round(100 * sum(fractions) / len(fractions), 1)
        if value["status"] != "completed":
            percent = min(percent, 99.9)
        value.update(completed_steps=done, skipped_steps=skipped,
                     remaining_steps=len(value["steps"]) - done - skipped,
                     percent=percent,
                     eta_seconds=(sum(estimates) if all(e is not None for e in estimates)
                                  and fresh and value["status"] in {"running", "completed"} else None))
        value["estimate_policy"] = 1
        value["estimate"] = forecast(value, now)
        return value
