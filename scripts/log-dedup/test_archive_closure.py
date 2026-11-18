import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

import archive_closure as closure


class ClosureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='vk-complete-closure-')
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base/'source'
        self.process = self.root/'aa/session/processes'
        self.process.mkdir(parents=True)
        self.manifest = self.process/'archived.jsonl'
        self.manifest.write_bytes(b'VKLOGCAS1\n{}')
        self.converted = [str(self.manifest.relative_to(self.root))]

    def test_complete_namespace_includes_raw_adjacent_nested_and_unreferenced(self):
        (self.process/'raw.jsonl').write_bytes(b'preserve raw pending content')
        (self.process/'capture.json').write_bytes(b'{"capture_state":"pending"}')
        (self.process/'adjacent.bin').write_bytes(b'unknown adjacent payload')
        store = self.process/'.log-objects'
        store.mkdir()
        (store/'unreferenced.gz').write_bytes(b'preserve unused object too')
        nested = self.process/'nested'
        nested.mkdir()
        (nested/'more').write_bytes(b'nested payload')
        (self.process/'link').symlink_to('raw.jsonl')
        os.link(self.process/'adjacent.bin',self.process/'second-name')
        layout = closure.closure_layout(self.root,self.converted)
        rows = list(closure.iter_rows(self.root,layout))
        self.assertEqual({r['path'] for r in rows}, {str(p.relative_to(self.root)) for p in self.process.rglob('*') if p.is_file() and not p.is_symlink()})
        self.assertEqual(len(layout['symlinks']),1)
        self.assertEqual(sum('hardlink_to'in r for r in rows),1)
        for number,batch in enumerate(closure.bundles(rows)):
            folder=self.base/str(number);folder.mkdir()
            proof=closure.pack_verify(self.root,batch,folder,lambda:None)
            self.assertEqual(proof['files'],len(batch))
            self.assertTrue(proof['independent_extraction']['passed'])

    def test_large_body_is_fully_restored_across_bounded_carriers(self):
        body = bytes(range(256))*59+b'tail'
        (self.process/'large.jsonl').write_bytes(body)
        layout=closure.closure_layout(self.root,self.converted)
        rows=list(closure.iter_rows(self.root,layout,maximum_body_bytes=4096))
        fragments=closure.FragmentVerifier()
        parts=[r for r in rows if 'source_offset'in r]
        self.assertEqual([r['source_offset'] for r in parts],[0,4096,8192,12288])
        self.assertTrue(all(r['bytes']<=4096 for r in rows))
        for number,batch in enumerate(closure.bundles(rows,maximum=8192)):
            folder=self.base/str(number);folder.mkdir()
            closure.pack_verify(self.root,batch,folder,lambda:None,fragments=fragments)
        self.assertEqual(fragments.finish()['whole_fragmented_files_verified'],1)
        self.assertEqual(parts[0]['source_sha256'],hashlib.sha256(body).hexdigest())

    def test_fragment_gaps_duplicates_and_corruption_fail(self):
        row=dict(path='raw',source_bytes=6,source_sha256=hashlib.sha256(b'abcdef').hexdigest(),source_offset=0,bytes=3,identity=[],metadata={})
        v=closure.FragmentVerifier();v.begin(row);v.update(row,b'abc');v.end(row)
        with self.assertRaisesRegex(ValueError,'Incomplete'):v.finish()
        with self.assertRaisesRegex(ValueError,'reordered'):v.begin(row)
        end=dict(row,source_offset=3)
        v.begin(end);v.update(end,b'bad')
        with self.assertRaisesRegex(ValueError,'differs'):v.end(end)

    def test_substituted_directory_and_special_file_refuse(self):
        os.mkfifo(self.process/'pipe')
        with self.assertRaisesRegex(ValueError,'special'):closure.closure_layout(self.root,self.converted)

    def test_source_change_after_inventory_refuses(self):
        layout=closure.closure_layout(self.root,self.converted)
        rows=list(closure.iter_rows(self.root,layout))
        self.manifest.write_bytes(b'changed')
        folder=self.base/'carrier';folder.mkdir()
        with self.assertRaisesRegex(ValueError,'changed'):closure.pack_verify(self.root,rows,folder,lambda:None)


if __name__=='__main__':
    unittest.main()
