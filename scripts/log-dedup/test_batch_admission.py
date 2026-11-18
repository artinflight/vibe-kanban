import gzip
import os
import unittest

import batch_admission as admission


class BatchAdmissionTests(unittest.TestCase):
    def source(self, size, number):
        return dict(path=str(number), raw_bytes=size, sidecar_bytes=[100])

    def test_expansion_bound_includes_real_incompressible_gzip_and_blocks(self):
        fragment = 4096
        for size in [0, 1, 16384, 16385, 262144, 524289]:
            with self.subTest(size=size):
                data = os.urandom(size)
                chunks = [data[n:n+16384] for n in range(0, size, 16384)]
                physical = sum(((len(gzip.compress(c, mtime=0))+4095)//4096+1)*4096 for c in chunks)
                value = admission.bound(size, [100])
                self.assertGreaterEqual(value['archive_upper_bytes'], physical+4096+4096)
                self.assertGreaterEqual(value['peak_extra_bytes'], 2*physical+size)

    def test_recomputes_capacity_after_each_batch_and_covers_every_source(self):
        sources = [self.source(8*1024**2, n) for n in range(40)]
        peak = admission.bound(sources[0]['raw_bytes'], [100])['peak_extra_bytes']
        reserve = 3*1024**3
        calls = []
        def available():
            calls.append(True)
            return reserve+admission.CONTROL_ALLOWANCE+peak*(1 if len(calls)==1 else 16)
        batches = list(admission.batches(dict(sources=sources), available=available, reserve_bytes=reserve))
        self.assertEqual(len(batches[0]), 1)
        self.assertEqual(len(batches[1]), 16)
        self.assertEqual([n for b in batches for n in b], [r['path'] for r in sources])
        self.assertEqual(len(calls), len(batches))

    def test_reserve_not_spent_and_large_source_not_silently_skipped(self):
        selected = dict(sources=[self.source(300*1024**2, 1)])
        with self.assertRaisesRegex(ValueError, 'headroom'):
            list(admission.batches(selected, available=lambda:3*1024**3+100*1024**2,
                                   reserve_bytes=3*1024**3))

    def test_capacity_drop_between_batches_refuses_before_next_pack(self):
        row = self.source(1024**2, 1)
        peak = admission.bound(row['raw_bytes'], row['sidecar_bytes'])['peak_extra_bytes']
        available = iter([admission.CONTROL_ALLOWANCE+peak, 0])
        iterator = admission.batches(dict(sources=[row,self.source(1024**2,2)]),
                                      available=lambda:next(available), reserve_bytes=0)
        self.assertEqual(next(iterator), ['1'])
        with self.assertRaisesRegex(ValueError, 'headroom'):
            next(iterator)

    def test_includes_sidecar_sizes_and_limits_body_count(self):
        sources = [dict(path=str(n),raw_bytes=1024**2,sidecar_bytes=[100,200]) for n in range(22)]
        batches = list(admission.batches(dict(sources=sources),available=lambda:10*1024**3,reserve_bytes=3*1024**3))
        self.assertEqual([len(b) for b in batches], [10,10,2])


if __name__ == '__main__':
    unittest.main()
