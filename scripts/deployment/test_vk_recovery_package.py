"""Portable metadata survives absent legacy local archive and descriptor paths."""
import json
from pathlib import Path
import unittest

import test_vk_desktop_backups as fixtures
from vk_archive_store import Archive, LOCATORS, reference
from vk_recovery_package import build, verify
from vk_rolling_backup import restore_chain


class RecoveryPackage(unittest.TestCase):
    setUp = fixtures.DesktopBackups.setUp
    tearDown = fixtures.DesktopBackups.tearDown
    mirror = fixtures.DesktopBackups.mirror
    backup = fixtures.DesktopBackups.backup
    remove_own_archive = fixtures.DesktopBackups.remove_own_archive

    def package(self):
        result = self.backup()
        folder = Path(result['folder'])
        receipt = folder / 'result.json'
        inventory = {'archive_files': [{'local': str(folder / result['archive']),
            'receipt': str(receipt), 'remote': self.directory + '/' + result['archive'],
            'sha256': result['receipt']['sha256'], 'bytes': result['receipt']['bytes']}],
            'backup_chain_heads': [{'descriptor': str(receipt)}]}
        path = self.root / 'inventory.json'; path.write_text(json.dumps(inventory))
        package = self.root / 'package'
        self.assertTrue(build(package, path, require_clean=False)['passed'])
        return package, result

    def test_portable_locator_works_without_original_descriptor_or_archive(self):
        package, first = self.package()
        self.remove_own_archive(first)
        for name in ['result.json', first['archive'] + '.result.json']:
            (Path(first['folder']) / name).unlink()
        LOCATORS.clear()
        verify(package)
        legacy = {key: reference(first)[key] for key in ['folder', 'archive', 'sha256']}
        self.assertEqual(Archive(legacy, desktop_only=True).manifest()['parent'], None)
        self.assertTrue(restore_chain(first, self.backups / 'restore', desktop_only=True)['passed'])

    def test_changed_descriptor_is_rejected(self):
        package, _ = self.package()
        (package / 'descriptors/0.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'Recovery package changed'):
            verify(package)

    def test_missing_resolver_is_rejected(self):
        package, _ = self.package()
        proof = json.loads((package / 'recovery-package.json').read_text())
        del proof['sha256']['tools/vk_archive_store.py']
        (package / 'recovery-package.json').write_text(json.dumps(proof))
        with self.assertRaisesRegex(ValueError, 'Missing required recovery tool'):
            verify(package)

    def test_existing_package_cannot_be_rewritten(self):
        package, _ = self.package()
        with self.assertRaisesRegex(ValueError, 'new recovery package'):
            build(package, self.root / 'inventory.json', require_clean=False)
