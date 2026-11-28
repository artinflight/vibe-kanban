"""Canonical large-index encoding without changing historical candidate limits."""
import hashlib
import io
import json
import unittest
from unittest.mock import patch

import vk_nightly_generation as generation
from vk_nightly_archive_index import NightlyArchiveProvider, validate_backup_entries
from vk_candidate_direct_b import DirectBProvider
from vk_nightly_json import load_index


class IndexEncoding(unittest.TestCase):
    def test_streamed_loader_handles_every_token_and_utf8_boundary(self):
        value={'proof':{'entries':{'a':{'bytes':123456789,'float':1.25e-100,'literal':'é😀','xattrs':{}}}},'ok':True,'extra':None}
        for ascii_only in (True,False):
            raw=json.dumps(value,ensure_ascii=ascii_only,separators=(',',':')).encode()
            for window in (1,2,3,7,64,65536):
                with self.subTest(ascii=ascii_only,window=window):
                    got,checksum=load_index(io.BytesIO(raw),chunk_size=window)
                    self.assertEqual(got,value);self.assertEqual(checksum,hashlib.sha256(raw).hexdigest())

    def test_streamed_loader_rejects_truncation_duplicate_trailing_and_bounds(self):
        for raw in (b'{"entries":{"a":{}}',b'{"entries":{"a":{},"a":{}}}',b'{"entries":{}} {}'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):load_index(io.BytesIO(raw),chunk_size=3)
        with self.assertRaises(ValueError):load_index(io.BytesIO(b'{"entries":{"a":{},"b":{}}}'),maximum_entries=1)
        with self.assertRaises(ValueError):load_index(io.BytesIO(b'{"entries":{}}'),maximum=4)

    def test_separately_decoded_rows_share_only_fixed_schema_vocabulary(self):
        raw=b'{"entries":{"first":{"kind":"file","bytes":1},"second":{"kind":"file","bytes":2}}}'
        value,_=load_index(io.BytesIO(raw),chunk_size=3)
        first,second=value['entries'].values()
        self.assertIs(next(iter(first)),next(iter(second)))
        self.assertIs(first['kind'],second['kind'])

    def test_nested_and_wide_tables_keep_exact_canonical_bytes(self):
        rows = {f'path/{i}': {'kind':'file','sha256':'a'*64,'bytes':i,
                             'xattrs':{},'literal':'é\n"\\'} for i in range(5000)}
        value = {'proof':{'entries':rows},'result':{'parent':None},'list':[[],{},True,1.25]}
        expected = json.dumps(value,sort_keys=True,separators=(',',':')).encode()
        self.assertEqual(generation.encoded(value),expected)
        self.assertEqual(generation.encoding_summary(value),(hashlib.sha256(expected).hexdigest(),len(expected)))

    def test_streamed_metadata_bound_rejects_before_returning_oversized_index(self):
        with patch.object(generation,'MAX_INDEX',128):
            for encode in (generation.encoded,generation.encoding_summary):
                with self.assertRaisesRegex(ValueError,'metadata exceeds'):
                    encode({'rows':{str(i):'payload'*4 for i in range(100)}})

    def test_nightly_budget_is_separate_from_historical_candidate_budget(self):
        provider = NightlyArchiveProvider('a'*64,[],metadata_budget_bytes=512*1024**2)
        self.assertEqual(provider.metadata_budget_bytes,512*1024**2)
        with self.assertRaises(ValueError):
            DirectBProvider('a'*64,[],metadata_budget_bytes=512*1024**2)
        with self.assertRaises(ValueError):
            NightlyArchiveProvider('a'*64,[],metadata_budget_bytes=512*1024**2+1)


if __name__=='__main__':unittest.main()
