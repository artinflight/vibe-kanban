"""Read-only progress from the converter's exact duplicate-staging allowlist.

No process I/O counters, heartbeat timestamps or repeated observations count as
progress. Only a durable verification-plan timestamp and newly absent owned
replicas with unchanged hash-verified primary copies can advance the clock.
"""
import hashlib
import json
from pathlib import Path
import re
import stat


def read(path, maximum=64 * 1024**2):
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > maximum:
        raise ValueError('Bounded regular retirement receipt required')
    raw = path.read_bytes()
    after = path.lstat()
    if identity(before) != identity(after):
        raise ValueError('Retirement receipt changed during observation')
    return json.loads(raw), hashlib.sha256(raw).hexdigest(), before.st_mtime


def identity(value):
    return [value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns]


def supplement(root, row, previous, now):
    root = Path(root)
    result = dict(row)
    if row['state'] not in ('running', 'stalled'):
        return result, previous
    candidates = [p for p in root.glob('batch-[0-9][0-9][0-9][0-9]')
                  if (p / 'STAGING_RETIREMENT_PLAN.private.json').exists()
                  and not (p / 'RESULT.private.json').exists()]
    if not candidates:
        return result, previous
    if len(candidates) != 1:
        raise ValueError('Ambiguous uncommitted retirement phase')
    folder = candidates[0]
    conversion, _, _ = read(folder / 'CONVERSION.private.json')
    journal, _, _ = read(folder / 'journal/state.json')
    recovery, _, _ = read(folder / 'DYNAMIC_RECOVERY.private.json')
    if (conversion.get('complete') is not True or conversion.get('outcome') != 'installed'
            or journal.get('complete') is not True or journal.get('outcome') != 'installed'
            or recovery.get('actual_independent_normal_restore', {}).get('independent_owner_controls_restore_verified') is not True):
        raise ValueError('Completed conversion and independent recovery required')
    plan, digest, plan_at = read(folder / 'STAGING_RETIREMENT_PLAN.private.json')
    original, _, _ = read(folder / 'PLAN.private.json')
    objects = plan['objects']
    if not objects and plan.get('retained_objects') and plan.get('original_or_primary_deletion') is False:
        # Retaining valid alternate encodings is not verified deletion progress.
        return result, previous
    if plan.get('original_or_primary_deletion') is not False or not 1 <= len(objects) <= 100000:
        raise ValueError('Finite duplicate-only retirement allowlist required')
    if not 0 <= plan_at <= now:
        raise ValueError('Invalid retirement receipt clock')
    token = folder.name + ':' + digest
    old = previous if previous and previous.get('token') == token else None
    removed = 0
    for item in objects:
        p = Path(item['path'])
        relative = p.relative_to(folder / 'archive')
        if (p.parent.name != '.log-objects' or not re.fullmatch('[0-9a-f]{64}\\.gz', p.name)
                or p.parent.resolve() != p.parent or '..' in relative.parts):
            raise ValueError('Foreign staging object reference')
        try:
            value = p.lstat()
        except FileNotFoundError:
            # The converter retires the recorded prefix in order. Check only new
            # removals against primary bytes; repeated observations earn no credit.
            if old is None or removed >= old['removed']:
                q = Path(item['primary'])
                if q != Path(original['source_root']) / relative:
                    raise ValueError('Foreign primary object reference')
                before = q.lstat()
                if not stat.S_ISREG(before.st_mode):
                    raise ValueError('Primary replica is not regular')
                with q.open('rb') as source:
                    actual = hashlib.file_digest(source, 'sha256').hexdigest()
                if actual != item['physical_sha256'] or identity(before) != identity(q.lstat()):
                    raise ValueError('Primary bytes changed during retirement observation')
            removed += 1
        else:
            if not stat.S_ISREG(value.st_mode) or identity(value) != item['identity']:
                raise ValueError('Retained staging object identity changed')
            break
    if old and removed < old['removed']:
        raise ValueError('Retired staging prefix regressed')
    at = max(plan_at, row['progress_at'])
    if old:
        at = max(at, now if removed > old['removed'] else old['at'])
    state = dict(token=token, removed=removed, at=at)
    result.update(progress_at=at, phase='verified_duplicate_staging_retirement',
                  retirement_batch=folder.name, retirement_removed=removed,
                  retirement_total=len(objects), state='running' if now-at < 600 else 'stalled',
                  needs_attention=now-at >= 600)
    return result, state
