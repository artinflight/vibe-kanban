"""Retained tool-binding fixtures; no B transfer or combined-release acceptance."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from vk_candidate_generation import Blocked
from vk_candidate_package import build, verify, RECORDED_VERIFIERS
from vk_prep_common import digest

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
        self.assertEqual(result['candidate_modules_verified'], 7)
        self.assertEqual(result['reviewed_source_files_verified'], 8)
        self.assertFalse(result['combined_backend_binary_bound'])
        self.assertFalse(result['operational_acceptance'])
        code = ('from vk_candidate_direct_b import source_pins; '
                'from vk_candidate_scaffold import authenticate_plan, add_context; '
                'print(len(source_pins()))')
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

    def test_recorded_verifier_requires_source_and_exact_immutable_receipts(self):
        result = build(self.package, self.inventory, fixture_only=True)
        path = self.package / 'candidate-tool-binding.json'
        contract = json.loads(path.read_text())
        del contract['required_modules']['vk_candidate_owner.py']
        path.write_text(json.dumps(contract))  # This new retained legacy fixture only.
        with self.assertRaisesRegex(Blocked, 'required contracts'):
            verify(self.package)
        with self.assertRaisesRegex(Blocked, 'required contracts'):
            verify(self.package, expected_source=result['source_commit'])
        # Fixture registration represents an independently pinned old contract;
        # production registers only the exact retained 01af package receipts.
        recorded = {result['source_commit']: (digest(path), digest(self.package / 'recovery-package.json'))}
        with patch.dict(RECORDED_VERIFIERS, recorded):
            old = verify(self.package, expected_source=result['source_commit'])
            self.assertEqual(old['candidate_modules_verified'], 6)
            with self.assertRaisesRegex(Blocked, 'source differs'):
                verify(self.package, expected_source='e' * 40)
            with path.open('a') as out:
                out.write(' ')
            with self.assertRaisesRegex(Blocked, 'receipts differ'):
                verify(self.package, expected_source=result['source_commit'])


if __name__ == '__main__':
    if not os.path.ismount('/mnt/vk-storage'):
        raise SystemExit('mounted secondary SSD required')
    PARENT.mkdir(exist_ok=True)
    unittest.main(verbosity=2)
