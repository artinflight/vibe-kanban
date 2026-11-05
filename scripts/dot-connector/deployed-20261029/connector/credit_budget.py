"""Fixed, observational CU readback; no provider refresh or execution control.

Adapted from the CU owner's reviewed read_credit_budget() contract. Account
values remain strings/null; this connector neither calculates nor reserves funds.
"""
import datetime as dt
from decimal import Decimal, InvalidOperation
import json
import urllib.error
import urllib.request

URL = 'http://127.0.0.1:4177/api/credits/budget'
MAX_BYTES = 65536
TIMEOUT_SECONDS = 5
TOOLS = [{
    'name': 'get_credit_budget',
    'description': 'Read current CU account-wide credit/budget observations without an agent turn or provider refresh. '
        'No arguments. Exact decimal strings/null and freshness are preserved. Unknown bank, settlement, '
        'historical holds and external reservation enforcement remain unknown. The overnight checkpoint '
        'is not extra funding; never reissue a reserved advance. Wallet/headroom or a false stop flag '
        'grants no launch permission. Does not stop agents, reserve credits or enforce a budget.',
    'inputSchema': {'type': 'object', 'properties': {}, 'required': [], 'additionalProperties': False},
    'annotations': {'readOnlyHint': True, 'destructiveHint': False,
                    'idempotentHint': True, 'openWorldHint': False},
}]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _decimals(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(item, (dict, list)) and (key.endswith('Credits') or key.endswith('CreditsPerHour')):
                if item is not None and (not isinstance(item, str) or len(item) > 256):
                    raise ValueError('Exact decimal string/null required')
                if item is not None and not Decimal(item).is_finite():
                    raise ValueError('Finite decimal required')
            _decimals(item)
    elif isinstance(value, list):
        for item in value:
            _decimals(item)


def _timely(value, now):
    observed = dt.datetime.fromisoformat(value['observedAt'])
    expires = dt.datetime.fromisoformat(value['expiresAt'])
    age = (now - observed).total_seconds()
    return (value.get('fresh') is True and 0 <= age < 60
            and now < expires <= observed + dt.timedelta(seconds=60))


def _validated(body, now):
    if (not isinstance(body, dict) or body.get('contractVersion') != 'account-credit-budget-v1'
            or body.get('unit') != 'credit' or body.get('scope') != 'all-account-use'
            or body.get('billedSpendCredits') is not None or body.get('pendingUsageCredits') is not None):
        raise ValueError('Unknown budget contract')
    admission = body.get('admission')
    if (not isinstance(admission, dict) or admission.get('permissionGranted') is not False
            or admission.get('automaticStopEnforced') is not False):
        raise ValueError('Reporting cannot grant or enforce execution')
    weekly = body.get('weeklyCredits')
    if (not isinstance(weekly, dict) or weekly.get('contractVersion') != 'weekly-credit-allocation-v1'
            or weekly.get('unit') != 'credit'):
        raise ValueError('Unknown weekly contract')
    timely = _timely(body, now) and _timely(weekly, now)
    overnight = weekly.get('overnight')
    if overnight is not None:
        if not isinstance(overnight, dict) or overnight.get('contractVersion') != 'overnight-credit-checkpoint-v1':
            raise ValueError('Unknown checkpoint contract')
        timely = _timely(overnight, now) and timely
    _decimals(body)
    return {'status': 'current' if timely else 'stale', 'fresh': timely, 'readback': body,
            'reason': 'Observational account-wide budget only. No launch permission, reservation or stop side effect. Stale/unknown evidence cannot authorize work.'}


def read_credit_budget():
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        request = urllib.request.Request(URL, headers={'Accept': 'application/json'}, method='GET')
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            if response.status != 200:
                raise ValueError('Unavailable')
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError('Oversize response')
            body = json.loads(raw)
        return _validated(body, dt.datetime.now(dt.timezone.utc))
    except (OSError, ValueError, TypeError, KeyError, AttributeError, InvalidOperation,
            RecursionError, urllib.error.URLError):
        return {'status': 'unavailable', 'fresh': False, 'readback': None,
                'reason': 'Current credit-budget readback unavailable; no allowance or stop success inferred.'}


def call(api, args):
    if not isinstance(args, dict) or args:
        raise ValueError('get_credit_budget accepts no arguments')
    return api.result(read_credit_budget())
