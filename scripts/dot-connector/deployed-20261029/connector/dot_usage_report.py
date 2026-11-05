"""Read existing CU reporting ledgers only; never scan, call a model or grant work.

The connector exposes read_usage_report with typed, bounded selectors. Files are
fixed by this installation, never supplied by a tool caller. No prompts, tool
logs, credentials, raw source paths or account identity are returned.
"""
import collections
from contextlib import closing
import datetime as dt
import json
import importlib.util
import pathlib
import re
import sqlite3
import uuid

TELEMETRY_DB = pathlib.Path('/mnt/vk-storage/codexusage-android/monitor/routing-usage.sqlite')
VIBE_DB = pathlib.Path('/home/mcp/.local/share/vibe-kanban-green-xdg/vibe-kanban/db.v2.sqlite')
CACHE_DIR = pathlib.Path('/home/mcp/code/codexusage/.cache/usage')
FIELDS = ('totalTokens', 'inputTokens', 'cachedInputTokens', 'uncachedInputTokens',
          'outputTokens', 'reasoningOutputTokens', 'unclassifiedTokens', 'unknownCacheInputTokens')
GROUPS = ('project', 'workspace', 'session', 'execution', 'model')
WINDOWS = ('since_reset', 'day', 'week', 'custom')
UTC = dt.timezone.utc
MAX_WINDOW = dt.timedelta(days=31)


def _time(value):
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError('Use an explicit RFC3339 timestamp with timezone')
    result = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timestamp timezone is required')
    return result.astimezone(UTC)


def _iso(value):
    return value.astimezone(UTC).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def _ro(file):
    # mode=ro includes committed WAL contents; immutable=1 would hide live WAL.
    db = sqlite3.connect(file.resolve().as_uri() + '?mode=ro', uri=True, timeout=2)
    db.execute('PRAGMA query_only=ON')
    db.execute('BEGIN')
    return db


def _rows(db, table, start=None, end=None):
    assert table in ('observations', 'routes', 'allowance', 'scans', 'import_issues')
    sql = 'SELECT body FROM ' + table
    args = ()
    if start is not None:
        sql += ' WHERE timestamp>=? AND timestamp<?'
        args = (_iso(start), _iso(end))
    return [json.loads(r[0]) for r in db.execute(sql + ' ORDER BY timestamp', args)]


def _sum(rows, empty_known=False):
    result = {'observations': len(rows), 'known': {}, 'missing': {}}
    for field in FIELDS:
        numbers = [r.get(field) for r in rows]
        valid = [n for n in numbers if type(n) is int and n >= 0]
        result['known'][field] = sum(valid)
        result['missing'][field] = len(numbers) - len(valid)
        result[field] = sum(valid) if len(valid) == len(rows) and (rows or empty_known) else None
    return result


def _uid(value):
    if value is None:
        return None
    return str(uuid.UUID(bytes=value)) if isinstance(value, bytes) else str(uuid.UUID(value))


def _metadata(db):
    workspaces, native = {}, collections.defaultdict(set)
    for wid, name, sid, thread, branch in db.execute('''SELECT w.id,w.name,s.id,t.agent_session_id,w.branch
        FROM workspaces w JOIN sessions s ON s.workspace_id=w.id
        LEFT JOIN execution_processes e ON e.session_id=s.id
        LEFT JOIN coding_agent_turns t ON t.execution_process_id=e.id'''):
        wid, sid = _uid(wid), _uid(sid)
        workspaces.setdefault(wid, {'id': wid, 'name': name or wid, 'projects': [], 'branch': branch})
        if thread:
            native[thread].add((wid, sid))
    # A Vibe project UUID is never a repository UUID. Prefer explicit issue
    # membership, then a unique actual project_repos association as fallback.
    for wid, pid, name in db.execute("""SELECT w.id,p.id,p.name FROM workspaces w
        JOIN tasks t ON t.id=w.task_id JOIN projects p ON p.id=t.project_id"""):
        item = workspaces.get(_uid(wid))
        if item:
            item['projects'] = [{'id': _uid(pid), 'name': name}]
    fallback = collections.defaultdict(dict)
    for wid, pid, name in db.execute("""SELECT DISTINCT wr.workspace_id,p.id,p.name
        FROM workspace_repos wr JOIN project_repos pr ON pr.repo_id=wr.repo_id
        JOIN projects p ON p.id=pr.project_id"""):
        fallback[_uid(wid)][_uid(pid)] = name
    for wid, candidates in fallback.items():
        item = workspaces.get(wid)
        if item and not item['projects'] and len(candidates) == 1:
            pid, name = next(iter(candidates.items()))
            item['projects'] = [{'id': pid, 'name': name}]
    return workspaces, native


