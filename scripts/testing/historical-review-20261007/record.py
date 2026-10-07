"""Retain sanitized strict-replay failure evidence, without live database access."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

compatibility = '--compatibility' in sys.argv
root = Path('/mnt/vk-storage/vk-combined-release-20261007') / ('compatibility-acceptance' if compatibility else 'repair-acceptance')
source = root.parent / 'source'
here = Path(__file__).resolve().parent
revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
assert revision == ('5ec5722455d9b12ae8a9b00b371351ad12a685ef' if compatibility else '2bc909d6375e13d0dd47f370eec0100fae3b2075')
assert os.path.ismount('/mnt/vk-storage')
assert os.statvfs(root).f_bavail * os.statvfs(root).f_frsize > 4 * 1024**3
env = {**os.environ, 'CARGO_TARGET_DIR': '/mnt/vk-storage/cargo-target',
       'CARGO_BUILD_JOBS': '2', 'CARGO_INCREMENTAL': '0', 'SQLX_OFFLINE': 'true',
       'CARGO_PROFILE_DEV_DEBUG': '0', 'CARGO_PROFILE_TEST_DEBUG': '0', 'TMPDIR': str(root / 'tmp')}
command = ['/home/mcp/.cargo/bin/cargo', '+nightly-2025-12-04', 'run', '--offline',
           '--manifest-path', str(here / 'Cargo.toml')]
started = time.time()
suffix = '-formatted' if sys.argv[1:] == ['--formatted'] else ''
assert sys.argv[1:] in ([], ['--formatted'], ['--compatibility'])
with (root / f'historical-replay{suffix}.jsonl').open('x') as output, (root / f'historical-build{suffix}.log').open('x') as log:
    result = subprocess.run(command, env=env, stdout=output, stderr=log, timeout=1200)
reports = [json.loads(line) for line in (root / f'historical-replay{suffix}.jsonl').read_text().splitlines()]
def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
receipt = {'source_commit': revision, 'exit_code': result.returncode,
           'seconds': time.time()-started, 'reports': reports,
           'source_hashes': {str(p.relative_to(here)): sha(p) for p in [here/'Cargo.toml', here/'Cargo.lock', here/'src/main.rs']},
           'binary_sha256': sha(Path('/mnt/vk-storage/cargo-target/debug/vk-historical-review-audit')),
           'production_changed': False, 'live_badges_cleared': False,
           'passed': result.returncode == 0 and len(reports) == 4,
           'historical_receipts_authorized': False}
with (root / f'historical-replay-result{suffix}.json').open('x') as output:
    json.dump(receipt, output, indent=2)
print(json.dumps(receipt), flush=True)
raise SystemExit(result.returncode)
