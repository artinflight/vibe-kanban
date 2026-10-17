import copy
import types
import unittest
import uuid
from unittest.mock import Mock, patch

import credit_budget
from prepare_credit_budget_status import ORIGINAL, patched

# Synthetic scope only. The real workspace binding is private deployment data.
CU = '11111111-1111-4111-8111-111111111111'
OTHER = '22222222-2222-4222-8222-222222222222'


def candidate():
    module = types.ModuleType('isolated_status')
    module.workspace_id = lambda value: str(uuid.UUID(value))
    module.Store = Mock(side_effect=AssertionError('Only isolated stores allowed'))
    exec(patched(ORIGINAL, CU), module.__dict__)
    return module


def delivery(fresh=False):
    return {'workspace_id': CU, 'hold': {'held': 1, 'version': 7, 'source': 'synthetic explicit intent'},
        'receipts': [{'receipt_id': 'synthetic', 'status': 'held', 'proof': None, 'payload': 'unchanged'}],
        'automatic_marking': 'requires_verified_atomic_backend', 'polling_interval_seconds': None,
        'proof_origin': 'receipt_ledger', 'readback_fresh': fresh, 'future_delivery_field': {'retained': True}}


class StatusCompatibility(unittest.TestCase):
    def test_only_adds_budget_and_preserves_every_delivery_value(self):
        for fresh in [False, True]:
            original = delivery(fresh)
            before = copy.deepcopy(original)
            budget = {'status': 'current', 'fresh': True,
                'readback': {'walletBalanceCredits': '1.12345678901234567890123456789',
                    'weeklyCredits': {'verifiedBankedRolloverCredits': None},
                    'admission': {'permissionGranted': False}}}
            store = Mock();store.status.return_value = original
            with patch.object(credit_budget, 'read_credit_budget', return_value=budget) as read:
                result = candidate().status(Mock(), {'workspace_id': CU}, store)
            self.assertIs(result['credit_budget'], budget)
            self.assertEqual({k: v for k, v in result.items() if k != 'credit_budget'}, before)
            self.assertEqual(original, before)
            store.status.assert_called_once_with(CU)
            read.assert_called_once_with()

    def test_other_workspace_returns_same_object_and_never_reads_credits(self):
        original = delivery();original['workspace_id'] = OTHER
        store = Mock();store.status.return_value = original
        with patch.object(credit_budget, 'read_credit_budget') as read:
            result = candidate().status(Mock(), {'workspace_id': OTHER}, store)
        self.assertIs(result, original)
        self.assertNotIn('credit_budget', result)
        read.assert_not_called()

    def test_stale_and_unavailable_budget_do_not_change_delivery_freshness(self):
        for budget in [{'status': 'stale', 'fresh': False, 'readback': {'full': 'stale contract'}},
                       {'status': 'unavailable', 'fresh': False, 'readback': None}]:
            original = delivery(False)
            store = Mock();store.status.return_value = original
            with patch.object(credit_budget, 'read_credit_budget', return_value=budget):
                result = candidate().status(Mock(), {'workspace_id': CU}, store)
            self.assertEqual(result['credit_budget'], budget)
            self.assertIs(result['readback_fresh'], False)
            self.assertEqual(result['hold'], original['hold'])
            self.assertEqual(result['receipts'], original['receipts'])

    def test_workspace_validation_and_old_argument_contract_remain(self):
        for args in [{}, {'workspace_id': CU, 'refresh': True}, {'workspace_id': CU, 'url': 'http://elsewhere/'},
                     {'workspace_id': 'not-a-uuid'}]:
            store = Mock()
            with patch.object(credit_budget, 'read_credit_budget') as read:
                with self.assertRaises((ValueError, KeyError)):
                    candidate().status(Mock(), args, store)
            store.status.assert_not_called();read.assert_not_called()

    def test_each_status_call_reads_current_data_without_cache(self):
        store = Mock();store.status.return_value = delivery()
        values = [{'status': 'current', 'fresh': True, 'readback': {'sequence': i}} for i in [1, 2]]
        module = candidate()
        with patch.object(credit_budget, 'read_credit_budget', side_effect=values) as read:
            replies = [module.status(Mock(), {'workspace_id': CU}, store) for _ in values]
        self.assertEqual([r['credit_budget'] for r in replies], values)
        self.assertEqual(read.call_count, 2)

    def test_normalized_uuid_matches_only_configured_scope(self):
        store = Mock();store.status.return_value = delivery()
        with patch.object(credit_budget, 'read_credit_budget', return_value={'fresh': False}) as read:
            candidate().status(Mock(), {'workspace_id': '{' + CU + '}'}, store)
        read.assert_called_once_with()

    def test_preparation_changes_only_the_one_status_function(self):
        prefix = '# Existing policy, holds and receipt implementation\n'
        suffix = '\nTOOLS = [{"name": "unchanged"}]\nHANDLERS = {"old": status}\n'
        source = prefix + ORIGINAL + suffix
        result = patched(source, CU)
        self.assertTrue(result.startswith(prefix));self.assertTrue(result.endswith(suffix))
        self.assertEqual(result.count('read_credit_budget()'), 1)
        for bad in ['', source + ORIGINAL, result]:
            with self.assertRaises(ValueError):patched(bad, CU)
        for scope in ['not-a-uuid', str(uuid.UUID(int=0))]:
            with self.assertRaises(ValueError):patched(source, scope)


if __name__ == '__main__':
    unittest.main()
