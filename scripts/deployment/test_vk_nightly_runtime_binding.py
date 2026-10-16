"""Current release capture must retain exact bytes, including hardlink aliases."""
import unittest
from vk_nightly_capture_adapter import verify_immutable_capture


class RuntimeBinding(unittest.TestCase):
    def setUp(self):
        self.config={'source_prefix':'/','immutable_source_files':{'/fixture/server':{'identity':[1,2,3,4],'sha256':'a'*64}}}
        self.row={'kind':'file','bytes':3,'sha256':'a'*64}
    def test_exact_file_and_verified_hardlink_alias(self):
        verify_immutable_capture(self.config,{'entries':{'fixture/server':self.row}})
        verify_immutable_capture(self.config,{'entries':{'fixture/server':{'kind':'hardlink','target':'fixture/canonical'},'fixture/canonical':self.row}})
    def test_omission_changed_bytes_and_symlink_fail_closed(self):
        for row in ({},{**self.row,'sha256':'b'*64},{**self.row,'bytes':4},{'kind':'symlink','target':'elsewhere'}):
            with self.assertRaises(ValueError):verify_immutable_capture(self.config,{'entries':{'fixture/server':row}})
    def test_missing_target_and_cycle_are_not_valid_aliases(self):
        for target in ('fixture/missing','fixture/server'):
            with self.assertRaises(ValueError):
                verify_immutable_capture(self.config,{'entries':{'fixture/server':{'kind':'hardlink','target':target}}})


if __name__=='__main__':unittest.main()
