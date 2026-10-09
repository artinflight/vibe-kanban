"""Reusable ABI source-only fixtures. No sudo, installation or live owner mutation."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
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
    return Path(tempfile.mkdtemp(prefix='r-', dir=FIXTURES))


class Fence:
    def __init__(self, events=None):
        self.sealed = False
        self.events = events if events is not None else []
    def seal(self):
        self.events.append('orchestration-sealed')
        self.sealed = True
        return True
    def verify(self):
        return self.sealed


class Fixtures(unittest.TestCase):
    def setUp(self):
        self.base = fixture()
        self.release_id = '1'*32
        for kind in ('objects', 'control'):
            (self.base / kind / self.release_id).mkdir(parents=True)
            (self.base / kind).chmod(0o700)
            (self.base / kind / self.release_id).chmod(0o700)
        self.path = self.base / 'objects' / self.release_id / 'server'
        self.path.write_bytes(b'approved unprivileged artifact')
        self.path.chmod(0o600)
        self.lease_path = self.base / 'control' / self.release_id / 'owner.lease'
        self.lease_path.write_bytes(b'')
        self.lease_path.chmod(0o600)
        self.manifest = {'scope_id': 'managed-artifacts-v1', 'release_id': self.release_id,
                         'source_sha256': '2'*64, 'root_binding': '3'*64, 'backup_manifest_sha256': '4'*64,
                         'lease': root.identity(self.lease_path.stat()),
                         'targets': [{'name': 'server', 'guard_held': False, 'identity': root.identity(self.path.stat()),
                                      'sha256': hashlib.sha256(self.path.read_bytes()).hexdigest()}]}
        self.request = {'abi': 1, 'nonce': '5'*64, 'owner_pid': os.getpid(),
                        'owner_start': process_start(os.getpid()), 'manifest': self.manifest}
        self.policy = {'abi': 1, 'caller_uid': 1000, 'scopes': {self.manifest['scope_id']: {
            'path': '/mnt/vk-storage/vk-process-inspection-managed-v1',
            'anchor_inode': self.base.stat().st_ino, 'filesystem_uuid': '26e4cac1-f2cf-485b-b1bc-d1be197a747e'}}}
        self.installation = {'code_sha256': 'a'*64, 'policy_sha256': 'b'*64}
        self.events = []
        self.live = {'source': self.manifest['source_sha256'], 'root_binding': self.manifest['root_binding'],
                     'manifest_sha256': self.manifest['backup_manifest_sha256']}
        self.status = client.BoundaryStatus(lambda: self.live)

    def scope(self):
        return root.open_path(str(self.base), directory=True)

    def receipt(self, req):
        return {'abi': 1, 'nonce': req['nonce'], 'owner_pid': req['owner_pid'], 'owner_start': req['owner_start'],
                'inspection_manifest_sha256': root.digest(req['manifest']), **self.installation,
                'issued_ns': time.time_ns(), 'scan_started_ns': time.time_ns()-1000,
                'issued_mono_ns': time.monotonic_ns(), 'scan_started_mono_ns': time.monotonic_ns()-1000,
                'euid': 0, 'consumer_clearance_passed': True, 'target_metadata_verified': True,
                'target_content_hashes_verified_by_root': False, 'action_authorized': False,
                'deletion_performed': False, 'production_changed': False,
                'visibility': {'processes': 1, 'tasks': 1, 'matches': 0, 'inspection_denied': 0,
                               'witness': [[os.getpid(), os.getpid(), process_start(os.getpid())]]}}

    def run_boundary(self, *, finish=None, consume=None, gates=None):
        info = self.lease_path.stat()
        with PreparationLease(self.lease_path, (info.st_dev, info.st_ino)) as lease:
            parent_fd = os.open(self.lease_path.parent, os.O_PATH | os.O_DIRECTORY)
            server = PreparationStatus(Path(f'/proc/self/fd/{parent_fd}/owner.sock'), lease, self.status)
            child = unittest.mock.Mock()
            child.poll.return_value = 0
            def default_finish(_, req):
                self.events.append('privileged-scan')
                fd = self.scope()
                try:
                    root.live_owner(fd, req, os.getuid())  # REAL peer/PID and kernel FLOCK
                finally:
                    os.close(fd)
                return self.receipt(req)
            try:
                with patch.object(client, 'launch_checker', return_value=child), \
                     patch.object(client, 'finish_checker', side_effect=finish or default_finish), \
                     patch.object(client, 'seal_process_creation', side_effect=lambda: self.events.append('kernel-process-seal')), \
                     patch.object(client, 'task_inventory', return_value={(os.getpid(), os.getpid(), process_start(os.getpid()))}):
                    return client.at_held_boundary(lease=lease, server=server, status=self.status,
                        manifest=self.manifest, scope_path=str(self.base), installation=self.installation,
                        prepare=lambda: self.events.extend(['SSH-SFTP-created', 'B-hashed']),
                        verify_gates=gates or (lambda: {key: True for key in client.GATES}),
                        orchestration_fence=Fence(self.events), consume=consume)
            finally:
                server.close()
                os.close(parent_fd)


class ScopeTests(Fixtures):
    def test_future_releases_same_root_policy_and_abi(self):
        root.validate_policy(self.policy)
        for release, source in (('6'*32, '7'*64), ('8'*32, '9'*64)):
            req = copy.deepcopy(self.request)
            req['manifest'].update(release_id=release, source_sha256=source)
            root.validate_request(req)
            root.validate_policy(self.policy)  # no target/source/owner/interpreter pins

    def test_request_extra_paths_commands_traversal_types_and_abi_block(self):
        for change in ({'command': 'id'}, {'path': '/etc/shadow'}, {'manifest_path': '/etc/shadow'},
                       {'owner_pid': True}, {'owner_start': '../1'}, {'nonce': 'old'}, {'abi': 2}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                root.validate_request({**self.request, **change})
        for name in ('../../shadow', '/etc/shadow', 'a/b', '..', 'server..old'):
            req = copy.deepcopy(self.request)
            req['manifest']['targets'][0]['name'] = name
            with self.assertRaises(ValueError):
                root.validate_request(req)

    def test_duplicate_oversized_and_excessive_targets_block(self):
        for raw in (b'{"x":1,"x":2}', b' '*65537):
            with self.assertRaises(ValueError):
                root.parse_json(raw)
        req = copy.deepcopy(self.request)
        req['manifest']['targets'] *= 33
        with self.assertRaises(ValueError):
            root.validate_request(req)

    def test_unenrolled_policy_and_arbitrary_scope_block(self):
        pending = copy.deepcopy(self.policy)
        pending['scopes'][self.manifest['scope_id']]['anchor_inode'] = None
        with self.assertRaises(ValueError):
            root.validate_policy(pending)
        unknown = {**self.manifest, 'scope_id': 'arbitrary'}
        with self.assertRaises(ValueError):
            root.open_scope(self.policy, unknown)
        changed = copy.deepcopy(self.policy)
        changed['scopes'][self.manifest['scope_id']]['path'] = '/home/mcp'
        with self.assertRaises(ValueError):
            root.validate_policy(changed)

    def test_mutable_anchor_and_inode_replacement_block(self):
        original_open = root.open_path
        with patch.object(root, 'open_path', side_effect=lambda *args, **kw: original_open(str(self.base), directory=True)), \
             patch.object(root, 'filesystem_device', return_value=self.base.stat().st_dev), self.assertRaises(ValueError):
            root.open_scope(self.policy, self.manifest)  # mcp-owned anchor never accepted
        fd = self.scope()
        try:
            info = os.fstat(fd)
            fake = unittest.mock.Mock(st_uid=0, st_mode=0o40755, st_ino=info.st_ino+1, st_dev=info.st_dev)
            with patch.object(root, 'open_path', return_value=os.dup(fd)), \
                 patch.object(root.os, 'fstat', return_value=fake), \
                 patch.object(root, 'filesystem_device', return_value=info.st_dev), self.assertRaises(ValueError):
                root.open_scope(self.policy, self.manifest)
        finally:
            os.close(fd)

    def test_opath_target_is_unreadable_handle_not_root_content_read(self):
        fd = self.scope()
        try:
            leaf = root.relative_handle(fd, ('objects', self.release_id, 'server'), os.getuid())
            try:
                with self.assertRaises(OSError):
                    os.read(leaf, 1)  # O_PATH cannot return artifact bytes
            finally:
                os.close(leaf)
            with patch.object(Path, 'open', side_effect=AssertionError('root artifact content read')):
                targets = root.inspect_targets(fd, self.manifest, os.getuid())
                self.assertEqual(targets, {(self.path.stat().st_dev, self.path.stat().st_ino)})
        finally:
            os.close(fd)

    def test_symlink_parent_leaf_hardlink_and_directory_targets_block(self):
        fd = self.scope()
        try:
            self.path.rename(self.path.with_name('original'))
            self.path.symlink_to('/etc/shadow')
            with self.assertRaises(ValueError):
                root.inspect_targets(fd, self.manifest, os.getuid())
            directory = self.base / 'objects' / self.release_id
            directory.rename(directory.with_name('retained'))
            directory.symlink_to(directory.with_name('retained'), target_is_directory=True)
            with self.assertRaises(OSError):
                root.inspect_targets(fd, self.manifest, os.getuid())
        finally:
            os.close(fd)

    def test_truthful_hardlink_or_directory_identity_is_not_authority(self):
        os.link(self.path, self.path.with_name('alias'))
        self.manifest['targets'][0]['identity'] = root.identity(self.path.stat())
        fd = self.scope()
        try:
            with self.assertRaises(ValueError):
                root.inspect_targets(fd, self.manifest, os.getuid())
        finally:
            os.close(fd)

    def test_wrong_owner_permissions_and_metadata_block(self):
        fd = self.scope()
        try:
            self.path.chmod(0o644)
            self.manifest['targets'][0]['identity'] = root.identity(self.path.stat())
            with self.assertRaises(ValueError):
                root.inspect_targets(fd, self.manifest, os.getuid())
            self.path.chmod(0o600)
            with self.assertRaises(ValueError):
                root.inspect_targets(fd, self.manifest, os.getuid()+1)
            self.manifest['targets'][0]['identity']['ino'] += 1
            with self.assertRaises(ValueError):
                root.inspect_targets(fd, self.manifest, os.getuid())
        finally:
            os.close(fd)

    def test_cross_device_component_is_rejected(self):
        fd = self.scope()
        original = os.fstat
        def other_device(handle):
            info = original(handle)
            if info.st_ino == self.path.stat().st_ino:
                return unittest.mock.Mock(st_dev=info.st_dev+1, st_uid=info.st_uid)
            return info
        try:
            with patch.object(root.os, 'fstat', side_effect=other_device), self.assertRaises(ValueError):
                root.relative_handle(fd, ('objects', self.release_id, 'server'), os.getuid())
        finally:
            os.close(fd)

    def test_user_mutable_privileged_code_blocked(self):
        with self.assertRaises(ValueError):
            root.trusted_path(str(self.path))

    def test_hashes_computed_unprivileged_and_mismatch_blocks(self):
        client.hash_artifacts(str(self.base), self.manifest)
        self.manifest['targets'][0]['sha256'] = '0'*64
        with self.assertRaises(ValueError):
            client.hash_artifacts(str(self.base), self.manifest)


class ProtocolTests(Fixtures):
    def test_sessions_B_hashes_and_native_hash_precede_scan_real_live_lease(self):
        proof = self.run_boundary()
        self.assertTrue(proof['consumer_clearance_passed'])
        self.assertEqual(self.events, ['SSH-SFTP-created', 'B-hashed', 'orchestration-sealed', 'privileged-scan'])
        self.assertIsNone(self.status.attestation)

    def test_no_targets_no_privilege_invocation_for_routine_restart(self):
        self.manifest['targets'] = []
        with patch.object(client, 'launch_checker', side_effect=AssertionError('unexpected sudo')):
            proof = self.run_boundary()
        self.assertFalse(proof['inspection_required'])
        self.assertEqual(self.events, ['SSH-SFTP-created', 'B-hashed'])

    def test_expensive_gate_callback_runs_once_before_scan(self):
        def gates():
            self.assertNotIn('privileged-scan', self.events)
            self.events.append('backup-gates-pinned')
            return {key: True for key in client.GATES}
        self.run_boundary(gates=gates, consume=lambda _: self.events.append('ACTION'))
        self.assertEqual(self.events.count('backup-gates-pinned'), 1)
        self.assertEqual(self.events[-2:], ['privileged-scan', 'ACTION'])

    def test_operation_process_seal_before_scan_then_immediate_continuation(self):
        self.run_boundary(consume=lambda _: self.events.append('in-process-continuation'))
        self.assertEqual(self.events, ['SSH-SFTP-created', 'B-hashed', 'orchestration-sealed',
                                      'kernel-process-seal', 'privileged-scan', 'in-process-continuation'])

    def test_bad_backup_QA_fallback_gate_blocks(self):
        with self.assertRaises(ValueError):
            self.run_boundary(gates=lambda: {key: key != 'fallback_preserved_until_human_qa' for key in client.GATES})
        self.assertNotIn('privileged-scan', self.events)

    def test_complete_root_metadata_pipeline_multiple_release_sources(self):
        for source in ('6'*64, '7'*64):
            self.manifest['source_sha256'] = source
            self.live['source'] = source
            req = {**self.request, 'nonce': '8'*64}
            self.status.attestation = {'abi': 1, 'nonce': req['nonce'],
                                      'manifest_sha256': root.digest(self.manifest), 'boundary_held': True}
            info = self.lease_path.stat()
            with PreparationLease(self.lease_path, (info.st_dev, info.st_ino)) as lease:
                parent = os.open(self.lease_path.parent, os.O_PATH | os.O_DIRECTORY)
                # Retain each socket fixture; no data/owner socket removal.
                old = self.lease_path.parent / 'owner.sock'
                if old.exists():
                    old.rename(self.lease_path.parent / ('retained-'+source[0]+'.sock'))
                server = PreparationStatus(Path(f'/proc/self/fd/{parent}/owner.sock'), lease, self.status)
                stop = __import__('threading').Event()
                def serve():
                    import select
                    while not stop.is_set():
                        if select.select([server.socket], [], [], .01)[0]:
                            server.serve_once()
                worker = __import__('threading').Thread(target=serve)
                worker.start()
                try:
                    with patch.object(root, 'visibility'), patch.object(root, 'open_scope', side_effect=lambda *_: self.scope()), \
                         patch.object(root, 'scan_consumers', return_value=self.receipt(req)['visibility']):
                        result = root.check(self.policy, req)
                        self.assertEqual(result['inspection_manifest_sha256'], root.digest(self.manifest))
                        self.assertFalse(result['target_content_hashes_verified_by_root'])
                finally:
                    stop.set()
                    worker.join(2)
                    server.close()
                    os.close(parent)
            self.status.attestation = None

    def test_metadata_substitution_after_privileged_scan_blocks(self):
        def scan(_, **kwargs):
            self.path.rename(self.path.with_name('old-target'))
            self.path.write_bytes(b'approved unprivileged artifact')
            self.path.chmod(0o600)
            return self.receipt(self.request)['visibility']
        with patch.object(root, 'visibility'), patch.object(root, 'open_scope', side_effect=lambda *_: self.scope()), \
             patch.object(root, 'live_owner'), patch.object(root, 'scan_consumers', side_effect=scan), \
             self.assertRaises(ValueError):
            root.check(self.policy, self.request)

    def test_wrong_nonce_source_manifest_and_lease_holder_block_real_status(self):
        def finish(_, req):
            fd = self.scope()
            try:
                for change in ({'nonce': 'a'*64}, {'owner_start': '0'}):
                    with self.assertRaises(ValueError):
                        root.live_owner(fd, {**req, **change}, os.getuid())
                changed = copy.deepcopy(req)
                changed['manifest']['source_sha256'] = 'e'*64
                with self.assertRaises(ValueError):
                    root.live_owner(fd, changed, os.getuid())
            finally:
                os.close(fd)
            return self.receipt(req)
        self.run_boundary(finish=finish)

    def test_declared_target_guard_requires_exact_live_owner_FLOCK(self):
        import fcntl
        self.manifest['targets'][0]['guard_held'] = True
        with self.assertRaises(ValueError):
            root.target_guards(self.request)
        with self.path.open('rb') as held:
            fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(root.target_guards(self.request), {(self.path.stat().st_dev, self.path.stat().st_ino)})
            changed = {**self.request, 'owner_pid': 1}
            with self.assertRaises(ValueError):
                root.target_guards(changed)

    def test_unheld_and_replaced_lease_blocks(self):
        fd = self.scope()
        try:
            with self.assertRaises(ValueError):
                root.lease_check(fd, self.request, os.getuid())
            self.lease_path.rename(self.lease_path.with_name('old'))
            self.lease_path.write_bytes(b'')
            self.lease_path.chmod(0o600)
            with self.assertRaises(ValueError):
                root.lease_check(fd, self.request, os.getuid())
        finally:
            os.close(fd)

    def test_replay_age_installation_or_invented_authority_block(self):
        for change in ({'nonce': 'old'}, {'issued_ns': time.time_ns()-6_000_000_000},
                       {'issued_mono_ns': time.monotonic_ns()-6_000_000_000}, {'owner_pid': 1},
                       {'inspection_manifest_sha256': 'f'*64}, {'code_sha256': 'f'*64},
                       {'action_authorized': True}, {'target_content_hashes_verified_by_root': True}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                client.validate_receipt({**self.receipt(self.request), **change}, self.request, self.installation)

    def test_observed_protected_SSH_birth_after_scan_blocks_even_fresh_receipt(self):
        proof = self.receipt(self.request)
        born = {(os.getpid(), os.getpid(), process_start(os.getpid())),
                (1632206, 1632206, '758494803'), (1632291, 1632291, '758494851'),
                (1632292, 1632292, '758494855')}
        with patch.object(client, 'task_inventory', return_value=born), self.assertRaises(ValueError):
            client.validate_receipt(proof, self.request, self.installation)

    def test_late_PID_TID_reuse_or_birth_and_inaccessible_inventory_block(self):
        witness = [[10, 10, '456']]
        for current in ({(10, 10, '457')}, {(10, 10, '456'), (10, 11, '500')}):
            with patch.object(client, 'task_inventory', return_value=current), self.assertRaises(ValueError):
                client.verify_witness(witness)
        with patch.object(client, 'task_inventory', side_effect=PermissionError), self.assertRaises(PermissionError):
            client.verify_witness(witness)


class ScanTests(unittest.TestCase):
    def make_proc(self, *, flags=0, state='S', maps=''):
        base = fixture()
        task = base / '10/task/10'
        task.mkdir(parents=True)
        fields = [state] + ['0']*19
        fields[6], fields[19] = str(flags), '456'
        text = '10 (name with ) parentheses) ' + ' '.join(fields)
        for path in (task / 'stat', base / '10/stat'):
            path.write_text(text)
        (task / 'fd').mkdir()
        (task / 'maps').write_text(maps)
        if not flags & 0x200000 and state != 'Z':
            for name in ('exe', 'cwd', 'root'):
                (task / name).symlink_to(base)
        return base, task

    def test_kernel_worker_and_zombie_metadata_are_not_opaque_user_consumers(self):
        for flags, state in ((0, 'S'), (0x200000, 'S'), (0, 'Z')):
            proc, _ = self.make_proc(flags=flags, state=state)
            result = root.scan_consumers({(99, 999)}, proc=proc)
            self.assertEqual(result['matches'], 0)
            self.assertEqual(result['witness'], [[10, 10, '456']])

    def test_fd_hardlink_maps_exe_cwd_root_consumers_block(self):
        for kind in ('fd', 'maps', 'exe', 'cwd', 'root'):
            proc, task = self.make_proc()
            target = proc / 'target'
            target.write_bytes(b'data')
            info = target.stat()
            if kind == 'maps':
                (task / 'maps').write_text(f'0-1 r--p 0 {os.major(info.st_dev):x}:{os.minor(info.st_dev):x} {info.st_ino} no-root-read\n')
            elif kind == 'fd':
                alias = proc / 'alias'
                os.link(target, alias)
                (task / 'fd/5').symlink_to(alias)
            else:
                (task / kind).rename(task / ('retained-'+kind))
                (task / kind).symlink_to(target)
            with self.assertRaises(ValueError):
                root.scan_consumers({(info.st_dev, info.st_ino)}, proc=proc)

    def test_nonleader_thread_private_FD_and_maps_consumers_block(self):
        import shutil
        for kind in ('fd', 'maps'):
            proc, leader = self.make_proc()
            task = leader.parent / '11'
            shutil.copytree(leader, task, symlinks=True)
            (task / 'stat').write_text((leader / 'stat').read_text().replace('10 (', '11 ('))
            target = proc / 'thread-only-target'
            target.write_bytes(b'nonleader private consumer')
            info = target.stat()
            if kind == 'fd':
                (task / 'fd/5').symlink_to(target)
            else:
                (task / 'maps').write_text(f'0-1 r--p 0 {os.major(info.st_dev):x}:{os.minor(info.st_dev):x} {info.st_ino} private-thread-map\n')
            with self.assertRaises(ValueError):
                root.scan_consumers({(info.st_dev, info.st_ino)}, proc=proc)

    def test_only_verified_owner_guard_FD_is_exempt_not_maps_or_other_PIDs(self):
        proc, task = self.make_proc()
        target = proc / 'target'
        target.write_bytes(b'data')
        info = target.stat()
        key = (info.st_dev, info.st_ino)
        (task / 'fd/5').symlink_to(target)
        result = root.scan_consumers({key}, owner_pid=10, guards={key}, proc=proc)
        self.assertEqual(result['matches'], 0)
        with self.assertRaises(ValueError):
            root.scan_consumers({key}, owner_pid=11, guards={key}, proc=proc)
        (task / 'maps').write_text(f'0-1 r--p 0 {os.major(info.st_dev):x}:{os.minor(info.st_dev):x} {info.st_ino} guard-does-not-exempt-map\n')
        with self.assertRaises(ValueError):
            root.scan_consumers({key}, owner_pid=10, guards={key}, proc=proc)

    def test_live_nondumpable_denial_malformed_maps_and_timeout_block(self):
        proc, task = self.make_proc()
        original = Path.open
        def denied(path, *args, **kwargs):
            if path == task / 'maps':
                raise PermissionError('non-dumpable')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'open', denied), self.assertRaises(PermissionError):
            root.scan_consumers({(99, 999)}, proc=proc)
        (task / 'maps').write_text('malformed')
        with self.assertRaises(ValueError):
            root.scan_consumers({(99, 999)}, proc=proc)
        ticks = iter([0, 31])
        with self.assertRaises(ValueError):
            root.scan_consumers({(99, 999)}, proc=proc, clock=lambda: next(ticks))

    def test_concurrent_process_churn_blocks(self):
        proc, _ = self.make_proc()
        original, calls = os.listdir, 0
        def birth(path):
            nonlocal calls
            if path == proc:
                calls += 1
                if calls == 2:
                    return ['10', '99']
            return original(path)
        with patch.object(os, 'listdir', birth), self.assertRaises(ValueError):
            root.scan_consumers({(99, 999)}, proc=proc)


class NativeOrderingTests(unittest.TestCase):
    def test_real_preparation_children_before_scan_and_postscan_SSH_denied(self):
        # Substitute only the privileged scanner. Real process/pipe/thread/lease
        # ordering and the actual kernel process seal run in a disposable actor.
        program = r"""
