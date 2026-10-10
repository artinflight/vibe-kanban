"""Build an immutable paired artifact on a disposable hosted runner. No deployment."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess


def capture(*args):
    return subprocess.check_output(args, text=True).strip()


def sha(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


repo = Path(capture("git", "rev-parse", "--show-toplevel")).resolve()
source = capture("git", "rev-parse", "HEAD")
assert source == os.environ["VK_EXPECTED_SOURCE"], "Source mismatch"
assert not capture("git", "status", "--porcelain", "--untracked-files=no"), "Dirty tracked source"
assert not (repo / ".env").exists(), "Never import a builder .env"
output = Path(os.environ["VK_ARTIFACT_DIR"]).resolve()
target = Path(os.environ["CARGO_TARGET_DIR"]).resolve()
assert not output.is_relative_to(repo) and not target.is_relative_to(repo)
assert not output.exists(), "Use a fresh immutable artifact destination"
spec = importlib.util.spec_from_file_location("fence", repo / "scripts/testing/combined-release-source.py")
fence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fence)
binding = fence.verify()
output.mkdir(parents=True)
env = {**os.environ, "VK_BUILD_SOURCE_COMMIT": source, "CARGO_INCREMENTAL": "0"}
# Build before frontend: retain the incumbent external-frontend/placeholder
# server packaging. Never start the application or open a database.
commands = [["cargo", "build", "--locked", "--profile", "acceptance", "-p", "server", "--bin", "server"],
            ["pnpm", "--filter", "@vibe/local-web", "run", "build"]]
subprocess.run(commands[0], env=env, check=True)
server = target / "acceptance/server"
build_info = json.loads(capture(str(server), "--capacity-build-info"))
assert build_info["sourceCommit"] == source
for key in ("automaticWorkspaceDeletion", "automaticAttachmentMigration", "automaticAttachmentCleanup"):
    assert build_info[key] is False, key
assert build_info["capacityWireVersion"] == 1
assert build_info["runtimeIdentityVersion"] == 1
assert build_info["initializationCompiled"] is True
subprocess.run(commands[1], env=env, check=True)
shutil.copy2(server, output / "server")
shutil.copytree(repo / "packages/local-web/dist", output / "frontend")
files = {str(path.relative_to(output)): {"sha256": sha(path), "bytes": path.stat().st_size}
         for path in sorted(output.rglob("*")) if path.is_file()}
frontend = {name.removeprefix("frontend/"): info for name, info in files.items() if name.startswith("frontend/")}
tree_sha = hashlib.sha256(json.dumps(frontend, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
manifest = {**binding, "files": files, "frontendTreeSha256": tree_sha,
            "buildInfo": build_info, "commands": commands, "platform": platform.platform(),
            "rustc": capture("rustc", "--version"), "cargo": capture("cargo", "--version"),
            "node": capture("node", "--version"), "profile": "acceptance",
            "runId": os.environ["GITHUB_RUN_ID"], "runAttempt": os.environ["GITHUB_RUN_ATTEMPT"],
            "deploymentPerformed": False,
            "unchangedSupportArtifacts": "Reuse incumbent capacity guard, routing module/scanner, wrapper, runtime identity/config and data. No replacements supplied."}
(output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
print(json.dumps({"sourceCommit": source, "server": files["server"], "frontendTreeSha256": tree_sha,
                  "manifestSha256": sha(output / "manifest.json")}, indent=2))
