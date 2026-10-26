"""Preparation must preserve live inputs and never imply activation readiness."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import prepare_approval_notifications as package


class ApprovalPackageTests(unittest.TestCase):
    def fixture(self, temp):
        root = Path(temp)
        connector, notifier = root/'live-connector', root/'live-notifier'
        connector.mkdir()
        notifier.mkdir()
        engine, reader = b'synthetic engine\n', b'synthetic reader\n'
        (connector/'approval_event_store.py').write_bytes(engine)
        (connector/'approval_notifications.py').write_bytes(reader)
        (notifier/'events.py').write_bytes(engine)
        baseline = {'approval_event_store.py': hashlib.sha256(engine).hexdigest(),
                    'approval_notifications.py': hashlib.sha256(reader).hexdigest()}
        return connector, notifier, root/'output', baseline

    def invoke(self, connector, notifier, output, baseline, dirty=False):
        def git(args, **_kwargs):
            if 'status' in args:
                return ' M source.py\n' if dirty else ''
            return ('b'*40 if 'HEAD^{tree}' in args else 'a'*40)+'\n'
        with mock.patch.object(package, 'BASELINE', baseline), \
             mock.patch.object(package, 'require_storage') as storage, \
             mock.patch.object(package.subprocess, 'check_output', side_effect=git), \
             mock.patch('sys.argv', ['prepare', '--connector-source', str(connector), '--notifier-source', str(notifier), '--output', str(output)]), \
             contextlib.redirect_stdout(io.StringIO()):
            package.main()
            storage.assert_called_once_with(output.resolve())

    def test_stage_and_rollback_are_hash_bound_without_touching_live_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            connector, notifier, output, baseline = self.fixture(temp)
            before = {p: p.read_bytes() for folder in [connector, notifier] for p in folder.iterdir()}
            self.invoke(connector, notifier, output, baseline)
            self.assertEqual(before, {p: p.read_bytes() for p in before})
            manifest = json.loads((output/'manifest.json').read_text())
            self.assertFalse(manifest['cutover_ready'])
            self.assertIsNone(manifest['backend_artifact'])
            self.assertEqual(manifest['source_commit'], 'a'*40)
            self.assertEqual(manifest['source_tree'], 'b'*40)
            self.assertEqual(len(manifest['files']), 5)
            self.assertEqual(len(manifest['rollback']), 3)
            for record in manifest['rollback']:
                p = output/'rollback'/record['component']/record['file']
                self.assertEqual(package.digest(p), record['sha256'])
                self.assertIn(p.read_bytes(), before.values())
            for p in output.rglob('*'):
                if p.is_file():
                    self.assertEqual(p.stat().st_mode & 0o777, 0o600)
            self.assertFalse((connector/'approval_preview.py').exists())
            self.assertFalse((notifier/'approval_preview.py').exists())
            with self.assertRaises(ValueError):
                self.invoke(connector, notifier, output, baseline)

    def test_changed_baseline_and_dirty_source_refuse_before_creating_output(self):
        with tempfile.TemporaryDirectory() as temp:
            connector, notifier, output, baseline = self.fixture(temp)
            with self.assertRaises(ValueError):
                self.invoke(connector, notifier, output, baseline, dirty=True)
            self.assertFalse(output.exists())
            (notifier/'events.py').write_text('changed by another owner')
            with self.assertRaises(ValueError):
                self.invoke(connector, notifier, output, baseline)
            self.assertFalse(output.exists())

    def test_unmounted_or_system_disk_output_is_refused(self):
        with mock.patch.object(package.os.path, 'ismount', return_value=False):
            with self.assertRaises(ValueError):
                package.require_storage(Path('/mnt/vk-storage/task'))
        with mock.patch.object(package.os.path, 'ismount', return_value=True):
            with self.assertRaises(ValueError):
                package.require_storage(Path('/tmp/task'))
