"""Export ONLY a compiled test verifier; no server, credentials or private inputs."""
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
            and entry.get("target", {}).get("name") == "server"
            and entry.get("target", {}).get("kind") == ["lib"]
            and entry.get("profile", {}).get("test")
            and entry.get("executable")):
        executables.add(entry["executable"])
assert len(executables) == 1, "Expected exactly one compiled server-library test executable"
out = Path(os.environ["VK_VERIFY_ARTIFACT"])
out.mkdir(parents=True, exist_ok=False)
binary = out / "native-recovery-verifier"
shutil.copyfile(executables.pop(), binary)
binary.chmod(0o755)
manifest = {"source": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
            "bytes": binary.stat().st_size,
            "test": "routes::execution_processes::historical_response::tests::verify_actual_native_sources_read_only",
            "run": "--exact TEST --ignored --nocapture --test-threads=1",
            "scope": "Two exact incident executions; read-only native/capture integrity. No server or DB writes."}
(out / "manifest.safe.json").write_text(json.dumps(manifest, indent=2) + "\n")
