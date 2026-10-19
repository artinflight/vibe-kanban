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


if __name__ == '__main__': unittest.main()
