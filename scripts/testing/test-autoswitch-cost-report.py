#!/usr/bin/env python3
"""Synthetic accounting fixtures only: fixture units are not billing weights."""
import copy
import datetime as dt
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('cost', Path(__file__).parents[1] / 'vk-autoswitch-cost-report.py')
cost = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cost)


class Accounting(unittest.TestCase):
    def setUp(self):
        self.settings = {'model': 'workhorse', 'reasoningEffort': 'high', 'serviceTier': 'standard'}
        self.execution = {'executionId': 'one', 'requested': {'model': 'frontier'}, 'decision': {'account_fingerprint': 'fixture-account', 'selected_model': 'routine', 'selected_effort': 'low', 'service_tier': 'standard', 'assessed_envelope': 'bounded', 'triage': {'uncertainty': 'low', 'ambiguity': 'low', 'needs_repo_inspection': False}, 'semantic': {'id': 'classifier-one', 'model': 'classifier', 'effort': 'low', 'service_tier': 'standard', 'input_tokens': 100, 'cached_input_tokens': 20, 'output_tokens': 10, 'reasoning_tokens': 5}}}
        self.events = {'binding': {'eventId': 'binding', 'kind': 'turn_bound', 'executionId': 'one', 'nativeThreadId': 'thread', 'nativeTurnId': 'turn', 'settingsSource': 'runtime_confirmed', 'effective': self.settings}}
        self.usage = {('thread', 'turn'): {**self.settings, 'complete': True, 'provenance': 'synthetic-native-export', 'tokens': {'input': 1000, 'cachedInput': 400, 'output': 100, 'reasoning': 50}}}
        self.weights = {'provenance': {'unit': 'fixture_units', 'accountScope': 'fixture-account'}, 'version': 'test-only', 'sha256': 'fixture', 'rates': {('workhorse', 'high', 'standard'): (Decimal(4), Decimal(1), Decimal(8)), ('routine', 'low', 'standard'): (Decimal(1), Decimal('.25'), Decimal(2)), ('classifier', 'low', 'standard'): (Decimal(1), Decimal('.25'), Decimal(2))}}
        self.models = [{'id': 'routine', 'qualifications': [{'effort': 'low', 'envelope': 'bounded', 'status': 'qualified'}]}]

    def run_report(self, **kw):
        return cost.report(kw.get('executions', [self.execution]), kw.get('events', self.events), kw.get('usage', self.usage), kw.get('weights', self.weights), kw.get('outcomes'), kw.get('models', self.models))

    def test_actual_baseline_wins_over_requested_frontier(self):
        row = self.run_report()['executions'][0]
        self.assertEqual(row['actualNative'][0]['model'], 'workhorse')
        self.assertEqual(row['costScenario']['baselineCost'], '0.0036')
        self.assertEqual(row['costScenario']['recommendedCost'], '0.0009')
        self.assertIsNone(row['netSavings'])

    def test_cache_discount_and_reasoning_not_double_counted(self):
        self.assertEqual(cost.price(self.settings, cost.tokens(self.usage[('thread', 'turn')]['tokens']), self.weights, 'fixture-account'), Decimal('.0036'))

    def test_classifier_is_part_of_attributed_total(self):
        self.assertEqual(self.run_report()['executions'][0]['observedAttributedCost'], '0.003705')

    def test_unknown_weights_never_become_rank_based_savings(self):
        row = self.run_report(weights=None)['executions'][0]
        self.assertIsNone(row['observedAttributedCost']); self.assertIsNone(row['costScenario'])

    def test_account_and_service_tier_must_match(self):
        self.assertIsNone(cost.price(self.settings, cost.tokens(self.usage[('thread', 'turn')]['tokens']), self.weights, 'other-account'))
        self.usage[('thread', 'turn')]['serviceTier'] = None
        self.events['binding']['effective']['serviceTier'] = None
        self.assertIsNone(self.run_report()['executions'][0]['observedAttributedCost'])

    def test_weights_must_cover_the_actual_native_observation_date(self):
        self.weights['provenance'].update(validFrom='2026-10-12T00:00:00Z', validUntil='2026-10-13T00:00:00Z')
        counts = cost.tokens(self.usage[('thread','turn')]['tokens'])
        for at in (None, '2026-10-11T12:00:00Z', 'invalid'):
            self.assertIsNone(cost.price(self.settings, counts, self.weights, 'fixture-account', at))
        self.assertEqual(cost.price(self.settings, counts, self.weights, 'fixture-account', '2026-10-12T12:00:00Z'), Decimal('.0036'))

    def test_missing_or_partial_native_usage_remains_unknown(self):
        for usage in ({}, {('thread', 'turn'): {**self.usage[('thread', 'turn')], 'complete': False}}):
            self.assertIsNone(self.run_report(usage=usage)['executions'][0]['observedAttributedCost'])

    def test_absent_classifier_is_zero_but_unknown_attempt_is_not(self):
        self.execution['decision'].pop('semantic')
        self.assertEqual(self.run_report()['executions'][0]['observedAttributedCost'], '0.0036')
        self.execution['decision']['semantic'] = {'id': 'unavailable'}
        row = self.run_report()['executions'][0]
        self.assertIsNone(row['observedAttributedCost'])
        self.assertIn('classifier_usage_unknown', row['gaps'])

    def test_unknown_cache_does_not_erase_known_input_output(self):
        self.execution['decision']['semantic']['cached_input_tokens'] = None
        self.usage[('thread','turn')]['tokens']['cachedInput'] = None
        result = self.run_report()
        self.assertEqual(result['classifierKnownTokenSubtotal']['input'], 100)
        self.assertEqual(result['executions'][0]['nativeKnownTokenSubtotal']['input'], 1000)
        self.assertIsNone(result['executions'][0]['observedAttributedCost'])

    def test_native_conflict_is_not_silently_resolved(self):
        self.usage[('thread', 'turn')]['model'] = 'different'
        with self.assertRaises(ValueError): self.run_report()

    def test_no_timestamp_fallback_or_synthetic_baseline(self):
        result = self.run_report(events={})
        self.assertEqual(result['missingNativeBindings'], 1)
        self.assertEqual(result['actualExecutions'], {})
        self.assertIsNone(result['executions'][0]['costScenario'])

    def test_immutable_records_ignore_partial_tail_and_verify_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/'events.jsonl'
            line = json.dumps({'schema': 'vk.routing.v1', 'eventId': 'one'}).encode() + b'\n'
            p.write_bytes(line + line + b'{"schema":')
            rows = cost.immutable_records(p, 'vk.routing.v1', lambda x:x.get('eventId'))
            self.assertEqual(len(rows), 1)
            self.assertTrue(rows.incomplete_tail)
            self.assertEqual(rows.sha256, cost.digest(line + line))
            p.write_bytes(line + json.dumps({'schema': 'vk.routing.v1', 'eventId': 'one', 'conflict': True}).encode()+b'\n')
            with self.assertRaises(ValueError): cost.immutable_records(p, 'vk.routing.v1', lambda x:x.get('eventId'))

    def test_conflicting_binding_settings_rejected(self):
        self.events['conflict'] = {**self.events['binding'], 'eventId': 'different', 'effective': {**self.settings, 'model': 'other'}}
        with self.assertRaises(ValueError): self.run_report()

    def test_goal_turns_are_not_counted_as_multiple_executions(self):
        self.events['extra'] = {**self.events['binding'], 'eventId': 'extra', 'nativeTurnId': 'extra'}
        self.usage[('thread','extra')] = copy.deepcopy(self.usage[('thread','turn')])
        result = self.run_report()
        self.assertEqual(result['actualExecutions'], {'workhorse/high': 1})
        self.assertEqual(result['actualNativeTurns'], {'workhorse/high': 2})
        self.assertEqual(result['executions'][0]['observedAttributedCost'], '0.007305')

    def test_invalid_counts_and_token_subsets_rejected(self):
        for counts in [{'input': -1, 'cachedInput': 0, 'output': 1}, {'input': 1, 'cachedInput': 2, 'output': 1}, {'input': 1, 'cachedInput': 0, 'output': 1, 'reasoning': 2}, {'input': True, 'cachedInput': 0, 'output': 1}]:
            with self.assertRaises(ValueError): cost.tokens(counts)

    def test_unqualified_proposal_is_not_a_cost_opportunity(self):
        for status in ('denied', 'experimental', 'unknown'):
            self.models[0]['qualifications'][0]['status'] = status
            row = self.run_report()['executions'][0]
            self.assertIsNone(row['costScenario']); self.assertIn('qualification_not_established', row['gaps'])

    def test_process_completion_does_not_pass_quality_gate(self):
        self.execution['status'] = 'completed'
        self.assertEqual(self.run_report()['executions'][0]['qualityGate'], 'unreviewed')

    def test_retries_and_classifier_are_included_in_net_comparison(self):
        two = copy.deepcopy(self.execution); two['executionId'] = 'two'; two['decision'].pop('semantic')
        three = copy.deepcopy(two); three['executionId'] = 'three'
        for name in ('two', 'three'):
            self.events[name] = {**self.events['binding'], 'eventId': name, 'executionId': name, 'nativeTurnId': name}
            self.usage[('thread', name)] = copy.deepcopy(self.usage[('thread', 'turn')])
        self.events['decision-three'] = {'kind': 'decision', 'executionId': 'three', 'action': 'escalate', 'parentExecutionId': 'two'}
        comparison = {'comparisonId': 'fixture-comparison', 'baselineAttemptIds': ['one'], 'candidateAttemptIds': ['two', 'three'], 'comparable': True, 'allAttemptsAccounted': True, 'qualityGate': 'accepted_both', 'provenance': 'synthetic-review'}
        result = self.run_report(executions=[self.execution, two, three], outcomes=[comparison])
        self.assertEqual(result['comparisons'][0]['netAcceptedTaskDifference'], '-0.003495')
        self.assertEqual(result['recoveryChains'][1]['observedInitialPlusRecoveryCost'], '0.0072')
        comparison['candidateAttemptIds'] = ['three']
        self.assertIsNone(self.run_report(executions=[self.execution, two, three], outcomes=[comparison])['comparisons'][0]['netAcceptedTaskDifference'])

    def test_comparison_requires_review_comparability_and_complete_usage(self):
        self.assertIsNone(self.run_report(outcomes=[{'baselineAttemptIds': ['one'], 'candidateAttemptIds': ['missing'], 'comparable': True, 'allAttemptsAccounted': True, 'qualityGate': 'accepted_both', 'provenance': 'synthetic-review'}])['comparisons'][0]['netAcceptedTaskDifference'])

    def test_missing_parent_is_unknown_not_zero_recovery(self):
        self.events['decision'] = {'kind': 'decision', 'executionId': 'one', 'action': 'escalate', 'parentExecutionId': 'outside-window'}
        result = self.run_report()
        self.assertFalse(result['recoveryChains'][0]['attributionComplete'])
        self.assertIsNone(result['recoveryChains'][0]['observedInitialPlusRecoveryCost'])

    def test_conflicting_native_turn_ownership_rejected(self):
        self.events['second'] = {**self.events['binding'], 'eventId': 'second', 'executionId': 'different'}
        with self.assertRaises(ValueError): self.run_report()

    def test_double_counted_classifier_turn_rejected(self):
        self.execution['decision']['semantic']['native_thread_id'] = 'thread'
        self.execution['decision']['semantic']['native_turn_id'] = 'turn'
        with self.assertRaises(ValueError): self.run_report()

    def test_weight_evidence_version_scope_units_hash_and_expiry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = {'kind': 'verified_telemetry', 'source': 'synthetic://fixture-only', 'sourceVersion': 'fixture-v1', 'unit': 'fixture_units', 'accountScope': 'fixture-account', 'validFrom': '2026-10-01T00:00:00Z', 'validUntil': '2026-11-01T00:00:00Z', 'rates': [{'model': 'workhorse', 'reasoningEffort': 'high', 'serviceTier': 'standard', 'basis': 'per_million_tokens', 'uncachedInput': 4, 'cachedInput': 1, 'output': 8}]}
            proof = root/'proof.json'; proof.write_text(json.dumps(source))
            data = {'schema': 'vk.autoswitch.weights.v1', 'version': 'fixture-v1', 'provenance': {k:v for k,v in source.items() if k != 'rates'}, 'rates': source['rates']}
            data['provenance']['sourceSha256'] = cost.digest(proof.read_bytes())
            weights = root/'weights.json'; weights.write_text(json.dumps(data)); now = dt.datetime(2026, 10, 12, tzinfo=dt.timezone.utc)
            self.assertEqual(cost.load_weights(weights, proof, now)['provenance']['unit'], 'fixture_units')
            with self.assertRaises(ValueError): cost.load_weights(weights, None, now)
            with self.assertRaises(ValueError): cost.load_weights(weights, proof, dt.datetime(2027,1,1,tzinfo=dt.timezone.utc))
            data['rates'][0]['basis'] = 'preference_rank'; weights.write_text(json.dumps(data))
            with self.assertRaises(ValueError): cost.load_weights(weights, proof, now)


if __name__ == '__main__':
    unittest.main(verbosity=2)
