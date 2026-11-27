"""Actual filesystem/SQLite failure tests; fixture store is NOT Desktop B proof."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import uuid
import unittest

from catalog import canonical, Conflict
from custody import Custody
from lifecycle import Lifecycle, digest
import payloads
import test_catalog as catalog_fixtures


class FixtureStore:
    def __init__(self, root):
        self.root = root
        self.offline = False
        self.captures = 0
        self.uncertain_once = False
        self.corrupt = False

    def capture(self, manifest):
        if self.offline:
            raise OSError('fixture B offline')
        path = self.root / manifest['operation_id']
        if not path.exists():
            path.mkdir()
            self.captures += 1
            (path / 'manifest').write_text(canonical(manifest))
            for index, row in enumerate(manifest['payloads']['entries']):
                if row['kind'] == 'file':
                    source = Path(manifest['payloads']['roots'][row['root']]) / row['relative']
                    (path / str(index)).write_bytes(source.read_bytes())
        elif json.loads((path / 'manifest').read_text()) != manifest:
            raise ValueError('different retained fixture operation')
        if self.uncertain_once:
            self.uncertain_once = False
            raise ConnectionError('capture committed but receipt interrupted')
        return dict(fixture_only=True, operation=manifest['operation_id'], sha256=digest(manifest))

    @contextmanager
    def recall(self, locator, expected):
        if self.offline:
            raise OSError('fixture B offline')
        path = self.root / locator['operation']
        raw = (path / 'manifest').read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('fixture B manifest corrupt')
        manifest = json.loads(raw)
        owner = self
        class Reader:
            @contextmanager
            def open_body(self, row):
                body = path / str(manifest['payloads']['entries'].index(row))
                if owner.corrupt:
                    import io
                    yield io.BytesIO(b'corrupt')
                else:
                    with body.open('rb') as source:
                        yield source
        reader = Reader()
        reader.manifest = manifest
        yield reader


class FixtureAuthority:
    def __init__(self, roots):
        self.roots = roots
        self.busy = False

    def check(self, workspace, manifest):
        if self.busy:
            raise Conflict('fixture foreign owner became active')

    def validate_plan(self, workspace, ownership):
        if ownership != {'roots': self.roots, 'fixture_only': True}:
            raise Conflict('unknown fixture ownership')

    def reserve_restore(self, manifest, stage):
        self.check(manifest['workspace_id'], manifest)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        fixture = catalog_fixtures.CatalogTests(methodName='test_interrupted_restore_keeps_input_and_blocks_new_archive')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.c, self.w, self.s, self.payload = fixture.catalog, fixture.w, fixture.s, fixture.payload
        self.root = fixture.path.parent
        for name in ('locks', 'stage', 'fixture-B', 'history', 'worktree'):
            (self.root / name).mkdir(mode=0o700)
        (self.root / 'history/log').write_bytes(b'exact log\n' * 70)
        (self.root / 'worktree/code').write_bytes(b'preserved source\n')
        (self.root / 'worktree/empty').touch()
        os.symlink('code', self.root / 'worktree/link')
        self.roots = [str(self.root / n) for n in ('history', 'worktree')]
        self.authority = FixtureAuthority(self.roots)
        self.b = FixtureStore(self.root / 'fixture-B')
        self.custody = Custody(self.root / 'locks', self.w, exclusive=True)
        self.addCleanup(self.custody.close)
        self.op = str(uuid.uuid4())
        self.events = []
        self.hook = None
        def event(kind, data):
            self.events.append(kind)
            if self.hook:
                self.hook(kind, data)
        self.life = Lifecycle(self.c, self.custody, self.b, self.authority, self.root / 'stage', event)

    def prepare(self):
        return self.life.prepare(1, self.op, {'roots': self.roots, 'fixture_only': True})

    def retain(self):
        request = str(uuid.uuid4())
        self.c.retain_input(self.w, self.s, request, self.payload)
        return request

    def interrupt(self, target):
        def hook(kind, data):
            if kind == target:
                raise InterruptedError(target)
        self.hook = hook

    def test_real_move_restore_preserves_history_code_empty_symlink_and_exact_input(self):
        manifest = self.prepare()
        self.life.retire()
        self.assertFalse(any(Path(p).exists() for p in self.roots))
        self.assertEqual(self.c.state(self.w)['phase'], 'cold')
        self.assertEqual(len(self.c.cold_generations()), 1)
        self.assertEqual(list((self.root / 'stage').iterdir()), [])
        self.retain()
        self.assertEqual(self.c.cold_generations(), [])
        self.life.restore()
        payloads.verify(manifest['payloads'])
        row = self.c.db.execute('SELECT payload,state FROM workspace_archive_inputs').fetchone()
        self.assertEqual((json.loads(row[0]), row[1]), (self.payload, 'ready'))
        self.assertEqual(self.b.captures, 1)
        self.assertEqual(self.c.db.execute('SELECT count(*) FROM workspace_archive_generations').fetchone()[0], 1)

    def test_uncertain_capture_reconciles_same_operation_without_recapture(self):
        self.b.uncertain_once = True
        with self.assertRaises(ConnectionError): self.prepare()
        self.life.resume_preparation()
        self.assertEqual(self.b.captures, 1)
        self.assertEqual(self.c.state(self.w)['phase'], 'verified')

    def test_offline_or_corrupt_b_never_retires_originals(self):
        self.b.offline = True
        with self.assertRaises(OSError): self.prepare()
        self.assertTrue(all(Path(p).exists() for p in self.roots))
        self.b.offline, self.b.corrupt = False, True
        with self.assertRaises(ValueError): self.life.resume_preparation()
        self.assertEqual(self.c.state(self.w)['phase'], 'preparing')
        self.assertTrue(all(Path(p).exists() for p in self.roots))
        self.assertEqual(self.c.cold_generations(), [])

    def test_incomplete_verification_restore_is_preserved_and_recovered_without_new_capture(self):
        self.b.corrupt = True
        with self.assertRaises(ValueError): self.prepare()
        self.b.corrupt = False
        manifest = self.life.resume_preparation()
        journal = self.c.io(self.w)['journal']
        self.assertEqual(self.b.captures, 1)
        self.assertEqual(self.c.state(self.w)['phase'], 'verified')
        self.assertEqual(len(journal['abandoned_verification']), 1)
        self.assertTrue(Path(journal['abandoned_verification'][0]).exists())
        payloads.verify(manifest['payloads'])

    def test_input_during_copy_cancels_intact_preparation_even_when_b_offline(self):
        self.b.offline = True
        with self.assertRaises(OSError): self.prepare()
        self.retain()
        self.life.restore()
        self.assertEqual(self.c.state(self.w)['phase'], 'active')
        self.assertTrue(all(Path(p).exists() for p in self.roots))

    def test_crash_between_root_renames_reconciles_then_retires(self):
        self.prepare()
        self.interrupt('root_retired')
        with self.assertRaises(InterruptedError): self.life.retire()
        self.assertEqual(self.c.state(self.w)['phase'], 'retiring')
        self.assertEqual(self.c.cold_generations(), [])
        self.hook = None
        self.life.retire()
        self.assertEqual(self.c.state(self.w)['phase'], 'cold')
        self.assertFalse(any(Path(p).exists() for p in self.roots))

    def test_message_during_retirement_rolls_back_complete_originals_without_b(self):
        manifest = self.prepare()
        self.interrupt('root_retired')
        with self.assertRaises(InterruptedError): self.life.retire()
        self.retain()
        self.hook, self.b.offline = None, True
        with self.assertRaises(Conflict): self.life.retire()
        self.life.restore()
        payloads.verify(manifest['payloads'])
        self.assertEqual(self.c.state(self.w)['phase'], 'active')

    def test_offline_revival_retains_input_then_recovers_and_resumes_publish_after_crash(self):
        manifest = self.prepare()
        self.life.retire()
        self.retain()
        self.b.offline = True
        with self.assertRaises(OSError): self.life.restore()
        self.assertEqual(self.c.state(self.w)['phase'], 'restoring')
        self.assertEqual(self.c.db.execute('SELECT state FROM workspace_archive_inputs').fetchone()[0], 'waiting_restore')
        self.b.offline = False
        self.interrupt('root_revived')
        with self.assertRaises(InterruptedError): self.life.restore()
        self.hook = None
        self.life.restore()
        payloads.verify(manifest['payloads'])
        self.assertEqual(self.c.state(self.w)['phase'], 'active')

    def test_newer_active_destination_is_never_overwritten(self):
        self.prepare()
        self.life.retire()
        self.retain()
        Path(self.roots[0]).mkdir()
        (Path(self.roots[0]) / 'new').write_bytes(b'newer data')
        with self.assertRaises(Conflict): self.life.restore()
        self.assertEqual((Path(self.roots[0]) / 'new').read_bytes(), b'newer data')
        self.assertEqual(self.c.state(self.w)['phase'], 'restoring')

    def test_changed_source_or_changed_owner_blocks_retirement(self):
        self.prepare()
        (Path(self.roots[0]) / 'log').write_bytes(b'changed source')
        with self.assertRaises(ValueError): self.life.retire()
        self.assertTrue(all(Path(p).exists() for p in self.roots))
        self.authority.busy = True
        with self.assertRaises(Conflict): self.life.retire()

    def test_unexpected_quarantine_data_is_protected_and_purge_can_resume_after_unlink(self):
        self.prepare()
        self.interrupt('cold')
        with self.assertRaises(InterruptedError): self.life.retire()
        journal = self.c.io(self.w)['journal']
        cold = Path(journal['retired_roots'][0])
        (cold / 'newer').write_bytes(b'foreign work')
        self.hook = None
        with self.assertRaises(ValueError): self.life.purge()
        self.assertEqual((cold / 'newer').read_bytes(), b'foreign work')
        (cold / 'newer').unlink()  # Remove only the test's own injected file.
        self.life.purge()
        self.assertFalse(any(Path(p).exists() for p in journal['retired_roots']))

    def test_tampered_retirement_path_cannot_delete_unrelated_data(self):
        self.prepare()
        row = self.c.io(self.w)
        row['journal']['retired_roots'][0] = str(self.root / 'fixture-B')
        self.c.save_io(self.w, self.op, row['journal'], row['revision'])
        with self.assertRaises(Conflict): self.life.retire()
        self.assertTrue((self.root / 'fixture-B').exists())
