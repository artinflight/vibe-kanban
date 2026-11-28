"""Real Git/SQLite-free ownership tests; local fixture B is not Desktop B proof."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from catalog import Conflict
import git_dependency as gd
from shared_dependency import SharedGit
import test_lifecycle as lifecycle_fixtures


class Authority:
    def check_shared(self, spec):
        # Production supplies its live reader/process/resource custody here;
        # Git graph and worktree qualification are exercised by SharedGit itself.
        pass

    def reserve_restore(self, manifest, destination):
        pass


class GitDependencyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        gd.git(self.repo, 'init', '-b', 'main')
        gd.git(self.repo, 'config', 'user.name', 'Archive Test')
        gd.git(self.repo, 'config', 'user.email', 'archive-test@example.invalid')
        (self.repo / 'tracked').write_text('original code\n')
        gd.git(self.repo, 'add', 'tracked')
        gd.git(self.repo, 'commit', '-m', 'fixture initial')
        self.worktree = self.root / 'workspace'
        gd.git(self.repo, 'worktree', 'add', '-b', 'archive-workspace', str(self.worktree))
        self.spec = gd.inspect(self.worktree, self.repo, 'archive-workspace')
        for name in ('locks', 'controls', 'fixture-B'):
            (self.root / name).mkdir(mode=0o700)
        self.store = lifecycle_fixtures.FixtureStore(self.root / 'fixture-B')
        def describe(locator, expected):
            with self.store.recall(locator, expected) as recalled:
                return recalled.manifest
        self.store.describe = describe
        self.dependency = SharedGit(self.root / 'controls', self.root / 'locks', self.store, Authority())

    def test_independent_graph_restore_and_reuse_survive_unrelated_branch_changes(self):
        accepted = self.dependency.ensure(self.spec)
        self.assertEqual(self.store.captures, 1)
        (self.repo / 'tracked').write_text('new main-branch code\n')
        gd.git(self.repo, 'commit', '-am', 'other owner change')
        new_head = gd.line(self.repo, 'rev-parse', 'HEAD')
        again = self.dependency.ensure(self.spec)
        self.assertEqual(again, accepted)
        self.assertEqual(self.store.captures, 1)
        with self.dependency.recall(accepted, self.spec, self.root / 'independent-restore') as restored:
            gd.verify_shared_snapshot(restored, self.spec['object_roots'])
        self.assertEqual(gd.line(self.repo, 'rev-parse', 'HEAD'), new_head)
        self.assertEqual((self.worktree / 'tracked').read_text(), 'original code\n')
        gd.verify_live(self.spec)

    def test_removed_worktree_keeps_branch_graph_independently_recoverable(self):
        gd.git(self.repo, 'worktree', 'remove', str(self.worktree))
        spec = gd.inspect_branch(self.repo, 'archive-workspace')
        accepted = self.dependency.ensure(spec)
        with self.dependency.recall(accepted, spec, self.root / 'removed-tree-restore') as restored:
            gd.verify_shared_snapshot(restored, spec['object_roots'])
        gd.verify_live(spec)
        self.assertFalse(self.worktree.exists())

    def test_second_workspace_reuses_same_shared_graph(self):
        accepted = self.dependency.ensure(self.spec)
        other = self.root / 'other-workspace'
        gd.git(self.repo, 'worktree', 'add', '-b', 'other-workspace', str(other))
        spec = gd.inspect(other, self.repo, 'other-workspace')
        self.assertEqual(self.dependency.ensure(spec), accepted)
        self.assertEqual(self.store.captures, 1)

    def test_dirty_untracked_wrong_branch_and_filter_program_are_protected(self):
        (self.worktree / 'untracked').write_text('preserve me')
        with self.assertRaisesRegex(Conflict, 'Dirty'):
            gd.inspect(self.worktree, self.repo, 'archive-workspace')
        self.assertEqual((self.worktree / 'untracked').read_text(), 'preserve me')
        (self.worktree / 'untracked').unlink()  # exact test-created file only
        with self.assertRaisesRegex(Conflict, 'branch differs'):
            gd.inspect(self.worktree, self.repo, 'different')
        gd.git(self.repo, 'config', 'filter.fixture.clean', 'touch must-not-run')
        with self.assertRaisesRegex(Conflict, 'filter programs'):
            gd.inspect(self.worktree, self.repo, 'archive-workspace')
        self.assertFalse((self.worktree / 'must-not-run').exists())

    def test_unfinished_git_operation_is_not_archived(self):
        pending = Path(self.spec['admin']) / 'MERGE_HEAD'
        pending.write_text(self.spec['head'] + '\n')
        with self.assertRaisesRegex(Conflict, 'Unfinished'):
            gd.inspect(self.worktree, self.repo, 'archive-workspace')
        self.assertTrue(pending.exists())

    def test_new_workspace_commit_extends_recovery_without_replacing_old_point(self):
        first = self.dependency.ensure(self.spec)
        (self.worktree / 'tracked').write_text('workspace follow-up\n')
        gd.git(self.worktree, 'commit', '-am', 'new workspace point')
        newer = gd.inspect(self.worktree, self.repo, 'archive-workspace')
        self.assertNotEqual(newer['head'], self.spec['head'])
        second = self.dependency.ensure(newer)
        self.assertNotEqual(first['manifest_sha256'], second['manifest_sha256'])
        self.assertEqual(self.store.captures, 2)
        self.assertEqual(len(list((self.root / 'controls').glob('*.accepted.json'))), 2)
        self.assertTrue(set(self.spec['object_roots']) <= set(second['manifest']['object_roots']))
        with self.assertRaisesRegex(Conflict, 'newer shared state'):
            gd.verify_live(self.spec)

    def test_corrupt_and_uncertain_recovery_preserve_originals_and_reuse_capture(self):
        self.store.uncertain_once = True
        with self.assertRaises(ConnectionError): self.dependency.ensure(self.spec)
        self.assertEqual(self.store.captures, 1)
        self.store.corrupt = True
        with self.assertRaises(ValueError): self.dependency.ensure(self.spec)
        self.assertEqual(list((self.root / 'controls').glob('*.accepted.json')), [])
        self.store.corrupt = False
        self.dependency.ensure(self.spec)
        self.assertEqual(self.store.captures, 1)
        self.assertEqual(len(list((self.root / 'controls').glob('*/restore-0.partial.json'))), 1)
        self.assertTrue(next((self.root / 'controls').glob('*/restore-0')).is_dir())
        self.assertEqual(gd.inspect(self.worktree, self.repo, 'archive-workspace'), self.spec)

    def test_offline_b_leaves_common_repository_and_worktree_intact(self):
        self.store.offline = True
        with self.assertRaises(OSError): self.dependency.ensure(self.spec)
        self.assertEqual(gd.inspect(self.worktree, self.repo, 'archive-workspace'), self.spec)
        self.assertEqual(list((self.root / 'controls').glob('*.accepted.json')), [])
        self.store.offline = False
        self.dependency.ensure(self.spec)
        self.assertEqual(self.store.captures, 1)


if __name__ == '__main__': unittest.main()
