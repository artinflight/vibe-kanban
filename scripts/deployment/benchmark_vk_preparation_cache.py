#!/usr/bin/env python3
"""Disposable offline cache benchmark; no Cargo, backup or service operations."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import uuid

from vk_prep_common import save, storage
from vk_prepare import Preparation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    root = storage(args.root) / ("cache-fixture-" + uuid.uuid4().hex)
    source = root / "source"
    source.mkdir(parents=True)

    def git(*arguments):
        subprocess.run(["git", "-C", str(source), *arguments], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    git("init", "-q")
    git("config", "user.name", "Preparation benchmark")
    git("config", "user.email", "fixture@example.invalid")
    (source / "behavior.txt").write_text("original")
    git("add", ".")
    git("commit", "-qm", "fixture")
    artifact = root / "server-fixture"
    counter = root / "build-calls"
    fresh = root / "fresh-calls"
    build = (
        "from pathlib import Path; import time; time.sleep(.30); "
        f"p=Path({str(counter)!r}); p.write_text(str(int(p.read_text())+1) if p.exists() else '1'); "
        f"Path({str(artifact)!r}).write_text(Path('behavior.txt').read_text())"
    )
    observe = (
        "from pathlib import Path; "
        f"p=Path({str(fresh)!r}); p.write_text(str(int(p.read_text())+1) if p.exists() else '1')"
    )
    plan = {"steps": [
        {"id": "build", "command": [sys.executable, "-c", build],
         "outputs": [str(artifact)], "tools": [[sys.executable, "--version"]], "cacheable": True},
        {"id": "acceptance", "command": [sys.executable, "-c", "import time; time.sleep(.15)"],
         "depends_on": ["build"], "cacheable": True},
        {"id": "fresh", "command": [sys.executable, "-c", observe],
         "volatile": True, "cacheable": False},
    ]}

    def run():
        return Preparation(source, root / "preparation", plan).run()

    initial = run()
    reused = run()
    git("commit", "--allow-empty", "-qm", "metadata-only checkpoint")
    metadata_only = run()
    (source / "behavior.txt").write_text("changed")
    git("add", ".")
    git("commit", "-qm", "changed behavior")
    changed = run()
    passed = (
        not initial["steps"]["build"]["reused"]
        and reused["steps"]["build"]["reused"]
        and reused["steps"]["acceptance"]["reused"]
        and metadata_only["steps"]["build"]["reused"]
        and not changed["steps"]["build"]["reused"]
        and not changed["steps"]["acceptance"]["reused"]
        and counter.read_text() == "2" and fresh.read_text() == "4"
        and artifact.read_text() == "changed"
    )
    report = {
        "passed": passed, "fixture_only": True, "compiler_invoked": False,
        "production_changed": False, "backup_operations": 0,
        "initial_seconds": initial["total_preparation_seconds"],
        "unchanged_seconds": reused["total_preparation_seconds"],
        "metadata_only_seconds": metadata_only["total_preparation_seconds"],
        "changed_seconds": changed["total_preparation_seconds"],
        "immutable_build_executions": int(counter.read_text()),
        "fresh_check_executions": int(fresh.read_text()),
        "unchanged_speedup": initial["total_preparation_seconds"] / reused["total_preparation_seconds"],
        "real_release_ten_minute_target_proven": False,
        "details": str(root),
    }
    save(storage(args.root) / "CACHE_BENCHMARK.safe.json", report)
    print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
