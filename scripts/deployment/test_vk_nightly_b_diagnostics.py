"""Small regressions for diagnostic bounds and demonstrated Windows fsync bug."""
import ast
from contextlib import closing
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import uuid

import rehearse_vk_nightly_recovery_compression as compression
import rehearse_vk_nightly_sqlite_registered as registered


def native_function(name, namespace):
    tree=ast.parse(compression.NATIVE)
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
    exec(compile(ast.Module(body=[node],type_ignores=[]),'native-helper','exec'),namespace)
    return namespace[name]


class Diagnostics(unittest.TestCase):
    def setUp(self):
        self.root=Path(tempfile.mkdtemp(prefix='diagnostic-test-',dir='/mnt/vk-storage/vk-restart-safeguards-20261009'))
    def test_serial_count_bound_rejects_before_remote_work(self):
        with patch.object(registered,'Resident') as remote:
            for count in (0,6):
                with self.assertRaisesRegex(ValueError,'one to five'):
                    registered.run(self.root,self.root/'missing',self.root/'out',count)
            remote.assert_not_called()
    def test_source_alias_rejected_before_remote_work(self):
        source=self.root/'source';source.write_bytes(b'fixture');alias=self.root/'alias';alias.symlink_to(source)
        with patch.object(registered,'Resident') as remote:
            with self.assertRaisesRegex(ValueError,'canonical'):
                registered.run(self.root,alias,self.root/'out',1)
            remote.assert_not_called()
    def test_parent_alias_rejected_before_remote_work(self):
        directory=self.root/'source-dir';directory.mkdir();(directory/'source').write_bytes(b'fixture')
        alias=self.root/'parent-alias';alias.symlink_to(directory,target_is_directory=True)
        with patch.object(registered,'Resident') as remote:
            with self.assertRaisesRegex(ValueError,'canonical'):
                registered.run(self.root,alias/'source',self.root/'out',1)
            remote.assert_not_called()
    def test_compression_requires_exact_accepted_image_before_transport(self):
        receipt=self.root/'receipt.json';receipt.write_text(json.dumps({'passed':True,'bytes':4734447616,'sha256':'wrong'}))
        with patch.object(compression.subprocess,'run') as remote:
            with self.assertRaisesRegex(ValueError,'exact accepted'):
                compression.run(receipt,self.root/'out',retire=True)
            remote.assert_not_called()
    def test_receipt_fsync_uses_write_descriptor_then_atomic_replace(self):
        def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
        namespace={'folder':self.root,'uuid':uuid,'json':json,'os':os,'digest':digest}
        save=native_function('save_receipt',namespace);receipt=self.root/'receipt.json';real_fsync=os.fsync;seen=[]
        def windows_commit(fd):
            mode=fcntl.fcntl(fd,fcntl.F_GETFL)&os.O_ACCMODE
            if mode==os.O_RDONLY:raise OSError(9,'Bad file descriptor')
            seen.append(mode);real_fsync(fd)
        with patch.object(os,'fsync',windows_commit):
            predecessor=save(receipt,{'verified':1});save(receipt,{'verified':2},predecessor)
        self.assertEqual(json.loads(receipt.read_text()),{'verified':2});self.assertEqual(len(seen),2)
    def test_receipt_substitution_preserves_unexpected_existing_file(self):
        namespace={'folder':self.root,'uuid':uuid,'json':json,'os':os,
                   'digest':lambda p:hashlib.sha256(p.read_bytes()).hexdigest()}
        save=native_function('save_receipt',namespace);receipt=self.root/'receipt.json';receipt.write_bytes(b'preserve')
        with self.assertRaisesRegex(AssertionError,'substituted'):
            save(receipt,{'new':1},'a'*64)
        self.assertEqual(receipt.read_bytes(),b'preserve')
    def test_native_sqlite_reader_closes_before_retirement(self):
        target=self.root/'fixture.sqlite'
        db=sqlite3.connect(target);db.execute('CREATE TABLE retained(value TEXT)');db.commit()
        expected={key:db.execute('PRAGMA '+key).fetchone()[0] for key in ('page_count','page_size','schema_version')};db.close()
        closed=[];connect=sqlite3.connect
        class Observed(sqlite3.Connection):
            def close(self):closed.append(True);super().close()
        verify=native_function('verify_sqlite',{'closing':closing,'sqlite3':sqlite3,'expected':expected})
        with patch.object(sqlite3,'connect',lambda *a,**k:connect(*a,factory=Observed,**k)):
            verify(target)
        self.assertEqual(closed,[True])


if __name__=='__main__':unittest.main()
