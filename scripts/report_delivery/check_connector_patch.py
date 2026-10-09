"""Check a one-file connector patch; test only a disposable SSD copy.

This never installs code, changes a service, or writes to the supplied source.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(source):
    binding = json.loads((ROOT / "connector-patch/binding.json").read_text())
    artifact = ROOT / "connector-patch/prepared-intent.patch"
    if sha(artifact) != binding["patch_sha256"]:
        raise ValueError("Patch artifact hash changed")
    if sha(source / "report_reconciliation.py") != binding["base_file_sha256"]:
        raise ValueError("Connector receipt source differs from reviewed base; owner reconciliation required")
    subprocess.run(["git", "apply", "--check", str(artifact)], cwd=source, check=True)
    return binding


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    source = args.source.resolve()
    binding = check(source)
    if args.test:
        if not os.path.ismount("/mnt/vk-storage"):
            raise ValueError("Mounted /mnt/vk-storage required for disposable fixtures")
        staging = Path("/mnt/vk-storage/vk-unread-integration-20261009")
        staging.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="patch-acceptance-", dir=staging) as folder:
            candidate = Path(folder)
            # Explicit code/test inputs only: no runtime keys, ledgers, native
            # logs, environment files, tunnel binaries or existing runs copied.
            inputs = [*source.glob("*.py"), *source.glob("*.mjs"),
                      source / "backend/report_review.rs",
                      source / "backend/20261007190000_workspace_report_receipts.sql"]
            for path in inputs:
                target = candidate / path.relative_to(source)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
            subprocess.run(["git", "apply", str(ROOT / "connector-patch/prepared-intent.patch")],
                           cwd=candidate, check=True)
            if sha(candidate / "report_reconciliation.py") != binding["candidate_file_sha256"]:
                raise ValueError("Applied candidate hash mismatch")
            env = dict(os.environ, TMPDIR=str(candidate), VK_CONNECTOR_SOURCE=str(candidate))
            subprocess.run([sys.executable, "-m", "unittest", "discover", "-v"],
                           cwd=candidate, env=env, check=True)
            subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(ROOT), "-v"],
                           cwd=ROOT, env=env, check=True)
    print(json.dumps({"patch_checked": True, "source_unchanged": True,
                      "file": "report_reconciliation.py", "tests_run": args.test,
                      "source": str(source)}))


if __name__ == "__main__":
    main()
