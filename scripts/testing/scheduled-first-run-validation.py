"""Run compiled VK tests within CU's reviewed kernel/supervisor boundary.

No fixture backend ever runs with host filesystem or host-manager authority.
The boundary directory is supplied explicitly and its complete source hashes
are recorded. This driver does not compile, deploy or change live settings.
"""
import argparse
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
parser.add_argument('--binary', type=Path, required=True)
parser.add_argument('--guard', type=Path, required=True)
parser.add_argument('--native', action='store_true')
parser.add_argument('--variant', choices=['success', 'input', 'failure', 'race', 'plan', 'empty'], default='success')
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
binary = a.binary.resolve(strict=True)
guard = a.guard.resolve(strict=True)
base = Path('/mnt/vk-storage/vk-sfr-20261006')
base.mkdir(exist_ok=True)
root, evidence = provision(base, 'vk-continuation-first-run-')
(root/'home').mkdir()
(root/'controller').mkdir()
supervisor = FixtureManager(root, guard)
publication = Publication(root)
try:
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
    with publication.open_text('validation.log') as log:
        result = subprocess.run(command(root, argv, controller=a.native, worker=not a.native),
                                env=env, stdout=log, stderr=log, timeout=180)
        log.flush(); log.seek(0); output = log.read()
    require(hashes == {name: hashlib.sha256((boundary/name).read_bytes()).hexdigest() for name in files},
            'Reviewed boundary changed while tests ran')
    publication.write_text('result.json', json.dumps(dict(exitCode=result.returncode,
        command=argv, binarySha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
        boundarySource=str(boundary), boundaryHashes=hashes, isolationProof=str(evidence/'proof.json'),
        nativeOffline=a.native, productionChanged=False, root=str(root)), indent=2))
    print(output, end='')
finally:
    publication.close()
    supervisor.close()
raise SystemExit(result.returncode)
