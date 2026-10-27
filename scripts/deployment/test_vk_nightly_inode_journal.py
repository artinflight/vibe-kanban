import ctypes
import errno
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from vk_nightly_inode_journal import Journal,WatchAdmissionError,require_full_coverage,check_watch_demand


class InodeJournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir='/dev/shm');self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.root=self.base/'source';self.root.mkdir()

    def enroll(self):
        journal=Journal({'sources':[str(self.root)]});self.addCleanup(journal.close)
        journal.tree(self.root);journal.ready=True;return journal

    def test_existing_external_and_multiple_source_aliases_report_every_selected_name(self):
        original=self.root/'original';original.write_bytes(b'first');inside=self.root/'inside';outside=self.base/'outside'
        os.link(original,inside);os.link(original,outside);journal=self.enroll();start=journal.report(0)['sequence']
        outside.write_bytes(b'later');report=journal.report(start)
        self.assertTrue(report['ready']);self.assertEqual(set(report['changed']),{str(original),str(inside)})
        self.assertEqual(report['regular_inode_watches'],1);self.assertEqual(report['regular_alias_paths'],2)
        self.assertEqual(report['coverage_model'],'all-selected-inodes-v1')

    def test_external_symlink_alias_metadata_is_observed_without_following_target(self):
        target=self.base/'not-in-scope';target.write_bytes(b'preserved target')
        link=self.root/'link';link.symlink_to(target);outside=self.base/'link-alias';os.link(link,outside,follow_symlinks=False)
        journal=self.enroll();start=journal.report(0)['sequence']
        os.utime(outside,ns=(1000000000,2000000000),follow_symlinks=False)
        report=journal.report(start)
        self.assertTrue(report['ready']);self.assertIn(str(link),report['changed'])
        self.assertEqual(report['symlink_inode_watches'],1);self.assertEqual(report['regular_inode_watches'],0)
        self.assertEqual(target.read_bytes(),b'preserved target')

    def test_external_link_created_after_enrollment_and_new_source_file_are_covered(self):
        original=self.root/'original';original.write_bytes(b'first');journal=self.enroll();start=journal.report(0)['sequence']
        outside=self.base/'later-link';os.link(original,outside);outside.write_bytes(b'later')
        report=journal.report(start);self.assertTrue(report['ready']);self.assertIn(str(original),report['changed'])
        added=self.root/'added';added.write_bytes(b'new');journal.report(report['sequence'])
        second=self.base/'second-link';os.link(added,second);second.write_bytes(b'changed')
        after=journal.report(report['sequence']);self.assertTrue(after['ready']);self.assertIn(str(added),after['changed'])

    def test_atomic_replacement_and_deletion_do_not_leave_unobserved_new_inode(self):
        original=self.root/'file';original.write_bytes(b'old');journal=self.enroll();start=journal.report(0)['sequence']
        replacement=self.base/'replacement';replacement.write_bytes(b'new');os.replace(replacement,original)
        first=journal.report(start);self.assertTrue(first['ready']);self.assertIn(str(original),first['changed'])
        outside=self.base/'alias';os.link(original,outside);outside.write_bytes(b'changed')
        second=journal.report(first['sequence']);self.assertTrue(second['ready']);self.assertIn(str(original),second['changed'])
        original.unlink();last=journal.report(second['sequence']);self.assertTrue(last['ready']);self.assertIn(str(original),last['changed'])

    def test_directory_move_retains_inode_alias_names_and_future_external_writes(self):
        first=self.root/'first';first.mkdir();original=first/'file';original.write_bytes(b'old');outside=self.base/'alias';os.link(original,outside)
        journal=self.enroll();start=journal.report(0)['sequence'];second=self.root/'second';first.rename(second)
        moved=journal.report(start);self.assertTrue(moved['ready']);self.assertGreater(moved['rename_count'],0)
        outside.write_bytes(b'later');report=journal.report(moved['sequence'])
        self.assertTrue(report['ready']);self.assertIn(str(second/'file'),report['changed']);self.assertNotIn(str(original),report['changed'])

    def test_old_ignored_event_cannot_erase_new_inode_name_mapping(self):
        old=self.root/'old';new=self.root/'new';old.write_bytes(b'a');new.write_bytes(b'b')
        journal=self.enroll();oldwd=journal.path_watches[str(old)];newwd=journal.path_watches[str(new)]
        # Model the already-delivered destination enrollment followed by the
        # old inode's queued IGNORED event. The new watch remains removable.
        journal.file_aliases[oldwd]={str(new)}
        journal.expected_ignored.add(oldwd)
        journal.event(oldwd,0x8000,'')
        self.assertEqual(journal.path_watches[str(new)],newwd)
        self.assertIn(newwd,journal.file_aliases)

    def test_replacement_during_child_enrollment_defers_until_actual_inode_is_watched(self):
        old=self.root/'file';old.write_bytes(b'a');journal=self.enroll()
        other=self.base/'replacement';other.write_bytes(b'b');real=os.lstat
        def replaced(path,*args,**kwargs):
            if str(path)==str(old):return real(other)
            return real(path,*args,**kwargs)
        with patch('vk_nightly_inode_journal.os.lstat',side_effect=replaced):
            journal.enroll_file(str(old))
        self.assertEqual(journal.pending_file_enrollments,{str(old)})
        self.assertEqual(journal.errors,[])
        report=journal.report(0)
        self.assertEqual(report['pending_file_enrollments'],0)
        self.assertTrue(report['ready'],report['errors'])
        self.assertIn(str(old),report['changed'])
        self.assertIn(str(old),journal.path_watches)

    def test_concurrent_atomic_replacement_and_alias_churn_remain_observed(self):
        import threading,time
        f=self.root/'file';f.write_bytes(b'a');outside=self.base/'outside';os.link(f,outside)
        journal=self.enroll();stop=threading.Event();failures=[]
        def drain():
            try:
                while not stop.wait(.001):journal.read()
            except BaseException as error:failures.append(str(error))
        thread=threading.Thread(target=drain);thread.start()
        try:
            for i in range(1500):
                p=self.root/'tmp';p.write_bytes(b'a');os.replace(p,f)
                if i%2==0:os.link(outside,self.root/'hard');(self.root/'hard').unlink()
            report=journal.report(0)
            self.assertEqual(failures,[]);self.assertTrue(report['ready'],report['errors'])
            self.assertEqual(report['pending_file_enrollments'],0)
            self.assertIn(str(f),report['changed'])
            self.assertIn(str(f),journal.path_watches)
            alias=self.base/'new-alias';os.link(f,alias);alias.write_bytes(b'later')
            after=journal.report(report['sequence'])
            self.assertTrue(after['ready'],after['errors']);self.assertIn(str(f),after['changed'])
        finally:stop.set();thread.join(timeout=5)
        self.assertFalse(thread.is_alive())

    def test_real_kernel_refusal_is_not_ignored_or_retried_using_another_route(self):
        original=self.root/'file';original.write_bytes(b'old');journal=Journal({'sources':[str(self.root)]});self.addCleanup(journal.close)
        def full(*_):ctypes.set_errno(errno.ENOSPC);return -1
        with patch.object(journal.lib,'inotify_add_watch',side_effect=full) as watch:
            with self.assertRaises(WatchAdmissionError):journal.tree(self.root)
        self.assertEqual(watch.call_count,1);self.assertFalse(journal.report(0)['ready'])

    def test_namespace_readiness_cannot_be_adopted_as_complete_inode_coverage(self):
        report=dict(ready=True,errors=[],terminal=None,barrier=True)
        with self.assertRaises(ValueError):require_full_coverage(report)
        report['coverage_model']='directory-namespace-only-v1'
        with self.assertRaises(ValueError):require_full_coverage(report)
        report['coverage_model']='all-selected-inodes-v1'
        with self.assertRaises(ValueError):require_full_coverage(report)
        report.update(instance='actual-source',sequence=42,barrier=dict(instance='actual-source',durable_sequence=42,kernel_drain_completed=True))
        require_full_coverage(report)
        for key,value in [('ready',False),('errors',[{'coverage_lost':True}]),('terminal','stopped'),('barrier',False)]:
            with self.subTest(key=key),self.assertRaises(ValueError):require_full_coverage(dict(report,**{key:value}))

    def test_known_watch_shortfall_is_rejected_without_changing_the_host(self):
        with self.assertRaises(WatchAdmissionError):check_watch_demand(849199,248899)
        check_watch_demand(100,248899) # Necessary condition only, not real enrollment.
        with self.assertRaises(ValueError):check_watch_demand(True,248899)

    def test_full_observer_admission_refuses_known_shortfall_before_state_or_watches(self):
        from vk_nightly_local_tracker import admit_inode_observation,run
        config=dict(watch_all_selected_inodes=True,retained_inode_watch_minimum=889894)
        with self.assertRaises(WatchAdmissionError):admit_inode_observation(config,read_limit=lambda:248899)
        admit_inode_observation(config,read_limit=lambda:1048576)
        with self.assertRaises(ValueError):admit_inode_observation(dict(watch_all_selected_inodes=True),read_limit=lambda:1048576)
        with patch('vk_nightly_local_tracker.admit_inode_observation',side_effect=WatchAdmissionError('known shortfall')),\
             patch('vk_nightly_local_tracker.serve') as serve:
            with self.assertRaises(WatchAdmissionError):run(config,guard=lambda:None)
        serve.assert_not_called()

    def test_kernel_reader_drains_burst_while_metadata_processing_lock_is_held(self):
        # Four tiny inode sources generate more events than the current
        # kernel FIFO can retain. No source payload workload or limit change.
        import time
        limit=int(Path('/proc/sys/fs/inotify/max_queued_events').read_text())
        if limit>65536:self.skipTest('host FIFO exceeds this bounded fixture admission')
        files=[self.root/str(i) for i in range(4)]
        for f in files:f.write_bytes(b'x')
        journal=self.enroll()
        with journal.lock:
            for i in range(limit+1024):
                os.utime(files[i%4],ns=(i+1,i+1))
                if i%256==0:time.sleep(.001)
        report=journal.report(0)
        self.assertTrue(report['ready'],report['errors'])
        self.assertEqual(set(report['changed']),set(map(str,files)))
        self.assertGreater(report['sequence'],limit)
        self.assertGreater(report['kernel_raw_buffer_peak_bytes'],4096)
        self.assertLessEqual(report['kernel_raw_buffer_peak_bytes'],16*1024**2)
        self.assertEqual(journal.raw_bytes,0)

    def test_finite_buffer_does_not_hide_actual_kernel_overflow(self):
        import time
        limit=int(Path('/proc/sys/fs/inotify/max_queued_events').read_text())
        if limit>65536:self.skipTest('host FIFO exceeds this bounded fixture admission')
        files=[self.root/str(i) for i in range(4)]
        for f in files:f.write_bytes(b'x')
        journal=Journal({'sources':[str(self.root)]},maximum_raw_bytes=4096)
        self.addCleanup(journal.close);journal.tree(self.root);journal.ready=True
        with journal.lock:
            for i in range(limit+1024):
                os.utime(files[i%4],ns=(i+1,i+1))
                if i%256==0:time.sleep(.001)
        report=journal.report(0)
        self.assertFalse(report['ready'])
        self.assertTrue(any(error.get('coverage_lost')==0x4000 for error in report['errors']))
        self.assertLessEqual(report['kernel_raw_buffer_peak_bytes'],4096)
        with self.assertRaises(ValueError):require_full_coverage(dict(report,barrier=True))

    def test_report_counts_do_not_iterate_all_registered_inodes(self):
        import stat
        f=self.root/'file';f.write_bytes(b'x');(self.root/'alias').symlink_to(f)
        journal=self.enroll()
        class NoValues(dict):
            def values(self):raise AssertionError('whole inode scan in ordinary heartbeat')
        journal.inode_kinds=NoValues(journal.inode_kinds)
        report=journal.report(0)
        self.assertEqual(report['regular_inode_watches'],1)
        self.assertEqual(report['symlink_inode_watches'],1)
        self.assertEqual(report['watches'],3)
        f.unlink();(self.root/'alias').unlink()
        report=journal.report(report['sequence'])
        self.assertEqual(report['regular_inode_watches'],0)
        self.assertEqual(report['symlink_inode_watches'],0)

    def test_owned_kernel_reader_closes_without_reusing_or_leaking_its_FD(self):
        journal=Journal({'sources':[str(self.root)]});journal.tree(self.root)
        fd=journal.fd;journal.close()
        self.assertFalse(journal.raw_reader.is_alive())
        with self.assertRaises(OSError):os.fstat(fd)

    def test_repeated_close_cannot_close_a_reused_descriptor_or_leave_ready(self):
        journal=Journal({'sources':[str(self.root)]});journal.tree(self.root);journal.ready=True
        journal.close();other=os.open('/dev/null',os.O_RDONLY)
        try:
            journal.close();os.fstat(other)
            self.assertFalse(journal.report(0)['ready'])
        finally:os.close(other)
