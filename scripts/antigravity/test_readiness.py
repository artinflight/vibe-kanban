import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from readiness import probe


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime = self.root / 'peer'
        self.receipt = self.root / 'receipt.json'

    def peer(self, session, *, initialization=None, prefix=''):
        initialization = initialization or {'protocolVersion': 1, 'authMethods': [{'id': 'oauth-personal'}]}
        program = '''#!/usr/bin/python3
import json, pathlib, sys, time
''' + prefix + '\n' + '''
for line in sys.stdin:
    value=json.loads(line)
    with pathlib.Path('methods').open('a') as out: out.write(value['method']+'\\n')
    print('PRIVATE_OAUTH_URL', file=sys.stderr, flush=True)
    result = INIT if value['method']=='initialize' else SESSION
    print(json.dumps(dict(jsonrpc='2.0',id=value['id'],**result)),flush=True)
'''.replace('INIT', repr({'result': initialization})).replace('SESSION', repr(session))
        self.runtime.write_text(program)
        self.runtime.chmod(0o700)
        return hashlib.sha256(self.runtime.read_bytes()).hexdigest()

    def run_probe(self, digest, **kwargs):
        return probe(self.runtime, digest, self.root, self.receipt, **kwargs)

    def test_auth_required_never_sends_authentication_or_prompt_or_logs_secrets(self):
        digest = self.peer({'error': {'code': -32000, 'message': 'PRIVATE_LOGIN_URL', 'data': 'SECRET'}})
        result = self.run_probe(digest)
        self.assertEqual(result['outcome'], 'authentication_required')
        self.assertEqual((self.root / 'methods').read_text(), 'initialize\nsession/new\n')
        self.assertNotIn('PRIVATE', self.receipt.read_text())
        self.assertNotIn('SECRET', self.receipt.read_text())
        self.assertEqual(self.receipt.stat().st_mode & 0o777, 0o600)

    def test_session_readiness_is_not_inference_and_does_not_publish_session_id(self):
        digest = self.peer({'result': {'sessionId': 'PRIVATE_SESSION', 'configOptions': []}})
        result = self.run_probe(digest)
        self.assertEqual(result['outcome'], 'session_ready_without_inference')
        self.assertTrue(result['config_options_present'])
        self.assertFalse(result['legacy_models_present'])
        self.assertEqual(result['prompt_calls'], 0)
        self.assertNotIn('PRIVATE_SESSION', self.receipt.read_text())

    def test_hash_mismatch_launches_nothing(self):
        self.peer({'result': {}})
        with self.assertRaises(ValueError):
            self.run_probe('0' * 64)
        self.assertFalse((self.root / 'methods').exists())
        self.assertFalse(self.receipt.exists())

    def test_consumed_receipt_cannot_be_reused(self):
        digest = self.peer({'result': {}})
        self.receipt.write_text('existing')
        with self.assertRaises(FileExistsError):
            self.run_probe(digest)
        self.assertEqual(self.receipt.read_text(), 'existing')

    def test_timeout_reaps_only_owned_child(self):
        digest = self.peer({'result': {}}, prefix='time.sleep(10)')
        result = self.run_probe(digest, request_timeout=.1, total_timeout=.2)
        self.assertEqual(result['error_type'], 'TimeoutError')
        self.assertTrue(result['owned_process_reaped'])

    def test_unsupported_protocol_never_creates_session(self):
        digest = self.peer({'result': {}}, initialization={'protocolVersion': 999})
        self.assertEqual(self.run_probe(digest)['outcome'], 'probe_failed')
        self.assertEqual((self.root / 'methods').read_text(), 'initialize\n')


if __name__ == '__main__':
    unittest.main()
