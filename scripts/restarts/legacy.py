"""Read-only adapter for an explicitly selected controller receipt directory.

No controller imports, shell commands, history scans, or access to its databases.
An explicitly selected attempt prevents unrelated/old receipts becoming current.
"""

import re
from pathlib import Path

from progress import read_json

PLAN = [
    ("backup", "Back up current state"),
    ("restore", "Verify the backup by restoring"),
    ("checks", "Bind release and safety checks"),
    ("quiet", "Wait for active work to finish"),
    ("capture", "Capture the final changes"),
    ("start", "Start the prepared Vibe release"),
    ("verify", "Verify Vibe through HTTPS"),
]
PLANNING = {
    "backup": (300, 1800, "Assume normal backup transfer and verification without retry."),
    "restore": (300, 1800, "Assume normal restore throughput without retry; replace this allowance when counters arrive."),
    "checks": (60, 300, "Assume prepared artifacts and safety checks pass without remediation."),
    "quiet": (300, 1800, "Assume active/queued work clears in 5–30 min and no new work arrives. "
              "No completion time was observed; this wait can extend indefinitely."),
    "capture": (60, 300, "Assume the final delta is small and backup delivery succeeds."),
    "start": (30, 180, "Assume the prepared release starts normally and ownership checks pass."),
    "verify": (60, 300, "Assume HTTPS acceptance passes without recovery."),
}
PHASES = {
    "fresh-Desktop-B-whole-capture-online-no-service-effects": "backup",
    "measured-Desktop-B-restore-online-no-service-effects": "restore",
    "waiting-for-natural-quiet-no-interruption": "quiet",
    "fenced-latest-data-backup": "capture",
    "candidate-direct-acceptance": "start",
    "candidate-trusted-HTTPS-acceptance": "verify",
    "verified-published": "verify",
}
RECOVERY = {
    "failed-or-safely-recovered", "held-current-active-work-not-interrupted",
    "compatible-rollback-serving-latest-data", "incumbent-preserved-before-candidate",
}


def safe_reason(value):
    # Legacy exception strings can contain private filenames. Publish only a
    # bounded summary; the private receipt retains the full diagnostic evidence.
    text = str(value)[:500]
    text = re.sub(r"(?:[A-Za-z]:[\\/]|/)[^\s,'\";]+", "[private path]", text)
    text = re.sub(r"(?i)(token|password|secret|key)\s*[=:]\s*\S+", r"\1=[redacted]", text)
    return text[:240]


class LegacySource:
    def __init__(self, config):
        self.config = config
        self.actor = Path(config["actor_directory"])
        self.backup = Path(config["backup_directory"])

    def snapshot(self):
        times = []

        def load(root, name):
            path = root / name
            try:
                value = read_json(path)
                times.append(path.stat().st_mtime)
                return value
            except FileNotFoundError:
                return {}

        actor = load(self.actor, "actor-state.safe.json")
        if not actor:
            raise ValueError("The selected controller has not published its first update")
        updated = self.actor.joinpath("actor-state.safe.json").stat().st_mtime
        steps = [dict(id=key, label=label, status="pending") for key, label in PLAN]
        for step in steps:
            lo, hi, assumption = PLANNING[step["id"]]
            step["planning_estimate"] = dict(lower_seconds=lo, upper_seconds=hi, assumption=assumption)
            if step["id"] == "quiet":
                step.update(wait_step=True)
                step["planning_estimate"]["recalibrate_on"] = "Controller leaves the natural-idle wait, or reports a blocker/recovery"
        by_id = {s["id"]: s for s in steps}
        phase = actor.get("phase", "unknown")
        current = PHASES.get(phase)
        backup = load(self.backup, "BACKUP_PROGRESS.safe.json")
        restore = load(self.backup, "restore-verification/PROGRESS.safe.json")
        restored = load(self.backup, "RESTORE_REHEARSAL.safe.json")
        ready = load(self.actor, "PREPARATION_READY.safe.json")
        bound = load(self.actor, "bound-release.safe.json")
        final = load(self.actor, "final-primary.safe.json")
        published = load(self.actor, "PUBLICATION_READY.safe.json")
        failure = load(self.actor, "failure.safe.json")
        restore_failure = load(self.backup, "restore-verification/FAILURE.safe.json")
        if backup.get("passed") is True and backup.get("receipt", {}).get("desktop_verified") is True:
            by_id["backup"].update(status="completed", duration_seconds=backup.get("seconds", 0),
                                   detail="Backup delivered and checksum verified.")
        if restored.get("passed") is True and restored.get("compressed_stream_fully_hash_verified") is True:
            by_id["restore"].update(status="completed", duration_seconds=restored.get("seconds", 0),
                                    detail="Restored data and compressed stream verified.")
        if ready.get("passed") is True and bound:
            by_id["checks"]["status"] = "completed"
        if current in {"capture", "start", "verify"}:
            by_id["quiet"]["status"] = "completed"
        if final.get("desktop_verified") is True:
            by_id["capture"]["status"] = "completed"
        if current == "verify":
            by_id["start"]["status"] = "completed"
        if current:
            for step in steps:
                if step["id"] == current and step["status"] != "completed":
                    step["status"] = "running"
        if current == "restore" and restore:
            counts = restore.get("counts", {})
            # The capture records planned paths, snapshots and one manifest.
            # Runtime sockets/deletions can reduce that count: this is explicitly
            # an estimated total, never proof that restoration is complete.
            total = backup.get("files", 0) + backup.get("databases", 0) + 1
            count = counts.get("members", 0)
            observed = self.backup.joinpath("restore-verification/PROGRESS.safe.json").stat().st_mtime
            updated = max(updated, observed)
            by_id["restore"].update(
                metric=dict(done=count, total=total if total > count else None,
                            unit="planned archive entries", observed_at=observed, estimated_total=True,
                            elapsed_seconds=restore.get("seconds", 0)),
                detail=f"{counts.get('restored_databases', 0)} / {backup.get('databases', 0)} databases checked. "
                       "Entry total is approximate; final verification must pass.",
            )
        errors, blockers = [], []
        if phase in RECOVERY or failure or restore_failure or backup.get("phase") == "failed":
            status = "blocked" if phase in RECOVERY else "failed"
            problem = failure or restore_failure or (actor if actor.get("reason") else backup)
            errors.append(dict(message=safe_reason(problem.get("reason") or "The release attempt stopped or entered recovery."),
                               kind=safe_reason(problem.get("error_type", "Controller stopped"))))
            blockers.append("Controller review is required before another attempt.")
            if current is None:
                current = PHASES.get(failure.get("failed_phase"))
            if current:
                by_id[current]["status"] = "blocked"
        elif current == "quiet":
            status = "blocked"
            by_id["quiet"].update(status="blocked", detail="Vibe remains available while current work drains.")
            blockers.append("Waiting for a natural idle boundary. Duration depends on active and queued work.")
        elif current is None:
            status = "blocked"
            blockers.append("Unrecognized controller stage; waiting for a supported update.")
        else:
            status = "running"
        if published and phase == "verified-published" and not failure:
            status, current = "completed", None
            for step in steps:
                step["status"] = "completed"
        return dict(schema=1, run_id=self.config["run_id"], title=self.config.get("title", "Vibe restart"),
                    status=status, current_step=current, started_at=self.config["started_at"],
                    updated_at=max(updated, max(times)), steps=steps, errors=errors, blockers=blockers,
                    controller_phase=phase, source="Restart controller receipts", events=[],
                    stale_after_seconds=300)
