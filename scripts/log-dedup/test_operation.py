from contextlib import contextmanager
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

import log_dedup as logs
import operation
import test_reclaim as fixtures


class OperationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ReclaimTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.events = []
        self.failure = None
        self.recovery_called = False
        self.config = self.fixture.base / 'config.json'
        self.config.write_text('{}')
        self.manifest = {'activation_inputs': {'path': '/sealed/inputs', 'sha256': 'a' * 64}}
        def activate(*args):
            self.assertIs(args[-2], self.fixture.fence)
            self.assertIs(args[-1], self.fixture.store)
            self.fixture.fence.check()
            self.events.append('activate')
        def seal(*args):
            self.events.append('seal')
            return {'config_path': str(self.config), 'config_sha256': logs.sha(b'{}')}
        def recover(*args):
            # The old software must never be selected while even one manifest
            # remains; real owner also repeats the full original hash check.
            self.fixture.assert_original()
            self.fixture.fence.check()
            self.recovery_called = True
        self.actions = SimpleNamespace(activate=activate, seal_controller_inputs=seal,
                                       recover_before_conversion=recover)
        @contextmanager
        def admit(config, plan, fence, recovery):
            self.events.append('admit')
            self.assertIs(fence, self.fixture.fence)
            self.assertIs(recovery, self.fixture.store)
            yield {'writer_fence': fence, 'recovery': recovery,
                   'reader_guard': self.fixture.reader, 'reserve_bytes': 0}
            self.fixture.fence.check()
        self.adapter = SimpleNamespace(admit_held=admit, owned_bytes=lambda path, sha: Path(path).read_bytes())

    def record(self, phase, detail):
        self.events.append(phase)
        if phase == self.failure:
            self.failure = None
            raise RuntimeError('injected completed-publication failure')

    def run_operation(self):
        return operation.convert_held(assembly=(self.adapter, self.actions), manifest=self.manifest,
            operation='12345678-0000-0000-0000-000000000000', plan=self.fixture.plan,
            archive=self.fixture.archive, journal=self.fixture.journal,
            fence=self.fixture.fence, recovery=self.fixture.store, record=self.record)

    def test_success_uses_same_held_fence_and_store_and_keeps_custody(self):
        with self.fixture.fence.held():
            result = self.run_operation()
            self.assertEqual(result['outcome'], 'installed')
            self.fixture.fence.check()
            for relative in self.fixture.paths:
                self.assertTrue((self.fixture.source / relative).read_bytes().startswith(logs.MAGIC))
        self.assertFalse(self.recovery_called)
        self.assertEqual(self.events[:3], ['activate', 'actual_reader_activation_complete', 'seal'])
        self.assertEqual(self.events.count('manifest_readback_complete'), 2)

    def test_partial_publication_recovers_raw_before_old_software(self):
        self.failure = 'manifest_readback_complete'
        with self.fixture.fence.held():
            with self.assertRaisesRegex(RuntimeError, 'injected'):
                self.run_operation()
        self.fixture.assert_original()
        self.assertTrue(self.recovery_called)
        self.assertLess(self.events.index('exact_raw_recovery_complete'), self.events.index('old_readers_recovered_frozen'))
        state = json.loads((self.fixture.journal / 'state.json').read_bytes())
        self.assertEqual(state['outcome'], 'restored')

    def test_lost_reader_guard_prevents_rollback_or_old_reader_selection(self):
        def record(phase, detail):
            self.events.append(phase)
            if phase == 'manifest_readback_complete':
                self.fixture.reader_ready = False
        self.record = record
        with self.fixture.fence.held():
            with self.assertRaises(ValueError):
                self.run_operation()
        self.assertFalse(self.recovery_called)
        self.assertTrue(any((self.fixture.source / p).read_bytes().startswith(logs.MAGIC)
                            for p in self.fixture.paths))
        self.assertFalse(json.loads((self.fixture.journal / 'state.json').read_bytes())['complete'])

    def test_pre_activation_failure_does_not_create_conversion_journal(self):
        def reject(*args):
            raise ValueError('owner changed')
        self.actions.activate = reject
        with self.fixture.fence.held():
            with self.assertRaisesRegex(ValueError, 'owner changed'):
                self.run_operation()
        self.fixture.assert_original()
        self.assertFalse(self.fixture.journal.exists())

    def test_sealed_loader_rejects_changed_source_before_execution(self):
        source = self.fixture.base / 'sealed.py'
        source.write_text('raise AssertionError("must not execute")\n')
        source.chmod(0o600)
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            operation.load_module('untrusted', {'path': str(source), 'sha256': '0' * 64})


if __name__ == '__main__':
    unittest.main()
