#!/usr/bin/env python3
"""Real Git/SQLite maintenance-path tests on disposable mounted storage only."""
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import unittest
from unittest.mock import patch
import uuid

import test_turn_git as fixtures
import reconcile_observation as repair
from turn_git import Blocked, atomic_json, read_json


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        fixture = self.fixture = fixtures.PreservationTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.workspace, self.turn, self.session = [uuid.uuid4() for _ in range(3)]
        self.request = dict(fixture.request, workspace=str(self.workspace), turn=str(self.turn))
        fixture.config['repositories'].clear()
        begun = fixture.engine.begin(self.request)
        self.assertEqual(begun['state'], 'blocked')
        # Model old deployed begin, before the new inventory/cause fields existed.
        self.ledger = fixture.engine.state_path(self.request)
        record = read_json(self.ledger)
        record.pop('observation_inventory')
        record.pop('admission_failure')
        atomic_json(self.ledger, record)
        fixture.changed(value='Historical completed B\n')
        fixtures.git(fixture.repo, 'add', '.')
        fixtures.git(fixture.repo, 'commit', '-qm', 'B')
        self.b = fixtures.git(fixture.repo, 'rev-parse', 'HEAD')
        self.config = fixture.root / 'external-policy.json'
        atomic_json(self.config, fixture.config)
        self.database = fixture.root / 'native.sqlite'
        self.connection = sqlite3.connect(self.database)
        self.addCleanup(self.connection.close)
        self.connection.executescript('''
CREATE TABLE sessions(id BLOB PRIMARY KEY, workspace_id BLOB);
CREATE TABLE execution_processes(id BLOB PRIMARY KEY,session_id BLOB,status TEXT,completed_at TEXT,dropped INTEGER,created_at TEXT DEFAULT '2026-10-16T07:59:00+00:00');
CREATE TABLE execution_process_repo_states(execution_process_id BLOB,repo_id BLOB,before_head_commit TEXT,after_head_commit TEXT,updated_at TEXT);
CREATE TABLE turn_github_sync(execution_process_id BLOB PRIMARY KEY,workspace_id BLOB,request TEXT,state TEXT,observation_state TEXT,observation_report TEXT,report TEXT,retry_at INTEGER,created_at TEXT,updated_at TEXT);
CREATE TABLE turn_github_sync_incoming(workspace_id BLOB,state TEXT);
CREATE TABLE turn_github_sync_user_queue(workspace_id BLOB);
''')
        self.repo_id = 'repo'  # Replace fixture ID with a native UUID in all identities.
        native_id = str(uuid.uuid4())
        self.request['repositories'][0] = dict(id=native_id, path=str(fixture.repo))
        record = read_json(self.ledger)
        record['obligations'][native_id] = record['obligations'].pop('repo')
        atomic_json(self.ledger, record)
        self.repo_id = native_id
        self.failure = json.dumps(dict(version=2, state='blocked', reason=repair.FAULT))
        self.connection.execute('INSERT INTO sessions VALUES(?,?)', (self.session.bytes, self.workspace.bytes))
        self.connection.execute('INSERT INTO execution_processes(id,session_id,status,completed_at,dropped) VALUES(?,?,?,?,0)',
                                (self.turn.bytes, self.session.bytes, 'completed', '2026-10-16T08:00:00+00:00'))
        self.connection.execute('INSERT INTO execution_process_repo_states VALUES(?,?,?,?,?)',
                                (self.turn.bytes, uuid.UUID(native_id).bytes, fixture.base, self.b,
                                 '2026-10-16T08:00:00.25+00:00'))
        self.connection.execute('INSERT INTO turn_github_sync VALUES(?,?,?,?,?,?,?,?,?,?)',
                                (self.turn.bytes, self.workspace.bytes, json.dumps(self.request),
                                 'blocked', 'failed', self.failure, '{}', int(time.time()) + 3600,
                                 '2026-10-16 07:59:00', '2026-10-16 08:00:00'))
        self.connection.commit()
        self.plan = fixture.root / 'repair-plan.json'

    def plan_repair(self):
        result = repair.create_plan(self.database, self.config, str(self.workspace), self.plan)
        self.assertNotIn('selected_turn', read_json(self.plan))
        return result['sha256']

    def state(self):
        return self.connection.execute('SELECT observation_state,state FROM turn_github_sync').fetchone()

    def unrelated_owner(self):
        other = uuid.uuid4()
        self.connection.execute('INSERT INTO execution_processes VALUES(?,?,?,?,0,?)',
                                (other.bytes, self.session.bytes, 'killed',
                                 '2026-10-16T08:02:00+00:00', '2026-10-16T08:01:00+00:00'))
        request = dict(self.request, turn=str(other))
        self.connection.execute('INSERT INTO turn_github_sync VALUES(?,?,?,?,?,?,?,?,?,?)',
                                (other.bytes, self.workspace.bytes, json.dumps(request),
                                 'blocked', 'pending', None, 'original unrelated report',
                                 int(time.time()) + 3600, '2026-10-16 08:01:00', '2026-10-16 08:02:00'))
        self.connection.commit()
        return other

    def test_exact_turn_repair_leaves_unrelated_uncertainty_intact(self):
        other = self.unrelated_owner()
        with self.assertRaisesRegex(Blocked, 'exact completed legacy'):
            self.plan_repair()
        digest = repair.create_plan(self.database, self.config, str(self.workspace),
                                    self.plan, str(self.turn))['sha256']
        self.assertEqual(len(read_json(self.plan)['entries']), 1)
        self.assertEqual(repair.apply_plan(self.plan, digest)['turns'], 1)
        self.assertTrue(repair.apply_plan(self.plan, digest)['already_applied'])
        untouched = self.connection.execute(
            'SELECT observation_state,state,report FROM turn_github_sync WHERE execution_process_id=?',
            (other.bytes,)).fetchone()
        self.assertEqual(untouched, ('pending', 'blocked', 'original unrelated report'))
        self.assertEqual(self.connection.execute(
            "SELECT count(*) FROM turn_github_sync WHERE observation_state!='observed'").fetchone()[0], 1)

    def test_exact_turn_plan_refuses_new_owner_or_changed_selection(self):
        digest = repair.create_plan(self.database, self.config, str(self.workspace),
                                    self.plan, str(self.turn))['sha256']
        self.unrelated_owner()
        with self.assertRaisesRegex(Blocked, 'owner inventory changed'):
            repair.apply_plan(self.plan, digest)
        self.assertEqual(self.connection.execute(
            'SELECT observation_state FROM turn_github_sync WHERE execution_process_id=?',
            (self.turn.bytes,)).fetchone()[0], 'failed')
        self.connection.execute('DELETE FROM execution_processes WHERE id!=?', (self.turn.bytes,))
        self.connection.execute('DELETE FROM turn_github_sync WHERE execution_process_id!=?', (self.turn.bytes,))
        self.connection.commit()
        plan = read_json(self.plan)
        plan['selected_turn'] = str(uuid.uuid4())
        atomic_json(self.plan, plan)
        with self.assertRaisesRegex(Blocked, 'selected turn differs'):
            repair.apply_plan(self.plan, hashlib.sha256(self.plan.read_bytes()).hexdigest())

    def test_exact_turn_plan_refuses_unknown_owner(self):
        with self.assertRaisesRegex(Blocked, 'not a checkpoint owner'):
            repair.create_plan(self.database, self.config, str(self.workspace),
                               self.plan, str(uuid.uuid4()))
        self.assertFalse(self.plan.exists())

    def test_execution_time_heads_reconcile_after_reset_without_green_coverage(self):
        digest = self.plan_repair()
        self.assertEqual(self.state(), ('failed', 'blocked'))
        fixtures.git(self.fixture.repo, 'reset', '--hard', self.fixture.base)
        original_index = (self.fixture.repo / '.git/index').read_bytes()
        result = repair.apply_plan(self.plan, digest)
        self.assertEqual(result['state'], 'reconciled')
        self.assertIs(result['coverage_verified'], False)
        self.assertEqual(self.state(), ('observed', 'blocked'))
        ledger = read_json(self.ledger)
        self.assertIn(self.b, ledger['obligations'][self.repo_id]['commits'])
        self.assertEqual(ledger['repositories'], [])
        self.assertEqual(ledger['state'], 'blocked')
        self.assertEqual(fixtures.git(self.fixture.repo, 'rev-parse', 'HEAD'), self.fixture.base)
        self.assertEqual((self.fixture.repo / '.git/index').read_bytes(), original_index)
        self.assertTrue(repair.apply_plan(self.plan, digest)['already_applied'])

    def test_pending_running_inputs_and_retry_boundaries_refuse_mutation(self):
        digest = self.plan_repair()
        cases = [('execution_processes', "status='running'", 'workspace is running'),
                 ('turn_github_sync', "retry_at=0", 'retry is due'),
                 ('turn_github_sync', "observation_state='pending'", 'exact completed legacy')]
        for table, change, reason in cases:
            with self.subTest(change=change):
                self.connection.execute('UPDATE ' + table + ' SET ' + change)
                self.connection.commit()
                with self.assertRaisesRegex(Blocked, reason):
                    repair.apply_plan(self.plan, digest)
                self.connection.execute("UPDATE execution_processes SET status='completed'")
                self.connection.execute("UPDATE turn_github_sync SET observation_state='failed',retry_at=?", (int(time.time()) + 3600,))
                self.connection.commit()
        self.connection.execute("INSERT INTO turn_github_sync_incoming VALUES(?,'received')", (self.workspace.bytes,))
        self.connection.commit()
        with self.assertRaisesRegex(Blocked, 'user work has priority'):
            repair.apply_plan(self.plan, digest)

    def test_missing_late_or_changed_terminal_evidence_stays_failed(self):
        digest = self.plan_repair()
        for change in ["after_head_commit=NULL", "updated_at='2026-10-16T09:00:00+00:00'"]:
            self.connection.execute('UPDATE execution_process_repo_states SET ' + change)
            self.connection.commit()
            with self.assertRaisesRegex(Blocked, 'provenance'):
                repair.apply_plan(self.plan, digest)
            self.assertEqual(self.state(), ('failed', 'blocked'))
            self.connection.execute('UPDATE execution_process_repo_states SET after_head_commit=?,updated_at=?',
                                    (self.b, '2026-10-16T08:00:00.25+00:00'))
            self.connection.commit()

    def test_tampered_plan_owner_inventory_policy_and_ledger_fail_closed(self):
        digest = self.plan_repair()
        with self.assertRaisesRegex(Blocked, 'SHA-256'):
            repair.apply_plan(self.plan, '0' * 64)
        record = read_json(self.ledger)
        record['reason'] = 'concurrent writer'
        atomic_json(self.ledger, record)
        with self.assertRaisesRegex(Blocked, 'ledger changed'):
            repair.apply_plan(self.plan, digest)
        self.assertEqual(self.state(), ('failed', 'blocked'))

    def test_plan_cannot_drop_an_original_even_with_a_new_digest(self):
        self.plan_repair()
        plan = read_json(self.plan)
        plan['originals'][self.repo_id]['commits'].remove(self.b)
        atomic_json(self.plan, plan)
        with self.assertRaisesRegex(Blocked, 'dropped or invented'):
            repair.apply_plan(self.plan, hashlib.sha256(self.plan.read_bytes()).hexdigest())
        self.assertEqual(self.state(), ('failed', 'blocked'))

    def test_policy_owner_and_native_state_drift_are_not_reconstructed(self):
        digest = self.plan_repair()
        self.connection.execute('UPDATE execution_process_repo_states SET after_head_commit=?',
                                (self.fixture.base,))
        self.connection.commit()
        with self.assertRaisesRegex(Blocked, 'historical capture changed'):
            repair.apply_plan(self.plan, digest)
        self.connection.execute('UPDATE execution_process_repo_states SET after_head_commit=?', (self.b,))
        self.connection.commit()
        config = read_json(self.config)
        config['review'] = 'changed policy'
        atomic_json(self.config, config)
        with self.assertRaisesRegex(Blocked, 'policy changed'):
            repair.apply_plan(self.plan, digest)
        self.assertEqual(self.state(), ('failed', 'blocked'))

    def test_next_execution_before_terminal_capture_refuses_reconciliation(self):
        digest = self.plan_repair()
        self.connection.execute('INSERT INTO execution_processes VALUES(?,?,?,?,0,?)',
                                (uuid.uuid4().bytes, self.session.bytes, 'completed',
                                 '2026-10-16T08:00:00.2+00:00', '2026-10-16T08:00:00.1+00:00'))
        self.connection.commit()
        with self.assertRaisesRegex(Blocked, 'overlaps the terminal capture'):
            repair.apply_plan(self.plan, digest)
        self.assertEqual(self.state(), ('failed', 'blocked'))

    def test_failed_observation_cas_never_releases_gate_and_retry_is_idempotent(self):
        digest = self.plan_repair()
        self.connection.execute("CREATE TRIGGER simulate_failed_update BEFORE UPDATE OF observation_state ON turn_github_sync BEGIN SELECT RAISE(IGNORE); END")
        self.connection.commit()
        with self.assertRaisesRegex(Blocked, 'compare-and-swap failed'):
            repair.apply_plan(self.plan, digest)
        self.assertEqual(self.state(), ('failed', 'blocked'))
        self.connection.execute('DROP TRIGGER simulate_failed_update')
        self.connection.commit()
        self.assertEqual(repair.apply_plan(self.plan, digest)['state'], 'reconciled')
        record = read_json(self.ledger)
        record['obligations'][self.repo_id]['commits'].remove(self.b)
        atomic_json(self.ledger, record)
        with self.assertRaisesRegex(Blocked, 'ledger is missing or changed'):
            repair.apply_plan(self.plan, digest)

    def test_interruption_after_ledger_write_leaves_gate_and_exact_retry_recovers(self):
        digest = self.plan_repair()
        real = repair.atomic_json
        def interrupted(path, value):
            real(path, value)
            if Path(path) == self.ledger:
                raise OSError('synthetic interruption after original capture')
        with patch.object(repair, 'atomic_json', interrupted):
            with self.assertRaises(OSError):
                repair.apply_plan(self.plan, digest)
        self.assertEqual(self.state(), ('failed', 'blocked'))
        self.assertIn(self.b, read_json(self.ledger)['obligations'][self.repo_id]['commits'])
        self.assertEqual(repair.apply_plan(self.plan, digest)['state'], 'reconciled')


