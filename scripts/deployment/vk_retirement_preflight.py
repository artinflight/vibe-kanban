"""ABI1 unprivileged release controller adapter. No installed/live adoption.

Prepare SSH/SFTP sessions and content hashes first. Root receives only a bounded
manifest, checks metadata + inode consumers, never reads artifact content.
A terminal operation seals fork/exec in all its own threads. Consumer clearance
is a bounded observation, not exclusion of unrelated host opens after inspection.
"""
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import select
import subprocess
import threading
import time

from vk_candidate_owner import process_start

COMMAND = ('/usr/bin/sudo', '-n', '--', '/usr/local/sbin/vk-process-inspect-v1')
GATES = ('target_approved', 'backup_verified', 'dependencies_excluded',
         'fallback_preserved_until_human_qa', 'rollback_ready')
FRESH_NS = 5_000_000_000
MAX_RECEIPT = 1024 * 1024  # matches root output bound including newline


def require(value):
    if not value:
        raise ValueError('operation preflight blocked')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


class BoundaryStatus:
    def __init__(self, live_status):
        self.live_status, self.attestation = live_status, None

    def __call__(self):
        value = dict(self.live_status())
        if self.attestation is not None:
            value['inspection_attestation'] = dict(self.attestation)
        return value


def seal_process_creation():
    """Irreversible unprivileged seccomp TSYNC, for a TERMINAL actor only.

    Checker and status thread must already exist. x86_64 only; other arches block.
    This prevents this actor's fork/exec/new threads, not unrelated host processes
    or commands written over preexisting SSH sockets. Those channels must be
    sealed by the owning orchestration fence before entry.
    """
    require(os.uname().machine == 'x86_64')
    class Filter(ctypes.Structure):
        _fields_ = [('code', ctypes.c_ushort), ('jt', ctypes.c_ubyte),
                    ('jf', ctypes.c_ubyte), ('k', ctypes.c_uint32)]
    class Program(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ushort), ('filters', ctypes.POINTER(Filter))]
    deny = 0x00050000 | errno.EPERM
    rules = [(0x20, 0, 0, 4), (0x15, 1, 0, 0xc000003e), (0x06, 0, 0, deny),
             (0x20, 0, 0, 0), (0x45, 0, 1, 0x40000000), (0x06, 0, 0, deny)]
    for number in (56, 57, 58, 59, 322, 435):  # clone/fork/vfork/execve/execveat/clone3
        rules.extend([(0x15, 0, 1, number), (0x06, 0, 0, deny)])
    rules.append((0x06, 0, 0, 0x7fff0000))
    filters = (Filter * len(rules))(*(Filter(*row) for row in rules))
    program = Program(len(rules), filters)
    libc = ctypes.CDLL(None, use_errno=True)
    require(libc.prctl(38, 1, 0, 0, 0) == 0)  # PR_SET_NO_NEW_PRIVS
    require(libc.syscall(317, 1, 1, ctypes.byref(program)) == 0)  # seccomp FILTER | TSYNC


def task_inventory():
    # Only visible PID/TID/start metadata. Never protected fd/maps reads by mcp.
    result = set()
    for name in os.listdir('/proc'):
        if not name.isdigit():
            continue
        for tid in os.listdir(f'/proc/{name}/task'):
            if tid.isdigit():
                result.add((int(name), int(tid), process_start(f'{name}/task/{tid}')))
    return result


def verify_witness(witness):
    require(type(witness) is list and len(witness) > 0)
    covered = set()
    for row in witness:
        require(type(row) is list and len(row) == 3 and type(row[0]) is int
                and type(row[1]) is int and type(row[2]) is str)
        covered.add(tuple(row))
    require(len(covered) == len(witness))
    # Exits need no new inspection. Every birth/reused PID/TID is a hard stop.
    require(task_inventory() <= covered)


