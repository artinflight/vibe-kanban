#!/usr/bin/env python3
"""Focused tests of the embedded PRODUCTION CU reader; zero provider inference."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('provider_receipts', ROOT / 'scripts/routing/provider_receipts.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
NOW = 1792608000000
POOL = 'pool-' + 'a' * 24
OTHER = 'pool-' + 'b' * 24

def iso(ms):
    return m.dt.datetime.fromtimestamp(ms / 1000, m.dt.timezone.utc).isoformat().replace('+00:00','Z')

def quota(**changes):
    row = {'schemaVersion': m.SCHEMA, 'normalizationVersion': 1, 'kind': 'quota',
           'provider': 'anthropic', 'product': 'claude-code', 'poolId': POOL,
           'billingSource': 'subscription', 'sourceKind': 'cli-export', 'evidence': 'observed',
           'sourceVersion': 'synthetic-native-v1', 'evidenceRef': 'synthetic-receipt-1',
           'eventId': 'synthetic-window-1', 'observedAt': iso(NOW - 1000),
           'quota': {'windowMinutes': 420, 'usedPercent': 25, 'resetsAt': iso(NOW + 300000),
                     'semantics': 'anchored', 'signal': 'available', 'model': None}}
    row.update(changes)
    return row

def report(events=None):
    return {'schemaVersion': m.SCHEMA, 'normalizationVersion': 1, 'advisoryOnly': True,
            'generatedAt': iso(NOW), 'products': [], 'pools': [], 'events': events or []}

def request(**changes):
    result = {'provider': 'claude', 'poolId': POOL, 'bindingReceipt': 'synthetic-independent-native-binding', 'model':'claude-sonnet-4-6'}
    result.update(changes)
    return result

def codes(result):
    return {b['code'] for b in result['blockers']}

class CUReceipts(unittest.TestCase):
    def test_exact_pinned_cu_producer_generated_schema_is_consumed(self):
        fixture=json.loads((ROOT/'scripts/testing/fixtures/cu-provider-pinned.json').read_text())
        generated=fixture['available'];pool=generated['pools'][0]['poolId']
        r=m.inspect_report(generated,request(poolId=pool),fixture['nowMs'])
        self.assertEqual(r['quotaState'],'observed-available');self.assertEqual(r['blockers'],[])
        self.assertFalse(r['dispatchAuthority']);self.assertEqual(r['windowInventory'],'not-declared-by-source')
        unknown=m.inspect_report(fixture['unknown'],request(poolId=None,bindingReceipt=None),fixture['nowMs'])
        self.assertIn('cu_account_pool_binding_unknown',codes(unknown))
        self.assertIn('cu_quota_observations_unavailable',codes(unknown))

    def test_actual_schema_fresh_observed_window_is_not_admission_or_measured_capacity(self):
        r = m.inspect_report(report([quota()]), request(), NOW)
        self.assertEqual(r['quotaState'], 'observed-available')
        self.assertTrue(r['bindingMatched'])
        self.assertEqual(r['windows'][0]['windowMinutes'],420) # no assumed five hours
        self.assertEqual(r['windowInventory'],'not-declared-by-source')
        self.assertIsNone(r['generation']);self.assertIsNone(r['capacityMeasurement'])
        self.assertFalse(r['dispatchAuthority']);self.assertFalse(r['providerStarted'])

    def test_deployed_unbound_usage_shape_never_becomes_quota(self):
        # Synthetic shape of deployed unbound usage metadata. Tokens
        # are usage only; unknown account/pool/quota is retained, never zeroed.
        usage=[dict(kind='usage',provider='anthropic',product='claude-code',poolId=None,totalTokens=4321)]
        r=m.inspect_report(report(usage), request(poolId=None,bindingReceipt=None), NOW)
        self.assertIn('cu_account_pool_binding_unknown',codes(r))
        self.assertIn('cu_quota_observations_unavailable',codes(r))
        self.assertEqual(r['quotaState'],'unknown');self.assertIsNone(r['capacityMeasurement'])

    def test_wrong_account_or_pool_is_not_an_alias(self):
        r=m.inspect_report(report([quota(poolId=OTHER)]),request(),NOW)
        self.assertIn('cu_account_pool_mismatch',codes(r))
        self.assertFalse(r['bindingMatched'])

    def test_report_generated_time_and_display_fresh_flag_do_not_refresh_old_quota(self):
        e=quota(observedAt=iso(NOW-60000));d=report([e]);d['generatedAt']=iso(NOW)
        d['pools']=[{'poolId':POOL,'windows':[{'fresh':True}]}]
        r=m.inspect_report(d,request(),NOW)
        self.assertIn('cu_quota_stale',codes(r));self.assertEqual(r['quotaObservedAtMs'],NOW-60000)
        d['generatedAt']=iso(NOW+100000)
        self.assertIn('cu_quota_stale',codes(m.inspect_report(d,request(),NOW)))

    def test_future_quota_timestamp_fails_closed(self):
        self.assertIn('cu_quota_stale',codes(m.inspect_report(report([quota(observedAt=iso(NOW+1))]),request(),NOW)))

    def test_reset_clock_alone_never_readmits(self):
        e=quota();e['quota']['resetsAt']=iso(NOW)
        self.assertIn('cu_reset_recovery_unverified',codes(m.inspect_report(report([e]),request(),NOW)))

    def test_usage_fetch_throttle_is_not_work_quota_exhaustion(self):
        e=quota();e['quota']['signal']='usage-endpoint-throttled'
        r=m.inspect_report(report([e]),request(),NOW)
        self.assertIn('cu_usage_fetch_throttled',codes(r))
        self.assertNotIn('cu_provider_quota_exhausted',codes(r))

    def test_actual_exhaustion_is_separate_from_auth_outage_or_task_failure(self):
        e=quota();e['quota']['signal']='work-exhausted'
        r=m.inspect_report(report([e]),request(),NOW)
        self.assertIn('cu_provider_quota_exhausted',codes(r))
        for kind in ['task','usage']:
            other=quota(kind=kind);other['stopReason']='provider-error'
            self.assertNotIn('cu_provider_quota_exhausted',codes(m.inspect_report(report([other]),request(),NOW)))

    def test_native_availability_exhaustion_is_not_cleared_by_clock_or_other_quota(self):
        e=quota(kind='availability',observedAt=iso(NOW-120000))
        e['availability']={'signal':'work-exhausted','reportedResetAt':iso(NOW-1000),
                           'basis':'native-terminal','recovery':'unverified'}
        r=m.inspect_report(report([e,quota()]),request(),NOW)
        self.assertIn('cu_reset_scope_unverified',codes(r))
        self.assertEqual(r['quotaState'],'recovery-unverified')
        self.assertTrue(r['availabilityObservations'][0]['accountBound'])
        e['poolId']=OTHER
        self.assertEqual(m.inspect_report(report([e,quota()]),request(),NOW)['blockers'],[])
        e['poolId']=None
        self.assertIn('cu_availability_binding_unverified',codes(m.inspect_report(report([e,quota()]),request(),NOW)))

    def test_native_availability_throttle_is_metadata_only_and_manual_is_unverified(self):
        e=quota(kind='availability')
        e['availability']={'signal':'usage-endpoint-throttled','reportedResetAt':None,'basis':'native-terminal'}
        r=m.inspect_report(report([e,quota()]),request(),NOW)
        self.assertIn('cu_usage_fetch_throttled',codes(r))
        self.assertNotIn('cu_provider_quota_exhausted',codes(r))
        e['availability']['signal']='work-exhausted'
        e['availability']['basis']='operator-supplied-native-terminal-ui'
        self.assertIn('cu_availability_binding_unverified',codes(m.inspect_report(report([e,quota()]),request(),NOW)))

    def test_other_models_quota_does_not_prove_selected_model(self):
        e=quota();e['quota']['model']='different-model'
        self.assertIn('cu_quota_observations_unavailable',codes(m.inspect_report(report([e]),request(),NOW)))

    def test_manual_fixture_api_and_unproven_version_stay_observations(self):
        for changes, expected in [({'sourceKind':'manual','evidence':'manual'},'cu_quota_source_not_native_verified'),
                                  ({'sourceKind':'fixture','evidence':'fixture'},'cu_quota_source_not_native_verified'),
                                  ({'billingSource':'api'},'cu_subscription_route_unproven'),
                                  ({'sourceVersion':None},'cu_quota_provenance_incomplete')]:
            self.assertIn(expected,codes(m.inspect_report(report([quota(**changes)]),request(),NOW)))

    def test_conflicts_duplicate_and_latest_window_evidence(self):
        e=quota();d=copy.deepcopy(e);d['quota']['usedPercent']=30
        self.assertIn('cu_quota_conflicting',codes(m.inspect_report(report([e,d]),request(),NOW)))
        r=m.inspect_report(report([e,e]),request(),NOW);self.assertEqual(r['blockers'],[])
        old=quota(observedAt=iso(NOW-60000))
        for rows in [[old,e],[e,old]]:
            self.assertEqual(m.inspect_report(report(rows),request(),NOW)['blockers'],[])

    def test_window_expiry_uses_tightest_applicable_window_without_summing_percentages(self):
        e=quota();d=quota(eventId='weekly');d['quota']['windowMinutes']=10080;d['quota']['resetsAt']=iso(NOW+10000)
        r=m.inspect_report(report([e,d]),request(),NOW)
        self.assertEqual(r['quotaExpiresAtMs'],NOW+10000);self.assertIsNone(r['capacityMeasurement'])

    def test_schema_bounds_missing_time_and_nonfinite_values_fail_closed(self):
        for d in [dict(report(),schemaVersion='future'),dict(report(),events=[None]),dict(report(),advisoryOnly=False)]:
            with self.assertRaises(m.ObservationError):m.inspect_report(d,request(),NOW)
        for value in [True,float('nan'),101]:
            e=quota();e['quota']['usedPercent']=value
            with self.assertRaises(m.ObservationError):m.inspect_report(report([e]),request(),NOW)
        with self.assertRaises(m.ObservationError):m.inspect_report(report([quota(observedAt='6:20PM')]),request(),NOW)

    def test_credit_reporting_permission_false_is_not_a_provider_policy(self):
        d={'contractVersion':'account-credit-budget-v1','scope':'all-account-use','unit':'credit',
           'fresh':True,'observedAt':iso(NOW-1000),'expiresAt':iso(NOW+300000),
           'admission':{'permissionGranted':False,'stopLaunchingMoreTurns':True}}
        c=m.credit_observation(d,NOW)
        self.assertTrue(c['historicalHoldObserved']);self.assertFalse(c['permissionAuthority'])
        self.assertEqual(c['accountBinding'],'not-exposed-by-this-contract')
        d['observedAt']=iso(NOW-60000);self.assertFalse(m.credit_observation(d,NOW)['observationFresh'])
        r=m.inspect_report(report([quota()]),request(),NOW)
        self.assertEqual(r['quotaState'],'observed-available') # no global false-flag veto

    def test_client_is_get_only_local_bounded_without_proxy_credentials_or_redirect(self):
        calls=[]
        class Response(io.BytesIO):
            status=200
            headers={'Content-Type':'application/json'}
        def open_request(req,timeout):
            calls.append(req)
            self.assertEqual(req.get_method(),'GET');self.assertEqual(timeout,3)
            self.assertTrue(req.full_url.startswith(m.ORIGIN+'/api/'))
            self.assertNotIn('Authorization',req.headers)
            value=report([quota()]) if req.full_url.endswith('/providers') else {'contractVersion':'account-credit-budget-v1','scope':'all-account-use','unit':'credit','admission':{}}
            return Response(json.dumps(value).encode())
        r=m.read_observations(request(),open_request,NOW)
        self.assertEqual(len(calls),2);self.assertFalse(r['dispatchAuthority'])
        with self.assertRaises(m.ObservationError):m.fetch('https://provider.invalid/quota',open_request)
        with self.assertRaises(m.ObservationError):m.NoRedirect().redirect_request(None,None,302,'',{},'https://provider.invalid')
        with self.assertRaises(m.ObservationError):m.fetch('/api/providers',lambda *a,**kw:Response(b'x'*(m.MAX_BODY+1)))

    def test_read_only_path_never_spawns_or_grants_even_when_metadata_succeeds(self):
        with patch('subprocess.Popen',side_effect=AssertionError('spawn forbidden')):
            result=m.inspect_report(report([quota()]),request(),NOW)
        self.assertFalse(result['providerStarted']);self.assertFalse(result['dispatchAuthority'])
        self.assertNotIn('permit',result);self.assertNotIn('budget_granted',result)

if __name__=='__main__':unittest.main(verbosity=2)
