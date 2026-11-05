"""Export a source-bound read-only test verifier; never private acceptance data."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

executables = set()
for line in Path(sys.argv[1]).read_text().splitlines():
    entry = json.loads(line)
    if (entry.get("reason") == "compiler-artifact"
            and entry.get("target", {}).get("name") == "services"
            and entry.get("target", {}).get("kind") == ["lib"]
            and entry.get("profile", {}).get("test")
            and entry.get("executable")):
        executables.add(entry["executable"])
assert len(executables) == 1, "Expected one compiled services test executable"
out = Path(os.environ["VK_VERIFY_ARTIFACT"])
out.mkdir(parents=True, exist_ok=False)
binary = out / "history-verifier"
shutil.copyfile(executables.pop(), binary)
binary.chmod(0o755)
with binary.open("rb") as stream:
    sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
manifest = {
    "source": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    "sha256": sha256,
    "bytes": binary.stat().st_size,
    "test": "services::original_worker::inputs::streaming_tests::verify_private_history_read_only",
    "run": "--exact TEST --ignored --nocapture --test-threads=1",
    "request_environment": "VK_HISTORY_ACCEPTANCE_REQUEST",
    "scope": "Read-only indexed native input verification. No VK database, grants, dispatch or server startup.",
}
(out / "manifest.safe.json").write_text(json.dumps(manifest, indent=2) + "\n")