def _bindings(routes, issues):
    poisoned = {r.get('eventId') for r in issues if r.get('eventId')}
    decisions, bindings = collections.defaultdict(list), collections.defaultdict(list)
    for row in routes:
        if row.get('eventId') in poisoned:
            continue
        if row.get('kind') == 'decision':
            decisions[row['executionId']].append(row)
        elif row.get('kind') == 'turn_bound':
            bindings[(row['nativeThreadId'], row['nativeTurnId'])].append(row)
    return decisions, bindings


def _attribute(source, workspaces, native, decisions, bindings):
    r = {k: source.get(k) for k in FIELDS}
    r.update(timestamp=source['timestamp'], nativeThreadId=source.get('nativeThreadId'),
             nativeTurnId=source.get('nativeTurnId'), model=source.get('model'),
             workspaceId=None, sessionId=None, executionId=None, projectId=None,
             attribution='native_only')
    matches = bindings.get((r['nativeThreadId'], r['nativeTurnId']), [])
    candidates = []
    for b in matches:
        ds = decisions.get(b['executionId'], [])
        if (len(ds) == 1 and b['routingId'] == ds[0]['routingId']
                and ds[0]['timestamp'] <= b['timestamp'] <= r['timestamp']):
            candidates.append(ds[0])
    identities = {(d['executionId'], d.get('workspaceId'), d.get('sessionId')) for d in candidates}
    # A conflicting binding must not acquire even a fallback execution identity.
    if len(identities) == 1 and len({(b['executionId'], b['routingId']) for b in matches}) == 1:
        ex, wid, sid = next(iter(identities))
        r.update(executionId=ex, workspaceId=wid, sessionId=sid, attribution='exact_thread_turn')
    elif matches:
        r['attribution'] = 'unresolved_or_conflicting_binding'
    elif len(native.get(r['nativeThreadId'], set())) == 1:
        wid, sid = next(iter(native[r['nativeThreadId']]))
        r.update(workspaceId=wid, sessionId=sid, attribution='native_thread_session')
    if not r['workspaceId']:
        parts = pathlib.Path(source.get('workspace') or '').parts
        contexts = [w['id'] for w in workspaces.values()
                    if re.fullmatch(r'[a-f0-9]{4,8}-.+', (w.get('branch') or '').split('/')[-1])
                    and (w['branch'].split('/')[-1] in parts)]
        if len(contexts) == 1:
            r['workspaceId'] = contexts[0]
            if r['attribution'] == 'native_only':
                r['attribution'] = 'native_worktree_context'
    w = workspaces.get(r['workspaceId'])
    if w:
        projects = w['projects']
        if len(projects) == 1:
            r['projectId'] = projects[0]['id']
    return r


def _reset(allowances):
    rows = [r for r in allowances if r.get('poolId') == 'codex' and r.get('weekly')]
    if not rows:
        return None, None
    current = rows[-1]
    weekly = current['weekly']
    end = _time(weekly['resetsAt'])
    minutes = weekly.get('windowMinutes')
    if type(minutes) not in (int, float) or minutes <= 0:
        return current, None
    start = end - dt.timedelta(minutes=minutes)
    # Corroborate a provider-derived start with a real change, not reset-time jitter.
    before = after = None
    for a, b in zip(rows, rows[1:]):
        if (a.get('accountKey') == b.get('accountKey') == current.get('accountKey')
                and a['weekly'].get('usedPercent', -1) > b['weekly'].get('usedPercent', 101)
                and _time(a['timestamp']) <= start <= _time(b['timestamp'])
                and abs((_time(b['weekly']['resetsAt']) - end).total_seconds()) <= 10):
            before, after = a['timestamp'], b['timestamp']
    return current, {'startsAt': _iso(start), 'resetsAt': _iso(end),
        'basis': 'provider_deadline_minus_reported_window',
        'corroboratedByObservedChange': before is not None,
        'changeBracket': {'after': before, 'by': after} if before else None,
        'cause': 'not_attributed_by_reporting'}


