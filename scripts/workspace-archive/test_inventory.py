"""Fixture checks; production data is read-only and never modified here."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import uuid

from inventory import inspect

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / 'crates/db/migrations/20261125000000_workspace_archive_requests.sql'


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / 'db.sqlite'
        self.conn = sqlite3.connect(self.db)
        self.addCleanup(self.conn.close)
        self.conn.executescript("""
            PRAGMA foreign_keys=ON;
            CREATE TABLE workspaces(id BLOB PRIMARY KEY, archived INTEGER, pinned INTEGER, container_ref TEXT);
            CREATE TABLE sessions(id BLOB PRIMARY KEY,workspace_id BLOB,executor TEXT);
            CREATE TABLE execution_processes(id BLOB PRIMARY KEY,session_id BLOB,status TEXT);
            CREATE TABLE coding_agent_turns(execution_process_id BLOB,agent_session_id TEXT);
            CREATE TABLE turn_github_sync_incoming(workspace_id BLOB,state TEXT);
            CREATE TABLE turn_github_sync_user_queue(workspace_id BLOB);
            CREATE TABLE watcher_job_leases(workspace_id BLOB,closed_at TEXT);
            CREATE TABLE scratch(id BLOB,scratch_type TEXT,payload TEXT);
        """)
        self.native = self.root / 'native.sqlite'
        with sqlite3.connect(self.native) as db:
            db.execute('CREATE TABLE threads(id TEXT,rollout_path TEXT,source TEXT DEFAULT \'cli\',attached_thread_parent_id TEXT)')
            db.execute('CREATE TABLE thread_spawn_edges(parent_thread_id TEXT,child_thread_id TEXT,status TEXT)')
        self.wid, self.sid, self.eid = self.workspace()

    def workspace(self, archived=1, pinned=0, status='completed'):
        w, s, e = (uuid.uuid4() for _ in range(3))
        self.conn.execute('INSERT INTO workspaces VALUES(?,?,?,?)',
                          (w.bytes, archived, pinned, str(self.root / str(w))))
        self.conn.execute('INSERT INTO sessions VALUES(?,?,?)', (s.bytes, w.bytes, 'CODEX'))
        self.conn.execute('INSERT INTO execution_processes VALUES(?,?,?)', (e.bytes, s.bytes, status))
        self.conn.commit()
        return w, s, e

    def read(self):
        self.conn.commit()
        return inspect(self.db, self.root / 'sessions', self.native)

    def row(self, result, wid=None):
        return next(r for r in result['workspaces'] if r['workspace_id'] == str(wid or self.wid))

    def test_native_descendants_are_included_and_open_children_are_protected(self):
        self.conn.execute('INSERT INTO coding_agent_turns VALUES(?,?)', (self.eid.bytes, 'parent'))
        with sqlite3.connect(self.native) as db:
            db.executemany('INSERT INTO threads(id,rollout_path) VALUES(?,?)',
                           [(n, str(self.root / (n + '.jsonl'))) for n in ('parent', 'child', 'grandchild')])
            db.executemany('INSERT INTO thread_spawn_edges VALUES(?,?,?)',
                           [('parent', 'child', 'closed'), ('child', 'grandchild', 'open')])
        row = self.row(self.read())
        self.assertEqual({r['thread_id'] for r in row['native_threads']}, {'parent', 'child', 'grandchild'})
        self.assertIn('open_native_child', row['holds'])

    def test_child_reused_by_another_workspace_protects_both_owners(self):
        other, _, execution = self.workspace(archived=0)
        self.conn.executemany('INSERT INTO coding_agent_turns VALUES(?,?)',
                             [(self.eid.bytes, 'parent'), (execution.bytes, 'child')])
        with sqlite3.connect(self.native) as db:
            db.executemany('INSERT INTO threads(id,rollout_path) VALUES(?,?)',
                           [(n, str(self.root / (n + '.jsonl'))) for n in ('parent', 'child')])
            db.execute("INSERT INTO thread_spawn_edges VALUES('parent','child','closed')")
        for workspace in (self.wid, other):
            self.assertIn('shared_native_history', self.row(self.read(), workspace)['holds'])

    def test_source_only_child_and_cyclic_ancestry_are_not_silently_ignored(self):
        self.conn.execute('INSERT INTO coding_agent_turns VALUES(?,?)', (self.eid.bytes, 'parent'))
        with sqlite3.connect(self.native) as db:
            db.execute('INSERT INTO threads(id,rollout_path) VALUES(?,?)', ('parent', str(self.root / 'parent')))
            db.execute('INSERT INTO threads(id,rollout_path,source) VALUES(?,?,?)',
                       ('child', str(self.root / 'child'), json.dumps({'subagent': {'thread_spawn': {'parent_thread_id': 'parent'}}})))
        self.assertIn('unresolved_native_child', self.row(self.read())['holds'])
        with sqlite3.connect(self.native) as db:
            db.executemany('INSERT INTO thread_spawn_edges VALUES(?,?,?)',
                           [('parent', 'child', 'closed'), ('child', 'parent', 'closed')])
        self.assertIn('cyclic_native_ownership', self.row(self.read())['holds'])

    def test_inventory_does_not_grant_retirement_or_backup_exclusion(self):
        result = self.read()
        self.assertTrue(self.row(result)['metadata_candidate'])
        self.assertFalse(result['movement_authorized'])
        self.assertFalse(result['backup_exclusion_authorized'])
        self.assertFalse(result['live_custody_verified'])

    def test_pinned_running_and_active_are_preserved(self):
        w, _, _ = self.workspace(archived=0, pinned=1, status='running')
        self.assertEqual(self.row(self.read(), w)['holds'],
                         ['active_workspace', 'pinned', 'running_execution'])

    def test_pending_inputs_and_open_lease_survive_old_completed_execution(self):
        self.conn.execute('INSERT INTO turn_github_sync_incoming VALUES(?,?)', (self.wid.bytes, 'received'))
        self.conn.execute('INSERT INTO turn_github_sync_user_queue VALUES(?)', (self.wid.bytes,))
        self.conn.execute('INSERT INTO watcher_job_leases VALUES(?,NULL)', (self.wid.bytes,))
        self.conn.execute('INSERT INTO scratch VALUES(?,?,?)',
                          (self.sid.bytes, 'DRAFT_FOLLOW_UP', json.dumps({'type': 'DRAFT_FOLLOW_UP', 'data': {'message': 'PRIVATE PROMPT'}})))
        result = self.read()
        self.assertEqual(self.row(result)['holds'],
                         ['draft_input', 'open_watcher_lease', 'pending_input', 'queued_input'])
        self.assertNotIn('PRIVATE PROMPT', json.dumps(result))

    def test_shared_native_history_is_never_attributed_exclusively(self):
        w, _, e = self.workspace(archived=0)
        for execution in (self.eid, e):
            self.conn.execute('INSERT INTO coding_agent_turns VALUES(?,?)', (execution.bytes, 'thread'))
        with sqlite3.connect(self.native) as db:
            db.execute('INSERT INTO threads(id,rollout_path) VALUES(?,?)', ('thread', str(self.root / 'rollout.jsonl')))
        result = self.read()
        for wid in (self.wid, w):
            self.assertIn('shared_native_history', self.row(result, wid)['holds'])

    def test_different_native_ids_sharing_one_file_are_protected(self):
        w, _, e = self.workspace()
        for execution, thread in ((self.eid, 'a'), (e, 'b')):
            self.conn.execute('INSERT INTO coding_agent_turns VALUES(?,?)', (execution.bytes, thread))
            with sqlite3.connect(self.native) as db:
                db.execute('INSERT INTO threads(id,rollout_path) VALUES(?,?)', (thread, str(self.root / 'same.jsonl')))
        self.assertIn('shared_native_history', self.row(self.read(), w)['holds'])

    def test_unresolved_native_and_shared_worktree_are_not_candidates(self):
        w, _, _ = self.workspace()
        self.conn.execute('UPDATE workspaces SET container_ref=?', (str(self.root / 'shared'),))
        self.conn.execute('INSERT INTO coding_agent_turns VALUES(?,?)', (self.eid.bytes, 'missing'))
        result = self.read()
        self.assertEqual(self.row(result)['holds'], ['shared_worktree', 'unresolved_native_history'])
        self.assertFalse(self.row(result, w)['metadata_candidate'])

    def test_missing_required_schema_fails_closed(self):
        self.conn.execute('DROP TABLE watcher_job_leases')
        with self.assertRaises(sqlite3.OperationalError):
            self.read()

    def migrate(self):
        self.conn.executescript(MIGRATION.read_text())

    def request(self):
        return self.conn.execute('SELECT requested_state,request_version FROM workspace_archive_requests WHERE workspace_id=?',
                                 (self.wid.bytes,)).fetchone()

    def test_backfill_and_normal_archive_action_share_one_outbox(self):
        active, _, _ = self.workspace(archived=0)
        self.migrate()
        self.assertEqual(self.request(), ('archived', 1))
        self.assertEqual(self.conn.execute('SELECT count(*) FROM workspace_archive_requests').fetchone()[0], 1)
        self.conn.execute('UPDATE workspaces SET archived=1 WHERE id=?', (active.bytes,))
        self.assertEqual(self.conn.execute('SELECT count(*) FROM workspace_archive_requests').fetchone()[0], 2)

    def test_revival_invalidates_archive_then_rearchive_gets_new_generation(self):
        self.migrate()
        for flag, expected in ((0, ('active', 2)), (1, ('archived', 3)), (1, ('archived', 3))):
            self.conn.execute('UPDATE workspaces SET archived=? WHERE id=?', (flag, self.wid.bytes))
            self.assertEqual(self.request(), expected)

    def test_failed_archive_transaction_leaves_no_phantom_request(self):
        self.migrate()
        self.conn.execute('UPDATE workspaces SET archived=0 WHERE id=?', (self.wid.bytes,))
        self.conn.rollback()
        self.assertEqual(self.request(), ('archived', 1))

    def test_new_archived_workspace_and_owner_deletion(self):
        self.migrate()
        w, _, _ = self.workspace()
        self.assertEqual(self.conn.execute('SELECT requested_state FROM workspace_archive_requests WHERE workspace_id=?',
                                          (w.bytes,)).fetchone()[0], 'archived')
        self.conn.execute('DELETE FROM workspaces WHERE id=?', (self.wid.bytes,))
        self.assertIsNone(self.request())


if __name__ == '__main__':
    unittest.main()
