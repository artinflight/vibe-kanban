"""Separate historical profile fixtures; no root entrypoint/sudo/live operations."""
import copy
from contextlib import ExitStack
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import Mock, patch

import vk_historical_archive_preflight as archive
import vk_retirement_preflight as boundary
from test_vk_retirement_preflight import Fixtures, Fence, root
from vk_candidate_owner import PreparationLease, PreparationStatus, process_start

spec = importlib.util.spec_from_file_location('historical_root', Path(__file__).parent / 'security/vk_historical_archive_check.py')
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)


class HistoricalTests(Fixtures):
    def setUp(self):
        super().setUp()
        self.policy = json.loads((Path(__file__).parent / 'security/historical-archive-policy.proposal.json').read_text())
        self.policy['control_scope']['anchor_inode'] = self.base.stat().st_ino
        target = {'path': str(self.path), 'identity': root.identity(self.path.stat()),
                  'sha256': hashlib.sha256(self.path.read_bytes()).hexdigest()}
        self.policy['target'] = target
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(profile, 'TARGET', target))
        stack.enter_context(patch.object(archive, 'PATH', self.path))
        stack.enter_context(patch.object(archive, 'IDENTITY', target['identity']))
        stack.enter_context(patch.object(archive, 'SHA256', target['sha256']))
        self.manifest = archive.manifest_for(root.identity(self.lease_path.stat()),
            source_sha256='2'*64, root_binding='3'*64, release_id=self.release_id)
        self.request['manifest'] = self.manifest
        self.live['manifest_sha256'] = archive.BACKUP
        self.installation['library_sha256'] = 'c'*64

    def proof(self, req):
        return {**self.receipt(req), 'profile': archive.PROFILE, 'library_sha256': 'c'*64}

    def run_archive(self, *, finish=None, consume=None):
        info = self.lease_path.stat()
        with PreparationLease(self.lease_path, (info.st_dev, info.st_ino)) as lease:
            parent = os.open(self.lease_path.parent, os.O_PATH | os.O_DIRECTORY)
            server = PreparationStatus(Path(f'/proc/self/fd/{parent}/owner.sock'), lease, self.status)
            child = Mock()
            child.poll.return_value = 0
            def checked(_, req):
                self.events.append('historical-scan')
                # Root ownership/host visibility/scan are explicitly substituted;
                # exact target O_PATH, real Unix peer, start and kernel FLOCK run.
                with patch.object(root, 'open_scope', side_effect=lambda *_: self.scope()), \
                     patch.object(root, 'visibility'), \
                     patch.object(root, 'scan_consumers', return_value=self.proof(req)['visibility']):
                    return {**profile.check(root, self.policy, req), **self.installation}
            try:
                with patch.object(archive, 'launch_checker', return_value=child), \
                     patch.object(boundary, 'finish_checker', side_effect=finish or checked), \
                     patch.object(boundary, 'seal_process_creation', side_effect=lambda: self.events.append('process-sealed')), \
                     patch.object(boundary, 'task_inventory', return_value={(os.getpid(), os.getpid(), process_start(os.getpid()))}):
                    return archive.at_archive_boundary(lease=lease, server=server, status=self.status,
                        manifest=self.manifest, scope_path=str(self.base), installation=self.installation,
                        prepare=lambda: self.events.extend(['SSH-finished', 'B-hashed']),
                        verify_gates=lambda: {key: True for key in boundary.GATES},
                        orchestration_fence=Fence(self.events), consume=consume, adoption_enabled=True)
            finally:
                server.close()
                os.close(parent)

    def test_preparation_and_hashes_before_held_scan_real_owner_then_continuation(self):
        original = archive.hash_archive
        def hashed(*args):
            original(*args)
            self.events.append('native-hashed')
        with patch.object(archive, 'hash_archive', side_effect=hashed):
            self.run_archive(consume=lambda _: self.events.append('approved-continuation'))
        self.assertEqual(self.events, ['SSH-finished', 'B-hashed', 'native-hashed',
            'orchestration-sealed', 'process-sealed', 'historical-scan', 'approved-continuation'])

    def test_profile_policy_fixes_path_inode_hash_backup_and_approval(self):
        profile.validate_profile(root, self.policy, self.request)
        for field, value in (('path', '/etc/shadow'), ('sha256', 'f'*64), ('identity', {**self.policy['target']['identity'], 'ino': 99})):
            changed = copy.deepcopy(self.policy)
            changed['target'][field] = value
            with self.assertRaises(ValueError):
                profile.validate_profile(root, changed, self.request)
        for field, value in (('profile', 'unknown'), ('backup_manifest_sha256', 'f'*64), ('approval_reference', 'UI-Approved')):
            with self.assertRaises(ValueError):
                profile.validate_profile(root, {**self.policy, field: value}, self.request)

    def test_unknown_profile_and_arbitrary_request_paths_reject(self):
        for scope in ('unknown', 'managed-artifacts-v1', '../../shadow'):
            req = copy.deepcopy(self.request)
            req['manifest']['scope_id'] = scope
            with self.assertRaises(ValueError):
                profile.validate_profile(root, self.policy, req)
        for field in ('path', 'command', 'manifest_path'):
            with self.assertRaises(ValueError):
                profile.validate_profile(root, self.policy, {**self.request, field: '/etc/shadow'})

    def test_target_name_traversal_and_identity_reject_before_reads(self):
        for name in ('../shadow', '/etc/shadow', 'other', 'x/y'):
            req = copy.deepcopy(self.request)
            req['manifest']['targets'][0]['name'] = name
            with self.assertRaises(ValueError):
                profile.validate_profile(root, self.policy, req)
        changed = copy.deepcopy(self.request)
        changed['manifest']['targets'][0]['identity']['ino'] += 1
        with self.assertRaises(ValueError):
            profile.validate_profile(root, self.policy, changed)

    def test_root_target_handle_metadata_only(self):
        with patch.object(Path, 'open', side_effect=AssertionError('artifact byte read')):
            self.assertEqual(profile.inspect_target(root, self.policy), {(self.path.stat().st_dev, self.path.stat().st_ino)})
        fd = root.open_path(str(self.path))
        try:
            with self.assertRaises(OSError):
                os.read(fd, 1)
        finally:
            os.close(fd)

    def test_leaf_symlink_rejects(self):
        self.path.rename(self.path.with_name('retained'))
        self.path.symlink_to('/etc/shadow')
        with self.assertRaises(ValueError):
            profile.inspect_target(root, self.policy)

    def test_parent_symlink_rejects(self):
        parent = self.path.parent
        parent.rename(parent.with_name('retained-directory'))
        parent.symlink_to(parent.with_name('retained-directory'), target_is_directory=True)
        with self.assertRaises(OSError):
            profile.inspect_target(root, self.policy)

    def test_truthful_hardlink_identity_still_rejects(self):
        os.link(self.path, self.path.with_name('alias'))
        self.policy['target']['identity'] = root.identity(self.path.stat())
        with self.assertRaises(ValueError):
            profile.inspect_target(root, self.policy)

    def test_substitution_during_scan_rejects_without_action(self):
        action = Mock()
        def replaced(_, req):
            def scan(*args, **kwargs):
                self.path.rename(self.path.with_name('original'))
                self.path.write_bytes(b'approved unprivileged artifact')
                self.path.chmod(0o600)
                return self.proof(req)['visibility']
            with patch.object(root, 'open_scope', side_effect=lambda *_: self.scope()), \
                 patch.object(root, 'visibility'), patch.object(root, 'scan_consumers', side_effect=scan):
                return profile.check(root, self.policy, req)
        with self.assertRaises(ValueError):
            self.run_archive(finish=replaced, consume=action)
        action.assert_not_called()

    def test_denied_visibility_rejects_without_action(self):
        action = Mock()
        def denied(_, req):
            with patch.object(root, 'visibility', side_effect=PermissionError):
                return profile.check(root, self.policy, req)
        with self.assertRaises(PermissionError):
            self.run_archive(finish=denied, consume=action)
        action.assert_not_called()

    def test_denied_protected_thread_scan_blocks_continuation(self):
        action = Mock()
        def denied(_, req):
            with patch.object(root, 'visibility'), \
                 patch.object(root, 'open_scope', side_effect=lambda *_: self.scope()), \
                 patch.object(root, 'scan_consumers', side_effect=PermissionError('opaque maps')):
                return profile.check(root, self.policy, req)
        with self.assertRaises(PermissionError):
            self.run_archive(finish=denied, consume=action)
        action.assert_not_called()

    def test_immediate_precontinuation_clock_recheck_blocks_after_handler_delay(self):
        clocks = [10_000_000_000, 10_000_000_000]
        action = Mock()
        original = archive.validate_receipt
        def delayed(*args):
            original(*args)
            clocks[:] = [x + boundary.FRESH_NS + 1 for x in clocks]
        with patch.object(boundary.time, 'time_ns', side_effect=lambda: clocks[0]), \
             patch.object(boundary.time, 'monotonic_ns', side_effect=lambda: clocks[1]), \
             patch.object(archive, 'validate_receipt', side_effect=delayed), self.assertRaises(ValueError):
            self.run_archive(consume=action)
        action.assert_not_called()

    def test_wrong_owner_start_nonce_or_source_rejects_real_peer_lease(self):
        def wrong(_, req):
            with patch.object(root, 'open_scope', side_effect=lambda *_: self.scope()), patch.object(root, 'visibility'):
                for field, value in (('owner_pid', 1), ('owner_start', '0'), ('nonce', 'a'*64)):
                    with self.assertRaises(ValueError):
                        profile.check(root, self.policy, {**req, field: value})
                other = copy.deepcopy(req)
                other['manifest']['source_sha256'] = 'e'*64
                with self.assertRaises(ValueError):
                    profile.check(root, self.policy, other)
            return self.proof(req)
        self.run_archive(finish=wrong)

    def test_stale_replayed_profile_or_library_output_rejects(self):
        for change in ({'nonce': 'old'}, {'owner_pid': 1}, {'profile': 'managed-artifacts-v1'},
                       {'library_sha256': 'f'*64}, {'issued_ns': time.time_ns()-6_000_000_000},
                       {'issued_mono_ns': time.monotonic_ns()-6_000_000_000}):
            with self.assertRaises(ValueError):
                archive.validate_receipt({**self.proof(self.request), **change}, self.request, self.installation)

    def test_exact_held_target_guard_requires_kernel_FLOCK(self):
        self.manifest['targets'][0]['guard_held'] = True
        with self.assertRaises(ValueError):
            self.run_archive()
        # Fresh fixture keeps original socket evidence, rather than removing it.
        self.setUp()
        self.manifest['targets'][0]['guard_held'] = True
        with self.path.open('rb') as guard:
            fcntl.flock(guard.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertTrue(self.run_archive()['consumer_clearance_passed'])

    def test_bootstrap_rejects_user_owned_library_inputs(self):
        with self.assertRaises(ValueError):
            profile.bootstrap_trust(str(self.path))

    def test_slow_final_witness_expires_output_and_no_action(self):
        proof = self.proof(self.request)
        proof.update(issued_ns=10_000_000_000, scan_started_ns=9_000_000_000,
                     issued_mono_ns=10_000_000_000, scan_started_mono_ns=9_000_000_000)
        clocks = [10_000_000_001, 10_000_000_001]
        def slow():
            clocks[:] = [x + boundary.FRESH_NS + 1 for x in clocks]
            return {(os.getpid(), os.getpid(), process_start(os.getpid()))}
        with patch.object(boundary.time, 'time_ns', side_effect=lambda: clocks[0]), \
             patch.object(boundary.time, 'monotonic_ns', side_effect=lambda: clocks[1]), \
             patch.object(boundary, 'task_inventory', side_effect=slow), self.assertRaises(ValueError):
            archive.validate_receipt(proof, self.request, self.installation)


if __name__ == '__main__':
    unittest.main()