def hash_artifacts(scope_path, manifest):
    """Ordinary actor permissions only; root never runs this code or these reads."""
    require(re.fullmatch(r'[0-9a-f]{32}', manifest['release_id']))
    anchor = os.open(scope_path, os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        for target in manifest['targets']:
            name = target['name']
            require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', name) and '..' not in name)
            parent = os.dup(anchor)
            try:
                for part in ('objects', manifest['release_id']):
                    next_fd = os.open(part, os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
                    os.close(parent)
                    parent = next_fd
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=parent)
                with os.fdopen(fd, 'rb') as stream:
                    def current():
                        return {key: getattr(os.fstat(stream.fileno()), 'st_' + key) for key in target['identity']}
                    require(current() == target['identity'])
                    checksum = hashlib.sha256()
                    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                        checksum.update(chunk)
                    require(checksum.hexdigest() == target['sha256'] and current() == target['identity'])
            finally:
                os.close(parent)
    finally:
        os.close(anchor)


def verify_target_metadata(scope_path, manifest):
    """Bounded O_PATH identity checks only; no content hashing or callbacks."""
    anchor = os.open(scope_path, os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        for target in manifest['targets']:
            parent = os.dup(anchor)
            try:
                for part in ('objects', manifest['release_id'], target['name']):
                    flags = os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC
                    if part != target['name']:
                        flags |= os.O_DIRECTORY
                    child = os.open(part, flags, dir_fd=parent)
                    os.close(parent)
                    parent = child
                current = {key: getattr(os.fstat(parent), 'st_' + key) for key in target['identity']}
                require(current == target['identity'])
            finally:
                os.close(parent)
    finally:
        os.close(anchor)


def launch_checker():
    # Created before sealing; blocks on stdin until the held operation is ready.
    return subprocess.Popen(COMMAND, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, env={'PATH': '/usr/bin:/bin', 'LANG': 'C'}, close_fds=True)


def finish_checker(child, request):
    try:
        raw, _ = child.communicate(json.dumps(request).encode(), timeout=45)
    except subprocess.TimeoutExpired:
        child.kill()
        child.communicate()
        raise ValueError('inspection timed out') from None
    require(child.returncode == 0 and len(raw) <= MAX_RECEIPT)
    return json.loads(raw)


def validate_freshness(receipt):
    for issued, scanned, now in (('issued_ns', 'scan_started_ns', time.time_ns()),
                                ('issued_mono_ns', 'scan_started_mono_ns', time.monotonic_ns())):
        require(type(receipt.get(issued)) is int and type(receipt.get(scanned)) is int and
                0 <= now - receipt[issued] <= FRESH_NS and 0 <= receipt[issued] - receipt[scanned] <= 35_000_000_000)


def validate_receipt(receipt, request, installation):
    require(type(receipt) is dict and type(receipt.get('abi')) is int and receipt['abi'] == 1)
    require(set(installation) == {'code_sha256', 'policy_sha256'} and
            all(receipt.get(key) == value for key, value in installation.items()))
    for field in ('nonce', 'owner_pid', 'owner_start'):
        require(receipt.get(field) == request[field])
    require(receipt.get('inspection_manifest_sha256') == digest(request['manifest']))
    require(receipt.get('euid') == 0 and receipt.get('consumer_clearance_passed') is True
            and receipt.get('target_metadata_verified') is True
            and receipt.get('target_content_hashes_verified_by_root') is False
            and receipt.get('action_authorized') is False and receipt.get('deletion_performed') is False
            and receipt.get('production_changed') is False)
    validate_freshness(receipt)
    counts = receipt.get('visibility', {})
    require(counts.get('matches') == 0 and counts.get('inspection_denied') == 0
            and type(counts.get('processes')) is int and counts['processes'] > 0
            and type(counts.get('tasks')) is int and counts['tasks'] >= counts['processes'])
    verify_witness(counts.get('witness'))
    validate_freshness(receipt)  # traversal must not consume the continuation's age budget


def at_held_boundary(*, lease, server, status, manifest, scope_path, installation,
                     prepare, verify_gates, orchestration_fence,
                     consume=None, adoption_enabled=False, _handlers=None):
    """One operation, no persisted receipt input/loop. No-target restart skips root.

    prepare/verify_gates may do expensive/network work ONLY before clearance.
    status.live_status and lease.verify must be bounded local metadata/in-memory
    checks. No post-scan gate or orchestration callbacks are run. The managed
    owner seals existing command channels before launch; the terminal actor seals
    process creation. Neither mechanism excludes unrelated existing host opens.
    """
    hash_targets, verify_targets, start_checker, check_receipt = _handlers or (
        hash_artifacts, verify_target_metadata, launch_checker, validate_receipt)
    require(adoption_enabled is True)  # explicit local adoption; rollback disables new admissions
    require(status.attestation is None and server.status is status)
    prepare()  # all SSH/SFTP creation, B authentication, expensive hashes FIRST
    gates = json.loads(json.dumps(verify_gates()))
    require(gates == {key: True for key in GATES})
    lease.verify()
    if not manifest['targets']:
        require(consume is None)  # ordinary restart with no retirement: no root check
        return {'inspection_required': False, 'action_authorized': False}
    manifest = json.loads(json.dumps(manifest))  # freeze the operation's release binding
    hash_targets(scope_path, manifest)
    live = json.loads(json.dumps(status()))
    require(live['source'] == manifest['source_sha256'] and live['root_binding'] == manifest['root_binding']
            and live['manifest_sha256'] == manifest['backup_manifest_sha256'])
    # Owning orchestration must seal remote command/channel creation too.
    require(orchestration_fence.seal() is True and orchestration_fence.verify() is True)
    request = {'abi': 1, 'nonce': secrets.token_hex(32), 'owner_pid': os.getpid(),
               'owner_start': process_start(os.getpid()), 'manifest': manifest}
    status.attestation = {'abi': 1, 'nonce': request['nonce'], 'manifest_sha256': digest(manifest), 'boundary_held': True}
    stopped, failures = threading.Event(), []
    def serve():
        try:
            while not stopped.is_set():
                if select.select([server.socket], [], [], 0.05)[0]:
                    server.serve_once()
        except Exception as error:
            failures.append(type(error).__name__)
    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    child = None
    try:
        child = start_checker()  # ONLY allowed final child, before process seal
        if consume is not None:
            seal_process_creation()  # dedicated terminal actor only; irreversible
        receipt = finish_checker(child, request)  # root check INSIDE held operation
        require(not failures)
        lease.verify()
        verify_targets(scope_path, manifest)
        require(status() == {**live, 'inspection_attestation': status.attestation})
        check_receipt(receipt, request, installation)  # includes late PID/TID birth rejection
        validate_freshness(receipt)  # immediate continuation check, including profile validation
        return receipt if consume is None else consume(receipt)
    finally:
        if child is not None:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=3)
            for stream in (child.stdin, child.stdout):
                if stream is not None:
                    stream.close()
        stopped.set()
        worker.join(timeout=3)
        status.attestation = None
        require(not worker.is_alive())
