#!/usr/bin/env python3
"""Read live GitHub settings and compare with the proposal. Never write settings."""
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def validate(protection, workflow_permissions, expected):
    errors = []
    status = protection.get("required_status_checks") or {}
    if status.get("strict") is not True:
        errors.append("strict current-base checks are not enforced")
    checks = {(x.get("context"), x.get("app_id")) for x in status.get("checks", [])}
    for item in expected["required_status_checks"]["checks"]:
        if (item["context"], item["app_id"]) not in checks:
            errors.append("missing required GitHub Actions check: " + item["context"])
    if protection.get("enforce_admins", {}).get("enabled") is not True:
        errors.append("administrators can bypass protection")
    review = protection.get("required_pull_request_reviews") or {}
    for key in ("dismiss_stale_reviews", "require_code_owner_reviews", "require_last_push_approval"):
        if review.get(key) is not True:
            errors.append("review rule absent: " + key)
    if review.get("required_approving_review_count", 0) < 1:
        errors.append("an independent approving review is required")
    if any(review.get("bypass_pull_request_allowances", {}).values()):
        errors.append("PR review bypass allowances are present")
    for key in ("allow_force_pushes", "allow_deletions"):
        if protection.get(key, {}).get("enabled") is not False:
            errors.append(key + " must be disabled")
    if protection.get("required_conversation_resolution", {}).get("enabled") is not True:
        errors.append("conversation resolution is not required")
    if workflow_permissions != {"default_workflow_permissions": "read", "can_approve_pull_request_reviews": False}:
        errors.append("default Actions token/review permissions differ from proposal")
    return errors


def main():
    def get(path):
        result = subprocess.run(["gh", "api", "repos/artinflight/vibe-kanban/" + path],
                                capture_output=True, text=True)
        if result.returncode:
            # Do not dump private responses or credentials in exception logs.
            raise ValueError("read unavailable: " + path)
        return json.loads(result.stdout)

    expected = json.loads((HERE / "proposed-branch-protection.json").read_text())
    permissions = get("actions/permissions/workflow")
    report = {}
    for branch in ("main", "staging"):
        try:
            protection = get(f"branches/{branch}/protection")
            report[branch] = validate(protection, permissions, expected)
        except ValueError as error:
            report[branch] = [str(error)]
    print(json.dumps({"prepared_only": True, "gaps": report}, indent=2))
    return 1 if any(report.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