def _cached_costs(start, end):
    # Existing report cache only: no Costs API request and no new credentials.
    try:
        files = sorted(CACHE_DIR.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:4]
        best = None
        for file in files:
            if file.stat().st_size > 4 * 1024 * 1024:
                continue
            raw = json.loads(file.read_text())
            data = raw.get('data', {})
            cost = data.get('openAiCosts', {})
            if cost.get('readable') is not True:
                continue
            days = [r for r in cost.get('days', []) if
                    _time(r['startTimeIso']) < end and _time(r['endTimeIso']) > start]
            record = {'source': 'saved OpenAI Organization Costs API report',
                      'reportedAt': data.get('generatedAt'), 'savedAt': _iso(dt.datetime.fromtimestamp(raw['cachedAtMs']/1000, UTC)), 'currency': 'USD',
                      'scope': 'organization API billing; independent of Codex subscription and paid Codex credits',
                      'attributableToSelectedEntity': False, 'exactRequestedWindowCostUsd': None,
                      'buckets': [{k: r.get(k) for k in ('startTimeIso','endTimeIso','totalCostUsd','currency')} for r in days]}
            record['status'] = 'buckets_available' if days else 'no_overlapping_buckets'
            if best is None or len(record['buckets']) > len(best['buckets']):
                best = record
        if best:
            return best
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return {'status': 'unavailable', 'exactRequestedWindowCostUsd': None, 'buckets': [],
            'attributableToSelectedEntity': False}


