import datetime as dt
import json
import unittest
from unittest.mock import Mock, patch
import urllib.error
import urllib.request

import credit_budget as m
from prepare_credit_budget_connector import patched

NOW = dt.datetime(2026, 10, 17, 2, 0, tzinfo=dt.timezone.utc)


def fixture():
    dated = {'fresh': True, 'observedAt': NOW.isoformat(),
             'expiresAt': (NOW + dt.timedelta(seconds=60)).isoformat()}
    return dict(dated, contractVersion='account-credit-budget-v1', unit='credit', scope='all-account-use',
        walletBalanceCredits='1000.12345678901234567890123456789012', billedSpendCredits=None,
        pendingUsageCredits=None, weeklyCredits=dict(dated,
            contractVersion='weekly-credit-allocation-v1', unit='credit', verifiedBankedRolloverCredits=None,
            overnight=dict(dated, contractVersion='overnight-credit-checkpoint-v1',
                verifiedCombinedRemainingCredits=None, advanceReservationEnforced=True,
                externalControllerReservationEnforcement='unverified', stopLaunchingMoreTurns=False)),
        admission={'permissionGranted': False, 'automaticStopEnforced': False})


class Readback(unittest.TestCase):
    def test_exact_decimals_null_and_holds_pass_through(self):
        body = fixture()
        reply = m._validated(body, NOW)
        self.assertTrue(reply['fresh'])
        self.assertEqual(reply['readback'], body)
        self.assertIs(reply['readback'], body)
        self.assertIsNone(body['weeklyCredits']['verifiedBankedRolloverCredits'])
        self.assertEqual(body['weeklyCredits']['overnight']['externalControllerReservationEnforcement'], 'unverified')

    def test_stale_boundary_and_future_clock(self):
        for delta in [-1, 60, 61]:
            self.assertFalse(m._validated(fixture(), NOW + dt.timedelta(seconds=delta))['fresh'])

    def test_expiry_and_upstream_stale(self):
        for path in [(), ('weeklyCredits',), ('weeklyCredits', 'overnight')]:
            for key, value in [('fresh', False), ('expiresAt', (NOW + dt.timedelta(seconds=61)).isoformat())]:
                body = fixture()
                nested = body
                for part in path:
                    nested = nested[part]
                nested[key] = value
                self.assertFalse(m._validated(body, NOW)['fresh'])

    def test_no_permission_or_billed_inference(self):
        for key in ['permissionGranted', 'automaticStopEnforced']:
            body = fixture()
            body['admission'][key] = True
            with self.assertRaises(ValueError):
                m._validated(body, NOW)
        for key in ['billedSpendCredits', 'pendingUsageCredits']:
            body = fixture()
            body[key] = '0'
            with self.assertRaises(ValueError):
                m._validated(body, NOW)

    def test_unknown_contract_scope_and_nested_contract(self):
        for key in ['contractVersion', 'unit', 'scope']:
            body = fixture()
            body[key] = 'other'
            with self.assertRaises(ValueError):
                m._validated(body, NOW)
        body = fixture()
        body['weeklyCredits']['contractVersion'] = 'other'
        with self.assertRaises(ValueError):
            m._validated(body, NOW)

    def test_float_and_nonfinite_budget_values_are_rejected(self):
        for value in [1.25, 0, True, 'NaN', 'Infinity', 'invalid']:
            body = fixture()
            body['walletBalanceCredits'] = value
            with self.assertRaises((ValueError, m.InvalidOperation)):
                m._validated(body, NOW)

    def test_fixed_route_get_no_redirect_or_proxy(self):
        reply = Mock()
        reply.status = 200
        reply.read.return_value = json.dumps(fixture()).encode()
        reply.__enter__ = Mock(return_value=reply)
        reply.__exit__ = Mock(return_value=None)
        opener = Mock()
        opener.open.return_value = reply
        with patch.object(m.urllib.request, 'build_opener', return_value=opener) as builder:
            m.read_credit_budget()
        handlers = builder.call_args.args
        self.assertEqual(handlers[0].proxies, {})
        self.assertIsNone(handlers[1].redirect_request(None, None, 302, '', {}, 'http://elsewhere/'))
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, 'http://127.0.0.1:4177/api/credits/budget')
        self.assertEqual(request.get_method(), 'GET')
        self.assertIsNone(request.data)
        self.assertEqual(opener.open.call_args.kwargs, {'timeout': 5})
        reply.read.assert_called_once_with(65537)

    def test_read_failure_redacts_diagnostics_and_preserves_unknown(self):
        for error in [OSError('private diagnostics'), urllib.error.HTTPError('private-url', 302, 'redirect', {}, None)]:
            with patch.object(m.urllib.request, 'build_opener', side_effect=error):
                reply = m.read_credit_budget()
            self.assertFalse(reply['fresh'])
            self.assertIsNone(reply['readback'])
            self.assertNotIn('private', str(reply))

    def test_oversize_invalid_and_missing_response_are_unavailable(self):
        for raw in [b'x' * 65537, b'not json', b'{}', b'null']:
            reply = Mock(status=200)
            reply.__enter__ = Mock(return_value=reply)
            reply.__exit__ = Mock(return_value=None)
            reply.read.return_value = raw
            opener = Mock()
            opener.open.return_value = reply
            with patch.object(m.urllib.request, 'build_opener', return_value=opener):
                self.assertEqual(m.read_credit_budget()['status'], 'unavailable')

    def test_schema_and_dispatch_are_no_argument_read_only(self):
        tool = m.TOOLS[0]
        self.assertEqual(tool['name'], 'get_credit_budget')
        self.assertEqual(tool['inputSchema'], {'type': 'object', 'properties': {}, 'required': [], 'additionalProperties': False})
        self.assertEqual(tool['annotations'], {'readOnlyHint': True, 'destructiveHint': False,
            'idempotentHint': True, 'openWorldHint': False})
        api = Mock()
        for args in [{'url': 'http://elsewhere/'}, {'refresh': True}, [], None]:
            with self.assertRaises(ValueError):
                m.call(api, args)
        with patch.object(m, 'read_credit_budget', return_value={'fixture': True}) as read:
            m.call(api, {})
        read.assert_called_once_with()
        api.result.assert_called_once_with({'fixture': True})

    def test_preparation_fails_on_unknown_or_already_integrated_adapter(self):
        for source in ['', 'import credit_budget\n']:
            with self.assertRaises(ValueError):
                patched(source)


if __name__ == '__main__':
    unittest.main()
