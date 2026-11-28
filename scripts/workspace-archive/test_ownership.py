"""Actual SQL/Git/process ownership tests; no production retirement or B claim."""
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import unittest
import uuid

from catalog import Conflict
import git_dependency
import ownership
import process_use
import test_inventory as fixtures


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.InventoryTests(methodName='test_inventory_does_not_grant_retirement_or_backup_exclusion')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.f, self.root, self.w = fixture, fixture.root, str(fixture.wid)
        self.sessions, self.worktrees, self.native = (self.root / x for x in ('sessions', 'worktrees', 'native'))
        for p in (self.sessions, self.worktrees, self.native):
            p.mkdir()
        self.container = self.worktrees / self.w
        self.history = self.sessions / str(fixture.sid)[:2] / str(fixture.sid)
        self.history.mkdir(parents=True)
        (self.history / 'log').write_bytes(b'exact conversation history')
        self.container.mkdir()
        db = fixture.conn
        db.executescript('''ALTER TABLE workspaces ADD COLUMN branch TEXT;
            ALTER TABLE workspaces ADD COLUMN worktree_deleted INTEGER DEFAULT 0;
            ALTER TABLE execution_processes ADD COLUMN completed_at TEXT DEFAULT 'fixture closed';
            CREATE TABLE repos(id INTEGER PRIMARY KEY,path TEXT,name TEXT);
            CREATE TABLE workspace_repos(workspace_id BLOB,repo_id INTEGER,target_branch TEXT);''')
        db.execute('UPDATE workspaces SET container_ref=?,branch=? WHERE id=?',
                   (str(self.container), 'owned', fixture.wid.bytes))
        db.commit()
        self.children = []
        fixture_children = self.children
        class FixtureProc:
            # Only fixture processes, but every inspection reads actual Linux
            # /proc. Host-wide privileged visibility is a separate acceptance.
            def iterdir(self):
                return iter([Path('/proc') / str(p.pid) for p in fixture_children])
        self.proc = FixtureProc()
        self.owner = ownership.Ownership(fixture.db, self.sessions, fixture.native, [self.native], self.worktrees,
            process_check=lambda roots: process_use.check(roots, proc=self.proc))

    def repository(self):
        self.repository_path = self.root / 'common'
        subprocess.run(['git', 'init', '-q', str(self.repository_path)], check=True)
        def git(*args):
            subprocess.run(['git', '-C', str(self.repository_path), *args], check=True, capture_output=True)
        git('config', 'user.name', 'Fixture')
        git('config', 'user.email', 'fixture@example.invalid')
        (self.repository_path / 'source').write_text('preserved source')
        git('add', 'source')
        git('commit', '-qm', 'fixture')
        git('worktree', 'add', '-b', 'owned', str(self.container / 'repo'))
        self.f.conn.execute('INSERT INTO repos VALUES(1,?,?)', (str(self.repository_path), 'repo'))
        self.f.conn.execute('INSERT INTO workspace_repos VALUES(?,1,?)', (self.f.wid.bytes, 'main'))
        self.f.conn.commit()
        return git

    def test_current_plan_includes_private_git_and_preserves_shared_root(self):
        self.repository()
        plan = self.owner.plan(self.w)
        self.assertEqual(len(plan['git']), 1)
        spec = plan['git'][0]
        self.assertEqual(plan['roots'], sorted([str(self.history), str(self.container), spec['admin']]))
        self.assertNotIn(spec['common'], plan['roots'])
        self.owner.validate(self.w, plan, archive=True)
        self.owner.complete_restore(self.w, plan)

    def test_message_or_pin_prevents_retirement_but_not_restoration(self):
        plan = self.owner.plan(self.w)
        self.f.conn.execute('UPDATE workspaces SET archived=0,pinned=1 WHERE id=?', (self.f.wid.bytes,))
        self.f.conn.execute("INSERT INTO turn_github_sync_incoming VALUES(?,'pending')", (self.f.wid.bytes,))
        self.f.conn.commit()
        with self.assertRaises(Conflict):
            self.owner.validate(self.w, plan, archive=True)
        self.owner.validate(self.w, plan, archive=False)
        self.f.conn.execute("UPDATE execution_processes SET status='running'")
        self.f.conn.commit()
        with self.assertRaisesRegex(Conflict, 'running_execution'):
            self.owner.validate(self.w, plan, archive=False)

    def test_native_children_and_missing_history_remain_protected(self):
        self.f.conn.execute('INSERT INTO coding_agent_turns VALUES(?,?)', (self.f.eid.bytes, 'parent'))
        with sqlite3.connect(self.f.native) as db:
            db.executemany('INSERT INTO threads(id,rollout_path) VALUES(?,?)',
                [(n, str(self.native / (n + '.jsonl'))) for n in ('parent', 'child')])
            db.execute("INSERT INTO thread_spawn_edges VALUES('parent','child','closed')")
        self.f.conn.commit()
        for name in ('parent', 'child'):
            (self.native / (name + '.jsonl')).write_text('native history')
        plan = self.owner.plan(self.w)
        self.assertIn(str(self.native / 'child.jsonl'), plan['roots'])
        (self.native / 'child.jsonl').unlink()
        with self.assertRaisesRegex(Conflict, 'missing'):
            self.owner.plan(self.w)
        # A cold journal permits known absence, not a changed native owner.
        self.owner.validate(self.w, plan, archive=False)
        with sqlite3.connect(self.f.native) as db:
            db.execute("UPDATE threads SET rollout_path=? WHERE id='child'", (str(self.native / 'different'),))
        with self.assertRaisesRegex(Conflict, 'ownership changed'):
            self.owner.validate(self.w, plan, archive=False)

    def test_overlap_dirty_work_and_replaced_database_are_protected(self):
        self.repository()
        (self.container / 'repo/source').write_text('new uncommitted work')
        with self.assertRaisesRegex(Conflict, 'Dirty'):
            self.owner.plan(self.w)
        other = uuid.uuid4()
        self.f.conn.execute("INSERT INTO workspaces(id,archived,pinned,container_ref,branch,worktree_deleted) VALUES(?,1,0,?,'owned',0)",
                            (other.bytes, str(self.container / 'nested')))
        self.f.conn.execute('UPDATE workspaces SET container_ref=? WHERE id=?',
                            (str(self.container / 'nested'), other.bytes))
        self.f.conn.commit()
        with self.assertRaisesRegex(Conflict, 'overlaps'):
            self.owner.plan(self.w)
        self.f.native.rename(self.f.native.with_suffix('.old'))
        self.f.native.write_bytes(b'newer unrelated SQL')
        with self.assertRaisesRegex(Conflict, 'changed'):
            self.owner.check_bindings()

    def test_durably_removed_worktree_still_has_shared_branch_recovery(self):
        git = self.repository()
        git('worktree', 'remove', str(self.container / 'repo'))
        self.container.rmdir()
        with self.assertRaisesRegex(Conflict, 'missing'):
            self.owner.plan(self.w)
        self.f.conn.execute('UPDATE workspaces SET worktree_deleted=1 WHERE id=?', (self.f.wid.bytes,))
        self.f.conn.commit()
        plan = self.owner.plan(self.w)
        self.assertEqual(plan['roots'], [str(self.history)])
        self.assertIsNone(plan['git'][0]['worktree'])
        git_dependency.verify_live(plan['git'][0])

    def child(self, body, path):
        p = subprocess.Popen([sys.executable, '-c', body, str(path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self.children.append(p)
        def finish():
            if p.poll() is None:
                p.stdin.close()
                p.wait(timeout=10)
            p.stdout.close()
        self.addCleanup(finish)
        self.assertEqual(p.stdout.readline(), b'ready\n')
        return p

    def test_actual_open_cwd_and_mapped_files_protect_workspace(self):
        log = self.history / 'log'
        child = self.child("import sys; f=open(sys.argv[1],'rb'); print('ready',flush=True); sys.stdin.read()", log)
        with self.assertRaisesRegex(Conflict, 'referenced'):
            self.owner.plan(self.w)
        child.stdin.close(); child.wait(timeout=10)
        child = self.child("import sys,os; os.chdir(sys.argv[1]); print('ready',flush=True); sys.stdin.read()", self.container)
        with self.assertRaisesRegex(Conflict, 'referenced'):
            self.owner.plan(self.w)
        child.stdin.close(); child.wait(timeout=10)
        st = log.stat()
        child = self.child("import sys,mmap; f=open(sys.argv[1],'rb'); m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ); f.close(); print('ready',flush=True); sys.stdin.read()", log)
        # Name-independent inode protection also covers a namespace alias.
        with self.assertRaises(Conflict):
            process_use.check([self.root / 'unrelated'], identities=[(st.st_dev, st.st_ino)], proc=self.proc)

    def test_aliased_and_foreign_worktree_root_are_protected(self):
        alias = self.worktrees / 'alias'
        alias.symlink_to(self.container, target_is_directory=True)
        self.f.conn.execute('UPDATE workspaces SET container_ref=? WHERE id=?', (str(alias), self.f.wid.bytes))
        self.f.conn.commit()
        with self.assertRaisesRegex(Conflict, 'aliased'):
            self.owner.plan(self.w)
