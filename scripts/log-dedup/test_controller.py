from pathlib import Path
from contextlib import contextmanager
import argparse
import json
from types import SimpleNamespace
from unittest.mock import patch
import test_reclaim as fixture_module
import tempfile
import unittest

import controller
import log_dedup as logs


class ControllerTests(unittest.TestCase):
    def test_command_plumbing_installs_and_restores_only_under_admitted_context(self):
        fixture = fixture_module.ReclaimTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        plan_path = fixture.base / 'plan.json'
        plan_path.write_text(json.dumps(fixture.plan))
        config_path = fixture.base / 'config.json'
        config_path.write_text('{}')
        @contextmanager
        def admit(config, plan, rollback=False):
            with fixture.fence.held():
                yield {'writer_fence': fixture.fence, 'recovery': fixture.store,
                       'reader_guard': fixture.reader, 'reserve_bytes': 0}
        args = argparse.Namespace(plan=plan_path, config=config_path,
                                  adapter=fixture.base / 'owner.py', adapter_sha256='0' * 64,
                                  archive=fixture.archive, journal=fixture.journal, rollback=False)
        with patch('controller.load_adapter', return_value=SimpleNamespace(admit=admit)):
            self.assertEqual(controller.run(args)['outcome'], 'installed')
            args.rollback = True
            self.assertEqual(controller.run(args)['outcome'], 'restored')
        fixture.assert_original()

    def test_unknown_hash_is_rejected_before_any_adapter_code_executes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / 'executed'
            source = root / 'adapter.py'
            source.write_text('from pathlib import Path\nPath(' + repr(str(marker)) + ').touch()\n')
            source.chmod(0o600)
            with self.assertRaisesRegex(ValueError, 'source hash mismatch'):
                controller.load_adapter(source, '0' * 64)
            self.assertFalse(marker.exists())

    def test_protocol_and_owner_writability_are_required(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'adapter.py'
            source.write_text('PROTOCOL = 0\nadmit = None\n')
            source.chmod(0o600)
            with self.assertRaisesRegex(ValueError, 'protocol'):
                controller.load_adapter(source, logs.sha(source.read_bytes()))
            source.chmod(0o666)
            with self.assertRaisesRegex(ValueError, 'owner adapter'):
                controller.load_adapter(source, logs.sha(source.read_bytes()))


if __name__ == '__main__':
    unittest.main()
