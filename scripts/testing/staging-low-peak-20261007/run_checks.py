#!/usr/bin/env python3
"""Run small offline regressions under an SSD budget; never launch live services."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from inventory import TOOLS, PIN
from scratch_retirement import FLOOR, SpaceBudget


def allocated(root):
    total = 0
    for directory, _, names in os.walk(root):
        for name in names:
            try:
                total += (Path(directory) / name).lstat().st_blocks * 512
            except FileNotFoundError:
                pass
    return total


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(TOOLS))
    from vk_prep_common import save, storage, digest
    assert subprocess.check_output(['git', '-C', str(TOOLS), 'rev-parse', 'HEAD'], text=True).strip() == PIN
    root = storage(args.output)
    root.mkdir(parents=True, mode=0o700, exist_ok=False)
    tmp = root / 'tmp'
    tmp.mkdir()
    environment = {**os.environ, 'TMPDIR': str(tmp), 'PYTHONDONTWRITEBYTECODE': '1',
                   'VK_LOW_PEAK_TEST_ROOT': str(root / 'fixtures')}
    budget = SpaceBudget(root)
    rows, peaks = [], []
    commands = {
        'focused': [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(Path(__file__).parent), '-v'],
        'pinned-backup': [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(TOOLS), '-v'],
    }
    for name, command in commands.items():
        budget.check(name + '-before', 512 * 1024**2)
        started = time.monotonic()
        with (root / (name + '.log')).open('w') as log:
            child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                     env=environment, start_new_session=True)
            failure = None
            try:
                while child.poll() is None:
                    budget.check(name + '-running', 256 * 1024**2)
                    peaks.append(allocated(root))
                    time.sleep(0.1)
            except BaseException as error:
                failure = str(error)
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait()
            code = child.wait()
        rows.append({'name': name, 'returncode': code, 'failure': failure,
                     'seconds': time.monotonic() - started, 'log_sha256': digest(root / (name + '.log'))})
        save(root / 'checks.json', {'checks': rows, 'passed': all(r['returncode'] == 0 and not r['failure'] for r in rows),
             'operational_pin': PIN, 'free_floor_bytes': FLOOR, 'free_samples': budget.samples,
             'minimum_observed_free_bytes': min(r['free_bytes'] for r in budget.samples),
             'maximum_observed_test_allocated_bytes': max(peaks, default=0),
             'production_modified': False, 'full_rehearsal_executed': False,
             'sampling_interval_seconds': 0.1, 'other_host_writes_not_attributed_to_this_test': True})
        print(json.dumps(rows[-1]), flush=True)
        if code or failure:
            raise SystemExit(1)


if __name__ == '__main__':
    main()
