"""Explicit printer-style connector transport; never impersonates native v2 receipts.

One POST at most per durable batch. Lost/queued replies reconcile exact persisted
execution prompts only. Missing evidence holds forever; it never permits resend.
"""
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import subprocess
import sys
import time
import uuid

import native_adapter as codec

TRANSPORT = 'connector-follow-up-v1'
CONNECTOR = Path('/home/mcp/code/vibe-dot-connector')
TERMINAL = {'completed', 'failed', 'killed'}


def load_connector():
    if str(CONNECTOR) not in sys.path:
        sys.path.insert(0, str(CONNECTOR))
    spec = importlib.util.spec_from_file_location('wakewatch_existing_connector', CONNECTOR / 'adapter.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def database(config):
    path = Path(config['vibe_db']).resolve(strict=True)
    db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=.5)
    db.execute('PRAGMA query_only=ON')
    deadline = time.monotonic() + 3
    db.set_progress_handler(lambda: int(time.monotonic() > deadline), 10000)
    return db


def owner_idle(config):
    import t26_watch
    import owner_activity
    return (not t26_watch.busy(t26_watch.owner_status(config))
            and not owner_activity.custody_issues(config))


class ConnectorBridge:
    transport = TRANSPORT

    def __init__(self, config):
        self.config = config
        settings = config.get('connector_transport', {})
        if config.get('dispatch_transport') != TRANSPORT or config.get('activation_approved') is not True or settings.get('enabled') is not True:
            raise ValueError('connector_transport_disabled')
        self._binding = {k: config[k] for k in ('workspace_id', 'session_id')}
        self._binding['executor_config_sha256'] = settings['executor_config_sha256']
        if not all(codec.uuid_text(self._binding[k]) for k in ('workspace_id', 'session_id')) or not re.fullmatch('[a-f0-9]{64}', self._binding['executor_config_sha256']):
            raise ValueError('exact_saved_owner_binding_required')
        self.max_validation_age_seconds = settings['max_validation_age_seconds']
        if type(self.max_validation_age_seconds) is not int or not 1 <= self.max_validation_age_seconds <= 60:
            raise ValueError('bounded_freshness_required')
        self.root = Path(config['state_file']).parent / 'connector-receipts'

    def binding(self):
        return dict(self._binding)

    def ready(self):
        if not owner_idle(self.config):
            return False
        module = load_connector()
        session = module.http_get('/api/sessions/' + self._binding['session_id'])
        data = session.get('data', {})
        if session.get('success') is not True or data.get('workspace_id') != self._binding['workspace_id'] or data.get('executor') != 'CODEX':
            return False
        config = module.resolve_followup_config(self._binding['session_id'])
        return (config.get('executor') == 'CODEX' and config.get('variant') in (None, 'DEFAULT')
                and (config.get('routing') or {}).get('mode') == 'shadow'
                and codec.digest(config) == self._binding['executor_config_sha256'])

    def observe(self, key):
        import monitor
        return monitor.sample_volume(self.config['volumes'][key])

    def validate(self, document):
        if (not codec.uuid_text(document['batch_id']) or not codec.uuid_text(document['attempt_id'])
                or codec.digest(document['intent']) != document['intent_sha256']
                or any(document['intent'].get(k) != v for k, v in self._binding.items())):
            raise ValueError('immutable_connector_binding_mismatch')
        prompt = document['intent']['prompt']
        if not isinstance(prompt, str) or not 1 <= len(prompt) <= 60000 or '[storage-response ' + document['batch_id'] + ']' not in prompt:
            raise ValueError('exact_batch_marker_required')
        return prompt

    def unknown(self, reason='connector_unconfirmed_no_retry'):
        return {'kind': 'unknown', 'reason': reason}

    def send(self, document):
        prompt = self.validate(document)
        path = self.root / (document['batch_id'] + '.json')
        if path.exists():
            return self.lookup(document['batch_id'], document['intent_sha256'], document)
        # This refusal occurs before any connector invocation; retry may use new
        # fresh evidence under the same immutable batch, unlike a lost response.
        observed = codec.parse_utc(document['validation']['observed_at']).timestamp()
        if not self.ready() or not 0 <= time.time() - observed <= self.max_validation_age_seconds:
            return {'kind': 'deferred', 'reason': 'connector_preflight_hold', 'batch_id': document['batch_id'],
                    'intent_sha256': document['intent_sha256'], 'receipt_id': 'local-preflight:' + document['attempt_id'],
                    'definitely_not_admitted': True}
        self.root.mkdir(mode=0o700, exist_ok=True)
        if len(list(self.root.glob('*.json'))) >= 4096:
            raise ValueError('retained_connector_receipt_quota')
        receipt = {'transport': TRANSPORT, 'batch_id': document['batch_id'], 'intent_sha256': document['intent_sha256'],
                   'attempt_id': document['attempt_id'], 'not_before': time.time(), 'state': 'dispatching'}
        # O_EXCL is a second cross-process fence. A crash after this commit is
        # deliberately ambiguous and cannot cause another POST after reopening.
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            return self.lookup(document['batch_id'], document['intent_sha256'], document)
        with os.fdopen(fd, 'w') as stream:
            json.dump(receipt, stream); stream.flush(); os.fsync(stream.fileno())
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)
        message = {'jsonrpc': '2.0', 'id': document['attempt_id'], 'method': 'tools/call',
                   'params': {'name': 'run_session_prompt', 'arguments': {'session_id': self._binding['session_id'], 'prompt': prompt}}}
        try:
            # Exactly the existing printer watcher entrypoint; no new API,
            # credentials, model selection, process injection or direct DB writes.
            result = subprocess.run(['/usr/bin/python3', '-B', str(CONNECTOR / 'adapter.py')],
                                    input=json.dumps(message) + '\n', capture_output=True, text=True,
                                    timeout=110, cwd=str(CONNECTOR))
            if len(result.stdout) <= 2 * 1024 * 1024:
                rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
                reply = next(row for row in rows if row.get('id') == document['attempt_id'])
                if not reply.get('error') and not reply.get('result', {}).get('isError'):
                    data = json.loads(reply['result']['content'][0]['text'])
                    receipt['state'] = 'queued_no_retry' if data.get('status') == 'queued' else 'response_received'
                    receipt['reported_execution_id'] = data.get('execution_id')
        except (OSError, ValueError, KeyError, StopIteration, subprocess.SubprocessError):
            receipt['state'] = 'unconfirmed_no_retry'
        tmp = path.with_suffix('.tmp')
        with tmp.open('w') as stream:
            os.chmod(tmp, 0o600); json.dump(receipt, stream); stream.flush(); os.fsync(stream.fileno())
        tmp.replace(path)
        # A connector success alone isn't certification: independently bind the
        # persisted execution to this exact session, prompt and saved config.
        return self.lookup(document['batch_id'], document['intent_sha256'], document)

    def lookup(self, batch_id, fingerprint, document=None):
        prompt = self.validate(document)
        if batch_id != document['batch_id'] or fingerprint != document['intent_sha256']:
            raise ValueError('lookup_binding_mismatch')
        path = self.root / (batch_id + '.json')
        if not path.exists():
            return self.unknown()
        receipt = json.loads(path.read_text())
        if receipt.get('transport') != TRANSPORT or receipt.get('intent_sha256') != fingerprint or receipt.get('batch_id') != batch_id:
            raise ValueError('local_receipt_binding_mismatch')
        since = dt.datetime.fromtimestamp(receipt['not_before'] - 5, dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        with database(self.config) as db:
            rows = db.execute('SELECT id,status,executor_action FROM execution_processes WHERE session_id=? AND datetime(created_at)>=datetime(?) ORDER BY created_at DESC LIMIT 129', (uuid.UUID(self._binding['session_id']).bytes, since)).fetchall()
        if len(rows) > 128:
            return self.unknown('connector_inventory_limit')
        found = []
        for eid, status, raw in rows:
            action = json.loads(raw).get('typ', {})
            if action.get('prompt') == prompt and codec.digest(action.get('executor_config')) == self._binding['executor_config_sha256']:
                found.append((str(uuid.UUID(bytes=eid)), status))
        if len(found) != 1:
            return self.unknown('connector_queued_no_retry' if receipt.get('state') == 'queued_no_retry' else 'connector_unconfirmed_no_retry')
        eid, status = found[0]
        if receipt.get('reported_execution_id') not in (None, eid):
            return self.unknown('connector_execution_mismatch')
        return {'kind': 'accepted', 'reason': 'connector_execution_verified', 'batch_id': batch_id,
                'intent_sha256': fingerprint, 'receipt_id': 'connector:' + receipt['attempt_id'],
                'execution_id': eid, 'execution_status': status}

    def execution(self, execution_id):
        with database(self.config) as db:
            row = db.execute('SELECT status FROM execution_processes WHERE id=? AND session_id=?',
                             (uuid.UUID(execution_id).bytes, uuid.UUID(self._binding['session_id']).bytes)).fetchone()
        if not row:raise ValueError('execution_status_unknown')
        return row[0]


def save_private(path, value):
    temp = path.with_suffix('.tmp')
    with temp.open('w') as stream:
        os.chmod(temp, 0o600); json.dump(value, stream, indent=2); stream.flush(); os.fsync(stream.fileno())
    temp.replace(path)


def process_probe(config):
    """One operator-requested probe, drained by the existing timer only when idle.

    Caller owns the same existing incident-file flock as normal disk ticks.
    No probe is created here, and an uncertain probe is never resubmitted.
    """
    path = Path(config['state_file']).parent / 'connector-probe.json'
    if not path.exists():
        return None
    probe = json.loads(path.read_text())
    if probe.get('state') in {'completed', 'failed', 'killed', 'expired'}:
        return probe['state']
    bridge = ConnectorBridge(config)
    if probe['state'] == 'pending':
        if time.time() > probe['expires_at']:
            probe['state'] = 'expired'
        elif not bridge.ready():
            return 'pending_owner_busy_or_config_hold'
        else:
            document = probe['document']
            document['validation']['observed_at'] = codec.utc(time.time())
            probe['state'] = 'dispatching'
            save_private(path, probe)
            outcome = bridge.send(document)
            # A definite pre-POST hold may safely remain pending. Everything
            # after the outbox intent is lookup-only on all future timer ticks.
            probe['state'] = 'pending' if outcome['kind'] == 'deferred' else outcome['kind']
            probe['outcome'] = outcome
    else:
        outcome = bridge.lookup(probe['document']['batch_id'], probe['document']['intent_sha256'], probe['document'])
        probe['outcome'] = outcome
        probe['state'] = outcome['kind']
        if outcome['kind'] == 'accepted':
            status = bridge.execution(outcome['execution_id'])
            if status in TERMINAL:
                probe['state'] = status
    save_private(path, probe)
    return probe['state']
