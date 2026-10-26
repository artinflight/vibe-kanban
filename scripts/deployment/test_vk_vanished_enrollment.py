import copy
import unittest
from vk_typed_recovery import checksum
from vk_vanished_enrollment import check_continuing, seal


class VanishedEnrollmentTests(unittest.TestCase):
    def setUp(self):
        self.observer = {'PID': 12, 'start_ticks': 34, 'fd': 3}
        self.initial = dict(ready=True, errors=[], instance='same', scope_sha256='a'*64, sequence=1)
        self.before = dict(self.initial, ready=False, sequence=8,
                           errors=[{'watch_failed': '/source/transient', 'errno': 2}],
                           events={'/source/transient': 0x40000600})
        self.after = dict(self.before, sequence=9, changed=[])
        self.kernel = dict(observer=self.observer, fd_device=1, fd_inode=2, rows=[{
            'path': '/source/transient', 'parent_device': 3, 'parent_inode': 4,
            'watch': dict(wd=5, ino=4, sdev=3, mask=0xfce), 'absence_errno': 2}])
        self.args = dict(observer=self.observer, initial=self.initial, before=self.before,
                         after=self.after, kernel=self.kernel, plan_sha256='b'*64,
                         required_sources=['/source'], subtree_names=lambda path: [])

    def test_current_absence_preserves_raw_errors_and_no_acceptance(self):
        c = seal(**self.args)
        self.assertEqual(c['after_raw']['errors'], self.before['errors'])
        self.assertFalse(c['full_current_set_accepted'])
        self.assertFalse(c['unobserved_transient_history_recovered'])
        result = check_continuing(c, checksum(c), plan_sha256='b'*64,
            required_sources=['/source'], watched=self.after, current_kernel=self.kernel)
        self.assertEqual(result['enrollment_gaps_conditionally_resolved'], 1)
        self.assertFalse(result['writer_fence_verified'])

    def test_required_roots_and_remaining_subtrees_refused(self):
        for updates in [dict(required_sources=['/source/transient']),
                        dict(subtree_names=lambda path: [path+'/child'])]:
            with self.assertRaises(ValueError): seal(**dict(self.args, **updates))

    def test_permissions_new_errors_and_duplicate_failure_refused(self):
        for errors in [[{'watch_failed': '/source/transient', 'errno': 13}],
                       self.before['errors']*2, self.before['errors']+[{'overflow': True}]]:
            b = dict(self.before, errors=errors)
            with self.assertRaises(ValueError): seal(**dict(self.args, before=b, after=dict(self.after, errors=errors)))

    def test_reappearance_and_regression_refused(self):
        for updates in [dict(changed=['/source/transient']),
                        dict(changed=['/source/transient/child']), dict(sequence=7)]:
            with self.assertRaises(ValueError): seal(**dict(self.args, after=dict(self.after, **updates)))

    def test_continuing_identity_error_and_watch_changes_refused(self):
        c = seal(**self.args)
        for updates in [dict(instance='replacement'), dict(sequence=0),
                        dict(errors=self.after['errors']*2), dict(changed=['/source/transient/new'])]:
            with self.assertRaises(ValueError): check_continuing(c, checksum(c),
                plan_sha256='b'*64, required_sources=['/source'],
                watched=dict(self.after, **updates), current_kernel=self.kernel)
        changed = copy.deepcopy(self.kernel); changed['rows'][0]['watch']['wd'] += 1
        with self.assertRaises(ValueError): check_continuing(c, checksum(c),
            plan_sha256='b'*64, required_sources=['/source'], watched=self.after, current_kernel=changed)

    def test_external_certificate_hash_required(self):
        c = seal(**self.args)
        with self.assertRaises(ValueError): check_continuing(c, 'f'*64,
            plan_sha256='b'*64, required_sources=['/source'], watched=self.after, current_kernel=self.kernel)



