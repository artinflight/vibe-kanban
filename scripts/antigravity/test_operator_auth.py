import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from operator_auth import authenticate


class OperatorAuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime = self.root / 'peer'
        self.attempt = self.root / 'attempt'
        self.browser = self.root / 'browser'
        self.browser.write_text('#!/bin/sh\nexit 0\n')
        self.browser.chmod(0o700)

    def peer(self, auth=None, *, methods=None, pause=False, client_request=False):
        init = {'protocolVersion': 1, 'authMethods': methods if methods is not None else [{'id': 'oauth-personal', 'type': 'agent'}]}
        responses = {
            'initialize': {'result': init},
            'authenticate': auth if auth is not None else {'result': {}},
            'session/new': {'result': {'sessionId': 'PRIVATE_SESSION', 'configOptions': []}},
        }
        self.runtime.write_text('''#!/usr/bin/python3
import json, pathlib, sys, time
responses = ''' + repr(responses) + '''
for line in sys.stdin:
    value = json.loads(line)
    with pathlib.Path('../methods').open('a') as out: out.write(value['method']+'\\n')
    print('PRIVATE_LOGIN_URL', file=sys.stderr, flush=True)
    if ''' + repr(pause) + ''' and value['method']=='authenticate': time.sleep(10)
    if ''' + repr(client_request) + ''' and value['method']=='authenticate':
        print(json.dumps({'jsonrpc':'2.0','id':99,'method':'session/request_permission','params':{}}),flush=True)
        continue
    print(json.dumps(dict(jsonrpc='2.0',id=value['id'],**responses[value['method']])),flush=True)
''')
        self.runtime.chmod(0o700)
        return hashlib.sha256(self.runtime.read_bytes()).hexdigest()

    def run_auth(self, digest, **kw):
        return authenticate(self.runtime, digest, self.attempt, self.browser, ':110', **kw)

    def methods(self):
        return (self.attempt / 'methods').read_text().splitlines()

    def test_personal_ack_before_session_no_prompt_and_no_secret_in_safe_receipt(self):
        result = self.run_auth(self.peer())
        self.assertTrue(result['session_created'])
        self.assertEqual(self.methods(), ['initialize', 'authenticate', 'session/new'])
        safe = (self.attempt / 'RESULT.safe.json').read_text()
        self.assertNotIn('PRIVATE', safe)
        self.assertEqual(result['prompt_calls'], 0)
        private = self.attempt / 'SESSION.private.json'
        self.assertEqual(private.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.attempt.stat().st_mode & 0o777, 0o700)
        self.assertEqual(json.loads(private.read_text())['sessionId'], 'PRIVATE_SESSION')

    def test_auth_rejection_never_creates_session_or_logs_provider_error(self):
        result = self.run_auth(self.peer({'error': {'code': -32000, 'message': 'PRIVATE_TOKEN'}}))
        self.assertFalse(result['session_created'])
        self.assertEqual(result['request_error_code'], -32000)
        self.assertEqual(self.methods(), ['initialize', 'authenticate'])
        self.assertNotIn('PRIVATE', (self.attempt / 'RESULT.safe.json').read_text())

    def test_missing_personal_method_does_not_use_other_billing(self):
        result = self.run_auth(self.peer(methods=[{'id': 'gemini-api-key'}]))
        self.assertEqual(result['authenticate_calls'], 0)
        self.assertEqual(self.methods(), ['initialize'])

    def test_timeout_reaps_owned_runtime(self):
        result = self.run_auth(self.peer(pause=True), auth_timeout=.1, total_timeout=.3)
        self.assertEqual(result['error_type'], 'TimeoutError')
        self.assertTrue(result['owned_process_reaped'])
        self.assertEqual(self.methods(), ['initialize', 'authenticate'])

    def test_unexpected_tool_request_fails_without_approval_or_session(self):
        result = self.run_auth(self.peer(client_request=True))
        self.assertFalse(result['session_created'])
        self.assertTrue(result['owned_process_reaped'])
        self.assertEqual(self.methods(), ['initialize', 'authenticate'])

    def test_consumed_attempt_and_hash_change_cannot_launch(self):
        digest = self.peer()
        with self.assertRaises(ValueError):
            self.run_auth('0' * 64)
        self.assertFalse(self.attempt.exists())
        self.attempt.mkdir()
        with self.assertRaises(FileExistsError):
            self.run_auth(digest)
        self.assertFalse((self.attempt / 'methods').exists())


if __name__ == '__main__':
    unittest.main()
