"""Non-activating preparation ownership; persisted status is never liveness.

No service, SSH, restore, production fence, route or cleanup operations. The
owning caller supplies the independently verified controller/root status.
"""
import errno
import fcntl
import json
import os
from pathlib import Path
import socket
import stat
import struct

from vk_candidate_generation import require, sync_directory


def process_start(pid):
    return Path('/proc', str(pid), 'stat').read_text().rpartition(') ')[2].split()[19]


def notify(value, fd=1):
    """Best-effort diagnostic only; never buffered or used as verification."""
    payload = (json.dumps(value, sort_keys=True) + '\n').encode()
    try:
        return os.write(fd, payload) == len(payload)
    except OSError as error:
        if error.errno in (errno.EPIPE, errno.ECONNRESET, errno.EBADF):
            return False
        raise


def record_verification(state, operation, fd=1):
    """Verification/transport failures remain fatal; notification EOF does not."""
    try:
        proof = operation()
    except Exception as error:
        state.publish(phase='verification-failed', verification_completed=False,
                      error_type=type(error).__name__, error=str(error))
        notify({'phase': 'verification-failed', 'error_type': type(error).__name__}, fd)
        raise
    state.publish(phase='verified-awaiting-live-probe', verification_completed=True, **proof)
    notify({'phase': 'verified-awaiting-live-probe'}, fd)
    return proof


class PreparationLease:
    def __init__(self, path, expected, *, expected_mode=0o600):
        self.path, self.expected, self.fd = Path(path), tuple(expected), None
        require(expected_mode in (0o600, 0o664), 'unsupported recorded lease mode')
        self.expected_mode = expected_mode

    def protected_parent(self):
        parent = self.path.parent.lstat()
        require(stat.S_ISDIR(parent.st_mode) and parent.st_uid == os.getuid()
                and stat.S_IMODE(parent.st_mode) == 0o700, 'lease parent must remain private')

    def __enter__(self):
        self.protected_parent()
        info = self.path.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                and info.st_uid == os.getuid() and info.st_gid == os.getgid()
                and stat.S_IMODE(info.st_mode) == self.expected_mode
                and (info.st_dev, info.st_ino) == self.expected, 'unsafe preparation lease')
        fd = os.open(self.path, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            current = os.fstat(fd)
            require((current.st_dev, current.st_ino) == self.expected, 'lease inode changed')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            os.close(fd)
            raise
        self.fd = fd
        try:
            self.verify()
        except BaseException:
            os.close(fd)
            self.fd = None
            raise
        return self

    def verify(self):
        self.protected_parent()
        require(self.fd is not None, 'preparation ownership released')
        info, current = os.fstat(self.fd), self.path.lstat()
        require(stat.S_ISREG(current.st_mode) and current.st_nlink == 1
                and current.st_uid == os.getuid() and current.st_gid == os.getgid()
                and stat.S_IMODE(current.st_mode) == self.expected_mode
                and (info.st_dev, info.st_ino) == (current.st_dev, current.st_ino) == self.expected,
                'preparation lease binding changed')
        probe = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            try:
                fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            raise ValueError('preparation lease is no longer held')
        finally:
            os.close(probe)

    def __exit__(self, *args):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


class PreparationState:
    def __init__(self, path, initial):
        self.path, self.value = Path(path), dict(initial)
        require(not self.path.exists() and not self.path.is_symlink(), 'preserve prior owner state')
        self.value.update(owner_pid=os.getpid(), owner_start=process_start(os.getpid()),
                          controller_retained_alive=False, requires_live_owner_probe=True)
        self.publish()

    def publish(self, **values):
        self.value.update(values)
        # This describes a durable result, not an assertion that its process
        # survives. Even SIGKILL cannot leave a persisted true liveness claim.
        self.value.update(controller_retained_alive=False, requires_live_owner_probe=True)
        temporary = self.path.with_name(self.path.name + '.next')
        with temporary.open('x') as stream:
            json.dump(self.value, stream, sort_keys=True, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.path)
        sync_directory(self.path.parent)


class PreparationStatus:
    def __init__(self, path, lease, status):
        self.path, self.lease, self.status = Path(path), lease, status
        require(not self.path.exists() and not self.path.is_symlink(), 'preserve prior status endpoint')
        self.socket = socket.socket(socket.AF_UNIX)
        self.socket.bind(str(self.path))
        os.chmod(self.path, 0o600)
        self.socket.listen(8)

    def serve_once(self):
        conn, _ = self.socket.accept()
        with conn:
            conn.settimeout(2)
            try:
                request = conn.recv(128)
                if request != b'STATUS':
                    value = {'held': True, 'reason': 'non-activating status only'}
                else:
                    self.lease.verify()
                    value = {**self.status(), 'owner_pid': os.getpid(),
                             'owner_start': process_start(os.getpid()),
                             'controller_retained_alive': True, 'preparation_lease_held': True,
                             'operational_activation_available': False, 'cleanup_available': False}
                conn.sendall(json.dumps(value, sort_keys=True).encode())
            except (BrokenPipeError, ConnectionResetError, socket.timeout):
                # Closing an SSH/client connection does not release ownership.
                pass

    def close(self):
        self.socket.close()  # Keep the path as retained evidence, never unlink.


def probe(path, pid, start, *, root_binding, source):
    """Authenticate a fresh live response, never the persisted alive field."""
    require(process_start(pid) == start, 'owner process identity changed')
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(2)
        client.connect(str(path))
        peer_pid, peer_uid, _ = struct.unpack('3i', client.getsockopt(
            socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize('3i')))
        require(peer_pid == pid and peer_uid == os.getuid(), 'status peer identity mismatch')
        client.sendall(b'STATUS')
        pieces, total = [], 0
        while True:
            piece = client.recv(4096)
            if not piece:
                break
            total += len(piece)
            require(total <= 65536, 'oversized preparation status')
            pieces.append(piece)
    value = json.loads(b''.join(pieces))
    require(process_start(pid) == start and value.get('owner_pid') == pid
            and value.get('owner_start') == start and value.get('root_binding') == root_binding
            and value.get('source') == source and value.get('preparation_lease_held') is True
            and value.get('controller_retained_alive') is True
            and value.get('operational_activation_available') is False
            and value.get('cleanup_available') is False, 'live preparation owner binding mismatch')
    return value
