"""Fixed-policy, read-only root checker. Install only after explicit approval.

Run only via /usr/bin/python3 -I -B <installed file>, with no script arguments.
No repo imports, commands, path arguments, environment credentials or writes.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import struct
import sys
import time

POLICY = '/etc/vibe-kanban/retirement-policy.json'
CODE = '/usr/local/libexec/vk-retirement-check.py'
MAX_JSON = 65536
MAX_SCAN_SECONDS = 30
LEASE_PATH = '/mnt/vk-storage/vk-cutover-candidate-20261009/initial-restore-owner.lease'
OWNER_ENDPOINT = '/mnt/vk-storage/vk-cutover-candidate-20261009/owner-097e1bfa.sock'
APPROVED_TARGET = {
    'id': 'incident-archive-db5bb16b',
    'path': '/mnt/vk-storage/vk-combined-preparation-20261007/backups/checkpoint-/db5bb16b095241319a79e02e5fc8cdf6/checkpoint--db5bb16b095241319a79e02e5fc8cdf6.tar.zst',
    'sha256': 'e994567edaacc75d8aa9a3497b8384a8dbacec462854a3f7f8c5760e1a9a0ce4',
    'identity': {'dev': 2065, 'ino': 7340415, 'size': 23441521918,
                 'mtime_ns': 1791409456129506845, 'ctime_ns': 1791409456129506845,
                 'nlink': 1, 'uid': 1000, 'gid': 1000, 'mode': 0o100600},
}


class Blocked(ValueError):
    pass


def require(condition):
    if not condition:
        raise Blocked('clearance blocked')


def identity(info):
    return {key: getattr(info, 'st_' + key) for key in
            ('dev', 'ino', 'size', 'mtime_ns', 'ctime_ns', 'nlink', 'uid', 'gid', 'mode')}


def open_path(raw, *, directory=False):
    """Walk every component using anchored O_NOFOLLOW directory descriptors."""
    require(isinstance(raw, str) and raw.startswith('/') and
            str(Path(raw)) == raw and '..' not in Path(raw).parts)
    parts = Path(raw).parts[1:]
    require(bool(parts))
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for index, name in enumerate(parts):
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
            if index < len(parts) - 1 or directory:
                flags |= os.O_DIRECTORY
            child = os.open(name, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def trusted_path(raw, *, directory=False):
    """Code/config and all their ancestors must be root-owned and immutable to mcp."""
    path = Path(raw)
    for item in [Path('/'), *list(path.parents)[::-1], path]:
        fd = open_path(str(item), directory=item != path or directory) if str(item) != '/' else os.open('/', os.O_RDONLY | os.O_DIRECTORY)
        try:
            info = os.fstat(fd)
            require(info.st_uid == 0 and not info.st_mode & 0o022)
            require(stat.S_ISDIR(info.st_mode) if item != path or directory else
                    stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
        finally:
            os.close(fd)


def read_json_fd(fd):
    with os.fdopen(os.dup(fd), 'rb') as stream:
        raw = stream.read(MAX_JSON + 1)
    require(len(raw) <= MAX_JSON)
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result)
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique)


def validate_request(request):
    require(type(request) is dict and set(request) ==
            {'target_id', 'nonce', 'owner_pid', 'owner_start', 'manifest_sha256'})
    require(request['target_id'] == 'incident-archive-db5bb16b')
    require(type(request['owner_pid']) is int and 1 < request['owner_pid'] < 2**31)
    require(type(request['owner_start']) is str and re.fullmatch(r'[0-9]{1,20}', request['owner_start']))
    for field in ('nonce', 'manifest_sha256'):
        require(type(request[field]) is str and re.fullmatch(r'[0-9a-f]{64}', request[field]))


def process_stat(base):
    fields = (base / 'stat').read_text().rpartition(') ')[2].split()
    require(len(fields) >= 20)
    return fields[19], fields[0], int(fields[6])  # start, state, flags


def lease_check(policy, request):
    lease = policy['lease']
    fd = open_path(lease['path'])
    try:
        info = os.fstat(fd)
        require(identity(info) == lease['identity'] and stat.S_ISREG(info.st_mode))
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            pass
        else:
            raise Blocked('clearance blocked')
        key = f"{os.major(info.st_dev):02x}:{os.minor(info.st_dev):02x}:{info.st_ino}"
        holders = []
        for line in Path('/proc/locks').read_text().splitlines():
            fields = line.split()
            if len(fields) == 8 and fields[5] == key:
                holders.append(fields[1:])
        require(holders == [['FLOCK', 'ADVISORY', 'WRITE', str(request['owner_pid']), key, '0', 'EOF']])
    finally:
        os.close(fd)


def live_owner(policy, request):
    owner = policy['owner']
    base = Path('/proc', str(request['owner_pid']))
    require(process_stat(base)[0] == request['owner_start'])
    require(base.stat().st_uid == policy['caller_uid'])
    lease_check(policy, request)
    # Reject endpoint/ancestor substitution. Socket is user-owned, never executed.
    parent_fd = open_path(str(Path(owner['endpoint']).parent), directory=True)
    try:
        parent = os.fstat(parent_fd)
        require(parent.st_uid == policy['caller_uid'] and stat.S_IMODE(parent.st_mode) == 0o700)
        endpoint = os.stat(Path(owner['endpoint']).name, dir_fd=parent_fd, follow_symlinks=False)
        require(stat.S_ISSOCK(endpoint.st_mode) and endpoint.st_uid == policy['caller_uid']
                and stat.S_IMODE(endpoint.st_mode) == 0o600)
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(2)
            # Anchored parent avoids symlink traversal between validation/connect.
            client.connect(f'/proc/self/fd/{parent_fd}/{Path(owner["endpoint"]).name}')
            peer = struct.unpack('3i', client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            require(peer[:2] == (request['owner_pid'], policy['caller_uid']))
            client.sendall(b'STATUS')
            pieces, total = [], 0
            while True:
                piece = client.recv(4096)
                if not piece:
                    break
                total += len(piece)
                require(total <= MAX_JSON)
                pieces.append(piece)
        value = json.loads(b''.join(pieces))
        require(value.get('owner_pid') == request['owner_pid'] and value.get('owner_start') == request['owner_start']
                and value.get('source') == owner['source'] and value.get('root_binding') == owner['root_binding']
                and value.get('manifest_sha256') == request['manifest_sha256'] == owner['manifest_sha256']
                and value.get('preparation_lease_held') is True and value.get('controller_retained_alive') is True
                and value.get('operational_activation_available') is False and value.get('cleanup_available') is False
                and value.get('retirement_boundary') == {'nonce': request['nonce'], 'target_id': request['target_id']})
        require(process_stat(base)[0] == request['owner_start'])
        lease_check(policy, request)
    finally:
        os.close(parent_fd)


def visibility(policy):
    require(os.stat('/proc').st_dev == policy['proc_dev'])
    for kind in ('pid', 'mnt'):
        expected = policy['namespaces'][kind]
        require(os.readlink(f'/proc/self/ns/{kind}') == os.readlink(f'/proc/1/ns/{kind}') == expected)
    mounts = [line.split() for line in Path('/proc/mounts').read_text().splitlines()]
    proc = [row for row in mounts if row[1] == '/proc']
    require(len(proc) == 1 and proc[0][2] == 'proc')
    require(not any(option.startswith(('hidepid=', 'subset=')) and option not in ('hidepid=0',)
                    for option in proc[0][3].split(',')))


def scan_consumers(target, *, proc=Path('/proc'), clock=time.monotonic):
    """Inspect all tasks, never emit names/maps/FD destinations or memory contents.

    A stable second enumeration detects births/PID reuse; any churn blocks.
    Kernel tasks are classified by PF_KTHREAD, never by name/UID heuristics.
    """
    started = clock()
    def inventory():
        result = {}
        for name in os.listdir(proc):
            if name.isdigit():
                base = proc / name
                try:
                    start = process_stat(base)[0]
                    tids = tuple(sorted((n for n in os.listdir(base / 'task') if n.isdigit()), key=int))
                    require(bool(tids))
                    result[name] = (start, tids)
                except FileNotFoundError:
                    # A disappearing process makes this pass inconclusive.
                    raise Blocked('clearance blocked') from None
        return result
    first = inventory()
    require(bool(first))
    matches, tasks = 0, 0
    for pid, (_, tids) in first.items():
        for tid in tids:
            require(clock() - started <= MAX_SCAN_SECONDS)
            base = proc / pid / 'task' / tid
            before = process_stat(base)
            tasks += 1
            # Kernel threads have no user file table or mm. Still inspect fd/maps.
            kernel = bool(before[2] & 0x200000)
            for kind in ('exe', 'cwd', 'root'):
                try:
                    info = (base / kind).stat()
                    matches += (info.st_dev, info.st_ino) == target
                except FileNotFoundError:
                    require(kernel or before[1] == 'Z')
            for name in os.listdir(base / 'fd'):
                require(name.isdigit())
                try:
                    info = (base / 'fd' / name).stat()
                    matches += (info.st_dev, info.st_ino) == target
                except FileNotFoundError:
                    pass  # closed FD; task start and inventory still rechecked
            with (base / 'maps').open() as stream:
                for line in stream:
                    require(len(line) <= 65536 and clock() - started <= MAX_SCAN_SECONDS)
                    fields = line.split(None, 5)
                    require(len(fields) >= 5)
                    major, minor = (int(value, 16) for value in fields[3].split(':'))
                    matches += (os.makedev(major, minor), int(fields[4])) == target
            require(process_stat(base)[0] == before[0])
    require(inventory() == first and clock() - started <= MAX_SCAN_SECONDS)
    require(matches == 0)
    return {'processes': len(first), 'tasks': tasks, 'matches': 0, 'inspection_denied': 0}


def target_check(fd, policy):
    require(identity(os.fstat(fd)) == policy['target']['identity'])
    current = open_path(policy['target']['path'])
    try:
        require(identity(os.fstat(current)) == policy['target']['identity'])
    finally:
        os.close(current)


def check(policy, request):
    validate_request(request)
    require(set(policy) == {'schema', 'caller_uid', 'target', 'owner', 'lease', 'proc_dev', 'namespaces'})
    require(policy['schema'] == 1 and policy['caller_uid'] == 1000)
    require(policy['target'] == APPROVED_TARGET)
    require(request['target_id'] == policy['target']['id'])
    require(set(policy['owner']) == {'endpoint', 'source', 'root_binding', 'manifest_sha256'})
    require(set(policy['lease']) == {'path', 'identity'})
    require(policy['lease']['path'] == LEASE_PATH and policy['owner']['endpoint'] == OWNER_ENDPOINT)
    for field in ('source', 'root_binding', 'manifest_sha256'):
        require(re.fullmatch(r'[0-9a-f]{64}', policy['owner'][field]))
    visibility(policy)
    live_owner(policy, request)
    fd = open_path(policy['target']['path'])
    try:
        target_check(fd, policy)
        require(stat.S_ISREG(os.fstat(fd).st_mode) and os.fstat(fd).st_nlink == 1)
        # Hash before consumer scan, so long preparation cannot age the receipt.
        digest = hashlib.sha256()
        with os.fdopen(os.dup(fd), 'rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        require(digest.hexdigest() == policy['target']['sha256'])
        target_check(fd, policy)
    finally:
        os.close(fd)  # our own reference must not mask an external consumer
    scanned_at = time.time_ns()
    scanned_mono = time.monotonic_ns()
    result = scan_consumers((policy['target']['identity']['dev'], policy['target']['identity']['ino']))
    visibility(policy)
    live_owner(policy, request)
    fd = open_path(policy['target']['path'])
    try:
        target_check(fd, policy)
    finally:
        os.close(fd)
    return {'schema': 1, **request, 'source': policy['owner']['source'],
            'root_binding': policy['owner']['root_binding'], 'lease': policy['lease']['identity'],
            'target': policy['target'], 'scan_started_ns': scanned_at, 'issued_ns': time.time_ns(),
            'scan_started_mono_ns': scanned_mono, 'issued_mono_ns': time.monotonic_ns(),
            'euid': 0, 'consumer_clearance_passed': True, 'deletion_performed': False,
            'production_changed': False, 'visibility': result}


def main():
    try:
        require(len(sys.argv) == 1 and sys.flags.isolated and sys.flags.dont_write_bytecode)
        require(os.geteuid() == 0 and os.environ.get('SUDO_UID') == '1000')
        # Python's -I ignores caller sys.path/PYTHONPATH; no local imports.
        require(__file__ == CODE)
        trusted_path(CODE)
        trusted_path('/usr/bin/python3.12')
        trusted_path(POLICY)
        fd = open_path(POLICY)
        try:
            policy = read_json_fd(fd)
        finally:
            os.close(fd)
        request = read_json_fd(0)
        result = check(policy, request)
        for key, path in (('code_sha256', CODE), ('policy_sha256', POLICY)):
            fd = open_path(path)
            try:
                with os.fdopen(os.dup(fd), 'rb') as stream:
                    result[key] = hashlib.sha256(stream.read(MAX_JSON + 1)).hexdigest()
            finally:
                os.close(fd)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception:
        # Do not leak protected paths, maps, command lines or exception details.
        print('{"consumer_clearance_passed":false,"reason":"clearance blocked"}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
