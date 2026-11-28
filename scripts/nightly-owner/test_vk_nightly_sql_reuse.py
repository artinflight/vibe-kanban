import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

from vk_nightly_sql_reuse import qualify_cold_image


class ColdSQLReuseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir='/dev/shm');self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'current.sqlite';snapshot=Path(self.tmp.name)/'accepted.sqlite'
        with sqlite3.connect(self.path) as source:
            source.execute('create table retained(value)');source.execute("insert into retained values('saved')");source.commit()
            with sqlite3.connect(snapshot) as destination:source.backup(destination)
        shutil.copyfile(snapshot,self.path)
        raw=snapshot.read_bytes();sha=hashlib.sha256(raw).hexdigest()
        proof=dict(sha256=sha,bytes=len(raw),integrity='ok')
        self.image=dict(sha256=sha,bytes=len(raw),proof={'native':proof,'Linux_reopen':proof})

    def qualify(self,**overrides):
        args=dict(allowed_sources={str(self.path)},guard=lambda:None,maximum_bytes=1024**2,timeout_seconds=5)
        args.update(overrides);return qualify_cold_image(self.path,self.image,**args)

    def test_actual_SQL_API_read_point_reuses_exact_consistent_image_without_copy(self):
        result=self.qualify();self.assertTrue(result['reusable']);self.assertEqual(result['new_backup_payload_bytes'],0)
        self.assertEqual(result['source_sha256'],self.image['sha256']);self.assertFalse(result['current_baseline_accepted'])

    def test_sidecars_and_larger_DBs_require_backup_API_not_raw_copy(self):
        wal=Path(str(self.path)+'-wal');wal.write_bytes(b'pending WAL')
        self.assertFalse(self.qualify()['reusable']);wal.unlink()
        self.assertFalse(self.qualify(maximum_bytes=1)['reusable'])

    def test_changed_current_data_does_not_reuse_old_integrity_receipt(self):
        with sqlite3.connect(self.path) as source:source.execute("insert into retained values('later')")
        self.assertFalse(self.qualify()['reusable'])

    def test_metadata_change_during_read_refuses_point_without_mutating_old_image(self):
        calls=0
        def change():
            nonlocal calls
            calls+=1
            if calls==2:self.path.chmod(0o600 if self.path.stat().st_mode&0o777!=0o600 else 0o644)
        with self.assertRaisesRegex(ValueError,'read point changed'):self.qualify(guard=change)

    def test_unproved_image_and_unlisted_source_refuse_before_source_read(self):
        with self.assertRaises(ValueError):self.qualify(allowed_sources=set())
        self.image['proof']['native']=dict(self.image['proof']['native'],integrity='not proved')
        with self.assertRaises(ValueError):self.qualify()


if __name__=='__main__':unittest.main()
