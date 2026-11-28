import hashlib
import unittest
from unittest.mock import patch

import test_vk_nightly_typed_capture as fixtures
from vk_nightly_current_map import CurrentMap,decode_member
from vk_nightly_typed_capture import capture_pending


class SmallCaptureTests(unittest.TestCase):
    setUp=fixtures.TypedCaptureTests.setUp
    close=fixtures.TypedCaptureTests.close
    prepare_group=fixtures.TypedCaptureTests.prepare_group

    def capture(self,m,guard=lambda:None,maximum=65536):
        return capture_pending(m,self.client,guard=guard,maximum_members=4,
            maximum_source_bytes=maximum,chunk_bytes=4096,acceptance_batch_members=4,
            small_object_batch_members=4)

    def test_mixed_large_and_small_batch_actual_readback_and_no_repeat_copy(self):
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            self.prepare_group(m);result=self.capture(m)
            self.assertEqual(result['completed_members'],4);self.assertFalse(result['more_pending'])
            self.assertEqual(result['small_object_batches'],1)
            self.assertEqual(result['small_prefetch_source_bytes'],3*4096)
            self.assertEqual(result['source_bytes_read'],12288+2*3*4096)
            self.assertEqual(result['independent_object_readbacks'],6)
            self.assertEqual(result['cached_small_readback_uses'],3)
            self.assertEqual(self.client.small_readback_cache,{})
            for name,raw in m.db.execute('select name,row from members'):
                row=decode_member(raw);proof=row['independent_file_proof'];member=row['member']
                self.assertEqual(proof['independent_ordered_B_readback_sha256'],member['sha256'])
                self.assertEqual(proof['independent_ordered_B_readback_bytes'],member['bytes'])
            sent=self.client.payload_bytes_sent
            self.assertEqual(self.capture(m)['completed_members'],0);self.assertEqual(self.client.payload_bytes_sent,sent)

    def test_group_interruption_preserves_all_pending_rows_and_reuses_every_completed_object(self):
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            self.prepare_group(m)
            def stop():
                if m.db.in_transaction:raise OSError('actual STOP at group commit')
            with self.assertRaisesRegex(OSError,'STOP at group commit'):self.capture(m,guard=stop)
            self.assertEqual(m.db.execute("select count(*) from members where state='file-needs-capture'").fetchone(),(4,))
            before={p.name:p.stat().st_ino for p in self.store.glob('*.zlib')};sent=self.client.payload_bytes_sent
            self.assertEqual(self.capture(m)['completed_members'],4)
            self.assertEqual(self.client.payload_bytes_sent,sent)
            self.assertEqual(before,{p.name:p.stat().st_ino for p in self.store.glob('*.zlib')})

    def test_source_changed_after_B_warmup_never_qualifies_wrong_version(self):
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            self.prepare_group(m);original=self.client.prefetch_small
            def changed(bodies):
                value=original(bodies);self.source.with_name('source-0').write_bytes(b'x'*4096);return value
            with patch.object(self.client,'prefetch_small',side_effect=changed):result=self.capture(m)
            self.assertEqual(result['completed_members'],3);self.assertTrue(result['more_pending'])
            self.assertTrue(result['requires_source_requalification'])
            name=str(self.source.with_name('source-0'))[1:]
            self.assertNotEqual(m.db.execute('select state from members where name=?',(name,)).fetchone()[0],'verified-file')

    def test_existing_source_budget_prevents_optional_double_reads(self):
        with CurrentMap.held(self.path,binding=self.binding,create=True) as m:
            self.prepare_group(m)
            with patch.object(self.client,'prefetch_small',side_effect=AssertionError('optional read exceeded source budget')):
                result=self.capture(m,maximum=23500)
            self.assertEqual(result['completed_members'],3);self.assertTrue(result['more_pending'])
            self.assertEqual(result['small_prefetch_source_bytes'],0)
            self.assertLessEqual(result['source_bytes_read'],23500)


if __name__=='__main__':unittest.main()