class RelocationReconciliationTests(unittest.TestCase):
    def setUp(self):
        ReconciliationTests.setUp(self)
        self.old_root = self.fixture.root / 'old-workspace'
        self.new_root = self.fixture.root / 'renamed-workspace'
        self.old_root.mkdir()
        self.new_root.mkdir()
        old = self.old_root / 'repo'
        current = self.new_root / 'repo'
        fixtures.git(self.fixture.repo, 'worktree', 'add', '-qb', 'feat/relocated', str(old), 'HEAD')
        record = read_json(self.ledger)
        record['obligations'][self.repo_id]['path'] = str(old)
        atomic_json(self.ledger, record)
        self.request['repositories'][0]['path'] = str(old)
        self.connection.executescript("""
CREATE TABLE workspaces(id BLOB PRIMARY KEY,container_ref TEXT);
CREATE TABLE repos(id BLOB PRIMARY KEY,name TEXT,path TEXT);
CREATE TABLE workspace_repos(workspace_id BLOB,repo_id BLOB);
""")
        self.connection.execute('INSERT INTO workspaces VALUES(?,?)', (self.workspace.bytes, str(self.new_root)))
        self.connection.execute('INSERT INTO repos VALUES(?,?,?)', (uuid.UUID(self.repo_id).bytes, 'repo', str(self.fixture.repo)))
        self.connection.execute('INSERT INTO workspace_repos VALUES(?,?)', (self.workspace.bytes, uuid.UUID(self.repo_id).bytes))
        self.connection.execute('UPDATE turn_github_sync SET request=?', (json.dumps(self.request),))
        self.connection.commit()
        fixtures.git(self.fixture.repo, 'worktree', 'move', str(old), str(current))
        self.old_root.rmdir()

    state = ReconciliationTests.state

    def plan_repair(self):
        return repair.create_plan(self.database, self.config, str(self.workspace), self.plan,
                                  relocation=(self.old_root, self.new_root))['sha256']

    def test_relocation_retains_originals_and_next_callback_observes_without_publication(self):
        digest = self.plan_repair()
        self.assertEqual(repair.apply_plan(self.plan, digest)['turns'], 1)
        self.assertEqual(self.state(), ('observed', 'blocked'))
        record = read_json(self.ledger)
        self.assertEqual(record['obligations'][self.repo_id]['path'], str(self.new_root / 'repo'))
        self.assertIn(self.b, record['obligations'][self.repo_id]['commits'])
        self.assertEqual(read_json(self.plan)['scope'], repair.RELOCATED_SCOPE)
        self.assertTrue(repair.apply_plan(self.plan, digest)['already_applied'])
        next_request = dict(self.request, turn=str(uuid.uuid4()), repositories=[dict(id=self.repo_id, path=str(self.new_root / 'repo'))])
        begun = self.fixture.engine.begin(next_request)
        self.assertEqual(begun['admission_failure'], repair.NO_POLICY)
        self.assertTrue(self.fixture.engine.observe_finished(next_request)['observation_complete'])
        self.assertEqual(self.fixture.engine.checkpoint(next_request)['state'], 'pending')
        self.assertFalse(self.fixture.prfile.exists())

    def test_new_inventory_original_obligation_mismatch_is_repairable(self):
        self.request['repositories'][0]['path'] = str(self.new_root / 'repo')
        record = read_json(self.ledger)
        record['observation_inventory'] = self.request['repositories']
        record['admission_failure'] = 'original repository identity changed'
        atomic_json(self.ledger, record)
        self.connection.execute('UPDATE turn_github_sync SET request=?,observation_report=?',
                                (json.dumps(self.request), json.dumps(dict(reason=repair.OBLIGATION_FAULT))))
        self.connection.commit()
        self.assertEqual(repair.apply_plan(self.plan, self.plan_repair())['state'], 'reconciled')

    def test_extant_old_root_and_changed_native_destination_refuse_repair(self):
        self.old_root.mkdir()
        with self.assertRaisesRegex(Blocked, 'absent old root'):
            self.plan_repair()
        self.old_root.rmdir()
        digest = self.plan_repair()
        self.connection.execute('UPDATE workspaces SET container_ref=?', (str(self.fixture.root),))
        self.connection.commit()
        with self.assertRaisesRegex(Blocked, 'native workspace root'):
            repair.apply_plan(self.plan, digest)
        self.assertEqual(self.state(), ('failed', 'blocked'))

    def test_missing_terminal_capture_and_unrelated_fault_are_not_cleared(self):
        self.connection.execute('UPDATE execution_process_repo_states SET after_head_commit=NULL')
        self.connection.commit()
        with self.assertRaisesRegex(Blocked, 'provenance'):
            self.plan_repair()
        self.connection.execute('UPDATE execution_process_repo_states SET after_head_commit=?', (self.b,))
        self.connection.execute('UPDATE turn_github_sync SET observation_report=?', (json.dumps(dict(reason='unknown failure')),))
        self.connection.commit()
        with self.assertRaisesRegex(Blocked, 'exact completed legacy'):
            self.plan_repair()

    def test_native_repository_and_worktree_backlink_must_match(self):
        admin = self.new_root / 'repo'
        git_dir = Path(fixtures.git(admin, 'rev-parse', '--absolute-git-dir'))
        (git_dir / 'gitdir').write_text(str(self.fixture.repo / '.git'))
        with self.assertRaisesRegex(Blocked, 'backlink'):
            self.plan_repair()

    def test_relocation_cannot_drop_originals_or_weaken_idle_boundary(self):
        digest = self.plan_repair()
        plan = read_json(self.plan)
        plan['originals'][self.repo_id]['commits'].remove(self.b)
        atomic_json(self.plan, plan)
        with self.assertRaisesRegex(Blocked, 'dropped or invented'):
            repair.apply_plan(self.plan, hashlib.sha256(self.plan.read_bytes()).hexdigest())
        self.plan.unlink()
        digest = self.plan_repair()
        self.connection.execute("INSERT INTO turn_github_sync_incoming VALUES(?,'received')", (self.workspace.bytes,))
        self.connection.commit()
        with self.assertRaisesRegex(Blocked, 'user work has priority'):
            repair.apply_plan(self.plan, digest)


if __name__ == '__main__':
    unittest.main(verbosity=2)
