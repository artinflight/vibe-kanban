#!/usr/bin/env python3
"""Offline native goal pause/resume + guarded expiry acceptance, on mounted SSD."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--guard', required=True, type=Path)
args = parser.parse_args()
ssd = Path('/mnt/vk-storage')
if not os.path.ismount(ssd) or not args.guard.is_absolute() or not args.guard.is_file():
    parser.error('Require the mounted SSD and an existing absolute guard binary')
repo = Path(__file__).resolve().parents[1]
root = Path(tempfile.mkdtemp(prefix='vk-continuation-acceptance-', dir=ssd / 'codexusage-capacity'))
env = dict(os.environ, CARGO_TARGET_DIR=str(ssd / 'cargo-target'), CARGO_INCREMENTAL='0')
# Explicitly choose the offline harness; never inherit a request for real usage.
for key in ('VK_GOAL_TEST_RESUME_THREAD', 'VK_GOAL_TEST_GUARD', 'OPENAI_API_KEY'):
    env.pop(key, None)
build = subprocess.run(['cargo', 'test', '-p', 'executors', 'native_goal_runtime', '--no-run', '--message-format=json'],
                       cwd=repo, env=env, text=True, stdout=subprocess.PIPE, check=True)
artifacts = [json.loads(line) for line in build.stdout.splitlines() if line.startswith('{')]
binary = next(item['executable'] for item in artifacts
              if item.get('reason') == 'compiler-artifact' and item.get('executable')
              and item.get('target', {}).get('name') == 'executors')
results = []
for scenario in ('capacity-stop', 'capacity-expiry'):
    home = root / scenario
    for resume in (False, True):
        current = dict(env, CODEX_HOME=str(home), VK_GOAL_TEST_SCENARIO=scenario)
        if scenario == 'capacity-expiry':
            current.update(VK_USE_SYSTEMD_RUN='1', VK_GOAL_TEST_GUARD=str(args.guard))
        if resume:
            (home / 'capacity-request-active').unlink()
            current['VK_GOAL_TEST_RESUME_THREAD'] = (home / 'capacity-thread-id').read_text()
        started = time.monotonic()
        result = subprocess.run([binary, 'native_goal_runtime', '--ignored', '--nocapture'],
                                cwd=repo, env=current, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=60)
        (root / f'{scenario}-{resume}.log').write_text(result.stdout)
        results.append(dict(scenario=scenario, resume=resume, passed=result.returncode == 0,
                            elapsed_ms=round((time.monotonic() - started) * 1000)))
        (root / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
        if result.returncode:
            raise SystemExit(f'FAILED: {scenario}, resume={resume}; see {root}')
# Exercise the real Codex executor resume path under durable managed authority.
home = root / 'capacity-stop'
current = dict(env, CODEX_HOME=str(home), VK_USE_SYSTEMD_RUN='1',
               VK_CAPACITY_STATE_DIR=str(home / 'controller'), VK_CAPACITY_GUARD=str(args.guard))
started = time.monotonic()
result = subprocess.run([binary, 'managed_capacity_runtime', '--ignored', '--nocapture'],
                        cwd=repo, env=current, text=True, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, timeout=60)
(root / 'managed-capacity.log').write_text(result.stdout)
results.append(dict(scenario='managed-capacity-two-runs', passed=result.returncode == 0,
                    elapsed_ms=round((time.monotonic() - started) * 1000)))
(root / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
if result.returncode:
    raise SystemExit(f'FAILED managed controller resume; see {root}')
print(json.dumps(dict(artifacts=str(root), results=results), indent=2))
