"""Bounded paged-recipe failures; production protocol is exercised separately."""
from contextlib import contextmanager
import copy
import hashlib
import io
import json
import unittest
import zlib

from vk_nightly_recipe_pages import Builder,decode,load,leaves,canonical,MAX_PAGE
from vk_typed_recovery import HeldRecoverySet

class MemoryCAS:
    def __init__(self):self.data={};self.stop=False;self.reads=0
    def check(self):
        if self.stop:raise PermissionError('owner STOP')
    guard=check
    def ensure(self,raw,**kw):
        self.check();sha=hashlib.sha256(raw).hexdigest();body=zlib.compress(raw);self.data[sha+'.zlib']=body
        return dict(layer='nightly-objects-v1',selector=sha+'.zlib',encoding='zlib',bytes=len(raw),sha256=sha,encoded_bytes=len(body),encoded_sha256=hashlib.sha256(body).hexdigest())
    @contextmanager
    def open(self,layer,selector):
        self.check();self.reads+=1
        with io.BytesIO(self.data[selector]) as f:yield f

class PageTests(unittest.TestCase):
    def recipe(self,count=129):
        c=MemoryCAS();b=Builder(c);parts=[]
        for i in range(count):
            raw=(str(i)+';').encode();parts.append(raw);b.add(c.ensure(raw),raw)
        return c,b.finish()[0],b''.join(parts)
    def test_boundaries_restore_in_exact_order_without_expanded_member(self):
        for count in (1,127,128,129,256,16385):
            with self.subTest(count=count):
                c,s,want=self.recipe(count);h=HeldRecoverySet.__new__(HeldRecoverySet);h.provider=c
                self.assertEqual(b''.join(h._segment(s)),want)
                self.assertLess(len(canonical(s)),1024)
    def test_corrupt_missing_page_and_real_stop_fail_closed(self):
        c,s,_=self.recipe();saved=c.data.pop(s['selector'])
        with self.assertRaises(KeyError):list(leaves(c,s))
        c.data[s['selector']]=saved+b'x'
        with self.assertRaises(ValueError):list(leaves(c,s))
        c.data[s['selector']]=saved;c.stop=True
        with self.assertRaisesRegex(PermissionError,'STOP'):list(leaves(c,s))
    def test_reordered_logical_stream_and_wrong_level_fail_normal_full_hash(self):
        c,s,_=self.recipe(2);node=load(c,s);node['children'].reverse()
        raw=canonical(node);obj=c.ensure(raw)
        altered=dict(obj,encoding='recipe-v1',bytes=s['bytes'],sha256=s['sha256'],page_bytes=obj['bytes'],page_sha256=obj['sha256'])
        h=HeldRecoverySet.__new__(HeldRecoverySet);h.provider=c
        with self.assertRaisesRegex(ValueError,'ordered full'):list(h._segment(altered))
        node['level']=2;raw=canonical(node)
        with self.assertRaises(ValueError):decode(dict(altered,page_bytes=len(raw),page_sha256=hashlib.sha256(raw).hexdigest()),raw)
    def test_oversized_page_is_rejected(self):
        c,s,_=self.recipe(1);bad=c.ensure(b'x'*(MAX_PAGE+1))
        s.update(page_bytes=bad['bytes'],page_sha256=bad['sha256'],selector=bad['selector'],encoded_bytes=bad['encoded_bytes'],encoded_sha256=bad['encoded_sha256'])
        with self.assertRaises(ValueError):load(c,s)
    def test_full_decoder_checks_guard_again_on_cached_body(self):
        c=MemoryCAS();b=Builder(c);raw=b'x'*16384
        for _ in range(3):b.add(c.ensure(raw),raw)
        s=b.finish()[0];h=HeldRecoverySet.__new__(HeldRecoverySet);h.provider=c
        it=h._segment(s);self.assertEqual(next(it),raw);c.stop=True
        with self.assertRaisesRegex(PermissionError,'STOP'):next(it)

if __name__=='__main__':unittest.main()
