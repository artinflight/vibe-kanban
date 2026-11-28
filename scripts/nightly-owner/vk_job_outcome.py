"""Small presentation receipts for Preparation jobs; never approval or delivery proof."""

import json
from pathlib import Path

from vk_prep_common import digest, save

MAX_OUTCOME_BYTES = 8192


def outcome(run_root, state, *, report=None, phase=None, error_type=None):
    run_root = Path(run_root)
    if state not in ("running", "blocked", "failed", "completed"):
        raise ValueError("Unknown job outcome state")
    if state in ("failed", "completed") and report is None:
        raise ValueError("Terminal job outcome requires its full result")
    value = {"schema": 1, "kind": "preparation-outcome", "job_id": run_root.name,
             "state": state, "passed": state == "completed", "scope": "preparation-only",
             "cutover_authorized": False, "task_completion": "not_inferred",
             "delivery": "not_attested", "qa": "separate_required"}
    if report is not None:
        path = run_root / "result.json"
        # Full evidence stays in the existing run-specific report. Never bind the
        # mutable latest-result alias or infer a pass from a previous job's file.
        if report["passed"] is not (state == "completed"):
            raise ValueError("Compact outcome disagrees with full result")
        value.update(result={"path": str(path), "bytes": path.stat().st_size, "sha256": digest(path)},
                     source_tree=report["source_tree"],
                     steps={"completed": len(report["steps"]),
                            "reused": sum(row["reused"] is True for row in report["steps"].values())})
    if phase:
        value["phase"] = phase[:256]
    if error_type:
        # No raw exception/command text: those may contain private arguments.
        value["error_type"] = error_type
    value["next_action"] = {
        "running": "Wait for this job's terminal outcome; do not launch a duplicate.",
        "blocked": "Existing cache owner must finish; do not duplicate or clear its lease.",
        "failed": "Inspect this job's bound result and phase log; correct the cause before retry.",
        "completed": "Reuse verified static evidence; current data/owner/QA gates remain required."
    }[state]
    if len(json.dumps(value, indent=2).encode()) > MAX_OUTCOME_BYTES:
        raise ValueError("Compact job outcome exceeds bounded presentation size")
    save(run_root / "outcome.json", value)
    return value
