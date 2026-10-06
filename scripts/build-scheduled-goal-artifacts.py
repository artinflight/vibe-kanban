"""Build a source-fenced acceptance bundle; never start an HTTP fixture backend.

Run on an isolated hosted builder with enough storage. Runtime validation uses
the separately reviewed kernel/supervisor boundary on the acceptance host.
"""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def capture(*args):
    return subprocess.check_output(args, text=True).strip()


def sha(path):
    with path.open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


repo = Path(capture('git', 'rev-parse', '--show-toplevel')).resolve()
source = capture('git', 'rev-parse', 'HEAD')
require(source == os.environ['VK_EXPECTED_SOURCE'], 'Source revision mismatch')
require(not capture('git', 'status', '--porcelain', '--untracked-files=no'), 'Dirty tracked source')
require(not (repo/'.env').exists(), 'Acceptance builder must not import a local .env')
output = Path(os.environ['VK_ARTIFACT_DIR']).resolve()
target = Path(os.environ['CARGO_TARGET_DIR']).resolve()
require(not output.is_relative_to(repo) and not target.is_relative_to(repo), 'Build/output must be outside source')
require(not output.exists(), 'Use a fresh immutable artifact output')
output.mkdir(parents=True)
files = capture('git', 'ls-files', '-z').split('\x00')
tracked = {name: sha(repo/name) for name in files if (repo/name).is_file()}
env = {**os.environ, 'VK_BUILD_SOURCE_COMMIT': source, 'CARGO_INCREMENTAL': '0'}
commands = []
artifacts = {}


def cargo(args, messages=False):
    command = ['cargo', *args, '--profile', 'acceptance', '--locked']
    commands.append(command)
    result = subprocess.run(command, env=env, check=True,
                            stdout=subprocess.PIPE if messages else None, text=True)
    return result.stdout


def publish(original, name):
    destination = output/name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(original, destination)
    artifacts[name] = {'sha256': sha(destination), 'bytes': destination.stat().st_size}
    return destination


for variant, features in [('candidate', []), ('rollback', ['--features', 'scheduled-goal-initialization-disabled'])]:
    cargo(['build', '-p', 'server', '--bin', 'server', *features])
    server = publish(target/'acceptance/server', variant+'/server')
    # This read-only identification path returns before deployment construction,
    # native state access and startup cleanup. No fixture server is launched.
    info = json.loads(subprocess.check_output([str(server), '--capacity-build-info'],
        env={**env, 'VK_CAPACITY_SCHEDULED_GOAL_INITIALIZATION': '1'}, text=True))
    require(info['sourceCommit'] == source and info['capacityLedgerVersions'] == [1, 2], 'Wrong build identity/reader')
    expected = variant == 'candidate'
    require(info['initializationCompiled'] == expected and info['scheduledGoalInitialization'] == int(expected), 'Wrong initialization feature fence')
    artifacts[variant+'/server']['buildInfo'] = info
    messages = cargo(['test', '-p', 'executors', '--lib', '--no-run', '--message-format=json', *features], True)
    binaries = [m['executable'] for line in messages.splitlines() if line.startswith('{')
                for m in [json.loads(line)] if m.get('reason') == 'compiler-artifact'
                and m.get('target', {}).get('name') == 'executors' and m.get('executable')]
    require(len(binaries) == 1, 'Expected exactly one executor test binary')
    publish(Path(binaries[0]), variant+'/executor-tests')
cargo(['build', '-p', 'capacity-guard', '--bin', 'vk-capacity-guard'])
publish(target/'acceptance/vk-capacity-guard', 'vk-capacity-guard')
require(tracked == {name: sha(repo/name) for name in tracked}, 'Tracked source changed during build')
require(not capture('git', 'status', '--porcelain', '--untracked-files=no'), 'Source became dirty')
manifest = {'sourceCommit': source, 'sourceTree': capture('git', 'rev-parse', 'HEAD^{tree}'),
    'trackedHashes': tracked, 'artifacts': artifacts, 'commands': commands,
    'rustc': capture('rustc', '-Vv'), 'cargo': capture('cargo', '-V'),
    'platform': platform.platform(), 'machine': platform.machine(),
    'runId': os.environ.get('GITHUB_RUN_ID'), 'runAttempt': os.environ.get('GITHUB_RUN_ATTEMPT'),
    'profile': 'acceptance', 'frontend': 'placeholder; external release required',
    'httpFixtureStarted': False, 'runtimeAcceptance': 'not performed by builder',
    'productionChanged': False}
(output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
print(json.dumps({name: value['sha256'] for name, value in artifacts.items()}, indent=2))
