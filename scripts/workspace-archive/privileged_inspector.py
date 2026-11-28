"""Root-installed metadata-only process visibility for workspace archival.

Reads process metadata and enumerates only caller-owned payload metadata under
root-configured, inode-bound scope roots. It never opens payload contents, changes
permissions, stops processes, deletes files, writes SQL or grants archive approval.
The launcher and this module/policy are installed only by the external manager.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
import uuid

CODE = '/usr/local/libexec/vk-workspace-archive-inspection-v1.py'
POLICY = '/etc/vibe-kanban/workspace-archive-inspection-v1.json'
MAX_INPUT = 32 * 1024**2


def require(value):
    if not value:
        raise ValueError('process inspection held')


def identity(st):
    return (st.st_dev, st.st_ino)


def birth(base):
    fields = (base / 'stat').read_text().rsplit(')', 1)[1].split()
    return fields[19], fields[0], int(fields[1]), int(fields[6])


def no_alias(path):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts and path.resolve(strict=True) == path)
    return path


def trusted(path):
    path = no_alias(path)
    for part in (path, *path.parents):
        info = part.lstat()
        require(info.st_uid == 0 and not info.st_mode & 0o022)
    require(path.is_file() and path.stat().st_nlink == 1)
    return path


def roots(policy):
    require(policy['abi'] == 1 and type(policy['caller_uid']) is int and policy['caller_uid'] > 0)
    result = []
    for row in policy['scopes']:
        path = no_alias(row['path'])
        st = path.lstat()
        require(path.is_dir() and st.st_uid == policy['caller_uid'] and list(identity(st)) == row['identity'])
        result.append(path)
    require(result)
    return result


def held(policy, request):
    pid, uid = request['owner_pid'], policy['caller_uid']
    require(type(pid) is int and pid > 1)
    base = Path('/proc') / str(pid)
    require(base.stat().st_uid == uid and birth(base)[0] == request['owner_start'])
    workspace = str(uuid.UUID(request['workspace_id']))
    require(workspace == request['workspace_id'])
    row = policy['custody_root']
    root = no_alias(row['path'])
    info = root.stat()
    require(identity(info) == tuple(row['identity']) and info.st_uid == uid and stat.S_IMODE(info.st_mode) == 0o700)
    lock = root / (workspace + '.lock')
    info = lock.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == uid and info.st_nlink == 1
            and stat.S_IMODE(info.st_mode) == 0o600)
    key = f'{os.major(info.st_dev):02x}:{os.minor(info.st_dev):02x}:{info.st_ino}'
    rows = [line.split()[1:] for line in Path('/proc/locks').read_text().splitlines()
            if len(line.split()) == 8 and line.split()[5] == key]
    require(rows == [['FLOCK', 'ADVISORY', 'WRITE', str(pid), key, '0', 'EOF']])


def unique_json(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result)
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs)


def directory(path):
    """Open every component without following links, including scoped parents."""
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts)
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for name in path.parts[1:]:
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def collect(policy, request, deadline):
    allowed, uid = roots(policy), policy['caller_uid']
    require(isinstance(request['roots'], list) and bool(request['roots']))
    selected = set()
    devices = {path.stat().st_dev for path in allowed}

    def visit(parent, name, device, depth=0):
        require(time.monotonic() < deadline and depth < 256)
        info = os.stat(name, dir_fd=parent, follow_symlinks=False)
        require(info.st_uid == uid and info.st_dev == device)
        selected.add(identity(info))
        require(len(selected) <= 1000000)
        if stat.S_ISDIR(info.st_mode):
            fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            try:
                require(identity(os.fstat(fd)) == identity(info))
                for child in os.listdir(fd):
                    visit(fd, child, device, depth + 1)
                after = os.fstat(fd)
                require((after.st_mtime_ns, after.st_ctime_ns) == (info.st_mtime_ns, info.st_ctime_ns))
            finally:
                os.close(fd)
            require(identity(os.stat(name, dir_fd=parent, follow_symlinks=False)) == identity(info))

    for raw in request['roots']:
        path = Path(raw)
        require(str(path) == raw and path.is_absolute() and '..' not in path.parts)
        matches = [root for root in allowed if root in path.parents]
        require(matches)
        scope = max(matches, key=lambda root: len(root.parts))
        binding = next(row for row in policy['scopes'] if row['path'] == str(scope))
        fd = directory(scope)
        try:
            require(list(identity(os.fstat(fd))) == binding['identity'])
            parts = path.relative_to(scope).parts
            missing = False
            for name in parts[:-1]:
                try:
                    child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                except FileNotFoundError:
                    missing = True
                    break
                os.close(fd)
                fd = child
                info = os.fstat(fd)
                require(info.st_uid == uid and info.st_dev == scope.stat().st_dev)
            if not missing:
                try:
                    info = os.stat(parts[-1], dir_fd=fd, follow_symlinks=False)
                except FileNotFoundError:
                    continue
                require(not stat.S_ISLNK(info.st_mode))
                visit(fd, parts[-1], scope.stat().st_dev)
        finally:
            os.close(fd)
    # Journal inode identities detect deleted/renamed open files. They can only
    # add a hold and must belong to a configured source filesystem. No process
    # names, paths or contents are returned for them.
    require(isinstance(request['identities'], list) and len(request['identities']) <= 1000000)
    for pair in request['identities']:
        require(isinstance(pair, list) and len(pair) == 2
                and all(type(n) is int and n > 0 for n in pair) and pair[0] in devices)
        selected.add(tuple(pair))
    return selected


def scan(targets, owner_pid, deadline, proc=Path('/proc')):
    # Each task is inspected independently; the exit of one thread must not
    # skip the still-live threads of the same process.
    inspected = 0
    for process in proc.iterdir():
        if not process.name.isdecimal():
            continue
        try:
            tasks = list((process / 'task').iterdir())
        except (FileNotFoundError, ProcessLookupError):
            continue
        for task in tasks:
            try:
                require(time.monotonic() < deadline)
                before = birth(task)
                kernel = bool(before[3] & 0x200000)
                for name in ('cwd', 'exe', 'root'):
                    try:
                        require(identity((task / name).stat()) not in targets)
                    except FileNotFoundError:
                        require(kernel or before[1] == 'Z' or not task.exists())
                for fd in (task / 'fd').iterdir():
                    try:
                        require(identity(fd.stat()) not in targets)
                    except FileNotFoundError:
                        continue
                with (task / 'maps').open() as maps:
                    while row := maps.readline(65537):
                        require(len(row) <= 65536 and time.monotonic() < deadline)
                        fields = row.split(None, 5)
                        require(len(fields) >= 5)
                        major, minor = (int(v, 16) for v in fields[3].split(':'))
                        require((os.makedev(major, minor), int(fields[4])) not in targets)
                require(birth(task)[0] == before[0])
                inspected += 1
            except (FileNotFoundError, ProcessLookupError):
                require(not task.exists())
    return inspected


def inspect(policy, request):
    require(set(request) == {'abi', 'nonce', 'owner_pid', 'owner_start', 'workspace_id', 'roots', 'identities'})
    require(request['abi'] == 1 and len(bytes.fromhex(request['nonce'])) == 32)
    # The real helper must share the host's namespaces and full proc visibility.
    for kind in ('pid', 'mnt', 'user'):
        require(os.readlink('/proc/self/ns/' + kind) == os.readlink('/proc/1/ns/' + kind))
    mounts = [line.split() for line in Path('/proc/mounts').read_text().splitlines()]
    proc = [row for row in mounts if row[1] == '/proc']
    require(len(proc) == 1 and proc[0][2] == 'proc')
    require(not any(option.startswith(('hidepid=', 'subset=')) and option != 'hidepid=0'
                    for option in proc[0][3].split(',')))
    held(policy, request)
    deadline = time.monotonic() + 60
    target = collect(policy, request, deadline)
    count = scan(target, request['owner_pid'], deadline)
    held(policy, request)
    require(collect(policy, request, deadline) == target)
    return dict(abi=1, nonce=request['nonce'], owner_pid=request['owner_pid'], owner_start=request['owner_start'],
                consumer_clearance_passed=True, production_changed=False, inspected_tasks=count,
                issued_mono_ns=time.monotonic_ns(), euid=os.geteuid())


def main():
    try:
        require(len(sys.argv) == 1 and sys.flags.isolated and sys.flags.no_site
                and sys.flags.dont_write_bytecode and os.geteuid() == 0 and __file__ == CODE)
        trusted(CODE); trusted(POLICY); trusted(os.path.realpath('/usr/bin/python3'))
        policy_raw = Path(POLICY).read_bytes()
        policy = unique_json(policy_raw)
        raw = sys.stdin.buffer.read(MAX_INPUT + 1)
        require(len(raw) <= MAX_INPUT)
        request = unique_json(raw)
        # Only the currently held owner or its sudo child chain may request a
        # receipt. This grants no generic root execution or payload read access.
        ancestor = os.getppid()
        for _ in range(8):
            if ancestor == request['owner_pid']:
                break
            ancestor = birth(Path('/proc') / str(ancestor))[2]
        require(ancestor == request['owner_pid'])
        result = inspect(policy, request)
        result.update(request_sha256=hashlib.sha256(raw).hexdigest(),
                      code_sha256=hashlib.sha256(Path(CODE).read_bytes()).hexdigest(),
                      policy_sha256=hashlib.sha256(policy_raw).hexdigest())
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception:
        print('{"consumer_clearance_passed":false,"production_changed":false}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
