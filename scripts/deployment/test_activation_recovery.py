"""Fault-injected terminal recovery: accepted traffic must retain its runtime,
and the original frozen usage monitor must be resumed on both cleanup paths.
"""
import ast
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
import fcntl
import os

SOURCE = Path(__file__).with_name('antigravity_activation.py')
NODES = [node for node in ast.parse(SOURCE.read_text()).body
         if isinstance(node, ast.FunctionDef) and node.name == 'recover']


class ActivationRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.lease = self.directory / 'lease'
        self.lease.touch()
        (self.directory / 'ACCEPTED.private.json').write_text('{}')
        self.ops = Mock()
        self.saved = {}
        self.resume = Mock()
        self.g = dict(D=self.directory, os=os, fcntl=fcntl, Path=Path, json=json,
                      setup=lambda: (dict(cutover_lease=str(self.lease)), self.ops, {}),
                      P=SimpleNamespace(current_variant=lambda _: 'candidate'),
                      base=SimpleNamespace(UNIT='vibe'),
                      unit=lambda _: dict(MainPID='123'), resume_cu=self.resume,
                      save=lambda name, value: self.saved.update({name: value}))
        exec(compile(ast.Module(body=NODES, type_ignores=[]), str(SOURCE), 'exec'), self.g)

    def tearDown(self):
        self.temp.cleanup()

    def test_accepted_cleanup_retains_runtime_and_resumes_original_monitor(self):
        self.g['recover']()
        self.ops.verify_public_review.assert_called_once_with()
        self.ops.resume_owned_consumers.assert_called_once_with(False)
        self.assertTrue(self.resume.called)
        self.ops.stop_variant_if_running.assert_not_called()
        self.ops.install_variant.assert_not_called()
        self.assertEqual(self.saved['RESULT.private.json']['PID'], '123')

    def test_cleanup_failure_still_resumes_monitor_without_false_success(self):
        self.ops.resume_owned_consumers.side_effect = RuntimeError('new ingress owner')
        with self.assertRaisesRegex(RuntimeError, 'new ingress owner'):
            self.g['recover']()
        self.resume.assert_called_once_with(self.ops)
        self.assertNotIn('RESULT.private.json', self.saved)
        self.ops.stop_variant_if_running.assert_not_called()

    def test_completed_controller_is_inert(self):
        (self.directory / 'RESULT.private.json').write_text('{}')
        self.g['recover']()
        self.assertFalse(self.ops.mock_calls)
        self.resume.assert_not_called()

    def test_unknown_runtime_owner_is_preserved(self):
        def changed(_):
            raise ValueError('unknown actual runtime')
        self.g['P'].current_variant = changed
        with self.assertRaisesRegex(ValueError, 'unknown actual runtime'):
            self.g['recover']()
        self.ops.stop_variant_if_running.assert_not_called()
        self.ops.install_variant.assert_not_called()
        self.assertNotIn('RESULT.private.json', self.saved)


if __name__ == '__main__':
    unittest.main()
