import unittest
from backup_budget import Budget


class BackupBudgetTests(unittest.TestCase):
    def test_existing_bodies_need_no_capture_budget(self):
        budget=Budget(original_bytes=50,control_bytes=100)
        self.assertEqual(budget.maximum_missing(1000),50)
        budget.original_captured(0)
        budget.original_captured(40)
        self.assertEqual(budget.maximum_missing(1000),10)
        with self.assertRaises(ValueError):budget.original_captured(11)
        self.assertEqual(budget.original_used,40)

    def test_control_charge_precedes_capture_and_survives_failure(self):
        budget=Budget(original_bytes=0,control_bytes=100)
        budget.admit_control(70)
        # A producer failure cannot refund an uncertain write.
        with self.assertRaises(ValueError):budget.admit_control(31)
        self.assertEqual(budget.control_used,70)
        budget.admit_control(30)
        self.assertEqual(budget.control_used,100)

    def test_ambiguous_or_negative_bounds_refuse(self):
        for value in [-1, True, 1.0, None]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):Budget(original_bytes=value,control_bytes=100)


if __name__=='__main__':unittest.main()
