"""Retained process/lease regressions, no VK, SSH, services or production roots."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest

from vk_candidate_owner import PreparationLease, PreparationState, notify, probe, record_verification


ROOT = Path('/mnt/vk-storage/vk-safe-release-20261008/owner-lifecycle-tests')
ROOT.mkdir(exist_ok=True)
CHILD = r'''
import json,os,sys
from pathlib import Path
from vk_candidate_owner import PreparationLease,PreparationState,PreparationStatus
root=Path(sys.argv[1]);p=root/'lease';s=p.stat()
with PreparationLease(p,(s.st_dev,s.st_ino)) as lease:
    state=PreparationState(root/'state.json',{'phase':'verified','root_binding':'a'*64,'source':'b'*64})
    # A durable successful verification precedes SSH/stdout closure.
    (root/'verified.json').write_text(json.dumps({'verification_completed':True}))
    server=PreparationStatus(root/'status.sock',lease,lambda:dict(state.value))
    server.socket.settimeout(5)
    os.write(1,b'V');assert sys.stdin.buffer.read(1)==b'C'
    from vk_candidate_owner import notify
    assert notify({'verification_completed':True}) is False
    for _ in range(4):server.serve_once()
    server.close()
'''


class OwnerTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='own-', dir=ROOT))
        self.path = self.root / 'lease'
        fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
        os.close(fd)
        s = self.path.stat()
        self.identity = (s.st_dev, s.st_ino)

    def test_closed_stdout_after_verification_preserves_owner_and_client_disconnect(self):
        env = {**os.environ, 'PYTHONPATH': str(Path(__file__).parent)}
        child = subprocess.Popen([sys.executable, '-B', '-c', CHILD, str(self.root)],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, env=env)
        ready = child.stdout.read(1)
        if ready != b'V':
            child.stdin.close(); child.stdout.close()
            child.wait(timeout=7)
            error = child.stderr.read().decode(); child.stderr.close()
            self.fail('fixture failed before ready: ' + error)
        state = json.loads((self.root / 'state.json').read_text())
        self.assertTrue(json.loads((self.root / 'verified.json').read_text())['verification_completed'])
        child.stdout.close()
        child.stdin.write(b'C'); child.stdin.flush()
        # A caller disappearing before a response must not release the owner.
        with socket.socket(socket.AF_UNIX) as gone:
            gone.connect(str(self.root / 'status.sock'))
        args = dict(root_binding='a' * 64, source='b' * 64)
        live = probe(self.root / 'status.sock', child.pid, state['owner_start'], **args)
        self.assertTrue(live['preparation_lease_held'])
        with self.assertRaisesRegex(ValueError, 'binding mismatch'):
            probe(self.root / 'status.sock', child.pid, state['owner_start'],
                  root_binding='a' * 64, source='e' * 64)
        live = probe(self.root / 'status.sock', child.pid, state['owner_start'], **args)
        self.assertEqual(live['phase'], 'verified')
        self.assertFalse(live['operational_activation_available'])
        child.wait(timeout=5)
        self.assertEqual(child.returncode, 0, child.stderr.read().decode())
        child.stdin.close(); child.stderr.close()
        # A successful durable proof cannot assert its process still survives.
        self.assertFalse(json.loads((self.root / 'state.json').read_text())['controller_retained_alive'])
        self.assertTrue(state['requires_live_owner_probe'])
        with self.assertRaises(FileNotFoundError):
            probe(self.root / 'status.sock', child.pid, state['owner_start'], **args)
        with PreparationLease(self.path, self.identity) as fresh:
            self.assertTrue(fresh.verify())

    def test_closed_optional_log_is_not_buffered(self):
        reader, writer = os.pipe()
        os.close(reader)
        self.assertFalse(notify({'verified': True}, fd=writer))
        os.close(writer)
        self.assertFalse(notify({'verified': True}, fd=writer))

    def test_closed_stdout_does_not_swallow_archive_transport_failure(self):
        state = PreparationState(self.root / 'state.json', {})
        reader, writer = os.pipe()
        os.close(reader)
        def failed_archive():
            raise ValueError('archive EOF verification failed')
        with self.assertRaisesRegex(ValueError, 'archive EOF'):
            record_verification(state, failed_archive, fd=writer)
        os.close(writer)
        raw = json.loads(state.path.read_text())
        self.assertFalse(raw['verification_completed'])
        self.assertFalse(raw['controller_retained_alive'])
        self.assertEqual(raw['phase'], 'verification-failed')

    def test_lease_contention_and_replacement_fail_closed_without_deletion(self):
        with PreparationLease(self.path, self.identity) as first:
            with self.assertRaises(BlockingIOError):
                with PreparationLease(self.path, self.identity):
                    pass
            self.path.rename(self.root / 'retained-original-lease')
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
            os.close(fd)
            with self.assertRaisesRegex(ValueError, 'binding changed'):
                first.verify()

    def test_persisted_alive_claim_is_replaced_by_required_live_probe(self):
        state = PreparationState(self.root / 'state.json', {'controller_retained_alive': True})
        state.publish(phase='verified', controller_retained_alive=True)
        raw = json.loads(state.path.read_text())
        self.assertFalse(raw['controller_retained_alive'])
        self.assertTrue(raw['requires_live_owner_probe'])

    def test_recorded_lease_mode_requires_exact_private_parent_without_chmod(self):
        self.path.chmod(0o664)  # New fixture only; no actual candidate chmod.
        with self.assertRaisesRegex(ValueError, 'unsafe preparation lease'):
            with PreparationLease(self.path, self.identity):
                pass
        with PreparationLease(self.path, self.identity, expected_mode=0o664) as lease:
            self.assertTrue(lease.verify())
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o664)
            self.root.chmod(0o755)  # Retained fixture demonstrates fail-closed exposure.
            with self.assertRaisesRegex(ValueError, 'remain private'):
                lease.verify()
