from pathlib import Path
import hashlib
import json
import os
import tempfile
import unittest
from subtree_recopy import RecopyJournal


class Cases(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=os.environ['TMPDIR'])
        self.base=Path(self.tmp.name)
        self.root=self.base/'files';self.root.mkdir()
        self.file=self.root/'work';self.file.write_text('before')
        self.value={'required_subtree_recopy':[str(self.root)],'changed':[], 'events':{}}
        first=RecopyJournal(lambda since:self.value)()
        self.parent={'archive':'capture.tar.zst','folder':str(self.base),
            'recopy_baseline':first['recopy_baseline'],'journal_instance':'one',
            'journal_sequence':42,'scope_sha256':'scope','plan_sha256':'plan',
            'receipt':{'sha256':'archive-proof'}}
        self.metadata=self.base/'capture.tar.zst.result.json'
        self.metadata.write_text(json.dumps(self.parent))
        self.parent['metadata_receipt']={'name':self.metadata.name,'desktop_verified':True,
            'sha256':hashlib.sha256(self.metadata.read_bytes()).hexdigest()}
    def tearDown(self):self.tmp.cleanup()
    def reader(self):return RecopyJournal(lambda since:self.value,self.parent)
    def test_unchanged_parent_copies_no_subtree(self):
        self.assertEqual(self.reader()()['changed'],[])
    def test_prefix_sibling_is_outside_covered_root(self):
        self.parent['recopy_baseline']['files'][str(self.root)+'-sibling/work']=['unrelated']
        verified={k:v for k,v in self.parent.items() if k!='metadata_receipt'}
        self.metadata.write_text(json.dumps(verified))
        self.parent['metadata_receipt']['sha256']=hashlib.sha256(self.metadata.read_bytes()).hexdigest()
        self.assertEqual(self.reader()()['changed'],[])
    def test_changed_file_copied_without_whole_root(self):
        self.file.write_text('after')
        value=self.reader()()
        self.assertIn(str(self.file),value['changed'])
        self.assertNotIn(str(self.root),value['changed'])
    def test_deletion_is_not_lost(self):
        self.file.unlink()
        self.assertIn(str(self.file),self.reader()()['changed'])
    def test_change_after_capture_starts_remains_in_both_fences(self):
        reader=self.reader();reader()
        self.file.write_text('while capturing')
        for _ in range(2):self.assertIn(str(self.file),reader()['changed'])
    def test_tampered_local_baseline_rejected(self):
        self.parent['recopy_baseline']['files']={}
        with self.assertRaises(AssertionError):self.reader()
    def test_tampered_metadata_rejected(self):
        self.metadata.write_text('{}')
        with self.assertRaises(AssertionError):self.reader()
    def test_unverified_desktop_metadata_rejected(self):
        self.parent['metadata_receipt']['desktop_verified']=False
        with self.assertRaises(AssertionError):self.reader()
    def test_old_parent_forces_whole_subtree(self):
        self.parent.pop('recopy_baseline')
        self.assertIn(str(self.root),self.reader()()['changed'])


if __name__=='__main__':unittest.main()
