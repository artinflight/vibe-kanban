import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from vk_nightly_delta import DeltaSelection, strict_scan


class Delta(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir='/mnt/vk-storage',prefix='nightly-delta-test-')
        self.root=Path(self.tmp.name);self.path=self.root/'history';self.path.write_bytes(b'historical work')
        st=self.path.stat();self.row={'kind':'file','sha256':hashlib.sha256(self.path.read_bytes()).hexdigest(),
            'bytes':st.st_size,'mode':st.st_mode & 0o7777,'uid':st.st_uid,'gid':st.st_gid,'mtime_ns':st.st_mtime_ns,'xattrs':{}}
        self.baseline={'generation':'generation-'+'a'*32,'scope_sha256':'b'*64,'parent':None,'entries':{'history':self.row,'deleted':self.row}}
        self.selection=DeltaSelection(self.baseline,self.root,'b'*64);self.selection.inventory([str(self.path)])
    def tearDown(self):self.tmp.cleanup()
    def test_complete_current_reuses_verified_payload_and_removes_absent(self):
        self.assertFalse(self.selection.include(str(self.path)));self.selection.finish({'changed':[]})
        result=self.selection.merge({'entries':{},'full_current_state':True})
        self.assertEqual(result['entries'],{'history':self.row});self.assertEqual(result['reused_files'],1)
    def test_same_size_mtime_tamper_is_hashed_and_transferred(self):
        st=self.path.stat();self.path.write_bytes(b'changed content')
        os.utime(self.path,ns=(st.st_atime_ns,st.st_mtime_ns))
        self.assertTrue(self.selection.include(str(self.path)))
    def test_change_after_reuse_and_journal_event_fail_closed(self):
        self.assertFalse(self.selection.include(str(self.path)))
        with self.assertRaises(ValueError):self.selection.finish({'changed':[str(self.path)]})
        self.path.write_bytes(b'new work')
        with self.assertRaises(ValueError):self.selection.finish({'changed':[]})
    def test_hardlink_payloads_and_symlinks_remain_in_capture(self):
        os.link(self.path,self.root/'alias');self.assertTrue(self.selection.include(str(self.path)))
        link=self.root/'link';link.symlink_to('history');self.assertTrue(self.selection.include(str(link)))
    def test_wrong_scope_parent_and_unproven_omission(self):
        with self.assertRaises(ValueError):DeltaSelection(self.baseline,self.root,'c'*64)
        with self.assertRaises(ValueError):DeltaSelection({**self.baseline,'parent':{}},self.root,'b'*64)
        with self.assertRaises(ValueError):self.selection.merge({'entries':{}})
    def test_unreadable_subtree_is_not_a_silent_exclusion(self):
        def unreadable(*args,**kwargs):
            kwargs['onerror'](PermissionError('denied fixture subtree'))
            return iter(())
        with patch('vk_nightly_delta.os.walk',unreadable):
            with self.assertRaises(PermissionError):strict_scan([self.root],lambda _:False)


if __name__=='__main__':unittest.main()
