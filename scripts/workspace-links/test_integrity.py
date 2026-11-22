"""Exercise the actual SQL migration/guards, without a provider or live writes."""
import pathlib
import sqlite3
import unittest
import uuid

SQL = (pathlib.Path(__file__).resolve().parents[2] / 'crates/db/migrations/20261103110000_workspace_issue_integrity.sql').read_text()
INBOX = bytes.fromhex('779542437AEF4AFDA98407B313FF74DC')


def fixture():
    db = sqlite3.connect(':memory:')
    db.executescript('''
    PRAGMA foreign_keys=ON;
    CREATE TABLE projects(id BLOB PRIMARY KEY, name TEXT NOT NULL,
        remote_project_id BLOB, archived INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE tasks(id BLOB PRIMARY KEY, project_id BLOB NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        title TEXT NOT NULL, description TEXT, status TEXT NOT NULL);
    CREATE TABLE workspaces(id BLOB PRIMARY KEY, task_id BLOB, branch TEXT NOT NULL,
        name TEXT, archived INTEGER DEFAULT 0, pinned INTEGER DEFAULT 0,
        container_ref TEXT, updated_at TEXT DEFAULT 'preserve');
    CREATE TABLE coding_agent_turns(id BLOB, seen INTEGER);
    INSERT INTO coding_agent_turns VALUES(X'01',0),(X'02',1);
    CREATE TABLE local_issue_assignees(issue_id BLOB, user_id BLOB);
    ''')
    return db


