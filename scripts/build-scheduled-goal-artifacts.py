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
# Package the actual scanner and test this identical executable with no optional skips.
from importlib.util import spec_from_file_location, module_from_spec
spec = spec_from_file_location('release_scanner', repo/'scripts/testing/prepare-release-scanner.py')
scanner_module = module_from_spec(spec)
spec.loader.exec_module(scanner_module)
scanner = scanner_module.prepare(output/'preservation')
artifacts['preservation/gitleaks'] = {'sha256': sha(scanner), 'bytes': scanner.stat().st_size}
scanner_proof = scanner.parent/'scanner-source.json'
artifacts['preservation/scanner-source.json'] = {'sha256': sha(scanner_proof), 'bytes': scanner_proof.stat().st_size}
fixtures = output/'scanner-fixtures'
fixtures.mkdir()
with (output/'scanner-acceptance.log').open('w') as log:
    subprocess.run(['python3', str(repo/'scripts/preservation/test_turn_git.py')],
                   check=True, env={**env, 'VK_PRESERVATION_TEST_ROOT': str(fixtures),
                                    'VK_TEST_GITLEAKS': str(scanner)}, stdout=log, stderr=subprocess.STDOUT)
artifacts['scanner-acceptance.log'] = {'sha256': sha(output/'scanner-acceptance.log'),
                                    'bytes': (output/'scanner-acceptance.log').stat().st_size}

cargo(['build', '-p', 'executors', '--bin', 'vk-routing-module'])
worker = publish(target/'acceptance/vk-routing-module', 'autoswitch-module/validator')
subprocess.run(['strip', str(worker)], check=True)
artifacts['autoswitch-module/validator'] = {'sha256': sha(worker), 'bytes': worker.stat().st_size}
defaults = json.loads(subprocess.check_output([str(worker), '--defaults'], text=True))
require(defaults['protocol'] == 2, 'Expected approved module protocol 2')
module = output/'autoswitch-module/releases'/('safe-'+source[:12])
module.mkdir(parents=True)
shutil.copy2(worker, module/'worker')
(module/'models.json').write_text(json.dumps(defaults['models'], indent=2)+'\n')
(module/'instructions.txt').write_text(defaults['instructions'])
module_manifest = {'protocol': 2, 'version': module.name,
                   'worker_sha256': sha(module/'worker'), 'models_sha256': sha(module/'models.json'),
                   'instructions_sha256': sha(module/'instructions.txt'),
                   'classifier_model': 'gpt-5.6-luna', 'classifier_effort': 'low'}
(module/'manifest.json').write_text(json.dumps(module_manifest, indent=2)+'\n')
subprocess.run([str(worker), '--verify-release', str(module)], check=True, timeout=15)
for file in module.iterdir():
    artifacts[str(file.relative_to(output))] = {'sha256': sha(file), 'bytes': file.stat().st_size}
import tarfile
with tarfile.open(output/'module-links.tar', 'w') as archive:
    link = tarfile.TarInfo('autoswitch-module/current')
    link.type = tarfile.SYMTYPE
    link.linkname = 'releases/'+module.name
    archive.addfile(link)
artifacts['module-links.tar'] = {'sha256': sha(output/'module-links.tar'), 'bytes': (output/'module-links.tar').stat().st_size}
subprocess.run(['pnpm', '--filter', '@vibe/local-web', 'run', 'build'], cwd=repo, env=env, check=True)
frontend = repo/'packages/local-web/dist'
require((frontend/'index.html').is_file(), 'Combined frontend missing')
shutil.copytree(frontend, output/'candidate/frontend')
for file in sorted((output/'candidate/frontend').rglob('*')):
    if file.is_file():
        artifacts[str(file.relative_to(output))] = {'sha256': sha(file), 'bytes': file.stat().st_size}

require(tracked == {name: sha(repo/name) for name in tracked}, 'Tracked source changed during build')
require(not capture('git', 'status', '--porcelain', '--untracked-files=no'), 'Source became dirty')
manifest = {'sourceCommit': source, 'sourceTree': capture('git', 'rev-parse', 'HEAD^{tree}'),
    'trackedHashes': tracked, 'artifacts': artifacts, 'commands': commands,
    'rustc': capture('rustc', '-Vv'), 'cargo': capture('cargo', '-V'),
    'platform': platform.platform(), 'machine': platform.machine(),
    'runId': os.environ.get('GITHUB_RUN_ID'), 'runAttempt': os.environ.get('GITHUB_RUN_ATTEMPT'),
    'profile': 'acceptance', 'frontend': 'source-bound combined phone frontend and MCP consent UI; backend embedded placeholder is unused',
    'httpFixtureStarted': False, 'runtimeAcceptance': 'not performed by builder',
    'productionChanged': False}
(output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
print(json.dumps({name: value['sha256'] for name, value in artifacts.items()}, indent=2))
