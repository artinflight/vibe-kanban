"""Reviewed storage-admission-v2 codec. Transport is explicitly injected, never discovered.

The runtime Bridge remains disabled. Isolated native tests supply the actual
router transport; a later reviewed ingress integration must supply production I/O.
"""
import datetime as dt
import hashlib
import json
import math
import re
import uuid

PROTOCOL = 'storage-admission-v2'
UNKNOWN = {'kind': 'unknown', 'reason': 'unconfirmed_delivery'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def utc(seconds):
    # Floor to microseconds so conversion cannot turn an observation into the future.
    micros = math.floor(seconds * 1_000_000)
    stamp = dt.datetime.fromtimestamp(micros // 1_000_000, dt.timezone.utc).replace(microsecond=micros % 1_000_000)
    precision = 'seconds' if stamp.microsecond == 0 else 'milliseconds' if stamp.microsecond % 1000 == 0 else 'microseconds'
    return stamp.isoformat(timespec=precision).replace('+00:00', 'Z')


def parse_utc(value):
    return dt.datetime.fromisoformat(value.replace('Z', '+00:00'))


def uuid_text(value):
    return isinstance(value, str) and str(uuid.UUID(value)) == value and uuid.UUID(value).int != 0


def decode(body, document, attempt_ids):
    """Only a fully bound native receipt yields admission or no-admission proof."""
    try:
        receipt = body['receipt']
        kind = body['outcome']
        intent = document['intent']
        if (body['protocol'] != PROTOCOL or kind not in {'accepted', 'deferred', 'rejected'}
                or type(body['replay']) is not bool or body['automatic_launch_queued'] is not False
                or body['no_admission'] is not (kind != 'accepted')
                or receipt['state'] != kind or receipt['reason'] != body['reason']
                or receipt['batch_id'] != document['batch_id']
                or receipt['intent_sha256'] != document['intent_sha256']
                or any(receipt[k] != intent[k] for k in ('workspace_id', 'session_id'))
                or not uuid_text(receipt['attempt_id']) or receipt['attempt_id'] not in attempt_ids
                or not re.fullmatch('[a-zA-Z0-9_]{1,80}', body['reason'])):
            return dict(UNKNOWN)
        # A replayed older deferral cannot authorize retry of a newer uncertain attempt.
        if kind != 'accepted' and receipt['attempt_id'] != document['attempt_id']:
            return dict(UNKNOWN)
        execution = receipt['execution_id']
        status = body['execution_status']
        if kind == 'accepted':
            if not uuid_text(execution) or status not in {None, 'running', 'completed', 'failed', 'killed'}:
                return dict(UNKNOWN)
        elif execution is not None or status is not None:
            return dict(UNKNOWN)
        return {'kind': kind, 'batch_id': document['batch_id'],
                'intent_sha256': document['intent_sha256'], 'receipt_id': receipt['attempt_id'],
                'execution_id': execution, 'execution_status': status,
                'definitely_not_admitted': kind != 'accepted', 'reason': body['reason']}
    except (KeyError, TypeError, ValueError, AttributeError):
        return dict(UNKNOWN)


def request(document):
    """Internal durable observations stay private; only their hash crosses ingress."""
    intent = document['intent']
    if digest(intent) != document['intent_sha256']:
        raise ValueError('intent_fingerprint_mismatch')
    return {k: document[k] for k in ('batch_id', 'attempt_id', 'intent_sha256', 'intent')} | {
        'protocol': PROTOCOL, 'validation': document['validation']}


class NativeAdapter:
    """Actual v2 methods over injected native transport(method, path, JSON-or-None).

    No credentials, default URL, subscription, DELETE, follow-up fallback or
    production enable flag. Non-2xx/native parser errors must raise in transport.
    """
    def __init__(self, binding, transport, observe, max_validation_age_seconds):
        self._binding = dict(binding)
        if (not all(uuid_text(binding[k]) for k in ('workspace_id', 'session_id'))
                or not re.fullmatch('[a-f0-9]{64}', binding['executor_config_sha256'])
                or type(max_validation_age_seconds) is not int
                or not 1 <= max_validation_age_seconds <= 300):
            raise ValueError('reviewed_exact_binding_and_freshness_required')
        self.transport, self.observe = transport, observe
        self.max_validation_age_seconds = max_validation_age_seconds

    def binding(self):
        return dict(self._binding)

    def ready(self):
        # Native atomic admission is authoritative, never a cached idle check.
        return True

    def send(self, document):
        if any(document['intent'].get(k) != v for k, v in self._binding.items()):
            raise ValueError('saved_binding_drift')
        body = self.transport('POST', '/api/storage-alerts/batches', request(document))
        return decode(body, document, document['known_attempt_ids'])

    def lookup(self, batch_id, fingerprint, document):
        body = self.transport('GET', f'/api/storage-alerts/batches/{batch_id}?intent_sha256={fingerprint}', None)
        return decode(body, document, document['known_attempt_ids'])
