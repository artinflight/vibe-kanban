#!/usr/bin/env python3
"""One-shot CU OBSERVATION reader. No provider/credential calls or launch authority.
The backend embeds this file; tests execute this exact implementation.
"""
import datetime as dt
import json
import math
import re
import sys
import time
import urllib.error
import urllib.request

ORIGIN = 'http://127.0.0.1:4177'
SCHEMA = 'cu.provider-telemetry.v1'
MAX_BODY = 2 * 1024 * 1024
MAX_REQUEST = 16 * 1024
MAX_EVENTS = 20000
MAX_AGE_MS = 60000
PRODUCTS = {'codex': ('openai', 'codex'), 'claude': ('anthropic', 'claude-code')}


class ObservationError(Exception):
    pass


def require(value, code):
    if not value:
        raise ObservationError(code)


def utc_ms(value):
    require(isinstance(value, str) and re.fullmatch(r'\d{4}-\d\d-\d\dT[^\s]+(?:Z|\+00:00)', value), 'cu_timestamp_invalid')
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        require(parsed.utcoffset() == dt.timedelta(0), 'cu_timestamp_invalid')
        return int(parsed.timestamp() * 1000)
    except (ValueError, OverflowError):
        raise ObservationError('cu_timestamp_invalid') from None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ObservationError('cu_redirect_refused')


def fetch(endpoint, open_request=None):
    require(endpoint in ('/api/providers', '/api/credits/budget'), 'cu_endpoint_refused')
    request = urllib.request.Request(ORIGIN + endpoint, headers={'Accept': 'application/json'}, method='GET')
    opener = open_request or urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect()).open
    try:
        with opener(request, timeout=3) as response:
            require(response.status == 200, 'cu_http_unavailable')
            content_type = response.headers.get('Content-Type', '').split(';')[0].strip()
            require(content_type == 'application/json', 'cu_content_type_invalid')
            body = response.read(MAX_BODY + 1)
        require(len(body) <= MAX_BODY, 'cu_response_oversized')
        return json.loads(body)
    except ObservationError:
        raise
    except (OSError, ValueError, urllib.error.URLError):
        raise ObservationError('cu_transport_or_json_unavailable') from None


def credit_observation(report, now_ms=None):
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
    require(isinstance(report, dict) and report.get('contractVersion') == 'account-credit-budget-v1'
            and report.get('scope') == 'all-account-use' and report.get('unit') == 'credit', 'cu_credit_schema_unsupported')
    admission = report.get('admission')
    require(isinstance(admission, dict), 'cu_credit_schema_unsupported')
    stop = admission.get('stopLaunchingMoreTurns')
    require(stop is None or type(stop) is bool, 'cu_credit_schema_unsupported')
    # permissionGranted is explicitly reporting-only in pinned credit-api.js.
    # It is NOT a policy setting that universally excludes Claude or other pools.
    # No wallet values, reason prose, account identifiers or grant are exported.
    try:
        observed, expires = utc_ms(report.get('observedAt')), utc_ms(report.get('expiresAt'))
        fresh = report.get('fresh') is True and observed <= now_ms < min(expires, observed + MAX_AGE_MS)
    except ObservationError:
        fresh = False
    return {'contract': 'account-credit-budget-v1', 'readOnly': True,
            'permissionAuthority': False, 'accountBinding': 'not-exposed-by-this-contract',
            'stopLaunchingMoreTurns': stop,
            'historicalHoldObserved': stop is True,
            'observationFresh': fresh,
            'observedAt': report.get('observedAt'),
            'independentAdmissionStillRequired': True}


