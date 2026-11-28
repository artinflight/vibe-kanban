"""Shared upload recovery fixtures; actual B acceptance remains separate."""
import os
from pathlib import Path
import tempfile
import unittest

from catalog import Conflict
from shared_files import SharedFiles
import test_lifecycle as fixtures


class Authority:
    def check_shared_files(self, roots): pass
    def reserve_restore(self, manifest, stage): pass
    def reserve_publication(self, manifest, index, destination): pass


class SharedFilesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in ('uploads', 'controls', 'locks', 'B-fixture'):
            (self.root / name).mkdir(mode=0o700)
        self.uploads = self.root / 'uploads'
        (self.uploads / 'photo').write_bytes(b'original uploaded bytes')
        os.setxattr(self.uploads / 'photo', 'user.fixture', b'original metadata')
        self.roots = [str(self.uploads)]
        self.b = fixtures.FixtureStore(self.root / 'B-fixture')
        def describe(locator, expected):
            with self.b.recall(locator, expected) as recalled:
                return recalled.manifest
        self.b.describe = describe
        self.shared = SharedFiles(self.root / 'controls', self.root / 'locks', self.b, Authority())

    def test_verified_shared_point_reuses_bodies_and_never_retires_source(self):
        point = self.shared.ensure(self.roots)
        self.assertEqual(self.shared.ensure(self.roots), point)
        self.assertEqual(self.b.captures, 1)
        self.assertEqual((self.uploads / 'photo').read_bytes(), b'original uploaded bytes')
        self.assertEqual(os.getxattr(self.uploads / 'photo', 'user.fixture'), b'original metadata')

    def test_new_upload_creates_distinct_point_and_preserves_old_recovery(self):
        old = self.shared.ensure(self.roots)
        (self.uploads / 'new').write_bytes(b'new active workspace upload')
        newer = self.shared.ensure(self.roots)
        self.assertNotEqual(newer['manifest_sha256'], old['manifest_sha256'])
        self.assertEqual(len(list((self.root / 'controls').glob('*.accepted.json'))), 2)
        self.shared.recover_missing(old, self.roots)
        self.assertEqual((self.uploads / 'new').read_bytes(), b'new active workspace upload')

    def test_missing_file_revival_preserves_newer_uploads_and_metadata(self):
        old = self.shared.ensure(self.roots)
        (self.uploads / 'photo').unlink()  # exact disposable fixture only
        (self.uploads / 'new').write_bytes(b'later upload')
        self.shared.recover_missing(old, self.roots)
        self.assertEqual((self.uploads / 'photo').read_bytes(), b'original uploaded bytes')
        self.assertEqual(os.getxattr(self.uploads / 'photo', 'user.fixture'), b'original metadata')
        self.assertEqual((self.uploads / 'new').read_bytes(), b'later upload')
        self.assertEqual(self.b.captures, 1)

    def test_offline_or_corrupt_shared_recovery_preserves_pending_repair(self):
        old = self.shared.ensure(self.roots)
        (self.uploads / 'photo').unlink()
        self.b.offline = True
        with self.assertRaises(OSError):
            self.shared.recover_missing(old, self.roots)
        self.assertFalse((self.uploads / 'photo').exists())
        self.b.offline = False
        self.b.corrupt = True
        with self.assertRaises(ValueError):
            self.shared.recover_missing(old, self.roots)
        self.assertFalse((self.uploads / 'photo').exists())
        self.b.corrupt = False
        self.shared.recover_missing(old, self.roots)
        self.assertEqual((self.uploads / 'photo').read_bytes(), b'original uploaded bytes')
        self.assertEqual(self.b.captures, 1)

    def test_newer_shared_member_and_alias_are_never_overwritten(self):
        old = self.shared.ensure(self.roots)
        (self.uploads / 'photo').write_bytes(b'newer data')
        with self.assertRaises(ValueError):
            self.shared.recover_missing(old, self.roots)
        self.assertEqual((self.uploads / 'photo').read_bytes(), b'newer data')
        (self.uploads / 'link').symlink_to('photo')
        with self.assertRaisesRegex(Conflict, 'aliases'):
            self.shared.ensure(self.roots)

    def test_uncertain_capture_reconciles_same_shared_operation(self):
        self.b.uncertain_once = True
        with self.assertRaises(ConnectionError):
            self.shared.ensure(self.roots)
        self.shared.ensure(self.roots)
        self.assertEqual(self.b.captures, 1)
