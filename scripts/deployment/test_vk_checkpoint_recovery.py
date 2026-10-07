import json
import os
from pathlib import Path
import socket
from types import SimpleNamespace
from unittest.mock import patch
import unittest

import test_vk_rolling_backup as fixture
import vk_rolling_backup as backup
import vk_runtime_ephemeral as ephemeral
from vk_backup_readiness import verify_workload


class CheckpointRecoveryTests(unittest.TestCase):
    setUp = fixture.BackupTests.setUp
    tearDown = fixture.BackupTests.tearDown
    mirror = fixture.BackupTests.mirror
    backup = fixture.BackupTests.backup
    restored = fixture.BackupTests.restored

    def abandoned(self):
        with patch.object(backup, 'validate_archive_warnings', side_effect=ValueError('pre-publication rejection')):
            with self.assertRaisesRegex(ValueError, 'pre-publication'):
                self.backup()
        return next(self.backups.glob('checkpoint-/*'))

    def test_verified_unpublished_archive_recovers_without_recopy_and_next_delta_recaptures_db(self):
        folder = self.abandoned()
        archive = next(folder.glob('*.tar.zst'))
        before = backup.digest(archive)
        pending = backup.recover_online_checkpoint(self.plan, self.backups, folder, self.journal.report)
        self.assertEqual(pending['database_proofs'], {})
        self.assertEqual(backup.digest(archive), before)
        result = backup.resume_delivery(self.plan, self.backups, folder, self.journal.report, self.mirror, self.mirror)
        self.assertTrue(result['passed'])
        delta = self.backup(result)
        self.assertIn(str(self.database), delta['sqlite_snapshots'])
        self.assertEqual((self.restored(delta) / self.note.name).read_text(), self.note.read_text())

    def test_recovery_rejects_changed_plan_or_journal(self):
        folder = self.abandoned()
        with self.assertRaisesRegex(ValueError, 'original full'):
            backup.recover_online_checkpoint({**self.plan, 'critical_sqlite': []}, self.backups, folder, self.journal.report)
        self.journal.instance = 'different'
        with self.assertRaisesRegex(ValueError, 'continuity'):
            backup.recover_online_checkpoint(self.plan, self.backups, folder, self.journal.report)

    def test_recovery_rejects_truncated_archive(self):
        folder = self.abandoned()
        archive = next(folder.glob('*.tar.zst'))
        archive.write_bytes(archive.read_bytes()[:30])
        with self.assertRaises(Exception):
            backup.recover_online_checkpoint(self.plan, self.backups, folder, self.journal.report)
        self.assertFalse((folder / 'pending-delivery.json').exists())

    def test_ephemeral_requires_exact_known_member_and_observed_deletion(self):
        raw = str(self.source / 'tmp/arg0/codex-arg0Abc123/apply_patch')
        log = 'tar: ' + raw.lstrip('/') + ': Warning: Cannot stat: No such file or directory'
        with patch.object(ephemeral, 'HOMES', (str(self.source),)):
            plan = ephemeral.warning_plan(log, self.plan)
            watched = {'changed': [raw], 'events': {raw: 0x200}}
            self.assertEqual(backup.validate_archive_warnings(log, watched, plan, True), [raw])
            for online, events in [(False, 0x200), (True, 0x2)]:
                with self.assertRaises(ValueError):
                    backup.validate_archive_warnings(log, {'changed': [raw], 'events': {raw: events}}, plan, online)
            with self.assertRaisesRegex(ValueError, 'Unknown Codex'):
                ephemeral.warning_plan(log.replace('apply_patch', 'user-work.txt'), self.plan)
            unrelated = log.replace('tmp/arg0/codex-arg0Abc123', 'sessions')
            with self.assertRaises(ValueError):
                backup.validate_archive_warnings(unrelated, watched, ephemeral.warning_plan(unrelated, self.plan), True)

    def test_clean_full_checkpoint_accepts_zero_recopy_and_rejects_scope_drift(self):
        proof = {'passed': True, 'full_current_checkpoint': True, 'all_protected_recopy_roots_in_archive': True}
        (self.root / 'full-checkpoint-proof.json').write_text(json.dumps(proof))
        baseline = {'journal_instance': 'same'}
        watched = {'ready': True, 'errors': [], 'instance': 'same'}
        adapter = {'production_recopy_roots': [], 'recopy_copies': []}
        self.assertTrue(verify_workload(self.root, adapter, baseline, watched))
        watched['required_subtree_recopy'] = ['/new/root']
        with self.assertRaisesRegex(ValueError, 'workload'):
            verify_workload(self.root, adapter, baseline, watched)

    def test_present_known_runtime_socket_is_distinct_from_file_payload(self):
        path = self.source / 'app-server-daemon/daemon-updater.sock'
        path.parent.mkdir()
        with socket.socket(socket.AF_UNIX) as endpoint, patch.object(ephemeral, 'HOMES', (str(self.source),)):
            endpoint.bind(str(path))
            log = 'tar: ' + str(path).lstrip('/') + ': socket ignored'
            self.assertEqual(ephemeral.runtime_socket_warning(log, self.plan), str(path))
            adapter = SimpleNamespace(validate_archive_warnings=backup.validate_archive_warnings)
            ephemeral.install(adapter)
            self.assertEqual(adapter.validate_archive_warnings(log, {'changed': [], 'events': {}}, self.plan, True), [str(path)])
            with self.assertRaises(ValueError):
                adapter.validate_archive_warnings(log + '\ntar: private.txt: Cannot stat: No such file or directory', {'changed': []}, self.plan, True)
            with self.assertRaises(ValueError):
                ephemeral.runtime_socket_warning(log, {'sources': []})
            with patch.object(os, 'getuid', return_value=os.getuid() + 1):
                with self.assertRaisesRegex(ValueError, 'owned socket'):
                    ephemeral.runtime_socket_warning(log, self.plan)

    def test_socket_warning_rejects_regular_missing_linked_and_unknown_paths(self):
        path = self.source / 'app-server-daemon/daemon-updater.sock'
        path.parent.mkdir()
        log = 'tar: ' + str(path).lstrip('/') + ': socket ignored'
        with patch.object(ephemeral, 'HOMES', (str(self.source),)):
            with self.assertRaises(OSError):
                ephemeral.runtime_socket_warning(log, self.plan)
            path.write_text('irreplaceable fixture data')
            with self.assertRaisesRegex(ValueError, 'owned socket'):
                ephemeral.runtime_socket_warning(log, self.plan)
            path.unlink()
            path.symlink_to(self.note)
            with self.assertRaises(ValueError):
                ephemeral.runtime_socket_warning(log, self.plan)
            with self.assertRaises(ValueError):
                ephemeral.runtime_socket_warning(log.replace('daemon-updater.sock', 'user.sock'), self.plan)
