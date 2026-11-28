"""Backup metadata stays preservation data; deployment validation is unchanged."""
import copy
import hashlib
import unittest
from vk_nightly_archive_index import validate_backup_entries
from vk_candidate_generation import validate_manifest, Blocked


class BackupIndex(unittest.TestCase):
    def row(self):return {'kind':'file','mode':0o4755,'uid':0,'gid':0,'mtime_ns':0,'xattrs':{},'bytes':4,'sha256':hashlib.sha256(b'work').hexdigest()}
    def test_unselected_parents_and_numeric_owner_preserved_not_deployable(self):
        rows={'home/mcp/tool':self.row()};validate_backup_entries(rows)
        with self.assertRaises(Blocked):validate_manifest(rows)
        self.assertEqual(rows['home/mcp/tool']['uid'],0);self.assertEqual(rows['home/mcp/tool']['mode'],0o4755)
    def test_literal_external_link_is_metadata_never_followed(self):
        row=self.row();row.update(kind='symlink',target='/unselected/original/dependency')
        validate_backup_entries({'selected/link':row})
    def test_traversal_and_link_ancestor_rejected(self):
        with self.assertRaises(ValueError):validate_backup_entries({'a/../b':self.row()})
        link=self.row();link.update(kind='symlink',target='/outside')
        with self.assertRaises(ValueError):validate_backup_entries({'a':link,'a/file':self.row()})
    def test_invalid_hardlink_or_unbound_payload_rejected(self):
        row=self.row();row.update(kind='hardlink',target='missing')
        with self.assertRaises(ValueError):validate_backup_entries({'a':row})
        row=self.row();row['sha256']='user-generated-result'
        with self.assertRaises(ValueError):validate_backup_entries({'a':row})


if __name__=='__main__':unittest.main()
