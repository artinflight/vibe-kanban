"""Actual filesystem/metadata and process-lock tests in disposable fixtures."""
import contextlib
import copy
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid

import custody
import payloads


class PayloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'workspace'
        self.source.mkdir(mode=0o750)
        (self.source / 'nested').mkdir()
        (self.source / 'nested/body').write_bytes(b'original history\n' * 100)
        (self.source / 'empty').write_bytes(b'')
        (self.source / 'link').symlink_to('nested/body')
        os.chmod(self.source / 'nested/body', 0o640)
        os.setxattr(self.source / 'nested/body', 'user.archive-proof', b'exact metadata')
        os.utime(self.source / 'nested/body', ns=(1234567890000000000, 1234567891234567890))
        self.manifest = payloads.snapshot([self.source])
        self.bodies = {(r['root'], r['relative']): (self.source / r['relative']).read_bytes()
                       for r in self.manifest['entries'] if r['kind'] == 'file'}

    @contextlib.contextmanager
    def body(self, row):
        yield io.BytesIO(self.bodies[(row['root'], row['relative'])])

    def test_independent_restore_preserves_bytes_links_empty_files_and_linux_metadata(self):
        roots = payloads.restore(self.manifest, self.root / 'restored', self.body)
        payloads.verify(self.manifest, roots)
        self.assertEqual((roots[0] / 'link').readlink(), Path('nested/body'))
        self.assertEqual(os.getxattr(roots[0] / 'nested/body', 'user.archive-proof'), b'exact metadata')
        self.assertEqual((roots[0] / 'nested/body').stat().st_mtime_ns, 1234567891234567890)
        self.assertEqual((roots[0] / 'empty').stat().st_size, 0)
        self.assertEqual((self.source / 'nested/body').read_bytes(), self.bodies[(0, 'nested/body')])

    def test_changed_body_directory_and_metadata_all_reject_source_retirement(self):
        for change in ('body', 'entry', 'xattr'):
            with self.subTest(change=change):
                old = payloads.snapshot([self.source])
                if change == 'body': (self.source / 'nested/body').write_bytes(b'new live work')
                elif change == 'entry': (self.source / 'new').write_text('new input')
                else: os.setxattr(self.source / 'nested/body', 'user.archive-proof', b'new metadata')
                with self.assertRaises(ValueError): payloads.verify(old, versions=True)
        self.assertEqual((self.source / 'nested/body').read_bytes(), b'new live work')
        self.assertEqual((self.source / 'new').read_text(), 'new input')

    def test_corrupt_truncated_and_overlong_recovery_cannot_publish(self):
        for n, bad in enumerate((b'corrupt', b'', b'excess' * 1000)):
            @contextlib.contextmanager
            def corrupt(row):
                yield io.BytesIO(bad if row['relative'] == 'nested/body' else self.bodies[(0, row['relative'])])
            with self.assertRaises(ValueError):
                payloads.restore(self.manifest, self.root / f'partial-{n}', corrupt)
            self.assertTrue((self.root / f'partial-{n}').is_dir())
        payloads.verify(self.manifest, versions=True)

    def test_interrupted_recovery_preserves_partial_and_original_and_never_reuses_it(self):
        calls = 0
        def interrupted():
            nonlocal calls
            calls += 1
            if calls == 4: raise InterruptedError('fixture interruption')
        destination = self.root / 'partial'
        with self.assertRaises(InterruptedError):
            payloads.restore(self.manifest, destination, self.body, guard=interrupted)
        with self.assertRaises(FileExistsError):
            payloads.restore(self.manifest, destination, self.body)
        payloads.verify(self.manifest, versions=True)

    def test_malicious_paths_and_symlink_parents_are_not_extracted(self):
        for relative in ('../escaped', '/absolute', 'nested/../../escaped', 'link/child'):
            manifest = copy.deepcopy(self.manifest)
            row = next(r for r in manifest['entries'] if r['relative'] == 'nested/body')
            row['relative'] = relative
            with self.assertRaises(ValueError): payloads.restore(manifest, self.root / 'bad', self.body)
            self.assertFalse((self.root / 'bad').exists())
        alias = self.root / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError): payloads.restore(self.manifest, alias / 'escape', self.body)

    def test_aliases_hardlinks_and_special_files_are_protected(self):
        hard = self.root / 'shared-body'
        os.link(self.source / 'nested/body', hard)
        with self.assertRaises(ValueError): payloads.snapshot([self.source])
        hard.unlink()
        os.mkfifo(self.source / 'pipe')
        with self.assertRaises(ValueError): payloads.snapshot([self.source])
        (self.source / 'pipe').unlink()
        with self.assertRaises(ValueError): payloads.snapshot([self.source, self.source / 'nested'])
        alias = self.root / 'alias'
        alias.symlink_to(self.source, target_is_directory=True)
        with self.assertRaises(ValueError): payloads.snapshot([alias])

    def test_source_changed_while_reading_is_detected(self):
        path = self.source / 'nested/body'
        before = payloads.signature(path.stat())
        changed = False
        def mutate():
            nonlocal changed
            if not changed:
                changed = True
                path.write_bytes(b'replaced while reading')
        with self.assertRaises(ValueError): list(payloads.read_file(path, before, mutate))
        self.assertEqual(path.read_bytes(), b'replaced while reading')

    def test_atomic_publication_never_replaces_even_an_empty_directory(self):
        destination = self.root / 'existing'
        destination.mkdir()
        inode = destination.stat().st_ino
        with self.assertRaises(FileExistsError): payloads.rename_new(self.source, destination)
        self.assertEqual(destination.stat().st_ino, inode)
        self.assertTrue(self.source.exists())
        new = self.root / 'moved'
        payloads.rename_new(self.source, new)
        payloads.verify(self.manifest, [new])


class CustodyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = str(uuid.uuid4())

    def test_shared_readers_prevent_only_their_workspace_retirement(self):
        with custody.Custody(self.root, self.workspace, exclusive=False) as reader:
            with custody.Custody(self.root, self.workspace, exclusive=False):
                with self.assertRaises(custody.Busy): custody.Custody(self.root, self.workspace, exclusive=True)
            with custody.Custody(self.root, str(uuid.uuid4()), exclusive=True): reader.check()
        inode = (self.root / (self.workspace + '.lock')).stat().st_ino
        with custody.Custody(self.root, self.workspace, exclusive=True):
            with self.assertRaises(custody.Busy): custody.Custody(self.root, self.workspace, exclusive=False)
        self.assertEqual((self.root / (self.workspace + '.lock')).stat().st_ino, inode)

    def test_another_process_obeys_the_same_lock_protocol(self):
        code = """import sys
from custody import Custody, Busy
try:
 with Custody(sys.argv[1], sys.argv[2], exclusive=True): print('acquired')
except Busy: print('busy')
"""
        def child():
            return subprocess.check_output([sys.executable, '-c', code, str(self.root), self.workspace],
                                           cwd=Path(__file__).parent, text=True).strip()
        with custody.Custody(self.root, self.workspace, exclusive=False): self.assertEqual(child(), 'busy')
        self.assertEqual(child(), 'acquired')

    def test_lock_alias_and_inode_replacement_refused_without_deleting_evidence(self):
        lock = self.root / (self.workspace + '.lock')
        other = self.root / 'other'
        other.write_text('evidence')
        lock.symlink_to(other)
        with self.assertRaises(OSError): custody.Custody(self.root, self.workspace, exclusive=True)
        self.assertEqual(other.read_text(), 'evidence')
        lock.unlink()
        with custody.Custody(self.root, self.workspace, exclusive=True) as held:
            lock.rename(self.root / 'old-lock')
            lock.write_text('foreign replacement')
            with self.assertRaises(ValueError): held.check()
        self.assertEqual(lock.read_text(), 'foreign replacement')


if __name__ == '__main__': unittest.main()
