"""Owned SSD fixtures only. No live services, B writes, root or agent calls."""
from contextlib import contextmanager
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from vk_nightly_generation import NightlyStore, MAX_INDEX, encoded, render_schedule
from vk_routine_restart import run, plan_digest, execution_inventory, wait_for_real_drain


def fixture_readback(folder, manifest):
    # MODEL ONLY, not a physical Windows B acceptance. Actual files were read
    # and hashed by verify(); this models the additional remote readback gate.
    return {'physical_b_verified': True, 'generation': manifest['generation'],
            'scope_sha256': manifest['scope_sha256'],
            'manifest_sha256': hashlib.sha256((folder / 'manifest.json').read_bytes()).hexdigest()}


class RestartSafeguards(unittest.TestCase):
    def setUp(self):
        if not os.path.ismount('/mnt/vk-storage'):
            raise RuntimeError('mounted SSD required')
        self.tmp = tempfile.TemporaryDirectory(prefix='restart-safeguards-', dir='/mnt/vk-storage')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / 'normal-nightly'
        self.root.mkdir()
        self.store = NightlyStore(self.root, 'a' * 64, lambda: self.base, independent_readback=fixture_readback)
        self.store.enroll_empty()

    def file(self, name, data):
        return name, {'kind': 'file', 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                      'uid': 1000, 'gid': 1000, 'mode': 0o600, 'mtime_ns': 123}, io.BytesIO(data)

    def advance(self, changes, absent=(), previous=None, adopted=False):
        return self.store.advance(changes, absent, expected_previous=previous,
                                  reserve_bytes=1024**2, retention_adopted=adopted)

    def test_incremental_is_self_contained_and_only_one_normal_nightly_retained(self):
        incident = self.base / 'protected-incident'
        incident.write_bytes(b'preserve original evidence')
        fallback = self.base / 'protected-fallback'
        fallback.write_bytes(b'preserve fallback')
        first = self.advance([self.file('data/unchanged', b'A'), self.file('data/changed', b'B')])
        old_inode = (self.root / first['generation'] / 'objects' / hashlib.sha256(b'A').hexdigest()).stat().st_ino
        second = self.advance([self.file('data/changed', b'C')], previous=first['generation'], adopted=True)
        current = self.store.current()
        self.assertIsNone(current['parent'])
        self.assertEqual(second['changed_bytes'], 1)
        self.assertFalse((self.root / first['generation']).exists())
        self.assertEqual((self.root / second['generation'] / 'objects' / hashlib.sha256(b'A').hexdigest()).stat().st_ino, old_inode)
        self.store.verify(current)
        self.assertEqual(incident.read_bytes(), b'preserve original evidence')
        self.assertEqual(fallback.read_bytes(), b'preserve fallback')
        self.assertEqual(len(list(self.root.glob('generation-*'))), 1)

    def test_metadata_only_update_reuses_verified_content_without_retransmission(self):
        first = self.advance([self.file('file', b'unchanged bytes')])
        row = dict(self.store.current()['entries']['file']); row['mode'] = 0o640
        result = self.advance([('file', row, None)], previous=first['generation'], adopted=True)
        self.assertEqual(result['changed_bytes'], 0)
        self.assertEqual(self.store.current()['entries']['file']['mode'], 0o640)
        self.store.verify(self.store.current())

    def test_unverified_new_snapshot_never_replaces_current_and_partials_are_bounded(self):
        first = self.advance([self.file('current', b'A')])
        bad = self.file('current', b'bad')
        bad[1]['sha256'] = 'b' * 64
        with self.assertRaisesRegex(ValueError, 'content mismatch'):
            self.advance([bad], previous=first['generation'])
        self.assertEqual(self.store.current()['generation'], first['generation'])
        with self.assertRaisesRegex(ValueError, 'overlap needs reconciliation'):
            self.advance([self.file('current', b'C')], previous=first['generation'])
        self.assertEqual(len(list(self.root.glob('generation-*'))), 2)

    def test_readback_failure_preserves_previous_pointer(self):
        first = self.advance([self.file('current', b'A')])
        original = self.store.verify
        def reject_new(value):
            if value['generation'] != first['generation']:
                raise ValueError('independent readback failed')
            return original(value)
        with patch.object(self.store, 'verify', side_effect=reject_new), self.assertRaises(ValueError):
            self.advance([self.file('current', b'C')], previous=first['generation'])
        self.assertEqual(self.store.current()['generation'], first['generation'])

    def test_no_unauthorized_retention_and_no_recursive_evidence_cleanup(self):
        first = self.advance([self.file('current', b'A')])
        self.advance([self.file('current', b'B')], previous=first['generation'])
        with self.assertRaisesRegex(ValueError, 'not authorized'):
            self.store.retire_previous(first['generation'])
        (self.root / first['generation'] / 'evidence.json').write_text('protected')
        with self.assertRaisesRegex(ValueError, 'unexpected evidence'):
            self.store.retire_previous(first['generation'], retention_adopted=True)
        self.assertTrue((self.root / first['generation'] / 'evidence.json').exists())

    def test_symlink_traversal_replay_missing_hardlink_and_scope_rejected(self):
        with self.assertRaises(ValueError):
            self.advance([self.file('../outside', b'x')])
        # A failed generation is deliberately retained; use independent stores
        # for each remaining rejection instead of deleting failed evidence.
        for index, row in enumerate([{'kind': 'hardlink', 'target': 'missing'},
                                     {'kind': 'file', 'sha256': '../outside', 'bytes': 0}]):
            root = self.base / ('case' + str(index)); root.mkdir()
            store = NightlyStore(root, 'a' * 64, lambda: self.base, independent_readback=fixture_readback); store.enroll_empty()
            with self.assertRaises(ValueError):
                store.advance([('safe', row, None)], [], expected_previous=None, reserve_bytes=1000)
        root = self.base / 'alias'; root.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError): NightlyStore(root, 'a' * 64, lambda: self.base)
        with self.assertRaises(ValueError): self.store.load('../elsewhere')
        with self.assertRaises(ValueError): NightlyStore(self.root, 'bad', lambda: self.base)

    def test_capacity_lease_and_current_generation_retirement_fail_closed(self):
        with self.assertRaises(ValueError):
            self.store.advance([], [], expected_previous=None, reserve_bytes=10**20)
        first = self.advance([self.file('current', b'A')])
        with open(self.root / 'lease', 'rb') as lease:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                self.advance([], previous=first['generation'])
        with self.assertRaises(ValueError):
            self.store.retire_previous(first['generation'], retention_adopted=True)
        with self.assertRaises(ValueError): self.advance([], previous='generation-' + '0' * 32)

    def test_missing_physical_b_readback_blocks_publication(self):
        self.store.independent_readback = None
        with self.assertRaisesRegex(ValueError, 'physical B'):
            self.advance([self.file('current', b'A')])
        self.assertIsNone(self.store.current())

    def test_scripted_timer_is_render_only_with_no_agent_or_privilege_calls(self):
        units = render_schedule('/mnt/vk-storage/approved-job.py', '/mnt/vk-storage/config.json')
        self.assertIn('02:00:00 UTC', units['timer'])
        self.assertIn('NoNewPrivileges=yes', units['service'])
        self.assertIn('Type=oneshot\n', units['service'])
        self.assertIn('TimeoutStartSec=7200\n', units['service'])
        self.assertIn('TimeoutStopSec=30\n', units['service'])
        self.assertNotIn('RuntimeMaxSec=', units['service'])
        self.assertFalse(units['enabled'])
        self.assertIsNone(units['test_run_receipt'])
        self.assertNotIn('sudo', units['service'])
        self.assertNotIn('codex', units['service'])
        with self.assertRaises(ValueError): render_schedule('/path/../unsafe', '/cfg')

    def test_removed_directory_and_metadata_survive_manifest(self):
        first = self.advance([('dir', {'kind': 'directory', 'mode': 0o700}, None), self.file('dir/child', b'A'),
                              ('link', {'kind': 'symlink', 'target': '/original/protected/path'}, None)])
        self.advance([], absent=['dir'], previous=first['generation'], adopted=True)
        self.assertEqual(set(self.store.current()['entries']), {'link'})
        self.assertEqual(self.store.current()['entries']['link']['target'], '/original/protected/path')
        self.assertFalse((self.root / 'link').exists(), 'links remain metadata, never a route into production')

    def test_host_scale_537739_path_manifest_exceeds_old_64mib_and_fits_explicit_budget(self):
        entries = {('home/mcp/' + 'p' * 115 + '/' + str(index)): {'kind': 'directory', 'mode': 0o700}
                   for index in range(537739)}
        data = encoded({'entries': entries})
        self.assertGreater(len(data), 64 * 1024**2)
        self.assertLess(len(data), MAX_INDEX)
        self.assertEqual(len(json.loads(data)['entries']), 537739)


