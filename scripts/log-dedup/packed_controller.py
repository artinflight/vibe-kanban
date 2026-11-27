"""One finite packed conversion under the existing converter lease.

The deployment adapter owns actual SQL/reader/recovery admission. This runner
never selects work again, retries a partial batch, changes services or schedules,
or removes a failed run. An existing RUN is always a reconciliation hold.
"""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import stat
import time

import log_dedup as logs
from packed_admission import pinned
from packed_recovery import write_new
import reclaim


def selection(mapping):
    groups = mapping['groups']
    if not 1 <= len(groups) <= 4096:
        raise ValueError('Finite nonempty packed selection required')
    seen = set()
    for key, group in groups.items():
        plan = group['plan']
        names = [r['path'] for r in plan['files']]
        if (key != group['plan_sha256'] or key != logs.sha(reclaim.canonical(plan))
                or plan['source_root'] != mapping['source_root']
                or not 1 <= len(names) <= 64 or len(set(names)) != len(names)
                or seen.intersection(names)
                or len({str(Path(n).parent) for n in names}) != 1
                or sum(r['raw_bytes'] for r in plan['files']) > 2 * 1024**3):
            raise ValueError('Unique bounded exact-session plans required')
        seen.update(names)
    return sorted(groups), seen


@contextmanager
def existing_owner(path):
    path = Path(path)
    if not path.is_absolute() or path.resolve(strict=True) != path:
        raise ValueError('Canonical existing converter lease required')
    before = path.lstat()
    if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid()
            or before.st_nlink != 1 or before.st_mode & 0o022):
        raise ValueError('Existing unique owned converter lease required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        opened = os.fstat(fd)
        identity = (before.st_dev, before.st_ino)
        if (opened.st_dev, opened.st_ino) != identity:
            raise ValueError('Converter lease replaced during open')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        def check():
            named = path.lstat()
            if (named.st_dev, named.st_ino) != identity:
                raise ValueError('Converter lease replaced while held')
        check()
        yield check
    finally:
        os.close(fd)


def execute(mapping_reference, folder, owner_lock, adapter, *, maximum_seconds,
            checkpoint=lambda value: None, clock=time.monotonic):
    """adapter: check, convert(group,journal,progress), verify(group,journal), seal.

    The production adapter binds real LiveReaders and NormalPreparedRecovery.
    Qualification may supply an explicitly isolated adapter. This generic runner
    alone is neither authorization nor an independent-recovery assertion.
    """
    if type(maximum_seconds) is not int or not 1 <= maximum_seconds <= 21600:
        raise ValueError('Finite duration of at most six hours required')
    mapping = pinned(mapping_reference)
    keys, names = selection(mapping)
    folder = Path(folder)
    if folder.resolve() != folder or folder.exists():
        raise FileExistsError('Existing run requires reconciliation; no replay')
    with existing_owner(owner_lock) as owner_check:
        adapter.check()
        folder.mkdir(mode=0o700)
        reclaim.sync_directory(folder.parent)
        write_new(folder/'RUN.json', dict(mapping=mapping_reference, groups=keys,
                                        source_files=len(names), replay_allowed=False))
        began = clock()
        results = []
        def guard():
            owner_check()
            adapter.check()
            if clock() - began > maximum_seconds:
                raise TimeoutError('Finite packed conversion deadline reached')
        try:
            for number, key in enumerate(keys):
                guard()
                group = mapping['groups'][key]
                journal = folder/('batch-%04d' % number)
                write_new(folder/('INTENT-%04d.json' % number),
                          dict(plan_sha256=key, journal=str(journal), replay_allowed=False))
                def progress(phase, path):
                    owner_check()
                    if clock() - began > maximum_seconds:
                        raise TimeoutError('Finite packed conversion deadline reached')
                    checkpoint(dict(phase=phase, path=str(path), batch=number,
                                    completed=len(results), total=len(keys)))
                outcome = adapter.convert(group, journal, progress)
                guard()
                proof = adapter.verify(group, journal)
                if (outcome.get('plan_sha256') != key or not outcome.get('originals_released')
                        or proof.get('plan_sha256') != key or proof.get('files') != len(group['files'])
                        or proof.get('full_EOF_verified') is not True):
                    raise ValueError('Complete retirement and current full-EOF proof required')
                receipt = dict(plan_sha256=key, retirement=outcome, verification=proof,
                               journal=str(journal))
                write_new(folder/('BATCH-%04d.json' % number), receipt)
                results.append(receipt)
                checkpoint(dict(phase='batch_committed', completed=len(results), total=len(keys)))
            guard()
            summary = dict(complete=True, source_files=len(names), groups=len(keys),
                           mapping=mapping_reference, elapsed_seconds=clock()-began)
            write_new(folder/'SUMMARY.json', summary)
            # Seal durable manifests, replacement identities and retirement
            # evidence as well as the complete run ledger through normal recovery.
            paths = sorted(p for p in folder.rglob('*.json') if p.is_file())
            proof = adapter.seal(paths)
            if proof.get('independent_recovery_verified') is not True:
                raise ValueError('Run journal restoration proof required')
            guard()
            result = dict(summary, recovery=proof)
            write_new(folder/'RESULT.json', result)
            return result
        except BaseException as error:
            write_new(folder/'FAILURE.json', dict(error_type=type(error).__name__,
                      reason=str(error)[:500], completed=len(results), total=len(keys),
                      replay_allowed=False, preserve_every_journal=True))
            raise
