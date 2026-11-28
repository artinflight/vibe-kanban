"""Bounded client for the existing local native gateway. No authentication claim.

The destination is fixed; this client uses existing host/process reachability.
It neither grants access nor changes the gateway's exposure or server controls.
"""
from http.client import HTTPConnection
import json
import re

import native_adapter as native

HOST = '127.0.0.1'
PORT = 4720
MAX_BYTES = 65536
TIMEOUT_SECONDS = 10
COLLECTION = '/api/storage-alerts/batches'
LOOKUP = re.compile(r'/api/storage-alerts/batches/([0-9a-f-]{36})\?intent_sha256=([0-9a-f]{64})')


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate_native_response_key')
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError('nonfinite_native_response')


class LocalNativeHTTP:
    """POST collection / GET exact receipt only; one connection, no retries.

    No URL, proxy, credential, Origin, relay-marker or caller-header options.
    HTTPConnection does not follow redirects or use environment proxy settings.
    This is client scoping, not an authentication/security boundary against
    another process running under the same existing host identity.
    """
    def __init__(self, binding):
        self.binding = dict(binding)

    def encode(self, method, path, body):
        if method == 'GET':
            match = LOOKUP.fullmatch(path) if isinstance(path, str) else None
            if body is not None or not match or not native.uuid_text(match[1]):
                raise ValueError('bound_native_lookup_required')
            return None
        if method != 'POST' or path != COLLECTION or not isinstance(body, dict):
            raise ValueError('native_method_path_not_allowed')
        if (set(body) != {'protocol', 'batch_id', 'attempt_id', 'intent_sha256', 'intent', 'validation'}
                or body['protocol'] != native.PROTOCOL
                or not native.uuid_text(body['batch_id']) or not native.uuid_text(body['attempt_id'])):
            raise ValueError('native_request_shape_required')
        intent = body['intent']
        if (not isinstance(intent, dict)
                or set(intent) != {'workspace_id', 'session_id', 'executor_config_sha256',
                                   'incidents', 'receipt_ref', 'prompt'}
                or any(intent.get(k) != v for k, v in self.binding.items())
                or native.digest(intent) != body['intent_sha256']):
            raise ValueError('native_exact_intent_binding_required')
        incidents = intent['incidents']
        if (not isinstance(incidents, list) or not 1 <= len(incidents) <= 8
                or any(not isinstance(i, dict)
                       or set(i) != {'incident_id', 'filesystem_uuid', 'policy', 'opened_at'}
                       or not native.uuid_text(i['incident_id']) for i in incidents)):
            raise ValueError('native_incident_shape_required')
        validation = body['validation']
        if (not isinstance(validation, dict)
                or set(validation) != {'observed_at', 'eligible_incident_ids', 'evidence_sha256'}
                or validation['eligible_incident_ids'] != [i['incident_id'] for i in incidents]
                or not isinstance(validation['evidence_sha256'], str)
                or not re.fullmatch('[a-f0-9]{64}', validation['evidence_sha256'])):
            raise ValueError('native_validation_shape_required')
        raw = native.canonical(body).encode('utf-8')
        if len(raw) > MAX_BYTES:
            raise ValueError('native_request_too_large')
        return raw

    def __call__(self, method, path, body):
        raw = self.encode(method, path, body)  # Validate before any socket can exist.
        connection = HTTPConnection(HOST, PORT, timeout=TIMEOUT_SECONDS)
        try:
            headers = {'Accept': 'application/json', 'Connection': 'close'}
            if raw is not None:
                headers['Content-Type'] = 'application/json'
            connection.request(method, path, body=raw, headers=headers)
            response = connection.getresponse()
            if (response.status != 200 or response.getheader('Content-Type', '').split(';')[0].strip().lower()
                    != 'application/json'):
                # Includes redirects, parser errors, gateway maintenance and access denial.
                # No alternate target, credential, header or status-based retry is attempted.
                raise ValueError('native_response_not_positive_protocol')
            data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError('native_response_too_large')
            result = json.loads(data.decode('utf-8'), object_pairs_hook=unique_object,
                                parse_constant=reject_constant)
            if not isinstance(result, dict):
                raise ValueError('native_response_object_required')
            return result
        finally:
            connection.close()
