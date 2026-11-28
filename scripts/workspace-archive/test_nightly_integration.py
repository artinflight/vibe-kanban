"""Actual maintained Nightly map/restore code composed with archive SQL fixtures."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'nightly-owner'))
import vk_nightly_workspace_archive as integration
from vk_nightly_composed_restore import restore_sample
import test_nightly_selection as fixtures


class NightlyIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.NightlySelectionTests(methodName='test_current_sql_cold_reference_and_shared_payload_are_one_selection')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.source=self.fixture.f
        self.temp=tempfile.TemporaryDirectory(dir='/dev/shm')
        self.addCleanup(self.temp.cleanup)
        self.scratch=Path(self.temp.name)

    def point(self):
        with self.fixture.select() as selection:
            point=self.fixture.snapshot(selection)
            expected=integration.contract(selection)
            self.assertEqual(integration.records(self.source.c.db),selection.references)
        return point,expected

    def test_actual_current_map_refuses_old_cold_bodies_and_requires_shared_data(self):
        _,expected=self.point()
        db=sqlite3.connect(':memory:');self.addCleanup(db.close)
        db.execute('CREATE TABLE members(name TEXT PRIMARY KEY,state TEXT) WITHOUT ROWID')
        db.executemany('INSERT INTO members VALUES(?,?)',[(p[1:],'verified-file')for p in expected['required_active_sources']])
        integration.check_map(db,expected,guard=lambda:None)
        root=next(iter(expected['excluded_roots']))
        db.execute('INSERT INTO members VALUES(?,?)',(root[1:]+'/old-log','verified-file'))
        with self.assertRaisesRegex(ValueError,'physically archived'):
            integration.check_map(db,expected,guard=lambda:None)
        db.execute('DELETE FROM members WHERE name=?',(root[1:]+'/old-log',))
        db.execute('DELETE FROM members WHERE name=?',(str(self.fixture.required)[1:],))
        with self.assertRaisesRegex(ValueError,'shared dependency missing'):
            integration.check_map(db,expected,guard=lambda:None)

    def handle(self,point):
        path=Path(point['image']);data=path.read_bytes()
        with sqlite3.connect(path) as db:
            schema=db.execute('select type,name,tbl_name,sql from sqlite_master order by type,name,tbl_name,sql').fetchall()
        db.close()
        schema_sha=hashlib.sha256(json.dumps(schema,separators=(',',':')).encode()).hexdigest()
        row=dict(kind='file',uid=os.getuid(),gid=os.getgid(),mode=0o600,mtime_ns=123,xattrs={},bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
        return SimpleNamespace(index=SimpleNamespace(entry=lambda _:row),
            descriptor={'SQLite':{point['source']:{'schema_sha256':schema_sha}}},
            blocks=lambda _:(data[i:i+65536]for i in range(0,len(data),65536)),check=lambda:None)

    def test_normal_SQL_readback_preserves_exact_cold_catalog_without_recapturing(self):
        point,expected=self.point()
        result=restore_sample(self.handle(point),point['source'],self.scratch,
                              guard=lambda:None,workspace_archive=expected)
        self.assertTrue(result['workspace_archive']['current_SQL_cold_catalog_verified'])
        self.assertEqual(result['workspace_archive']['body_bytes_recaptured'],0)
        self.assertEqual(result['workspace_archive']['cold_generations'],1)
        self.assertEqual(self.source.b.captures,1)
        self.assertEqual(list(self.scratch.iterdir()),[])

    def test_normal_SQL_reader_preserves_failed_recovery_when_reference_differs(self):
        point,expected=self.point();bad=copy.deepcopy(expected)
        bad['cold_generations_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'lost or changed') as failed:
            restore_sample(self.handle(point),point['source'],self.scratch,
                           guard=lambda:None,workspace_archive=bad)
        kept=Path(failed.exception.nightly_composed_restore_preserved_path)
        self.assertEqual(kept.read_bytes(),Path(point['image']).read_bytes())

    def test_restored_SQL_with_pending_revival_cannot_be_accepted(self):
        self.point();self.source.retain()
        with self.assertRaisesRegex(ValueError,'incomplete|pending input'):
            integration.records(self.source.c.db)


if __name__=='__main__': unittest.main()
