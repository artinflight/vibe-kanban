"""Keep unrelated qualified histories reusable while a real subtree gap is open."""
import copy
import hashlib
import os
from pathlib import Path
import tempfile
import unittest

from vk_change_journal import Journal,scope
from vk_nightly_scoped_coverage import ScopedCoverage,seal,kernel_roots
from vk_nightly_qualification import qualify_file,still_covered
from vk_nightly_tracked_delta import select,ReconciliationRequired
from vk_prep_common import identity


class ScopedTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.work=self.root/'work';self.work.mkdir()
        self.old=self.work/'old';self.new=self.work/'new';self.old.mkdir()
        self.history=self.root/'history';self.history.mkdir();self.file=self.history/'log';self.file.write_bytes(b'accepted')
        self.plan={'sources':[str(self.work),str(self.history)]}
        self.journal=Journal(self.plan);self.addCleanup(self.journal.close)
        for root in self.plan['sources']:self.journal.tree(root)
        self.journal.ready=True
        self.observer=dict(PID=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),fd=self.journal.fd)
        self.old.rename(self.new)
        self.report=self.journal.report();self.report['plan_sha256']=identity(self.plan);self.report['since']=0
        self.assertFalse(self.report['ready'])

    def certificate(self):
        return seal(self.plan,self.report,observer=self.observer,reconciliation_roots=[str(self.old),str(self.new)])

    def coverage(self):
        cert=self.certificate();return ScopedCoverage(cert,identity(cert),plan=self.plan)

    def test_real_move_preserves_raw_fault_and_allows_only_unaffected_file_points(self):
        coverage=self.coverage();before=copy.deepcopy(self.report)
        result=qualify_file(self.file,maximum_bytes=100,journal=self.report,carriers=lambda *_:[],guard=lambda:None,coverage=coverage)
        self.assertEqual(result['state'],'qualified-pending-body');self.assertEqual(self.report,before)
        self.assertFalse(result['scoped_qualification_coverage']['whole_scope_accepted'])
        self.assertFalse(result['scoped_qualification_coverage']['raw_journal_ready'])
        self.assertTrue(still_covered(result,self.report,coverage=coverage))

    def test_open_subtree_or_ancestor_can_never_use_unaffected_coverage(self):
        coverage=self.coverage()
        for path in (self.old,self.new,self.new/'child',self.work):
            with self.assertRaises(ValueError):coverage.check(self.report,[str(path)])
        with self.assertRaises(ValueError):qualify_file(self.file,maximum_bytes=100,journal=self.report,carriers=lambda *_:[],guard=lambda:None,coverage=True)

    def test_overflow_unknown_new_fault_or_move_invalidates_certificate(self):
        coverage=self.coverage()
        for error in ({'coverage_lost':16384},{'watch_removed':str(self.history)},{'directory_moved':str(self.history)}):
            value=copy.deepcopy(self.report);value['errors'].append(error)
            with self.assertRaises(ValueError):coverage.check(value,[str(self.file)])
        value=copy.deepcopy(self.report);value['events'][str(self.history/'other')]=0x40000040
        with self.assertRaises(ValueError):coverage.check(value,[str(self.file)])

    def test_whole_baseline_delta_still_refuses_the_raw_unready_report(self):
        self.coverage().check(self.report,[str(self.file)])
        anchor=dict(baseline_accepted=True,instance=self.report['instance'],scope_sha256=self.report['scope_sha256'],plan_sha256=identity(self.plan),sequence=0,sources=self.plan['sources'])
        with self.assertRaises(ReconciliationRequired):select(anchor,self.report,required_sql=[],maximum_paths=10,enumerate_subtree=lambda _:[])

    def test_affected_closure_cannot_drop_required_roots_or_miss_a_move_path(self):
        with self.assertRaises(ValueError):seal(self.plan,self.report,observer=self.observer,reconciliation_roots=[str(self.work)])
        with self.assertRaises(ValueError):seal(self.plan,self.report,observer=self.observer,reconciliation_roots=[str(self.new)])

    def test_epoch_or_root_identity_change_does_not_inherit_coverage(self):
        coverage=self.coverage();value=dict(self.report,instance='new')
        with self.assertRaises(ValueError):coverage.check(value,[str(self.file)])
        coverage.check(self.report,[str(self.file)])
        outside=self.root/'preserved';self.history.rename(outside);self.history.mkdir();value=dict(self.report,sequence=self.report['sequence']+1)
        with self.assertRaises(ValueError):coverage.check(self.report,[str(self.file)])
        with self.assertRaises(ValueError):coverage.check(value,[str(self.file)])


if __name__=='__main__':unittest.main()
