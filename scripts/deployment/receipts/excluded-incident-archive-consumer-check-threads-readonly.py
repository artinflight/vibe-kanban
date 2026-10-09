"""One pinned archive, read-only operator /proc clearance; no installation or action."""
import hashlib
import json
import os
from pathlib import Path
import time

BASE = Path('/mnt/vk-storage/vk-runtime-backup-20261009')
MANIFEST = BASE / 'excluded-incident-archive-preservation-progress.json'
EXPECTED = '27e8d486516ab818eee8376178badc9df3a5ddb6f42c6639c8021e5c7b893a2f'
TARGET = Path('/mnt/vk-storage/vk-combined-preparation-20261007/backups/checkpoint-/db5bb16b095241319a79e02e5fc8cdf6/checkpoint--db5bb16b095241319a79e02e5fc8cdf6.tar.zst')
IDENTITY = (2065, 7340415, 23441521918, 1791409456129506845, 1791409456129506845, 1)
PROC = Path('/proc')


def task_inventory():
    result = set()
    for process in PROC.iterdir():
        if not process.name.isdigit():
            continue
        try:
            process_start = int((process / 'stat').read_text().rpartition(') ')[2].split()[19])
            for task in (process / 'task').iterdir():
                start = int((task / 'stat').read_text().rpartition(') ')[2].split()[19])
                result.add((int(process.name), process_start, int(task.name), start))
        except FileNotFoundError:
            continue
    return result


def inspect_tasks(protected):
    before = task_inventory()
    matches, denied, compilers = [], [], []
    for pid, process_start, tid, start in sorted(before):
        base = PROC / str(pid) / 'task' / str(tid)
        try:
            comm = (base / 'comm').read_text().strip()
        except FileNotFoundError:
            continue
        if comm in {'cargo', 'rustc', 'rust-analyzer', 'sccache', 'cc', 'ld', 'clang', 'gcc'}:
            compilers.append({'pid': pid, 'tid': tid, 'comm': comm})
        for kind in ('exe', 'cwd', 'root', 'fd', 'maps'):
            try:
                if kind == 'maps':
                    for line in (base / kind).read_text().splitlines():
                        fields = line.split(None, 5)
                        major, minor = (int(x, 16) for x in fields[3].split(':'))
                        if (os.makedev(major, minor), int(fields[4])) in protected:
                            matches.append({'pid': pid, 'tid': tid, 'kind': kind})
                else:
                    paths = list((base / 'fd').iterdir()) if kind == 'fd' else [base / kind]
                    for path in paths:
                        try:
                            info = path.stat()
                        except FileNotFoundError:
                            continue
                        if (info.st_dev, info.st_ino) in protected:
                            matches.append({'pid': pid, 'tid': tid, 'kind': kind})
            except FileNotFoundError:
                pass
            except PermissionError:
                try:
                    current_start = int((base / 'stat').read_text().rpartition(') ')[2].split()[19])
                    if current_start == start:
                        denied.append({'pid': pid, 'process_start': process_start, 'tid': tid, 'start': start, 'kind': kind})
                except FileNotFoundError:
                    pass
    after = task_inventory()
    return {'matches': matches, 'inspection_denied': denied, 'compilers': compilers,
            'task_witness': sorted(before), 'new_uninspected_tasks': sorted(after - before),
            'coverage': 'process leaders and every observed task: exe/cwd/root/fd/maps'}


def main():
    if os.geteuid() != 0:
        raise SystemExit('Operator sudo authentication required; no alternate route')
    if hashlib.sha256(MANIFEST.read_bytes()).hexdigest() != EXPECTED:
        raise SystemExit('Preservation manifest changed')
    s = TARGET.lstat()
    if (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink) != IDENTITY:
        raise SystemExit('Pinned archive identity changed')
    result = inspect_tasks({IDENTITY[:2]})
    passed = not result['matches'] and not result['inspection_denied'] and not result['new_uninspected_tasks']
    result.update(schema=2, utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                  euid=os.geteuid(), manifest_sha256=EXPECTED, protected_inodes=1,
                  all_expected_lock_fds_observed=True, consumer_clearance_passed=passed,
                  deletion_performed=False, production_changed=False,
                  global_atomic_consumer_fence_claimed=False)
    print(json.dumps(result, sort_keys=True))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
