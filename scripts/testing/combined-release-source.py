"""Fence the candidate to the deployed source plus the two reviewed fixes."""
import hashlib
import json
from pathlib import Path
import subprocess

BASE = "5ce84ee21be814b1519cfb2715b50f3432c3e8ba"
BACKEND = "c3c48e6324f778ccd03a5761c2314b440e9ceac3"
REVIEWED = {
    "capture": "6e27580a4f38975f40326ba773e7f82a27384be6",
    "consent": "b5e49f393a419a03631cf71ddca74d52e08b9cdc",
}


def git(*args):
    return subprocess.check_output(["git", *args])


def blob(ref, path):
    return git("show", f"{ref}:{path}")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify():
    approved = {}
    for ref in REVIEWED.values():
        names = git("diff", "--name-only", BACKEND, ref).decode().splitlines()
        for name in names:
            if name.startswith(("crates/", "packages/", "scripts/testing/")):
                assert name not in approved, f"Overlapping reviewed changes: {name}"
                approved[name] = ref
    assert len(approved) == 21
    extra = {
        ".github/workflows/test.yml", "HANDOFF.md", "STREAM.md",
        "handoffs/e3e1-combined-capture-consent.md",
        "VK_COMBINED_CAPTURE_CONSENT_20261010.md",
        "scripts/testing/combined-release-source.py",
        "scripts/build-combined-capture-consent.py",
        "crates/server/tests/fixtures/c3_strict_log_reader.rs",
    }
    changed = set(git("diff", "--name-only", BASE, "HEAD").decode().splitlines())
    changed.update(git("diff", "--name-only", "HEAD").decode().splitlines())
    assert changed <= set(approved) | extra, f"Unapproved changes: {changed - set(approved) - extra}"
    for name, ref in approved.items():
        actual, expected = Path(name).read_bytes(), blob(ref, name)
        if name == "crates/server/tests/report_review_integration.rs":
            assert actual.startswith(expected.rstrip()), "Existing writer acceptance was changed"
        else:
            assert actual == expected, f"Reviewed implementation changed: {name}"
    overlay = git("diff", "--name-only", BACKEND, BASE).decode().splitlines()
    live_code = [name for name in overlay if name.startswith(("packages/", "scripts/"))]
    for name in live_code:
        assert Path(name).read_bytes() == blob(BASE, name), f"Live-only source changed: {name}"
    # Keep the actual old reader function as a compiled, exact rollback fixture.
    reader = blob(BACKEND, "crates/utils/src/execution_logs.rs")
    reader = reader[reader.index(b"pub async fn read_execution_log_strict("):]
    assert Path("crates/server/tests/fixtures/c3_strict_log_reader.rs").read_bytes().endswith(reader)
    # No schema, permissions, routing, connector or dependency lock changes.
    for name in ("Cargo.toml", "Cargo.lock", "pnpm-lock.yaml", "shared/types.ts"):
        assert Path(name).read_bytes() == blob(BASE, name), name
    return {
        "sourceCommit": git("rev-parse", "HEAD").decode().strip(),
        "sourceTree": git("rev-parse", "HEAD^{tree}").decode().strip(),
        "base": BASE, "incumbentBackend": BACKEND, "reviewed": REVIEWED,
        "approvedFiles": sorted(approved),
        "preservedLiveFiles": {name: digest(blob(BASE, name)) for name in live_code},
        "incumbentStrictReaderFunctionSha256": digest(reader),
    }


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2, sort_keys=True))
