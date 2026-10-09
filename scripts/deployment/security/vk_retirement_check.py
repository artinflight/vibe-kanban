"""Stable ABI1 metadata-only proc inspector. Source only; no installation.

Root never opens artifact/lease contents, hashes them, enumerates data roots,
executes release code or accepts paths to manifests. Policy/code are root-owned.
Release manifest authenticity is live SO_PEERCRED + held FLOCK + nonce, not a
claim of independent release signing, human QA or permission to delete.
"""
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

POLICY = '/etc/vibe-kanban/process-inspection-v1.json'
CODE = '/usr/local/libexec/vk-process-inspection-v1.py'
ABI = 1
MAX_JSON = 65536
MAX_SCAN_SECONDS = 30
MAX_TARGETS = 32
IDENTITY_KEYS = {'dev', 'ino', 'size', 'mtime_ns', 'ctime_ns', 'nlink', 'uid', 'gid', 'mode'}


class Blocked(ValueError):
    pass


def require(condition):
    if not condition:
        raise Blocked('inspection blocked')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def identity(info):
    return {key: getattr(info, 'st_' + key) for key in IDENTITY_KEYS}


def hex64(value):
    return type(value) is str and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def parse_json(raw):
    require(len(raw) <= MAX_JSON)
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result)
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique)


def read_json_fd(fd):
    with os.fdopen(os.dup(fd), 'rb') as stream:
        return parse_json(stream.read(MAX_JSON + 1))


