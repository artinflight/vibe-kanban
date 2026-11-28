"""Source-bound finite RPC transport for the existing metadata observer.

The observer protocol and every returned coverage/error/sequence field remain
unchanged. This only authenticates the Unix peer and bounds the client wait.
It never opens the live SQLite spool, starts a listener or restarts a process.
"""
from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import socket
import stat
import struct
import time


def birth(pid):
    return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])


class TrackingClient:
    def __init__(self, module, *, endpoint, instance, owner_pid, owner_start_ticks,
                 owner_uid, timeout_seconds=90, guard):
        if (type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds)
                or not 0 < timeout_seconds <= 120):
            raise ValueError('Finite admitted observer response wait required')
        self.module = module
        self.endpoint = Path(endpoint)
        self.instance = instance
        self.owner = owner_pid, owner_start_ticks, owner_uid
        self.timeout = timeout_seconds
        self.guard = guard

    def check(self):
        self.guard()
        pid, start, uid = self.owner
        path = self.endpoint
        info = path.lstat()
        if (path.resolve() != path or not stat.S_ISSOCK(info.st_mode)
                or info.st_uid != uid or info.st_mode & 0o077 or birth(pid) != start):
            raise ValueError('Exact owned observer endpoint/process required')
        return info.st_dev, info.st_ino

    def query(self, endpoint, value):
        if Path(endpoint) != self.endpoint or value.get('instance') != self.instance:
            raise ValueError('Request differs from the bound observer')
        identity = self.check()
        started = time.monotonic()
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(self.timeout)
            client.connect(str(self.endpoint))
            pid, uid, _ = struct.unpack('3i', client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            if (pid, uid) != (self.owner[0], self.owner[2]):
                raise ValueError('Observer socket peer differs')
            raw = self.module.canonical(value)
            if len(raw) > 4096:
                raise ValueError('Observer request exceeds existing protocol bound')
            client.sendall(raw)
            blocks = []
            size = 0
            while True:
                self.guard()
                remaining = self.timeout - (time.monotonic() - started)
                if remaining <= 0:
                    raise TimeoutError('Admitted observer response time exceeded')
                client.settimeout(remaining)
                block = client.recv(65536)
                if not block:
                    break
                size += len(block)
                if size > self.module.MAX_RESPONSE:
                    raise ValueError('Complete bounded tracking response required')
                blocks.append(block)
        if self.check() != identity:
            raise ValueError('Observer endpoint changed during response')
        result = json.loads(b''.join(blocks))
        if 'request_error' in result:
            message = result['request_error']
            prefix = 'retained B journal prefix required through '
            if isinstance(message, str) and message.startswith(prefix):
                number = message[len(prefix):]
                if number.isascii() and number.isdecimal() and len(number) <= 19:
                    raise self.module.RetainedPrefixRequired(int(number))
            raise ValueError(message)
        return result


@contextmanager
def installed(module, client):
    """Explicit trusted single-controller adaptation; restore on every exit.

    The release must pin this adapter and declare its runtime use separately
    from the unchanged Nightly source files. This is not an acceptance adapter.
    """
    if client.module is not module:
        raise ValueError('Observer module binding differs')
    original = module.query
    bound = client.query
    module.query = bound
    try:
        yield client
    finally:
        if module.query is not bound:
            raise ValueError('Concurrent observer transport replacement detected')
        module.query = original


def deliver_when_ready(source, client, *, maximum_seconds=90, on_wait=lambda _: None,
                       clock=time.monotonic, sleep=time.sleep):
    """Wait for genuine inode enrollment completion; never rewrite readiness.

    Atomic file replacement can leave pending inode enrollment momentarily.
    A real error, changed epoch/root/owner, terminal state or expired admission
    still aborts. Only the exact source-ready race is retried, before any body
    work; every successful delivery retains the normal B reopen and nonce ACK.
    """
    if not 0 < maximum_seconds <= 120:
        raise ValueError('Finite source-ready wait required')
    module = client.module
    if (client.instance != source.reference['instance']
            or client.endpoint != Path(source.config['endpoint'])):
        raise ValueError('Exact source/client binding required')
    deadline = clock() + maximum_seconds
    original_timeout = client.timeout

    def health():
        client.check()
        path = Path(source.config['status'])
        info = path.lstat()
        if (path.resolve() != path or not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid() or info.st_mode & 0o022):
            raise ValueError('Owned exact source health required')
        with path.open('rb') as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise ValueError('Bounded source health required')
        value = json.loads(raw)
        if (value.get('phase') != 'tracking' or value.get('raw_errors')
                or value.get('instance') != client.instance
                or (value.get('owner_pid'), value.get('owner_start_ticks')) != client.owner[:2]
                or value.get('plan_sha256') != module.identity(source.plan)
                or value.get('scope_sha256') != module.identity(module.scope(source.plan))
                or value.get('coverage_model') != 'all-selected-inodes-v1'
                or set(value.get('required_root_bindings', {})) != set(source.plan['sources'])
                or not 0 <= time.time() - value['heartbeat_utc'] <= 90):
            raise ValueError('Source fault, changed binding or stale heartbeat; no readiness retry')
        return value

    try:
        with installed(module, client):
            while True:
                left = deadline - clock()
                if left <= 0:
                    raise TimeoutError('Genuine source readiness did not arrive within admission')
                client.timeout = min(original_timeout, left)
                observed = health()
                report = module.request(client.endpoint, client.instance, observed['sequence'], barrier=True)
                if (report.get('errors') or report.get('terminal')
                        or report.get('instance') != client.instance
                        or report.get('plan_sha256') != observed['plan_sha256']
                        or report.get('scope_sha256') != observed['scope_sha256']
                        or report.get('coverage_model') != 'all-selected-inodes-v1'):
                    raise ValueError('Actual source barrier has a fault or changed binding')
                if report.get('ready') is True and observed.get('ready') is True:
                    try:
                        source.check()
                        result = source.deliver()
                    except ValueError as error:
                        if str(error) not in ('complete actual barrier required for delivery',
                                               'current exact healthy source owner required'):
                            raise
                        # Re-read actual health/barrier on the next pass. Never
                        # reinterpret a native drive, ownership or access error.
                        on_wait({'reason': str(error), 'actual_ready': report['ready'],
                                 'instance': client.instance})
                    else:
                        if clock() > deadline:
                            raise TimeoutError('Source delivery completed after readiness admission')
                        return result
                else:
                    on_wait({'reason': 'actual source inode enrollment not yet ready',
                             'actual_ready': report.get('ready'), 'instance': client.instance})
                sleep(max(0, min(.25, deadline - clock())))
    finally:
        client.timeout = original_timeout


@contextmanager
def metadata_lane(path):
    """Serialize one Staging metadata follower with the final update owner.

    Opens an existing private task lease only. No polling, file creation or
    producer restart; contention returns to the current owner unchanged.
    """
    import fcntl
    path = Path(path)
    if path.resolve() != path or not path.is_relative_to('/mnt/vk-storage'):
        raise ValueError('Canonical SSD task metadata lane required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_nlink != 1 or info.st_mode & 0o077):
            raise ValueError('Existing private owned metadata lane required')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)
