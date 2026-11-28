"""Finite engine recovery through actual SQLite, kernel custody and file IO.

The existing lifecycle fixture's B transport and host authority remain fixtures;
this is not a substitute for the combined deployment/normal B acceptance.
"""
import unittest

from catalog import Conflict
from controller import Controller
from custody import Custody
import test_lifecycle as fixtures


class ControllerTests(unittest.TestCase):
    def setUp(self):
        f = fixtures.LifecycleTests(methodName='test_real_move_restore_preserves_history_code_empty_symlink_and_exact_input')
        f.setUp()
        f.custody.close()
        self.addCleanup(f.doCleanups)
        self.f = f
        self.action = None
        self.failed_dependency = False
        self.prepared = 0
        def begin(workspace, action):
            self.assertEqual(workspace, f.w)
            self.action = action
        def plan(workspace):
            self.prepared += 1
            return dict(roots=f.authority.roots, fixture_only=True)
        def complete_restore(workspace, manifest):
            if self.failed_dependency:
                raise Conflict('fixture shared dependency unavailable')
        f.authority.begin = begin
        f.authority.plan = plan
        f.authority.finish = lambda *_: None
        f.authority.complete_restore = complete_restore

    def run_action(self, action, event=lambda *_: None):
        f = self.f
        with Custody(f.root / 'locks', f.w, exclusive=True) as custody:
            return Controller(f.c, custody, f.b, f.authority, f.root / 'stage', event).run(action)

    def test_archive_repeat_and_revival_do_not_duplicate_capture_or_dispatch(self):
        result = self.run_action('archive')
        self.assertEqual(result['phase'], 'cold')
        operation = result['operation_id']
        self.assertEqual(self.run_action('archive')['operation_id'], operation)
        self.assertEqual(self.prepared, 1)
        self.assertEqual(self.f.b.captures, 1)
        self.assertEqual(self.run_action('ensure')['phase'], 'active')
        self.assertEqual(self.run_action('ensure')['phase'], 'active')
        self.assertEqual((self.f.root / 'history/log').read_bytes(), b'exact log\n' * 70)

    def test_lost_capture_receipt_reconciles_same_durable_operation(self):
        self.f.b.uncertain_once = True
        with self.assertRaises(ConnectionError):
            self.run_action('archive')
        operation = self.f.c.state(self.f.w)['operation_id']
        result = self.run_action('archive')
        self.assertEqual(result['operation_id'], operation)
        self.assertEqual(self.prepared, 1)
        self.assertEqual(self.f.b.captures, 1)

    def test_message_after_verification_restores_before_any_new_archival(self):
        def crash(phase, _):
            if phase == 'root_retired':
                raise RuntimeError('fixture process loss')
        with self.assertRaises(RuntimeError):
            self.run_action('archive', crash)
        self.f.c.db.execute('UPDATE workspaces SET archived=0 WHERE id=?', (bytes.fromhex(self.f.w.replace('-', '')),))
        with self.assertRaises(Conflict):
            self.run_action('archive')
        self.assertEqual(self.run_action('ensure')['phase'], 'active')
        self.assertTrue((self.f.root / 'history/log').exists())

    def test_shared_dependency_failure_keeps_restored_input_unready(self):
        self.run_action('archive')
        self.f.retain()
        self.failed_dependency = True
        with self.assertRaisesRegex(Conflict, 'dependency'):
            self.run_action('ensure')
        self.assertEqual(self.f.c.state(self.f.w)['phase'], 'restoring')
        self.assertEqual(self.f.c.db.execute('SELECT state FROM workspace_archive_inputs').fetchone()[0], 'waiting_restore')
        self.assertTrue((self.f.root / 'history/log').exists())
        self.failed_dependency = False
        self.assertEqual(self.run_action('ensure')['phase'], 'active')

    def test_second_physical_owner_cannot_enter_held_workspace(self):
        with Custody(self.f.root / 'locks', self.f.w, exclusive=False):
            with self.assertRaisesRegex(RuntimeError, 'in use'):
                self.run_action('archive')
        self.assertEqual(self.f.b.captures, 0)

    def test_changed_generation_does_not_relabel_a_previous_cold_point(self):
        self.run_action('archive')
        self.f.c.db.execute('UPDATE workspace_archive_requests SET request_version=request_version+1')
        with self.assertRaisesRegex(Conflict, 'generation'):
            self.run_action('archive')
        self.assertEqual(self.f.b.captures, 1)
