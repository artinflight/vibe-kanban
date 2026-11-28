import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest

from vk_restart_tracking_client import TrackingClient, birth, installed


class PrefixRequired(ValueError):
    pass


class TrackingTransport(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='vk-tracker-rpc-test-', dir='/dev/shm')
        self.endpoint = Path(self.temp.name) / 'observer.sock'
        self.server = socket.socket(socket.AF_UNIX)
        self.server.bind(str(self.endpoint))
        os.chmod(self.endpoint, 0o600)
        self.server.listen(1)
        self.server.settimeout(.5)
        self.original = lambda *_: {'original': True}
        self.module = SimpleNamespace(canonical=lambda value: json.dumps(value).encode(),
                                      MAX_RESPONSE=1024, RetainedPrefixRequired=PrefixRequired,
                                      query=self.original)
        self.threads = []

    def tearDown(self):
        self.server.close()
        for thread in self.threads:
            thread.join(timeout=1)
        self.temp.cleanup()

    def reply(self, value, delay=0):
        def serve():
            try:
                connection, _ = self.server.accept()
                with connection:
                    connection.settimeout(.5)
                    connection.recv(4096)
                    if delay:
                        threading.Event().wait(delay)
                    connection.sendall(json.dumps(value).encode())
            except OSError:
                pass
        thread = threading.Thread(target=serve)
        self.threads.append(thread)
        thread.start()

    def client(self, **changes):
        fields = {'endpoint': self.endpoint, 'instance': 'a' * 32,
                  'owner_pid': os.getpid(), 'owner_start_ticks': birth(os.getpid()),
                  'owner_uid': os.getuid(), 'timeout_seconds': .5, 'guard': lambda: None}
        fields.update(changes)
        return TrackingClient(self.module, **fields)

    def query(self, client):
        return client.query(self.endpoint, {'instance': 'a' * 32, 'since': 0, 'barrier': True})

    def test_raw_coverage_fields_pass_unchanged(self):
        raw = {'ready': False, 'errors': [{'actual': 'coverage error'}],
               'instance': 'a' * 32, 'sequence': 9}
        self.reply(raw)
        self.assertEqual(self.query(self.client()), raw)

    def test_retained_prefix_requirement_is_preserved(self):
        self.reply({'request_error': 'retained B journal prefix required through 481'})
        with self.assertRaises(PrefixRequired) as caught:
            self.query(self.client())
        self.assertEqual(caught.exception.args, (481,))

    def test_whole_response_wait_is_finite(self):
        self.reply({'ready': True}, delay=.2)
        start = time.monotonic()
        with self.assertRaises(TimeoutError):
            self.query(self.client(timeout_seconds=.05))
        self.assertLess(time.monotonic() - start, .5)

    def test_peer_PID_is_authenticated(self):
        self.reply({'ready': True})
        with self.assertRaisesRegex(ValueError, 'socket peer'):
            self.query(self.client(owner_pid=os.getppid(), owner_start_ticks=birth(os.getppid())))

    def test_process_birth_mismatch_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'endpoint/process'):
            self.query(self.client(owner_start_ticks=birth(os.getpid()) + 1))

    def test_response_bound_is_preserved(self):
        self.reply({'payload': 'a' * 2048})
        with self.assertRaisesRegex(ValueError, 'bounded tracking response'):
            self.query(self.client())

    def test_source_and_epoch_cannot_be_selected_by_request(self):
        client = self.client()
        with self.assertRaisesRegex(ValueError, 'bound observer'):
            client.query(self.endpoint, {'instance': 'b' * 32})
        with self.assertRaisesRegex(ValueError, 'bound observer'):
            client.query(self.endpoint.with_name('other.sock'), {'instance': 'a' * 32})

    def test_explicit_adapter_restores_module_on_success_and_failure(self):
        client = self.client()
        with installed(self.module, client):
            self.assertIsNot(self.module.query, self.original)
        self.assertIs(self.module.query, self.original)
        with self.assertRaisesRegex(RuntimeError, 'test failure'):
            with installed(self.module, client):
                raise RuntimeError('test failure')
        self.assertIs(self.module.query, self.original)


if __name__ == '__main__':
    unittest.main()