class WatchedAncestorTests(VanishedEnrollmentTests):
    def setUp(self):
        super().setUp()
        self.kernel['rows'][0].update(watched_ancestor='/source', absent_child='/source/transient')

    def seal(self, **updates):
        from vk_vanished_enrollment import seal_ancestors
        return seal_ancestors(**dict(self.args, **updates))

    def test_reenrollment_and_nested_absence_use_entire_missing_child(self):
        target = '/source/transient/tree/.git/objects'
        before = dict(self.before, errors=[{'watch_reenrollment_stat_failed': target, 'errno': 2}])
        after = dict(self.after, errors=before['errors'])
        kernel = copy.deepcopy(self.kernel); kernel['rows'][0]['path'] = target
        requested = []
        c = self.seal(before=before, after=after, kernel=kernel,
                      subtree_names=lambda name: requested.append(name) or [])
        self.assertEqual(requested, ['/source/transient'])
        self.assertEqual(c['after_raw'], after)
        self.assertFalse(c['historical_gap_closed'])

    def test_open_historical_gap_is_preserved_without_relabeling_initial_report(self):
        initial = dict(self.initial, format='T17-open-gap-current-observation-v2',
                       ready=False, observation_ready=True, coverage_gap={'accepted_selector': False})
        c = self.seal(initial=initial)
        self.assertEqual(c['initial_raw'], initial)
        self.assertFalse(c['full_current_set_accepted'])
        with self.assertRaises(ValueError): self.seal(initial=dict(initial, observation_ready=False))

    def test_required_descendant_and_nonempty_absent_subtree_refused(self):
        for updates in (dict(required_sources=['/source', '/source/transient/required']),
                        dict(subtree_names=lambda child: [child+'/old-version'])):
            with self.assertRaises(ValueError): self.seal(**updates)

    def test_unwitnessed_delete_bad_ancestor_and_permission_errors_refused(self):
        bad = copy.deepcopy(self.kernel); bad['rows'][0]['watched_ancestor'] = '/unrelated'
        for updates in (dict(kernel=bad), dict(before=dict(self.before, events={})),
                        dict(before=dict(self.before, errors=[{'watch_failed': '/source/transient', 'errno': 13}])),
                        dict(after=dict(self.after, pending_directory_moves=1))):
            with self.assertRaises(ValueError): self.seal(**updates)

    def test_ancestor_recreation_and_subscription_drift_fail_continuing_check(self):
        from vk_vanished_enrollment import check_ancestors
        c = self.seal()
        args = dict(plan_sha256='b'*64, required_sources=['/source'],
                    watched=self.after, current_kernel=self.kernel)
        result = check_ancestors(c, checksum(c), **args)
        self.assertEqual(result['enrollment_gaps_conditionally_resolved'], 1)
        self.assertFalse(result['historical_gap_closed'])
        changed = copy.deepcopy(self.kernel); changed['rows'][0]['watch']['wd'] += 1
        for updates in (dict(watched=dict(self.after, changed=['/source/transient/new'])),
                        dict(current_kernel=changed), dict(watched=dict(self.after, instance='new'))):
            with self.assertRaises(ValueError): check_ancestors(c, checksum(c), **dict(args, **updates))
        with self.assertRaises(ValueError): check_ancestors(c, '0'*64, **args)

    def test_real_kernel_watched_ancestor_and_reappearance(self):
        import os
        from pathlib import Path
        import tempfile
        from vk_change_journal import Journal
        from vk_vanished_enrollment import probe, start_ticks
        with tempfile.TemporaryDirectory(prefix='nightly-absent-ancestor-') as folder:
            root = Path(folder); missing = root/'missing'/'intermediate'/'failed'
            journal = Journal({'sources': [folder]})
            try:
                journal.tree(folder)
                observer = dict(PID=os.getpid(), start_ticks=start_ticks(os.getpid()), fd=journal.fd)
                evidence = probe(observer, [str(missing)], ancestors=True)
                self.assertEqual(evidence['rows'][0]['watched_ancestor'], folder)
                self.assertEqual(evidence['rows'][0]['absent_child'], str(root/'missing'))
                (root/'missing').mkdir()
                with self.assertRaises(ValueError): probe(observer, [str(missing)], ancestors=True)
            finally:
                journal.close()

    def test_typed_consumer_uses_raw_v2_certificate_and_current_bracket(self):
        from vk_vanished_enrollment import WatchedAncestorCoverage
        c = self.seal(); calls = []
        def reader(since):
            calls.append(since)
            return self.after
        coverage = WatchedAncestorCoverage(c, checksum(c), reader,
            kernel_reader=lambda observer, paths, **kw: self.kernel)
        anchor = dict(enrollment_resolution_sha256=checksum(c), errors=self.after['errors'],
                      instance=self.after['instance'], scope_sha256=self.after['scope_sha256'], start=1, end=9)
        self.assertEqual(coverage.validate_anchor(anchor, plan_sha256='b'*64, required_sources=['/source']),
                         ['/source/transient'])
        self.assertEqual(calls, [9, 9])
        with self.assertRaises(ValueError): coverage.validate_anchor(dict(anchor, errors=[]),
            plan_sha256='b'*64, required_sources=['/source'])


if __name__ == '__main__': unittest.main()
