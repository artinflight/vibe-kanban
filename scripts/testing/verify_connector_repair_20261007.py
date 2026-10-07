"""Verify the delivered repair and run narrowly scoped, isolated Rust checks."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

SOURCE = Path('/mnt/vk-storage/vk-combined-release-20261007/source')
ROOT = SOURCE.parent / 'repair-acceptance'
BINDING = Path('/mnt/vk-storage/vibe-dot-connector-maintenance/backend/review-repair-binding.json')
REVISION = '2bc909d6375e13d0dd47f370eec0100fae3b2075'


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify():
    manifest = json.loads(BINDING.read_text())
    assert manifest['revised_commit'] == REVISION
    assert digest(manifest['patch']) == '88c4c1299ab25ea1b20d4e5092eb2d4ef18e97ba2d8c809d0cb485878adf8a57'
    assert digest(BINDING) == '3974d7840b1d987f8b98c34fe11b4cadf80da688249235192d25d5f4827eb405'
    for name, hashes in manifest['files'].items():
        for revision, key in [(manifest['base_commit'], 'base_sha256'), (REVISION, 'candidate_sha256')]:
            if hashes[key] is not None:
                data = subprocess.check_output(['git', 'show', f'{revision}:{name}'], cwd=SOURCE)
                assert hashlib.sha256(data).hexdigest() == hashes[key], (revision, name)
    for record in manifest['receipts'].values():
        assert record['exit_code'] == 0 and not record['floor_hit']
        for key in ['receipt', 'log']:
            assert digest(record[key]) == record[key + '_sha256']
    for path, record in manifest['compiled_test_binaries'].items():
        assert digest(path) == record['sha256'], path
    assert not subprocess.check_output(['git', 'diff', REVISION, '--', 'packages', 'shared', 'package.json', 'pnpm-lock.yaml'], cwd=Path(manifest['worktree']))
    result = {'revision': REVISION, 'binding_sha256': digest(BINDING), 'source_files': len(manifest['files']), 'developer_receipts': len(manifest['receipts']), 'test_binaries': len(manifest['compiled_test_binaries']), 'verified_at': time.time(), 'production_changed': False}
    with (ROOT / 'binding-verification.json').open('x') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result), flush=True)


def run_checks():
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=SOURCE).decode().strip() == REVISION
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=SOURCE)
    env = {**os.environ, 'PATH': '/home/mcp/.cargo/bin:' + os.environ['PATH'],
           'CARGO_TARGET_DIR': '/mnt/vk-storage/cargo-target', 'CARGO_BUILD_JOBS': '2',
           'CARGO_INCREMENTAL': '0', 'SQLX_OFFLINE': 'true', 'CARGO_PROFILE_DEV_DEBUG': '0',
           'CARGO_PROFILE_TEST_DEBUG': '0', 'TMPDIR': str(ROOT / 'tmp'),
           'VK_REVIEW_ACCEPTANCE_ROOT': str(SOURCE)}
    commands = {
        'integration': ['cargo', 'test', '--offline', '-p', 'server', '--test', 'report_review_integration', '--', '--test-threads=1'],
        'http': ['cargo', 'test', '--offline', '-p', 'server', '--lib', 'routes::workspaces::report_review::tests', '--', '--test-threads=1'],
        'capture': ['cargo', 'test', '--offline', '-p', 'utils', '-p', 'services', '--lib', 'review_', '--', '--test-threads=1'],
        'normalizer': ['cargo', 'test', '--offline', '-p', 'executors', '--lib', 'codex::normalize_logs::tests', '--', '--test-threads=1'],
        'compile': ['cargo', 'check', '--offline', '-p', 'server', '--bin', 'server', '--tests'],
    }
    for name, command in commands.items():
        minimum = os.statvfs(ROOT).f_bavail * os.statvfs(ROOT).f_frsize
        assert minimum > 4 * 1024**3
        start = time.time()
        floor_hit = False
        with (ROOT / (name + '.log')).open('x') as log:
            child = subprocess.Popen(command, cwd=SOURCE, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            while child.poll() is None:
                stats = os.statvfs(ROOT)
                minimum = min(minimum, stats.f_bavail * stats.f_frsize)
                if minimum < 4 * 1024**3 or time.time() - start > 1800:
                    floor_hit = minimum < 4 * 1024**3
                    os.killpg(child.pid, signal.SIGTERM)
                    try:
                        child.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid, signal.SIGKILL)
                    break
                time.sleep(1)
            code = child.wait()
        result = {'command': command, 'exit_code': code, 'seconds': time.time()-start, 'minimum_free_bytes': minimum, 'floor_hit': floor_hit, 'source_commit': REVISION, 'production_changed': False}
        with (ROOT / (name + '.json')).open('x') as stream:
            json.dump(result, stream, indent=2)
        print(json.dumps(result), flush=True)
        if code:
            raise SystemExit(code)


if __name__ == '__main__':
    subprocess.run(['mountpoint', '-q', '/mnt/vk-storage'], check=True)
    (ROOT / 'tmp').mkdir(parents=True, exist_ok=True)
    {'verify': verify, 'test': run_checks}[sys.argv[1]]()
