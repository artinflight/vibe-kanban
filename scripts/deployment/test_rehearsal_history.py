from copy import deepcopy
import unittest
from check_rehearsal_history import canonical_page, digest


class RehearsalHistoryTests(unittest.TestCase):
    def setUp(self):
        self.page = dict(entries=[
            dict(index=0, entry=dict(kind='system', text='exact startup routing')),
            dict(index=1, entry=dict(kind='error', text='exact startup diagnostic')),
            dict(index=2, entry=dict(kind='assistant', text='complete reply')),
            dict(index=3, entry=dict(kind='tool', text='complete tool result')),
        ], next_before=None, capture_error=None, capture_pending=False)
        self.policy = dict(pair_entry_sha256=[digest(r['entry']) for r in self.page['entries'][:2]])

    def test_only_verified_leading_swap_compares_equal(self):
        swapped = deepcopy(self.page)
        swapped['entries'][0]['entry'], swapped['entries'][1]['entry'] = (
            swapped['entries'][1]['entry'], swapped['entries'][0]['entry'])
        self.assertNotEqual(digest(self.page), digest(swapped))
        self.assertEqual(canonical_page(self.page, self.policy), canonical_page(swapped, self.policy))

    def test_no_policy_preserves_exact_page(self):
        original = deepcopy(self.page)
        self.assertEqual(canonical_page(self.page), original)
        canonical_page(self.page, self.policy)
        self.assertEqual(self.page, original)

    def test_changed_diagnostic_or_duplicate_rejected(self):
        for mode in ['change', 'duplicate']:
            altered = deepcopy(self.page)
            altered['entries'][0]['entry'] = (dict(kind='system', text='changed') if mode == 'change'
                                             else deepcopy(altered['entries'][1]['entry']))
            with self.assertRaises(ValueError):
                canonical_page(altered, self.policy)

    def test_pair_at_other_indices_rejected(self):
        self.page['entries'][0]['index'] = 7
        with self.assertRaises(ValueError):
            canonical_page(self.page, self.policy)

    def test_missing_pair_rejected(self):
        self.page['entries'] = self.page['entries'][:1]
        with self.assertRaises(ValueError):
            canonical_page(self.page, self.policy)

    def test_reply_or_tool_change_still_changes_digest(self):
        expected = digest(canonical_page(self.page, self.policy))
        for index in [2, 3]:
            altered = deepcopy(self.page)
            altered['entries'][index]['entry']['text'] = 'truncated'
            self.assertNotEqual(digest(canonical_page(altered, self.policy)), expected)

    def test_other_order_missing_or_duplicate_entry_still_fails_comparison(self):
        expected = digest(canonical_page(self.page, self.policy))
        for tail in [list(reversed(self.page['entries'][2:])), [], self.page['entries'][2:] * 2]:
            altered = deepcopy(self.page)
            altered['entries'] = altered['entries'][:2] + deepcopy(tail)
            self.assertNotEqual(digest(canonical_page(altered, self.policy)), expected)

    def test_capture_and_pagination_metadata_remain_checked(self):
        expected = digest(canonical_page(self.page, self.policy))
        for field, value in [('capture_error', 'incomplete'), ('capture_pending', True), ('next_before', 12)]:
            altered = deepcopy(self.page)
            altered[field] = value
            self.assertNotEqual(digest(canonical_page(altered, self.policy)), expected)


if __name__ == '__main__':
    unittest.main()
