"""Actual PR229 capture/archive/controller contracts, retained offline fixtures.

The backing archive store is explicitly local test data, never real B. No receiver
SSH, API, service, route, cleanup or permissions bypass is called. Archives in
the fixture backing store are not capture staging or production acceptance.
"""
import copy
from contextlib import contextmanager
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import vk_direct_capture
import vk_rolling_backup
from vk_archive_store import Archive
from vk_archive_stream import StreamingArchive
from vk_candidate_direct_b import BoundSupervisor, DirectBProvider
from vk_candidate_generation import (Blocked, CandidateController, Layout, digest, inventory,
                                     namespace_runtime_identity)
from vk_change_journal import Journal, scope
from vk_prep_common import identity


PARENT = Path('/mnt/vk-storage/vk-safe-release-20261008/direct-b-contract-tests')


class TestOwner(BoundSupervisor):
    """Record only ownership intents; never start a process or switch a route."""
    def activate_candidate(self, proof, receipt):
        return {'root_binding': proof['root_binding'], 'fixture_only': True, 'actual_instance_started': False}

    activate_compatible_fallback = activate_candidate


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix=self._testMethodName + '-', dir=PARENT))
        self.inc = self.root / 'incumbent'
        (self.inc / 'home/state').mkdir(parents=True)
        self.db = self.inc / 'home/state/state.sqlite'
        with sqlite3.connect(self.db) as db:
            db.execute('CREATE TABLE retained(value TEXT)')
            db.execute("INSERT INTO retained VALUES('before')")
            db.execute('CREATE TABLE vk_runtime_identity(singleton INTEGER PRIMARY KEY, dataset_id TEXT)')
            db.execute('INSERT INTO vk_runtime_identity VALUES(1, ?)', ['0123456789abcdef' * 2])
        (self.inc / 'home/state/note').write_bytes(b'original dirty work')
        os.setxattr(self.inc / 'home/state/note', 'user.proof', b'preserve xattr')
        os.link(self.inc / 'home/state/note', self.inc / 'home/state/note-link')
        (self.inc / 'home/worktrees').symlink_to('state')
        self.store = self.root / 'fixture-archive-store'
        self.store.mkdir()
        self.journals = []
        self.scope = digest({'namespace': '/', 'required': ['home/state/state.sqlite'], 'fixture_only': True})
        # Actual combined tooling hashes, not a dummy binary-release acceptance.
        self.source = digest({p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in Path(__file__).parent.glob('vk_*.py')})
        self.layout = Layout(self.root / 'candidate', self.root / 'candidate/tree',
                             self.root / 'candidate/evidence', (self.inc, self.store))
        self.policy = {'source': self.source, 'scope': self.scope, 'measured': True,
                       'reserve_bytes': 1024 * 1024, 'fixture_only': True, 'max_fixture_payload': 8 * 1024**2}
        self.supervisor = TestOwner(self.layout, self.source, self.scope, self.policy, 'c' * 64, fixture_only=True)
        self.provider = DirectBProvider(self.scope, ['home/state/state.sqlite'],
                                        archive_factory=self.factory, fixture_only=True)
        self.controller = CandidateController(self.layout, self.scope, self.source, self.provider, self.supervisor,
            ['home/state/state.sqlite'], fallback_artifact_sha256='c' * 64, capacity_policy_sha256=digest(self.policy))
        self.stop_proof(None)
        self.lease = (self.root / 'scope-writer-lease').open('xb+')
        fcntl.flock(self.lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.read_passes = []

    def tearDown(self):
        for journal in self.journals:
            journal.close()
        self.lease.close()
        # Every source, failed attempt, result, old state and archive is retained.

    def factory(self, ref, *args, **kwargs):
        self.read_passes.append(ref['archive'])
        return Archive(ref, archive_directory=self.store, desktop_only=False)

    def mirror(self, source):
        if isinstance(source, StreamingArchive):
            tar = io.BytesIO()
            source.produce(tar)
            require_size = tar.tell()
            if require_size > 8 * 1024**2:
                raise Blocked('owned test archive exceeds 8 MiB')
            encoded = subprocess.run(['zstd', '-T1', '-3', '-c'], input=tar.getvalue(),
                                     capture_output=True, check=True).stdout
            source.sha256, source.bytes = hashlib.sha256(encoded).hexdigest(), len(encoded)
            target = self.store / source.name
            with target.open('xb') as out:
                out.write(encoded)
            return {'name': source.name, 'bytes': len(encoded), 'sha256': source.sha256,
                    'desktop_directory': 'B:/vk-backups/offline-contract-fixture',
                    'desktop_verified': True, 'direct_stream': True}
        raw = Path(source).read_bytes()
        return {'desktop_verified': True, 'sha256': hashlib.sha256(raw).hexdigest(),
                'bytes': len(raw), 'fixture_metadata_only': True}

    def capture(self, name, source=None, parent=None, journal=None, frozen=False, origin='incumbent'):
        source = source or self.inc
        db = source / 'home/state/state.sqlite'
        plan = {'sources': [str(source)], 'sqlite_snapshots': [str(db)],
                'excluded_rebuildable_directories': []}
        if journal is None:
            journal = Journal(plan)
            journal.tree(source)
            journal.ready = True
            self.journals.append(journal)
        kwargs = {}
        if frozen:
            kwargs['verify_fence'] = lambda: self.supervisor.held_fence(self.lease.fileno(), name)
        backup = self.root / ('capture-' + name)
        with patch.object(vk_direct_capture, 'Archive', self.factory), patch.object(vk_rolling_backup, 'Archive', self.factory):
            result = vk_direct_capture.capture(plan, backup, journal.report, self.mirror, parent, self.mirror,
                                               max_snapshot_bytes=64 * 1024, **kwargs)
        self.provider.register(name, result, identity(plan), identity(scope(plan)), source,
                               origin_root_binding=origin)
        self.assertEqual(result['local_archive_bytes'], 0)
        self.assertEqual(result['local_snapshot_bytes'], 0)
        self.assertFalse(list(backup.rglob('*.tar.zst')))
        self.assertFalse(list(backup.rglob('*.sqlite')))
        return result, journal

    def stop_proof(self, binding):
        self.supervisor.stopped_proofs[binding] = {'root_binding': binding, 'source': self.source,
             'scope': self.scope, 'all_declared_writers_stopped': True, 'fixture_only': True}

    def acceptance(self, stage, capture):
        binding = self.layout.binding()
        self.stop_proof(binding)
        self.supervisor.capture = capture
        pin = namespace_runtime_identity(self.layout, '/home/state/state.sqlite', '/home/worktrees')
        checks = ('private_filesystem_pid_network_manager_boundary', 'no_incumbent_write_access',
                  'binary_module_scanner_bound', 'capacity_controller_ready', 'runtime_database_workspace_identity_bound',
                  'operational_dependency_closure_verified',
                  'whole_state_capacity_restore_verified', 'full_required_linux_metadata_verified',
                  'recommend_and_usage_controls_preserved', 'consent_accepted', 'current_report_receipts_preserved',
                  'cleanup_unavailable', 'fallback_latest_data_compatible')
        # These are explicit fixture receipts. Real packaged scanner, consent,
        # RAM/whole-state/worker acceptance are not supplied or certified here.
        self.supervisor.acceptance_proofs[stage] = {'root_binding': binding, 'source': self.source,
            'scope': self.scope, 'stage': stage, 'capture_id': capture,
            'manifest_sha256': digest(inventory(self.layout.tree)), 'runtime_identity_sha256': pin['sha256'],
            'checks': {k: True for k in checks}, 'fallback_artifact_sha256': 'c' * 64, 'fixture_only': True}

    def prepare_tested(self):
        initial, journal = self.capture('initial')
        self.controller.restore('initial')
        self.acceptance('rehearsal', 'initial')
        self.controller.accept_rehearsal()
        return initial, journal

    def test_authenticated_recorded_missing_link_policy_is_opt_in(self):
        (self.inc / 'home/history-link').symlink_to('unavailable-history')
        self.capture('initial')
        with self.assertRaisesRegex(Blocked, 'namespace dependency missing'):
            self.provider.verify('initial')
        self.provider.preserve_recorded_missing_links = True
        proof = self.provider.verify('initial')
        self.assertEqual(proof['recorded_link_exceptions'], {'home/history-link': 'unavailable-history'})
        self.assertFalse(proof['operational_dependency_closure_verified'])
        self.controller.restore('initial')
        self.assertEqual(os.readlink(self.layout.tree / 'home/history-link'), 'unavailable-history')
        self.assertEqual(inventory(self.layout.tree), proof['entries'])

    def test_actual_direct_capture_chain_catchup_and_latest_data_fallback(self):
        initial, journal = self.prepare_tested()
        (self.layout.tree / 'home/state/test-only').write_bytes(b'keep test evidence')
        with sqlite3.connect(self.db) as db:
            db.execute("INSERT INTO retained VALUES('since initial')")
        final, _ = self.capture('final', parent=initial, journal=journal, frozen=True)
        binding = self.layout.binding()
        self.controller.catch_up('final')
        self.assertEqual(self.layout.binding(), binding)
        self.assertEqual(list(self.layout.evidence.glob('*-test-and-prior-state/home/state/test-only'))[0].read_bytes(),
                         b'keep test evidence')
        self.acceptance('activation', 'final')
        self.controller.promote()  # Only the explicit test intent owner.
        with sqlite3.connect(self.layout.tree / 'home/state/state.sqlite') as db:
            db.execute("INSERT INTO retained VALUES('after intent promotion')")
        latest_parent, latest_journal = self.capture('latest-parent', source=self.layout.tree, origin=binding)
        latest, _ = self.capture('latest', source=self.layout.tree, parent=latest_parent,
                                journal=latest_journal, frozen=True, origin=binding)
        def after_normalization(stage, capture):
            self.acceptance(stage, capture)
            return self.supervisor.acceptance_proofs[stage]
        self.supervisor.acceptance_reader = after_normalization
        self.controller.fallback('latest')
        with sqlite3.connect(self.layout.tree / 'home/state/state.sqlite') as db:
            self.assertIn(('after intent promotion',), db.execute('SELECT value FROM retained').fetchall())
        self.assertEqual(self.layout.binding(), binding)
        self.assertFalse(self.controller.owner_receipt['actual_instance_started'])
        self.assertTrue(self.provider.verify('latest')['fixture_only'])

    def test_acl_xattr_modes_links_and_bulk_replay_from_actual_pax(self):
        path = self.inc / 'home/state/note'
        acl = struct.pack('<I', 2) + b''.join(struct.pack('<HHI', tag, perms, ident) for tag, perms, ident in
            [(1,6,0xffffffff),(2,4,2000),(4,0,0xffffffff),(16,4,0xffffffff),(32,0,0xffffffff)])
        os.setxattr(path, 'system.posix_acl_access', acl)
        self.capture('initial')
        passes, contents = [], Archive.contents
        @contextmanager
        def counted(archive):
            passes.append(archive.sha256)
            with contents(archive) as tar:
                yield tar
        with patch.object(Archive, 'contents', counted):
            self.controller.restore('initial')
        self.assertEqual(os.getxattr(self.layout.tree / 'home/state/note', 'system.posix_acl_access'), acl)
        self.assertEqual(os.getxattr(self.layout.tree / 'home/state/note', 'user.proof'), b'preserve xattr')
        self.assertEqual((self.layout.tree / 'home/state/note').stat().st_ino,
                         (self.layout.tree / 'home/state/note-link').stat().st_ino)
        self.assertEqual(os.readlink(self.layout.tree / 'home/worktrees'), 'state')
        # Manifest authentication plus one index pass and one replay pass;
        # adding files must not cause a full archive download for each file.
        self.assertEqual(len(passes), 3)

    def test_late_replay_failure_retains_partial_tree_without_acceptance(self):
        self.capture('initial')
        replay = self.provider.file_members
        @contextmanager
        def failing(capture, selected):
            with replay(capture, selected) as members:
                yield members
            raise ValueError('injected EOF verification failure')
        with patch.object(self.provider, 'file_members', failing):
            with self.assertRaisesRegex(ValueError, 'EOF verification'):
                self.controller.restore('initial')
        self.assertEqual(self.controller.phase, 'restoring')
        self.assertTrue(self.layout.tree.exists())
        self.assertFalse(list(self.layout.evidence.glob('*-restored.json')))

    def test_stale_acceptance_cannot_authorize_promotion(self):
        initial, journal = self.prepare_tested()
        self.capture('final', parent=initial, journal=journal, frozen=True)
        self.controller.catch_up('final')
        self.acceptance('activation', 'final')
        (self.layout.tree / 'home/state/unaccepted-edit').write_bytes(b'retained test state')
        with self.assertRaises(Blocked):
            self.controller.promote()
        self.assertEqual(self.controller.phase, 'refreshed')
        self.assertIsNone(self.controller.owner_receipt)

    def test_released_kernel_lease_blocks_fenced_refresh(self):
        initial, journal = self.prepare_tested()
        self.capture('final', parent=initial, journal=journal, frozen=True)
        fcntl.flock(self.lease, fcntl.LOCK_UN)
        before = inventory(self.layout.tree)
        with self.assertRaisesRegex(Blocked, 'lease is no longer held'):
            self.controller.catch_up('final')
        self.assertEqual(inventory(self.layout.tree), before)

    def test_archive_corruption_cannot_start_restore(self):
        result, _ = self.capture('initial')
        path = self.store / result['archive']
        with path.open('ab') as stream:
            stream.write(b'corrupt fixture suffix')
        with self.assertRaises(ValueError):
            self.controller.restore('initial')
        self.assertFalse(self.layout.tree.exists())

    def test_default_bound_supervisor_has_no_operational_launch(self):
        supervisor = BoundSupervisor(self.layout, self.source, self.scope, self.policy, 'c' * 64, fixture_only=True)
        for action in (supervisor.activate_candidate, supervisor.activate_compatible_fallback):
            with self.assertRaisesRegex(Blocked, 'no operational'):
                action({}, {})

    def test_provider_missing_plan_or_metadata_bindings_rejected(self):
        result, _ = self.capture('initial')
        bad = copy.deepcopy(result)
        bad['metadata_receipt']['desktop_verified'] = False
        with self.assertRaisesRegex(Blocked, 'metadata publication'):
            self.provider.register('bad', bad, result['plan_sha256'], result['scope_sha256'], self.inc,
                                   origin_root_binding='incumbent')

    def test_descriptor_fence_changes_cannot_borrow_old_published_digest(self):
        result, _ = self.capture('initial')
        altered = copy.deepcopy(result)
        altered['writer_fence'] = {'verified': True, 'forged': True}
        with self.assertRaisesRegex(Blocked, 'descriptor digest'):
            self.provider.register('changed', altered, result['plan_sha256'], result['scope_sha256'], self.inc,
                                   origin_root_binding='incumbent')

    def test_fixture_policy_cannot_be_used_by_operational_supervisor(self):
        with self.assertRaisesRegex(Blocked, 'fixture capacity policy'):
            BoundSupervisor(self.layout, self.source, self.scope, self.policy, 'c' * 64)


if __name__ == '__main__':
    if not os.path.ismount('/mnt/vk-storage'):
        raise SystemExit('mounted secondary SSD required')
    PARENT.mkdir(exist_ok=True)
    unittest.main(verbosity=2)
