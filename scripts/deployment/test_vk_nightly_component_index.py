"""Small isolated control fixtures: no source crawl or archive payload copy."""
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from vk_nightly_component_index import ComponentIndex
from vk_nightly_checkpoints import sha256


def fixture(number):
    row=dict(action='file',path='/source/'+str(number),bytes=3,sha256='a'*64,
             metadata=dict(mode=0o644,uid=os.getuid(),gid=os.getgid(),mtime_ns=123,xattrs={}))
    raw=(json.dumps(row)+'\n').encode()
    def seal(name,size,checksum):return dict(name=name,bytes=size,sha256=checksum,file_identity=[1,number,size,123])
    return dict(encoding='zip-member',members=1,raw_bytes=3,
                archive=seal(str(number)+'.zip',100,'b'*64),
                records=seal(str(number)+'.jsonl',len(raw),sha256(raw))),raw


class ComponentIndexTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'control.sqlite'

    def test_restart_skips_committed_components_and_supports_hash_carrier_lookup(self):
        c,raw=fixture(1)
        with ComponentIndex.held(self.path,create=True) as index:
            self.assertFalse(index.adopt(c,raw)['already_committed'])
        with ComponentIndex.held(self.path) as index:
            self.assertTrue(index.contains(c))
            self.assertEqual(index.adopt(c,b'not reread'),dict(already_committed=True,metadata_bytes_read=0))
            self.assertEqual(len(list(index.carriers('a'*64,3))),1)
            self.assertFalse(index.summary()['full_backup_accepted'])

    def test_interruption_rolls_back_only_incomplete_component(self):
        a,raw=fixture(1);b,other=fixture(2)
        def interrupted():raise RuntimeError('owned interruption')
        with ComponentIndex.held(self.path,create=True) as index:
            index.adopt(a,raw)
            with self.assertRaises(RuntimeError):index.adopt(b,other,checkpoint=interrupted)
            self.assertEqual(index.summary()['components'],1)
        with ComponentIndex.held(self.path) as index:
            self.assertFalse(index.contains(b));index.adopt(b,other)
            self.assertEqual(index.summary()['components'],2)

    def test_native_carrier_binding_change_is_not_skipped_as_same_hash(self):
        a,raw=fixture(1)
        with ComponentIndex.held(self.path,create=True) as index:
            index.adopt(a,raw);a['archive']['file_identity'][1]+=1
            self.assertFalse(index.contains(a))

    def test_checksum_or_count_failure_preserves_completed_versions(self):
        a,raw=fixture(1);b,other=fixture(2)
        with ComponentIndex.held(self.path,create=True) as index:
            index.adopt(a,raw)
            with self.assertRaises(ValueError):index.adopt(b,other+b'x')
            self.assertEqual(index.summary()['components'],1)

    def test_competing_owner_and_substituted_or_linked_inode_are_refused(self):
        with ComponentIndex.held(self.path,create=True) as index:
            with self.assertRaises(BlockingIOError):
                with ComponentIndex.held(self.path):pass
            old=self.path.with_name('preserved');self.path.rename(old);self.path.write_text('replacement')
            with self.assertRaises(ValueError):index.check()
            self.path.unlink();old.rename(self.path)
        link=self.path.with_name('link');link.symlink_to(self.path)
        with self.assertRaises(ValueError):
            with ComponentIndex.held(link):pass


if __name__=='__main__':unittest.main()
