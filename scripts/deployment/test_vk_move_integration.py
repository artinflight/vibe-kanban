"""Real journal/move/archive/restore coverage, with no production or service writes."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from journal_compat import journal as covered_journal, source_removal
from subtree_recopy import RecopyJournal
from vk_change_journal import Journal
from vk_prep_common import digest
from vk_rolling_backup import capture, configured_reader, restore_chain
from private_desktop_fixture import PrivateDesktop


class MoveIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ['TMPDIR'])
        self.root = Path(self.tmp.name)
        self.desktop = PrivateDesktop(self.root)
        self.source = self.root/'protected'
        self.old = self.source/'old'/'hyroxready-app'
        self.new = self.source/'new'/'hyroxready-app'
        self.old.mkdir(parents=True)
        self.new.parent.mkdir()
        (self.old/'dirty-work').write_text('uncommitted agent work')
        (self.old/'dirty-work').chmod(0o640)
        (self.old/'rollout.jsonl').write_text('original thread history\n')
        self.package = self.root/'package'
        self.package.mkdir()
        self.plan = {'sources':[str(self.source)], 'move_coverage':{
            'recopy_roots':[str(self.new.parent)],
            'move_sources':{str(self.new):str(self.old)},
            'journal_identity':{'service':'fixture.service','pid':'1'}}}
        (self.package/'backup-plan.json').write_text(json.dumps(self.plan))
        self.journal = Journal(self.plan)
        self.journal.tree(self.source)
        self.journal.ready = True

    def tearDown(self):
        self.journal.close()
        self.desktop.close()
        self.tmp.cleanup()

    def mirror(self, path):
        return self.desktop.mirror(path)

    def watches(self, *args):
        result=set()
        for raw in self.journal.watches.values():
            path=Path(raw)
            if path.is_dir():
                st=path.stat()
                result.add(((os.major(st.st_dev)<<20)|os.minor(st.st_dev),st.st_ino))
        return result

    def reader(self, parent=None):
        return RecopyJournal(lambda since:covered_journal(self.package,since),parent)

    def test_clean_journal_still_rejects_missing_protected_recopy_root(self):
        absent=self.source/'already-missing'
        self.plan['move_coverage']['recopy_roots']=[str(absent)]
        (self.package/'backup-plan.json').write_text(json.dumps(self.plan))
        with patch('vk_change_journal.request',side_effect=lambda endpoint,since:self.journal.report(since)), \
             patch('journal_compat.kernel_watches',side_effect=self.watches):
            self.assertFalse(self.journal.report()['errors'])
            with self.assertRaisesRegex(AssertionError,'missing or linked'):
                self.reader()(0)

    def test_clean_journal_still_rejects_unwatched_protected_recopy_root(self):
        with patch('vk_change_journal.request',side_effect=lambda endpoint,since:self.journal.report(since)), \
             patch('journal_compat.kernel_watches',return_value=set()):
            with self.assertRaisesRegex(AssertionError,'no current kernel watch'):
                self.reader()(0)

    def test_clean_journal_still_rejects_symlink_recovery_root(self):
        linked=self.source/'alias'
        linked.symlink_to(self.new.parent,target_is_directory=True)
        self.plan['move_coverage']['recopy_roots']=[str(linked)]
        (self.package/'backup-plan.json').write_text(json.dumps(self.plan))
        with patch('vk_change_journal.request',side_effect=lambda endpoint,since:self.journal.report(since)), \
             patch('journal_compat.kernel_watches',side_effect=self.watches):
            with self.assertRaisesRegex(AssertionError,'missing or linked'):
                self.reader()(0)

    def test_fresh_full_checkpoint_preserves_data_and_old_journal_evidence(self):
        with patch('vk_change_journal.request',side_effect=lambda endpoint,since:self.journal.report(since)), \
             patch('journal_compat.kernel_watches',side_effect=self.watches):
            previous=capture(self.plan,self.root/'old-backups',self.reader(),self.mirror,publish=self.mirror)
            self.journal.errors.append({'directory_moved':str(self.new.parent/'unknown-old-move')})
            historical=self.journal.report()
            with self.assertRaises(AssertionError):
                self.reader(previous)(previous['journal_sequence'])
            old=self.journal
            fresh=Journal(self.plan)
            fresh.tree(self.source)
            fresh.ready=True
            self.journal=fresh
            try:
                with self.assertRaisesRegex(ValueError,'journal instance'):
                    capture(self.plan,self.root/'new-backups',self.reader(previous),self.mirror,previous,self.mirror)
                checkpoint=capture(self.plan,self.root/'new-backups',self.reader(),self.mirror,publish=self.mirror)
                self.assertIsNone(checkpoint['parent'])
                destination=self.root/'new-backups'/'restored'
                restore_chain(checkpoint,destination)
                recovered=destination/'files'/str(self.old).lstrip('/')
                self.assertEqual((recovered/'dirty-work').read_text(),'uncommitted agent work')
                self.assertEqual((recovered/'rollout.jsonl').read_text(),'original thread history\n')
                self.assertEqual(old.report()['errors'],historical['errors'])
                self.assertTrue(Path(previous['folder'],previous['archive']).is_file())
            finally:
                fresh.close()
                self.journal=old

    def test_cli_reader_uses_sidecar_without_changing_parent_plan(self):
        coverage=self.plan.pop('move_coverage')
        plan_path=self.package/'custom-plan.json'
        plan_path.write_text(json.dumps(self.plan))
        (self.package/'move-coverage.json').write_text(json.dumps(coverage))
        original=plan_path.read_bytes()
        with patch('vk_change_journal.request',side_effect=lambda endpoint,since:self.journal.report(since)), \
             patch('journal_compat.kernel_watches',side_effect=self.watches):
            reader=configured_reader(plan_path,self.package/'journal.sock')
            self.assertIsInstance(reader,RecopyJournal)
            reader(0)
            self.old.rename(self.new)
            with self.assertRaisesRegex(AssertionError,'new capture'):
                reader(0)
            result=configured_reader(plan_path,self.package/'journal.sock')(0)
            self.assertTrue(result['ready'])
            self.assertEqual(result['required_subtree_recopy'],[str(self.new.parent)])
        self.assertEqual(plan_path.read_bytes(),original)

    def test_actual_cross_parent_move_restores_destination_and_source_tombstone(self):
        with patch('vk_change_journal.request',side_effect=lambda endpoint,since:self.journal.report(since)), \
             patch('journal_compat.kernel_watches',side_effect=self.watches):
            first=capture(self.plan,self.root/'backups',self.reader(),self.mirror,publish=self.mirror)
            self.old.rename(self.new)
            observed=self.journal.report()
            self.assertEqual(observed['events'][str(self.old)] & 0x40000040,0x40000040)
            self.assertEqual(observed['events'][str(self.new)] & 0x40000080,0x40000080)
            second=capture(self.plan,self.root/'backups',self.reader(first),self.mirror,first,self.mirror,
                           verify_fence=lambda:{'verified':True,'fixture':True})
            self.assertTrue(second['frozen_boundary_verified'])
            self.assertIn(str(self.old),second['absent_paths'])
            restored=self.root/'backups'/'restored'
            restore_chain(second,restored)
            base=restored/'files'/str(self.source).lstrip('/')
            self.assertFalse((base/'old'/'hyroxready-app').exists())
            self.assertEqual((base/'new'/'hyroxready-app'/'dirty-work').read_text(),'uncommitted agent work')
            self.assertEqual((base/'new'/'hyroxready-app'/'dirty-work').stat().st_mode & 0o777,0o640)
            self.assertEqual((base/'new'/'hyroxready-app'/'rollout.jsonl').read_text(),'original thread history\n')
            self.assertTrue((self.new/'dirty-work').exists())

    def test_missing_protected_root_is_not_a_move_exception(self):
        self.plan['sources'].append(str(self.root/'missing-important-data'))
        with self.assertRaisesRegex(ValueError,'Missing source roots'):
            capture(self.plan,self.root/'backups',self.journal.report,self.mirror)

    def test_unrelated_source_removal_cannot_prove_destination_move(self):
        events={str(self.new.parent/'unrelated'):0x40000040}
        with self.assertRaisesRegex(AssertionError,'explicit source'):
            source_removal(self.new,self.new.parent,events,{self.source},lambda _:True,{})

    def test_rename_requires_explicit_pair_and_preserves_events(self):
        renamed=self.new.with_name('renamed-repository')
        events={str(self.old):0x40000140,str(renamed):0x40000880}
        before=copy.deepcopy(events)
        self.assertEqual(source_removal(renamed,self.new.parent,events,{self.source},lambda _:True,
            {str(renamed):str(self.old)}),str(self.old))
        self.assertEqual(events,before)
        with self.assertRaises(AssertionError):
            source_removal(renamed,self.new.parent,events,{self.source},lambda _:True,{})

    def test_symlink_escape_is_rejected_even_with_directory_event(self):
        link=self.source/'escape'
        link.symlink_to(self.root,target_is_directory=True)
        raw=str(link/'hyroxready-app')
        with self.assertRaisesRegex(AssertionError,'symlink'):
            source_removal(self.new,self.new.parent,{raw:0x40000040},{self.source},lambda _:True,{str(self.new):raw})

    def test_normalization_alias_cannot_substitute_exact_source(self):
        raw=str(self.source/'old')+'/../old/hyroxready-app'
        with self.assertRaisesRegex(AssertionError,'Invalid move source'):
            source_removal(self.new,self.new.parent,{raw:0x40000040},{self.source},lambda _:True,{str(self.new):raw})

    def test_two_matching_sources_are_not_guessed(self):
        events={str(self.new.parent/'one'/'hyroxready-app'):0x40000040,
                str(self.new.parent/'two'/'hyroxready-app'):0x40000040}
        with self.assertRaises(AssertionError):
            source_removal(self.new,self.new.parent,events,{self.source},lambda _:True,{})


if __name__=='__main__':unittest.main()