def _report(telemetry, metadata, *, now, window='since_reset', from_time=None, to_time=None,
            group_by='workspace', project_id=None, workspace_id=None, session_id=None,
            execution_id=None, model=None, limit=50, offset=0):
    if window not in WINDOWS or group_by not in GROUPS:
        raise ValueError('Unknown window or grouping')
    if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or not 0 <= offset <= 100000:
        raise ValueError('Use limit 1..100 and nonnegative offset <=100000')
    selectors = {k: _uid(v) for k, v in [('projectId', project_id), ('workspaceId', workspace_id),
                 ('sessionId', session_id), ('executionId', execution_id)] if v is not None}
    if model is not None:
        if not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9._:/-]{1,128}', model):
            raise ValueError('Invalid model selector')
        selectors['model'] = model
    scans = _rows(telemetry, 'scans')
    latest_scan = max(scans, key=lambda s: s.get('to', ''), default=None)
    latest = telemetry.execute('SELECT body FROM allowance ORDER BY timestamp DESC LIMIT 1').fetchone()
    latest = json.loads(latest[0]) if latest else None
    current, reset = _reset([latest] if latest else [])
    if reset:
        boundary = _time(reset['startsAt'])
        bracket_rows = _rows(telemetry, 'allowance', boundary-dt.timedelta(minutes=2), boundary+dt.timedelta(minutes=2))
        _, corroboration = _reset(bracket_rows + [current])
        if corroboration:
            reset = corroboration
    observed_to = _time(latest_scan['to']) if latest_scan else None
    end = _time(to_time) if to_time is not None else min(now, observed_to or now)
    if window == 'custom':
        start = _time(from_time)
    elif from_time is not None:
        raise ValueError('from_time requires window=custom')
    elif window == 'since_reset':
        if not reset:
            return {'schema': 'cu.dot-report.v1', 'contractVersion': 'cu.dot-report.v1', 'status': 'unavailable', 'reason': 'Provider reset basis not available',
                    'accountTotals': None, 'selectedTotals': None, 'rows': []}
        start = _time(reset['startsAt'])
    elif window == 'day':
        start = end.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        start = end.replace(hour=0, minute=0, second=0, microsecond=0) - dt.timedelta(days=end.weekday())
    if window == 'since_reset' and start >= end and to_time is None:
        return {'schema': 'cu.dot-report.v1', 'contractVersion': 'cu.dot-report.v1', 'status': 'awaiting_scan',
                'window': {'selector': window, 'from': _iso(start), 'to': _iso(end)},
                'accountTotals': None, 'selectedTotals': None, 'rows': [],
                'freshness': {'fresh': False, 'requestedWindowCovered': False},
                'reason': 'Allowance reset observed; existing token scan has not reached the new period yet'}
    if not start < end <= now or end - start > MAX_WINDOW:
        raise ValueError('Use a past ordered interval of at most 31 days')
    covering = [s for s in scans if _time(s['from']) <= start and _time(s['to']) >= end
                and s.get('sources') and all(not r.get('unreadable') for r in s['sources'])]
    # Routes are retained independently of the selected observation window.
    decisions, bindings = _bindings(_rows(telemetry, 'routes'), _rows(telemetry, 'import_issues'))
    workspaces, native = _metadata(metadata)
    rows = [_attribute(r, workspaces, native, decisions, bindings)
            for r in _rows(telemetry, 'observations', start, end)]
    selected = [r for r in rows if all((r.get(k) == v or (k == 'sessionId' and r.get('nativeThreadId') == v)) for k, v in selectors.items())]
    projects = {p['id']: p['name'] for w in workspaces.values() for p in w['projects']}
    grouped = collections.defaultdict(list)
    for r in selected:
        key = r.get(group_by + 'Id') if group_by != 'model' else r['model']
        if group_by == 'session' and not key:
            key = 'native:' + (r['nativeThreadId'] or 'unknown')
        grouped[key or 'unknown'].append(r)
    output = []
    for key, records in grouped.items():
        label = (workspaces.get(key, {}).get('name') if group_by == 'workspace' else
                 projects.get(key) if group_by == 'project' else None) or key
        output.append({'id': key, 'name': label, **_sum(records),
                       'models': sorted({r['model'] or 'unknown' for r in records}),
                       'nativeThreadIds': sorted({r['nativeThreadId'] for r in records if r['nativeThreadId']})[:20],
                       'nativeThreadCount': len({r['nativeThreadId'] for r in records if r['nativeThreadId']}),
                       'workspaceIds': sorted({r['workspaceId'] for r in records if r['workspaceId']})[:20],
                       'workspaceCount': len({r['workspaceId'] for r in records if r['workspaceId']}),
                       'sessionIds': sorted({r['sessionId'] for r in records if r['sessionId']})[:20],
                       'sessionCount': len({r['sessionId'] for r in records if r['sessionId']}),
                       'relatedIdentityListsLimit': 20,
                       'firstObservedAt': records[0]['timestamp'], 'lastObservedAt': records[-1]['timestamp'],
                       'accountTokenSharePercent': 100 * sum(r.get('totalTokens') or 0 for r in records) / sum(r.get('totalTokens') or 0 for r in rows) if rows and sum(r.get('totalTokens') or 0 for r in rows) > 0 and all(r.get('totalTokens') is not None for r in rows) else None})
    output.sort(key=lambda r: (-r['known']['totalTokens'], r['id']))
    age = max(0, (now - observed_to).total_seconds()) if observed_to else None
    return {'schema': 'cu.dot-report.v1', 'contractVersion': 'cu.dot-report.v1', 'status': 'recorded' if covering else 'partial',
        'generatedAt': _iso(now), 'window': {'selector': window, 'from': _iso(start), 'to': _iso(end), 'interval': '[from,to)', 'timezone': 'UTC'},
        'freshness': {'observedThrough': _iso(observed_to) if observed_to else None,
                      'ageSeconds': age, 'maxAgeSeconds': 300, 'fresh': age is not None and 0 <= (now-observed_to).total_seconds() <= 300,
                      'requestedWindowCovered': bool(covering)},
        'accountScope': 'all locally recorded Codex sources; provider account completeness is not guaranteed',
        'accountIdentityBound': False,
        'accountTotals': _sum(rows, bool(covering)), 'selectedTotals': _sum(selected, bool(covering)),
        'selectors': selectors, 'groupBy': group_by, 'rows': output[offset:offset+limit],
        'pagination': {'offset': offset, 'limit': limit, 'totalRows': len(output),
                       'nextOffset': offset+limit if offset+limit < len(output) else None,
                       'pinToTime': _iso(end)},
        'normalAllowance': {'observedAt': current['timestamp'] if current else None,
                            'weekly': {k: current['weekly'].get(k) for k in ('usedPercent','resetsAt','windowMinutes')} if current else None, 'resetWindow': reset,
                            'fresh': bool(current and 0 <= (now-_time(current['timestamp'])).total_seconds() <= 60),
                            'providerReportingLagMs': None,
                            'attribution': 'whole account; rounded provider percent, not token-to-credit conversion'},
        'attribution': {'exactExecution': _sum([r for r in rows if r['executionId']], bool(covering)),
                        'unattributedExecution': _sum([r for r in rows if not r['executionId']], bool(covering)),
                        'worktreeContextObservations': sum(r['attribution']=='native_worktree_context' for r in rows),
                        'conflictingOrUnresolvedObservations': sum(r['attribution']=='unresolved_or_conflicting_binding' for r in rows)},
        'coverage': {'coveringScans': len(covering), 'oldestObservation': telemetry.execute('SELECT min(timestamp) FROM observations').fetchone()[0],
                     'accountingMethods': 'Existing scanner-normalized, deduplicated token observations; last_token_usage or explicit cumulative differences. No cumulative session totals added.',
                     'providerBillingComplete': False},
        'costs': {'codexBilledUsd': None, 'codexBilledCredits': None, 'apiTokenEstimateUsd': None,
                  'organizationApi': _cached_costs(start, end)},
        'limitations': ['Cached input is a subset of input; reasoning is a subset of output. Never add either twice.',
                       'Each dimension is a different grouping of the same observations, not additive usage. Related-ID lists show at most 20 with full counts; group rows are fully paginated.',
                       'Unknown components remain null with partial known subtotals; no observations without covering scans is not zero.',
                       'Execution attribution requires exact native thread+turn binding. Native session mappings and unique worktree context only locate sessions/workspaces; context-only rows have no session/execution identity.',
                       'Reset-window start is provider deadline minus duration, with an observed-change bracket when retained. Reset cause is not inferred.',
                       'Historical token reports do not rewrite the independent credit ledger. Wallet decreases are not billed spend.',
                       'No launch permission or stop enforcement is granted. Reads do not trigger scans/provider refresh or coding turns.']}


