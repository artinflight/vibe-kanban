import stat
import unittest
from vk_nightly_inode_journal import AliasIndex,InodeKinds


class CompactTests(unittest.TestCase):
    def test_aliases_preserve_hardlinks_and_retirement(self):
        value=AliasIndex();value.add(5,'first');value.add(5,'first')
        self.assertEqual(set(value[5]),{'first'})
        self.assertIsInstance(value.rows[5],str)
        value.add(5,'second');self.assertEqual(set(value[5]),{'first','second'})
        value.remove(5,'first');self.assertEqual(set(value[5]),{'second'})
        self.assertIsInstance(value.rows[5],str)
        value.discard(5,'missing');value.remove(5,'second')
        self.assertFalse(value[5]);self.assertIn(5,value)
        value.pop(5);self.assertNotIn(5,value)
    def test_alias_mapping_assignment_and_pop_are_detached(self):
        value=AliasIndex();value[4]={'one'};old=value.pop(4)
        self.assertEqual(set(old),{'one'});value[4]={'different'}
        self.assertEqual(set(old),{'one'})
    def test_sparse_kind_pages_handle_high_wds_and_free_empty_pages(self):
        value=InodeKinds();keys=[1,4095,4096,2**30]
        for key in keys:value[key]=stat.S_IFREG
        self.assertEqual(len(value.pages),3);self.assertEqual(len(value),4)
        value[4096]=stat.S_IFLNK;self.assertEqual(value[4096],stat.S_IFLNK)
        self.assertEqual(set(dict(value)),set(keys))
        self.assertEqual(value.pop(2**30),stat.S_IFREG)
        self.assertEqual(len(value.pages),2)
        for key in keys[:-1]:del value[key]
        self.assertEqual(len(value),0);self.assertFalse(value.pages)
    def test_kind_replacement_does_not_inflate_counts(self):
        value=InodeKinds();value[9]=stat.S_IFREG;value[9]=stat.S_IFLNK
        self.assertEqual(len(value),1);self.assertEqual(value[9],stat.S_IFLNK)
        with self.assertRaises(ValueError):value[10]=stat.S_IFDIR


if __name__=='__main__':unittest.main()
