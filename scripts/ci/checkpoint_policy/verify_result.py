#!/usr/bin/env python3
"""Read-only final gate. A skipped test is never a passing test."""
import json
import os
from pathlib import Path
import re
import urllib.request


def verify(event, current, base, merge, results, expected, sha, repository):
    pr = event["pull_request"]
    if repository != "artinflight/vibe-kanban":
        raise ValueError("policy is scoped to artinflight/vibe-kanban")
    if current.get("state") != "open" or current.get("draft") is not False:
        raise ValueError("final validation requires an open, ready PR")
    if pr.get("draft") is not False:
        raise ValueError("draft checkpoints have no merge approval")
    if current["base"]["repo"]["full_name"] != repository:
        raise ValueError("wrong base repository")
    branch = current["base"]["ref"]
    if branch not in ("main", "staging") or branch != pr["base"]["ref"]:
        raise ValueError("base branch changed or unsupported")
    head = current["head"]["sha"]
    base_sha = base["commit"]["sha"]
    if head != pr["head"]["sha"] or base_sha != pr["base"]["sha"]:
        raise ValueError("source or base changed: run fresh validation")
    if current["base"]["sha"] != base_sha:
        raise ValueError("PR base readback is stale")
    if current.get("merge_commit_sha") != sha or merge["sha"] != sha:
        raise ValueError("tests are not bound to the current test merge commit")
    if [p["sha"] for p in merge["parents"]] != [base_sha, head]:
        raise ValueError("test merge parents do not match current base and source")
    if not expected or set(results) != set(expected):
        raise ValueError("missing or unexpected required test jobs")
    for name in expected:
        if results[name].get("result") != "success":
            raise ValueError(f"{name}: real tests did not succeed")
    return {"repository": repository, "pr": event["number"], "head": head,
            "base": base_sha, "tested_merge": sha, "jobs": expected}


def main():
    if os.environ.get("GITHUB_EVENT_NAME") != "pull_request":
        raise ValueError("only PR test merges can satisfy the merge gate")
    repository = os.environ["GITHUB_REPOSITORY"]
    sha = os.environ["GITHUB_SHA"]
    if repository != "artinflight/vibe-kanban" or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("invalid repository or tested commit")
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())

    def get(path):
        request = urllib.request.Request(
            f"https://api.github.com/repos/{repository}/{path}",
            headers={"Authorization": "Bearer " + os.environ["GH_TOKEN"],
                     "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28"},
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.load(response)

    current = get(f"pulls/{int(event['number'])}")
    branch = current["base"]["ref"]
    if branch not in ("main", "staging"):
        raise ValueError("unsupported base branch")
    base = get(f"branches/{branch}")
    merge = get(f"git/commits/{sha}")
    receipt = verify(event, current, base, merge,
                     json.loads(os.environ["VK_CI_RESULTS"]),
                     json.loads(os.environ["VK_CI_REQUIRED_JOBS"]), sha, repository)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
