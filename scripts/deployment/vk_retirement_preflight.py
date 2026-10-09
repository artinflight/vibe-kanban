"""Unprivileged held-boundary adapter for PR231's PreparationStatus.

Owning driver wraps live_status with BoundaryStatus and passes the existing
PreparationStatus server here. No service controls, deletion or backup writes.
"""
import json
import os
import secrets
import select
import subprocess
import threading
import time

from vk_candidate_owner import process_start

COMMAND = ('/usr/bin/sudo', '-n', '--', '/usr/bin/python3.12', '-I', '-S', '-B',
           '/usr/local/libexec/vk-retirement-check.py')
GATES = ('target_approved', 'backup_verified', 'dependencies_excluded',
         'fallback_preserved_until_human_qa', 'rollback_ready')
FRESH_NS = 5_000_000_000


def require(value):
    if not value:
        raise ValueError('retirement preflight blocked')


class BoundaryStatus:
    def __init__(self, live_status):
        self.live_status = live_status
        self.boundary = None

    def __call__(self):
        value = dict(self.live_status())
        if self.boundary is not None:
            value['retirement_boundary'] = dict(self.boundary)
        return value


def privileged_check(request):
    # Fixed argv, clean environment, bounded output through a pipe, no shell.
    # Timeout is inconclusive; callers must never use a prior receipt instead.
    with subprocess.Popen(COMMAND, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, env={'PATH': '/usr/bin:/bin', 'LANG': 'C'},
                          close_fds=True) as child:
        try:
            raw, _ = child.communicate(json.dumps(request).encode(), timeout=600)
        except subprocess.TimeoutExpired:
            child.kill()
            child.communicate()
            raise ValueError('retirement preflight timed out') from None
        require(child.returncode == 0 and len(raw) <= 65536)
    return json.loads(raw)


def validate_receipt(receipt, request, status, expected_target, expected_lease, installation, now, monotonic_now):
    require(type(receipt) is dict and type(receipt.get('schema')) is int and receipt['schema'] == 1)
    require(set(installation) == {'code_sha256', 'policy_sha256'} and
            all(receipt.get(key) == value for key, value in installation.items()))
    require(all(receipt.get(key) == value for key, value in request.items()))
    require(receipt.get('source') == status['source'] and receipt.get('root_binding') == status['root_binding'])
    require(receipt.get('lease') == expected_lease and receipt.get('target') == expected_target)
    require(receipt.get('euid') == 0 and receipt.get('consumer_clearance_passed') is True
            and receipt.get('deletion_performed') is False and receipt.get('production_changed') is False)
    issued, scanned = receipt.get('issued_ns'), receipt.get('scan_started_ns')
    require(type(issued) is int and type(scanned) is int and
            0 <= now - issued <= FRESH_NS and 0 <= issued - scanned <= 35_000_000_000)
    mono_issued, mono_scanned = receipt.get('issued_mono_ns'), receipt.get('scan_started_mono_ns')
    require(type(mono_issued) is int and type(mono_scanned) is int and
            0 <= monotonic_now - mono_issued <= FRESH_NS and 0 <= mono_issued - mono_scanned <= 35_000_000_000)
    counts = receipt.get('visibility', {})
    require(counts.get('matches') == 0 and counts.get('inspection_denied') == 0
            and type(counts.get('processes')) is int and counts['processes'] > 0
            and type(counts.get('tasks')) is int and counts['tasks'] >= counts['processes'])


def at_held_boundary(*, lease, server, status, expected_target, expected_lease,
                     installation, prepare, verify_gates, consume, checker=privileged_check):
    """Finish preparation, then obtain and consume ONE live receipt while held.

    consume is the owner's existing unprivileged boundary continuation. It must
    independently preserve its target/path pins and all human interruption gates.
    No persisted/operator receipt is accepted, no automatic retry or fallback.
    """
    require(status.boundary is None and server.status is status)
    prepare()  # expensive preparation must precede the scan/receipt
    require(verify_gates() == {key: True for key in GATES})
    lease.verify()
    live = status()
    require(live.get('manifest_sha256') and live.get('source'))
    request = {'target_id': expected_target['id'], 'nonce': secrets.token_hex(32),
               'owner_pid': os.getpid(), 'owner_start': process_start(os.getpid()),
               'manifest_sha256': live['manifest_sha256']}
    status.boundary = {key: request[key] for key in ('nonce', 'target_id')}
    stopped, failures = threading.Event(), []

    def serve():
        try:
            while not stopped.is_set():
                ready, _, _ = select.select([server.socket], [], [], 0.05)
                if ready:
                    server.serve_once()
        except Exception as error:
            failures.append(type(error).__name__)

    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    try:
        monotonic_start = time.monotonic_ns()
        receipt = checker(request)
        require(not failures)
        # A backward wall-clock adjustment cannot turn an old receipt fresh.
        require(0 <= time.monotonic_ns() - monotonic_start <= 600_000_000_000)
        lease.verify()
        require(status() == {**live, 'retirement_boundary': status.boundary})
        require(verify_gates() == {key: True for key in GATES})
        validate_receipt(receipt, request, live, expected_target, expected_lease, installation, time.time_ns(), time.monotonic_ns())
        # Validate AFTER fresh gate/live checks, immediately before continuation.
        return consume(receipt)
    finally:
        stopped.set()
        worker.join(timeout=3)
        status.boundary = None
        require(not worker.is_alive())
