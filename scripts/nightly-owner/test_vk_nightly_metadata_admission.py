import unittest
from vk_nightly_metadata_admission import check,MetadataDeferred


class MetadataAdmissionTests(unittest.TestCase):
    def call(self,*,available=1800,maximum='2000',current=300,swap='0',events=None,metadata_only=True):
        return check(maximum_memory_bytes=2000,maximum_frame_bytes=100,metadata_only=metadata_only,
            cgroup=lambda:dict(maximum=maximum,current=current,swap=swap,events=events or {}),memory=lambda:available)

    def test_residents_count_once_in_the_actual_enforced_peak(self):
        v=self.call();self.assertEqual(v['additional_peak_reserved_bytes'],1700);self.assertFalse(v['body_or_SQL_admitted'])

    def test_actual_remaining_allocation_shortfall_defers_without_a_fake_fault(self):
        with self.assertRaises(MetadataDeferred):self.call(available=1699)

    def test_near_limit_cannot_admit_another_frame(self):
        with self.assertRaises(MetadataDeferred):self.call(current=1950)

    def test_real_oom_and_missing_or_raised_enforcement_fail_closed(self):
        for change in [dict(events={'oom':1}),dict(events={'oom_kill':1}),dict(maximum='max'),dict(maximum='2001'),dict(swap='1')]:
            with self.subTest(change=change),self.assertRaises(ValueError):self.call(**change)

    def test_body_or_sql_scope_cannot_borrow_metadata_admission(self):
        with self.assertRaises(ValueError):self.call(metadata_only=False)


if __name__=='__main__':unittest.main()
