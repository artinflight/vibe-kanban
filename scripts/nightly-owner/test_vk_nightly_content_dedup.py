"""Bounded fixtures only; native B/whole-current acceptance remains separate."""
import hashlib
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import unittest

from vk_nightly_objects import ContentDefinedChunkSink,ObjectClient
from test_vk_nightly_objects import ObjectTests


class MemoryCAS:
    maximum=256*1024
    def __init__(self):self.objects={};self.uploaded=0
    def ensure(self,raw,readback_sink=None):
        key=hashlib.sha256(raw).hexdigest()
        if key not in self.objects:self.objects[key]=raw;self.uploaded+=len(raw)
        if readback_sink is not None:readback_sink.write(self.objects[key])
        return dict(sha256=key,bytes=len(raw),reused=False)


def fixture():
    return b''.join(hashlib.sha256(str(n).encode()).hexdigest().encode()+b'\\n' for n in range(9000))


def capture(client,body,width=65536):
    restored=io.BytesIO();sink=ContentDefinedChunkSink(client,chunk_bytes=1024**2,readback_sink=restored)
    for i in range(0,len(body),width):
        assert sink.write(body[i:i+width])==len(body[i:i+width])
        assert len(sink.buffer)<=256*1024
    rows=sink.finish()
    assert restored.getvalue()==body
    return rows


class ContentDedupTests(unittest.TestCase):
    def test_fragmentation_and_empty_file(self):
        body=fixture();a=capture(MemoryCAS(),body,17);b=capture(MemoryCAS(),body,1024**2)
        self.assertEqual(a,b);self.assertTrue(all(0<r['bytes']<=256*1024 for r in a))
        self.assertEqual(capture(MemoryCAS(),b'')[0]['bytes'],0)

    def test_insertion_resynchronizes_and_repeated_histories_reuse(self):
        c=MemoryCAS();body=fixture();capture(c,body);before=c.uploaded
        capture(c,b'new execution header\\n'+body)
        self.assertLess(c.uploaded-before,len(body)//2)
        before=c.uploaded;capture(c,b'new execution header\\n'+body)
        self.assertEqual(c.uploaded,before)

    def test_exact_shared_VKLOGCAS1_cuts(self):
        source=Path('/home/mcp/code/worktrees/0815-vk-deduplicate-c/_vibe_kanban_repo/scripts/log-dedup/log_dedup.py')
        if not source.exists():self.skipTest('shared owner source unavailable')
        spec=importlib.util.spec_from_file_location('shared_log_cuts',source);shared=importlib.util.module_from_spec(spec);spec.loader.exec_module(shared)
        body=fixture()+b'no-newline-tail';expected=[(hashlib.sha256(b).hexdigest(),len(b)) for b in shared.chunks(io.BytesIO(body))]
        self.assertEqual([(r['sha256'],r['bytes']) for r in capture(MemoryCAS(),body)],expected)

    def test_guards_and_sink_fault_are_not_swallowed(self):
        with self.assertRaises(ValueError):ContentDefinedChunkSink(MemoryCAS(),chunk_bytes=8192)
        class Denied(MemoryCAS):
            def ensure(self,*a,**k):raise PermissionError('actual STOP/access denied')
        with self.assertRaises(PermissionError):capture(Denied(),fixture())


class NativeProtocolDedupTests(unittest.TestCase):
    setUp=ObjectTests.setUp
    close_children=ObjectTests.close_children
    def test_actual_receiver_reopen_restore_resume_without_duplicate_objects(self):
        code='import sys;sys.path.insert(0,'+repr(str(Path(__file__).parent))+');from vk_nightly_objects import receive;receive('+repr(str(self.store))+',sys.stdin.buffer,sys.stdout.buffer,guard=lambda n:None,maximum_object_bytes=262144)'
        p=subprocess.Popen([sys.executable,'-B','-u','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE);self.children.append(p)
        client=ObjectClient(p.stdout,p.stdin,guard=lambda:None,ram_root=self.root,maximum_object_bytes=262144)
        body=fixture();rows=capture(client,body);sent=client.payload_bytes_sent
        second=capture(client,body,4093);self.assertEqual(second,rows);self.assertEqual(client.payload_bytes_sent,sent)
        restore=io.BytesIO()
        for row in rows:client.verify(row,restore)
        self.assertEqual(restore.getvalue(),body);self.assertEqual(client.payload_bytes_sent,sent)
        self.assertGreater(client.native_receipts_reused,0)


class CapturePolicyTests(NativeProtocolDedupTests):
    def test_actual_capture_proof_records_CDC_and_disables_raw_prefetch(self):
        import sqlite3
        from vk_nightly_current_map import CurrentMap,decode_member
        from vk_nightly_namespace import observe
        from vk_nightly_qualification import qualify_file,encode_observation
        from vk_nightly_typed_capture import capture_pending
        body=fixture();source=self.root/'source';source.write_bytes(body)
        journal=dict(ready=True,errors=[],instance='fixture',sequence=1,scope_sha256='a'*64,plan_sha256='b'*64)
        point=qualify_file(source,maximum_bytes=len(body),journal=journal,carriers=lambda *_:[],guard=lambda:None)
        name=str(source)[1:];ns=sqlite3.connect(':memory:');self.addCleanup(ns.close)
        ns.execute('create table namespace(name text primary key,row blob)')
        ns.execute('insert into namespace values(?,?)',(name,encode_observation(observe(source))))
        code='import sys;sys.path.insert(0,'+repr(str(Path(__file__).parent))+');from vk_nightly_objects import receive;receive('+repr(str(self.store))+',sys.stdin.buffer,sys.stdout.buffer,guard=lambda n:None,maximum_object_bytes=262144)'
        p=subprocess.Popen([sys.executable,'-B','-u','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE);self.children.append(p)
        client=ObjectClient(p.stdout,p.stdin,guard=lambda:None,ram_root=self.root,maximum_object_bytes=262144)
        def forbidden(*a,**k):raise AssertionError('raw whole-body prefetch under CDC')
        client.prefetch_small=forbidden
        with CurrentMap.held(self.root/'map.sqlite',binding={'test':'RAM'},create=True) as current:
            current.compile(ns,lambda _:point,SQL_sources=[],checkpoint=lambda:None,maximum_paths=10)
            args=dict(guard=lambda:None,maximum_members=1,maximum_source_bytes=len(body),chunk_bytes=262144,
                      file_chunking='content-defined-v1',small_object_batch_members=16)
            capture_pending(current,client,**args)
            row=decode_member(current.db.execute('select row from members where name=?',(name,)).fetchone()[0])
            self.assertEqual(row['independent_file_proof']['file_chunking'],'content-defined-v1')
            self.assertEqual(row['independent_file_proof']['independent_ordered_B_readback_sha256'],hashlib.sha256(body).hexdigest())
            sent=client.payload_bytes_sent;capture_pending(current,client,**args)
            self.assertEqual(client.payload_bytes_sent,sent)
