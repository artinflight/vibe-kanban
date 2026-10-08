"""Private bounded fixtures: direct-stream delivery, rejection and metadata."""
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_vk_rolling_backup as fixtures
from vk_archive_stream import RECEIVER, StreamingArchive, packet, response
from vk_archive_store import Archive, reference
from vk_direct_capture import capture
from vk_prep_common import digest


class DirectStreamTests(unittest.TestCase):
    setUp = fixtures.BackupTests.setUp
    tearDown = fixtures.BackupTests.tearDown
    mirror = fixtures.BackupTests.mirror
    backup = fixtures.BackupTests.backup

    def descriptor(self, produce=None, name='test.tar.zst', maximum=16*1024**2):
        return StreamingArchive(self.backups, name, produce or (lambda out: out.write(b'fixture'*4096)), maximum)

    def deliver(self, archive, code=RECEIVER):
        return archive.deliver(self.desktop.directory, [sys.executable, '-c', code])

    def no_local_payload(self):
        self.assertFalse(list(self.backups.rglob('*.tar.zst')))
        self.assertFalse(list(self.backups.rglob('*.sqlite')))
        self.assertFalse(list(self.backups.rglob('*.partial-*')))

    def test_success_full_readback_and_no_local_payload_accumulation(self):
        (self.source/'random.bin').write_bytes(os.urandom(2*1024**2))
        first = capture(self.plan, self.backups, self.journal.report, self.mirror, publish=self.mirror)
        second = capture(self.plan, self.backups, self.journal.report, self.mirror, first, self.mirror)
        for result in (first, second):
            self.assertTrue(result['receipt']['direct_stream'])
            self.assertEqual(result['local_archive_bytes'], 0)
            self.assertEqual(result['local_snapshot_bytes'], 0)
            Archive(reference(result)).verify()
        self.no_local_payload()
        self.assertLess(sum(p.stat().st_size for p in self.backups.rglob('*') if p.is_file()), 128*1024)

    def test_unavailable_b_never_starts_archive_or_falls_back(self):
        calls = []
        archive = self.descriptor(lambda out: calls.append(True))
        with self.assertRaises((ValueError, BrokenPipeError)):
            archive.deliver(self.desktop.directory, [sys.executable, '-c', 'raise SystemExit(1)'])
        self.assertEqual(calls, [])
        self.no_local_payload()

    def test_interrupted_producer_preserves_previous_good_and_partial_evidence(self):
        good = self.deliver(self.descriptor(name='good.tar.zst'))
        remote = Path(self.desktop.directory)/good['name']
        def broken(out):
            out.write(os.urandom(2*1024**2));out.flush()
            raise RuntimeError('injected source interruption')
        with self.assertRaisesRegex(RuntimeError, 'source interruption'):
            self.deliver(self.descriptor(broken, name='broken.tar.zst'))
        self.assertEqual(digest(remote), good['sha256'])
        self.assertFalse((remote.parent/'broken.tar.zst').exists())
        self.assertEqual(len(list(remote.parent.glob('broken.tar.zst.partial-*'))), 1)
        self.no_local_payload()

    def test_interrupted_receiver_does_not_accept_archive(self):
        code = RECEIVER.replace("if n==0:break", "if n==0:break\n        raise ValueError('injected receiver interruption')")
        with self.assertRaises((ValueError, BrokenPipeError)):
            self.deliver(self.descriptor(lambda out: out.write(os.urandom(3*1024**2))), code)
        self.assertFalse((Path(self.desktop.directory)/'test.tar.zst').exists())
        self.no_local_payload()

    def test_wrong_end_to_end_checksum_leaves_no_final_archive(self):
        remote = subprocess.Popen([sys.executable, '-c', RECEIVER], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            packet(remote.stdin, {'directory':self.desktop.directory, 'name':'bad.tar.zst', 'limit':1024})
            self.assertEqual(response(remote), {'ready':True})
            remote.stdin.write(struct.pack('!I', 4)+b'data'+struct.pack('!I',0))
            packet(remote.stdin, {'bytes':4, 'sha256':'0'*64})
            remote.stdin.close()
            self.assertNotEqual(remote.wait(timeout=10), 0)
            self.assertFalse((Path(self.desktop.directory)/'bad.tar.zst').exists())
        finally:
            if remote.poll() is None: remote.kill()
            remote.wait();remote.stdout.close()

    def test_remote_readback_failure_does_not_publish(self):
        code = RECEIVER.replace("verify.hexdigest()!=expected['sha256']", "True")
        with self.assertRaises(ValueError):
            self.deliver(self.descriptor(), code)
        self.assertFalse((Path(self.desktop.directory)/'test.tar.zst').exists())

    def test_receiver_receipt_identity_failure_is_rejected(self):
        code = RECEIVER.replace("'direct_stream':True", "'direct_stream':False")
        with self.assertRaisesRegex(ValueError, 'receipt'):
            self.deliver(self.descriptor(), code)

    def test_existing_good_archive_cannot_be_overwritten(self):
        receipt = self.deliver(self.descriptor())
        with self.assertRaises((ValueError, BrokenPipeError)):
            self.deliver(self.descriptor(lambda out: out.write(b'different')))
        self.assertEqual(digest(Path(self.desktop.directory)/receipt['name']), receipt['sha256'])

    def test_stream_size_bound_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'bound'):
            self.deliver(self.descriptor(lambda out: out.write(os.urandom(1024**2)), maximum=4096))
        self.assertFalse((Path(self.desktop.directory)/'test.tar.zst').exists())
        self.no_local_payload()

    def test_memory_bound_does_not_stage_sqlite_or_advance_head(self):
        first = self.backup()
        head = (self.backups/'latest-result.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'memory bound'):
            capture(self.plan, self.backups, self.journal.report, self.mirror, max_snapshot_bytes=1)
        self.assertEqual((self.backups/'latest-result.json').read_bytes(), head)
        self.assertTrue((Path(self.desktop.directory)/first['archive']).exists())
        self.no_local_payload()

    def test_remote_validation_failure_preserves_head_and_previous_backup(self):
        first = self.backup()
        head = (self.backups/'latest-result.json').read_bytes()
        with patch('vk_direct_capture.verify_remote_snapshots', side_effect=ValueError('injected validation')):
            with self.assertRaisesRegex(ValueError, 'validation'):
                self.backup(first)
        self.assertEqual((self.backups/'latest-result.json').read_bytes(), head)
        Archive(reference(first)).verify()
        self.no_local_payload()

    def test_metadata_bound_failure_does_not_publish_head(self):
        with patch('vk_direct_capture.MAX_CAPTURE_METADATA_BYTES', 4096):
            with self.assertRaisesRegex(ValueError, 'metadata'):
                self.backup()
        self.assertFalse((self.backups/'latest-result.json').exists())
        self.no_local_payload()

    def test_linux_metadata_and_full_non_database_scope_are_in_archive(self):
        os.setxattr(self.attachment, 'user.backup-test', b'preserve me')
        self.attachment.chmod(0o640)
        (self.source/'symlink').symlink_to(self.attachment.name)
        os.link(self.attachment, self.source/'hardlink')
        result = self.backup()
        members = {}
        with Archive(reference(result)).contents() as archive:
            for member in archive:
                members[member.name] = member
                if member.isfile(): archive.extractfile(member).read()
        prefix = str(self.source).lstrip('/')+'/'
        row = members[prefix+self.attachment.name]
        st = self.attachment.stat()
        self.assertEqual((row.mode,row.uid,row.gid), (0o640,st.st_uid,st.st_gid))
        self.assertAlmostEqual(row.mtime, st.st_mtime, places=5)
        self.assertEqual(row.pax_headers['SCHILY.xattr.user.backup-test'], 'preserve me')
        self.assertTrue(members[prefix+'symlink'].issym())
        self.assertTrue(members[prefix+'hardlink'].islnk())
        for path in (self.note,self.history,self.attachment): self.assertIn(prefix+path.name,members)
        snapshot = members['payload/'+result['sqlite_snapshots'][str(self.database)]['path']]
        self.assertEqual((snapshot.uid,snapshot.gid), (self.database.stat().st_uid,self.database.stat().st_gid))

    def test_no_implicit_path_adapter_to_legacy_local_copy(self):
        with self.assertRaises(TypeError):
            os.fspath(self.descriptor())

    def test_packaged_mirror_adapter_accepts_stream_without_converting_to_path(self):
        from vk_rolling_backup import mirror_desktop
        with patch('vk_archive_stream.receiver_command', return_value=[sys.executable, '-c', RECEIVER]):
            result = capture(self.plan, self.backups, self.journal.report,
                lambda archive: mirror_desktop(archive, self.desktop.directory))
        self.assertTrue(result['receipt']['direct_stream'])
        self.no_local_payload()

    def test_capture_never_even_opens_a_local_payload_path(self):
        original = Path.open
        attempts = []
        def checked(path, mode='r', *args, **kwargs):
            if path.is_relative_to(self.backups) and (path.suffix == '.sqlite' or path.name.endswith('.tar.zst')):
                attempts.append(str(path))
                raise AssertionError('Local payload file opened')
            return original(path, mode, *args, **kwargs)
        with patch.object(Path, 'open', checked):
            self.backup()
        self.assertEqual(attempts, [])

    def test_invalid_destinations_rejected_before_subprocess(self):
        for directory in ('/tmp/backups', 'C:/backups', 'B:/vk-backups/../bad'):
            with self.subTest(directory=directory), patch('subprocess.Popen') as called:
                with self.assertRaises(ValueError):self.descriptor().deliver(directory, [])
                called.assert_not_called()


if __name__ == '__main__':unittest.main()
