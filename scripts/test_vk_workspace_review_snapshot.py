import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import uuid

import vk_workspace_review_snapshot as snapshot


class ReviewSnapshotTests(unittest.TestCase):
    def setUp(self):
        if not snapshot.SSD.is_mount():
            self.skipTest('Requires mounted secondary SSD; no system-disk fixture fallback')
        self.root = tempfile.TemporaryDirectory(dir='/mnt/vk-storage')
        self.addCleanup(self.root.cleanup)
        self.path = Path(self.root.name) / 'fixture.sqlite'
        self.db = sqlite3.connect(self.path)
        self.addCleanup(self.db.close)
        self.db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE workspaces(id BLOB PRIMARY KEY, name TEXT, archived INTEGER, pinned INTEGER);
            CREATE TABLE sessions(id BLOB PRIMARY KEY, workspace_id BLOB);
            CREATE TABLE execution_processes(id BLOB PRIMARY KEY, session_id BLOB, status TEXT);
            CREATE TABLE coding_agent_turns(id BLOB PRIMARY KEY, execution_process_id BLOB,
                seen INTEGER, updated_at TEXT, prompt TEXT, summary TEXT);
        ''')
        self.workspace, self.session, self.execution, self.turn = [uuid.uuid4() for _ in range(4)]
        self.db.execute('INSERT INTO workspaces VALUES(?,?,0,1)', (self.workspace.bytes, 'Recent work'))
        self.db.execute('INSERT INTO sessions VALUES(?,?)', (self.session.bytes, self.workspace.bytes))
        self.db.execute('INSERT INTO execution_processes VALUES(?,?,?)', (self.execution.bytes, self.session.bytes, 'completed'))
        self.db.execute('INSERT INTO coding_agent_turns VALUES(?,?,0,?,?,?)',
                        (self.turn.bytes, self.execution.bytes, 'before', 'private prompt', 'private summary'))
        self.db.commit()

    def test_live_wal_and_metadata_mapping(self):
        result = snapshot.capture(self.path, 'before publication')
        row = result['tables']['coding_agent_turns'][0]
        self.assertEqual(row['id'], str(self.turn))
        self.assertEqual(row['execution_process_id'], str(self.execution))
        self.assertEqual(result['tables']['sessions'][0]['workspace_id'], str(self.workspace))
        self.assertEqual(row['seen'], 0)
        self.assertNotIn('private prompt', json.dumps(result))
        self.assertNotIn('private summary', json.dumps(result))
        self.assertIsNone(result['review_journal_head'])
        self.assertFalse(result['review_journal_enabled'])

    def test_capture_does_not_mark_read(self):
        before = self.db.execute('SELECT * FROM coding_agent_turns').fetchall()
        snapshot.capture(self.path, 'read only')
        self.assertEqual(self.db.execute('SELECT * FROM coding_agent_turns').fetchall(), before)

    def test_capture_closes_its_sqlite_reader(self):
        snapshot.capture(self.path, 'before writer closes')
        self.db.close()
        self.assertFalse(Path(str(self.path) + '-wal').exists())
        self.assertFalse(Path(str(self.path) + '-shm').exists())

    def test_api_identity_and_flags(self):
        result = snapshot.capture(self.path, 'verify')
        live = {'workspaces': [{'id': str(self.workspace)}], 'summaries': [
            {'workspace_id': str(self.workspace), 'has_unseen_turns': True}]}
        snapshot.verify_api_identity(result, live)
        live['summaries'][0]['has_unseen_turns'] = False
        with self.assertRaises(ValueError):
            snapshot.verify_api_identity(result, live)
        live['workspaces'][0]['id'] = str(uuid.uuid4())
        with self.assertRaises(ValueError):
            snapshot.verify_api_identity(result, live)

    def test_storage_is_fail_closed(self):
        with patch.object(Path, 'is_mount', return_value=False):
            with self.assertRaises(ValueError):
                snapshot.verify_destination('/mnt/vk-storage/snapshot.json')
        with self.assertRaises(ValueError):
            snapshot.verify_destination('/tmp/snapshot.json')
        self.assertEqual(snapshot.verify_destination(Path(self.root.name) / 'snapshot.json'),
                         Path(self.root.name) / 'snapshot.json')

    def test_journal_read_unread_delete_and_identity(self):
        snapshot.install_journal(self.path)
        self.db.execute('UPDATE coding_agent_turns SET seen=1,updated_at="reviewed"')
        self.db.execute('UPDATE coding_agent_turns SET seen=0,updated_at="new completion"')
        self.db.commit()
        events = self.db.execute('SELECT old_seen,new_seen,workspace_id,session_id FROM workspace_review_events ORDER BY sequence').fetchall()
        self.assertEqual(events, [(0, 1, self.workspace.bytes, self.session.bytes),
                                  (1, 0, self.workspace.bytes, self.session.bytes)])
        self.assertEqual(snapshot.capture(self.path, 'after')['review_journal_head'], 2)
        self.assertTrue(snapshot.capture(self.path, 'after')['review_journal_enabled'])
        self.db.execute('DELETE FROM coding_agent_turns')
        self.db.commit()
        self.assertEqual(self.db.execute('SELECT action,old_seen,new_seen FROM workspace_review_events ORDER BY sequence DESC LIMIT 1').fetchone(), ('delete', 0, None))

    def test_summary_streaming_does_not_fill_journal(self):
        snapshot.install_journal(self.path)
        self.db.execute('UPDATE coding_agent_turns SET summary="streaming",updated_at="stream"')
        self.db.commit()
        self.assertEqual(self.db.execute('SELECT count(*) FROM workspace_review_events').fetchone()[0], 0)

    def test_insert_and_reinstall_preserve_journal(self):
        snapshot.install_journal(self.path)
        self.db.execute('INSERT INTO coding_agent_turns VALUES(?,?,0,?,?,?)',
                        (uuid.uuid4().bytes, self.execution.bytes, 'new', '', ''))
        self.db.commit()
        snapshot.install_journal(self.path)
        self.assertEqual(self.db.execute('SELECT action,workspace_id FROM workspace_review_events').fetchall(),
                         [('insert', self.workspace.bytes)])

    def test_rollback_reverts_event_as_well(self):
        snapshot.install_journal(self.path)
        self.db.execute('UPDATE coding_agent_turns SET seen=1,updated_at="bad repair"')
        self.db.rollback()
        self.assertEqual(self.db.execute('SELECT seen FROM coding_agent_turns').fetchone()[0], 0)
        self.assertEqual(self.db.execute('SELECT count(*) FROM workspace_review_events').fetchone()[0], 0)

    def test_remote_checksum_failure_blocks_publication(self):
        path = Path(self.root.name) / 'review.json'
        path.write_text('{}')
        with patch.object(snapshot.subprocess, 'check_output', side_effect=['', 'not-the-sha256']), \
             patch.object(snapshot.subprocess, 'run'):
            with self.assertRaises(ValueError):
                snapshot.mirror(path, 'desktop', 'B:/vk-backups/reviews', [])

    def test_frontend_snapshot_failure_preserves_production_pointer(self):
        root = Path(self.root.name)
        scripts = root / 'scripts'
        scripts.mkdir()
        entry = scripts / 'vk-publish-frontend-dist.sh'
        entry.write_text((Path(__file__).parent / entry.name).read_text())
        build = root / 'packages/local-web/dist'
        build.mkdir(parents=True)
        (build / 'index.html').write_text('candidate')
        tools = root / 'bin'
        tools.mkdir()
        for name, content in [('pnpm', '#!/bin/sh\nexit 0\n'), ('python3', '#!/bin/sh\nexit 77\n')]:
            path = tools / name
            path.write_text(content)
            path.chmod(0o755)
        previous = root / 'previous'
        previous.mkdir()
        pointer = root / 'current'
        pointer.symlink_to(previous, target_is_directory=True)
        environment = {'PATH': str(tools) + ':/usr/bin:/bin', 'HOME': str(root),
                       'VK_STATE_DIR': str(root), 'VK_FRONTEND_DIST_DIR': str(pointer),
                       'VK_REVIEW_SNAPSHOT_API_URL': 'http://127.0.0.1:5411'}
        result = subprocess.run(['bash', str(entry)], env=environment, capture_output=True)
        self.assertEqual(result.returncode, 77)
        self.assertEqual(pointer.resolve(), previous)
        self.assertFalse((root / 'frontend-dist/releases').exists())

    def test_frontend_requires_explicit_live_identity(self):
        entry = Path(__file__).parent / 'vk-publish-frontend-dist.sh'
        result = subprocess.run(['bash', str(entry)], env={'PATH': '/usr/bin:/bin'},
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('VK_STATE_DIR', result.stderr)


if __name__ == '__main__':
    unittest.main()
