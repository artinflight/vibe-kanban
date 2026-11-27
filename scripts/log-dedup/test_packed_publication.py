import copy
import fcntl
import io
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
import uuid

import log_dedup as logs
import packed_objects as packed
import packed_forward
from packed_publication import PackedBatch, PinnedReaders
from scoped_fence import ClosedLogFence, WriterRoster


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='packed-publication-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.root = self.base/'logs'; self.root.mkdir()
        self.workspace, self.session = str(uuid.uuid4()), str(uuid.uuid4())
        self.names = [f'{self.session[:2]}/{self.session}/processes/{uuid.uuid4()}.jsonl' for _ in range(3)]
        self.raw = b'{"Stdout":"exact shared history"}\n'*10000
        for name in self.names:
            p = self.root/name; p.parent.mkdir(parents=True, exist_ok=True); p.parent.chmod(0o700)
            p.write_bytes(self.raw); p.chmod(0o640)
            os.setxattr(p, 'user.dedup-test', b'preserved')
            p.with_suffix('.capture.json').write_text('{"capture_state":"closed"}')
        self.db = self.base/'db.sqlite'
        with sqlite3.connect(self.db) as c:
            c.executescript('CREATE TABLE sessions(id BLOB PRIMARY KEY, workspace_id BLOB); CREATE TABLE execution_processes(id BLOB PRIMARY KEY, session_id BLOB, status TEXT, completed_at TEXT); CREATE TABLE saved_inputs(body TEXT); INSERT INTO saved_inputs VALUES("pending input");')
            c.execute('INSERT INTO sessions VALUES(?,?)',(uuid.UUID(self.session).bytes, uuid.UUID(self.workspace).bytes))
            for name in self.names:
                c.execute('INSERT INTO execution_processes VALUES(?,?,?,?)',(uuid.UUID(Path(name).stem).bytes,uuid.UUID(self.session).bytes,'completed','closed'))
        self.plan = logs.scan(self.root, self.names[:2])
        self.roster = WriterRoster([dict(pid=os.getpid(),sha256='0'*64)],lambda:None)
        self.roster.qualify=lambda:None; self.roster.check=lambda:None
        # Only the unit fixture substitutes process qualification. Execution
        # flock, SQL binding, original inodes and kernel leases remain real.
        self.readers = object.__new__(PinnedReaders); self.readers.check=lambda:None
        self.prepared = self.base/'prepared'
        self.recovery_calls = []

    def make(self, plan=None, prepared=None, journal='journal'):
        plan = plan or self.plan
        fence = ClosedLogFence(root=self.root,database=self.db,workspace_id=self.workspace,plan=plan,roster=self.roster)
        def recovery(sealed):
            self.recovery_calls.append(sealed['plan_sha256'])
            for row in sealed['files']:
                packed.verify((prepared or self.prepared)/Path(row['path']).name)
        return PackedBatch(plan,prepared or self.prepared,self.base/journal,fence,self.readers,recovery,reserve_bytes=0)

    def loose(self):
        archive = self.base/'loose'
        logs.pack(self.plan, archive)
        for row in self.plan['files']:
            path = self.root/row['path']; source = archive/row['path']
            store = path.parent/'.log-objects';store.mkdir(exist_ok=True)
            for obj in (source.parent/'.log-objects').iterdir():
                if not (store/obj.name).exists():(store/obj.name).write_bytes(obj.read_bytes())
            path.write_bytes(source.read_bytes());row['identity']=logs.version(path.stat())
        packed.prepare([self.root/r['path']for r in self.plan['files']], self.prepared)

    def exact(self):
        for row in self.plan['files']:
            p=self.root/row['path'];out=io.BytesIO();packed.verify(p,out)
            self.assertEqual(out.getvalue(),self.raw)
            self.assertEqual(p.stat().st_mode & 0o777,0o640)
            self.assertEqual(os.getxattr(p,'user.dedup-test'),b'preserved')
        self.assertEqual((self.root/self.names[2]).read_bytes(),self.raw)
        with sqlite3.connect(self.db) as c:self.assertEqual(c.execute('SELECT body FROM saved_inputs').fetchall(),[('pending input',)])

    def test_raw_forward_publish_reuses_packs_and_retires_exact_inodes(self):
        proof=packed_forward.prepare(self.plan,self.prepared)
        self.assertEqual(proof['loose_objects_created'],0)
        b=self.make()
        with b.fence.held():
            b.publish();b.retire();self.exact()
        self.assertFalse((b.parent/'.log-objects').exists())
        next_plan=logs.scan(self.root,[self.names[2]])
        next_dir=self.base/'next'
        reused=packed_forward.prepare(next_plan,next_dir,reuse=[self.root/self.names[0]])
        self.assertEqual(reused['new_packs'],0)
        self.assertEqual(packed.load_manifest(next_dir/Path(self.names[2]).name)['packs'],packed.load_manifest(self.root/self.names[0])['packs'])

    def test_lazy_reader_blocks_retirement_then_allows_it(self):
        self.loose();b=self.make();old=(self.root/self.names[0]).open('rb')
        try:
            with b.fence.held():
                b.publish()
                with self.assertRaises(BlockingIOError):b.retire()
                self.assertTrue(list((b.parent/'.log-objects').glob('*.gz')))
                self.assertTrue(old.read().startswith(logs.MAGIC))
        finally:old.close()
        with b.fence.held():b.retire();self.exact()
        self.assertEqual(list((b.parent/'.log-objects').glob('*.gz')),[])

    def test_raw_reader_blocks_original_release(self):
        packed_forward.prepare(self.plan,self.prepared);b=self.make()
        with (self.root/self.names[0]).open('rb') as old,b.fence.held():
            b.publish()
            with self.assertRaises(BlockingIOError):b.retire()
            self.assertEqual(old.read(),self.raw)
        with b.fence.held():b.retire();self.exact()

    def test_partial_publication_resumes_only_the_recorded_inode(self):
        self.loose();b=self.make()
        def crash(phase,path):
            if phase=='manifest_published':raise RuntimeError('simulated crash')
        with b.fence.held():
            with self.assertRaises(RuntimeError):b.publish(crash)
        with b.fence.held():b.publish();b.retire();self.exact()

    def test_crash_after_retaining_original_is_recoverable(self):
        self.loose();b=self.make()
        def crash(phase,path):
            if phase=='original_retained':raise RuntimeError('simulated crash')
        with b.fence.held():
            with self.assertRaises(RuntimeError):b.publish(crash)
        with b.fence.held():b.publish();b.retire();self.exact()

    def test_partial_retirement_reconciles_without_republication(self):
        self.loose();b=self.make()
        def crash(phase,path):
            if phase=='object_retired':raise RuntimeError('simulated crash')
        with b.fence.held():
            b.publish()
            with self.assertRaises(RuntimeError):b.retire(crash)
        with b.fence.held():b.retire();self.exact()

    def test_equal_bytes_foreign_inode_is_not_adopted(self):
        self.loose();b=self.make()
        with b.fence.held():b.publish()
        path=self.root/self.names[0];other=path.with_suffix('.foreign');other.write_bytes(path.read_bytes());other.replace(path)
        with b.fence.held():
            with self.assertRaises(ValueError):b.publish()
            with self.assertRaises(ValueError):b.retire()
        self.assertTrue(list((b.parent/'.log-objects').glob('*.gz')))

    def test_remaining_unselected_manifest_keeps_shared_objects(self):
        self.loose();b=self.make()
        other=self.root/self.names[2];other.write_bytes((self.root/self.names[0]).read_bytes())
        with b.fence.held():b.publish();result=b.retire()
        self.assertGreater(result['objects_kept_for_other_manifests'],0)
        out=io.BytesIO();logs.reconstruct(other,out);self.assertEqual(out.getvalue(),self.raw)

    def test_busy_execution_lock_and_lost_recovery_preserve_originals(self):
        self.loose();b=self.make();p=self.root/self.names[0];before=p.read_bytes()
        lock=p.with_suffix('.mutation.lock');lock.touch(mode=0o600)
        with lock.open('rb') as f:
            fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                with b.fence.held():b.publish()
        def fail(_):raise ValueError('Recovery owner unavailable')
        b.recovery_guard=fail
        with b.fence.held():
            with self.assertRaises(ValueError):b.publish()
        self.assertEqual(p.read_bytes(),before)

    def test_changed_source_metadata_and_pending_capture_are_preserved(self):
        self.loose();b=self.make()
        with b.fence.held():
            with b.locked():b.seal()
        p=self.root/self.names[0];os.setxattr(p,'user.dedup-test',b'new owner metadata')
        with b.fence.held():
            with self.assertRaisesRegex(ValueError,'metadata'):b.publish()
        self.assertEqual(os.getxattr(p,'user.dedup-test'),b'new owner metadata')
        side=p.with_suffix('.capture.json');side.write_text('{"capture_state":"pending"}')
        with self.assertRaises(ValueError):
            with b.fence.held():b.publish()

    def test_open_loose_object_blocks_its_deletion(self):
        self.loose();b=self.make()
        with b.fence.held():b.publish()
        obj=next((b.parent/'.log-objects').glob('*.gz'))
        with obj.open('rb') as reader,b.fence.held():
            with self.assertRaises(BlockingIOError):b.retire()
            self.assertTrue(obj.exists());self.assertTrue(reader.read())
        with b.fence.held():b.retire();self.exact()

    def test_missing_original_pin_after_refused_retirement_cannot_authorize_unlink(self):
        self.loose();b=self.make();old=(self.root/self.names[0]).open('rb')
        try:
            with b.fence.held():
                b.publish()
                with self.assertRaises(BlockingIOError):b.retire()
                pin=b.retained/(Path(self.names[0]).name+'.old');pin.unlink()
                with self.assertRaisesRegex(ValueError,'Missing original pin'):b.retire()
                self.assertTrue(list((b.parent/'.log-objects').glob('*.gz')))
        finally:old.close()

    def test_interrupted_original_release_uses_its_durable_safe_release_receipt(self):
        self.loose();b=self.make()
        def crash(phase,path):
            if phase=='original_retired':raise RuntimeError('simulated crash')
        with b.fence.held():
            b.publish()
            with self.assertRaises(RuntimeError):b.retire(crash)
        with b.fence.held():
            b.retire();self.exact()
            again=b.retire();self.assertTrue(again['originals_released'])
            with self.assertRaises(ValueError):b.publish()

    def test_changed_cas_pack_never_overwrites_existing_bytes(self):
        self.loose();b=self.make();store=b.parent/'.log-packs';store.mkdir()
        name=next((self.prepared/'.log-packs').iterdir()).name;(store/name).write_bytes(b'foreign')
        with b.fence.held():
            with self.assertRaises(ValueError):b.publish()
        self.assertEqual((store/name).read_bytes(),b'foreign')


if __name__=='__main__':unittest.main()
