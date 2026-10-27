import io
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

    def test_wait_timeout_is_not_hidden_or_resolved_by_killing_worker(self):
        def timeout(**_):raise subprocess.TimeoutExpired('owned SSH',.01)
        process=SimpleNamespace(stdin=io.BytesIO(),stdout=io.BytesIO(),stderr=io.BytesIO(),wait=timeout)
        with self.assertRaises(subprocess.TimeoutExpired):finish(process,timeout=.01)
