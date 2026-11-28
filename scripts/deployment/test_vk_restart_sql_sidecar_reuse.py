"""Real RAM SQLite/WAL and kernel-event fixtures; no live B acceptance claim."""
import copy
import ctypes
import hashlib
import os
from pathlib import Path
import sqlite3
import stat
import struct
import tempfile
import time
import unittest

from vk_restart_sql_reuse import attributes, fingerprint
from vk_restart_sql_sidecar_reuse import canonical, qualify_sidecar_source


class SidecarReuse(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='vk-sidecar-reuse-', dir='/dev/shm')
        self.root = Path(self.temp.name);self.path = self.root / 'source.sqlite'
        self.writer = sqlite3.connect(self.path)
        self.writer.execute('pragma journal_mode=WAL')
        self.writer.execute('create table sample(value text)')
        self.writer.execute('insert into sample values(?)', ('a' * 4096,));self.writer.commit()
        self.sidecars = {'-wal':self.observation(self.path.with_name(self.path.name+'-wal')), '-journal':None}
        info = self.path.stat()
        metadata = dict(device=info.st_dev, inode=info.st_ino, mode=stat.S_IMODE(info.st_mode),
                        uid=info.st_uid, gid=info.st_gid, mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns, xattrs=attributes(self.path))
        image = self.root / 'image.sqlite'
        with sqlite3.connect(self.path.as_uri()+'?mode=ro', uri=True) as source:
            with sqlite3.connect(image) as target:source.backup(target)
        with sqlite3.connect(image.as_uri()+'?mode=ro&immutable=1', uri=True) as reader:
            self.assertEqual(reader.execute('pragma integrity_check').fetchall(), [('ok',)])
        sha = hashlib.sha256(image.read_bytes()).hexdigest()
        member = dict(kind='file', bytes=image.stat().st_size, sha256=sha,
                      **{k:metadata[k] for k in ['mode','uid','gid','mtime_ns','xattrs']})
        self.request = dict(format='vk-nightly-current-SQL-cohort-request-v1', sources=[str(self.path)],
            always_SQL_API_sources=[],metadata_delta=dict(through=100),binding=dict(source_instance='a'*32,plan_sha256='b'*64,scope_sha256='c'*64))
        self.request['cohort_id'] = hashlib.sha256(canonical(self.request)).hexdigest()
        self.point = dict(source=str(self.path), SQL_cohort_id=self.request['cohort_id'], status='consistent_SQL_point_verified',
            method='SQLite-backup-API', source_changed_online=False, source_API_point_qualifies_later_epoch_not_original=True,
            original_source_API_point_at=time.time(), member=member, bytes=member['bytes'], sha256=sha,
            independent=dict(integrity='ok',bytes=member['bytes'],sha256=sha),B_acceptance_object=dict(sha256='d'*64),
            source_metadata_before=metadata, source_metadata_after=copy.deepcopy(metadata), source_identity_before=fingerprint(info))
        self.report = dict(instance='a'*32,plan_sha256='b'*64,scope_sha256='c'*64,since=100,sequence=200,
            ready=True,errors=[],coverage_model='all-selected-inodes-v1',changed=[str(self.path)+'-wal',str(self.path)+'-shm'],
            events={str(self.path)+'-wal':0x8,str(self.path)+'-shm':0x2},
            barrier=dict(kernel_drain_completed=True,durable_sequence=200,instance='a'*32))

    def observation(self, path):
        info=path.stat()
        return dict(source=str(path), required_SQL_source=str(self.path), namespace=dict(kind='file',bytes=info.st_size,
            identity=fingerprint(info), mode=stat.S_IMODE(info.st_mode),uid=info.st_uid,gid=info.st_gid,mtime_ns=info.st_mtime_ns,xattrs=attributes(path)))

    def tearDown(self):
        self.writer.close();self.temp.cleanup()

    def qualify(self, guard=lambda:None):
        return qualify_sidecar_source(self.path,self.point,self.sidecars,self.request,self.report,guard=guard)

    def test_unchanged_WAL_preserves_old_API_epoch_and_requires_native_proof(self):
        old = copy.deepcopy(self.point)
        result = self.qualify()
        self.assertTrue(result['eligible_unchanged_SQL_reuse'])
        self.assertEqual(result['accepted_API_point_at'],self.point['original_source_API_point_at'])
        self.assertFalse(result['new_API_epoch_claimed'])
        self.assertFalse(result['backup_acceptance_claimed'])
        self.assertTrue(result['baseline_independent_restore_and_native_B_acceptance_required'])
        self.assertEqual(self.point,old)

    def test_actual_kernel_CLOSE_WRITE_without_write_is_eligible(self):
        lib=ctypes.CDLL(None,use_errno=True);lib.inotify_init1.argtypes=[ctypes.c_int];lib.inotify_add_watch.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_uint32]
        fd=lib.inotify_init1(os.O_NONBLOCK|os.O_CLOEXEC)
        self.assertGreaterEqual(fd,0)
        try:
            wal=Path(str(self.path)+'-wal');self.assertGreaterEqual(lib.inotify_add_watch(fd,os.fsencode(wal),0xfce),0)
            handle=os.open(wal,os.O_RDWR);os.close(handle)
            raw=os.read(fd,8192);mask=0
            while raw:
                _,event,_,length=struct.unpack('iIII',raw[:16]);mask|=event;raw=raw[16+length:]
            self.assertEqual(mask,0x8)
            self.report['events'][str(wal)]=mask
            self.assertTrue(self.qualify()['eligible_unchanged_SQL_reuse'])
        finally:os.close(fd)

    def test_real_committed_WAL_change_refuses_even_when_main_stays_same(self):
        before=fingerprint(self.path.stat())
        self.writer.execute('update sample set value=?',('b'*4096,));self.writer.commit()
        self.assertEqual(fingerprint(self.path.stat()),before)
        self.assertFalse(self.qualify()['eligible_unchanged_SQL_reuse'])

    def test_any_real_data_or_namespace_event_refuses_even_equal_current_metadata(self):
        for mask in [0x2,0x4,0xa,0x40,0x80,0x100,0x200,0x400]:
            self.report['events'][str(self.path)+'-wal']=mask
            with self.subTest(mask=mask):self.assertFalse(self.qualify()['eligible_unchanged_SQL_reuse'])

    def test_new_rollback_journal_refuses(self):
        Path(str(self.path)+'-journal').touch()
        self.assertFalse(self.qualify()['eligible_unchanged_SQL_reuse'])

    def test_same_size_WAL_rewrite_with_restored_mtime_refuses(self):
        wal=Path(str(self.path)+'-wal');before=wal.stat()
        lib=ctypes.CDLL(None,use_errno=True)
        lib.inotify_init1.argtypes=[ctypes.c_int]
        lib.inotify_add_watch.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_uint32]
        fd=lib.inotify_init1(os.O_NONBLOCK|os.O_CLOEXEC)
        self.assertGreaterEqual(fd,0)
        try:
            self.assertGreaterEqual(lib.inotify_add_watch(fd,os.fsencode(wal),0xfce),0)
            with wal.open('r+b') as stream:stream.seek(64);stream.write(b'x')
            os.utime(wal,ns=(before.st_atime_ns,before.st_mtime_ns))
            self.assertEqual(wal.stat().st_size,before.st_size)
            self.assertEqual(wal.stat().st_mtime_ns,before.st_mtime_ns)
            # tmpfs ctime can share a timestamp tick. Use the actual complete
            # kernel report rather than falsely reporting CLOSE_WRITE alone.
            raw=os.read(fd,8192);mask=0
            while raw:
                _,event,_,length=struct.unpack('iIII',raw[:16]);mask|=event;raw=raw[16+length:]
            self.assertTrue(mask & 0x2)
            self.report['events'][str(wal)]=mask
            self.assertFalse(self.qualify()['eligible_unchanged_SQL_reuse'])
        finally:os.close(fd)

    def test_unstable_API_or_missing_independent_proof_refuses(self):
        old=copy.deepcopy(self.point)
        for change in [dict(source_changed_online=True),dict(independent={}),dict(SQL_cohort_id='e'*64)]:
            self.point=dict(old,**change)
            with self.subTest(change=change):self.assertFalse(self.qualify()['eligible_unchanged_SQL_reuse'])

    def test_wrong_epoch_gap_or_missing_before_capture_history_refuses(self):
        old=copy.deepcopy(self.report)
        for change in [dict(instance='e'*32),dict(since=101),dict(ready=False),dict(errors=['overflow']),dict(barrier={})]:
            self.report=dict(old,**change)
            with self.subTest(change=change):self.assertFalse(self.qualify()['eligible_unchanged_SQL_reuse'])

    def test_sidecar_change_during_observation_refuses(self):
        calls=0
        def guard():
            nonlocal calls
            calls+=1
            if calls==2:os.utime(Path(str(self.path)+'-wal'),None)
        self.assertFalse(self.qualify(guard=guard)['eligible_unchanged_SQL_reuse'])

    def test_mandatory_database_cannot_reuse(self):
        self.request['always_SQL_API_sources']=[str(self.path)]
        self.request['cohort_id']=hashlib.sha256(canonical({k:v for k,v in self.request.items() if k!='cohort_id'})).hexdigest()
        self.point['SQL_cohort_id']=self.request['cohort_id']
        self.assertFalse(self.qualify()['eligible_unchanged_SQL_reuse'])


if __name__=='__main__':unittest.main()
