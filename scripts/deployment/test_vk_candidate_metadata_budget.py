import unittest

from test_vk_candidate_direct_b import ContractTests
from vk_candidate_direct_b import DirectBProvider, MAX_INDEX_BYTES
from vk_candidate_generation import Blocked


class MetadataBudgetTests(ContractTests):
    def test_default_unchanged_and_unbounded_policies_rejected(self):
        self.assertEqual(self.provider.metadata_budget_bytes, MAX_INDEX_BYTES)
        for value in (0, -1, True, 256 * 1024**2 + 1):
            with self.assertRaises(Blocked):
                DirectBProvider(self.scope, [], archive_factory=self.factory,
                                fixture_only=True, metadata_budget_bytes=value)

    def test_explicit_catalog_bound_checked_and_included_in_proof(self):
        result, _ = self.capture('metadata-bound')
        provider = DirectBProvider(self.scope, ['home/state/state.sqlite'],
                archive_factory=self.factory, fixture_only=True, metadata_budget_bytes=128*1024)
        record = self.provider.records['metadata-bound']
        provider.register('metadata-bound', result, record['plan'], record['scope'], self.inc,
                          origin_root_binding='incumbent')
        proof = provider.verify('metadata-bound')
        self.assertEqual(proof['metadata_budget_bytes'], 128*1024)
        self.assertGreater(proof['metadata_encoded_bytes'], 1)
        provider.metadata_budget_bytes = 1
        with self.assertRaisesRegex(Blocked, 'metadata budget'):
            provider.verify('metadata-bound')


if __name__ == '__main__':
    suite = unittest.TestSuite(MetadataBudgetTests(name) for name in (
        'test_default_unchanged_and_unbounded_policies_rejected',
        'test_explicit_catalog_bound_checked_and_included_in_proof'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
