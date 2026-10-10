"""Package the exact reviewed two-chat reader. Never starts an application."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


root = Path(run('git', 'rev-parse', '--show-toplevel'))
source = run('git', 'rev-parse', 'HEAD')
assert source == os.environ['GITHUB_SHA']
assert not run('git', 'status', '--porcelain', '--untracked-files=no')
fence = json.loads((root / 'scripts/testing/two-chat-reader-source.json').read_text())
for path, digest in fence['included_file_sha256'].items():
    assert sha(root / path) == digest, path
for path in ('Cargo.toml', 'Cargo.lock', 'pnpm-lock.yaml'):
    expected = subprocess.check_output(['git', 'show', fence['backend_base'] + ':' + path])
    assert (root / path).read_bytes() == expected, path
assert not run('git', 'diff', '--name-only', fence['backend_base'], 'HEAD', '--', 'crates/db')
output = Path(os.environ['VK_CHAT_ARTIFACT'])
assert not output.exists()
output.mkdir(parents=True)
env = dict(os.environ, VK_BUILD_SOURCE_COMMIT=source, CARGO_INCREMENTAL='0')
subprocess.run(['cargo', 'build', '--locked', '--profile', 'acceptance', '-p', 'server', '--bin', 'server'], env=env, check=True)
server = root / 'target/acceptance/server'
info = json.loads(run(str(server), '--capacity-build-info'))
assert info['sourceCommit'] == source
for key in ('automaticWorkspaceDeletion', 'automaticAttachmentMigration', 'automaticAttachmentCleanup'):
    assert info[key] is False, key
assert info['runtimeIdentityVersion'] == 1 and info['capacityWireVersion'] == 1
shutil.copy2(server, output / 'server')
subprocess.run(['pnpm', '--filter', '@vibe/local-web', 'run', 'build'], check=True)
shutil.copytree(root / 'packages/local-web/dist', output / 'frontend')
files = {str(p.relative_to(output)): {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in sorted(output.rglob('*')) if p.is_file()}
manifest = dict(fence, sourceCommit=source, sourceTree=run('git', 'rev-parse', 'HEAD^{tree}'), files=files, buildInfo=info, profile='acceptance', runId=os.environ['GITHUB_RUN_ID'], productionStarted=False, fallback='Existing c3 latest-current-data runtime; zero DB schema changes; recovered sidecars ignored by old reader.')
(output / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
print(json.dumps({'source': source, 'server': files['server'], 'manifestSha256': sha(output / 'manifest.json')}, indent=2))
