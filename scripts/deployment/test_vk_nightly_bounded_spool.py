import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from vk_nightly_bounded_spool import held
from vk_nightly_tracking import FORMAT
from vk_nightly_b_tracker import write_health


class BoundedSpoolTests(unittest.TestCase):
    def test_preallocated_spool_survives_Desktop_off_and_health_ENOSPC_then_reopens_exact_cursor(self):
        import errno
        with tempfile.TemporaryDirectory(dir='/dev/shm') as root:
            path=Path(root)/'source.sqlite';cap=256*1024
            binding=dict(format=FORMAT,instance='same-kernel-owner',plan_sha256='a'*64,
                scope_sha256='b'*64,owner_pid=os.getpid())
            with held(path,maximum_bytes=cap,guard=lambda:None) as store:
                store.start(binding)
                def full(*_):raise OSError(errno.ENOSPC,'synthetic optional mirror full')
                for cursor in range(1,6):
                    store.commit(dict(format=FORMAT,instance=binding['instance'],scope_sha256='b'*64,
                        sequence=cursor,since=cursor-1,ready=True,errors=[],changed=['/source/file'],events={'/source/file':2}))
                    write_health(store.db,Path(root)/'status',dict(ready=True,sequence=cursor),mirror=full)
                self.assertEqual(store.report(binding['instance'],0)['sequence'],5)
                self.assertEqual(store.db.execute('pragma journal_mode').fetchone()[0],'persist')
                self.assertEqual(path.stat().st_blocks*512,cap)
                self.assertLessEqual(path.stat().st_size,cap)
                self.assertLessEqual(Path(str(path)+'-journal').stat().st_blocks*512,cap+1024**2)
            with held(path,maximum_bytes=cap,guard=lambda:None) as store:
                value=store.report(binding['instance'],0)
                self.assertEqual(value['changed'],['/source/file']);self.assertEqual(value['sequence'],5)
                self.assertEqual(store.db.execute('pragma integrity_check').fetchall(),[('ok',)])

    def test_fixed_page_ceiling_rejects_overflow_without_unbounded_local_growth(self):
        with tempfile.TemporaryDirectory(dir='/dev/shm') as root:
            path=Path(root)/'source.sqlite';cap=256*1024
            with held(path,maximum_bytes=cap,guard=lambda:None) as store:
                store.db.execute('create table fixture(body blob)')
                with self.assertRaises(sqlite3.OperationalError):store.db.execute('insert into fixture values(zeroblob(?))',(cap*2,))
                self.assertEqual(store.db.execute('select count(*) from fixture').fetchone()[0],0)
                self.assertLessEqual(path.stat().st_size,cap)
                self.assertEqual(store.db.execute('pragma integrity_check').fetchall(),[('ok',)])

    def test_unbounded_spool_is_not_admitted(self):
        with self.assertRaisesRegex(ValueError,'bounded'):
            with held('/dev/shm/not-created',maximum_bytes=64*1024**2,guard=lambda:None):pass

    def test_refused_mount_or_admission_never_creates_fallback_state(self):
        with tempfile.TemporaryDirectory(dir='/dev/shm') as root:
            path=Path(root)/'never-created'
            def denied():raise OSError('mount or physical reservation unavailable')
            with self.assertRaisesRegex(OSError,'reservation'):
                with held(path,maximum_bytes=256*1024,guard=denied):self.fail('not admitted')
            self.assertFalse(path.exists())

    def test_failed_physical_reservation_preserves_cursor_for_next_admission(self):
        import errno
        with tempfile.TemporaryDirectory(dir='/dev/shm') as root:
            path=Path(root)/'source.sqlite';cap=256*1024
            with held(path,maximum_bytes=cap,guard=lambda:None) as store:
                store.start(dict(format=FORMAT,instance='one',plan_sha256='a'*64,scope_sha256='b'*64,owner_pid=os.getpid()))
                store.commit(dict(instance='one',sequence=9,ready=True,errors=[],events={'/source/file':2},changed=['/source/file'],scope_sha256='b'*64))
            with patch('vk_nightly_bounded_spool.reserve',side_effect=OSError(errno.ENOSPC,'synthetic physical exhaustion')):
                with self.assertRaises(OSError):
                    with held(path,maximum_bytes=cap,guard=lambda:None):self.fail('not physically admitted')
            with held(path,maximum_bytes=cap,guard=lambda:None) as store:
                value=store.report('one',0)
                self.assertEqual(value['sequence'],9);self.assertEqual(value['changed'],['/source/file'])
                self.assertEqual(store.db.execute('pragma integrity_check').fetchall(),[('ok',)])

    def test_aliased_journal_is_refused_before_database_creation(self):
        with tempfile.TemporaryDirectory(dir='/dev/shm') as root:
            path=Path(root)/'source.sqlite';victim=Path(root)/'preserved';victim.write_bytes(b'preserved')
            Path(str(path)+'-journal').symlink_to(victim)
            with self.assertRaisesRegex(ValueError,'rollback journal'):
                with held(path,maximum_bytes=256*1024,guard=lambda:None):pass
            self.assertFalse(path.exists());self.assertEqual(victim.read_bytes(),b'preserved')

    def test_only_verified_issued_delivery_releases_old_generations_and_requires_B_prefix(self):
        replica=dict(B_root='B:/vk-backups/source/controls-v1',index_name='forward',checkpoint_sha256='c'*64)
        with tempfile.TemporaryDirectory(dir='/dev/shm') as root:
            with held(Path(root)/'source.sqlite',maximum_bytes=256*1024,guard=lambda:None,replica=replica) as store:
                store.start(dict(format=FORMAT,instance='one',plan_sha256='a'*64,scope_sha256='b'*64,owner_pid=os.getpid()))
                def report(seq,events):return dict(instance='one',sequence=seq,ready=True,errors=[],events=events,changed=list(events),scope_sha256='b'*64)
                store.commit(report(7,{'/old':2,'/same':4}))
                value=store.report('one',0);value['barrier']=dict(durable_sequence=7,kernel_drain_completed=True)
                offered=store.offer(value)
                proof=dict(replica,**offered['delivery'],actual_native_B_reopen_verified=True)
                with self.assertRaises(ValueError):store.acknowledge('one',dict(proof,actual_native_B_reopen_verified=False))
                self.assertEqual(len(store.report('one',0)['changed']),2)
                store.commit(report(8,{'/new':2,'/same':2}))
                self.assertEqual(store.acknowledge('one',proof)['acknowledged'],7)
                self.assertTrue(store.acknowledge('one',proof)['duplicate'])
                with self.assertRaisesRegex(ValueError,'B journal prefix required'):store.report('one',0)
                self.assertEqual(store.report('one',7)['changed'],['/new','/same'])
                self.assertEqual(store.report('one',7)['sequence'],8)
                self.assertEqual(store.db.execute('pragma integrity_check').fetchall(),[('ok',)])
