import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
import zlib

from vk_nightly_prefix_reader import LINUX_READER,NATIVE_READER,read_prefix


class PrefixReaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir='/dev/shm');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);(self.root/'lease').touch()

    def read(self,segments):
        query=dict(expected_uid=os.getuid(),expected_gid=os.getgid(),accepted_base_root=str(self.root),accepted_base_inode=self.root.stat().st_ino,
                   lease=str(self.root/'lease'),roots={'old':str(self.root)},segments=segments)
        return subprocess.run([sys.executable,'-B','-c',LINUX_READER],input=json.dumps(query).encode()+b'\n',capture_output=True,timeout=10)

    def test_actual_raw_zlib_zip_components_restore_in_exact_order(self):
        segments=[]
        for name,codec,body in [('one','raw',b'old point\n'),('two','zlib',b'later tail\n'),('three','zip-member',b'ZIP tail\n')]:
            p=self.root/name
            if codec=='raw':p.write_bytes(body)
            elif codec=='zlib':p.write_bytes(zlib.compress(body))
            else:
                with zipfile.ZipFile(p,'x') as archive:archive.writestr('kept/member',body)
            row=dict(layer='old',selector=name,encoding=codec,bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
            if codec!='raw':row.update(encoded_bytes=p.stat().st_size,encoded_sha256=hashlib.sha256(p.read_bytes()).hexdigest())
            if codec=='zip-member':row['member']='kept/member'
            segments.append(row)
        result=self.read(segments)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout,b'VK_PREFIX_READY_V1\nold point\nlater tail\nZIP tail\n')

    def test_symlink_traversal_size_and_hash_mismatch_fail_without_other_path_reads(self):
        body=b'kept';(self.root/'one').write_bytes(body)
        row=dict(layer='old',selector='one',bytes=4,sha256=hashlib.sha256(body).hexdigest())
        for bad in [dict(row,selector='../outside'),dict(row,bytes=3),dict(row,sha256='0'*64)]:
            self.assertNotEqual(self.read([bad]).returncode,0)
        (self.root/'alias').symlink_to('one')
        self.assertNotEqual(self.read([dict(row,selector='alias')]).returncode,0)

    def test_native_relay_syntax_and_unbound_reader_refusal(self):
        compile(NATIVE_READER,'native-prefix','exec')
        class Session:config={}
        with self.assertRaisesRegex(ValueError,'exact existing'):read_prefix(Session(),{},None)


if __name__=='__main__':unittest.main()
