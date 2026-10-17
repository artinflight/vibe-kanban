"""Bounded read-only facade for the CU owner's fixed local report helper.

CU owns aggregation, coverage, reset boundaries and accounting. No token-to-credit
conversion or control, provider refresh, caller URL/path, or subprocess is added.
"""
import datetime as dt
import json
import re
import uuid

WINDOWS = ('since_reset', 'day', 'week', 'custom')
GROUPS = ('workspace', 'project', 'session', 'execution', 'model')
MAX_BYTES = 262144
CONTRACT = 'cu.dot-report.v1'
PROPERTIES = {
    'window': {'type': 'string', 'enum': list(WINDOWS), 'default': 'since_reset'},
    'from_time': {'type': 'string', 'format': 'date-time'},
    'to_time': {'type': 'string', 'format': 'date-time'},
    'group_by': {'type': 'string', 'enum': list(GROUPS), 'default': 'workspace'},
    **{key: {'type': 'string', 'format': 'uuid'} for key in
       ('project_id', 'workspace_id', 'session_id', 'execution_id')},
    'model': {'type': 'string', 'minLength': 1, 'maxLength': 128,
              'pattern': '^[A-Za-z0-9._:/-]+$'},
    'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100, 'default': 50},
    'offset': {'type': 'integer', 'minimum': 0, 'maximum': 100000, 'default': 0},
}
ANNOTATIONS = {'readOnlyHint': True, 'destructiveHint': False,
               'idempotentHint': True, 'openWorldHint': False}
TOOLS = [{
    'name': 'get_usage_report',
    'description': 'Read CU account totals and paginated project/workspace/session/execution/model '
        'breakdowns with input, cached, output tokens and available sourced cost/credit metrics. '
        'Default is since the account reset. Custom RFC3339 intervals are half-open [from,to), '
        'at most 31 days. Coverage, freshness, null attribution and estimates remain explicit; '
        'account totals differ from filtered rows. No prompts/logs, provider refresh, agent turn, '
        'budget permission or control. Credits are never inferred from tokens.',
    'inputSchema': {'type': 'object', 'properties': PROPERTIES,
                    'additionalProperties': False},
    'annotations': ANNOTATIONS,
}, {
    'name': 'get_usage_summary',
    'description': 'Read a bounded CU account/reset-window usage summary, with coverage and '
        'freshness. No arguments, provider refresh or execution control. Use get_usage_report '
        'for selectable windows and paginated breakdowns. Unknown cost/credits stay unknown.',
    'inputSchema': {'type': 'object', 'properties': {}, 'additionalProperties': False},
    'annotations': ANNOTATIONS,
}]


def _timestamp(value):
    if not isinstance(value, str) or not re.fullmatch(
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})', value):
        raise ValueError('Explicit RFC3339 timestamp required')
    return dt.datetime.fromisoformat(value.replace('Z', '+00:00'))


def arguments(args):
    if not isinstance(args, dict) or set(args) - set(PROPERTIES):
        raise ValueError('Unknown reporting argument')
    result = dict(args)
    window = result.setdefault('window', 'since_reset')
    group = result.setdefault('group_by', 'workspace')
    if window not in WINDOWS or group not in GROUPS:
        raise ValueError('Invalid reporting window or grouping')
    if window == 'custom':
        start, end = (_timestamp(result.get(key)) for key in ('from_time', 'to_time'))
        if not dt.timedelta(0) < end - start <= dt.timedelta(days=31):
            raise ValueError('Custom interval must be positive and at most 31 days')
    elif 'from_time' in result:
        raise ValueError('Explicit from_time requires window=custom')
    if 'to_time' in result:
        _timestamp(result['to_time'])  # Pin any window to its returned pagination cutoff.
    for key in ('project_id', 'workspace_id', 'session_id', 'execution_id'):
        if key in result:
            if not isinstance(result[key], str):
                raise ValueError('UUID string required')
            result[key] = str(uuid.UUID(result[key]))
            if uuid.UUID(result[key]).int == 0:
                raise ValueError('Non-nil scope required')
    if 'model' in result and (not isinstance(result['model'], str)
            or not re.fullmatch(r'[A-Za-z0-9._:/-]{1,128}', result['model'])):
        raise ValueError('Invalid model filter')
    for key, default, low, high in [('limit', 50, 1, 100), ('offset', 0, 0, 100000)]:
        value = result.setdefault(key, default)
        if type(value) is not int or not low <= value <= high:
            raise ValueError('Invalid reporting pagination')
    return result


def _bounded(value, maximum=MAX_BYTES):
    if not isinstance(value, dict) or value.get('contractVersion') != CONTRACT:
        raise ValueError('Invalid CU reporting response')
    if len(json.dumps(value, allow_nan=False).encode()) > maximum:
        raise ValueError('CU reporting response exceeds connector bound')
    return value


def read_summary():
    try:
        import dot_usage_report
        return _bounded(dot_usage_report.read_usage_summary(), 16384)
    except (ImportError, OSError, ValueError, TypeError, KeyError, RecursionError):
        return {'contractVersion': CONTRACT, 'status': 'unavailable', 'fresh': False, 'readback': None,
                'reason': 'CU summary unavailable; no zero usage, complete coverage or allowance inferred.'}


def call(api, name, args):
    if name == 'get_usage_summary':
        if not isinstance(args, dict) or args:
            raise ValueError('get_usage_summary accepts no arguments')
        return api.result(read_summary())
    if name != 'get_usage_report':
        raise ValueError('Unknown reporting tool')
    selected = arguments(args)  # Reject before loading/reading any local store.
    try:
        import dot_usage_report
        value = _bounded(dot_usage_report.read_usage_report(**selected))
    except (ImportError, OSError, ValueError, TypeError, KeyError, RecursionError):
        value = {'contractVersion': CONTRACT, 'status': 'unavailable', 'fresh': False, 'readback': None,
                 'reason': 'CU report unavailable; narrow the query or inspect CU coverage. No usage or cost inferred.'}
    return api.result(value)
