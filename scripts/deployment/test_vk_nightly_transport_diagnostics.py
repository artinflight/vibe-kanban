import io
import json
import subprocess
import sys
import unittest
from types import SimpleNamespace

from vk_nightly_transport_diagnostics import Diagnostics,finish


class DiagnosticTests(unittest.TestCase):
    def test_large_stderr_cannot_block_protocol_and_only_bounded_tail_retained(self):
        p=subprocess.Popen([sys.executable,'-B','-c',
            "import sys;sys.stderr.buffer.write(b'x'*200000+b'FIRST_NATIVE_CAUSE');sys.stderr.flush();print('ready',flush=True)"],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        diagnostics=Diagnostics(p.stderr)
        self.assertEqual(p.stdout.readline(),b'ready\n')
        finish(p,diagnostics=diagnostics,timeout=5)
        self.assertLessEqual(len(diagnostics.tail),65536)
        self.assertTrue(diagnostics.text().endswith('FIRST_NATIVE_CAUSE'))

    def test_broken_pipe_cleanup_preserves_original_and_native_cause(self):
        class Broken(io.BytesIO):
            def close(self):
                super().close();raise BrokenPipeError('secondary close')
        process=SimpleNamespace(stdin=Broken(),stdout=io.BytesIO(),stderr=io.BytesIO(b'actual native failure'),wait=lambda **_:1)
        original=EOFError('protocol ended')
        finish(process,original=original)
        self.assertTrue(any('secondary close' in note for note in original.__notes__))
        self.assertTrue(any('actual native failure' in note for note in original.__notes__))

    def test_owned_SSH_network_loss_marks_original_without_hiding_secondary_errors(self):
        from vk_nightly_service import failure_exit_code
        healthy=dict(event='native-health-observation',query_seconds=.3,health_observations=2,
            health_query_seconds=.6,reported_drive_fault=False,UTC='2026-10-28T02:00:00+00:00')
        details=[b'ssh: connect to host 10.0.0.109 port 22: Connection refused\n',
            (json.dumps(healthy)+'\nclient_loop: send disconnect: Broken pipe\n').encode(),
            b'Timeout, server 10.0.0.109 not responding.\n']
        for detail in details:
            p=SimpleNamespace(args=['/usr/bin/ssh','desktop','fixed'],stdin=io.BytesIO(),stdout=io.BytesIO(),
                stderr=io.BytesIO(detail),wait=lambda **_:255)
            original=EOFError('original protocol EOF')
            self.assertEqual(failure_exit_code(original),1)
            finish(p,original=original)
            self.assertEqual(type(original),EOFError)
            self.assertEqual(failure_exit_code(original),75)
            self.assertTrue(any(detail.decode().strip() in note for note in original.__notes__))

    def test_access_STOP_fault_unknown_and_missing_observation_never_become_offline(self):
        from vk_nightly_service import failure_exit_code
        from vk_nightly_transport_diagnostics import Desktop_unavailable
        network='ssh: connect to host 10.0.0.109 port 22: Connection timed out\n'
        denied=['desktop: Permission denied (publickey).\n','Host key verification failed.\n',
            'WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!\n','PermissionError: persistent B access denied\n',
            'AssertionError: reported B SMART health failure\n','ValueError: own STOP present\n',
            'ValueError: destination native serial changed\n','unexpected native diagnostic\n']
        for detail in denied+[network+d for d in denied]+['', 'only protocol EOF']:
            p=SimpleNamespace(args=['ssh','desktop'],stdin=io.BytesIO(),stdout=io.BytesIO(),
                stderr=io.BytesIO(detail.encode()),wait=lambda **_:255)
            error=EOFError('keep first error');finish(p,original=error)
            self.assertEqual(failure_exit_code(error),1,detail)
        p=SimpleNamespace(args=['python','fixture'])
        self.assertFalse(Desktop_unavailable(p,255,network))
        p.args=['ssh','desktop']
        for code in (0,1,None,-9):self.assertFalse(Desktop_unavailable(p,code,network))
        for error in (TimeoutError('unknown native observation'),PermissionError('access denied')):
            self.assertEqual(failure_exit_code(error),1)
        for error in (PermissionError('access denied'),ValueError('own STOP present'),
                      AssertionError('reported drive fault'),RuntimeError('bad native proof')):
            p=SimpleNamespace(args=['ssh','desktop'],stdin=io.BytesIO(),stdout=io.BytesIO(),
                stderr=io.BytesIO(network.encode()),wait=lambda **_:255)
            finish(p,original=error)
            self.assertEqual(failure_exit_code(error),1)

    def test_real_owned_protocol_standin_exits_with_EOF_and_keeps_first_cause(self):
        from vk_nightly_service import failure_exit_code
        # Actual isolated child/pipes/exit; a deliberately explicit SSH stand-in,
        # not a real Desktop outage or another endpoint/network connection.
        program="import sys;sys.stderr.write('ssh: connect to host 10.0.0.109 port 22: Connection refused\\n');sys.exit(255)"
        p=subprocess.Popen(['ssh','-B','-S','-c',program],executable=sys.executable,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        diagnostics=Diagnostics(p.stderr)
        self.assertEqual(p.stdout.read(1),b'')
        original=EOFError('actual stand-in pipe ended')
        finish(p,original=original,diagnostics=diagnostics,timeout=5)
        self.assertEqual(p.returncode,255);self.assertEqual(failure_exit_code(original),75)
        self.assertEqual(str(original),'actual stand-in pipe ended')

    def test_wait_timeout_is_not_hidden_or_resolved_by_killing_worker(self):
        def timeout(**_):raise subprocess.TimeoutExpired('owned SSH',.01)
        process=SimpleNamespace(stdin=io.BytesIO(),stdout=io.BytesIO(),stderr=io.BytesIO(),wait=timeout)
        with self.assertRaises(subprocess.TimeoutExpired):finish(process,timeout=.01)
