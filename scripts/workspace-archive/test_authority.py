"""Composed source lifecycle with real Git, SQL and bytes; fixture host/B only."""
import json
from pathlib import Path
import unittest
import uuid

from authority import WorkspaceAuthority
from catalog import Catalog, Conflict
from controller import Controller
from custody import Custody
import ownership
from shared_dependency import SharedGit
from shared_files import SharedFiles
import test_inventory as inventory_fixture
import test_lifecycle as lifecycle_fixture
import test_ownership as ownership_fixture


class IntegratedAuthorityTests(unittest.TestCase):
    def setUp(self):
        f = ownership_fixture.OwnershipTests(methodName='test_current_plan_includes_private_git_and_preserves_shared_root')
        f.setUp(); f.repository()
        self.addCleanup(f.doCleanups)
        self.f, self.root = f, f.root
        self.guard_checks = 0
        f.f.conn.executescript(inventory_fixture.MIGRATION.read_text())
        f.f.conn.executescript((inventory_fixture.ROOT / 'crates/db/migrations/20261127000000_workspace_archive_catalog.sql').read_text())
        self.catalog = Catalog(f.f.db)
        self.addCleanup(self.catalog.close)
        for name in ('locks', 'stage', 'controls', 'B-fixture', 'uploads'):
            (self.root / name).mkdir(mode=0o700)
        (self.root / 'uploads/photo').write_bytes(b'original shared attachment')
        self.provider = lifecycle_fixture.FixtureStore(self.root / 'B-fixture')
        def describe(locator, expected):
            with self.provider.recall(locator, expected) as recovered:
                return recovered.manifest
        self.provider.describe = describe
        self.config = dict(database=str(f.f.db), sessions_root=str(f.sessions), native_state=str(f.f.native),
            native_roots=[str(f.native)], worktrees_root=str(f.worktrees), attachment_roots=[str(self.root / 'uploads')])
        owner = self
        class FixtureHost:
            def qualify(self): self.check()
            def check(self): owner.guard_checks += 1
            def check_boundary(self): self.check()
            def check_processes(self, roots, identities=()):
                import process_use
                process_use.check(roots, identities=identities, proc=f.proc)
            def reserve_restore(self, tree, stage): self.check()
            def reserve_publication(self, tree, index, destination): self.check()
        self.host = FixtureHost()

    def invoke(self, action):
        authority = WorkspaceAuthority(self.f.w, self.config, self.host)
        authority.bind_dependencies(SharedGit(self.root / 'controls', self.root / 'locks', self.provider, authority),
                                    SharedFiles(self.root / 'controls', self.root / 'locks', self.provider, authority))
        with Custody(self.root / 'locks', self.f.w, exclusive=True) as custody:
            return Controller(self.catalog, custody, self.provider, authority, self.root / 'stage').run(action)

    def retain(self):
        payload = dict(prompt='exact saved message\n', executor_config={'model': 'selected', 'permission': 'review'},
                       perform_git_reset=False, force_when_dirty=False, retry_process_id=None)
        self.catalog.retain_input(self.f.w, str(self.f.f.sid), str(uuid.uuid4()), payload)
        return payload

    def test_composed_archive_and_message_revival_restore_dependencies_before_input_ready(self):
        (self.f.container / 'AGENTS.md').write_text(ownership.WORKSPACE_CONFIG)
        self.assertEqual(self.invoke('archive')['phase'], 'cold')
        self.assertFalse(self.f.history.exists())
        self.assertFalse(self.f.container.exists())
        self.assertTrue(self.f.repository_path.exists())
        (self.root / 'uploads/photo').unlink()  # disposable fixture loss only
        (self.root / 'uploads/new').write_bytes(b'later active upload')
        wanted = self.retain()
        self.assertEqual(self.invoke('ensure')['phase'], 'active')
        row = self.catalog.db.execute('SELECT payload,state FROM workspace_archive_inputs').fetchone()
        self.assertEqual(json.loads(row[0]), wanted)
        self.assertEqual(row[1], 'ready')
        self.assertEqual((self.root / 'uploads/photo').read_bytes(), b'original shared attachment')
        self.assertEqual((self.root / 'uploads/new').read_bytes(), b'later active upload')
        self.assertGreater(self.guard_checks, 0)

    def test_newer_shared_branch_is_preserved_and_input_stays_retained(self):
        self.invoke('archive')
        import git_dependency as gd
        (self.f.repository_path / 'source').write_text('new main state')
        gd.git(self.f.repository_path, 'commit', '-am', 'new main')
        head = gd.line(self.f.repository_path, 'rev-parse', 'HEAD')
        gd.git(self.f.repository_path, 'update-ref', 'refs/heads/owned', head)
        self.retain()
        with self.assertRaisesRegex(Conflict, 'branch'):
            self.invoke('ensure')
        self.assertEqual(gd.line(self.f.repository_path, 'rev-parse', 'owned'), head)
        self.assertEqual(self.catalog.db.execute('SELECT state FROM workspace_archive_inputs').fetchone()[0], 'waiting_restore')

    def test_custom_outer_work_or_external_alias_is_preserved_before_capture(self):
        (self.f.container / 'AGENTS.md').write_text('custom untracked user notes')
        with self.assertRaisesRegex(Conflict, 'Untracked'):
            self.invoke('archive')
        self.assertEqual(self.provider.captures, 0)
        (self.f.container / 'AGENTS.md').unlink()
        attachments = self.f.container / '.vibe-attachments'
        attachments.mkdir()
        (attachments / 'external').symlink_to(self.root / 'unqualified-external-source')
        with self.assertRaisesRegex(Conflict, 'external dependency'):
            self.invoke('archive')
        self.assertTrue(self.f.container.exists())
        self.assertIsNone(self.catalog.state(self.f.w))

    def test_generated_config_contract_matches_current_rust_source(self):
        source = (inventory_fixture.ROOT / 'crates/local-deployment/src/container.rs').read_text()
        actual = source.split('const WORKSPACE_AGENT_IMAGE_SHARING_INSTRUCTIONS: &str = r#"', 1)[1].split('"#;', 1)[0]
        self.assertEqual(actual, ownership.WORKSPACE_CONFIG)
