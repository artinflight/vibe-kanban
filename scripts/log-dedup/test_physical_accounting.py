import os
from pathlib import Path
import tempfile
import unittest

import physical_accounting


class PhysicalAccountingTests(unittest.TestCase):
    def test_counts_directory_blocks_and_hardlinks_once_without_following_links(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tree = root/'tree'
            tree.mkdir()
            data = tree/'body'
            data.write_bytes(b'original'*1000)
            os.link(data, tree/'second-name')
            (root/'outside').write_bytes(b'outside'*10000)
            (tree/'alias').symlink_to(root/'outside')
            value = physical_accounting.measure([tree, data])
            expected = sum(p.lstat().st_blocks*512 for p in [tree,data,tree/'alias'])
            self.assertEqual(value['allocated_bytes'], expected)
            self.assertEqual((value['files'],value['directories'],value['symlinks']), (1,1,1))

    def test_missing_or_special_path_is_not_silently_omitted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(FileNotFoundError):
                physical_accounting.measure([root/'missing'])
            os.mkfifo(root/'pipe')
            with self.assertRaisesRegex(ValueError, 'special'):
                physical_accounting.measure([root])


if __name__ == '__main__':
    unittest.main()
