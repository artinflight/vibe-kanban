#!/usr/bin/env python3
"""Offline AutoSwitch accounting. Read-only inputs; never routes or runs inference."""
import argparse
import collections
import datetime as dt
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid


def digest(data):
    return hashlib.sha256(data).hexdigest()


def quantity(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError('Invalid token count')
    return value


def tokens(value):
    """Reasoning is a subset of output, cached input a subset of input."""
    if not isinstance(value, dict):
        return None
    if any(value.get(k) is None for k in ('input', 'cachedInput', 'output')):
        return None
    result = {k: quantity(value[k]) for k in ('input', 'cachedInput', 'output')}
    reasoning = value.get('reasoning')
    result['reasoning'] = None if reasoning is None else quantity(reasoning)
    if result['cachedInput'] > result['input'] or (
        reasoning is not None and reasoning > result['output']
    ):
        raise ValueError('Inconsistent token subsets')
    return result


def known_components(value):
    if not isinstance(value, dict):
        return {}
    known = {k:quantity(value[k]) for k in ('input', 'cachedInput', 'output', 'reasoning') if value.get(k) is not None}
    if ('input' in known and known.get('cachedInput', 0) > known['input']) or ('output' in known and known.get('reasoning', 0) > known['output']):
        raise ValueError('Inconsistent observed token subsets')
    return known


def identity(value):
    if not isinstance(value, dict):
        return None
    fields = tuple(value.get(k) for k in ('model', 'reasoningEffort', 'serviceTier'))
    return fields if all(isinstance(x, str) and x for x in fields) else None


def load_weights(path=None, proof=None):
    if path is None:
        return None
    if proof is None:
        raise ValueError('Weights require the exact reviewed source evidence file')
    raw = Path(path).read_bytes()
    data = json.loads(raw)
    provenance = data.get('provenance', {})
    if data.get('schema') != 'vk.autoswitch.weights.v1' or not data.get('version'):
        raise ValueError('Unsupported weight schema/version')
    if provenance.get('kind') not in ('verified_telemetry', 'versioned_authoritative'):
        raise ValueError('Preference ranks and unverified estimates are not cost weights')
    if not all(provenance.get(k) for k in ('source', 'sourceVersion', 'unit', 'accountScope', 'validFrom', 'validUntil')):
        raise ValueError('Incomplete weight provenance or scope')
    source = Path(proof).read_bytes()
    if digest(source) != provenance.get('sourceSha256'):
        raise ValueError('Weight source evidence hash mismatch')
    # The reviewed evidence must supply these exact rates/scope, not merely exist.
    evidence = json.loads(source)
    if any(evidence.get(k) != provenance.get(k) for k in ('kind', 'source', 'sourceVersion', 'unit', 'accountScope', 'validFrom', 'validUntil', 'regime')) or evidence.get('rates') != data.get('rates'):
        raise ValueError('Weight data does not match reviewed source evidence')
    begin = dt.datetime.fromisoformat(provenance['validFrom'].replace('Z', '+00:00'))
    end = dt.datetime.fromisoformat(provenance['validUntil'].replace('Z', '+00:00'))
    if not begin.tzinfo or not end.tzinfo or begin >= end:
        raise ValueError('Invalid weight applicability interval')
    rates = {}
    for row in data.get('rates', []):
        key = identity(row)
        if key is None or row.get('basis') != 'per_million_tokens':
            raise ValueError('Rates require unique exact model/effort/tier and compatible basis')
        amounts = tuple(Decimal(str(row[k])) for k in ('uncachedInput', 'cachedInput', 'output'))
        if any(not x.is_finite() or x < 0 for x in amounts):
            raise ValueError('Invalid cost rate')
        start = dt.datetime.fromisoformat(row.get('validFrom', provenance['validFrom']).replace('Z', '+00:00'))
        stop = dt.datetime.fromisoformat(row.get('validUntil', provenance['validUntil']).replace('Z', '+00:00'))
        if not start.tzinfo or not stop.tzinfo or not begin <= start < stop <= end:
            raise ValueError('Invalid rate applicability interval')
        regime = row.get('regime', provenance.get('regime'))
        version = row.get('weightVersion', evidence.get('weightVersion'))
        if not isinstance(regime, str) or not regime or not isinstance(version, str) or not version:
            raise ValueError('Rates require explicit regime and version')
        rates.setdefault(key, []).append({'amounts': amounts, 'from': start, 'until': stop, 'regime': regime, 'version': version})
    if not rates:
        raise ValueError('Empty rates')
    return {'rates': rates, 'provenance': provenance, 'sha256': digest(raw), 'version': data['version']}


def event_time(value):
    try:
        at = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        return at.astimezone(dt.timezone.utc) if at.tzinfo else None
    except (ValueError, TypeError, AttributeError):
        return None


def observations_agree(evidence):
    if any(evidence.get(field) for field in ('timestampConflict', 'regimeConflict', 'weightVersionConflict', 'accountConflict')):
        return False
    for source_field, field, normalize in (
        ('timestampSources', 'timestamp', event_time), ('regimeSources', 'regime', lambda x: x),
        ('weightVersionSources', 'weightVersion', lambda x: x), ('accountSources', 'accountScope', lambda x: x),
    ):
        sources = evidence.get(source_field, [])
        expected = normalize(evidence.get(field))
        if not isinstance(sources, list) or (sources and expected is None) or any(normalize(x) != expected for x in sources):
            return False
    return True


def price(settings, usage, weights, account, evidence=None):
    """Half-open per-event applicability; never use report/admission time."""
    if weights is None or usage is None or account != weights['provenance']['accountScope']:
        return None
    if not isinstance(evidence, dict) or evidence.get('accountScope') != account:
        return None
    at = event_time(evidence.get('timestamp'))
    regime = evidence.get('regime'); version = evidence.get('weightVersion')
    if at is None or not regime or not version or not observations_agree(evidence):
        return None
    matches = [r for r in weights['rates'].get(identity(settings), [])
               if r['regime'] == regime and r['version'] == version and r['from'] <= at < r['until']]
    if len(matches) != 1:
        return None
    rate = matches[0]['amounts']
    uncached = usage['input'] - usage['cachedInput']
    return (uncached * rate[0] + usage['cachedInput'] * rate[1] + usage['output'] * rate[2]) / Decimal(1000000)


def measurement_cost(settings, measurement, weights, account):
    if not isinstance(measurement, dict) or measurement.get('complete') is not True or not measurement.get('provenance'):
        return None
    if not observations_agree(measurement):
        return None
    count = tokens(measurement.get('tokens'))
    if count is None:
        return None
    events = measurement.get('events')
    if events is None:
        return price(settings, count, weights, account, measurement)
    if not isinstance(events, list) or not events:
        return None
    seen = {}; total = Decimal(0); summed = collections.Counter(); times = []
    for item in events:
        if not isinstance(item, dict):
            return None
        eid = item.get('eventId')
        if not eid or (eid in seen and seen[eid] != item):
            return None
        if eid in seen:
            continue
        seen[eid] = item
        if item.get('complete') is not True or not item.get('provenance'):
            return None
        if identity(item) != identity(settings):
            return None
        for field in ('regime', 'weightVersion', 'accountScope', 'nativeThreadId', 'nativeTurnId'):
            if measurement.get(field) is not None and measurement[field] != item.get(field):
                return None
        part = tokens(item.get('tokens'))
        value = price(settings, part, weights, account, item)
        if value is None:
            return None
        total += value; summed.update({k:part[k] for k in ('input', 'cachedInput', 'output')})
        times.append(event_time(item.get('timestamp')))
    if any(summed[k] != count[k] for k in ('input', 'cachedInput', 'output')):
        return None
    if measurement.get('timestamp') is not None and event_time(measurement['timestamp']) != max(times):
        return None
    return total


def verified_no_classifier(execution, proofs):
    """Absence of a trace is not proof; require a reviewed exact execution receipt."""
    d = execution['decision']; p = (proofs or {}).get(execution['executionId'])
    if not isinstance(p, dict) or p.get('verified') is not True or type(p.get('calls')) is not int or p['calls'] != 0:
        return False
    provenance = p.get('provenance')
    source_hash = provenance.get('sourceSha256') if isinstance(provenance, dict) else None
    if not isinstance(provenance, dict) or not provenance.get('reviewRef') or not isinstance(source_hash, str) or len(source_hash) != 64 or any(x not in '0123456789abcdef' for x in source_hash):
        return False
    if p.get('executionId') != execution['executionId'] or p.get('decisionId') != d.get('id') or not p.get('decisionId'):
        return False
    path = p.get('path'); module_hash = p.get('moduleManifestSha256')
    if path not in ('completed_context_reference_lookup', 'completed_context_bounded_record') or not isinstance(module_hash, str) or len(module_hash) != 64 or any(x not in '0123456789abcdef' for x in module_hash):
        return False
    evidence = (d.get('triage') or {}).get('evidence', [])
    return path in evidence and 'bounded_semantic_fallback' not in evidence and any(
        x.startswith('routing_module:') and x.endswith(':' + module_hash) for x in evidence)


class Records(dict):
    sha256 = None
    incomplete_tail = False


def immutable_records(path, schema, key):
    rows = Records()
    if path is None:
        return rows
    hasher = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while line := stream.readline(1048577):
            if len(line) > 1048576:
                raise ValueError('Oversized telemetry record')
            if not line.endswith(b'\n'):
                rows.incomplete_tail = True
                break
            hasher.update(line)
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get('schema') != schema:
                raise ValueError('Unexpected input schema')
            ident = key(item)
            if not ident or (ident in rows and rows[ident] != item):
                raise ValueError('Missing or conflicting immutable identity')
            rows[ident] = item
    rows.sha256 = hasher.hexdigest()
    return rows


def report(executions, events, usage, weights=None, outcomes=None, models=None, classifier_proofs=None):
    """Missing observations stay unknown; process completion is not review acceptance."""
    decisions = {}; bindings = {}; turn_owner = {}
    for event in events.values():
        eid = event['executionId']
        if event['kind'] == 'decision':
            if eid in decisions and decisions[eid] != event:
                raise ValueError('Conflicting execution decision')
            decisions[eid] = event
        if event['kind'] == 'turn_bound':
            turn = (event['nativeThreadId'], event['nativeTurnId'])
            if not all(isinstance(x, str) and x for x in turn):
                raise ValueError('Missing exact native turn identity')
            if turn in turn_owner and turn_owner[turn] != eid:
                raise ValueError('Native turn belongs to multiple executions')
            turn_owner[turn] = eid
            previous = bindings.setdefault(eid, {}).get(turn)
            if previous and any(previous.get(k) != event.get(k) for k in ('effective', 'settingsSource', 'routingId')):
                raise ValueError('Conflicting native binding settings')
            bindings[eid][turn] = event
    details = []; attributed = {}; classifier_seen = set()
    classifier_totals = collections.Counter(); classifier_unknown = 0
    for execution in executions:
        eid = execution['executionId']; d = execution['decision']; trace = d.get('semantic')
        requested = execution.get('requested', {})
        recommended = {'model': d.get('selected_model'), 'reasoningEffort': d.get('selected_effort'), 'serviceTier': d.get('service_tier')}
        gaps = []; execution_costs = []; actual = []; native_subtotal = collections.Counter()
        turns = bindings.get(eid, {})
        if not turns:
            gaps.append('native_binding_missing')
        for turn, binding in turns.items():
            effective = binding.get('effective', {}) if binding.get('settingsSource') == 'runtime_confirmed' else {}
            measured = usage.get(turn)
            # Native usage is authoritative; confirmed feed fields may fill only absent values.
            settings = {k: (measured.get(k) if measured else None) or effective.get(k) for k in ('model', 'reasoningEffort', 'serviceTier')}
            if measured and any(measured.get(k) and effective.get(k) and measured[k] != effective[k] for k in settings):
                raise ValueError('Native settings conflict')
            actual.append(settings)
            complete = measured and measured.get('complete') is True and measured.get('provenance')
            observed_count = known_components(measured.get('tokens')) if measured and measured.get('provenance') else {}
            native_subtotal.update(observed_count)
            count = tokens(measured.get('tokens')) if complete else None
            if count is None:
                gaps.append('execution_usage_missing_or_incomplete')
            value = measurement_cost(settings, measured, weights, d.get('account_fingerprint'))
            if value is None:
                gaps.append('baseline_weights_or_settings_unknown')
            execution_costs.append(value)
        baseline_cost = sum(execution_costs, Decimal(0)) if turns and all(v is not None for v in execution_costs) else None
        overhead = None; overhead_tokens = None; overhead_raw = {}
        if trace:
            tid = trace.get('id')
            if not tid or tid in classifier_seen:
                raise ValueError('Classifier identity reused or missing')
            classifier_seen.add(tid)
            if (trace.get('native_thread_id'), trace.get('native_turn_id')) in turn_owner:
                raise ValueError('Classifier usage already belongs to an execution')
            overhead_raw = {'input': trace.get('input_tokens'), 'cachedInput': trace.get('cached_input_tokens'), 'output': trace.get('output_tokens'), 'reasoning': trace.get('reasoning_tokens')}
            overhead_tokens = tokens(overhead_raw)
            classifier_totals.update(known_components(overhead_raw))
            if overhead_tokens is None:
                classifier_unknown += 1; gaps.append('classifier_usage_unknown')
            classifier_measurement = usage.get((trace.get('native_thread_id'), trace.get('native_turn_id')))
            classifier_settings = {'model': trace.get('model'), 'reasoningEffort': trace.get('effort'), 'serviceTier': trace.get('service_tier')}
            if classifier_measurement and identity(classifier_measurement) == identity(classifier_settings) and tokens(classifier_measurement.get('tokens')) == overhead_tokens and overhead_tokens is not None:
                overhead = measurement_cost(classifier_settings, classifier_measurement, weights, d.get('account_fingerprint'))
            if overhead is None:
                gaps.append('classifier_cost_unknown')
        elif verified_no_classifier(execution, classifier_proofs):
            overhead = Decimal(0)
        else:
            classifier_unknown += 1; gaps.append('classifier_absence_unverified')
        total = baseline_cost + overhead if baseline_cost is not None and overhead is not None else None
        attributed[eid] = total
        triage = d.get('triage') or {}
        confidence = triage.get('uncertainty') == 'low' and triage.get('ambiguity') == 'low' and not triage.get('needs_repo_inspection')
        qualification = next((q.get('status') for model in models or [] if model['id'] == recommended['model'] for q in model.get('qualifications', []) if q['effort'] == recommended['reasoningEffort'] and q['envelope'] == d.get('assessed_envelope')), 'unknown')
        candidate_safe = qualification in ('qualified', 'minimum_required')
        baseline = actual[0] if len(actual) == 1 else None
        # A same-token-demand scenario is reviewable, but NOT a cheaper-model outcome.
        scenario = None
        if baseline is not None and len(turns) == 1:
            record = usage.get(next(iter(turns)))
            count = tokens(record.get('tokens')) if record and record.get('complete') is True else None
            scenario_record = None
            if record:
                scenario_record = {**record, **recommended}
                if record.get('events') is not None:
                    scenario_record['events'] = [{**x, **recommended} for x in record['events']]
            proposed = measurement_cost(recommended, scenario_record, weights, d.get('account_fingerprint'))
            if baseline_cost is not None and proposed is not None and candidate_safe:
                scenario = {'kind': 'same_token_demand_only', 'baselineCost': str(baseline_cost), 'recommendedCost': str(proposed), 'candidateInitialCostWithObservedClassifierOverhead': str(proposed + overhead) if overhead is not None else None, 'grossDifference': str(baseline_cost - proposed), 'netSavings': None, 'limitations': ['gross_difference_excludes_overhead_and_rework', 'lower_model_token_demand_unknown', 'candidate_retry_rework_unknown', 'comparable_accepted_outcome_missing']}
        details.append({'executionId': eid, 'requested': requested, 'actualNative': actual, 'recommended': recommended, 'confidenceGate': confidence, 'qualificationGate': qualification, 'qualityGate': 'unreviewed', 'classification': d.get('assessed_envelope'), 'reason': d.get('reason'), 'classifierTokens': overhead_tokens, 'classifierKnownTokenSubtotal': known_components(overhead_raw) if trace else {}, 'nativeKnownTokenSubtotal': dict(native_subtotal), 'baselineExecutionCost': None if baseline_cost is None else str(baseline_cost), 'observedClassifierCost': None if overhead is None else str(overhead), 'observedAttributedCost': None if total is None else str(total), 'costScenario': scenario, 'netSavings': None, 'gaps': sorted(set(gaps + ['comparable_accepted_outcome_missing'] + ([] if candidate_safe else ['qualification_not_established'])))})
    # Explicit escalation links only. A timestamp, same session or ordinary follow-up is not rework.
    roots = {}; chains = {}
    for eid in attributed:
        seen = set(); current = eid
        while decisions.get(current, {}).get('action') == 'escalate':
            if current in seen:
                raise ValueError('Escalation cycle')
            seen.add(current); parent = decisions[current].get('parentExecutionId')
            if not parent:
                raise ValueError('Escalation lacks parent identity')
            current = parent
        roots[eid] = current; chains.setdefault(current, []).append(eid)
    chain_rows = []
    for root, members in chains.items():
        missing_parent = root not in attributed
        values = [attributed[x] for x in members]
        chain_rows.append({'rootExecutionId': root, 'attemptExecutionIds': members, 'observedInitialPlusRecoveryCost': str(sum(values, Decimal(0))) if not missing_parent and all(v is not None for v in values) else None, 'attributionComplete': not missing_parent, 'untrackedReviewCorrectionsOrRework': 'unknown', 'qualityGate': 'unreviewed'})
    comparisons = []
    for item in outcomes or []:
        baseline = item.get('baselineAttemptIds', []); candidate = item.get('candidateAttemptIds', [])
        eligible = (item.get('comparable') is True and item.get('allAttemptsAccounted') is True and item.get('qualityGate') == 'accepted_both' and bool(item.get('provenance')) and baseline and candidate and not set(baseline) & set(candidate) and len(set(baseline)) == len(baseline) and len(set(candidate)) == len(candidate))
        ids = baseline + candidate
        eligible = eligible and all(x in attributed and attributed[x] is not None for x in ids)
        # Require every attributable attempt, not just the final successful attempt.
        eligible = eligible and all(set(chains[roots[x]]) <= set(group) and roots[x] in attributed for group in (baseline, candidate) for x in group)
        accounts = {x['decision'].get('account_fingerprint') for x in executions if x['executionId'] in ids}
        eligible = eligible and weights is not None and accounts == {weights['provenance']['accountScope']}
        delta = sum((attributed[x] for x in baseline), Decimal(0)) - sum((attributed[x] for x in candidate), Decimal(0)) if eligible else None
        comparisons.append({'comparisonId': item.get('comparisonId'), 'netAcceptedTaskDifference': None if delta is None else str(delta), 'unit': weights['provenance']['unit'] if eligible else None, 'status': 'measured_usage_weighted_comparison' if eligible else 'unknown', 'gaps': [] if eligible else ['incomplete_attribution_or_quality_or_comparability_or_weights']})
    distribution = lambda settings: dict(collections.Counter('/'.join(str(x.get(k)) for k in ('model', 'reasoningEffort')) for x in settings))
    executed = collections.Counter()
    for item in details:
        settings = {tuple(x.get(k) for k in ('model', 'reasoningEffort')) for x in item['actualNative']}
        if settings:
            executed['/'.join(str(k) for k in next(iter(settings))) if len(settings) == 1 else 'mixed_native_settings'] += 1
    return {'schema': 'vk.autoswitch.cost-report.v1', 'basis': 'actual_native_execution_not_all_astra', 'weights': None if weights is None else {'version': weights['version'], 'sha256': weights['sha256'], 'provenance': weights['provenance']}, 'executionCount': len(details), 'recommendations': distribution(x['recommended'] for x in details), 'actualExecutions': dict(executed), 'actualNativeTurns': distribution(y for x in details for y in x['actualNative']), 'missingNativeBindings': sum(not x['actualNative'] for x in details), 'classifierKnownTokenSubtotal': dict(classifier_totals), 'classifierUnknownUsageCount': classifier_unknown, 'executions': details, 'recoveryChains': chain_rows, 'comparisons': comparisons, 'netObservedSavings': None, 'limitations': ['recommendation_is_not_execution', 'no_all_astra_counterfactual', 'weights_are_provenanced_estimates_not_observed_billing', 'process_exit_is_not_quality_acceptance']}


def read_executions(db, start, end):
    start = start.replace('Z', '+00:00'); end = end.replace('Z', '+00:00')
    for value in (start, end):
        if dt.datetime.fromisoformat(value).utcoffset() != dt.timedelta(0):
            raise ValueError('Report window requires UTC timestamps')
    if dt.datetime.fromisoformat(start) >= dt.datetime.fromisoformat(end):
        raise ValueError('Report window must have increasing bounds')
    connection = sqlite3.connect(Path(db).resolve().as_uri() + '?mode=ro', uri=True)
    connection.execute('PRAGMA query_only=ON')
    rows = connection.execute("SELECT id, created_at, executor_action FROM execution_processes WHERE run_reason='codingagent' AND dropped=0 AND created_at>=? AND created_at<? ORDER BY created_at", (start, end))
    result = []
    for eid, timestamp, raw in rows:
        action = json.loads(raw); decision = action.get('routing_decision')
        if decision is None:
            continue
        config = action.get('typ', {}).get('executor_config', {})
        result.append({'executionId': str(uuid.UUID(bytes=eid)), 'timestamp': timestamp, 'decision': decision, 'requested': {'model': config.get('model_id'), 'reasoningEffort': config.get('reasoning_id')}})
    connection.close()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True); parser.add_argument('--routing-feed', required=True)
    parser.add_argument('--start', required=True); parser.add_argument('--end', required=True)
    parser.add_argument('--usage'); parser.add_argument('--weights'); parser.add_argument('--weight-evidence'); parser.add_argument('--outcomes'); parser.add_argument('--classifier-proof')
    parser.add_argument('--models', type=Path, default=Path(__file__).resolve().parents[1] / 'crates/executors/src/routing_models.json')
    args = parser.parse_args()
    events = immutable_records(args.routing_feed, 'vk.routing.v1', lambda x: x.get('eventId'))
    usage = immutable_records(args.usage, 'vk.autoswitch.usage.v1', lambda x: (x.get('nativeThreadId'), x.get('nativeTurnId')) if x.get('nativeThreadId') and x.get('nativeTurnId') else None)
    outcomes = immutable_records(args.outcomes, 'vk.autoswitch.comparison.v1', lambda x: x.get('comparisonId'))
    proofs = immutable_records(args.classifier_proof, 'vk.autoswitch.classifier-path.v1', lambda x:x.get('executionId'))
    weights = load_weights(args.weights, args.weight_evidence)
    output = report(read_executions(args.db, args.start, args.end), events, usage, weights, outcomes.values(), json.loads(args.models.read_text()), proofs)
    output['observationWindow'] = {'startInclusive': args.start, 'endExclusive': args.end, 'basis': 'execution_admission', 'nativeBindings': 'all_exact_attributed_turns_available_at_report_time', 'reportUtc': dt.datetime.now(dt.timezone.utc).isoformat()}
    output['inputProvenance'] = {'routingCompletePrefixSha256': events.sha256, 'routingIncompleteTail': events.incomplete_tail, 'usageCompletePrefixSha256': usage.sha256, 'usageIncompleteTail': usage.incomplete_tail, 'qualificationSha256': digest(args.models.read_bytes()), 'classifierProofCompletePrefixSha256': proofs.sha256, 'query': 'read-only VK execution decisions joined by exact native turn IDs'}
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
