from pathlib import Path
import shutil
import sqlite3
import unittest

import packed_forward_plan as forward
import test_packed_publication as fixtures


class ForwardPlanTests(unittest.TestCase):
    def setUp(self):
        self.t=fixtures.PublicationTests();self.t.setUp();self.addCleanup(self.t.doCleanups)
        self.protected=self.t.base/'protected.sqlite';shutil.copy2(self.t.db,self.protected)
        self.databases=dict(main=str(self.t.db),protected=str(self.protected))
    def inventory(self):
        return forward.inventory(self.t.root,self.databases,minimum_age_seconds=0,guard=lambda:None)
    def test_pending_and_active_other_owner_are_preserved(self):
        path=self.t.root/self.t.names[2];path.with_suffix('.capture.json').write_text('{"capture_state":"pending"}')
        observed=self.inventory();self.assertEqual(len(observed['eligible']),2)
        with sqlite3.connect(self.protected)as db:db.execute("update execution_processes set status='running'where rowid=3")
        self.assertFalse(self.inventory()['eligible']);self.assertEqual(path.read_bytes(),self.t.raw)
    def test_prepare_is_bounded_direct_pack_and_preserves_raw_sources(self):
        rows=self.inventory()['eligible'][:2]
        result=forward.prepare(rows,self.t.root,self.databases,self.t.base/'forward',guard=lambda:None)
        self.assertTrue(result['beneficial']);self.assertEqual(result['preparation']['loose_objects_created'],0)
        self.assertFalse(result['source_mutations']);self.assertEqual(len(result['group']['files']),2)
        for name in self.t.names:self.assertEqual((self.t.root/name).read_bytes(),self.t.raw)
        self.assertFalse(list(self.t.base.rglob('*.gz')))
    def test_changed_capture_is_refused_before_preparation(self):
        rows=self.inventory()['eligible'][:2]
        (self.t.root/rows[0]['path']).with_suffix('.capture.json').write_text('{"capture_state":"pending"}')
        folder=self.t.base/'forward'
        with self.assertRaisesRegex(ValueError,'capture metadata'):forward.prepare(rows,self.t.root,self.databases,folder,guard=lambda:None)
        self.assertFalse(folder.exists())
    def test_partition_never_merges_sessions_or_exceeds_qualified_bounds(self):
        rows=self.inventory()['eligible'];groups=forward.partition(rows,maximum_files=1)
        self.assertEqual(len(groups),3)
        with self.assertRaises(ValueError):forward.partition(rows,maximum_bytes=1)
        with self.assertRaises(ValueError):forward.partition(rows+[rows[0]])


if __name__=='__main__':unittest.main()
