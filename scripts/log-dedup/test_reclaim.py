from contextlib import contextmanager
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import uuid

sys.path.insert(0, str(Path(__file__).parent))
import log_dedup as logs
import reclaim


class Recovery:
    location = 'desktop:B:/vk-backups/synthetic-fixture'

    def __init__(self, root):
        self.bodies = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
        self.corrupt = False
        self.reads = []

    @contextmanager
    def open_original(self, relative, sha256):
        self.reads.append((relative, sha256))
        yield io.BytesIO(b'corrupt' if self.corrupt else self.bodies[relative])


class ReclaimTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='vk-reclaim-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / 'sessions'
        self.source.mkdir()
        session = '12345678-1234-1234-1234-123456789abc'
        self.paths = ['12/' + session + '/processes/' + value + '.jsonl' for value in (
            '12345678-0000-0000-0000-000000000001', '12345678-0000-0000-0000-000000000002')]
        self.original = (json.dumps({'Stdout': 'exact readable history — ✓\n' * 400}) + '\n').encode()
        for relative in self.paths:
            path = self.source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(self.original)
            path.chmod(0o640)
            os.setxattr(path, 'user.log_dedup_fixture', b'preserve extended metadata')
            path.with_suffix('.capture.json').write_text('{"capture_state":"closed"}\n')
        self.db = self.base / 'database'
        with sqlite3.connect(self.db) as conn:
            conn.execute('CREATE TABLE execution_processes(id BLOB, session_id BLOB, status TEXT, completed_at TEXT)')
            for relative in self.paths:
                conn.execute('INSERT INTO execution_processes VALUES(?,?,?,?)',
                             (uuid.UUID(Path(relative).stem).bytes, uuid.UUID(session).bytes, 'completed', 'now'))
        self.plan = logs.scan(self.source, self.paths)
        self.archive = self.base / 'archive'
        logs.pack(self.plan, self.archive)
        self.store = Recovery(self.source)
        self.journal = self.base / 'operation'
        self.lock = self.base / 'capacity.lock'
        self.lock.touch(mode=0o600)
        self.state = {'version': 2, 'epoch': 'fixture', 'revision': 1, 'goals': {}}
        (self.base / 'capacity.json').write_text(json.dumps(self.state))
        (self.base / 'route').write_text('maintenance')
        before = {'complete': True, 'active': [], 'durable_queue': [], 'incoming_pending': [],
                  'database_identity': [self.db.stat().st_dev, self.db.stat().st_ino], 'fingerprint': 'fixture'}
        binding = {'log_source_root': str(self.source), 'database': str(self.db), 'database_target': str(self.db), 'capacity_lock': str(self.lock),
                   'capacity_state': str(self.base / 'capacity.json'), 'capacity_persisted_version': 2,
                   'route_path': str(self.base / 'route'), 'maintenance_bytes': 'maintenance',
                   'frozen_units': {'backend': {'pid': 123, 'invocation': 'birth'}}, 'stopped_units': []}
        self.units = {'MainPID': '123', 'InvocationID': 'birth', 'ControlGroup': '/user.slice/fixture',
                      'ActiveState': 'active', 'FreezerState': 'frozen'}
        self.fence = reclaim.WriterFence(binding, before, {'protocolVersion': 1, 'owned': False,
                       'state': dict(self.state, version=1)}, inspect=lambda _: self.units,
                       processes=lambda _: {123})
        self.patcher = patch('vk_restart_writer_fence.frozen', return_value=before)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.reader_ready = True

    def reader(self):
        if not self.reader_ready:
            raise ValueError('Reader/consumer qualification lost')

    def batch(self, **kwargs):
        return reclaim.Batch(self.plan, self.archive, self.journal, self.fence,
                             self.store, self.reader, reserve_bytes=kwargs.get('reserve', 0))

    def assert_original(self):
        for relative in self.paths:
            self.assertEqual((self.source / relative).read_bytes(), self.original)

    def test_custody_for_another_log_root_cannot_authorize_conversion(self):
        self.fence.binding['log_source_root'] = '/another/storage/root'
        with self.fence.held():
            with self.assertRaisesRegex(ValueError, 'exact log root'):
                self.batch().run()
        self.assert_original()

    def test_real_writer_lease_required_not_boolean_or_unheld_object(self):
        with self.assertRaises(ValueError):
            reclaim.Batch(self.plan, self.archive, self.journal, True, self.store, self.reader, reserve_bytes=0)
        with self.assertRaisesRegex(ValueError, 'retained capacity lease'):
            self.batch().run()
        self.assert_original()

    def test_install_and_raw_rollback_preserve_bytes_sidecars_and_modes(self):
        sidecars = [(self.source / p).with_suffix('.capture.json').read_bytes() for p in self.paths]
        with self.fence.held():
            self.assertTrue(self.batch().run()['complete'])
            for relative in self.paths:
                path = self.source / relative
                self.assertTrue(path.read_bytes().startswith(logs.MAGIC))
                self.assertEqual(logs.reconstruct(path)['sha256'], logs.sha(self.original))
                self.assertEqual(path.stat().st_mode & 0o777, 0o640)
                self.assertEqual(os.getxattr(path, 'user.log_dedup_fixture'), b'preserve extended metadata')
            self.assertTrue(self.batch().run(rollback=True)['complete'])
        self.assert_original()
        self.assertEqual(sidecars, [(self.source / p).with_suffix('.capture.json').read_bytes() for p in self.paths])
        self.assertEqual(len(self.store.reads), 8)
        for relative in self.paths:
            self.assertEqual(os.getxattr(self.source / relative, 'user.log_dedup_fixture'), b'preserve extended metadata')

    def test_crash_after_manifest_publication_resumes_exact_operation(self):
        def crash(_):
            raise RuntimeError('Injected crash after replace before receipt')
        with self.fence.held():
            with self.assertRaises(RuntimeError):
                self.batch().run(after_replace=crash)
            state = json.loads((self.journal / 'state.json').read_bytes())
            self.assertFalse(state['complete'])
            self.assertTrue(self.batch().run()['complete'])
            self.batch().run(rollback=True)
        self.assert_original()

    def test_crash_after_raw_rollback_publication_is_recoverable(self):
        with self.fence.held():
            self.batch().run()
            with self.assertRaises(RuntimeError):
                self.batch().run(rollback=True, after_replace=lambda _: (_ for _ in ()).throw(RuntimeError('crash')))
            self.assertTrue(self.batch().run(rollback=True)['complete'])
        self.assert_original()

    def test_exact_subset_never_converts_deferred_sample_files(self):
        self.plan = dict(self.plan, files=self.plan['files'][:1])
        with self.fence.held():
            self.batch().run()
        self.assertTrue((self.source / self.paths[0]).read_bytes().startswith(logs.MAGIC))
        self.assertEqual((self.source / self.paths[1]).read_bytes(), self.original)

    def test_other_running_execution_in_selected_session_blocks(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE execution_processes SET status='running' WHERE rowid=2")
        self.plan = dict(self.plan, files=self.plan['files'][:1])
        with self.fence.held():
            with self.assertRaisesRegex(ValueError, 'terminal execution'):
                self.batch().run()
        self.assert_original()

    def test_recorded_partial_reconstruction_is_cleaned_after_recovery_reverification(self):
        with self.fence.held():
            self.batch().run()
            stage = (self.source / self.paths[0]).parent / ('.restore-' + str(uuid.uuid4()))
            stage.write_bytes(self.original[:100])
            state_path = self.journal / 'state.json'
            state = json.loads(state_path.read_bytes())
            state['files'][self.paths[0]]['restore_temp'] = {
                'name': stage.name, 'inode': [stage.stat().st_dev, stage.stat().st_ino]}
            state_path.write_bytes(reclaim.canonical(state))
            self.batch().run(rollback=True)
            self.assertFalse(stage.exists())
        self.assert_original()

    def test_changed_bytes_in_recorded_staging_inode_are_preserved(self):
        with self.fence.held():
            self.batch().run()
            stage = (self.source / self.paths[0]).parent / ('.restore-' + str(uuid.uuid4()))
            stage.write_bytes(b'new external content')
            state_path = self.journal / 'state.json'
            state = json.loads(state_path.read_bytes())
            state['files'][self.paths[0]]['restore_temp'] = {
                'name': stage.name, 'inode': [stage.stat().st_dev, stage.stat().st_ino]}
            state_path.write_bytes(reclaim.canonical(state))
            with self.assertRaisesRegex(ValueError, 'staging content changed'):
                self.batch().run(rollback=True)
            self.assertEqual(stage.read_bytes(), b'new external content')

    def test_foreign_staging_inode_is_retained_instead_of_deleted(self):
        with self.fence.held():
            self.batch().run()
            stage = (self.source / self.paths[0]).parent / ('.restore-' + str(uuid.uuid4()))
            stage.write_bytes(b'foreign work')
            state_path = self.journal / 'state.json'
            state = json.loads(state_path.read_bytes())
            state['files'][self.paths[0]]['restore_temp'] = {'name': stage.name, 'inode': [0, 0]}
            state_path.write_bytes(reclaim.canonical(state))
            with self.assertRaisesRegex(ValueError, 'Foreign reconstruction'):
                self.batch().run(rollback=True)
            self.assertEqual(stage.read_bytes(), b'foreign work')

    def test_corrupt_or_missing_current_b_body_never_replaces_sources(self):
        self.store.corrupt = True
        with self.fence.held():
            with self.assertRaises(ValueError):
                self.batch().run()
        self.assert_original()

    def test_active_or_mismatched_execution_blocks(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE execution_processes SET status='running'")
        with self.fence.held():
            with self.assertRaisesRegex(ValueError, 'terminal execution'):
                self.batch().run()
        self.assert_original()

    def test_reader_or_physical_fence_loss_blocks(self):
        with self.fence.held():
            self.reader_ready = False
            with self.assertRaisesRegex(ValueError, 'qualification lost'):
                self.batch().run()
            self.reader_ready = True
            self.units['FreezerState'] = 'running'
            with self.assertRaises(ValueError):
                self.batch().run()
            self.units['FreezerState'] = 'frozen'
        self.assert_original()

    def test_foreign_identical_manifest_inode_is_never_overwritten_on_rollback(self):
        with self.fence.held():
            self.batch().run()
            target = self.source / self.paths[0]
            foreign = target.parent / 'foreign-manifest'
            raw = target.read_bytes()
            foreign.write_bytes(raw)
            foreign.replace(target)
            with self.assertRaisesRegex(ValueError, 'Foreign installed manifest'):
                self.batch().run(rollback=True)
            self.assertEqual(target.read_bytes(), raw)

    def test_unexpected_newer_data_after_partial_install_is_preserved(self):
        with self.fence.held():
            self.batch().run()
            target = self.source / self.paths[0]
            target.write_bytes(b'newer external content')
            with self.assertRaisesRegex(ValueError, 'Unknown/newer'):
                self.batch().run(rollback=True)
            self.assertEqual(target.read_bytes(), b'newer external content')

    def test_publication_peak_is_reserved_before_copying_any_objects(self):
        with self.fence.held():
            free = sum(row['raw_bytes'] for row in self.plan['files']) + 1
            with patch('reclaim.shutil.disk_usage', return_value=SimpleNamespace(free=free)):
                with self.assertRaisesRegex(ValueError, 'headroom'):
                    self.batch().run()
        self.assert_original()
        self.assertFalse(((self.source / self.paths[0]).parent / '.log-objects').exists())

    def test_insufficient_reconstruction_capacity_blocks(self):
        with self.fence.held():
            with self.assertRaisesRegex(ValueError, 'headroom'):
                self.batch(reserve=10**18).run()
        self.assert_original()

    def test_object_publication_failure_is_safe_and_resumable(self):
        with self.fence.held():
            with patch('reclaim.os.link', side_effect=OSError('injected publication failure')):
                with self.assertRaises(OSError):
                    self.batch().run()
            self.assert_original()
            self.assertTrue(self.batch().run()['complete'])

    def test_changed_sidecar_and_foreign_same_byte_inode_are_preserved(self):
        sidecar = (self.source / self.paths[0]).with_suffix('.capture.json')
        saved = sidecar.read_bytes()
        sidecar.write_text('{"capture_state":"pending"}')
        with self.fence.held():
            with self.assertRaisesRegex(ValueError, 'sidecar'):
                self.batch().run()
            sidecar.write_bytes(saved)
            source = self.source / self.paths[0]
            external = source.parent / 'external'
            external.write_bytes(self.original)
            external.replace(source)
            with self.assertRaisesRegex(ValueError, 'inode changed'):
                self.batch().run()
            self.assert_original()

    def test_symlink_object_never_becomes_a_valid_shared_reference(self):
        manifest = logs.load_manifest(self.archive / self.paths[0])
        store = (self.source / self.paths[0]).parent / '.log-objects'
        store.mkdir()
        (store / (manifest['chunks'][0]['sha256'] + '.gz')).symlink_to(self.source / self.paths[0])
        with self.fence.held():
            with self.assertRaises(ValueError):
                self.batch().run()
        self.assert_original()

    def test_corrupted_object_fails_before_publication(self):
        first = self.archive / self.paths[0]
        obj = next((first.parent / '.log-objects').iterdir())
        obj.write_bytes(b'corrupt')
        with self.fence.held():
            with self.assertRaises((ValueError, OSError)):
                self.batch().run()
        self.assert_original()


if __name__ == '__main__':
    unittest.main()
