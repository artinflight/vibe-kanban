#!/usr/bin/env python3
"""Synthetic accounting fixtures only: fixture units are not billing weights."""
import copy
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
        self.execution = {'executionId': 'one', 'requested': {'model': 'frontier'}, 'decision': {'account_fingerprint': 'fixture-account', 'selected_model': 'routine', 'selected_effort': 'low', 'service_tier': 'standard', 'assessed_envelope': 'bounded', 'triage': {'uncertainty': 'low', 'ambiguity': 'low', 'needs_repo_inspection': False}, 'id': 'decision-one', 'semantic': {'native_thread_id': 'classifier-thread', 'native_turn_id': 'classifier-turn', 'id': 'classifier-one', 'model': 'classifier', 'effort': 'low', 'service_tier': 'standard', 'input_tokens': 100, 'cached_input_tokens': 20, 'output_tokens': 10, 'reasoning_tokens': 5}}}
        self.events = {'binding': {'eventId': 'binding', 'kind': 'turn_bound', 'executionId': 'one', 'nativeThreadId': 'thread', 'nativeTurnId': 'turn', 'settingsSource': 'runtime_confirmed', 'effective': self.settings}}
        self.usage = {('thread', 'turn'): {**self.settings, 'complete': True, 'provenance': 'synthetic-native-export', 'tokens': {'input': 1000, 'cachedInput': 400, 'output': 100, 'reasoning': 50}}}
        self.metadata = {'timestamp': '2026-10-12T12:00:00Z', 'regime': 'fixture-regime', 'weightVersion': 'test-only', 'accountScope': 'fixture-account'}
        self.usage[('thread', 'turn')].update(self.metadata)
        self.usage[('classifier-thread', 'classifier-turn')] = {**self.metadata, 'model': 'classifier', 'reasoningEffort': 'low', 'serviceTier': 'standard', 'complete': True, 'provenance': 'synthetic-native-export', 'tokens': {'input': 100, 'cachedInput': 20, 'output': 10, 'reasoning': 5}}
        self.proofs = {}
        self.weights = {'provenance': {'unit': 'fixture_units', 'accountScope': 'fixture-account'}, 'version': 'test-only', 'sha256': 'fixture', 'rates': {('workhorse', 'high', 'standard'): (Decimal(4), Decimal(1), Decimal(8)), ('routine', 'low', 'standard'): (Decimal(1), Decimal('.25'), Decimal(2)), ('classifier', 'low', 'standard'): (Decimal(1), Decimal('.25'), Decimal(2))}}
        self.weights['rates'] = {key: [{'amounts': amounts, 'from': cost.event_time('2026-10-12T00:00:00Z'), 'until': cost.event_time('2026-10-13T00:00:00Z'), 'regime': 'fixture-regime', 'version': 'test-only'}] for key, amounts in self.weights['rates'].items()}
        self.models = [{'id': 'routine', 'qualifications': [{'effort': 'low', 'envelope': 'bounded', 'status': 'qualified'}]}]

    def run_report(self, **kw):
        return cost.report(kw.get('executions', [self.execution]), kw.get('events', self.events), kw.get('usage', self.usage), kw.get('weights', self.weights), kw.get('outcomes'), kw.get('models', self.models), kw.get('classifier_proofs', self.proofs))

    def prove_no_classifier(self, execution):
        d = execution['decision']
        d.pop('semantic', None)
        d['id'] = 'decision-' + execution['executionId']
        path = 'completed_context_bounded_record'; module = 'a' * 64
        d['triage']['evidence'] = [path, 'routing_module:fixture:' + module]
        self.proofs[execution['executionId']] = {'executionId': execution['executionId'], 'decisionId': d['id'], 'verified': True, 'calls': 0, 'path': path, 'moduleManifestSha256': module, 'provenance': {'reviewRef': 'synthetic-reviewed-receipt', 'sourceSha256': 'b' * 64}}

    def test_actual_baseline_wins_over_requested_frontier(self):
        row = self.run_report()['executions'][0]
        self.assertEqual(row['actualNative'][0]['model'], 'workhorse')
        self.assertEqual(row['costScenario']['baselineCost'], '0.0036')
        self.assertEqual(row['costScenario']['recommendedCost'], '0.0009')
        self.assertIsNone(row['netSavings'])

    def test_cache_discount_and_reasoning_not_double_counted(self):
        self.assertEqual(cost.price(self.settings, cost.tokens(self.usage[('thread', 'turn')]['tokens']), self.weights, 'fixture-account', self.metadata), Decimal('.0036'))

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
            self.assertIsNone(cost.price(self.settings, counts, self.weights, 'fixture-account', {**self.metadata, 'timestamp': at}))
        self.assertEqual(cost.price(self.settings, counts, self.weights, 'fixture-account', self.metadata), Decimal('.0036'))

    def test_missing_or_partial_native_usage_remains_unknown(self):
        for usage in ({}, {('thread', 'turn'): {**self.usage[('thread', 'turn')], 'complete': False}}):
            self.assertIsNone(self.run_report(usage=usage)['executions'][0]['observedAttributedCost'])

    def test_absent_classifier_is_unknown_without_verified_zero_inference(self):
        self.execution['decision'].pop('semantic')
        row = self.run_report()['executions'][0]
        self.assertIsNone(row['observedAttributedCost'])
        self.assertIn('classifier_absence_unverified', row['gaps'])
        self.prove_no_classifier(self.execution)
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
        self.prove_no_classifier(two); self.prove_no_classifier(three)
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
            source = {'kind': 'verified_telemetry', 'source': 'synthetic://fixture-only', 'sourceVersion': 'fixture-v1', 'unit': 'fixture_units', 'accountScope': 'fixture-account', 'validFrom': '2020-01-01T00:00:00Z', 'validUntil': '2020-02-01T00:00:00Z', 'regime': 'fixture-regime', 'rates': [{'model': 'workhorse', 'reasoningEffort': 'high', 'serviceTier': 'standard', 'weightVersion': 'fixture-v1', 'basis': 'per_million_tokens', 'uncachedInput': 4, 'cachedInput': 1, 'output': 8}]}
            proof = root/'proof.json'; proof.write_text(json.dumps(source))
            data = {'schema': 'vk.autoswitch.weights.v1', 'version': 'fixture-v1', 'provenance': {k:v for k,v in source.items() if k != 'rates'}, 'rates': source['rates']}
            data['provenance']['sourceSha256'] = cost.digest(proof.read_bytes())
            weights = root/'weights.json'; weights.write_text(json.dumps(data))
            self.assertEqual(cost.load_weights(weights, proof)['provenance']['unit'], 'fixture_units')
            with self.assertRaises(ValueError): cost.load_weights(weights, None)
            # Expiration at report time does not invalidate historical in-window observations.
            loaded = cost.load_weights(weights, proof)
            self.assertIsNotNone(cost.price(self.settings, cost.tokens(self.usage[('thread', 'turn')]['tokens']), loaded, 'fixture-account', {**self.metadata, 'timestamp': '2020-01-12T12:00:00Z', 'weightVersion': 'fixture-v1'}))
            self.assertIsNone(cost.price(self.settings, cost.tokens(self.usage[('thread', 'turn')]['tokens']), loaded, 'fixture-account', {**self.metadata, 'timestamp': '2027-01-01T00:00:00Z', 'weightVersion': 'fixture-v1'}))
            data['rates'][0]['basis'] = 'preference_rank'; weights.write_text(json.dumps(data))
            with self.assertRaises(ValueError): cost.load_weights(weights, proof)

    def test_weight_windows_are_half_open_and_historical_not_report_time(self):
        counts = cost.tokens(self.usage[('thread', 'turn')]['tokens'])
        for at, expected in [('2026-10-11T23:59:59.999999Z', None), ('2026-10-12T00:00:00Z', Decimal('.0036')), ('2026-10-12T23:59:59.999999Z', Decimal('.0036')), ('2026-10-13T00:00:00Z', None), ('2027-01-01T00:00:00Z', None)]:
            with self.subTest(at=at):
                self.assertEqual(cost.price(self.settings, counts, self.weights, 'fixture-account', {**self.metadata, 'timestamp': at}), expected)

    def changed_regime(self):
        key = cost.identity(self.settings)
        first = self.weights['rates'][key][0]
        first['until'] = cost.event_time('2026-10-12T12:00:00Z')
        self.weights['rates'][key].append({**first, 'from': first['until'], 'until': cost.event_time('2026-10-13T00:00:00Z'), 'regime': 'changed', 'version': 'v2', 'amounts': (Decimal(8), Decimal(2), Decimal(16))})

    def test_changed_regime_boundary_and_version_match_exact_event(self):
        self.changed_regime(); counts = cost.tokens(self.usage[('thread', 'turn')]['tokens'])
        for metadata, expected in [({**self.metadata, 'timestamp': '2026-10-12T11:59:59Z'}, Decimal('.0036')), (self.metadata, None), ({**self.metadata, 'regime': 'changed', 'weightVersion': 'v2'}, Decimal('.0072')), ({**self.metadata, 'regime': 'changed'}, None)]:
            self.assertEqual(cost.price(self.settings, counts, self.weights, 'fixture-account', metadata), expected)

    def test_missing_conflicting_time_regime_version_account_are_unknown(self):
        count = cost.tokens(self.usage[('thread', 'turn')]['tokens'])
        for field in ('timestamp', 'regime', 'weightVersion', 'accountScope'):
            missing = dict(self.metadata); missing.pop(field)
            self.assertIsNone(cost.price(self.settings, count, self.weights, 'fixture-account', missing))
        for extra in ({'timestamp': '2026-10-12T12:00:00'}, {'timestampConflict': True}, {'regimeConflict': True}, {'weightVersionConflict': True}, {'accountConflict': True}, {'timestampSources': ['2026-10-12T11:00:00Z']}, {'regimeSources': ['other']}, {'weightVersionSources': ['other']}, {'accountSources': ['other']}, {'timestampSources': None}):
            self.assertIsNone(cost.price(self.settings, count, self.weights, 'fixture-account', {**self.metadata, **extra}))
        self.assertEqual(cost.price(self.settings, count, self.weights, 'fixture-account', {**self.metadata, 'timestampSources': ['2026-10-12T14:00:00+02:00']}), Decimal('.0036'))

    def test_overlapping_rates_are_unknown(self):
        key = cost.identity(self.settings)
        self.weights['rates'][key].append(copy.deepcopy(self.weights['rates'][key][0]))
        self.assertIsNone(self.run_report()['executions'][0]['baselineExecutionCost'])

    def test_effort_model_and_tier_are_exact_not_family_fallback(self):
        for field in ('model', 'reasoningEffort', 'serviceTier'):
            self.assertIsNone(cost.price({**self.settings, field: 'other'}, cost.tokens(self.usage[('thread', 'turn')]['tokens']), self.weights, 'fixture-account', self.metadata))

    def split_measurement(self):
        self.changed_regime()
        measurement = copy.deepcopy(self.usage[('thread', 'turn')])
        for field in ('regime', 'weightVersion'):
            measurement.pop(field)
        measurement['events'] = []
        for eid, at, regime, version in [('before', '2026-10-12T11:59:59Z', 'fixture-regime', 'test-only'), ('after', '2026-10-12T12:00:00Z', 'changed', 'v2')]:
            measurement['events'].append({**self.settings, **self.metadata, 'eventId': eid, 'timestamp': at, 'regime': regime, 'weightVersion': version, 'complete': True, 'provenance': 'synthetic-native-event', 'tokens': {'input': 500, 'cachedInput': 200, 'output': 50, 'reasoning': 25}})
        return measurement

    def test_one_native_turn_spanning_regimes_prices_each_usage_event(self):
        measurement = self.split_measurement()
        self.assertEqual(cost.measurement_cost(self.settings, measurement, self.weights, 'fixture-account'), Decimal('.0054'))
        measurement['events'].append(copy.deepcopy(measurement['events'][0]))
        self.assertEqual(cost.measurement_cost(self.settings, measurement, self.weights, 'fixture-account'), Decimal('.0054'))

    def test_changed_regime_missing_event_conflicting_totals_or_metadata_unknown(self):
        measurement = self.split_measurement()
        for change in ('missing-time', 'missing-version', 'sum', 'aggregate-regime', 'aggregate-time', 'conflicting-duplicate', 'malformed'):
            row = copy.deepcopy(measurement)
            if change == 'missing-time': row['events'][0].pop('timestamp')
            if change == 'missing-version': row['events'][1].pop('weightVersion')
            if change == 'sum': row['events'][1]['tokens']['output'] = 51
            if change == 'aggregate-regime': row['regime'] = 'changed'
            if change == 'aggregate-time': row['timestamp'] = '2026-10-12T11:59:59Z'
            if change == 'conflicting-duplicate': row['events'].append({**row['events'][0], 'timestamp': '2026-10-12T11:59:58Z'})
            if change == 'malformed': row['events'][0] = None
            with self.subTest(change=change):
                self.assertIsNone(cost.measurement_cost(self.settings, row, self.weights, 'fixture-account'))

    def test_aggregate_event_evidence_conflicts_and_cross_turn_deltas_unknown(self):
        measurement = self.split_measurement()
        for update in ({'timestampSources': ['2026-10-12T11:59:59Z']}, {'regimeSources': ['changed']}, {'weightVersionConflict': True}, {'accountSources': ['other']}, {'nativeThreadId': 'other-thread'}, {'nativeTurnId': 'other-turn'}):
            with self.subTest(update=update):
                self.assertIsNone(cost.measurement_cost(self.settings, {**measurement, **update}, self.weights, 'fixture-account'))

    def test_correct_aggregate_metadata_cannot_substitute_for_missing_event_dates(self):
        measurement = self.split_measurement()
        measurement['events'][0].pop('timestamp')
        self.assertIsNone(cost.measurement_cost(self.settings, measurement, self.weights, 'fixture-account'))

    def test_classifier_has_own_timestamp_and_regime_not_parent_admission(self):
        classifier = self.usage[('classifier-thread', 'classifier-turn')]
        self.execution['timestamp'] = '2020-01-01T00:00:00Z'
        self.assertEqual(self.run_report()['executions'][0]['observedClassifierCost'], '0.000105')
        for update in ({'timestamp': '2026-10-11T23:59:59Z'}, {'regime': 'other'}, {'weightVersion': 'other'}, {'timestampConflict': True}):
            original = copy.deepcopy(classifier); classifier.update(update)
            self.assertIsNone(self.run_report()['executions'][0]['observedClassifierCost'])
            classifier.clear(); classifier.update(original)

    def test_classifier_native_evidence_missing_or_conflicting_never_zero(self):
        for usage in ({('thread', 'turn'): self.usage[('thread', 'turn')]}, {**self.usage, ('classifier-thread', 'classifier-turn'): {**self.usage[('classifier-thread', 'classifier-turn')], 'tokens': {'input': 101, 'cachedInput': 20, 'output': 10}}}):
            self.assertIsNone(self.run_report(usage=usage)['executions'][0]['observedClassifierCost'])

    def test_reviewed_zero_inference_requires_matching_path_decision_and_module(self):
        self.prove_no_classifier(self.execution)
        self.assertEqual(self.run_report()['executions'][0]['observedClassifierCost'], '0')
        proof = self.proofs['one']
        for update in ({'verified': False}, {'calls': True}, {'calls': 1}, {'decisionId': 'stale'}, {'executionId': 'stale'}, {'moduleManifestSha256': 'c' * 64}, {'path': 'unreviewed'}, {'provenance': {}}):
            with self.subTest(update=update):
                changed = {**proof, **update}
                self.assertIsNone(self.run_report(classifier_proofs={'one': changed})['executions'][0]['observedClassifierCost'])
        self.execution['decision']['triage']['evidence'].append('bounded_semantic_fallback')
        self.assertIsNone(self.run_report()['executions'][0]['observedClassifierCost'])

    def test_rework_cost_uses_recovery_timestamp_and_regime(self):
        self.changed_regime()
        self.usage[('thread', 'turn')]['timestamp'] = '2026-10-12T11:59:59Z'
        two = copy.deepcopy(self.execution); two['executionId'] = 'two'; self.prove_no_classifier(two)
        recovery = {**copy.deepcopy(self.usage[('thread', 'turn')]), 'timestamp': '2026-10-12T12:00:00Z', 'regime': 'changed', 'weightVersion': 'v2'}
        self.usage[('thread', 'two')] = recovery
        self.events['two'] = {**self.events['binding'], 'eventId': 'two', 'executionId': 'two', 'nativeTurnId': 'two'}
        self.events['decision-two'] = {'kind': 'decision', 'executionId': 'two', 'action': 'escalate', 'parentExecutionId': 'one'}
        result = self.run_report(executions=[self.execution, two])
        self.assertEqual(result['recoveryChains'][0]['observedInitialPlusRecoveryCost'], '0.010905')
        recovery.pop('regime')
        self.assertIsNone(self.run_report(executions=[self.execution, two])['recoveryChains'][0]['observedInitialPlusRecoveryCost'])

    def test_acceptance_workflow_cannot_weaken_namespace_security(self):
        root = Path(__file__).resolve().parents[2]
        for name in ('autoswitch-module-acceptance.yml', 'test.yml'):
            workflow = (root / '.github/workflows' / name).read_text()
            for forbidden in ('sysctl', 'apparmor_parser', 'aa-disable', 'aa-complain', 'setcap', 'apparmor-profiles'):
                self.assertNotIn(forbidden, workflow)
            self.assertIn('command -v bwrap', workflow)
        workflow = (root / '.github/workflows/autoswitch-module-acceptance.yml').read_text()
        for name in ('autoswitch-module-acceptance.yml', 'test.yml'):
            workflow = (root / '.github/workflows' / name).read_text()
            self.assertIn("if: runner.environment == 'github-hosted' && runner.os == 'Linux'", workflow)
            self.assertIn('sudo apt-get install --no-install-recommends -y bubblewrap', workflow)
            self.assertIn('diff -u "$audit/before.sha256" "$audit/after.sha256"', workflow)
            allowed = ('sudo apt-get update', 'sudo apt-get install --no-install-recommends -y bubblewrap', 'sudo cat /sys/kernel/security/apparmor/profiles')
            # Restrict privilege in the AutoSwitch acceptance workflow. Other
            # normal PR jobs retain unrelated existing build dependencies.
            if name == 'autoswitch-module-acceptance.yml':
                for line in workflow.splitlines():
                    if 'sudo' in line:
                        self.assertTrue(any(line.strip().startswith(command) for command in allowed), line)
            self.assertIn('test ! -u /usr/bin/bwrap', workflow)
            self.assertIn('test -z "$(getcap /usr/bin/bwrap)"', workflow)


if __name__ == '__main__':
    unittest.main(verbosity=2)
