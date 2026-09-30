#!/usr/bin/env python3
"""Ownership client validation without production RPCs."""
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

spec=importlib.util.spec_from_file_location('ownership',Path(__file__).with_name('vk-capacity-ownership.py'))
client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)

class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(os.path.ismount('/mnt/vk-storage'))
        self.temporary=tempfile.TemporaryDirectory(prefix='ownership-client-',dir='/mnt/vk-storage')
        self.addCleanup(self.temporary.cleanup)
        self.token=Path(self.temporary.name)/'token'
        self.token.write_text('fixture-token-'*4)
        self.token.chmod(0o600)

    def test_mutation_requires_explicit_generation(self):
        for receipt in [None,{}, {'epoch':'a','revision':True},{'epoch':'a','revision':-1}]:
            with self.assertRaises(ValueError):client.request('http://127.0.0.1:5000',self.token,'acquire',receipt)

    def test_public_origin_and_symlink_or_public_token_rejected(self):
        with self.assertRaises(ValueError):client.request('https://example.com',self.token)
        self.token.chmod(0o644)
        with self.assertRaises(ValueError):client.request('http://localhost:5000',self.token)
        self.token.chmod(0o600)
        link=self.token.with_name('link');link.symlink_to(self.token)
        with self.assertRaises(ValueError):client.request('http://localhost:5000',link)

    def test_release_sends_exact_receipt_not_other_state(self):
        response=io.BytesIO(json.dumps({'protocolVersion':1,'owned':False,'state':{}}).encode())
        with patch.object(client.urllib.request,'urlopen',return_value=response) as request:
            client.request('http://127.0.0.1:5000',self.token,'release',{'epoch':'generation','revision':7,'goals':{}})
        req=request.call_args.args[0]
        self.assertEqual(req.get_method(),'POST')
        self.assertEqual(json.loads(req.data),{'epoch':'generation','revision':7})
        self.assertTrue(req.full_url.endswith('/api/capacity/ownership/release'))

    def test_legacy_backend_rejected_before_pause(self):
        error=urllib.error.HTTPError('http://localhost',404,'missing',{},None)
        with patch.object(client.urllib.request,'urlopen',side_effect=error):
            with self.assertRaisesRegex(ValueError,'lacks ownership'):
                client.request('http://localhost:5000',self.token)

    def test_unknown_protocol_rejected(self):
        with patch.object(client.urllib.request,'urlopen',return_value=io.BytesIO(b'{"protocolVersion":2}')):
            with self.assertRaisesRegex(ValueError,'Unsupported'):
                client.request('http://localhost:5000',self.token)

if __name__=='__main__':unittest.main()
