"""Lossless compressed-object recovery, overlap and exact crash reconciliation."""
import hashlib
import io
import os
from pathlib import Path
import tempfile
import unittest
import zlib

from test_vk_restart_safeguards import fixture_readback
from vk_nightly_generation import COMPRESSED, NightlyStore, object_blocks
import test_vk_nightly_lifecycle as lifecycle_tests


class CompressedObjects(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir='/mnt/vk-storage',prefix='nightly-codec-test-')
        self.root=Path(self.tmp.name);self.store=NightlyStore(self.root,'a'*64,lambda:self.root.parent,
            independent_readback=fixture_readback,object_encoding=COMPRESSED)
        self.store.enroll_empty()
    def tearDown(self):self.tmp.cleanup()
    def row(self,data):return {'kind':'file','bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    def advance(self,entries,absent=(),previous=None,reserve=2*1024**2):
        return self.store.advance(entries,absent,expected_previous=previous,reserve_bytes=reserve,retention_adopted=True)
    def recover(self,manifest,key):
        row=manifest['entries'][key]
        return b''.join(object_blocks(self.root/manifest['generation']/'objects'/row['sha256'],row['sha256'],row['bytes'],manifest['object_encoding']))
    def test_cold_then_delta_current_independent_after_old_retirement(self):
        data=b'immutable history\n'*100000;first=self.advance([('history',self.row(data),io.BytesIO(data))])
        current=self.store.current();object_path=self.root/current['generation']/'objects'/self.row(data)['sha256'];inode=object_path.stat().st_ino
        self.assertLess(first['stored_changed_bytes'],len(data)//10)
        second=self.advance([('note',self.row(b'new'),io.BytesIO(b'new'))],previous=current['generation'])
        self.assertFalse((self.root/current['generation']).exists())
        current=self.store.current();self.assertIsNone(current['parent']);self.assertEqual(self.recover(current,'history'),data)
        self.assertEqual((self.root/current['generation']/'objects'/self.row(data)['sha256']).stat().st_ino,inode)
        self.assertEqual(second['changed_bytes'],3);self.store.verify(current)
    def test_exact_decoded_bound_blocks_bomb_trailing_truncation_and_wrong_hash(self):
        p=self.root/'object';data=b'x'*2*1024**2
        for payload,size,checksum in [(zlib.compress(data),10,hashlib.sha256(data).hexdigest()),
            (zlib.compress(data)+b'extra',len(data),hashlib.sha256(data).hexdigest()),
            (zlib.compress(data)[:-1],len(data),hashlib.sha256(data).hexdigest()),
            (zlib.compress(data),len(data),'0'*64)]:
            p.write_bytes(payload)
            with self.assertRaises(ValueError):list(object_blocks(p,checksum,size,COMPRESSED))
    def test_encoded_reservation_not_raw_size_and_failed_current_preserved(self):
        data=b'0'*4*1024**2
        first=self.advance([('history',self.row(data),io.BytesIO(data))],reserve=64*1024)
        current=self.store.current()
        with self.assertRaises(ValueError):self.advance([('noise',self.row(os.urandom(1024**2)),io.BytesIO(os.urandom(1024**2)))],previous=current['generation'],reserve=4096)
        self.assertEqual(self.store.current()['generation'],first['generation']);self.assertEqual(self.recover(current,'history'),data)
    def test_unknown_encoding_and_substituted_object(self):
        with self.assertRaises(ValueError):NightlyStore(self.root,'a'*64,lambda:self.root.parent,object_encoding='guess')
        data=b'data';self.advance([('data',self.row(data),io.BytesIO(data))]);m=self.store.current()
        p=self.root/m['generation']/'objects'/self.row(data)['sha256'];p.unlink();p.symlink_to(self.root/'store.json')
        with self.assertRaises(OSError):self.store.verify(m)
    def test_duplicate_content_consumes_one_encoded_reservation(self):
        data=os.urandom(65536);row=self.row(data)
        result=self.advance([('a',row,io.BytesIO(data)),('b',row,io.BytesIO(data))],reserve=70000)
        self.assertEqual(result['changed_bytes'],2*len(data));self.assertLess(result['stored_changed_bytes'],70000)
        self.assertEqual(self.recover(self.store.current(),'b'),data)


class CompressedLifecycle(lifecycle_tests.NightlyLifecycle):
    def setUp(self):
        super().setUp();self.store_job.object_encoding=COMPRESSED
    def latest_rows(self):
        import sqlite3
        m=self.store_job.current();r=m['entries']['home/state/state.sqlite']
        data=b''.join(object_blocks(self.nightly/m['generation']/'objects'/r['sha256'],r['sha256'],r['bytes'],COMPRESSED))
        with sqlite3.connect(':memory:') as db:
            db.deserialize(data);return db.execute('SELECT value FROM retained ORDER BY rowid').fetchall()


if __name__=='__main__':unittest.main()
