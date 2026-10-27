import hashlib
import io
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

from vk_nightly_objects import ObjectClient,ChunkSink,control,read_control,exact,store_lease,retained_SQL_probe


class ObjectTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir='/dev/shm');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.store=self.root/'objects';self.store.mkdir()
        self.children=[];self.addCleanup(self.close_children)

    def close_children(self):
        for p in self.children:
            if p.stdin and not p.stdin.closed:p.stdin.close()
            if p.poll() is None:
                try:p.wait(timeout=3)
                except subprocess.TimeoutExpired:p.kill();p.wait()
            p.stdout.close();p.stderr.close()

    def receiver(self):
        code='import sys;sys.path.insert(0,'+repr(str(Path(__file__).parent))+');from vk_nightly_objects import receive;receive('+repr(str(self.store))+',sys.stdin.buffer,sys.stdout.buffer,guard=lambda n:None,maximum_object_bytes=8192)'
        p=subprocess.Popen([sys.executable,'-B','-u','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.children.append(p);return p

    def client(self,p):return ObjectClient(p.stdout,p.stdin,guard=lambda:None,ram_root=self.root,maximum_object_bytes=8192)

    def test_actual_encoded_disk_reopen_RAM_restore_and_identity_bound_reuse(self):
        p=self.receiver();client=self.client(p);raw=b'complete point\n'*200
        first=client.ensure(raw);sent=client.payload_bytes_sent
        self.assertFalse(first['reused']);self.assertGreater(sent,0)
        self.assertEqual(first['sha256'],hashlib.sha256(raw).hexdigest())
        second=client.ensure(raw)
        self.assertTrue(second['reused']);self.assertEqual(client.payload_bytes_sent,sent)
        self.assertEqual(list(self.root.glob('nightly-object-restore-*')),[])

    def test_ordered_sink_uses_actual_independent_readback_once_for_new_and_reused_objects(self):
        from unittest.mock import patch
        p=self.receiver();client=self.client(p);raw=b'actual independent body'*100
        output=io.BytesIO()
        with patch.object(client,'_restore',wraps=client._restore) as recall:
            client.ensure(raw,readback_sink=output)
            self.assertEqual(output.getvalue(),raw);self.assertEqual(recall.call_count,1)
            output=io.BytesIO();sent=client.payload_bytes_sent
            client.ensure(raw,readback_sink=output)
            self.assertEqual(output.getvalue(),raw);self.assertEqual(recall.call_count,2)
            self.assertEqual(client.payload_bytes_sent,sent)
        client.health()

    def test_interrupted_independent_readback_resumes_same_candidate_no_payload_recopy(self):
        p=self.receiver();raw=b'interrupted point'*200;sha=hashlib.sha256(raw).hexdigest()
        control(p.stdin,dict(sha256=sha,bytes=len(raw)))
        self.assertEqual(read_control(p.stdout)['status'],'send')
        encoded=zlib.compress(raw);p.stdin.write(struct.pack('!I',len(encoded))+encoded+struct.pack('!I',0));p.stdin.flush()
        self.assertEqual(read_control(p.stdout)['status'],'readback');self.assertEqual(exact(p.stdout,len(raw)),raw)
        p.stdin.close();self.assertNotEqual(p.wait(timeout=3),0)
        before=(self.store/(sha+'.zlib')).stat()
        resumed=self.receiver();client=self.client(resumed);client.ensure(raw)
        after=(self.store/(sha+'.zlib')).stat()
        self.assertEqual(client.payload_bytes_sent,0);self.assertEqual(client.candidates_recovered,1)
        self.assertEqual((before.st_ino,before.st_size,before.st_mtime_ns),(after.st_ino,after.st_size,after.st_mtime_ns))

    def test_native_accepted_probe_reuses_exact_receipts_without_payload_or_RAM_copy(self):
        from unittest.mock import patch
        p=self.receiver();client=self.client(p)
        rows=[client.ensure(b'first verified'),client.ensure(b'second verified')]
        before={f.name:(f.stat().st_ino,f.stat().st_size,f.stat().st_mtime_ns) for f in self.store.iterdir()}
        sent=client.payload_bytes_sent
        with patch('vk_nightly_objects.os.statvfs',side_effect=AssertionError('metadata probe allocated scratch')):
            proof=client.probe_accepted([rows[0],rows[1],rows[0]])
        self.assertEqual(proof['objects_verified'],2);self.assertEqual(proof['payload_bytes_read'],0)
        self.assertFalse(proof['fresh_body_decode_claimed']);self.assertTrue(proof['prior_independent_readback_proofs_reused'])
        self.assertEqual(client.payload_bytes_sent,sent)
        self.assertEqual(before,{f.name:(f.stat().st_ino,f.stat().st_size,f.stat().st_mtime_ns) for f in self.store.iterdir()})
        self.assertEqual(list(self.root.glob('nightly-object-restore-*')),[])
        self.assertEqual(client.probe_accepted(rows)['ordered_receipt_set_sha256'],proof['ordered_receipt_set_sha256'])
        client.health() # No unread payload/frame remains on the protocol.

    def test_native_probe_missing_receipt_never_requests_upload_or_creates_candidate(self):
        p=self.receiver();client=self.client(p);sha=hashlib.sha256(b'missing').hexdigest()
        row=dict(layer='nightly-objects-v1',selector=sha+'.zlib',encoding='zlib',bytes=7,
                 sha256=sha,encoded_bytes=15,encoded_sha256='a'*64)
        client.health();before=set(self.store.iterdir())
        with self.assertRaisesRegex(ValueError,'metadata proof unavailable'):client.probe_accepted([row])
        self.assertEqual(client.payload_bytes_sent,0);self.assertEqual(set(self.store.iterdir()),before)

    def test_native_probe_detects_same_length_rewrite_even_with_restored_mtime(self):
        p=self.receiver();client=self.client(p);row=client.ensure(b'accepted body')
        target=self.store/row['selector'];before=target.stat();encoded=target.read_bytes()
        target.write_bytes(bytes([encoded[0]^1])+encoded[1:]);os.utime(target,ns=(before.st_atime_ns,before.st_mtime_ns))
        with self.assertRaisesRegex(ValueError,'metadata proof unavailable'):client.probe_accepted([row])
        self.assertEqual(target.stat().st_size,before.st_size);self.assertEqual(target.stat().st_ino,before.st_ino)
        self.assertNotEqual(target.read_bytes(),encoded)

    def test_native_probe_refuses_changed_encoding_and_candidate_only_proof(self):
        p=self.receiver();client=self.client(p);row=client.ensure(b'accepted point')
        with self.assertRaisesRegex(ValueError,'metadata proof unavailable'):
            client.probe_accepted([dict(row,encoded_sha256='0'*64)])
        # Make a genuine completed candidate, then interrupt before its
        # independent restore acknowledgement. A probe may never adopt it.
        q=self.receiver();raw=b'unaccepted candidate';sha=hashlib.sha256(raw).hexdigest()
        control(q.stdin,dict(sha256=sha,bytes=len(raw)));self.assertEqual(read_control(q.stdout)['status'],'send')
        encoded=zlib.compress(raw);q.stdin.write(struct.pack('!I',len(encoded))+encoded+struct.pack('!I',0));q.stdin.flush()
        self.assertEqual(read_control(q.stdout)['status'],'readback');self.assertEqual(exact(q.stdout,len(raw)),raw)
        q.stdin.close();self.assertNotEqual(q.wait(timeout=3),0)
        candidate=dict(layer='nightly-objects-v1',selector=sha+'.zlib',encoding='zlib',bytes=len(raw),
            sha256=sha,encoded_bytes=len(encoded),encoded_sha256=hashlib.sha256(encoded).hexdigest())
        before={f.name:f.stat().st_ino for f in self.store.iterdir()}
        resumed=self.client(self.receiver())
        with self.assertRaisesRegex(ValueError,'metadata proof unavailable'):resumed.probe_accepted([candidate])
        self.assertEqual({f.name:f.stat().st_ino for f in self.store.iterdir()},before)
        self.assertEqual(resumed.payload_bytes_sent,0)

    def test_probe_validates_entire_batch_before_sending_and_preserves_guard_denials(self):
        from unittest.mock import patch
        p=self.receiver();client=self.client(p);row=client.ensure(b'accepted point')
        for rows in ([],[row]*65,[dict(row,layer='outside')],[row,dict(row,encoded_sha256='0'*64)]):
            with self.assertRaises(ValueError):client.probe_accepted(rows)
        client.health()
        with patch.object(client,'guard',side_effect=PermissionError('actual STOP unreadable')):
            with self.assertRaisesRegex(PermissionError,'STOP unreadable'):client.probe_accepted([row])
        client.health()

    def test_partial_stream_retained_without_accepted_receipt(self):
        p=self.receiver();raw=b'missing finish';sha=hashlib.sha256(raw).hexdigest()
        control(p.stdin,dict(sha256=sha,bytes=len(raw)));self.assertEqual(read_control(p.stdout)['status'],'send')
        p.stdin.write(struct.pack('!I',4)+b'half');p.stdin.flush();p.stdin.close()
        self.assertNotEqual(p.wait(timeout=3),0)
        self.assertEqual(len(list(self.store.glob('*.partial'))),1)
        self.assertFalse((self.store/(sha+'.accepted.json')).exists())

    def test_corrupt_accepted_object_is_not_overwritten_or_reaccepted(self):
        p=self.receiver();client=self.client(p);raw=b'accepted';row=client.ensure(raw)
        target=self.store/(row['sha256']+'.zlib');target.write_bytes(b'corrupt')
        with self.assertRaises(EOFError):client.ensure(raw)
        self.assertEqual(target.read_bytes(),b'corrupt')

    def test_chunker_is_bounded_and_repeated_chunks_reuse_objects(self):
        p=self.receiver();client=self.client(p);sink=ChunkSink(client,chunk_bytes=4096)
        raw=b'a'*4096+b'b'*4096+b'a'*4096
        self.assertEqual(sink.write(raw),len(raw));segments=sink.finish()
        self.assertEqual(len(segments),3);self.assertEqual(client.native_receipts_reused,1)
        self.assertEqual(sum(s['bytes'] for s in segments),len(raw))

    def test_competing_store_lease_and_non_RAM_restore_are_refused(self):
        with store_lease(self.store):
            with self.assertRaises(BlockingIOError):
                with store_lease(self.store):pass
        with self.assertRaisesRegex(ValueError,'tmpfs'):
            ObjectClient(io.BytesIO(),io.BytesIO(),guard=lambda:None,ram_root='/tmp',maximum_object_bytes=8192)

    def test_composed_independent_readback_preserves_order_and_uploads_no_completed_bytes(self):
        p=self.receiver();client=self.client(p);sink=ChunkSink(client,chunk_bytes=4096)
        raw=b'a'*4096+b'b'*4096+b'a'*2048;sink.write(raw);segments=sink.finish()
        uploaded=client.payload_bytes_sent;restored=io.BytesIO()
        for row in segments:client.verify(row,restored)
        self.assertEqual(restored.getvalue(),raw)
        self.assertEqual(client.payload_bytes_sent,uploaded)

    def test_readback_refuses_missing_or_differently_bound_objects(self):
        p=self.receiver();client=self.client(p);row=client.ensure(b'accepted point')
        wrong=dict(row,encoded_sha256='0'*64)
        with self.assertRaisesRegex(ValueError,'binding differs'):client.verify(wrong,io.BytesIO())

    def test_death_after_rename_before_candidate_recovers_exact_body_without_upload(self):
        raw=b'completed before receipt';sha=hashlib.sha256(raw).hexdigest()
        path=self.store/(sha+'.zlib');path.write_bytes(zlib.compress(raw));before=path.stat()
        p=self.receiver();client=self.client(p);client.ensure(raw)
        self.assertEqual(client.payload_bytes_sent,0);self.assertEqual(client.candidates_recovered,1)
        self.assertEqual(path.stat().st_ino,before.st_ino)

    def test_unrecorded_corrupt_body_cannot_be_overwritten_or_accepted(self):
        raw=b'expected';sha=hashlib.sha256(raw).hexdigest();path=self.store/(sha+'.zlib')
        path.write_bytes(zlib.compress(b'corrupt'))
        p=self.receiver();client=self.client(p)
        with self.assertRaises(EOFError):client.ensure(raw)
        self.assertEqual(zlib.decompress(path.read_bytes()),b'corrupt')
        self.assertFalse((self.store/(sha+'.candidate.json')).exists())

    def test_health_creates_no_payload_and_keeps_same_owned_receiver(self):
        p=self.receiver();client=self.client(p);client.health();client.health()
        self.assertEqual(client.payload_bytes_sent,0);self.assertEqual(list(self.store.glob('*.zlib')),[])

    def test_accepted_native_SQL_aliases_reopen_hash_without_copy_or_single_link_assumption(self):
        p=self.store/('sqlite-consistent-'+'a'*32+'.sqlite');p.write_bytes(b'accepted image')
        os.link(p,self.store/'other-alias');before=p.stat();sha=hashlib.sha256(p.read_bytes()).hexdigest()
        expected=[before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns]
        result=retained_SQL_probe(p,expected,allowed_root=self.store,expected_sha256=sha,guard=lambda n:None)
        self.assertEqual(result['sha256'],sha);self.assertEqual(p.stat().st_nlink,2)
        with self.assertRaisesRegex(ValueError,'identity differs'):
            retained_SQL_probe(p,[*expected[:3],0],allowed_root=self.store,expected_sha256=sha,guard=lambda n:None)


if __name__=='__main__':unittest.main()
