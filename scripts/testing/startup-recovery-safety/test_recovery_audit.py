import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('recovery_audit', REPO / 'scripts/verify_recovered_tree.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RecoveryAuditTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix='recovery-audit-', dir=os.environ.get('VK_SAFETY_TEST_ROOT'))
        self.root = Path(self.scratch.name)
        self.path = self.root / 'edit'
        self.path.write_bytes(b'baseline bytes')
        self.path.chmod(0o640)
        self.rows = [{'path': 'edit', 'type': 'file', 'mode': 0o640,
                      'sha256': hashlib.sha256(b'baseline bytes').hexdigest()}]
        self.journal = {'ready': True, 'instance': 'fixture', 'scope_sha256': 'scope', 'sequence': 9, 'errors': []}
        self.coverage = {'instance': 'fixture', 'scope_sha256': 'scope', 'sequence_start': 5}

    def tearDown(self):
        self.scratch.cleanup()

    def audit(self, rows=None):
        return module.audit(self.root, self.rows if rows is None else rows, self.journal, coverage=self.coverage)

    def test_content_and_mode_match_still_does_not_prove_zero_loss(self):
        result = self.audit()
        self.assertTrue(result['baseline_verified'])
        self.assertTrue(result['journal_coverage_verified'])
        self.assertFalse(result['zero_loss_proven'])
        self.assertFalse(result['post_backup_content_preservation_verified'])
        self.assertFalse(result['new_file_preservation_verified'])

    def test_existing_filename_with_newer_bytes_is_measured_and_preserved(self):
        self.path.write_bytes(b'newer surviving uncommitted edit')
        before = self.path.stat()
        result = self.audit()
        self.assertEqual(result['findings'][0]['reason'], 'content')
        self.assertEqual(self.path.read_bytes(), b'newer surviving uncommitted edit')
        self.assertEqual(before.st_mtime_ns, self.path.stat().st_mtime_ns)

    def test_missing_file_and_mode_drift(self):
        self.path.chmod(0o600)
        self.assertEqual(self.audit()['findings'][0]['reason'], 'mode')
        self.path.unlink()
        self.assertEqual(self.audit()['counts']['missing'], 1)

    def test_link_substitution_and_dangling_links(self):
        self.path.unlink()
        self.path.symlink_to('does-not-exist')
        self.assertEqual(self.audit()['findings'][0]['reason'], 'type')
        row = {'path': 'edit', 'type': 'symlink', 'mode': stat.S_IMODE(self.path.lstat().st_mode), 'target': 'does-not-exist'}
        self.assertTrue(self.audit([row])['baseline_verified'])
        row['target'] = 'another-target'
        self.assertFalse(self.audit([row])['baseline_verified'])

    def test_hardlink_identity_not_just_identical_bytes(self):
        os.link(self.path, self.root / 'linked')
        row = {**self.rows[0], 'path': 'linked', 'type': 'hardlink', 'target': 'edit'}
        self.assertTrue(self.audit([row])['baseline_verified'])
        (self.root / 'linked').unlink()
        (self.root / 'linked').write_bytes(b'baseline bytes')
        (self.root / 'linked').chmod(0o640)
        self.assertEqual(self.audit([row])['findings'][0]['reason'], 'hardlink identity')

    def test_directory_type_and_mode(self):
        (self.root / 'folder').mkdir(mode=0o750)
        row = {'path': 'folder', 'type': 'directory', 'mode': 0o750}
        self.assertTrue(self.audit([row])['baseline_verified'])

    def test_missing_metadata_does_not_pass(self):
        for key in ('type', 'mode', 'sha256'):
            row = dict(self.rows[0]); del row[key]
            self.assertEqual(self.audit([row])['counts']['unverified'], 1)

    def test_fifo_substitution_is_rejected_without_blocking(self):
        self.path.unlink(); os.mkfifo(self.path)
        self.assertEqual(self.audit()['findings'][0]['reason'], 'type')

    def test_parent_link_never_followed(self):
        (self.root / 'alias').symlink_to(self.root, target_is_directory=True)
        row = {**self.rows[0], 'path': 'alias/edit'}
        self.assertEqual(self.audit([row])['counts']['error'], 1)

    def test_traversal_duplicate_and_empty_manifest_rejected(self):
        for name in ('/edit', '../edit', 'a/../edit', './edit', 'a//edit'):
            with self.assertRaises(ValueError):
                self.audit([{**self.rows[0], 'path': name}])
        with self.assertRaises(ValueError): self.audit(self.rows * 2)
        with self.assertRaises(ValueError): self.audit([])

    def test_journal_gap_instance_scope_and_sequence_fail_closed(self):
        for patch in ({'ready': False}, {'errors': [{'coverage_lost': 16384}]},
                      {'instance': 'replacement'}, {'scope_sha256': 'different'}, {'sequence': 2}):
            original = dict(self.journal)
            self.journal.update(patch)
            self.assertFalse(self.audit()['journal_coverage_verified'])
            self.journal = original
        self.assertFalse(module.audit(self.root, self.rows, self.journal)['journal_coverage_verified'])

    def test_new_names_without_baseline_remain_unverified(self):
        result = module.audit(self.root, self.rows, self.journal, ['new-missing'], self.coverage)
        self.assertFalse(result['baseline_verified'])
        self.assertFalse(result['uncovered_names'][0]['current_exists'])
        self.assertFalse(result['new_file_preservation_verified'])

    def test_runtime_gates_precede_stateful_startup_and_no_automatic_deletion(self):
        main = (REPO / 'crates/server/src/main.rs').read_text()
        self.assertLess(main.index('parse_server_invocation(std::env::args_os()'), main.index('sentry_utils::init_once'))
        self.assertLess(main.index('validate_startup_identity()?'), main.index('if !asset_dir().exists()'))
        deployment = (REPO / 'crates/local-deployment/src/lib.rs').read_text()
        constructor = deployment.split('async fn new(shutdown: CancellationToken)')[1]
        self.assertLess(constructor.index('validate_startup_identity()?'), constructor.index('migrate_execution_logs_to_files'))
        container = (REPO / 'crates/local-deployment/src/container.rs').read_text()
        self.assertNotIn('spawn_workspace_cleanup', container)
        self.assertNotIn('cleanup_expired_workspaces', container)
        status_gate = container.split('fn status_worktree_cleanup_enabled')[1].split('async fn')[0]
        self.assertIn('false', status_gate)
        orphan = (REPO / 'crates/workspace-manager/src/workspace_manager.rs').read_text().split('async fn cleanup_orphans_in_directory')[1].split('#[cfg')[0]
        self.assertNotIn('remove_dir', orphan)
        self.assertNotIn('cleanup_workspace_without_repos', orphan)


if __name__ == '__main__':
    unittest.main()