def _read_tokens(window='since_reset', from_time=None, to_time=None, group_by='workspace',
                      project_id=None, workspace_id=None, session_id=None, execution_id=None,
                      model=None, limit=50, offset=0):
    """Bounded recorded-usage report; credit snapshot and costs keep their own scope."""
    try:
        with closing(_ro(TELEMETRY_DB)) as telemetry, closing(_ro(VIBE_DB)) as metadata:
            result = _report(telemetry, metadata, now=dt.datetime.now(UTC), window=window,
                from_time=from_time, to_time=to_time, group_by=group_by, project_id=project_id,
                workspace_id=workspace_id, session_id=session_id, execution_id=execution_id,
                model=model, limit=limit, offset=offset)
        return result
    except (sqlite3.Error, OSError, json.JSONDecodeError):
        return {'schema': 'cu.dot-report.v1', 'contractVersion': 'cu.dot-report.v1', 'status': 'unavailable',
                'reason': 'Existing reporting data unavailable; no zero usage or allowance inferred',
                'accountTotals': None, 'selectedTotals': None, 'rows': []}



def read_usage_report(window='since_reset', from_time=None, to_time=None, group_by='workspace',
                      project_id=None, workspace_id=None, session_id=None, execution_id=None,
                      model=None, limit=50, offset=0):
    report = _read_tokens(window, from_time, to_time, group_by, project_id, workspace_id,
                          session_id, execution_id, model, limit, offset)
    report['credits'] = _credit_snapshot()
    return report


def _credit_snapshot():
    try:
        spec = importlib.util.spec_from_file_location('cu_reporting_credit_reader', pathlib.Path(__file__).with_name('dot_credit_budget.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.read_credit_budget()
    except (OSError, ImportError, AttributeError):
        return {'status': 'unavailable', 'fresh': False, 'readback': None,
                'reason': 'Existing independent credit snapshot unavailable'}


def read_usage_summary():
    """Small default projection for the existing T24 status tool; no schema change."""
    report = _read_tokens(limit=5)
    keys = ('contractVersion', 'status', 'generatedAt', 'window', 'freshness', 'accountScope',
            'accountTotals', 'selectedTotals', 'groupBy', 'pagination', 'normalAllowance', 'coverage')
    summary = {key: report.get(key) for key in keys}
    summary['rows'] = [{key: row.get(key) for key in ('id','name','inputTokens','cachedInputTokens',
                       'outputTokens','totalTokens','accountTokenSharePercent')} for row in report.get('rows', [])]
    summary['costs'] = {'codexBilledUsd': None, 'codexBilledCredits': None,
                        'exactWindowOrganizationApiUsd': None,
                        'scope': 'Independent organization billing buckets are available in the full report'}
    summary['limitations'] = ['Cached input is included in input; output includes reasoning.',
                             'Local recorded tokens are not exact subscription or credit billing.',
                             'Use the full report for all groups, filters, cost buckets and unattributed usage.']
    return summary
