"""Synthetic owned fixtures only; no production Git receipts/fence acceptance."""
from contextlib import contextmanager
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import vk_restart_git_boundary as git
from test_vk_restart_safeguards import Routine
from vk_routine_restart import run


class GitBoundary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir='/mnt/vk-storage', prefix='restart-git-fixture-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.helper = self.root/'helper.py'; self.helper.write_text('# synthetic fixture only\n')
        self.policy = self.root/'policy.json'; self.policy.write_text('{"synthetic":true}')
        self.helper_pin = hashlib.sha256(self.helper.read_bytes()).hexdigest()
        pinned = patch.object(git, 'HELPER_SHA256', self.helper_pin)
        pinned.start(); self.addCleanup(pinned.stop)
        self.owner = {'uid': os.getuid(), 'operation': 'synthetic-fixture'}
        self.ledger = {'version': 2, 'state': 'verified', 'config': git.digest({'synthetic': True}),
                       'repositories': [{'id': 'fixture', 'path': str(self.root)}],
                       'obligations': {'fixture': {'commits': ['a'*40]}}}
        self.binding = {'owner': self.owner, 'turns': [{'workspace': 'fixture', 'turn': 'synthetic',
                            'repositories': [{'id': 'fixture', 'path': str(self.root)}]}],
                        'ledgers': {'fixture/synthetic': self.ledger}}
        self.fenced = False; self.calls = []
        parent = self
        @contextmanager
        def fence(before):
            with (self.root/'writer.lock').open('a+b') as held:
                fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.fenced = True
                class Lease:
                    def assert_held(self, pinned):
                        git.require(parent.fenced and pinned['owner'] == parent.owner, 'fixture owner/fence changed')
                        # A separate open description must actually contend.
                        with (parent.root/'writer.lock').open('rb') as other:
                            with parent.assertRaises(BlockingIOError):fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
                try:yield Lease()
                finally:self.fenced = False
        self.adapter = git.HeldGitCheck(self.helper, self.policy, hashlib.sha256(self.policy.read_bytes()).hexdigest(),
                                       git.digest(self.binding), lambda: copy.deepcopy(self.binding), fence)
        def checked(helper, policy, request, timeout):
            self.assertTrue(self.fenced);self.calls.append(request)
            return 0, json.dumps(self.output()).encode()
        self.checked = checked

    def output(self):
        return {'version': 2, 'state': 'verified', 'scope': 'eligible-repository-work-only',
                'checked_at': time.time(), 'turns': [{'version': 2, 'state': 'verified',
                'workspace': 'fixture', 'turn': 'synthetic', 'receipt_digest': git.digest(self.ledger),
                'repositories': self.ledger['repositories']}]}

    def test_fixed_check_all_inside_real_fixture_lock_through_continuation(self):
        with patch.object(git, 'invoke_check_all', self.checked):
            with self.adapter.held(lambda: 20) as witness:
                self.assertTrue(self.fenced); self.assertEqual(witness['state'], 'verified')
        self.assertFalse(self.fenced);self.assertEqual(self.calls[0]['turns'], self.binding['turns'])

    def test_missing_malformed_pending_nonzero_and_wrong_schema_rejected(self):
        for raw, code in [(b'{}',0),(b'not-json',0),(json.dumps({**self.output(),'state':'pending'}).encode(),0),
                          (json.dumps(self.output()).encode(),2),(json.dumps({**self.output(),'version':1}).encode(),0)]:
            with self.subTest(raw=raw[:30],code=code), patch.object(git,'invoke_check_all',return_value=(code,raw)):
                with self.assertRaises(ValueError):
                    with self.adapter.held(lambda:20):self.fail('continuation reached')

    def test_changed_ledger_inventory_owner_and_unfenced_boolean_rejected(self):
        for key in ('owner','turns','ledgers'):
            old=copy.deepcopy(self.binding)
            self.binding[key] = {} if key!='turns' else []
            with self.assertRaises((ValueError,KeyError)):
                with self.adapter.held(lambda:20):self.fail('continuation reached')
            self.binding=old
        @contextmanager
        def fake_fence(before):yield {'writers_fenced': True}
        self.adapter.writer_fence=fake_fence
        with self.assertRaises(ValueError):
            with self.adapter.held(lambda:20):self.fail('continuation reached')

    def test_changed_original_after_check_and_during_handover_rejected(self):
        def changed(*args):
            value=self.checked(*args);self.binding['ledgers']['fixture/synthetic']['obligations']={};return value
        with patch.object(git,'invoke_check_all',changed),self.assertRaises(ValueError):
            with self.adapter.held(lambda:20):self.fail('continuation reached')
        self.binding['ledgers']['fixture/synthetic']['obligations']={'fixture':{'commits':['a'*40]}}
        with patch.object(git,'invoke_check_all',self.checked),self.assertRaises(ValueError):
            with self.adapter.held(lambda:20):self.binding['owner']['operation']='changed'

    def test_routine_consumes_and_propagates_git_witness(self):
        fixture=Routine();fixture.setUp();fixture.plan['git_activation']=True
        original=fixture.driver.handover
        def handover(plan, package, backup, budget, *, git_boundary):
            self.assertTrue(self.fenced);return {**original(plan,package,backup,budget),'git_boundary':git_boundary}
        fixture.driver.handover=handover
        with patch.object(git,'invoke_check_all',self.checked):
            result=run(fixture.plan,fixture.driver,fix_ready_monotonic=fixture.fix_ready,git_boundary=self.adapter)
        self.assertTrue(result['passed'],result)
        result=run(fixture.plan,fixture.driver,fix_ready_monotonic=fixture.fix_ready)
        self.assertFalse(result['passed']);self.assertFalse(result['production_action_attempted'])

    def test_fixed_transport_bounds_only_exact_fixture_child(self):
        self.helper.write_text('import json,sys\njson.load(sys.stdin)\nprint("x"*1000)\n')
        with patch.object(git,'MAX_JSON',100),self.assertRaises(ValueError):
            git.invoke_check_all(self.helper,self.policy,{'turns':[]},2)


if __name__ == '__main__':unittest.main()