def open_path(raw, *, directory=False):
    """O_PATH handles only: no read permission, file bytes or directory listing."""
    require(type(raw) is str and raw.startswith('/') and str(Path(raw)) == raw
            and '..' not in Path(raw).parts)
    parts = Path(raw).parts[1:]
    fd = os.open('/', os.O_PATH | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for index, name in enumerate(parts):
            flags = os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC
            if index < len(parts) - 1 or directory:
                flags |= os.O_DIRECTORY
            child = os.open(name, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def trusted_path(raw):
    path = Path(raw)
    for item in [*list(path.parents)[::-1], path]:
        fd = open_path(str(item), directory=item != path)
        try:
            info = os.fstat(fd)
            require(info.st_uid == 0 and not info.st_mode & 0o022)
            require(stat.S_ISDIR(info.st_mode) if item != path else
                    stat.S_ISREG(info.st_mode) and info.st_nlink == 1)
        finally:
            os.close(fd)


def validate_request(request):
    require(type(request) is dict and set(request) == {'abi', 'nonce', 'owner_pid', 'owner_start', 'manifest'})
    require(type(request['abi']) is int and request['abi'] == ABI and hex64(request['nonce']))
    require(type(request['owner_pid']) is int and 1 < request['owner_pid'] < 2**31)
    require(type(request['owner_start']) is str and re.fullmatch(r'[0-9]{1,20}', request['owner_start']))
    manifest = request['manifest']
    require(type(manifest) is dict and set(manifest) ==
            {'scope_id', 'release_id', 'source_sha256', 'root_binding', 'backup_manifest_sha256', 'lease', 'targets'})
    require(type(manifest['scope_id']) is str and re.fullmatch(r'[a-z][a-z0-9-]{0,31}', manifest['scope_id']))
    require(type(manifest['release_id']) is str and re.fullmatch(r'[0-9a-f]{32}', manifest['release_id']))
    for field in ('source_sha256', 'root_binding', 'backup_manifest_sha256'):
        require(hex64(manifest[field]))
    def valid_identity(value):
        require(type(value) is dict and set(value) == IDENTITY_KEYS)
        require(all(type(n) is int and 0 <= n < 2**64 for n in value.values()))
    valid_identity(manifest['lease'])
    targets = manifest['targets']
    require(type(targets) is list and 0 < len(targets) <= MAX_TARGETS)
    names, inodes = set(), set()
    for target in targets:
        require(type(target) is dict and set(target) == {'name', 'identity', 'sha256', 'guard_held'})
        require(type(target['name']) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', target['name'])
                and '..' not in target['name'])
        require(target['name'] not in names and hex64(target['sha256']) and type(target['guard_held']) is bool)
        names.add(target['name'])
        valid_identity(target['identity'])
        key = (target['identity']['dev'], target['identity']['ino'])
        require(key not in inodes)
        inodes.add(key)


def validate_policy(policy):
    require(type(policy) is dict and set(policy) == {'abi', 'caller_uid', 'scopes'})
    require(type(policy['abi']) is int and policy['abi'] == ABI)
    require(type(policy['caller_uid']) is int and policy['caller_uid'] == 1000)
    require(type(policy['scopes']) is dict and 0 < len(policy['scopes']) <= 4)
    for scope_id, scope in policy['scopes'].items():
        require(re.fullmatch(r'[a-z][a-z0-9-]{0,31}', scope_id))
        require(set(scope) == {'path', 'anchor_inode', 'filesystem_uuid'})
        require(type(scope['anchor_inode']) is int and scope['anchor_inode'] > 0)
        require(type(scope['filesystem_uuid']) is str and re.fullmatch(r'[0-9a-f-]{36}', scope['filesystem_uuid']))
        require(type(scope['path']) is str and re.fullmatch(r'/mnt/vk-storage/vk-process-inspection-[a-z0-9-]{1,32}', scope['path']))


def filesystem_device(scope):
    # Fixed, root-policy selected OS device metadata; never read block contents.
    info = os.stat('/dev/disk/by-uuid/' + scope['filesystem_uuid'])
    require(stat.S_ISBLK(info.st_mode) and info.st_uid == 0)
    return info.st_rdev


def open_scope(policy, manifest):
    require(manifest['scope_id'] in policy['scopes'])
    scope = policy['scopes'][manifest['scope_id']]
    fd = open_path(scope['path'], directory=True)
    try:
        info = os.fstat(fd)
        require(info.st_uid == 0 and stat.S_IMODE(info.st_mode) == 0o755
                and info.st_ino == scope['anchor_inode'] and info.st_dev == filesystem_device(scope))
        return fd
    except BaseException:
        os.close(fd)
        raise


def relative_handle(scope_fd, parts, uid, *, directory=False):
    """No recursive paths/enumeration. Every mutable directory is private to actor."""
    fd = os.dup(scope_fd)
    device = os.fstat(scope_fd).st_dev
    try:
        for index, name in enumerate(parts):
            require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', name) and '..' not in name)
            is_dir = index < len(parts) - 1 or directory
            flags = os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC | (os.O_DIRECTORY if is_dir else 0)
            child = os.open(name, flags, dir_fd=fd)
            os.close(fd)
            fd = child
            info = os.fstat(fd)
            require(info.st_dev == device and info.st_uid == uid)
            if is_dir:
                require(stat.S_ISDIR(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o700)
            else:
                require(not stat.S_ISLNK(info.st_mode))
        return fd
    except BaseException:
        os.close(fd)
        raise


def inspect_targets(scope_fd, manifest, uid):
    targets = set()
    for target in manifest['targets']:
        fd = relative_handle(scope_fd, ('objects', manifest['release_id'], target['name']), uid)
        try:
            info = os.fstat(fd)
            require(identity(info) == target['identity'] and stat.S_ISREG(info.st_mode)
                    and info.st_nlink == 1 and stat.S_IMODE(info.st_mode) in (0o400, 0o500, 0o600, 0o700))
            targets.add((info.st_dev, info.st_ino))
        finally:
            os.close(fd)  # don't keep our own references during proc scan
    return targets



def target_guards(request):
    expected = {(target['identity']['dev'], target['identity']['ino'])
                for target in request['manifest']['targets'] if target['guard_held']}
    lines = Path('/proc/locks').read_text().splitlines()
    for device, inode in expected:
        key = f'{os.major(device):02x}:{os.minor(device):02x}:{inode}'
        rows = [line.split()[1:] for line in lines if len(line.split()) == 8 and line.split()[5] == key]
        require(rows == [['FLOCK', 'ADVISORY', 'WRITE', str(request['owner_pid']), key, '0', 'EOF']])
    return expected

def process_stat(base):
    fields = (base / 'stat').read_text().rpartition(') ')[2].split()
    require(len(fields) >= 20)
    return fields[19], fields[0], int(fields[6])


def lease_check(scope_fd, request, uid):
    manifest = request['manifest']
    fd = relative_handle(scope_fd, ('control', manifest['release_id'], 'owner.lease'), uid)
    try:
        info = os.fstat(fd)
        require(identity(info) == manifest['lease'] and stat.S_ISREG(info.st_mode)
                and info.st_nlink == 1 and stat.S_IMODE(info.st_mode) == 0o600 and info.st_size == 0)
        key = f'{os.major(info.st_dev):02x}:{os.minor(info.st_dev):02x}:{info.st_ino}'
        holders = []
        for line in Path('/proc/locks').read_text().splitlines():
            fields = line.split()
            if len(fields) == 8 and fields[5] == key:
                holders.append(fields[1:])
        require(holders == [['FLOCK', 'ADVISORY', 'WRITE', str(request['owner_pid']), key, '0', 'EOF']])
    finally:
        os.close(fd)  # no root read/open/flock of caller's lease data


def live_owner(scope_fd, request, uid):
    manifest = request['manifest']
    base = Path('/proc', str(request['owner_pid']))
    require(process_stat(base)[0] == request['owner_start'] and base.stat().st_uid == uid)
    lease_check(scope_fd, request, uid)
    parent = relative_handle(scope_fd, ('control', manifest['release_id']), uid, directory=True)
    try:
        endpoint = os.stat('owner.sock', dir_fd=parent, follow_symlinks=False)
        require(stat.S_ISSOCK(endpoint.st_mode) and endpoint.st_uid == uid
                and stat.S_IMODE(endpoint.st_mode) == 0o600)
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(2)
            client.connect(f'/proc/self/fd/{parent}/owner.sock')
            peer = struct.unpack('3i', client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            require(peer[:2] == (request['owner_pid'], uid))
            # PR231 STATUS remains the transport; manifest is authenticated in reply.
            client.sendall(b'STATUS')
            raw = b''
            while True:
                piece = client.recv(4096)
                if not piece:
                    break
                raw += piece
                require(len(raw) <= MAX_JSON)
        value = parse_json(raw)
        require(value.get('owner_pid') == request['owner_pid'] and value.get('owner_start') == request['owner_start']
                and value.get('source') == manifest['source_sha256'] and value.get('root_binding') == manifest['root_binding']
                and value.get('manifest_sha256') == manifest['backup_manifest_sha256']
                and value.get('preparation_lease_held') is True and value.get('controller_retained_alive') is True
                and value.get('operational_activation_available') is False and value.get('cleanup_available') is False
                and value.get('inspection_attestation') == {'abi': ABI, 'nonce': request['nonce'],
                                                           'manifest_sha256': digest(manifest), 'boundary_held': True})
        require(process_stat(base)[0] == request['owner_start'])
        lease_check(scope_fd, request, uid)
    finally:
        os.close(parent)


def visibility():
    # Dynamic host identity, stable across boots. Root never accepts proc/PID paths.
    for kind in ('pid', 'mnt', 'user'):
        require(os.readlink(f'/proc/self/ns/{kind}') == os.readlink(f'/proc/1/ns/{kind}'))
    require(Path('/proc/1').stat().st_uid == 0)
    mounts = [line.split() for line in Path('/proc/mounts').read_text().splitlines()]
    proc = [row for row in mounts if row[1] == '/proc']
    require(len(proc) == 1 and proc[0][2] == 'proc')
    require(not any(option.startswith(('hidepid=', 'subset=')) and option != 'hidepid=0'
                    for option in proc[0][3].split(',')))
def scan_consumers(targets, *, owner_pid=None, guards=frozenset(), proc=Path('/proc'), clock=time.monotonic):
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
                    tids = tuple((n, process_stat(base / 'task' / n)[0]) for n in
                                 sorted((n for n in os.listdir(base / 'task') if n.isdigit()), key=int))
                    require(bool(tids))
                    result[name] = (start, tids)
                except FileNotFoundError:
                    # A disappearing process makes this pass inconclusive.
                    raise Blocked('clearance blocked') from None
        return result
    first = inventory()
    require(bool(first))
    matches, tasks, guard_fds_seen = 0, 0, set()
    for pid, (_, tids) in first.items():
        for tid, expected_start in tids:
            require(clock() - started <= MAX_SCAN_SECONDS)
            base = proc / pid / 'task' / tid
            before = process_stat(base)
            require(before[0] == expected_start)
            tasks += 1
            # Kernel threads have no user file table or mm. Still inspect fd/maps.
            kernel = bool(before[2] & 0x200000)
            for kind in ('exe', 'cwd', 'root'):
                try:
                    info = (base / kind).stat()
                    matches += (info.st_dev, info.st_ino) in targets
                except FileNotFoundError:
                    require(kernel or before[1] == 'Z')
            for name in os.listdir(base / 'fd'):
                require(name.isdigit())
                try:
                    info = (base / 'fd' / name).stat()
                    key = (info.st_dev, info.st_ino)
                    if int(pid) == owner_pid and key in guards:
                        guard_fds_seen.add(key)  # only verified exact owner's FD guard
                    else:
                        matches += key in targets
                except FileNotFoundError:
                    pass  # closed FD; task start and inventory still rechecked
            with (base / 'maps').open() as stream:
                for line in stream:
                    require(len(line) <= 65536 and clock() - started <= MAX_SCAN_SECONDS)
                    fields = line.split(None, 5)
                    require(len(fields) >= 5)
                    major, minor = (int(value, 16) for value in fields[3].split(':'))
                    matches += (os.makedev(major, minor), int(fields[4])) in targets
            require(process_stat(base)[0] == before[0])
    require(inventory() == first and clock() - started <= MAX_SCAN_SECONDS)
    require(matches == 0 and guard_fds_seen == guards)
    return {'processes': len(first), 'tasks': tasks, 'matches': 0, 'inspection_denied': 0,
            'witness': [[int(pid), int(tid), start] for pid, (_, tids) in first.items() for tid, start in tids]}


def check(policy, request):
    validate_policy(policy)
    validate_request(request)
    visibility()
    scope_fd = open_scope(policy, request['manifest'])
    try:
        live_owner(scope_fd, request, policy['caller_uid'])
        targets = inspect_targets(scope_fd, request['manifest'], policy['caller_uid'])
        scanned_at, scanned_mono = time.time_ns(), time.monotonic_ns()
        guards = target_guards(request)
        result = scan_consumers(targets, owner_pid=request['owner_pid'], guards=guards)
        require(target_guards(request) == guards)
        visibility()
        live_owner(scope_fd, request, policy['caller_uid'])
        require(inspect_targets(scope_fd, request['manifest'], policy['caller_uid']) == targets)
        # Reopen the scope path to reject replacement/removal while using anchored FD.
        current = open_scope(policy, request['manifest'])
        try:
            require((os.fstat(current).st_dev, os.fstat(current).st_ino) ==
                    (os.fstat(scope_fd).st_dev, os.fstat(scope_fd).st_ino))
        finally:
            os.close(current)
        return {'abi': ABI, 'nonce': request['nonce'], 'owner_pid': request['owner_pid'],
                'owner_start': request['owner_start'], 'inspection_manifest_sha256': digest(request['manifest']),
                'scan_started_ns': scanned_at, 'issued_ns': time.time_ns(),
                'scan_started_mono_ns': scanned_mono, 'issued_mono_ns': time.monotonic_ns(),
                'euid': 0, 'consumer_clearance_passed': True, 'visibility': result,
                'target_metadata_verified': True, 'target_content_hashes_verified_by_root': False,
                'action_authorized': False, 'deletion_performed': False, 'production_changed': False}
    finally:
        os.close(scope_fd)


def main():
    try:
        require(len(sys.argv) == 1 and sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode)
        require(os.geteuid() == 0 and __file__ == CODE)
        trusted_path(CODE)
        trusted_path(os.path.realpath('/usr/bin/python3'))
        trusted_path(POLICY)
        # Only root-owned static code/policy are opened for bytes, never release inputs.
        with open(POLICY, 'rb') as stream:
            raw_policy = stream.read(MAX_JSON + 1)
        result = check(parse_json(raw_policy), read_json_fd(0))
        with open(CODE, 'rb') as stream:
            raw_code = stream.read(MAX_JSON + 1)
        require(len(raw_code) <= MAX_JSON)
        result.update(code_sha256=hashlib.sha256(raw_code).hexdigest(),
                      policy_sha256=hashlib.sha256(raw_policy).hexdigest())
        encoded = json.dumps(result, sort_keys=True)
        require(len(encoded.encode()) <= MAX_JSON)
        print(encoded)
        return 0
    except Exception:
        print('{"consumer_clearance_passed":false,"reason":"inspection blocked"}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
