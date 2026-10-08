"""Small retained kernel probe; no backend, manager action, credential or network request."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from vk_candidate_generation import Layout, bind_reviewed_namespace, inventory, require

FILES = ("fixture_isolation.py", "fixture_publication.py", "fixture_manager.py",
         "fixture_manager_worker.py", "fixture_manager_client.py")


def run(boundary, expected_sha256):
    require(os.path.ismount("/mnt/vk-storage"), "secondary SSD must be mounted")
    boundary = Path(boundary).resolve(strict=True)
    hashes = {name: hashlib.sha256((boundary / name).read_bytes()).hexdigest() for name in FILES}
    require(hashes["fixture_isolation.py"] == expected_sha256, "reviewed boundary pin differs")
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(boundary))
    import fixture_isolation

    parent = Path("/mnt/vk-storage/vk-safe-release-20261008")
    root = Path(tempfile.mkdtemp(prefix="candidate-cross-prefix-kernel-", dir=parent))
    protected = root / "protected"
    protected.mkdir()
    (protected / "sentinel").write_bytes(b"untouched private canary")
    task = root / "candidate"
    task.mkdir()
    tree = task / "tree"
    (tree / "home/mcp/code").mkdir(parents=True)
    (tree / "mnt/vk-storage/worktrees").mkdir(parents=True)
    (tree / "home/mcp/code/worktrees").symlink_to("/mnt/vk-storage/worktrees")
    (tree / "runtime").mkdir()
    fixture_isolation.private_tmp(tree).mkdir()
    layout = Layout(task, tree, task / "evidence", (protected,))
    child = r'''from pathlib import Path
import errno,json,os,socket
target=Path('/home/mcp/code/worktrees/private-canary')
target.write_bytes(b'candidate generation')
assert target.resolve()==Path('/mnt/vk-storage/worktrees/private-canary')
try: Path(os.environ['PROBE_SENTINEL']).write_bytes(b'forbidden')
except OSError as e: denied=e.errno
else: raise RuntimeError('protected host path was writable')
assert denied in (errno.EROFS,errno.EACCES,errno.ENOENT)
try:
 with socket.socket(socket.AF_UNIX) as sock: sock.connect('/run/user/'+str(os.getuid())+'/systemd/private')
except OSError: manager_denied=True
else: raise RuntimeError('host manager endpoint accessible')
print(json.dumps({'crossPrefixLinkResolved':True,'outsideWriteDenied':denied,'hostManagerHidden':manager_denied}))
'''
    original = inventory(protected)
    argv = fixture_isolation.command(tree, ["/usr/bin/python3", "-B", "-c", child], worker=True, cwd="/usr")
    plan = bind_reviewed_namespace(layout, argv, ["/home/mcp", "/mnt/vk-storage"],
                                  {"WORKSPACES": "/home/mcp/code/worktrees"})
    env = fixture_isolation.environment(tree)
    env["PROBE_SENTINEL"] = str(protected / "sentinel")
    result = subprocess.run(plan["argv"], env=env, capture_output=True, text=True, timeout=20)
    require(hashes == {name: hashlib.sha256((boundary / name).read_bytes()).hexdigest() for name in FILES},
            "boundary changed during probe")
    receipt = {"exitCode": result.returncode, "stdout": result.stdout, "stderr": result.stderr,
               "root": str(root), "boundaryHashes": hashes,
               "protectedUnchanged": inventory(protected) == original,
               "candidateCanaryPresent": (tree / "mnt/vk-storage/worktrees/private-canary").read_bytes()
                   == b"candidate generation" if result.returncode == 0 else False,
               "productionModified": False, "operationalAcceptance": False,
               "limitations": "No real VK/CU/native worker/controller, consent, scanner or whole-state restore acceptance."}
    (root / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))
    require(result.returncode == 0 and receipt["protectedUnchanged"] and receipt["candidateCanaryPresent"],
            "kernel probe failed; no alternative route is attempted")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boundary-dir", required=True)
    parser.add_argument("--expected-boundary-sha256", required=True)
    args = parser.parse_args()
    run(args.boundary_dir, args.expected_boundary_sha256)
