from pathlib import Path
import os
import tempfile
import unittest
from subtree_recopy import RecopyJournal


class Cases(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=os.environ['TMPDIR'])
        self.root=Path(self.tmp.name)
        self.file=self.root/'data';self.file.write_text('original')
        self.value={'required_subtree_recopy':[str(self.root)],'changed':[], 'events':{}}
        self.reader=RecopyJournal(lambda since:self.value)
    def tearDown(self):self.tmp.cleanup()
    def test_first_read_forces_complete_subtree_copy(self):
        self.assertIn(str(self.root),self.reader(100)['changed'])
        self.assertEqual(self.reader(101)['changed'],[])
    def test_unobserved_file_write_is_detected(self):
        self.reader();self.file.write_text('modified')
        self.assertIn(str(self.file),self.reader()['changed'])
    def test_unobserved_rename_has_both_old_and_new_paths(self):
        self.reader();new=self.root/'new';self.file.rename(new)
        self.assertTrue({str(self.file),str(new)}<=set(self.reader()['changed']))
    def test_changed_file_remains_changed_for_both_final_fence_checks(self):
        self.reader();self.file.unlink()
        self.assertIn(str(self.file),self.reader()['changed'])
        self.assertIn(str(self.file),self.reader()['changed'])
    def test_new_move_scope_is_rejected(self):
        self.reader();self.value['required_subtree_recopy']=[]
        with self.assertRaises(AssertionError):self.reader()
    def test_symlink_root_is_rejected(self):
        link=self.root/'link';link.symlink_to(self.root,target_is_directory=True)
        self.value['required_subtree_recopy']=[str(link)]
        with self.assertRaises(AssertionError):self.reader()
    def test_original_reader_errors_are_not_cleared(self):
        self.value['errors']=[{'coverage_lost':1}]
        self.assertEqual(self.reader()['errors'],self.value['errors'])

if __name__=='__main__':unittest.main()
