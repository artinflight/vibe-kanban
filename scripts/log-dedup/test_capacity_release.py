import copy
import fcntl
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import capacity_release as release


class CapacityReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.lock = self.root / 'controller.lock'
        self.lock.touch(mode=0o600)
        self.path = self.root / 'state.json'
        self.state = dict(version=1, epoch='fixture', revision=8,
                          goals={'goal': {'grant': None}}, issuedIds=['previous'],
                          foregroundUntilMs=0)
        self.write_state()
        self.calls = []
        self.records = []
        self.reply = dict(protocolVersion=1, owned=False, state=None)
        self.error = TimeoutError('Release committed but response lost')
        self.boundary = SimpleNamespace(
            config=dict(capacity_token='/never-read', capacity_lock=str(self.lock),
                        capacity_state=str(self.path), capacity_persisted_version=2),
            data={'released': None}, owner_guard=lambda: None,
            original_check=lambda: None, record=self.record,
            rpc=SimpleNamespace(request=self.rpc))

    def write_state(self, **changes):
        self.path.write_text(json.dumps(dict(self.state, version=2, **changes)))
        self.path.chmod(0o600)

    def record(self, phase):
        self.records.append((phase, copy.deepcopy(self.boundary.data)))
        if phase == 'authenticated_capacity_release_reconciled':
            with self.lock.open() as handle:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def rpc(self, origin, token, action='status', receipt=None):
        self.calls.append(action)
        if action == 'release':
            self.assertEqual(self.records[0][1]['capacity_release_intent']['state'], self.state)
            if self.error:
                raise self.error
            return dict(protocolVersion=1, owned=False, state=copy.deepcopy(self.state))
        return self.reply

    def run_release(self):
        return release.release(self.boundary, dict(protocolVersion=1, owned=True,
                                                   state=copy.deepcopy(self.state)))

    def test_lost_response_uses_null_status_and_real_lock(self):
        before = self.path.read_bytes()
        result = self.run_release()
        self.assertEqual(self.calls, ['release', 'status'])
        self.assertEqual(result['state'], self.state)
        self.assertTrue(result['reconciled_under_capacity_lock'])
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.records[-1][1]['released'], result)
        with self.lock.open() as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_normal_release_preserves_authenticated_receipt(self):
        self.error = None
        result = self.run_release()
        self.assertEqual(self.calls, ['release'])
        self.assertEqual(result, dict(protocolVersion=1, owned=False, state=self.state))

    def test_changed_epoch_revision_or_history_refused(self):
        for changes in [dict(epoch='foreign'), dict(revision=9),
                        dict(goals={}), dict(issuedIds=[]), dict(foregroundUntilMs=1)]:
            with self.subTest(changes=changes):
                self.boundary.data = {'released': None}
                self.write_state(**changes)
                with self.assertRaisesRegex(ValueError, 'history changed'):
                    self.run_release()
                self.assertIsNone(self.boundary.data['released'])

    def test_foreign_or_unresolved_owner_preserved(self):
        self.reply = dict(protocolVersion=1, owned=True, state=self.state)
        with self.assertRaisesRegex(ValueError, 'unresolved or foreign'):
            self.run_release()
        self.assertIsNone(self.boundary.data['released'])
        self.assertIsNotNone(self.boundary.data['capacity_release_intent'])

    def test_real_competing_lock_refused(self):
        with self.lock.open() as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                self.run_release()
        self.assertIsNone(self.boundary.data['released'])

    def test_restart_reconciles_durable_intent_without_replaying_rpc(self):
        self.reply = dict(protocolVersion=1, owned=True, state=self.state)
        with self.assertRaises(ValueError):
            self.run_release()
        saved = json.loads(json.dumps(self.records[0][1]))
        self.boundary.data = saved
        self.reply = dict(protocolVersion=1, owned=False, state=None)
        result = release.reconcile(self.boundary)
        self.assertEqual(result['state'], self.state)
        self.assertEqual(self.calls.count('release'), 1)

    def test_replaced_lock_refused(self):
        self.reply = dict(protocolVersion=1, owned=True, state=self.state)
        with self.assertRaises(ValueError):
            self.run_release()
        self.lock.rename(self.root / 'old.lock')
        self.lock.touch(mode=0o600)
        self.reply = dict(protocolVersion=1, owned=False, state=None)
        with self.assertRaisesRegex(ValueError, 'lock changed'):
            release.reconcile(self.boundary)

    def test_symlink_state_refused(self):
        self.path.rename(self.root / 'real-state.json')
        self.path.symlink_to(self.root / 'real-state.json')
        with self.assertRaisesRegex(ValueError, 'Literal capacity'):
            self.run_release()

    def test_pending_grants_refused_before_rpc(self):
        self.state['goals']['goal']['grant'] = {'id': 'active'}
        with self.assertRaisesRegex(ValueError, 'drained'):
            self.run_release()
        self.assertEqual(self.calls, [])

    def test_existing_intent_never_replayed(self):
        self.run_release()
        with self.assertRaisesRegex(ValueError, 'never replayed'):
            self.run_release()
        self.assertEqual(self.calls.count('release'), 1)

    def test_unknown_intent_never_inferred(self):
        with self.assertRaisesRegex(ValueError, 'No durable'):
            release.reconcile(self.boundary)
        self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main()
