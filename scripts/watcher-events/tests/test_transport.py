"""Real local HTTP/TLS fixtures. No production addresses or credentials."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
import uuid
from unittest.mock import patch

from test_monitor import m


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        self.server.received.append((self.path, self.headers.get('Authorization'),
                                     self.rfile.read(int(self.headers['Content-Length']))))
        self.send_response(200)
        self.end_headers()
        body = {'success': True, 'data': {'id': str(uuid.uuid4()), 'session_id': self.server.sid}}
        self.wfile.write(json.dumps(body).encode())

    def do_GET(self):
        sid = self.server.sid
        if self.path.endswith('/storage-response'):
            data = {'protocol': 1, 'session_id': sid, 'workspace_id': self.server.wid, 'ready': True}
        elif '/scratch/' in self.path:
            data = {'payload': {'data': {'executor_config': self.server.config}}}
        else:
            data = {'id': sid, 'workspace_id': self.server.wid, 'executor': 'CODEX'}
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps({'success': True, 'data': data}).encode())


class Transport(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.received = []
        self.server.sid, self.server.wid = str(uuid.uuid4()), str(uuid.uuid4())
        self.server.config = {'executor': 'CODEX', 'model_id': 'fixture-selected', 'reasoning_id': 'fixture-effort',
                              'permission_policy': 'AUTO', 'routing': {'mode': 'shadow', 'floor': 'assessed',
                                                                       'denied_models': ['fixture-denied'], 'allow_escalation': False}}

    def start(self):
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        if hasattr(self, 'thread'):
            self.server.shutdown()
            self.thread.join()
        self.server.server_close()
        self.temp.cleanup()

    def test_tls_pin_binds_same_connection_before_any_post_or_secret(self):
        cert, key = self.root / 'fixture.crt', self.root / 'fixture.key'
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                        '-subj', '/CN=fixture.invalid', '-keyout', str(key), '-out', str(cert)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, key)
        self.server.socket = ctx.wrap_socket(self.server.socket, server_side=True)
        self.start()
        digest = hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert.read_text())).hexdigest()
        env = self.root / 'fixture.env'
        def write(pin):
            env.write_text(f'MCP_NOTIFICATIONS_NTFY_URL=https://127.0.0.1:{self.server.server_port}\n'
                           'MCP_NOTIFICATIONS_NTFY_TOPIC=fixture-only\n'
                           'MCP_NOTIFICATIONS_NTFY_TOKEN=fixture-canary-not-a-credential\n'
                           f'MCP_NOTIFICATIONS_NTFY_TLS_PIN_SHA256={pin}\n'
                           'UNRELATED_VARIABLE=must-never-transmit\n')
        write('0' * 64)
        with self.assertRaises(ValueError):
            m.publisher({'notification_env': str(env)})('ssd', 'critical', 93)
        self.assertFalse(self.server.received)
        write(digest)
        m.publisher({'notification_env': str(env)})('ssd', 'critical', 93)
        self.assertEqual(len(self.server.received), 1)
        path, auth, body = self.server.received[0]
        self.assertEqual(path, '/fixture-only')
        self.assertEqual(auth, 'Bearer fixture-canary-not-a-credential')
        self.assertNotIn(b'must-never-transmit', body)

    def test_existing_connector_selection_on_fixture_is_not_a_T64_protocol_test(self):
        source = os.environ.get('STORAGE_CONNECTOR_SOURCE')
        if not source:
            self.skipTest('Set STORAGE_CONNECTOR_SOURCE for existing-transport compatibility test')
        source = Path(source)
        sys.path.insert(0, str(source))
        spec = importlib.util.spec_from_file_location('fixture_adapter', source / 'adapter.py')
        api = importlib.util.module_from_spec(spec)
        # Current connector helpers resolve their owning facade through sys.modules.
        # Register only this isolated fixture module; never import/mutate a live adapter.
        with patch.dict(sys.modules, {'fixture_adapter': api}):
            spec.loader.exec_module(api)
            self.start()
            api.BASE = f'http://127.0.0.1:{self.server.server_port}'
            # Avoid the live WebSocket helper entirely: the execution snapshot is a fixture.
            api.session_configs = lambda sid: [{'session_id': sid, 'created_at': 'fixture', 'config': self.server.config}]
            self.assertEqual(api.resolve_followup_config(self.server.sid), self.server.config)
            self.assertFalse(self.server.received)


if __name__ == '__main__':
    unittest.main()
