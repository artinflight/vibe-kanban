from pathlib import Path
import os
import sqlite3
import tempfile
import unittest

from vk_nightly_gap_namespace import initialize,advance
from vk_nightly_qualification import decode_observation
from vk_prep_common import identity
from vk_change_journal import scope


class GapNamespaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir='/dev/shm');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.source=self.root/'source';self.source.mkdir()
        (self.source/'child').mkdir();(self.source/'one').write_text('must not read body')
        (self.source/'child'/'two').write_text('preserved source')
        self.db=sqlite3.connect(':memory:',isolation_level=None);self.addCleanup(self.db.close)
        self.plan={'sources':[str(self.source)]}
        self.anchor=dict(ready=True,errors=[],terminal=None,instance='one',sequence=10,
            plan_sha256=identity(self.plan),scope_sha256=identity(scope(self.plan)))
        self.binding=initialize(self.db,self.plan,self.anchor)

    def advance(self,n=10,**extra):
        return advance(self.db,self.plan,self.binding,guard=lambda:None,maximum_directories=n,maximum_paths=100,**extra)

    def test_closed_directories_resume_without_relisting_and_suffix_remains_explicit(self):
        first=self.advance(1);self.assertFalse(first['enumeration_complete'])
        (self.source/'after-completed-parent').write_text('journal suffix handles this')
        final=self.advance();self.assertTrue(final['enumeration_complete'])
        self.assertEqual(self.db.execute('select count(*) from namespace where name=?',(str(self.source/'after-completed-parent')[1:],)).fetchone()[0],0)
        self.assertTrue(final['journal_suffix_required']);self.assertFalse(final['current_baseline_accepted'])
        self.assertEqual(final['source_body_bytes_read'],0)

    def test_literal_external_symlink_is_recorded_and_never_traversed(self):
        outside=self.root/'outside';outside.mkdir();(outside/'private').write_text('not scoped')
        (self.source/'link').symlink_to(outside)
        result=self.advance();self.assertTrue(result['enumeration_complete'])
        row=self.db.execute('select row from namespace where name=?',(str(self.source/'link')[1:],)).fetchone()
        self.assertEqual(decode_observation(row[0])['kind'],'symlink')
        self.assertEqual(self.db.execute('select count(*) from namespace where name like ?',('%/private',)).fetchone()[0],0)

    def test_missing_directory_preserves_explicit_replay_error(self):
        self.advance(1);(self.source/'child'/'two').unlink();(self.source/'child').rmdir()
        final=self.advance();self.assertTrue(final['enumeration_complete']);self.assertGreater(final['replay_errors'],0)
        self.assertFalse(final['current_baseline_accepted'])

    def test_changed_observer_cannot_silently_resume_prior_namespace(self):
        self.advance(1)
        with self.assertRaisesRegex(ValueError,'observer/scope/root changed'):
            initialize(self.db,self.plan,dict(self.anchor,instance='two'))

    def test_metadata_path_bound_rolls_back_batch_preserving_cursor(self):
        with self.assertRaisesRegex(ValueError,'path bound'):
            advance(self.db,self.plan,self.binding,guard=lambda:None,maximum_directories=10,maximum_paths=1)
        self.assertEqual(self.db.execute('select count(*) from namespace').fetchone()[0],0)
        self.assertEqual(self.db.execute('select count(*) from gap_pending where done=1').fetchone()[0],0)
        self.assertTrue(self.advance()['enumeration_complete'])


if __name__=='__main__':unittest.main()
