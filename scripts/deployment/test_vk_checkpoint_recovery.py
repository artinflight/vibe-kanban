import json
import os
from pathlib import Path
import socket
import subprocess
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
        from legacy_capture_fixture import legacy_capture
        with patch.object(backup, 'validate_archive_warnings', side_effect=ValueError('pre-publication rejection')):
            with self.assertRaisesRegex(ValueError, 'pre-publication'):
                legacy_capture(self.plan, self.backups, self.journal.report, self.mirror, publish=self.mirror)
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

    def runtime_case(self, directory, name):
        path = self.source / directory / name
        path.parent.mkdir(exist_ok=True)
        log = 'tar: ' + str(path).lstrip('/') + ': Warning: Cannot stat: No such file or directory'
        return path, log, {'changed': [str(path)], 'events': {str(path): 0x200}}

    def test_released_runtime_names_require_observed_online_deletion(self):
        thread = '01a1181d-8887-7962-bb8c-597d70cbfaf4'
        with patch.object(ephemeral, 'HOMES', (str(self.source),)):
            for directory, name in [('shell_snapshots', thread + '.1791408487176536081.sh'),
                                    ('thread-writer-locks', thread + '.lock')]:
                path, log, watched = self.runtime_case(directory, name)
                plan = ephemeral.warning_plan(log, self.plan)
                self.assertIn(str(path), plan['online_ephemeral_roots'])
                self.assertNotIn(str(path.parent), plan['online_ephemeral_roots'])
                self.assertEqual(backup.validate_archive_warnings(log, watched, plan, True), [str(path)])
                for observation, online in [(watched, False), ({'changed': [], 'events': {}}, True),
                                           ({'changed': [str(path)], 'events': {str(path): 0x2}}, True)]:
                    with self.assertRaises(ValueError):
                        backup.validate_archive_warnings(log, observation, plan, online)
                path.write_text('present data must not be waived')
                with self.assertRaises(ValueError):
                    backup.validate_archive_warnings(log, watched, plan, True)
                path.unlink()
                path.symlink_to(self.note)
                with self.assertRaises(ValueError):
                    backup.validate_archive_warnings(log, watched, plan, True)
                path.unlink()

    def test_runtime_classifier_never_waives_other_names_or_required_state(self):
        thread = '01a1181d-8887-7962-bb8c-597d70cbfaf4'
        with patch.object(ephemeral, 'HOMES', (str(self.source),)):
            for directory, name in [('sessions', thread + '.lock'), ('shell_snapshots', 'user-work.sh'),
                                    ('shell_snapshots', thread + '.sh'),
                                    ('shell_snapshots', thread + '.12.sh/notes.txt'),
                                    ('thread-writer-locks', '.coordination.lock'),
                                    ('thread-writer-locks', 'notes.lock')]:
                path = self.source / directory / name
                log = 'tar: ' + str(path).lstrip('/') + ': Warning: Cannot stat: No such file or directory'
                plan = ephemeral.warning_plan(log, self.plan)
                with self.assertRaises(ValueError):
                    backup.validate_archive_warnings(log, {'changed': [str(path)], 'events': {str(path): 0x200}}, plan, True)
            path, log, _ = self.runtime_case('shell_snapshots', thread + '.123.sh')
            with self.assertRaises(ValueError):
                ephemeral.warning_plan(log, {**self.plan, 'sources': [*self.plan['sources'], str(path)]})
            self.assertFalse(ephemeral.released_runtime_file(path, {'sources': []}))
            with patch.object(os, 'getuid', return_value=os.getuid() + 1):
                with self.assertRaises(ValueError):
                    ephemeral.warning_plan(log, self.plan)

    def test_runtime_classifier_rejects_symlink_parent(self):
        with patch.object(ephemeral, 'HOMES', (str(self.source),)):
            root = self.source / 'thread-writer-locks'
            root.symlink_to(self.root, target_is_directory=True)
            raw = root / '01a1181d-8887-7962-bb8c-597d70cbfaf4.lock'
            with self.assertRaises(ValueError):
                ephemeral.warning_plan('tar: ' + str(raw).lstrip('/') + ': Warning: Cannot stat: No such file or directory', self.plan)

    def test_real_capture_runtime_release_restores_history_and_catches_up_deletion(self):
        thread = '01a1181d-8887-7962-bb8c-597d70cbfaf4'
        shell, _, _ = self.runtime_case('shell_snapshots', thread + '.123.sh')
        lock, _, _ = self.runtime_case('thread-writer-locks', thread + '.lock')
        shell.write_text('# Snapshot file\nexport FIXTURE=preserved\n')
        lock.touch()
        self.journal.report()
        first = self.backup()
        first_restore = self.restored(first, 'before-release')
        self.assertEqual((first_restore / shell.relative_to(self.source)).read_text(), shell.read_text())
        shell.write_text('# Snapshot file\nexport FIXTURE=recaptured\n')
        original_run = subprocess.Popen
        deleted = []
        def release_before_tar(command, *args, **kwargs):
            if command[0] == 'tar' and not deleted:
                shell.unlink()
                lock.unlink()
                deleted.extend([str(shell), str(lock)])
            return original_run(command, *args, **kwargs)
        adapter = SimpleNamespace(validate_archive_warnings=backup.validate_archive_warnings)
        ephemeral.install(adapter)
        with patch.object(ephemeral, 'HOMES', (str(self.source),)), \
                patch.object(backup, 'validate_archive_warnings', adapter.validate_archive_warnings), \
                patch.object(subprocess, 'Popen', side_effect=release_before_tar):
            second = self.backup(first)
        self.assertTrue(second['passed'])
        self.assertIn(str(shell), second['online_archive_warnings_recaptured_by_next_delta'])
        # The journal sequence stays at the capture start, so the next delta
        # removes released files from the restored view, not from live sources.
        third = self.backup(second)
        restored = self.restored(third, 'after-release')
        self.assertFalse((restored / shell.relative_to(self.source)).exists())
        self.assertFalse((restored / lock.relative_to(self.source)).exists())
        self.assertEqual((restored / self.history.name).read_bytes(), self.history.read_bytes())
        self.assertEqual((restored / self.note.name).read_bytes(), self.note.read_bytes())
