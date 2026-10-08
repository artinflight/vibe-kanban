"""Retained tool-binding fixtures; no B transfer or combined-release acceptance."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from vk_candidate_generation import Blocked
from vk_candidate_package import build, verify

PARENT = Path('/mnt/vk-storage/vk-safe-release-20261008/candidate-package-tests')


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix=self._testMethodName + '-', dir=PARENT))
        self.inventory = self.root / 'fixture-inventory.json'
        self.inventory.write_text(json.dumps({'archive_files': [], 'backup_chain_heads': [],
                                              'fixture_only': True}) + '\n')
        self.package = self.root / 'tool-package'

    def test_new_package_and_actual_packaged_review_loader(self):
        result = build(self.package, self.inventory, fixture_only=True)
        self.assertEqual(result['candidate_modules_verified'], 5)
        self.assertEqual(result['reviewed_source_files_verified'], 8)
        self.assertFalse(result['combined_backend_binary_bound'])
        self.assertFalse(result['operational_acceptance'])
        code = 'from vk_candidate_direct_b import source_pins; print(len(source_pins()))'
        output = subprocess.check_output([sys.executable, '-B', '-O', '-c', code],
                                         cwd=self.package / 'tools', text=True)
        self.assertEqual(output.strip(), '8')

    def test_changed_candidate_module_cannot_verify(self):
        build(self.package, self.inventory, fixture_only=True)
        # Only this new negative fixture is altered. No original package or
        # historical receipt is rewritten, and every fixture remains retained.
        with (self.package / 'tools/vk_candidate_generation.py').open('ab') as out:
            out.write(b'\n# owned mutation fixture\n')
        with self.assertRaisesRegex(ValueError, 'package changed'):
            verify(self.package)

    def test_empty_inventory_cannot_be_operational_package(self):
        with self.assertRaisesRegex(Blocked, 'only a tool-binding fixture'):
            build(self.package, self.inventory)
        self.assertFalse(self.package.exists())


if __name__ == '__main__':
    if not os.path.ismount('/mnt/vk-storage'):
        raise SystemExit('mounted secondary SSD required')
    PARENT.mkdir(exist_ok=True)
    unittest.main(verbosity=2)
