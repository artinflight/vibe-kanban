"""Run compiled VK tests within CU's reviewed kernel/supervisor boundary.

No fixture backend ever runs with host filesystem or host-manager authority.
The boundary directory is supplied explicitly and its complete source hashes
are recorded. This driver does not compile, deploy or change live settings.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

# Import the external reviewed boundary without writing caches beside it.
sys.dont_write_bytecode = True

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--boundary-dir', type=Path, required=True)
binary_source = parser.add_mutually_exclusive_group(required=True)
binary_source.add_argument('--binary', type=Path)
binary_source.add_argument('--binary-stdin', action='store_true',
                           help='Load executable bytes into sealed memory, without bulk disk output')
parser.add_argument('--expected-sha256', help='Required for stdin executable bytes')
parser.add_argument('--guard', type=Path, required=True)
parser.add_argument('--native', action='store_true')
parser.add_argument('--variant', choices=['success', 'input', 'failure', 'race', 'plan', 'empty',
                                        'stalled-revocation', 'stalled-expiry', 'stalled-two'], default='success')
parser.add_argument('test_args', nargs=argparse.REMAINDER)
a = parser.parse_args()
boundary = a.boundary_dir.resolve(strict=True)
files = ['fixture_isolation.py', 'fixture_manager.py', 'fixture_manager_worker.py',
         'fixture_manager_client.py', 'fixture_publication.py']
hashes = {name: hashlib.sha256((boundary/name).read_bytes()).hexdigest() for name in files}
sys.path.insert(0, str(boundary))
from fixture_isolation import provision, prove, command, environment, wrapper, require
from fixture_manager import FixtureManager
from fixture_publication import Publication

require(os.path.ismount('/mnt/vk-storage'), 'SSD must be mounted')
memory_fd = None
if a.binary_stdin:
    require(a.expected_sha256 is not None and len(a.expected_sha256) == 64
            and all(c in '0123456789abcdef' for c in a.expected_sha256), 'Expected SHA-256 required')
    memory_fd = os.memfd_create('vk-verified-acceptance', os.MFD_ALLOW_SEALING)
    digest = hashlib.sha256()
    total = 0
    while chunk := sys.stdin.buffer.read(1024*1024):
        total += len(chunk)
        require(total <= 256*1024*1024, 'Executable exceeds memory transport limit')
        digest.update(chunk)
        remaining = memoryview(chunk)
        while remaining:
            remaining = remaining[os.write(memory_fd, remaining):]
    binary_sha = digest.hexdigest()
    require(total > 0 and binary_sha == a.expected_sha256, 'Executable checksum mismatch')
    fcntl.fcntl(memory_fd, fcntl.F_ADD_SEALS,
                fcntl.F_SEAL_WRITE | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SEAL)
    os.lseek(memory_fd, 0, os.SEEK_SET)
else:
    binary = a.binary.resolve(strict=True)
    binary_sha = hashlib.sha256(binary.read_bytes()).hexdigest()
    require(not a.expected_sha256 or binary_sha == a.expected_sha256, 'Executable checksum mismatch')
guard = a.guard.resolve(strict=True)
base = Path('/mnt/vk-storage/vk-sfr-20261006')
base.mkdir(exist_ok=True)
root, evidence = provision(base, 'vk-continuation-first-run-')
(root/'home').mkdir()
(root/'controller').mkdir()
supervisor = FixtureManager(root, guard)
publication = Publication(root)
try:
    if memory_fd is not None:
        binary = root/'validation-binary'
        publication.write_text('validation-binary', '', mode=0o500)
    proof = prove(root, evidence)
    env = environment(root)
    env.update(CODEX_HOME=str(root/'home'), VK_CAPACITY_SCHEDULED_GOAL_INITIALIZATION='1')
    if a.native:
        isolated_guard = wrapper(root, guard, 'isolated-capacity-guard')
        env.update(VK_SCHEDULED_FIRST_RUN_OFFLINE='1', VK_SCHEDULED_FIRST_RUN_VARIANT=a.variant, VK_CAPACITY_STATE_DIR=str(root/'controller'),
                   VK_CAPACITY_GUARD=str(isolated_guard), VK_USE_SYSTEMD_RUN='1',
                   VK_CAPACITY_MODEL_PROVIDER='fixture', VK_GOAL_TEST_SCENARIO='scheduled-seed',
                   VK_CODEX_BASE_COMMAND='python3 '+str(Path(__file__).resolve().with_name('codex_goal_provider.py')))
    args = a.test_args
    if args and args[0] == '--': args = args[1:]
    argv = [str(binary), *(args or ['--test-threads=1'])]
    print('Isolated evidence: '+str(root), flush=True)
    isolated = command(root, argv, controller=a.native, worker=not a.native)
    if memory_fd is not None:
        # Add only a read-only executable within the existing writable fixture
        # root. All reviewed host-root/socket/PID/network/supervisor restrictions
        # remain byte-for-byte intact; the sealed bytes cannot be altered.
        end = isolated.index('--')
        isolated[end:end] = ['--perms', '0500', '--ro-bind-data', str(memory_fd), str(binary)]
    with publication.open_text('validation.log') as log:
        result = subprocess.run(isolated, env=env, stdout=log, stderr=log, timeout=180,
                                pass_fds=() if memory_fd is None else (memory_fd,))
        log.flush(); log.seek(0); output = log.read()
    require(hashes == {name: hashlib.sha256((boundary/name).read_bytes()).hexdigest() for name in files},
            'Reviewed boundary changed while tests ran')
    publication.write_text('result.json', json.dumps(dict(exitCode=result.returncode,
        command=argv, binarySha256=binary_sha, sealedMemoryTransport=memory_fd is not None,
        boundarySource=str(boundary), boundaryHashes=hashes, isolationProof=str(evidence/'proof.json'),
        nativeOffline=a.native, productionChanged=False, root=str(root)), indent=2))
    print(output, end='')
finally:
    publication.close()
    supervisor.close()
    if memory_fd is not None:
        os.close(memory_fd)
raise SystemExit(result.returncode)
