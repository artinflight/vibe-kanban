"""One-shot full task audit for an exact, kernel-leased retained image.

Not an installed privileged policy. Caller supplies the pinned inspector's stat
parser, host visibility check and held backup-lane/inode boundaries. Only absence
of a whole task directory proves exit. Missing live metadata, denied inspection,
identity changes, consumers, nonconvergence and deadlines preserve the image.
New tasks must be inspected before clearance; no names or maps are emitted.
"""
import os
import time
from pathlib import Path


class Inconclusive(RuntimeError):
    pass


def scan_consumers(targets, *, process_stat, boundary, owner_pid, guards,
                   proc=Path('/proc'), clock=time.monotonic,
                   maximum_seconds=60, maximum_rounds=8):
    started = clock()
    exits, inspected, guard_seen = set(), set(), set()
    tasks = 0

    def check():
        if clock() - started >= maximum_seconds:
            raise Inconclusive('consumer audit deadline; preserve image')
        boundary()

    def gone(base):
        # ENOENT on stat/maps/fd/exe alone is never proof of exit.
        try:
            base.stat()
        except FileNotFoundError:
            exits.add(str(base.relative_to(proc)))
            return True
        return False

    def inventory():
        result = {}
        for pid in os.listdir(proc):
            if not pid.isdigit():
                continue
            check()
            leader = proc / pid
            try:
                leader_start = process_stat(leader)[0]
                tids = [t for t in os.listdir(leader / 'task') if t.isdigit()]
                if not tids:
                    raise Inconclusive('empty live task inventory')
                for tid in tids:
                    base = leader / 'task' / tid
                    try:
                        start = process_stat(base)[0]
                    except FileNotFoundError:
                        if gone(base):
                            continue
                        raise Inconclusive(f'missing stat in live task {base}') from None
                    result[(pid, leader_start, tid, start)] = base
                if process_stat(leader)[0] != leader_start:
                    raise Inconclusive('process identity changed')
            except FileNotFoundError:
                if gone(leader):
                    result = {k: v for k, v in result.items() if k[0] != pid}
                    continue
                raise Inconclusive(f'missing metadata in live process {leader}') from None
        if not result:
            raise Inconclusive('empty host inventory')
        return result

    def consumer(key):
        if key in targets:
            raise Inconclusive('retained image has a consumer; preserve image')

    def inspect(key, base):
        nonlocal tasks
        pid, leader_start, tid, expected_start = key
        check()
        try:
            before = process_stat(base)
            if before[0] != expected_start or process_stat(proc / pid)[0] != leader_start:
                raise Inconclusive('task identity changed')
            tasks += 1
            kernel = bool(before[2] & 0x200000)
            for kind in ('exe', 'cwd', 'root'):
                try:
                    info = (base / kind).stat()
                    consumer((info.st_dev, info.st_ino))
                except FileNotFoundError:
                    if gone(base):
                        return
                    if not (kernel or before[1] == 'Z'):
                        raise Inconclusive(f'missing live task reference {base}/{kind}') from None
            for name in os.listdir(base / 'fd'):
                check()
                if not name.isdigit():
                    raise Inconclusive('malformed fd inventory')
                try:
                    info = (base / 'fd' / name).stat()
                except FileNotFoundError:
                    continue  # Closed FD; recheck task identity below.
                inode = (info.st_dev, info.st_ino)
                if int(pid) == owner_pid and inode in guards:
                    guard_seen.add(inode)
                else:
                    consumer(inode)  # Includes O_PATH, unlike kernel leases.
            with (base / 'maps').open() as stream:
                for line in stream:
                    check()
                    fields = line.split(None, 5)
                    if len(line) > 65536 or len(fields) < 5:
                        raise Inconclusive('malformed maps')
                    major, minor = (int(v, 16) for v in fields[3].split(':'))
                    consumer((os.makedev(major, minor), int(fields[4])))
            if process_stat(base)[0] != expected_start or process_stat(proc / pid)[0] != leader_start:
                raise Inconclusive('task identity changed')
        except FileNotFoundError:
            if gone(base):
                return
            raise Inconclusive(f'incomplete live task inspection {base}') from None
        inspected.add(key)

    current = inventory()
    for round_number in range(1, maximum_rounds + 1):
        for key, base in current.items():
            if key not in inspected:
                inspect(key, base)
        check()
        current = inventory()
        if set(current) <= inspected:
            if guard_seen != guards:
                raise Inconclusive('owner inode guard not observed')
            check()
            return dict(processes=len({k[0] for k in current}), tasks=tasks,
                        final_live_tasks=len(current), proven_exits=len(exits),
                        rounds=round_number, matches=0, inspection_denied=0,
                        elapsed_seconds=clock() - started,
                        method='full-task-audit-with-proven-exits-and-kernel-lease')
    raise Inconclusive('new task inventory did not converge; preserve image')
