"""Read one owner-coordinated snapshot. No ledger, telemetry inference or allocation writes."""
import hashlib
import json
import os
import re
import stat
import uuid

SCHEMA = 'storage-remaining-future/v1'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def integer(value):
    return type(value) is int and 0 <= value <= 2**63 - 1


def timestamp(value):
    return type(value) in (int, float) and 0 <= value < 2**53


def validate(document, expected, identity, now):
    """Completeness and remaining bytes are asserted by the existing coordinating owner.

    Receipt hashes bind authority/usage evidence; hashes alone do not prove its
    semantics or authorize a publisher. Producer ownership/review is an activation prerequisite.
    """
    authorities = expected['authorities']
    max_age = expected['max_age_seconds']
    if (not authorities or type(max_age) is not int or max_age <= 0
            or any(not re.fullmatch('[a-f0-9]{64}', h) for h in authorities.values())
            or document['schema'] != SCHEMA or document['filesystem_uuid'] != identity
            or document['authority_set_sha256'] != digest(authorities)
            or document['complete'] is not True):
        raise ValueError('incomplete_or_wrong_authority')
    snapshot_id = str(uuid.UUID(document['snapshot_id']))
    at, expires = document['observed_at'], document['valid_until']
    if (not timestamp(at) or not timestamp(expires) or not at <= now < expires <= at + max_age
            or now - at > max_age):
        raise ValueError('stale_or_future_accounting')
    entries = document['allocations']
    if not isinstance(entries, list) or len(entries) != len(authorities):
        raise ValueError('incomplete_or_duplicate_allocations')
    seen, total = set(), 0
    for row in entries:
        key = row['allocation_id']
        if (key in seen or key not in authorities or row['authority_sha256'] != authorities[key]
                or not integer(row['remaining_future_bytes'])
                or not timestamp(row['usage_observed_at'])
                or not at - max_age <= row['usage_observed_at'] <= at
                or now - row['usage_observed_at'] > max_age
                or not re.fullmatch('[a-f0-9]{64}', row['usage_receipt_sha256'])):
            raise ValueError('invalid_owner_reconciliation')
        seen.add(key)
        total += row['remaining_future_bytes']
    if seen != set(authorities) or total > 2**63 - 1:
        raise ValueError('incomplete_accounting')
    return {'status': 'known', 'remaining_future_bytes': total,
            'snapshot_id': snapshot_id, 'snapshot_sha256': digest(document),
            'observed_at': at, 'valid_until': expires,
            'authority_set_sha256': document['authority_set_sha256']}


def load(expected, identity, now):
    try:
        # Read a bounded regular file through one descriptor; no symlink or root fallback.
        fd = os.open(expected['snapshot_path'], os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                    or info.st_mode & 0o077):
                raise ValueError('private_owner_input_required')
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise ValueError('oversized_accounting')
        return validate(json.loads(raw), expected, identity, now)
    except Exception:
        # Do not echo owner evidence, paths, raw parse errors or balances.
        return {'status': 'unknown', 'reason': 'missing_stale_or_unverified_accounting'}