def inspect_report(report, request, now_ms):
    require(isinstance(request, dict) and request.get('provider') in PRODUCTS, 'cu_provider_unsupported')
    provider, product = PRODUCTS[request['provider']]
    require(isinstance(report, dict) and report.get('schemaVersion') == SCHEMA
            and report.get('normalizationVersion') == 1 and report.get('advisoryOnly') is True,
            'cu_provider_schema_unsupported')
    events = report.get('events')
    require(isinstance(events, list) and len(events) <= MAX_EVENTS, 'cu_event_bound_invalid')
    require(isinstance(report.get('pools'), list) and len(report['pools']) <= 32, 'cu_pool_bound_invalid')
    require(isinstance(report.get('products'), list) and len(report['products']) <= 8, 'cu_product_bound_invalid')
    require(all(isinstance(e, dict) for e in events), 'cu_event_schema_invalid')
    selected = [e for e in events if e.get('provider') == provider and e.get('product') == product]
    expected = request.get('poolId')
    model = request.get('model')
    require(model is None or isinstance(model, str) and 0 < len(model) <= 128, 'cu_model_scope_invalid')
    if expected is not None:
        require(isinstance(expected, str) and re.fullmatch(r'pool-[a-f0-9]{24}', expected), 'cu_expected_pool_invalid')
    result = {'contractVersion': 'vk.cu-observation.v1', 'sourceContract': SCHEMA,
              'provider': request['provider'], 'product': product, 'status': 'observed',
              'dispatchAuthority': False, 'providerStarted': False, 'blockers': [],
              'usageObservations': sum(e.get('kind') == 'usage' for e in selected),
              'quotaState': 'unknown', 'windows': [], 'windowInventory': 'not-declared-by-source',
              'generation': None, 'bindingMatched': False,
              'capacityMeasurement': None, 'availabilityObservations': [], 'modelScope': model, 'quotaObservedAtMs': None, 'quotaExpiresAtMs': None}
    def block(code, action):
        if code not in [b['code'] for b in result['blockers']]:
            result['blockers'].append({'code': code, 'action': action})
    if not selected:
        block('cu_provider_observations_unavailable', 'await_bound_provider_metadata')
    if expected is None or not isinstance(request.get('bindingReceipt'), str) or not request['bindingReceipt']:
        block('cu_account_pool_binding_unknown', 'verify_native_account_pool_binding')
    elif not any(e.get('poolId') == expected for e in selected):
        block('cu_account_pool_mismatch', 'reconcile_exact_account_pool_binding')
    else:
        result['bindingMatched'] = True
    quotas = [e for e in selected if e.get('kind') == 'quota' and (expected is None or e.get('poolId') == expected)
              and (model is None or e.get('quota', {}).get('model') in (None, model))]
    if not quotas:
        block('cu_quota_observations_unavailable', 'await_fresh_provider_quota_evidence')
    windows = {}
    # Newest evidence first: superseded old windows cannot poison a fresh latest observation.
    for event in sorted(quotas, key=lambda e: utc_ms(e.get('observedAt')), reverse=True):
        q = event.get('quota')
        if event.get('billingSource') != 'subscription':
            block('cu_subscription_route_unproven', 'verify_native_subscription_binding_without_api_fallback')
            continue
        require(event.get('schemaVersion') == SCHEMA and event.get('normalizationVersion') == 1
                and isinstance(q, dict), 'cu_quota_schema_invalid')
        if event.get('sourceKind') not in ('local-session', 'cli-export') or event.get('evidence') != 'observed':
            block('cu_quota_source_not_native_verified', 'retain_manual_or_fixture_as_observation_only')
            continue
        if not all(isinstance(event.get(k), str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:@+-]{0,127}', event[k]) for k in ('sourceVersion', 'eventId', 'evidenceRef')):
            block('cu_quota_provenance_incomplete', 'retain_exact_versioned_source_receipt')
            continue
        observed = utc_ms(event.get('observedAt'))
        reset = utc_ms(q.get('resetsAt')) if q.get('resetsAt') is not None else None
        duration, percent, signal = q.get('windowMinutes'), q.get('usedPercent'), q.get('signal')
        require(type(duration) is int and duration > 0, 'cu_window_invalid')
        require(percent is None or type(percent) in (int, float) and math.isfinite(percent) and 0 <= percent <= 100, 'cu_window_invalid')
        require(signal in ('available', 'work-exhausted', 'usage-endpoint-throttled', 'unknown'), 'cu_signal_unsupported')
        model = q.get('model')
        require(model is None or isinstance(model, str), 'cu_window_invalid')
        # Report generatedAt, pool.windows.fresh and report freshness NEVER redate
        # underlying observations. Every window retains its event/reset timestamps.
        key = (duration, model)
        window = {'windowMinutes': duration, 'usedPercent': percent, 'model': model,
                  'signal': signal, 'observedAtMs': observed, 'resetAtMs': reset,
                  'sourceVersion': event['sourceVersion'], 'evidenceRef': event['evidenceRef'],
                  'status': 'unknown'}
        prior = windows.get(key)
        if prior and prior['observedAtMs'] > observed:
            continue
        if prior and prior['observedAtMs'] == observed:
            if {k:v for k,v in prior.items() if k != 'status'} != {k:v for k,v in window.items() if k != 'status'}:
                block('cu_quota_conflicting', 'reconcile_conflicting_window_observations')
            continue
        require(len(windows) < 64 or key in windows, 'cu_window_bound_invalid')
        if observed > now_ms or now_ms - observed >= MAX_AGE_MS:
            window['status'] = 'stale'
            block('cu_quota_stale', 'await_fresh_provider_quota_evidence')
        elif signal == 'usage-endpoint-throttled':
            window['status'] = 'measurement-throttled'
            block('cu_usage_fetch_throttled', 'bounded_metadata_backoff_not_provider_failover')
        elif reset is None or reset <= now_ms:
            block('cu_reset_recovery_unverified', 'observe_actual_reset_recovery')
        elif signal == 'work-exhausted' or percent == 100:
            window['status'] = 'exhausted'
            block('cu_provider_quota_exhausted', 'await_verified_provider_reset')
        elif signal == 'available' and percent is not None:
            window['status'] = 'available'
        else:
            block('cu_quota_unknown', 'await_explicit_quota_availability')
        windows[key] = window
    result['windows'] = sorted(windows.values(), key=lambda w: (w['windowMinutes'], w['model'] or ''))
    if result['windows']:
        result['quotaObservedAtMs'] = min(w['observedAtMs'] for w in result['windows'])
        result['quotaExpiresAtMs'] = min(min(w['observedAtMs'] + MAX_AGE_MS, w['resetAtMs'] or w['observedAtMs']) for w in result['windows'])
        if not result['blockers'] and all(w['status'] == 'available' for w in result['windows']):
            result['quotaState'] = 'observed-available'
        elif any(w['status'] == 'exhausted' for w in result['windows']):
            result['quotaState'] = 'exhausted'
    # Native availability has NO identified window or verified recovery field in
    # this pinned contract. Retain exhaustion after the reported clock/reset;
    # neither a freshly generated report nor an unrelated fresh quota can prove
    # recovery of that unidentified window. Do not transfer it to another pool.
    for event in selected:
        if event.get('kind') != 'availability' or event.get('poolId') not in (None, expected):
            continue
        a = event.get('availability')
        require(event.get('schemaVersion') == SCHEMA and event.get('normalizationVersion') == 1
                and isinstance(a, dict), 'cu_availability_schema_invalid')
        observed = utc_ms(event.get('observedAt'))
        signal = a.get('signal')
        require(signal in ('work-exhausted', 'usage-endpoint-throttled', 'unknown'), 'cu_signal_unsupported')
        require(len(result['availabilityObservations']) < 64, 'cu_availability_bound_invalid')
        native = (event.get('sourceKind') in ('local-session', 'cli-export')
                  and event.get('evidence') == 'observed'
                  and a.get('basis') == 'native-terminal'
                  and event.get('billingSource') == 'subscription')
        bound = expected is not None and event.get('poolId') == expected
        result['availabilityObservations'].append({'signal': signal, 'observedAtMs': observed,
            'reportedResetAtMs': utc_ms(a['reportedResetAt']) if a.get('reportedResetAt') else None,
            'native': native, 'accountBound': bound, 'recovery': 'unverified'})
        if observed > now_ms:
            block('cu_availability_time_invalid', 'reconcile_exact_observation_timestamp')
        elif signal == 'work-exhausted':
            block('cu_reset_scope_unverified' if bound and native else 'cu_availability_binding_unverified',
                  'observe_native_bound_window_and_recovery' if bound and native else 'reconcile_exact_native_availability_binding')
            # This is historical negative evidence, not a new authoritative quota
            # event. Existing Controller-native quota signals remain separate.
            result['quotaState'] = 'recovery-unverified'
        elif signal == 'usage-endpoint-throttled' and 0 <= now_ms - observed < MAX_AGE_MS:
            block('cu_usage_fetch_throttled', 'bounded_metadata_backoff_not_provider_failover')
    if result['blockers'] and result['quotaState'] == 'observed-available':
        result['quotaState'] = 'unknown'
    # This source does not expose generation/complete applicable-window inventory,
    # calibrated accepted-task capacity or a work-scoped admission/lease permit.
    # Do not forge any of those fields or build a runnable Pool from token totals.
    return result


def read_observations(request, open_request=None, now_ms=None):
    result = inspect_report(fetch('/api/providers', open_request), request,
                            int(time.time() * 1000) if now_ms is None else now_ms)
    try:
        result['creditObservation'] = credit_observation(fetch('/api/credits/budget', open_request), now_ms)
    except ObservationError as error:
        result['creditObservation'] = {'status': 'unavailable', 'code': str(error), 'permissionAuthority': False}
    return result


def main():
    try:
        raw = sys.stdin.buffer.read(MAX_REQUEST + 1)
        require(len(raw) <= MAX_REQUEST, 'cu_request_oversized')
        request = json.loads(raw)
        require(isinstance(request, dict) and set(request) <= {'provider', 'poolId', 'bindingReceipt', 'model'}, 'cu_request_schema_invalid')
        result = read_observations(request)
    except (ObservationError, ValueError, OSError) as error:
        code = str(error) if isinstance(error, ObservationError) else 'cu_request_or_transport_unavailable'
        result = {'contractVersion': 'vk.cu-observation.v1', 'status': 'unavailable',
                  'dispatchAuthority': False, 'providerStarted': False,
                  'blockers': [{'code': code, 'action': 'inspect_existing_cu_observation_service'}]}
    sys.stdout.write(json.dumps(result, separators=(',', ':')) + '\n')


if __name__ == '__main__':
    main()
