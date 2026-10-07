"""Normal regression selection covers old hardlinks across later archive writes."""
import os
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch

import test_vk_desktop_backups as fixtures
from probe_vk_restore_hardlinks import exercise
from vk_rolling_backup import detach_restore_alias, restore_chain


class HardlinkRestore(unittest.TestCase):
    setUp = fixtures.DesktopBackups.setUp
    tearDown = fixtures.DesktopBackups.tearDown
    mirror = fixtures.DesktopBackups.mirror
    backup = fixtures.DesktopBackups.backup

    def case(self, name):
        result = exercise(self.root / name, name)
        self.assertTrue(result['correctness_passed'], result)

    def test_unchanged_links_are_preserved(self):
        self.case('unchanged')

    def test_replacing_target_does_not_modify_untouched_alias(self):
        self.case('A')

    def test_replacing_alias_does_not_modify_untouched_target(self):
        self.case('B')

    def test_explicit_same_archive_links_are_preserved(self):
        self.case('both-linked')

    def test_snapshot_replacement_detaches_old_regular_alias(self):
        a, b = self.source / 'A', self.source / 'B'
        a.write_bytes(b'original non-database'); os.link(a, b)
        first = self.backup()
        temporary = self.source / 'new.sqlite'
        with sqlite3.connect(temporary) as db:
            db.execute('CREATE TABLE evidence (value TEXT)')
            db.execute("INSERT INTO evidence VALUES ('new')")
        temporary.chmod(0o640); temporary.replace(a)
        second = self.backup(first)
        destination = self.backups / 'snapshot-restore'
        restore_chain(second, destination, desktop_only=True)
        files = destination / 'files' / str(self.source).lstrip('/')
        self.assertEqual((files / 'B').read_bytes(), b'original non-database')
        self.assertFalse(os.path.samefile(files / 'A', files / 'B'))
        self.assertEqual((files / 'A').stat().st_mode & 0o777, 0o640)
        with sqlite3.connect(files / 'A') as db:
            self.assertEqual(db.execute('SELECT value FROM evidence').fetchall(), [('new',)])

    def test_mode_change_after_detach_does_not_change_untouched_alias(self):
        a, b = self.source / 'A', self.source / 'B'
        a.write_bytes(b'old'); a.chmod(0o640); os.link(a, b)
        first = self.backup()
        temporary = self.source / 'replacement'; temporary.write_bytes(b'new')
        temporary.chmod(0o600); temporary.replace(a)
        second = self.backup(first)
        destination = self.backups / 'mode-restore'; restore_chain(second, destination, desktop_only=True)
        files = destination / 'files' / str(self.source).lstrip('/')
        self.assertEqual((files / 'A').stat().st_mode & 0o777, 0o600)
        self.assertEqual((files / 'B').stat().st_mode & 0o777, 0o640)

    def test_symlink_destination_is_rejected_without_following(self):
        original = self.source / 'original'; original.write_text('protected')
        alias = self.source / 'alias'; alias.symlink_to(original)
        with self.assertRaisesRegex(ValueError, 'symlink restore destination'):
            detach_restore_alias(alias)
        self.assertEqual(original.read_text(), 'protected')

    def test_failed_detach_leaves_both_original_names(self):
        a, b = self.source / 'A', self.source / 'B'
        a.write_bytes(b'old'); os.link(a, b)
        with patch.object(Path, 'unlink', side_effect=PermissionError('fixture denial')):
            with self.assertRaises(PermissionError):
                detach_restore_alias(a)
        self.assertEqual(a.read_bytes(), b.read_bytes())
        self.assertTrue(os.path.samefile(a, b))
