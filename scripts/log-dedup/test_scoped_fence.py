import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import io
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import uuid

import controller
import log_dedup as logs
import reclaim
from scoped_fence import ClosedLogFence, WriterRoster
from test_reclaim import Recovery


class ScopedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='vk-scoped-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base/'sessions'; self.root.mkdir()
        self.workspace = str(uuid.uuid4()); self.session = str(uuid.uuid4())
        self.names = [f'{self.session[:2]}/{self.session}/processes/{uuid.uuid4()}.jsonl' for _ in range(3)]
        self.original = b'{"Stdout":"exact history"}\n' * 10000
        for name in self.names:
            p = self.root/name; p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(self.original); p.chmod(0o600)
            p.with_suffix('.capture.json').write_text('{"capture_state":"closed"}\n')
        self.db = self.base/'db.sqlite'
        with sqlite3.connect(self.db) as conn:
            conn.executescript('CREATE TABLE sessions(id BLOB PRIMARY KEY, workspace_id BLOB); CREATE TABLE execution_processes(id BLOB PRIMARY KEY, session_id BLOB, status TEXT, completed_at TEXT); CREATE TABLE saved_inputs(body TEXT); INSERT INTO saved_inputs VALUES("preserve pending input");')
            conn.execute('INSERT INTO sessions VALUES(?,?)',(uuid.UUID(self.session).bytes,uuid.UUID(self.workspace).bytes))
            for i,name in enumerate(self.names):
                conn.execute('INSERT INTO execution_processes VALUES(?,?,?,?)',(uuid.UUID(Path(name).stem).bytes,uuid.UUID(self.session).bytes,'running' if i==2 else 'completed',None if i==2 else 'closed'))
        (self.root/self.names[2]).with_suffix('.capture.json').write_text('{"capture_state":"pending"}\n')
        self.plan=logs.scan(self.root,self.names[:2]); self.archive=self.base/'archive'; logs.pack(self.plan,self.archive)
        self.store=Recovery(self.root)
        # Synthetic roster only for unit tests. Cross-language tests below use
        # real /proc identity, binary hashing and --build-info probing.
        self.roster=WriterRoster([{'pid':os.getpid(),'sha256':'0'*64}],lambda:None)
        self.roster.qualify=lambda:None; self.roster.check=lambda:None
        self.fence=self.make_fence()

    def make_fence(self, **overrides):
        values=dict(root=self.root,database=self.db,workspace_id=self.workspace,plan=self.plan,roster=self.roster)
        values.update(overrides); return ClosedLogFence(**values)

    def batch(self):
        return reclaim.Batch(self.plan,self.archive,self.base/'journal',self.fence,self.store,lambda:None,reserve_bytes=0)

    def test_other_execution_and_pending_input_continue_during_install_and_rollback(self):
        current=self.root/self.names[2]
        with current.open('ab') as writer, self.fence.held():
            writer.write(b'new work\n');writer.flush()
            with sqlite3.connect(self.db) as conn:conn.execute('INSERT INTO saved_inputs VALUES("new input")')
            old_reader=(self.root/self.names[0]).open('rb')
            try:
                self.assertTrue(self.batch().run()['complete'])
                self.assertEqual(old_reader.read(),self.original)
                for name in self.names[:2]:self.assertEqual(logs.reconstruct(self.root/name)['sha256'],logs.sha(self.original))
                writer.write(b'more work\n');writer.flush()
                self.assertTrue(self.batch().run(rollback=True)['complete'])
            finally:old_reader.close()
        self.assertTrue(current.read_bytes().endswith(b'new work\nmore work\n'))
        with sqlite3.connect(self.db) as conn:self.assertEqual(conn.execute('SELECT COUNT(*) FROM saved_inputs').fetchone()[0],2)

    def test_active_pending_missing_closure_and_wrong_workspace_are_rejected(self):
        for kind in ('active','pending','missing','workspace'):
            with self.subTest(kind=kind):
                target=self.root/self.names[0];side=target.with_suffix('.capture.json');before=side.read_bytes()
                with sqlite3.connect(self.db) as conn:
                    conn.execute("UPDATE execution_processes SET status='completed',completed_at='closed' WHERE id=?",(uuid.UUID(target.stem).bytes,))
                    if kind=='active':conn.execute("UPDATE execution_processes SET status='running' WHERE id=?",(uuid.UUID(target.stem).bytes,))
                if kind=='pending':side.write_text('{"capture_state":"pending"}')
                if kind=='missing':side.unlink()
                fence=self.make_fence(workspace_id=str(uuid.uuid4())) if kind=='workspace' else self.fence
                with self.assertRaises(ValueError):
                    with fence.held():pass
                side.write_bytes(before)
        self.assertEqual((self.root/self.names[0]).read_bytes(),self.original)

    def test_busy_lock_releases_earlier_locks_without_waiting(self):
        busy=(self.root/sorted(self.names[:2])[-1]).with_suffix('.mutation.lock')
        busy.touch(mode=0o600)
        with busy.open('rb') as held:
            fcntl.flock(held,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                with self.fence.held():pass
        self.assertFalse(self.fence.locks)
        with self.fence.held():self.fence.check()

    def test_unheld_fence_or_foreign_lock_inode_cannot_authorize(self):
        with self.assertRaisesRegex(ValueError,'retained execution'):self.batch().run()
        with self.assertRaisesRegex(ValueError,'inode changed'):
            with self.fence.held():
                p=(self.root/self.names[0]).with_suffix('.mutation.lock')
                foreign=p.with_suffix('.foreign');foreign.touch(mode=0o600);foreign.replace(p)
                self.batch().run()
        self.assertEqual((self.root/self.names[0]).read_bytes(),self.original)

    def test_foreign_member_cannot_be_added_to_held_plan(self):
        with self.fence.held():
            self.batch().run()
            with self.assertRaisesRegex(ValueError,'outside held'):
                self.fence.validate_entry(dict(self.plan['files'][0],path=self.names[2]))

    def test_crash_after_publication_reacquires_locks_and_resumes_or_restores(self):
        def crash(_):raise RuntimeError('crash')
        with self.assertRaises(RuntimeError):
            with self.fence.held():self.batch().run(after_replace=crash)
        self.assertFalse(self.fence.locks)
        with self.fence.held():self.assertTrue(self.batch().run()['complete'])
        with self.fence.held():self.assertTrue(self.batch().run(rollback=True)['complete'])
        for name in self.names[:2]:self.assertEqual((self.root/name).read_bytes(),self.original)

    def test_backup_corruption_never_replaces_log(self):
        self.store.corrupt=True
        with self.fence.held():
            with self.assertRaises(ValueError):self.batch().run()
        for name in self.names[:2]:self.assertEqual((self.root/name).read_bytes(),self.original)

    def test_owner_loss_aborts_and_releases_only_scoped_locks(self):
        def lost():raise ValueError('owner changed')
        with self.assertRaisesRegex(ValueError,'owner changed'):
            with self.fence.held():
                self.roster.check=lost;self.batch().run()
        self.assertFalse(self.fence.locks)

    def test_online_controller_requires_online_adapter_without_calling_global_admission(self):
        @contextmanager
        def admit_online(config,plan,rollback=False):
            archive=self.archive
            class Provider:
                location='desktop:B:/vk-backups/synthetic-scoped-archive'
                @contextmanager
                def open_member(self,relative,sha):
                    yield io.BytesIO((archive/relative).read_bytes())
            with self.fence.held():yield dict(writer_fence=self.fence,recovery=self.store,archive_recovery=Provider(),reader_guard=lambda:None,reserve_bytes=0)
        class Adapter:
            def admit(*args,**kwargs):raise AssertionError('global pause path must never be called')
        adapter=Adapter();adapter.admit_online=admit_online
        plan=self.base/'plan';plan.write_text(json.dumps(self.plan));cfg=self.base/'cfg';cfg.write_text('{}')
        args=argparse.Namespace(plan=plan,config=cfg,adapter=self.base/'adapter',adapter_sha256='0'*64,archive=self.archive,journal=self.base/'journal',rollback=False,online=True)
        with patch('controller.load_adapter',return_value=adapter):self.assertTrue(controller.run(args)['complete'])

    def test_online_corrupt_archive_backup_blocks_before_replacing_any_log(self):
        class Provider:
            location='desktop:B:/vk-backups/synthetic-scoped-archive'
            @contextmanager
            def open_member(self,relative,sha):yield io.BytesIO(b'corrupt')
        @contextmanager
        def admit_online(config,plan,rollback=False):
            with self.fence.held():yield dict(writer_fence=self.fence,recovery=self.store,archive_recovery=Provider(),reader_guard=lambda:None,reserve_bytes=0)
        class Adapter:pass
        adapter=Adapter();adapter.admit_online=admit_online
        plan=self.base/'plan';plan.write_text(json.dumps(self.plan));cfg=self.base/'cfg';cfg.write_text('{}')
        args=argparse.Namespace(plan=plan,config=cfg,adapter=self.base/'adapter',adapter_sha256='0'*64,archive=self.archive,journal=self.base/'journal',rollback=False,online=True)
        with patch('controller.load_adapter',return_value=adapter):
            with self.assertRaises(ValueError):controller.run(args)
        for name in self.names[:2]:self.assertEqual((self.root/name).read_bytes(),self.original)
        self.assertFalse(self.store.reads)

    @unittest.skipUnless(os.environ.get('VK_LOG_LOCK_PROBE'),'compile actual Rust lock probe first')
    def test_actual_rust_writer_interoperates_and_crash_releases_its_kernel_lock(self):
        executable=Path(os.environ['VK_LOG_LOCK_PROBE'])
        other=self.root/self.names[2]
        process=subprocess.Popen([str(executable),'--hold',str(other)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            self.assertEqual(process.stdout.readline(),b'LOCKED\n')
            roster=WriterRoster([dict(pid=process.pid,sha256=hashlib.sha256(executable.read_bytes()).hexdigest())],lambda:None)
            fence=self.make_fence(roster=roster)
            with fence.held():
                p=subprocess.run([str(executable),'--hold',str(self.root/self.names[0])],input=b'x',capture_output=True,timeout=3)
                self.assertEqual(p.returncode,3)
                batch=self.batch();batch.fence=fence
                self.assertTrue(batch.run()['complete'])
                fence.check()
            process.kill();process.wait(timeout=3)
            with self.assertRaises((ValueError,OSError)):roster.check()
            with other.with_suffix('.mutation.lock').open('rb') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        finally:
            if process.poll() is None:process.kill();process.wait(timeout=3)
            for stream in (process.stdin,process.stdout,process.stderr):stream.close()

    def test_process_death_after_replace_is_recoverable_without_any_global_pause(self):
        pid=os.fork()
        if pid==0:
            try:
                with self.fence.held():self.batch().run(after_replace=lambda _:os._exit(77))
            except BaseException:os._exit(78)
            os._exit(79)
        _,status=os.waitpid(pid,0)
        self.assertEqual(os.waitstatus_to_exitcode(status),77)
        with self.fence.held():self.assertTrue(self.batch().run()['complete'])
        with self.fence.held():self.assertTrue(self.batch().run(rollback=True)['complete'])
        for name in self.names[:2]:self.assertEqual((self.root/name).read_bytes(),self.original)

    @unittest.skipUnless(os.environ.get('VK_LOG_LOCK_PROBE'),'compile actual Rust lock probe first')
    def test_actual_rust_writer_excludes_converter_from_same_log(self):
        executable=Path(os.environ['VK_LOG_LOCK_PROBE'])
        process=subprocess.Popen([str(executable),'--hold',str(self.root/self.names[0])],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            self.assertEqual(process.stdout.readline(),b'LOCKED\n')
            roster=WriterRoster([dict(pid=process.pid,sha256=hashlib.sha256(executable.read_bytes()).hexdigest())],lambda:None)
            with self.assertRaises(BlockingIOError):
                with self.make_fence(roster=roster).held():pass
            self.assertEqual((self.root/self.names[0]).read_bytes(),self.original)
        finally:
            process.kill();process.wait(timeout=3)
            for stream in (process.stdin,process.stdout,process.stderr):stream.close()

    def test_old_writer_capability_is_rejected_before_any_lock_is_created(self):
        roster=WriterRoster([dict(pid=os.getpid(),sha256=hashlib.sha256(Path('/proc/self/exe').read_bytes()).hexdigest())],lambda:None)
        class Reply:stdout=b'{"runtimeIdentityVersion":1}'
        with patch('scoped_fence.subprocess.run',return_value=Reply()):
            with self.assertRaisesRegex(ValueError,'protocol 1'):
                with self.make_fence(roster=roster).held():pass
        self.assertFalse(list(self.root.rglob('*.mutation.lock')))
