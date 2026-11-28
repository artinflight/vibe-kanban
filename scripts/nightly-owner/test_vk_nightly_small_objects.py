import hashlib
import io
import os
from pathlib import Path
import struct
import subprocess
import sys
import time
import unittest
from unittest.mock import patch
import zlib

import vk_nightly_objects as objects
import test_vk_nightly_objects as fixtures


class SmallBatchTests(unittest.TestCase):
    setUp=fixtures.ObjectTests.setUp
    close_children=fixtures.ObjectTests.close_children
    receiver=fixtures.ObjectTests.receiver
    client=fixtures.ObjectTests.client

    def bodies(self,n=16):return [hashlib.sha256(str(i).encode()).digest()*32 for i in range(n)]

    def send(self,p,bodies,*,persist_candidate=True):
        items=[dict(sha256=hashlib.sha256(b).hexdigest(),bytes=len(b)) for b in bodies]
        objects.control(p.stdin,dict(operation='ensure-small-batch-v1' if persist_candidate else 'ensure-small-batch-v2',objects=items))
        ready=objects.read_control(p.stdout)
        self.assertEqual(ready['status'],'small-batch-ready-v1')
        for raw,new in zip(bodies,ready['send']):
            if new:
                encoded=zlib.compress(raw,1)
                p.stdin.write(struct.pack('!I',len(encoded))+encoded+struct.pack('!I',0))
        p.stdin.flush();header=objects.read_control(p.stdout)
        self.assertEqual(header['status'],'small-batch-readback-v1')
        for raw in bodies:self.assertEqual(objects.exact(p.stdout,len(raw)),raw)
        return items

    def test_actual_batch_independent_disk_decode_RAM_reopen_and_legacy_compatible_reuse(self):
        p=self.receiver();client=self.client(p);bodies=self.bodies()
        result=client.prefetch_small(bodies)
        self.assertEqual(result['objects'],16);self.assertEqual(client.independent_readback_objects,16)
        sent=client.payload_bytes_sent;identities={f.name:f.stat().st_ino for f in self.store.glob('*.zlib')}
        for raw in bodies:
            out=io.BytesIO();row=client.ensure(raw,readback_sink=out)
            self.assertEqual(out.getvalue(),raw);self.assertFalse(row['reused'])
        self.assertEqual(client.payload_bytes_sent,sent);self.assertEqual(client.independent_readback_objects,16)
        self.assertEqual(client.cached_small_readback_uses,16);client.health()
        client.prefetch_small(bodies)
        self.assertEqual(client.payload_bytes_sent,sent);self.assertEqual(client.native_receipts_reused,16)
        self.assertEqual(identities,{f.name:f.stat().st_ino for f in self.store.glob('*.zlib')})
        self.assertEqual(list(self.root.glob('nightly-object-restore-*')),[])
        client.small_readback_cache.clear()
        self.assertTrue(client.ensure(bodies[0])['reused']);self.assertEqual(client.payload_bytes_sent,sent)

    def test_missing_real_independent_ack_preserves_candidates_and_recovers_without_copy(self):
        bodies=self.bodies(3);p=self.receiver();self.send(p,bodies)
        p.stdin.close();self.assertNotEqual(p.wait(timeout=3),0)
        self.assertEqual(len(list(self.store.glob('*.accepted.json'))),0)
        ids={f.name:f.stat().st_ino for f in self.store.glob('*.zlib')}
        client=self.client(self.receiver());client.prefetch_small(bodies)
        self.assertEqual(client.payload_bytes_sent,0);self.assertEqual(client.candidates_recovered,3)
        self.assertEqual(ids,{f.name:f.stat().st_ino for f in self.store.glob('*.zlib')})
        client.health()

    def test_wrong_ack_cannot_accept_any_object(self):
        bodies=self.bodies(2);p=self.receiver();items=self.send(p,bodies)
        objects.control(p.stdin,dict(operation='small-batch-independent-RAM-verified-v1',objects=[]))
        self.assertIsNone(objects.read_control(p.stdout));self.assertNotEqual(p.wait(timeout=3),0)
        self.assertEqual(len(list(self.store.glob('*.accepted.json'))),0)
        self.assertEqual(len(list(self.store.glob('*.candidate.json'))),len(items))

    def test_corrupt_accepted_data_fails_closed_without_overwrite(self):
        p=self.receiver();client=self.client(p);bodies=self.bodies(2);client.prefetch_small(bodies)
        path=self.store/(hashlib.sha256(bodies[0]).hexdigest()+'.zlib');before=path.stat()
        raw=path.read_bytes();path.write_bytes(bytes([raw[0]^1])+raw[1:]);os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns))
        with self.assertRaises(ValueError):client.prefetch_small(bodies)
        self.assertEqual(path.read_bytes(),bytes([raw[0]^1])+raw[1:])
        self.assertEqual(client.small_readback_cache,{})

    def test_bound_validation_and_genuine_guard_denial_do_not_send_payload(self):
        p=self.receiver();client=self.client(p)
        for bodies in ([],self.bodies(17),[b'x'*8193],['not bytes']):
            with self.assertRaises(ValueError):client.prefetch_small(bodies)
        client.health()
        with patch.object(client,'guard',side_effect=PermissionError('actual STOP unreadable')):
            with self.assertRaisesRegex(PermissionError,'STOP unreadable'):client.prefetch_small(self.bodies(2))
        self.assertEqual(client.payload_bytes_sent,0);self.assertEqual(list(self.store.glob('*.zlib')),[])
        client.health()

    def test_duplicate_body_batch_has_one_actual_B_readback_and_bounded_cache(self):
        p=self.receiver();client=self.client(p);raw=b'repeated exact version'
        value=client.prefetch_small([raw]*16)
        self.assertEqual(value['objects'],1);self.assertEqual(client.independent_readback_objects,1)
        self.assertEqual(sum(len(v[1]) for v in client.small_readback_cache.values()),len(raw))
        for _ in range(16):
            out=io.BytesIO();client.ensure(raw,readback_sink=out);self.assertEqual(out.getvalue(),raw)
        client.health()

    def modified_receiver(self,change):
        code=('import sys;sys.path.insert(0,'+repr(str(Path(__file__).parent))+');'
              'import vk_nightly_objects as o\n'+change+'\n'
              'o.receive('+repr(str(self.store))+',sys.stdin.buffer,sys.stdout.buffer,'
              'guard=lambda n:None,maximum_object_bytes=8192)')
        p=subprocess.Popen([sys.executable,'-B','-u','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.children.append(p);return p

    def test_partial_acknowledgement_write_reuses_accepted_and_candidate_identities(self):
        change="""old=o.write_new
count=0
def interrupted(path,value):
 global count
 if str(path).endswith('.accepted.json'):
  count+=1
  if count==2:raise OSError('lost receiver during accepted metadata')
 old(path,value)
o.write_new=interrupted"""
        p=self.modified_receiver(change);client=self.client(p);bodies=self.bodies(3)
        with self.assertRaises(ValueError):client.prefetch_small(bodies)
        self.assertNotEqual(p.wait(timeout=3),0)
        self.assertEqual(len(list(self.store.glob('*.accepted.json'))),1)
        before={f.name:f.stat().st_ino for f in self.store.glob('*.zlib')}
        resumed=self.client(self.receiver());resumed.prefetch_small(bodies)
        self.assertEqual(resumed.payload_bytes_sent,0);self.assertEqual(resumed.native_receipts_reused,1)
        self.assertEqual(resumed.candidates_recovered,2)
        self.assertEqual(before,{f.name:f.stat().st_ino for f in self.store.glob('*.zlib')})

    def test_actual_corrupted_readback_cannot_be_replaced_by_ready_flags(self):
        change="""old=o.decoded
def bad(*args,**kwargs):
 for block in old(*args,**kwargs):
  yield bytes([block[0]^1])+block[1:] if block else block
o.decoded=bad"""
        p=self.modified_receiver(change);client=self.client(p)
        with self.assertRaisesRegex(ValueError,'RAM hash differs'):client.prefetch_small(self.bodies(2))
        self.assertEqual(client.small_readback_cache,{})
        self.assertEqual(len(list(self.store.glob('*.accepted.json'))),0)
        self.assertGreater(len(list(self.root.glob('nightly-object-restore-*'))),0)
        p.stdin.close();p.wait(timeout=3)
        resumed=self.client(self.receiver());resumed.prefetch_small(self.bodies(2))
        self.assertEqual(resumed.payload_bytes_sent,0)

    def test_interrupted_second_upload_does_not_duplicate_first_completed_body(self):
        bodies=self.bodies(2);p=self.receiver()
        items=[dict(sha256=hashlib.sha256(b).hexdigest(),bytes=len(b)) for b in bodies]
        objects.control(p.stdin,dict(operation='ensure-small-batch-v1',objects=items))
        self.assertEqual(objects.read_control(p.stdout)['send'],[True,True])
        encoded=zlib.compress(bodies[0],1)
        p.stdin.write(struct.pack('!I',len(encoded))+encoded+struct.pack('!I',0))
        p.stdin.write(struct.pack('!I',4)+b'half');p.stdin.flush();p.stdin.close()
        self.assertNotEqual(p.wait(timeout=3),0)
        first=self.store/(items[0]['sha256']+'.zlib');inode=first.stat().st_ino
        self.assertEqual(len(list(self.store.glob('*.accepted.json'))),0)
        resumed=self.client(self.receiver());resumed.prefetch_small(bodies)
        self.assertEqual(first.stat().st_ino,inode)
        self.assertEqual(resumed.payload_bytes_sent,len(zlib.compress(bodies[1],1)))
        self.assertGreaterEqual(len(list(self.store.glob('*.partial'))),1)

    def test_control_roundtrips_are_amortized_with_identical_bytes_and_proofs(self):
        original=objects.control;results=[];bodies=self.bodies()
        for batch in (False,True):
            # Separate stores make both trials genuine new-object writes.
            if batch:
                self.store=self.root/'second-store';self.store.mkdir()
            p=self.receiver();client=self.client(p);calls=[]
            def paced(stream,value):
                if stream is p.stdin:calls.append(True);time.sleep(.01)
                return original(stream,value)
            started=time.monotonic()
            with patch.object(objects,'control',side_effect=paced):
                if batch:client.prefetch_small(bodies)
                for raw in bodies:
                    sink=io.BytesIO();client.ensure(raw,readback_sink=sink);self.assertEqual(sink.getvalue(),raw)
            results.append((len(calls),time.monotonic()-started,client.independent_readback_objects))
            client.health()
        self.assertEqual(results[0][0],32);self.assertEqual(results[1][0],3)
        self.assertEqual(results[0][2],results[1][2]);self.assertLess(results[1][1],results[0][1])
        print('small-batch modeled10ms control delay:',results,flush=True)


    def test_v2_keeps_data_and_acceptance_fsync_but_omits_redundant_candidate_write(self):
        change="""import atexit,json
old=o.os.fsync
count=0
def counted(fd):
 global count
 count+=1
 return old(fd)
o.os.fsync=counted
atexit.register(lambda:print(json.dumps(dict(actual_fsync_calls=count)),file=sys.stderr))"""
        bodies=self.bodies(3)
        for persist,expected in ((True,9),(False,6)):
            with self.subTest(persist=persist):
                self.store=self.root/('fsync-'+str(persist));self.store.mkdir()
                p=self.modified_receiver(change);client=self.client(p)
                client.prefetch_small(bodies,persist_candidate=persist)
                self.assertEqual(client.independent_readback_objects,3)
                self.assertEqual(len(list(self.store.glob('*.candidate.json'))),3 if persist else 0)
                self.assertEqual(len(list(self.store.glob('*.accepted.json'))),3)
                # Accepted V2 bytes keep the ORIGINAL legacy public reader path.
                client.small_readback_cache.clear();sent=client.payload_bytes_sent
                self.assertTrue(client.ensure(bodies[0])['reused'])
                self.assertEqual(client.payload_bytes_sent,sent)
                p.stdin.close();self.assertEqual(p.wait(timeout=3),0)
                import json
                self.assertEqual(json.loads(p.stderr.read())['actual_fsync_calls'],expected)

    def test_v2_interruption_before_ACK_recovers_fsynced_orphans_via_legacy_without_recopy(self):
        bodies=self.bodies(3);p=self.receiver();self.send(p,bodies,persist_candidate=False)
        p.stdin.close();self.assertNotEqual(p.wait(timeout=3),0)
        self.assertEqual(list(self.store.glob('*.accepted.json')),[])
        self.assertEqual(list(self.store.glob('*.candidate.json')),[])
        before={f.name:f.stat().st_ino for f in self.store.glob('*.zlib')}
        # Old V1 reader/receiver, unchanged default, independently requalifies
        # actual disk bytes instead of requiring another source upload.
        resumed=self.client(self.receiver());resumed.prefetch_small(bodies)
        self.assertEqual(resumed.payload_bytes_sent,0);self.assertEqual(resumed.candidates_recovered,3)
        self.assertEqual(before,{f.name:f.stat().st_ino for f in self.store.glob('*.zlib')})
        self.assertEqual(len(list(self.store.glob('*.accepted.json'))),3)

    def test_v2_partial_acceptance_and_corruption_remain_fail_closed(self):
        change="""old=o.write_new
count=0
def interrupted(path,value):
 global count
 if str(path).endswith('.accepted.json'):
  count+=1
  if count==2:raise OSError('lost after first durable acceptance')
 old(path,value)
o.write_new=interrupted"""
        p=self.modified_receiver(change);client=self.client(p);bodies=self.bodies(3)
        with self.assertRaises(ValueError):client.prefetch_small(bodies,persist_candidate=False)
        self.assertNotEqual(p.wait(timeout=3),0)
        self.assertEqual(len(list(self.store.glob('*.accepted.json'))),1)
        self.assertEqual(list(self.store.glob('*.candidate.json')),[])
        before={f.name:f.stat().st_ino for f in self.store.glob('*.zlib')}
        resumed=self.client(self.receiver());resumed.prefetch_small(bodies,persist_candidate=False)
        self.assertEqual(resumed.payload_bytes_sent,0);self.assertEqual(resumed.native_receipts_reused,1)
        self.assertEqual(before,{f.name:f.stat().st_ino for f in self.store.glob('*.zlib')})
        path=self.store/(hashlib.sha256(bodies[2]).hexdigest()+'.zlib');raw=path.read_bytes()
        path.write_bytes(bytes([raw[0]^1])+raw[1:])
        with self.assertRaises(ValueError):resumed.prefetch_small(bodies,persist_candidate=False)
        self.assertEqual(resumed.small_readback_cache,{})

    def test_v2_real_RAM_readback_failure_cannot_accept_or_overwrite_data(self):
        change="""old=o.decoded
def corrupt(*args,**kw):
 for block in old(*args,**kw):yield bytes([block[0]^1])+block[1:] if block else block
o.decoded=corrupt"""
        p=self.modified_receiver(change);client=self.client(p)
        with self.assertRaisesRegex(ValueError,'RAM hash differs'):
            client.prefetch_small(self.bodies(2),persist_candidate=False)
        self.assertEqual(list(self.store.glob('*.accepted.json')),[])
        self.assertEqual(list(self.store.glob('*.candidate.json')),[])
        self.assertEqual(len(list(self.store.glob('*.zlib'))),2)
        self.assertGreater(len(list(self.root.glob('nightly-object-restore-*'))),0)


if __name__=='__main__':unittest.main()
