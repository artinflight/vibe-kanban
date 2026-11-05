"""Export an exact-source executor test artifact, with no server or account use."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def capture(*args):
    return subprocess.check_output(args, text=True).strip()


def sha(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


revision = capture('git', 'rev-parse', 'HEAD')
assert revision == os.environ['VK_EXPECTED_SOURCE']
assert not capture('git', 'status', '--porcelain', '--untracked-files=no')
repo = Path(capture('git', 'rev-parse', '--show-toplevel')).resolve()
output = Path(os.environ['VK_STEERING_TEST_ARTIFACT']).resolve()
assert not output.exists() and not output.is_relative_to(repo)
assert not (repo / '.env').exists()
messages = [json.loads(line) for line in Path(sys.argv[1]).read_text().splitlines()
            if line.startswith('{')]
binaries = [Path(message['executable']) for message in messages
            if message.get('reason') == 'compiler-artifact'
            and message.get('target', {}).get('name') == 'executors'
            and message.get('profile', {}).get('test') is True
            and message.get('executable')]
assert len(binaries) == 1
output.mkdir()
destination = output / 'executor-tests'
shutil.copy2(binaries[0], destination)
tracked = {name: sha(repo / name) for name in capture('git', 'ls-files', '-z').split('\x00')
           if (repo / name).is_file()}
manifest = {'sourceCommit': revision, 'sourceTree': capture('git', 'rev-parse', 'HEAD^{tree}'),
            'trackedHashes': tracked,
            'artifacts': {'executor-tests': {'sha256': sha(destination), 'bytes': destination.stat().st_size}},
            'profile': 'test', 'rustc': capture('rustc', '-Vv'),
            'runId': os.environ.get('GITHUB_RUN_ID'),
            'purpose': 'isolated steering test only; not a deployment artifact',
            'nativeAcceptance': 'pending account-backed sample', 'productionChanged': False}
(output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(manifest['artifacts']))