import errno, json, os, subprocess, sys
from unittest.mock import patch
from test_vk_retirement_preflight import Fixtures, Fence, client
from vk_candidate_owner import PreparationLease, PreparationStatus, process_start
case = Fixtures(); case.setUp()
events = []
child = None
calls = []
def prepare():
    subprocess.run(['/usr/bin/true'], check=True)
    events.append('preparation-child-finished')
def gates():
    calls.append('gates')
    subprocess.run(['/usr/bin/true'], check=True)
    events.append('gate-child-finished')
    return {key: True for key in client.GATES}
def launch():
    global child
    child = subprocess.Popen([sys.executable, '-B', '-c',
        "import sys,json; req=json.loads(sys.stdin.read()); print(req['nonce'])"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert os.path.exists('/proc/' + str(child.pid))
    events.append('inspection-child-created')
    return child
def finish(child, request):
    out, err = child.communicate(json.dumps(request).encode(), timeout=3)
    assert child.returncode == 0 and out.strip().decode() == request['nonce'], err
    events.append('inspection-response')
    return case.receipt(request)
def consume(receipt):
    assert len(calls) == 1
    try:
        subprocess.run(['/usr/bin/ssh', '-V'], check=True)
    except OSError as error:
        assert error.errno == errno.EPERM
        events.append('postscan-SSH-denied')
    else:
        raise AssertionError('postscan process creation permitted')
    events.append('exact-in-process-continuation')
    return events
info = case.lease_path.stat()
with PreparationLease(case.lease_path, (info.st_dev, info.st_ino)) as lease:
    parent = os.open(case.lease_path.parent, os.O_PATH | os.O_DIRECTORY)
    server = PreparationStatus('/proc/self/fd/' + str(parent) + '/owner.sock', lease, case.status)
    try:
        with patch.object(client, 'launch_checker', side_effect=launch), \
             patch.object(client, 'finish_checker', side_effect=finish), \
             patch.object(client, 'task_inventory', return_value={(os.getpid(), os.getpid(), process_start(os.getpid()))}):
            result = client.at_held_boundary(lease=lease, server=server, status=case.status,
                manifest=case.manifest, scope_path=str(case.base), installation=case.installation,
                prepare=prepare, verify_gates=gates, orchestration_fence=Fence(), consume=consume)
        assert result == ['preparation-child-finished', 'gate-child-finished',
                          'inspection-child-created', 'inspection-response',
                          'postscan-SSH-denied', 'exact-in-process-continuation'], result
    finally:
        server.close(); os.close(parent)
print(json.dumps(result))
"""
        completed = subprocess.run([sys.executable, '-B', '-c', program],
                                   cwd=Path(__file__).parent, capture_output=True, text=True, timeout=8)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn('postscan-SSH-denied', completed.stdout)


class NativeSealTests(unittest.TestCase):
    def test_terminal_actor_cannot_fork_exec_or_spawn_thread_after_seal(self):
        program = r'''
import errno,os,subprocess,threading
from vk_retirement_preflight import seal_process_creation
ready = threading.Event()
results = []
def existing_thread():
    ready.wait()
    try: os.fork()
    except OSError as e: results.append(e.errno)
    else: results.append('fork permitted')
worker = threading.Thread(target=existing_thread)
worker.start()
seal_process_creation()
ready.set(); worker.join(timeout=2)
assert results == [errno.EPERM], results
try: os.fork()
except OSError as e: assert e.errno == errno.EPERM
else: raise AssertionError('fork permitted')
try: os.execve('/usr/bin/true', ['/usr/bin/true'], {})
except OSError as e: assert e.errno == errno.EPERM
else: raise AssertionError('same PID exec permitted')
try: subprocess.run(['/usr/bin/true'])
except OSError as e: assert e.errno == errno.EPERM
else: raise AssertionError('exec permitted')
try: threading.Thread(target=lambda:None).start()
except RuntimeError: pass
else: raise AssertionError('new thread permitted')
print('sealed')
'''
        completed = subprocess.run([sys.executable, '-B', '-c', program],
                                   cwd=Path(__file__).parent, capture_output=True, text=True, timeout=5)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), 'sealed')


if __name__ == '__main__':
    unittest.main()