class Routine(unittest.TestCase):
    def setUp(self):
        self.fix_ready = time.monotonic()
        self.plan = {'route': 'authoritative-current-data', 'retire_paths': [], 'cleanup_enabled': False,
                     'fallback_compatible': True, 'action_authorized': True}
        self.events = []
        self.now = 0
        parent = self
        class Driver:
            def authorization(self, plan):
                return {'authenticated_owner_approval': True, 'authorized_plan_sha256': plan_digest(plan)}
            def build(self, plan, budget):
                parent.events.append('prepare')
                return {'verified': True, 'plan_sha256': plan_digest(plan)}
            def validate(self, plan, package, budget):
                parent.events.append('validate')
                return {'passed': True, 'plan_sha256': plan_digest(plan),
                        'backend_unchanged': True, 'backend_api_compatible': True}
            def backup(self, plan, package, budget):
                parent.events.append('backup')
                return {'desktop_verified': True, 'integrity': 'ok', 'full_baseline_retained': True,
                        'plan_sha256': plan_digest(plan)}
            def review(self, plan, package, backup, budget):
                parent.events.append('review')
                return {'passed': True, 'approved_plan_sha256': plan_digest(plan)}
            @contextmanager
            def held(self, plan):
                parent.events.append('held'); yield
            def boundary(self, plan, package, backup):
                parent.events.append('boundary')
                return {'authenticated_owner': True, 'lease_held': True, 'active_executions': [], 'identity_pins_match': True}
            def handover(self, plan, package, backup, budget):
                parent.events.append('handover')
                return {'plan_sha256': plan_digest(plan), 'live_acceptance': True, 'latest_data_preserved': True,
                        'fallback_retained': True, 'cleanup_enabled': False, 'blocked_work_resumed': True}
            def recover_latest(self, plan):
                parent.events.append('latest-data-recovery')
                return {'latest_data_preserved': True}
        self.driver = Driver()

    def test_process_preparation_order_real_processes_and_kernel_lease(self):
        with tempfile.TemporaryDirectory(dir='/mnt/vk-storage') as raw:
            log = Path(raw) / 'events'
            original_prepare = self.driver.build
            original_backup = self.driver.backup
            def child(label):
                subprocess.run([sys.executable, '-B', '-c',
                                'from pathlib import Path; import sys; p=Path(sys.argv[1]); '
                                'p.open("a").write(sys.argv[2]+"\\n")', str(log), label], check=True)
            def prepare(plan, budget):
                child('actual-package-process-finished'); return original_prepare(plan, budget)
            def backup(plan, package, budget):
                child('actual-backup-process-finished'); return original_backup(plan, package, budget)
            @contextmanager
            def held(plan):
                with open(Path(raw) / 'lease', 'a+b') as lease:
                    fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self.assertEqual(log.read_text().splitlines(), ['actual-package-process-finished', 'actual-backup-process-finished'])
                    self.events.append('held'); yield
            self.driver.build, self.driver.backup, self.driver.held = prepare, backup, held
            result = run(self.plan, self.driver, fix_ready_monotonic=self.fix_ready)
            self.assertTrue(result['passed'])
            self.assertEqual(self.events, ['prepare', 'validate', 'backup', 'review', 'held', 'boundary', 'handover'])

    def test_real_active_execution_inventory_is_not_falsified_even_at_host_scale(self):
        with patch.object(self.driver, 'boundary', return_value={'authenticated_owner': True, 'lease_held': True,
                          'active_executions': list(range(4582)), 'identity_pins_match': True}):
            result = run(self.plan, self.driver, fix_ready_monotonic=self.fix_ready)
        self.assertFalse(result['passed'])
        self.assertNotIn('handover', self.events)
        self.assertFalse(result['production_action_attempted'])

    def test_review_binding_backup_scope_and_policy_fail_before_action(self):
        for key, value in [('route', 'restore'), ('retire_paths', ['/archive']),
                           ('cleanup_enabled', True), ('fallback_compatible', False), ('action_authorized', False)]:
            plan = dict(self.plan); plan[key] = value
            self.assertFalse(run(plan, self.driver, fix_ready_monotonic=self.fix_ready)['passed'])
        with patch.object(self.driver, 'review', return_value={'passed': True, 'approved_plan_sha256': 'wrong'}):
            self.assertFalse(run(self.plan, self.driver, fix_ready_monotonic=self.fix_ready)['passed'])
        self.assertNotIn('handover', self.events)
        with patch.object(self.driver, 'authorization', return_value={'approved': True}):
            self.assertFalse(run(self.plan, self.driver, fix_ready_monotonic=self.fix_ready)['passed'])

    def test_ten_minute_total_bound_and_separate_timing(self):
        result = run(self.plan, self.driver, fix_ready_monotonic=self.fix_ready)
        self.assertEqual(result['routine_goal_seconds'], 600)
        self.assertIn('preparation_seconds', result)
        self.assertIn('switch_seconds', result)
        def prepare(plan, budget):
            self.now = 601
            return {'verified': True, 'plan_sha256': plan_digest(plan)}
        self.driver.build = prepare
        result = run(self.plan, self.driver, fix_ready_monotonic=0, clock=lambda: self.now)
        self.assertFalse(result['passed'])
        self.assertFalse(result['production_action_attempted'])

    def test_fix_ready_queue_time_is_counted_and_resumed_work_is_required(self):
        result = run(self.plan, self.driver, fix_ready_monotonic=0, clock=lambda: 601)
        self.assertFalse(result['passed'])
        self.assertFalse(result['production_action_attempted'])
        with patch.object(self.driver, 'handover', return_value={'plan_sha256': plan_digest(self.plan),
                          'live_acceptance': True, 'latest_data_preserved': True,
                          'fallback_retained': True, 'cleanup_enabled': False, 'blocked_work_resumed': False}):
            self.assertFalse(run(self.plan, self.driver, fix_ready_monotonic=self.fix_ready)['passed'])

    def test_frontend_only_requires_backend_identity_and_api_compatibility(self):
        self.plan['deployment_kind'] = 'frontend-only'
        with patch.object(self.driver, 'validate', return_value={'passed': True, 'plan_sha256': plan_digest(self.plan)}):
            self.assertFalse(run(self.plan, self.driver, fix_ready_monotonic=self.fix_ready)['passed'])

    def test_production_timestamp_remains_mandatory(self):
        with self.assertRaises(TypeError):
            run(self.plan, self.driver)  # Deliberately omitted: no wrapper supplies it.
        self.assertEqual(self.events, [])

    def test_real_sqlite_execution_completion_is_waited_for_and_never_forged(self):
        with tempfile.TemporaryDirectory(dir='/mnt/vk-storage') as raw:
            database = Path(raw) / 'lifecycle.sqlite'
            key = bytes.fromhex('1' * 32)
            with sqlite3.connect(database) as db:
                db.execute('CREATE TABLE execution_processes(id BLOB, status TEXT, dropped INTEGER)')
                db.execute("INSERT INTO execution_processes VALUES(?, 'running', 0)", (key,))
            ticks = [0]
            def actual_fixture_completion(seconds):
                # Only this owned fixture models the original execution's real
                # lifecycle writer. Production wait_for_real_drain never writes.
                with sqlite3.connect(database) as db:
                    db.execute("UPDATE execution_processes SET status='completed'")
                ticks[0] += seconds
            self.assertEqual(execution_inventory(database), ['1' * 32])
            result = wait_for_real_drain(lambda: execution_inventory(database), '1' * 32, 600,
                                        clock=lambda: ticks[0], sleep=actual_fixture_completion)
            self.assertTrue(result['real_execution_drained'])
            self.assertFalse(result['status_rows_changed'])
            with self.assertRaises(ValueError):
                wait_for_real_drain(lambda: ['2' * 32], '1' * 32, 600, clock=lambda: 0)

    def test_failed_acceptance_recovers_latest_and_never_restores_old_snapshot(self):
        with patch.object(self.driver, 'handover', return_value={'live_acceptance': False}):
            result = run(self.plan, self.driver, fix_ready_monotonic=self.fix_ready)
        self.assertFalse(result['passed'])
        self.assertEqual(result['failed_stage'], 'handover')
        self.assertTrue(result['recovery']['latest_data_preserved'])
        self.assertFalse(result['operator_command_requested'])


if __name__ == '__main__': unittest.main()
