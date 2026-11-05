#!/usr/bin/env python3
"""Small Git/SQLite fixtures; no model, live DB or hosted calls."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch
import uuid

import inspect_observation as inspect
import reconcile_observation as repair
import test_reconcile_observation as fixtures
from turn_git import Blocked, atomic_json


class InspectionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = f = fixtures.ReconciliationTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        f.connection.executescript('''
ALTER TABLE execution_processes ADD COLUMN exit_code INTEGER DEFAULT 0;
CREATE TABLE workspaces(id BLOB, branch TEXT,container_ref TEXT);
CREATE TABLE repos(id BLOB,name TEXT);
CREATE TABLE workspace_repos(workspace_id BLOB,repo_id BLOB);
''')
        f.connection.execute('INSERT INTO workspaces VALUES(?,?,?)',
                             (f.workspace.bytes, 'feat/fixture', str(f.fixture.repo.parent)))
        f.connection.execute('INSERT INTO repos VALUES(?,?)', (uuid.UUID(f.repo_id).bytes, 'repo'))
        f.connection.execute('INSERT INTO workspace_repos VALUES(?,?)', (f.workspace.bytes, uuid.UUID(f.repo_id).bytes))
        f.connection.commit()

    def report(self):
        f = self.fixture
        return inspect.inspect_turn(f.database, f.config, str(f.workspace), str(f.turn))

    def before(self):
        f = self.fixture
        return (f.ledger.read_bytes(), f.connection.execute('SELECT * FROM turn_github_sync').fetchall(),
                f.connection.execute('SELECT * FROM execution_processes').fetchall(),
                (f.fixture.repo / '.git/index').read_bytes())

    def test_completed_inspection_has_no_ack_apply_or_publication_authority(self):
        before = self.before()
        with patch.object(inspect, 'atomic_json', side_effect=AssertionError('read-only')):
            report = self.report()
        self.assertEqual(report['state'], 'inspected')
        self.assertTrue(report['terminal_provenance_passed'])
        self.assertFalse(report['apply_supported'])
        self.assertFalse(report['coverage_verified'])
        self.assertEqual(report['admitted_inventory'], [])
        self.assertEqual(report['requested_inventory'], report['current_inventory'])
        self.assertEqual(before, self.before())

    def test_failed_status_and_prior_failure_survive_even_timely_capture(self):
        f = self.fixture
        f.connection.execute("UPDATE execution_processes SET status='failed',exit_code=1")
        f.connection.commit()
        before = self.before()
        report = self.report()
        self.assertEqual(report['native_execution']['status'], 'failed')
        self.assertEqual(report['native_execution']['exit_code'], 1)
        self.assertTrue(report['terminal_provenance_passed'])
        self.assertEqual([b['code'] for b in report['blockers']], ['execution_outcome_unsupported'])
        self.assertEqual(report['prior_observation_report'], json.loads(f.failure))
        self.assertEqual(before, self.before())
        with self.assertRaisesRegex(Blocked, 'exact completed legacy'):
            f.plan_repair()

    def test_failed_late_capture_reports_both_blockers_without_current_head_substitution(self):
        f = self.fixture
        f.connection.execute("UPDATE execution_processes SET status='failed',exit_code=1")
        f.connection.execute("UPDATE execution_process_repo_states SET updated_at='2026-10-16T08:00:06.414+00:00'")
        f.connection.commit()
        before = self.before()
        report = self.report()
        self.assertEqual({b['code'] for b in report['blockers']},
                         {'execution_outcome_unsupported', 'terminal_provenance_unproven'})
        self.assertFalse(report['terminal_provenance_passed'])
        self.assertAlmostEqual(report['native_states'][0]['capture_delay_seconds'], 6.414, places=3)
        self.assertEqual(report['historical_file_snapshot'], 'not_inferred')
        self.assertFalse(report['observation_state_changed'])
        self.assertEqual(before, self.before())

    def test_inspection_cannot_be_applied_even_with_its_correct_hash(self):
        f = self.fixture
        report = self.report()
        output = f.fixture.root / 'inspection.json'
        atomic_json(output, report)
        with self.assertRaisesRegex(Blocked, 'unsupported repair authority'):
            repair.apply_plan(output, hashlib.sha256(output.read_bytes()).hexdigest())
        self.assertEqual(f.state(), ('failed', 'blocked'))

    def test_running_or_queued_work_refuses_inspection(self):
        f = self.fixture
        f.connection.execute("UPDATE execution_processes SET status='running'")
        f.connection.commit()
        with self.assertRaisesRegex(Blocked, 'workspace is running'):
            self.report()
        f.connection.execute("UPDATE execution_processes SET status='completed'")
        f.connection.execute("INSERT INTO turn_github_sync_incoming VALUES(?,'received')", (f.workspace.bytes,))
        f.connection.commit()
        with self.assertRaisesRegex(Blocked, 'user work has priority'):
            self.report()

    def test_current_inventory_change_or_overlap_does_not_authorize_repair(self):
        f = self.fixture
        other = f.fixture.root / 'other'
        other.mkdir()
        f.connection.execute("UPDATE repos SET name='other'")
        f.connection.commit()
        self.assertIn('current_inventory_changed', [b['code'] for b in self.report()['blockers']])
        f.connection.execute("UPDATE repos SET name='repo'")
        f.connection.execute('INSERT INTO execution_processes(id,session_id,status,completed_at,dropped,created_at) VALUES(?,?,?,?,0,?)',
                             (uuid.uuid4().bytes, f.session.bytes, 'completed', '2026-10-16T08:00:00.1+00:00', '2026-10-16T08:00:00.05+00:00'))
        f.connection.commit()
        self.assertIn('terminal_provenance_unproven', [b['code'] for b in self.report()['blockers']])

    def test_cli_failed_inspection_returns_nonzero_and_writes_only_external_report(self):
        f = self.fixture
        f.connection.execute("UPDATE execution_processes SET status='failed',exit_code=1")
        f.connection.commit()
        output = f.fixture.root / 'failed-inspection.json'
        before = self.before()
        result = subprocess.run([sys.executable, str(Path(inspect.__file__)), '--database', str(f.database),
                                 '--config', str(f.config), '--workspace', str(f.workspace), '--turn', str(f.turn),
                                 '--output', str(output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertFalse(json.loads(result.stdout)['apply_supported'])
        self.assertEqual(json.loads(output.read_text())['native_execution']['status'], 'failed')
        self.assertEqual(before, self.before())

    def test_cli_refuses_repo_or_live_ledger_output_and_retains_existing_reports(self):
        f = self.fixture
        for output in [f.fixture.repo / 'inspection.json', f.ledger.parent / 'inspection.json', f.config]:
            before = self.before()
            result = subprocess.run([sys.executable, str(Path(inspect.__file__)), '--database', str(f.database),
                                     '--config', str(f.config), '--workspace', str(f.workspace), '--turn', str(f.turn),
                                     '--output', str(output)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertEqual(before, self.before())

    def test_unknown_capture_fields_stay_unknown_and_do_not_disappear(self):
        f = self.fixture
        f.connection.execute('UPDATE execution_process_repo_states SET after_head_commit=NULL,updated_at=NULL')
        f.connection.commit()
        before = self.before()
        report = self.report()
        self.assertIsNone(report['native_states'][0]['after_head_commit'])
        self.assertIsNone(report['native_states'][0]['capture_delay_seconds'])
        self.assertFalse(report['terminal_provenance_passed'])
        self.assertIn('terminal_provenance_unproven', [b['code'] for b in report['blockers']])
        self.assertEqual(before, self.before())

    def test_explicit_failed_owner_plan_preserves_native_failure_and_unknown_coverage(self):
        f = self.fixture
        f.connection.execute("UPDATE execution_processes SET status='failed',exit_code=1")
        f.connection.commit()
        with self.assertRaisesRegex(Blocked, 'requires one exact'):
            repair.create_plan(f.database, f.config, str(f.workspace), f.plan, failed_owner=True)
        result = repair.create_plan(f.database, f.config, str(f.workspace), f.plan, str(f.turn), failed_owner=True)
        original_failure = f.connection.execute('SELECT * FROM execution_processes').fetchall()
        response = repair.apply_plan(f.plan, result['sha256'])
        self.assertFalse(response['coverage_verified'])
        self.assertEqual(f.connection.execute('SELECT * FROM execution_processes').fetchall(), original_failure)
        ledger = json.loads(f.ledger.read_text())
        self.assertEqual(ledger['repositories'], [])
        self.assertEqual(ledger['failed_owner_observation_resolution']['native_failure']['status'], 'failed')
        self.assertEqual(ledger['failed_owner_observation_resolution']['prior_observation_report'], json.loads(f.failure))
        ack = json.loads(f.connection.execute('SELECT observation_report FROM turn_github_sync').fetchone()[0])
        self.assertFalse(ack['task_success_proven'])
        self.assertFalse(ack['coverage_verified'])
        self.assertEqual(ack['native_execution']['exit_code'], 1)
        self.assertTrue(repair.apply_plan(f.plan, result['sha256'])['already_applied'])
        f.connection.execute('UPDATE execution_process_repo_states SET after_head_commit=NULL')
        f.connection.commit()
        with self.assertRaisesRegex(Blocked, 'contemporaneous'):
            repair.apply_plan(f.plan, result['sha256'])

    def test_explicit_failed_owner_still_refuses_late_unknown_or_overlapping_capture(self):
        f = self.fixture
        f.connection.execute("UPDATE execution_processes SET status='failed',exit_code=1")
        f.connection.execute("UPDATE execution_process_repo_states SET updated_at='2026-10-16T08:00:06.414+00:00'")
        f.connection.commit()
        before = self.before()
        with self.assertRaisesRegex(Blocked, 'contemporaneous'):
            repair.create_plan(f.database, f.config, str(f.workspace), f.plan, str(f.turn), failed_owner=True)
        self.assertEqual(before, self.before())
        self.assertFalse(f.plan.exists())
        f.connection.execute("UPDATE execution_process_repo_states SET updated_at='2026-10-16T08:00:00.25+00:00',after_head_commit=NULL")
        f.connection.commit()
        with self.assertRaisesRegex(Blocked, 'contemporaneous'):
            repair.create_plan(f.database, f.config, str(f.workspace), f.plan, str(f.turn), failed_owner=True)
        f.connection.execute("UPDATE execution_process_repo_states SET updated_at='2026-10-16T08:00:05.000001+00:00',after_head_commit=?", (f.b,))
        f.connection.commit()
        with self.assertRaisesRegex(Blocked, 'contemporaneous'):
            repair.create_plan(f.database, f.config, str(f.workspace), f.plan, str(f.turn), failed_owner=True)
        f.connection.execute("UPDATE execution_process_repo_states SET updated_at='2026-10-16T08:00:00.25+00:00'")
        f.connection.execute('INSERT INTO execution_processes(id,session_id,status,completed_at,dropped,created_at) VALUES(?,?,?,?,0,?)',
                             (uuid.uuid4().bytes, f.session.bytes, 'completed', '2026-10-16T08:00:00.1+00:00', '2026-10-16T08:00:00.05+00:00'))
        f.connection.commit()
        with self.assertRaisesRegex(Blocked, 'overlaps the terminal capture'):
            repair.create_plan(f.database, f.config, str(f.workspace), f.plan, str(f.turn), failed_owner=True)

    def test_failed_owner_plan_drift_never_relabels_or_clears_failure(self):
        f = self.fixture
        f.connection.execute("UPDATE execution_processes SET status='failed',exit_code=1")
        f.connection.commit()
        result = repair.create_plan(f.database, f.config, str(f.workspace), f.plan, str(f.turn), failed_owner=True)
        f.connection.execute('UPDATE execution_processes SET exit_code=2')
        f.connection.commit()
        with self.assertRaisesRegex(Blocked, 'failure evidence changed'):
            repair.apply_plan(f.plan, result['sha256'])
        self.assertEqual(f.state(), ('failed', 'blocked'))
        self.assertEqual(f.connection.execute('SELECT status,exit_code FROM execution_processes').fetchone(), ('failed', 2))
        f.connection.execute("UPDATE execution_processes SET status='completed',exit_code=0")
        f.connection.commit()
        with self.assertRaisesRegex(Blocked, 'exact terminal native failure'):
            repair.apply_plan(f.plan, result['sha256'])

    def test_failed_owner_scope_and_ack_cannot_override_ledger_or_worker_guards(self):
        f = self.fixture
        f.connection.execute("UPDATE execution_processes SET status='failed',exit_code=1")
        f.connection.commit()
        result = repair.create_plan(f.database, f.config, str(f.workspace), f.plan, str(f.turn), failed_owner=True)
        f.connection.execute('UPDATE turn_github_sync SET retry_at=0')
        f.connection.commit()
        with self.assertRaisesRegex(Blocked, 'retry is due'):
            repair.apply_plan(f.plan, result['sha256'])
        self.assertEqual(f.state(), ('failed', 'blocked'))
        f.connection.execute('UPDATE turn_github_sync SET retry_at=?', (int(time.time()) + 3600,))
        f.connection.commit()
        record = json.loads(f.ledger.read_text()); record['reason'] = 'concurrent exact-owner change'
        atomic_json(f.ledger, record)
        with self.assertRaisesRegex(Blocked, 'ledger changed'):
            repair.apply_plan(f.plan, result['sha256'])
        self.assertEqual(f.state(), ('failed', 'blocked'))
