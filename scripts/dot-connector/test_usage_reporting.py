import copy
import datetime as dt
import json
import sys
import types
import unittest
import uuid
from unittest.mock import Mock, patch

import credit_budget
import usage_reporting as m
from prepare_credit_budget_status import ORIGINAL, patched as budget_status
from prepare_usage_reporting import adapter, status

CU = '11111111-1111-4111-8111-111111111111'
OTHER = '22222222-2222-4222-8222-222222222222'


class Reporting(unittest.TestCase):
    def setUp(self):
        self.helper = types.ModuleType('dot_usage_report')
        self.helper.read_usage_report = Mock(return_value={'contractVersion': m.CONTRACT, 'fixture': True})
        self.helper.read_usage_summary = Mock(return_value={'contractVersion': m.CONTRACT, 'status': 'stale', 'fresh': False,
            'coverage': 'partial', 'totals': {'cost': None, 'tokens': '12345678901234567890'}})
        self.modules = patch.dict(sys.modules, {'dot_usage_report': self.helper})
        self.modules.start();self.addCleanup(self.modules.stop)
        self.api = Mock();self.api.result.side_effect = lambda value: value

    def test_schema_is_explicitly_readonly_and_has_no_path_url_refresh_or_control(self):
        self.assertEqual({t['name'] for t in m.TOOLS}, {'get_usage_report', 'get_usage_summary'})
        for tool in m.TOOLS:
            self.assertTrue(tool['annotations']['readOnlyHint'])
            self.assertFalse(tool['annotations']['openWorldHint'])
            self.assertFalse(tool['annotations']['destructiveHint'])
            self.assertFalse(tool['inputSchema']['additionalProperties'])
        self.assertEqual(set(m.PROPERTIES), {'window', 'from_time', 'to_time', 'group_by',
            'project_id', 'workspace_id', 'session_id', 'execution_id', 'model', 'limit', 'offset'})

    def test_defaults_delegate_exactly_once_without_changing_accounting(self):
        body = {'contractVersion': m.CONTRACT, 'accountTotals': {'credits': None, 'cost': '1.123456789123456789'},
                'rows': [], 'coverage': 'no_observations'}
        self.helper.read_usage_report.return_value = body
        result = m.call(self.api, 'get_usage_report', {})
        self.assertIs(result, body)
        self.helper.read_usage_report.assert_called_once_with(
            window='since_reset', group_by='workspace', limit=50, offset=0)

    def test_every_dimension_filter_and_window(self):
        for group in m.GROUPS:
            for window in ('since_reset', 'day', 'week'):
                args = dict(window=window, group_by=group, model='gpt-test',
                    project_id=CU, workspace_id=OTHER, session_id=CU, execution_id=OTHER,
                    limit=1, offset=3)
                m.call(self.api, 'get_usage_report', args)
                self.helper.read_usage_report.assert_called_with(**args)

    def test_custom_half_open_boundaries_preserved_and_31_days_allowed(self):
        args = {'window': 'custom', 'from_time': '2026-09-01T00:00:00Z',
                'to_time': '2026-10-02T00:00:00+00:00'}
        m.call(self.api, 'get_usage_report', args)
        got = self.helper.read_usage_report.call_args.kwargs
        self.assertEqual(got['from_time'], args['from_time'])
        self.assertEqual(got['to_time'], args['to_time'])

    def test_pagination_cutoff_can_pin_every_noncustom_window(self):
        for window in ('since_reset', 'day', 'week'):
            args = {'window': window, 'to_time': '2026-10-17T10:02:00Z', 'offset': 50}
            m.call(self.api, 'get_usage_report', args)
            self.assertEqual(self.helper.read_usage_report.call_args.kwargs['to_time'], args['to_time'])

    def test_custom_can_use_latest_recorded_cutoff_without_inventing_to_time(self):
        args = {'window': 'custom', 'from_time': '2026-10-17T10:02:00Z'}
        m.call(self.api, 'get_usage_report', args)
        got = self.helper.read_usage_report.call_args.kwargs
        self.assertEqual(got['from_time'], args['from_time'])
        self.assertNotIn('to_time', got)
        self.helper.read_usage_report.assert_called_once()

    def test_invalid_inputs_fail_before_any_read(self):
        invalid = [[], None, False, {'path': '/private'}, {'url': 'http://host'},
            {'refresh': True}, {'window': 'all'}, {'window': None}, {'group_by': 'prompt'},
            {'limit': 0}, {'limit': 101}, {'limit': True}, {'offset': -1}, {'offset': 100001},
            {'offset': False}, {'model': ''}, {'model': '\n'}, {'model': 'x' * 129},
            {'workspace_id': 'invalid'}, {'execution_id': 0}, {'session_id': str(uuid.UUID(int=0))},
            {'from_time': '2026-10-17T00:00:00Z'}, {'to_time': 'invalid'}, {'window': 'custom'},
            {'window': 'custom', 'from_time': '2026-10-01', 'to_time': '2026-10-02'},
            {'window': 'custom', 'from_time': '2026-10-01T00:00:00', 'to_time': '2026-10-02T00:00:00'},
            {'window': 'custom', 'from_time': '2026-10-02T00:00:00Z', 'to_time': '2026-10-01T00:00:00Z'},
            {'window': 'custom', 'from_time': '2026-10-01T00:00:00Z', 'to_time': '2026-10-01T00:00:00Z'},
            {'window': 'custom', 'from_time': '2026-09-01T00:00:00Z', 'to_time': '2026-10-03T00:00:00Z'}]
        for args in invalid:
            with self.subTest(args=args), self.assertRaises(ValueError):
                m.call(self.api, 'get_usage_report', args)
        self.helper.read_usage_report.assert_not_called()
        self.helper.read_usage_summary.assert_not_called()

    def test_missing_database_and_malformed_response_do_not_become_zero(self):
        for error in (OSError('/private/path'), ValueError('private details'), KeyError('private key')):
            self.helper.read_usage_report.side_effect = error
            response = m.call(self.api, 'get_usage_report', {})
            self.assertEqual(response['status'], 'unavailable')
            self.assertIsNone(response['readback'])
            self.assertNotIn('private', json.dumps(response))
        self.helper.read_usage_report.side_effect = None
        for body in (None, [], {}, {'contractVersion': 'unexpected'},
                     {'contractVersion': m.CONTRACT, 'bad': float('nan')},
                     {'contractVersion': m.CONTRACT, 'too_large': 'x' * m.MAX_BYTES}):
            self.helper.read_usage_report.return_value = body
            self.assertEqual(m.call(self.api, 'get_usage_report', {})['status'], 'unavailable')

    def test_summary_preserves_stale_coverage_exact_values_and_rejects_large_payload(self):
        result = m.call(self.api, 'get_usage_summary', {})
        self.assertEqual(result, self.helper.read_usage_summary.return_value)
        self.assertFalse(result['fresh'])
        self.assertIsNone(result['totals']['cost'])
        self.helper.read_usage_summary.return_value = {'contractVersion': m.CONTRACT, 'large': 'x' * 16384}
        self.assertEqual(m.read_summary()['status'], 'unavailable')

    def test_summary_has_no_caller_selection_and_no_full_report(self):
        for args in (None, [], False, {'limit': 5}, {'window': 'day'}):
            with self.assertRaises(ValueError):m.call(self.api, 'get_usage_summary', args)
        self.helper.read_usage_summary.assert_not_called()
        self.helper.read_usage_report.assert_not_called()

    def test_status_preserves_old_delivery_budget_and_unrelated_workspace(self):
        module = types.ModuleType('test_status')
        module.workspace_id = lambda value: str(uuid.UUID(value))
        exec(status(budget_status(ORIGINAL, CU), CU), module.__dict__)
        delivery = {'readback_fresh': False, 'hold': {'retained': True},
                    'receipts': [{'id': 'synthetic'}], 'unknown_future_field': 'unchanged'}
        before = copy.deepcopy(delivery)
        store = Mock();store.status.return_value = delivery
        budget = {'fresh': True, 'readback': {'credits': None}}
        with patch.object(credit_budget, 'read_credit_budget', return_value=budget) as read:
            result = module.status(Mock(), {'workspace_id': CU}, store)
            self.assertEqual({k: v for k, v in result.items() if k not in
                {'credit_budget', 'usage_report'}}, before)
            self.assertIs(result['credit_budget'], budget)
            self.assertEqual(result['usage_report'], self.helper.read_usage_summary.return_value)
            self.assertEqual(delivery, before)
            result = module.status(Mock(), {'workspace_id': OTHER}, store)
            self.assertIs(result, delivery)
            read.assert_called_once_with()
        self.helper.read_usage_summary.assert_called_once_with()
        self.helper.read_usage_report.assert_not_called()

    def test_status_patches_only_budget_function_with_exact_private_scope(self):
        source = 'PREFIX = 1\n' + budget_status(ORIGINAL, CU) + '\nTOOLS = ["unchanged"]\n'
        result = status(source, CU)
        self.assertTrue(result.startswith('PREFIX = 1\n'))
        self.assertTrue(result.endswith('\nTOOLS = ["unchanged"]\n'))
        for bad in (ORIGINAL, source + source, result):
            with self.assertRaises(ValueError):status(bad, CU)
        with self.assertRaises(ValueError):status(source, OTHER)

    def test_adapter_overlay_refuses_changed_or_already_patched_source(self):
        with self.assertRaises(ValueError):adapter('unknown baseline')
        with self.assertRaises(ValueError):adapter('import usage_reporting\n')


if __name__ == '__main__':
    unittest.main()
