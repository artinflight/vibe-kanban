"""Real bounded normal decoding/provider leases; no B transport or source scan."""
import base64
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sqlite3
import sys
import tempfile
import time
import unittest
import zipfile
import zlib

from vk_nightly_selected_reader import qualify, held, checksum, send
from vk_nightly_selected_recovery import Reader, LOADER
from vk_nightly_typed_worker import source_closure, host_guard, ResourceDeferred
from vk_nightly_current_map import encode_member


def sha(body):return hashlib.sha256(body).hexdigest()


class SelectedRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir='/dev/shm');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.layer=self.root/'provider';self.layer.mkdir();lease=self.layer/'READ.lease';lease.touch()
        self.source='/home/state';name='home/state/aa/aa000000-0000-0000-0000-000000000000/processes/bb000000-0000-0000-0000-000000000000.jsonl';self.body=(b'closed original\n'*10000)
        packed=zlib.compress(self.body);(self.layer/'body.zlib').write_bytes(packed)
        self.segment=dict(layer='retained',selector='body.zlib',encoding='zlib',bytes=len(self.body),sha256=sha(self.body),encoded_bytes=len(packed),encoded_sha256=sha(packed))
        meta=dict(uid=os.getuid(),gid=os.getgid(),mode=0o664,mtime_ns=123456789,xattrs={})
        self.row=dict(meta,kind='file',bytes=len(self.body),sha256=sha(self.body),segments=[self.segment])
        self.request=dict(source_root=self.source,files=[dict(relative='aa/aa000000-0000-0000-0000-000000000000/processes/bb000000-0000-0000-0000-000000000000.jsonl',normal_namespace_name=name,bytes=len(self.body),sha256=sha(self.body),Linux_metadata=dict(meta,atime_ns=999))])
        record=dict(member=self.row,qualification=dict(source='/'+name,state='qualified-retained-body',row=self.row))
        info=self.layer.stat();self.packet=dict(request=self.request,request_sha256=checksum(self.request),rows={name:record},dependencies={'retained':{'proof':'independently pinned'}},provider_placement=dict(roots={'retained':str(self.layer)},root_bindings={'retained':[info.st_dev,info.st_ino]},lease_paths={'retained':str(lease)},expected_uid=os.getuid(),expected_gid=os.getgid()),deadline_epoch=time.time()+30,memory_floor_bytes=1024**2,swap_floor_bytes=0)
        self.freeze(self.packet)

    def freeze(self,packet):
        path=self.layer/'selected.sqlite'
        with sqlite3.connect(path) as db:
            db.execute('create table if not exists selected_recovery_request(format text,request_sha256 text)')
            db.execute('create table if not exists selected_recovery_members(name text primary key,row blob)')
            db.execute('delete from selected_recovery_request');db.execute('delete from selected_recovery_members')
            db.execute('insert into selected_recovery_request values(?,?)',('vk-nightly-selected-original-versions-v1',packet['request_sha256']))
            db.executemany('insert into selected_recovery_members values(?,?)',[(name,encode_member(row)) for name,row in packet['rows'].items()])
        packet['index_reference']=dict(layer='retained',selector=path.name,bytes=path.stat().st_size,sha256=sha(path.read_bytes()))

    def test_exact_selected_content_has_no_complete_set_verified_flag(self):
        with held(self.packet,lambda:None) as h:
            self.assertFalse(hasattr(h,'verified'))
            self.assertEqual(b''.join(h.blocks('home/state/aa/aa000000-0000-0000-0000-000000000000/processes/bb000000-0000-0000-0000-000000000000.jsonl')),self.body)

    def test_exact_metadata_version_namespace_and_dependency_rejections(self):
        variants=[]
        for field,value in [('sha256','0'*64),('bytes',1),('uid',333),('mtime_ns',1)]:
            p=copy.deepcopy(self.packet)
            if field in ('uid','mtime_ns'):p['request']['files'][0]['Linux_metadata'][field]=value
            else:p['request']['files'][0][field]=value
            p['request_sha256']=checksum(p['request']);variants.append(p)
        p=copy.deepcopy(self.packet);p['dependencies']={'wrong':{}};p['provider_placement']['roots']={'wrong':str(self.layer)};variants.append(p)
        for p in variants:
            with self.subTest(p=p['request']['files'][0]):
                with self.assertRaises((ValueError,KeyError)):
                    with held(p,lambda:None):pass

    def test_corrupt_encoded_body_and_wrong_whole_hash_fail(self):
        with held(self.packet,lambda:None) as h:
            (self.layer/'body.zlib').write_bytes(b'wrong')
            with self.assertRaises((ValueError,zlib.error)):list(h.blocks('home/state/aa/aa000000-0000-0000-0000-000000000000/processes/bb000000-0000-0000-0000-000000000000.jsonl'))
        (self.layer/'body.zlib').write_bytes(zlib.compress(self.body))
        p=copy.deepcopy(self.packet);p['rows']['home/state/aa/aa000000-0000-0000-0000-000000000000/processes/bb000000-0000-0000-0000-000000000000.jsonl']['member']['sha256']='1'*64
        # qualification and member share no identity after deepcopy mutation;
        # update the independently supplied request to test full-body mismatch.
        p['request']['files'][0]['sha256']='1'*64;p['request_sha256']=checksum(p['request']);self.freeze(p)
        with held(p,lambda:None) as h:
            with self.assertRaisesRegex(ValueError,'whole-body'):list(h.blocks('home/state/aa/aa000000-0000-0000-0000-000000000000/processes/bb000000-0000-0000-0000-000000000000.jsonl'))

    def test_provider_lease_replacement_and_ended_context_fail(self):
        with self.assertRaisesRegex(ValueError,'lease replaced'):
            with held(self.packet,lambda:None) as h:
                lease=self.layer/'READ.lease';lease.rename(self.layer/'preserved.lease');lease.touch()
                h.check()
        with self.assertRaisesRegex(ValueError,'lease has ended'):h.check()

    def test_raw_and_zip_normal_decoders(self):
        (self.layer/'raw').write_bytes(self.body)
        for codec in ['raw','zip-member']:
            p=copy.deepcopy(self.packet);s=p['rows']['home/state/aa/aa000000-0000-0000-0000-000000000000/processes/bb000000-0000-0000-0000-000000000000.jsonl']['member']['segments'][0]
            if codec=='raw':s.clear();s.update(layer='retained',selector='raw',bytes=len(self.body),sha256=sha(self.body))
            else:
                path=self.layer/'member.zip'
                with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:z.writestr('original',self.body)
                raw=path.read_bytes();s.update(encoding=codec,selector=path.name,member='original',encoded_bytes=len(raw),encoded_sha256=sha(raw))
            self.freeze(p)
            with held(p,lambda:None) as h:self.assertEqual(b''.join(h.blocks('home/state/aa/aa000000-0000-0000-0000-000000000000/processes/bb000000-0000-0000-0000-000000000000.jsonl')),self.body)

    def test_wrong_placement_and_request_hash_rejected(self):
        p=copy.deepcopy(self.packet);p['provider_placement']['root_bindings']['retained'][1]+=1
        with self.assertRaisesRegex(ValueError,'placement changed'):
            with held(p,lambda:None):pass
        p=copy.deepcopy(self.packet);p['request_sha256']='f'*64
        with self.assertRaisesRegex(ValueError,'request differs'):
            with held(p,lambda:None):pass

    def client(self, in_memory=False):
        module=Path(__file__).with_name('vk_nightly_selected_reader.py')
        argv=[sys.executable,'-B','-S','-u','-c',LOADER] if in_memory else [sys.executable,'-B','-S',str(module),checksum(self.packet)]
        process=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        def cleanup():
            for pipe in (process.stdin,process.stdout):
                if not pipe.closed:pipe.close()
            try:process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill();process.wait(timeout=3)
            if not process.stderr.closed:process.stderr.close()
        self.addCleanup(cleanup)
        if in_memory:
            sources={}
            for filename in source_closure(module.parent,'vk_nightly_selected_reader'):
                code=(module.parent/filename).read_text();sources[filename[:-3]]=dict(source=code,sha256=sha(code.encode()))
            send(process.stdin,dict(sources=sources,packet_sha256=checksum(self.packet)))
        send(process.stdin,self.packet)
        class DB:
            def execute(inner,query,params):
                class Cursor:
                    def fetchone(inner):return (encode_member(self.packet['rows'][params[0]]),)
                return Cursor()
        client=Reader(process,{'home/state/aa/aa000000-0000-0000-0000-000000000000/processes/bb000000-0000-0000-0000-000000000000.jsonl':self.row},DB(),lambda:None)
        self.assertEqual(client.receive(),dict(ready=True,protocol=1,packet_sha256=checksum(self.packet)))
        return client,process

    def test_real_protocol_complete_EOF_check_and_close(self):
        client,p=self.client();self.assertEqual(b''.join(client.blocks('home/state/aa/aa000000-0000-0000-0000-000000000000/processes/bb000000-0000-0000-0000-000000000000.jsonl')),self.body)
        self.assertEqual(len(client.completed),1);client.check();client.send(dict(op='close'));self.assertEqual(client.receive(),dict(closed=True));p.stdin.close();self.assertEqual(p.wait(timeout=3),0);p.stdout.close();p.stderr.close()

    def test_actual_pinned_in_memory_bootstrap_and_normal_decoder(self):
        client,p=self.client(in_memory=True)
        self.assertEqual(b''.join(client.blocks('home/state/aa/aa000000-0000-0000-0000-000000000000/processes/bb000000-0000-0000-0000-000000000000.jsonl')),self.body)
        client.check();client.send(dict(op='close'));self.assertEqual(client.receive(),dict(closed=True))
        p.stdin.close();self.assertEqual(p.wait(timeout=3),0)

    def test_consumer_no_total_heuristic_preserves_real_resource_and_owner_deadline(self):
        c=dict(format='vk-nightly-typed-worker-B-v1',root_floor_bytes=0,
            control_margin_bytes=0,memory_floor_bytes=0,swap_floor_bytes=0,timeout_seconds=None)
        host_guard(c,-10**12)
        with self.assertRaisesRegex(ResourceDeferred,'finite worker phase'):
            host_guard(dict(c,timeout_seconds=1),-10**12)
        with self.assertRaisesRegex(ResourceDeferred,'whole-cycle deadline'):
            host_guard(dict(c,whole_cycle_deadline_UTC='2000-01-01T00:00:00+00:00'),-10**12)
        with self.assertRaisesRegex(ResourceDeferred,'memory/swap'):
            host_guard(dict(c,memory_floor_bytes=10**30),-10**12)

    def test_source_pinned_memory_reader_without_agent_total_timeout(self):
        self.packet['deadline_epoch']=None
        client,p=self.client(in_memory=True)
        self.assertEqual(b''.join(client.blocks('home/state/aa/aa000000-0000-0000-0000-000000000000/processes/bb000000-0000-0000-0000-000000000000.jsonl')),self.body)
        client.check();client.send(dict(op='close'));self.assertEqual(client.receive(),dict(closed=True))
        p.stdin.close();self.assertEqual(p.wait(timeout=3),0)

    def test_partial_body_poisoned_and_no_completion(self):
        client,p=self.client();body=client.blocks('home/state/aa/aa000000-0000-0000-0000-000000000000/processes/bb000000-0000-0000-0000-000000000000.jsonl');next(body);body.close()
        self.assertEqual(client.completed,[])
        with self.assertRaisesRegex(ValueError,'incomplete selected body'):client.check()
        p.stdin.close();p.stdout.close();self.assertNotEqual(p.wait(timeout=3),0);p.stderr.close()

    def test_protocol_corruption_and_truncation_fail_closed(self):
        for wire in [b'{"data":"badbase64"}\n',b'{"eof":true,"bytes":1,"sha256":"bad"}\n']:
            with self.subTest(wire=wire):
                class P:pass
                p=P();p.stdin=io.BytesIO();p.stdout=io.BytesIO();p.poll=lambda:0
                r=Reader(p,{'x':self.row},None,lambda:None);r.entry=lambda _:self.row
                replies=iter([dict(opened=True,name='x',bytes=self.row['bytes'],sha256=self.row['sha256']),json.loads(wire)])
                r.receive=lambda:next(replies)
                with self.assertRaises((ValueError,StopIteration)):list(r.blocks('x'))
                self.assertTrue(r.poisoned);self.assertEqual(r.completed,[])


if __name__=='__main__':unittest.main()