class Integrity(unittest.TestCase):
    def setUp(self):
        self.db = fixture()
        self.project, self.issue, self.workspace = [uuid.uuid4().bytes for _ in range(3)]
        self.db.execute('INSERT INTO projects(id,name) VALUES(?,?)', (self.project, 'Example project'))
        self.db.execute('INSERT INTO tasks VALUES(?,?,?,?,?)', (self.issue, self.project, 'Example workspace', None, 'inprogress'))

    def install(self):
        self.db.executescript(SQL)

    def insert(self, issue=None, workspace=None):
        workspace = workspace or self.workspace
        self.db.execute('INSERT INTO workspaces(id,task_id,branch,name,archived,pinned,container_ref) VALUES(?,?,?,?,1,1,?)',
                        (workspace, issue, 'vk/example-workspace', 'Example workspace', '/existing/work'))
        return workspace

    def assert_valid(self):
        self.assertEqual(self.db.execute('SELECT count(*) FROM workspaces w LEFT JOIN tasks t ON t.id=w.task_id LEFT JOIN projects p ON p.id=t.project_id WHERE t.id IS NULL OR p.id IS NULL').fetchone()[0], 0)

    def test_reproduce_original_null_and_dangling_creation(self):
        self.insert()
        self.insert(uuid.uuid4().bytes, uuid.uuid4().bytes)
        self.assertEqual(self.db.execute('SELECT count(*) FROM workspaces WHERE task_id IS NULL').fetchone()[0], 1)

    def test_preserves_valid_links_and_all_existing_state(self):
        self.insert(self.issue)
        self.db.execute('INSERT INTO local_issue_assignees VALUES(?,?)', (self.issue, b'dot'))
        snapshots = {t: self.db.execute('SELECT * FROM '+t).fetchall() for t in ['projects','tasks','workspaces','coding_agent_turns','local_issue_assignees']}
        self.install()
        for t, rows in snapshots.items():
            self.assertEqual(self.db.execute('SELECT * FROM '+t).fetchall(), rows)
        self.assert_valid()
        self.assertEqual(self.db.execute('SELECT count(*) FROM workspace_issue_recoveries').fetchone()[0], 0)

    def test_backfills_null_and_dangling_without_changing_work_or_unread(self):
        self.insert()
        other = self.insert(uuid.uuid4().bytes, uuid.uuid4().bytes)
        before = self.db.execute('SELECT id,branch,name,archived,pinned,container_ref,updated_at FROM workspaces').fetchall()
        self.install()
        self.assert_valid()
        self.assertEqual(self.db.execute('SELECT id,branch,name,archived,pinned,container_ref,updated_at FROM workspaces').fetchall(), before)
        self.assertEqual(self.db.execute('SELECT seen FROM coding_agent_turns').fetchall(), [(0,), (1,)])
        self.assertEqual(self.db.execute('SELECT count(*) FROM workspace_issue_recoveries').fetchone()[0], 2)
        self.assertEqual(self.db.execute('SELECT task_id FROM workspaces WHERE id=?', (other,)).fetchone()[0], other)

    def test_standalone_gets_one_visible_unassigned_issue_atomically(self):
        self.install()
        self.insert()
        self.assert_valid()
        self.assertEqual(self.db.execute('SELECT project_id FROM tasks WHERE id=?', (self.workspace,)).fetchone()[0], INBOX)
        self.assertEqual(self.db.execute('SELECT count(*) FROM local_issue_assignees').fetchone()[0], 0)
        self.assertEqual(self.db.execute('SELECT count(*) FROM tasks').fetchone()[0], 2)

    def test_valid_explicit_link_needs_no_inbox(self):
        self.install()
        self.insert(self.issue)
        self.assert_valid()
        self.assertEqual(self.db.execute('SELECT count(*) FROM projects').fetchone()[0], 1)

    def test_dangling_insert_and_unlink_are_rejected(self):
        self.install()
        with self.assertRaises(sqlite3.IntegrityError):
            self.insert(uuid.uuid4().bytes)
        self.assertEqual(self.db.execute('SELECT count(*) FROM workspaces').fetchone()[0], 0)
        self.insert(self.issue)
        for value in [None, uuid.uuid4().bytes]:
            with self.assertRaises(sqlite3.IntegrityError):
                self.db.execute('UPDATE workspaces SET task_id=? WHERE id=?', (value, self.workspace))
        self.assert_valid()

    def test_delete_and_identity_changes_cannot_orphan_work(self):
        self.install()
        self.insert(self.issue)
        for foreign_keys in [False, True]:
            self.db.commit()
            self.db.execute('PRAGMA foreign_keys='+str(int(foreign_keys)))
            for query, params in [
                ('DELETE FROM tasks WHERE id=?', (self.issue,)),
                ('DELETE FROM projects WHERE id=?', (self.project,)),
                ('UPDATE tasks SET id=? WHERE id=?', (uuid.uuid4().bytes, self.issue)),
                ('UPDATE tasks SET project_id=? WHERE id=?', (uuid.uuid4().bytes, self.issue)),
                ('UPDATE projects SET id=? WHERE id=?', (uuid.uuid4().bytes, self.project)),
            ]:
                with self.assertRaises(sqlite3.IntegrityError, msg=query):
                    self.db.execute(query, params)
            self.assert_valid()

    def test_valid_relink_and_workspace_deletion_remain_possible(self):
        self.install()
        self.insert()
        self.db.execute('UPDATE workspaces SET task_id=? WHERE id=?', (self.issue, self.workspace))
        self.db.execute('DELETE FROM tasks WHERE id=?', (self.workspace,))
        self.assert_valid()
        self.db.execute('DELETE FROM workspaces WHERE id=?', (self.workspace,))
        self.db.execute('DELETE FROM tasks WHERE id=?', (self.issue,))

    def test_trigger_and_transaction_failure_roll_back_new_issue(self):
        self.install()
        self.db.commit()
        self.db.execute('BEGIN')
        self.insert()
        self.db.rollback()
        self.assertEqual(self.db.execute('SELECT count(*) FROM tasks').fetchone()[0], 1)
        self.assertEqual(self.db.execute('SELECT count(*) FROM projects').fetchone()[0], 1)

    def test_returning_is_stale_until_model_reloads(self):
        self.install()
        result = self.db.execute('INSERT INTO workspaces(id,branch) VALUES(?,?) RETURNING task_id', (self.workspace, 'branch')).fetchone()[0]
        self.assertIsNone(result)
        self.assertEqual(self.db.execute('SELECT task_id FROM workspaces WHERE id=?', (self.workspace,)).fetchone()[0], self.workspace)

    def test_reapplying_is_idempotent(self):
        self.insert()
        self.install()
        before = self.db.execute('SELECT * FROM workspaces').fetchall()
        self.install()
        self.assertEqual(self.db.execute('SELECT * FROM workspaces').fetchall(), before)
        self.assertEqual(self.db.execute('SELECT count(*) FROM tasks').fetchone()[0], 2)

    def test_replace_cannot_bypass_deletion_guards(self):
        self.install()
        self.insert(self.issue)
        self.db.execute('CREATE UNIQUE INDEX remote_project_id ON projects(remote_project_id) WHERE remote_project_id IS NOT NULL')
        remote = uuid.uuid4().bytes
        self.db.execute('UPDATE projects SET remote_project_id=? WHERE id=?', (remote,self.project))
        other_project, other_issue = uuid.uuid4().bytes, uuid.uuid4().bytes
        self.db.execute('INSERT INTO projects(id,name) VALUES(?,?)', (other_project,'Other'))
        self.db.execute('INSERT INTO tasks VALUES(?,?,?,?,?)', (other_issue,other_project,'Other',None,'todo'))
        self.db.commit()
        self.db.execute('PRAGMA foreign_keys=OFF')
        self.db.execute('PRAGMA recursive_triggers=OFF')
        for query, values in [
            ('INSERT OR REPLACE INTO tasks VALUES(?,?,?,?,?)', (self.issue,uuid.uuid4().bytes,'Invalid',None,'todo')),
            ('UPDATE OR REPLACE tasks SET id=?,project_id=? WHERE id=?', (self.issue,uuid.uuid4().bytes,other_issue)),
            ('INSERT OR REPLACE INTO projects(id,name,remote_project_id) VALUES(?,?,?)', (uuid.uuid4().bytes,'Replacement',remote)),
            ('UPDATE OR REPLACE projects SET remote_project_id=? WHERE id=?', (remote,other_project)),
        ]:
            with self.assertRaises(sqlite3.IntegrityError, msg=query):
                self.db.execute(query,values)
            self.assert_valid()

    def test_online_installer_is_atomic_and_cannot_acknowledge_turns(self):
        from audit import authorize, fingerprints, install, probe
        self.insert(self.issue)
        self.db.commit()
        before = fingerprints(self.db)
        self.db.execute('BEGIN IMMEDIATE')
        self.db.set_authorizer(authorize)
        install(self.db)
        self.assertTrue(self.db.in_transaction)
        self.assertTrue(probe(self.db, check_deletion=False)['rolled_back'])
        with self.assertRaises(sqlite3.DatabaseError):
            self.db.execute('UPDATE coding_agent_turns SET seen=1')
        self.db.rollback()
        self.db.set_authorizer(None)
        self.assertEqual(fingerprints(self.db), before)
        self.assertEqual(self.db.execute("SELECT count(*) FROM sqlite_master WHERE name='workspace_issue_validate_insert'").fetchone()[0],0)

    def test_untyped_imports_cannot_create_null_or_non_uuid_links(self):
        self.install()
        for value in [None, b'short', 'not-a-uuid']:
            with self.assertRaises(sqlite3.IntegrityError):
                self.db.execute('INSERT INTO workspaces(id,branch) VALUES(?,?)',(value,'invalid'))
        self.db.execute("INSERT INTO projects(id,name) VALUES('invalid','Invalid')")
        invalid_issue = uuid.uuid4().bytes
        self.db.execute('INSERT INTO tasks VALUES(?,?,?,?,?)',(invalid_issue,'invalid','Invalid',None,'todo'))
        with self.assertRaises(sqlite3.IntegrityError):
            self.insert(invalid_issue)
        self.insert(self.issue)
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE tasks SET project_id='invalid' WHERE id=?",(self.issue,))
        self.assert_valid()

    def test_complete_migration_chain(self):
        from audit import statements
        db = sqlite3.connect(':memory:', isolation_level=None)
        for path in sorted((pathlib.Path(__file__).resolve().parents[2] / 'crates/db/migrations').glob('*.sql')):
            db.execute('BEGIN')
            for statement in statements(path.read_text()):
                db.execute(statement)
            db.commit()
        workspace = uuid.uuid4().bytes
        db.execute('INSERT INTO workspaces(id,branch) VALUES(?,?)', (workspace,'all-migrations'))
        self.assertEqual(db.execute('SELECT task_id FROM workspaces WHERE id=?',(workspace,)).fetchone()[0],workspace)
        db.close()

    def test_identity_collision_fails_without_adopting_another_issue(self):
        self.install()
        self.workspace = self.issue
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'collision'):
            self.insert()
        self.assertEqual(self.db.execute('SELECT count(*) FROM workspaces').fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()
