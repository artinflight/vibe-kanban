"""Unprivileged retained fixtures; no installed helper/sudo/live target invocation."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import tempfile
import time
import unittest
from unittest.mock import patch

import vk_retirement_preflight as client
from vk_candidate_owner import PreparationLease, PreparationStatus, process_start

spec = importlib.util.spec_from_file_location('root_check', Path(__file__).parent / 'security/vk_retirement_check.py')
root = importlib.util.module_from_spec(spec)
spec.loader.exec_module(root)
FIXTURES = Path('/mnt/vk-storage/vk-retirement-preflight-tests')


def fixture():
    if not os.path.ismount('/mnt/vk-storage'):
        raise RuntimeError('secondary SSD mount required')
    FIXTURES.mkdir(exist_ok=True)
    return Path(tempfile.mkdtemp(prefix='t-', dir=FIXTURES))


def request():
    return {'target_id': 'incident-archive-db5bb16b', 'nonce': 'a' * 64,
            'manifest_sha256': 'b' * 64, 'owner_pid': os.getpid(),
            'owner_start': process_start(os.getpid())}


class RootTests(unittest.TestCase):
    def test_strict_request_allowlist(self):
        root.validate_request(request())
        for changes in ({'path': '/etc/shadow'}, {'command': 'id'}, {'nonce': '../foo'},
                        {'owner_pid': True}, {'owner_start': '1\n2'}, {'target_id': 'other'},
                        {'manifest_sha256': '/etc/passwd'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                root.validate_request({**request(), **changes})

    def test_duplicate_json_and_oversize_rejected(self):
        for raw in (b'{"x":1,"x":2}', b' ' * 65537):
            path = fixture() / 'request'
            path.write_bytes(raw)
            with path.open('rb') as stream, self.assertRaises(ValueError):
                root.read_json_fd(stream.fileno())

    def test_symlink_parent_leaf_and_noncanonical_rejected(self):
        base = fixture()
        (base / 'file').write_text('private fixture')
        (base / 'link').symlink_to(base / 'file')
        (base / 'parent').symlink_to(base, target_is_directory=True)
        for path in (str(base / 'link'), str(base / 'parent/file'), str(base) + '/../file', str(base) + '//file'):
            with self.subTest(path=path), self.assertRaises((OSError, ValueError)):
                root.open_path(path)

    def test_user_writable_code_rejected(self):
        path = fixture() / 'helper.py'
        path.write_text('print(1)')
        with self.assertRaises(ValueError):
            root.trusted_path(str(path))

    def make_proc(self, *, flags=0, state='S', maps=''):
        base = fixture()
        task = base / '10/task/10'
        task.mkdir(parents=True)
        fields = [state] + ['0'] * 19
        fields[6], fields[19] = str(flags), '456'
        text = '10 (name with ) parentheses) ' + ' '.join(fields)
        (task / 'stat').write_text(text)
        (base / '10/stat').write_text(text)
        (task / 'fd').mkdir()
        (task / 'maps').write_text(maps)
        if not flags & 0x200000 and state != 'Z':
            for name in ('exe', 'cwd', 'root'):
                (task / name).symlink_to(base)
        return base, task

    def test_scan_clean_kernel_and_zombie(self):
        for flags, state in ((0, 'S'), (0x200000, 'S'), (0, 'Z')):
            proc, _ = self.make_proc(flags=flags, state=state)
            self.assertEqual(root.scan_consumers((99, 999), proc=proc)['tasks'], 1)

    def test_open_fd_hardlink_and_maps_consumers_block(self):
        for kind in ('fd', 'maps'):
            proc, task = self.make_proc()
            target = proc / 'target'
            target.write_text('content')
            info = target.stat()
            if kind == 'fd':
                alias = proc / 'alias'
                os.link(target, alias)
                (task / 'fd/5').symlink_to(alias)
            else:
                (task / 'maps').write_text(f'0-1 r--p 0 {os.major(info.st_dev):x}:{os.minor(info.st_dev):x} {info.st_ino} no-path-needed\n')
            with self.assertRaises(ValueError):
                root.scan_consumers((info.st_dev, info.st_ino), proc=proc)

    def test_missing_live_exe_denied_maps_and_malformed_maps_block(self):
        for scenario in ('missing', 'denied', 'malformed'):
            proc, task = self.make_proc()
            if scenario == 'missing':
                (task / 'exe').rename(task / 'retained-exe')
            if scenario == 'malformed':
                (task / 'maps').write_text('malformed')
            if scenario == 'denied':
                original = Path.open
                def fail(path, *args, **kwargs):
                    if path == task / 'maps':
                        raise PermissionError('protected')
                    return original(path, *args, **kwargs)
                with patch.object(Path, 'open', fail), self.assertRaises(PermissionError):
                    root.scan_consumers((99, 999), proc=proc)
            else:
                with self.assertRaises(ValueError):
                    root.scan_consumers((99, 999), proc=proc)

    def test_thread_consumer_and_process_birth_block(self):
        proc, task = self.make_proc()
        thread = task.parent / '11'
        thread.mkdir()
        for name in ('stat', 'maps'):
            (thread / name).write_bytes((task / name).read_bytes())
        (thread / 'fd').mkdir()
        for name in ('exe', 'cwd', 'root'):
            (thread / name).symlink_to(proc)
        (thread / 'fd/3').symlink_to(proc / '10/stat')
        target = (proc / '10/stat').stat()
        with self.assertRaises(ValueError):
            root.scan_consumers((target.st_dev, target.st_ino), proc=proc)
        original = os.listdir
        calls = 0
        def birth(path):
            nonlocal calls
            if path == proc:
                calls += 1
                if calls == 2:
                    return ['10', '99']
            return original(path)
        with patch.object(os, 'listdir', birth), self.assertRaises(ValueError):
            root.scan_consumers((99, 999), proc=proc)

    def test_scan_timeout_blocks(self):
        proc, _ = self.make_proc()
        ticks = iter([0, 31])
        with self.assertRaises(ValueError):
            root.scan_consumers((99, 999), proc=proc, clock=lambda: next(ticks))

    def test_target_replacement_identity_and_hash_block(self):
        base = fixture()
        path = base / 'target'
        path.write_bytes(b'original')
        approved = {'id': request()['target_id'], 'path': str(path),
                    'identity': root.identity(path.stat()), 'sha256': hashlib.sha256(b'original').hexdigest()}
        policy = {'schema': 1, 'caller_uid': 1000, 'target': approved, 'owner': {'source': 'c'*64, 'root_binding': 'd'*64, 'manifest_sha256': 'b'*64, 'endpoint': root.OWNER_ENDPOINT}, 'lease': {'path': root.LEASE_PATH, 'identity': {}}, 'proc_dev': 1, 'namespaces': {}}
        with patch.object(root, 'APPROVED_TARGET', approved), patch.object(root, 'visibility'), patch.object(root, 'live_owner'):
            changed = copy.deepcopy(policy)
            changed['target']['sha256'] = 'f' * 64
            with patch.object(root, 'APPROVED_TARGET', changed['target']), self.assertRaises(ValueError):
                root.check(changed, request())
            fd = root.open_path(str(path))
            try:
                path.rename(base / 'original')
                path.write_bytes(b'original')
                with self.assertRaises(ValueError):
                    root.target_check(fd, policy)
            finally:
                os.close(fd)

    def test_complete_hash_scan_order_and_postscan_replacement(self):
        base = fixture()
        path = base / 'target'
        path.write_bytes(b'original')
        approved = {'id': request()['target_id'], 'path': str(path),
                    'identity': root.identity(path.stat()), 'sha256': hashlib.sha256(b'original').hexdigest()}
        policy = {'schema': 1, 'caller_uid': 1000, 'target': approved,
                  'owner': {'endpoint': root.OWNER_ENDPOINT, 'source': 'c'*64,
                            'root_binding': 'd'*64, 'manifest_sha256': 'b'*64},
                  'lease': {'path': root.LEASE_PATH, 'identity': {}}, 'proc_dev': 1, 'namespaces': {}}
        events = []
        def scan(key):
            self.assertEqual(key, (path.stat().st_dev, path.stat().st_ino))
            # No checker target descriptor remains open at the consumer scan.
            for fd in Path('/proc/self/fd').iterdir():
                try:
                    self.assertNotEqual((fd.stat().st_dev, fd.stat().st_ino), key)
                except FileNotFoundError:
                    pass
            events.append('scan')
            return {'processes': 1, 'tasks': 1, 'matches': 0, 'inspection_denied': 0}
        with patch.object(root, 'APPROVED_TARGET', approved), patch.object(root, 'visibility'), \
             patch.object(root, 'live_owner', side_effect=lambda *args: events.append('owner')), \
             patch.object(root, 'scan_consumers', side_effect=scan):
            proof = root.check(policy, request())
            self.assertTrue(proof['consumer_clearance_passed'])
            self.assertEqual(events, ['owner', 'scan', 'owner'])
        def replace(key):
            path.rename(base / 'old')
            path.write_bytes(b'original')
            return {'processes': 1, 'tasks': 1, 'matches': 0, 'inspection_denied': 0}
        with patch.object(root, 'APPROVED_TARGET', approved), patch.object(root, 'visibility'), \
             patch.object(root, 'live_owner'), patch.object(root, 'scan_consumers', side_effect=replace), \
             self.assertRaises(ValueError):
            root.check(policy, request())

    def test_namespace_visibility_mismatch_blocks(self):
        policy = {'proc_dev': -1, 'namespaces': {'pid': 'wrong', 'mnt': 'wrong'}}
        with self.assertRaises(ValueError):
            root.visibility(policy)
        policy['proc_dev'] = os.stat('/proc').st_dev
        with self.assertRaises((ValueError, OSError)):
            root.visibility(policy)

    def test_arbitrary_root_policy_target_rejected_before_read(self):
        policy = {'schema': 1, 'caller_uid': 1000, 'target': {'id': request()['target_id'], 'path': '/etc/shadow'},
                  'owner': {}, 'lease': {}, 'proc_dev': 1, 'namespaces': {}}
        with patch.object(root, 'visibility'), self.assertRaises(ValueError):
            root.check(policy, request())

    def test_main_fail_closed_unprivileged_and_arguments(self):
        with patch.object(root.sys, 'argv', ['check', '--path=/etc/shadow']):
            with patch('builtins.print') as output:
                self.assertEqual(root.main(), 1)
                self.assertNotIn('/etc/shadow', output.call_args.args[0])


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.base = fixture()
        self.lease_path = self.base / 'lease'
        self.lease_path.write_text('')
        self.lease_path.chmod(0o600)
        self.expected_lease = root.identity(self.lease_path.stat())
        self.target = {'id': request()['target_id'], 'path': str(self.base / 'archive'), 'identity': {}, 'sha256': 'e' * 64}
        self.live = {'manifest_sha256': 'b' * 64, 'source': 'c' * 64, 'root_binding': {'tree': 123}}
        self.status = client.BoundaryStatus(lambda: self.live)
        self.events = []
        self.installation = {'code_sha256': 'd'*64, 'policy_sha256': 'e'*64}

    def receipt(self, req):
        self.events.append('scan')
        return {'schema': 1, **req, **self.live, **self.installation, 'target': self.target, 'lease': self.expected_lease,
                'issued_ns': time.time_ns(), 'scan_started_ns': time.time_ns() - 1000, 'euid': 0,
                'issued_mono_ns': time.monotonic_ns(), 'scan_started_mono_ns': time.monotonic_ns() - 1000,
                'consumer_clearance_passed': True, 'deletion_performed': False, 'production_changed': False,
                'visibility': {'processes': 1, 'tasks': 1, 'matches': 0, 'inspection_denied': 0}}

    def run_boundary(self, checker=None, gates=None):
        info = self.lease_path.stat()
        with PreparationLease(self.lease_path, (info.st_dev, info.st_ino)) as lease:
            server = PreparationStatus(self.base / 's', lease, self.status)
            try:
                with patch.object(client, 'privileged_check', checker or self.receipt):
                    return client.at_held_boundary(lease=lease, server=server, status=self.status,
                    expected_target=self.target, expected_lease=self.expected_lease, installation=self.installation,
                    prepare=lambda: self.events.append('prepare'),
                    verify_gates=gates or (lambda: {key: True for key in client.GATES}),
                    consume=lambda proof: self.events.append('consume'))
            finally:
                server.close()

    def test_preparation_before_scan_and_single_use(self):
        self.run_boundary()
        self.assertEqual(self.events, ['prepare', 'scan', 'consume'])
        self.assertIsNone(self.status.boundary)

    def test_failure_and_missing_qa_fallback_gate_never_consume(self):
        with self.assertRaises(ValueError):
            self.run_boundary(gates=lambda: {key: key != 'fallback_preserved_until_human_qa' for key in client.GATES})
        self.assertEqual(self.events, ['prepare'])

    def test_stale_replayed_future_and_substituted_receipts_block(self):
        for change in ({'issued_ns': time.time_ns() - 6_000_000_000}, {'nonce': 'f' * 64},
                       {'issued_ns': time.time_ns() + 60_000_000_000}, {'owner_pid': 1},
                       {'lease': {}}, {'target': {}}, {'policy_sha256': '0'*64}, {'code_sha256': '0'*64},
                       {'issued_mono_ns': time.monotonic_ns() - 6_000_000_000}, {'source': 'f' * 64},
                       {'manifest_sha256': 'f' * 64}, {'root_binding': {}},
                       {'consumer_clearance_passed': False}, {'euid': 1000},
                       {'visibility': {'matches': 0, 'inspection_denied': 1}}):
            with self.subTest(change=change):
                req = request()
                proof = {**self.receipt(req), **change}
                with self.assertRaises(ValueError):
                    client.validate_receipt(proof, req, self.live, self.target, self.expected_lease, self.installation, time.time_ns(), time.monotonic_ns())

    def test_real_live_peer_and_kernel_lease_during_boundary(self):
        def checked(req):
            policy = {'caller_uid': os.getuid(), 'lease': {'path': str(self.lease_path), 'identity': self.expected_lease},
                      'owner': {**self.live, 'endpoint': str(self.base / 's')}}
            root.live_owner(policy, req)
            proof = self.receipt(req)
            root.live_owner(policy, req)
            return proof
        self.run_boundary(checker=checked)
        self.assertEqual(self.events, ['prepare', 'scan', 'consume'])

    def test_owner_manifest_change_and_lease_release_block(self):
        def changed(req):
            proof = self.receipt(req)
            self.live['manifest_sha256'] = 'f' * 64
            return proof
        with self.assertRaises(ValueError):
            self.run_boundary(checker=changed)
        self.assertNotIn('consume', self.events)

    def test_released_lease_and_checker_error_never_consume(self):
        def released(req):
            proof = self.receipt(req)
            self.lease_path.rename(self.base / 'old-lease')
            self.lease_path.write_text('')
            self.lease_path.chmod(0o600)
            return proof
        with self.assertRaises(ValueError):
            self.run_boundary(checker=released)
        self.assertNotIn('consume', self.events)
        self.assertIsNone(self.status.boundary)

    def test_no_boundary_and_replayed_live_request_block(self):
        def checked(req):
            policy = {'caller_uid': os.getuid(), 'lease': {'path': str(self.lease_path), 'identity': self.expected_lease},
                      'owner': {**self.live, 'endpoint': str(self.base / 's')}}
            with self.assertRaises(ValueError):
                root.live_owner(policy, {**req, 'nonce': 'f'*64})
            proof = self.receipt(req)
            self.status.boundary = None
            with self.assertRaises(ValueError):
                root.live_owner(policy, req)
            raise ValueError('inconclusive')
        with self.assertRaises(ValueError):
            self.run_boundary(checker=checked)
        self.assertNotIn('consume', self.events)

    def test_dead_owner_and_replaced_lease_block(self):
        policy = {'caller_uid': os.getuid(), 'lease': {'path': str(self.lease_path), 'identity': self.expected_lease},
                  'owner': {**self.live, 'endpoint': str(self.base / 's')}}
        req = {**request(), 'owner_start': '0'}
        with self.assertRaises(ValueError):
            root.live_owner(policy, req)
        with self.assertRaises(ValueError):
            root.lease_check(policy, request())  # unheld kernel lease

    def test_wrong_socket_peer_blocks(self):
        info = self.lease_path.stat()
        with PreparationLease(self.lease_path, (info.st_dev, info.st_ino)) as lease:
            server = PreparationStatus(self.base / 's', lease, self.status)
            policy = {'caller_uid': os.getuid(), 'lease': {'path': str(self.lease_path), 'identity': self.expected_lease},
                      'owner': {**self.live, 'endpoint': str(self.base / 's')}}
            try:
                with patch.object(root.struct, 'unpack', return_value=(1, 0, 0)), self.assertRaises(ValueError):
                    root.live_owner(policy, request())
            finally:
                server.close()


if __name__ == '__main__':
    unittest.main()
