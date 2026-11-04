import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import uuid

import log_dedup as logs
import stage_objects as stage


class StageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'sessions'
        self.sid, self.pid = uuid.uuid4(), uuid.uuid4()
        self.relative = f'{str(self.sid)[:2]}/{self.sid}/processes/{self.pid}.jsonl'
        self.log = self.root / self.relative
        self.log.parent.mkdir(parents=True)
        self.raw = (b'{"Stdout":"a readable original turn\\n"}\n' * 100)
        self.log.write_bytes(self.raw)
        self.log.with_suffix('.capture.json').write_text(json.dumps({'capture_state': 'closed'}))
        self.plan = logs.scan(self.root, [self.relative])
        self.archive = self.base / 'archive'
        logs.pack(self.plan, self.archive)
        self.db = self.base / 'test.sqlite'
        with sqlite3.connect(self.db) as conn:
            conn.execute('CREATE TABLE execution_processes(id BLOB, session_id BLOB, status TEXT, completed_at TEXT)')
            conn.execute('INSERT INTO execution_processes VALUES(?,?,?,?)',
                         (self.pid.bytes, self.sid.bytes, 'completed', '2026-11-04'))
        self.store = self.log.parent / '.log-objects'

    def run_stage(self, guard=lambda: None):
        with patch.object(stage.shutil, 'disk_usage', return_value=shutil._ntuple_diskusage(2**50, 0, 2**50)):
            return stage.stage(self.plan, self.archive, self.db, guard)

    def test_additions_keep_originals_and_can_resume_without_replacing_objects(self):
        before = logs.version(self.log.stat())
        result = self.run_stage()
        self.assertGreater(result['objects_created'], 0)
        self.assertEqual(result['manifest_replacements'], 0)
        self.assertEqual(self.log.read_bytes(), self.raw)
        self.assertEqual(logs.version(self.log.stat()), before)
        objects = {p.name: logs.version(p.stat()) for p in self.store.iterdir()}
        again = self.run_stage()
        self.assertEqual(again['objects_created'], 0)
        self.assertEqual(again['objects_reused'], len(objects))
        self.assertEqual(objects, {p.name: logs.version(p.stat()) for p in self.store.iterdir()})

    def test_corrupt_existing_object_is_preserved_and_original_stays_raw(self):
        self.run_stage()
        obj = next(self.store.iterdir())
        obj.write_bytes(b'foreign corrupt bytes')
        with self.assertRaises(Exception):
            self.run_stage()
        self.assertEqual(obj.read_bytes(), b'foreign corrupt bytes')
        self.assertEqual(self.log.read_bytes(), self.raw)

    def test_active_session_refused_before_any_addition(self):
        with sqlite3.connect(self.db) as conn:
            conn.execute('INSERT INTO execution_processes VALUES(?,?,?,NULL)', (uuid.uuid4().bytes, self.sid.bytes, 'running'))
        with self.assertRaises(logs.ArchiveError):
            self.run_stage()
        self.assertFalse(self.store.exists())

    def test_archive_alias_or_changed_sidecar_refused(self):
        alias = self.base / 'foreign'
        alias.mkdir()
        self.store.symlink_to(alias, target_is_directory=True)
        with self.assertRaises(logs.ArchiveError):
            self.run_stage()
        self.assertFalse(list(alias.iterdir()))
        self.store.unlink()
        self.log.with_suffix('.capture.json').write_text('{"capture_state":"pending"}')
        with self.assertRaises(logs.ArchiveError):
            self.run_stage()
        self.assertFalse(self.store.exists())

    def test_publication_failure_preserves_partial_objects_and_source(self):
        link = os.link
        def fail_after_link(*args, **kwargs):
            link(*args, **kwargs)
            raise OSError('injected failure')
        with patch.object(stage.os, 'link', side_effect=fail_after_link):
            with self.assertRaises(OSError):
                self.run_stage()
        self.assertEqual(self.log.read_bytes(), self.raw)
        self.assertTrue(list(self.store.glob('*.gz')))
        self.assertFalse(list(self.store.glob('.new-*')))
        result = self.run_stage()
        self.assertEqual(result['objects_created'], 0)

    def test_external_original_change_during_publication_is_preserved(self):
        link = os.link
        changed = self.raw + b'external new data\n'
        def change_original(*args, **kwargs):
            link(*args, **kwargs)
            self.log.write_bytes(changed)
        with patch.object(stage.os, 'link', side_effect=change_original):
            with self.assertRaises(logs.ArchiveError):
                self.run_stage()
        self.assertEqual(self.log.read_bytes(), changed)
        self.assertTrue(list(self.store.glob('*.gz')))

    def test_foreign_replacement_of_temporary_is_never_removed(self):
        link = os.link
        foreign = []
        def replace_temporary(temporary, target, **kwargs):
            temporary.rename(temporary.with_name(temporary.name + '.saved'))
            temporary.write_bytes(b'foreign replacement')
            foreign.append(temporary)
            link(temporary, target, **kwargs)
        with patch.object(stage.os, 'link', side_effect=replace_temporary):
            with self.assertRaises(Exception):
                self.run_stage()
        self.assertTrue(foreign)
        self.assertEqual(foreign[0].read_bytes(), b'foreign replacement')
        self.assertEqual(self.log.read_bytes(), self.raw)

    def test_packed_object_change_between_verification_and_copy_is_rejected(self):
        original = stage.object_bytes
        def change_packed(path, chunk):
            original(path, chunk)
            if path.is_relative_to(self.archive):
                path.write_bytes(b'changed packed input')
        with patch.object(stage, 'object_bytes', side_effect=change_packed):
            with self.assertRaises(logs.ArchiveError):
                self.run_stage()
        self.assertEqual(self.log.read_bytes(), self.raw)
        self.assertFalse(list(self.store.glob('*.gz')))

    def test_actual_capacity_guard_refuses_before_object_directory(self):
        with patch.object(stage.shutil, 'disk_usage', return_value=shutil._ntuple_diskusage(0, 0, 0)):
            with self.assertRaises(logs.ArchiveError):
                stage.stage(self.plan, self.archive, self.db, lambda: None)
        self.assertFalse(self.store.exists())

    def test_guard_failure_does_not_mutate_originals(self):
        def guard():
            raise logs.ArchiveError('resource unavailable')
        with self.assertRaises(logs.ArchiveError):
            self.run_stage(guard)
        self.assertEqual(self.log.read_bytes(), self.raw)
        self.assertFalse(self.store.exists())


if __name__ == '__main__':
    unittest.main()
