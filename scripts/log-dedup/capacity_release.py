"""Recover a lost capacity-release reply without guessing ownership.

The status route intentionally returns null state after release. Persist the
complete intent before the RPC, then verify durable state under the real lock.
No retries, state rewrites, service actions or implicit maintenance release.
"""
import copy
import fcntl
import json
import os
from pathlib import Path
import stat


def _owned_file(path):
    path = Path(path)
    if not path.is_absolute() or path.resolve(strict=True) != path:
        raise ValueError('Literal capacity file path required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_nlink != 1 or info.st_mode & 0o022):
            raise ValueError('Unique owned capacity file required')
        return fd
    except BaseException:
        os.close(fd)
        raise


def _identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _request(boundary, action='status', state=None):
    return boundary.rpc.request('http://127.0.0.1:5621',
                                Path(boundary.config['capacity_token']), action, state)


def _drained(state):
    if (not isinstance(state, dict) or state.get('version') != 1
            or not isinstance(state.get('epoch'), str) or not state['epoch']
            or type(state.get('revision')) is not int or state['revision'] < 0
            or not isinstance(state.get('goals'), dict)
            or not isinstance(state.get('issuedIds'), list)
            or any(not isinstance(goal, dict) or goal.get('grant') is not None
                   for goal in state['goals'].values())):
        raise ValueError('Complete drained capacity state required')


def reconcile(boundary):
    """Record release only after authenticated status and locked durable proof.

    May run after worker death using its saved intent. Unknown owners, changed
    state, busy/replaced locks or unavailable API leave maintenance in place.
    """
    intent = boundary.data.get('capacity_release_intent')
    if intent is None:
        raise ValueError('No durable capacity release intent; retain maintenance')
    expected = intent['state']
    _drained(expected)
    boundary.owner_guard()
    boundary.original_check()
    observed = _request(boundary)
    if (observed.get('protocolVersion') != 1 or observed.get('owned') is not False
            or observed.get('state') is not None):
        raise ValueError('Capacity release unresolved or foreign owner; retain maintenance')
    lock_path = Path(boundary.config['capacity_lock'])
    fd = _owned_file(lock_path)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_identity = list(_identity(os.fstat(fd))[:2])
        if lock_identity != intent['lock_identity']:
            raise ValueError('Capacity lock changed since release intent')
        state_fd = _owned_file(boundary.config['capacity_state'])
        with os.fdopen(state_fd, 'rb') as stream:
            before = os.fstat(stream.fileno())
            persisted = json.load(stream)
            after = os.fstat(stream.fileno())
        if (_identity(before) != _identity(after)
                or _identity(after) != _identity(Path(boundary.config['capacity_state']).lstat())
                or persisted.get('version') != boundary.config['capacity_persisted_version']
                or dict(persisted, version=1) != expected):
            raise ValueError('Released capacity epoch/revision/history changed')
        if lock_identity != list(_identity(lock_path.lstat())[:2]):
            raise ValueError('Capacity lock replaced during reconciliation')
        boundary.owner_guard()
        boundary.original_check()
        receipt = dict(protocolVersion=1, owned=False, state=copy.deepcopy(expected),
                       reconciled_under_capacity_lock=True)
        boundary.data['released'] = receipt
        boundary.record('authenticated_capacity_release_reconciled')
        return receipt
    finally:
        os.close(fd)


def release(boundary, status):
    if status.get('protocolVersion') != 1 or status.get('owned') is not True:
        raise ValueError('Authenticated capacity owner required')
    state = status.get('state')
    _drained(state)
    if boundary.data.get('capacity_release_intent') is not None:
        raise ValueError('Existing release intent must be reconciled, never replayed')
    fd = _owned_file(boundary.config['capacity_lock'])
    try:
        identity = list(_identity(os.fstat(fd))[:2])
    finally:
        os.close(fd)
    boundary.data['capacity_release_intent'] = dict(state=copy.deepcopy(state),
                                                   lock_identity=identity)
    boundary.record('releasing_authenticated_capacity')
    try:
        receipt = _request(boundary, 'release', state)
    except Exception:
        return reconcile(boundary)
    if (receipt.get('protocolVersion') != 1 or receipt.get('owned') is not False
            or receipt.get('state') != state):
        raise ValueError('Unexpected capacity release response; retain intent for recovery')
    boundary.data['released'] = receipt
    boundary.record('authenticated_capacity_released')
    return receipt
