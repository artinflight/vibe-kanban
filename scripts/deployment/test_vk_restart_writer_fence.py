"""Physical guard regression on private RAM fixtures; never freezes services."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from vk_restart_writer_fence import WriterFence


class Fence(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir='/dev/shm');self.root=Path(self.temp.name)
        self.db=self.root/'db';self.db.write_text('fixture')
        self.lock=self.root/'controller.lock';self.lock.touch(mode=0o600)
        self.state=dict(version=2,epoch='fixture',revision=7,goals={});(self.root/'state.json').write_text(json.dumps(self.state))
        (self.root/'route').write_text('maintenance')
        self.before=dict(complete=True,active=[],durable_queue=[],incoming_pending=[],database_identity=[self.db.stat().st_dev,self.db.stat().st_ino],fingerprint='fixture')
        self.binding=dict(capacity_persisted_version=2,database=str(self.db),database_target=str(self.db),capacity_lock=str(self.lock),capacity_state=str(self.root/'state.json'),route_path=str(self.root/'route'),maintenance_bytes='maintenance',frozen_units={'backend':dict(pid=123,invocation='birth'),'poller':dict(pid=456,invocation='pollbirth')},stopped_units=['connector','publisher'])
        self.units={'backend':dict(MainPID='123',InvocationID='birth',ControlGroup='/user.slice/backend',ActiveState='active',FreezerState='frozen'),'poller':dict(MainPID='456',InvocationID='pollbirth',ControlGroup='/user.slice/poller',ActiveState='active',FreezerState='frozen')}
        for name in ['connector','publisher']:self.units[name]=dict(MainPID='0',ActiveState='inactive',ControlGroup='')
        self.processes={'/user.slice/backend':{123},'/user.slice/poller':{456}}
        self.fence=WriterFence(self.binding,self.before,dict(protocolVersion=1,owned=False,state=dict(self.state,version=1)),inspect=lambda name:self.units[name],processes=lambda group:self.processes[group])
    def tearDown(self):self.temp.cleanup()
    def test_requires_held_lease_not_boolean(self):
        with self.assertRaisesRegex(ValueError,'retained capacity lease'):self.fence.check()
    def test_live_writer_or_descendant_blocks_before_lease(self):
        for change in ['running','child','ingress']:
            with self.subTest(change=change):
                if change=='running':self.units['backend']['FreezerState']='running'
                elif change=='child':self.units['backend']['FreezerState']='frozen';self.processes['/user.slice/backend'].add(999)
                else:self.processes['/user.slice/backend']={123};self.units['connector']['ActiveState']='active'
                with self.assertRaises(ValueError):
                    with self.fence.held():self.fail('Live writer admitted')
                self.assertIsNone(self.fence.fd)
    def test_owned_ingress_start_hold_is_continuously_required(self):
        import hashlib
        path=self.root/'hold.conf';raw=b'[Unit]\nRefuseManualStart=yes\n';path.write_bytes(raw);path.chmod(0o600)
        self.binding['stopped_unit_start_holds']=[dict(unit='connector',path=str(path),sha256=hashlib.sha256(raw).hexdigest())]
        self.units['connector']['RefuseManualStart']='yes';self.fence.controls()
        self.units['connector']['RefuseManualStart']='no'
        with self.assertRaises(ValueError):self.fence.controls()
        self.units['connector']['RefuseManualStart']='yes';path.write_text('unknown owner')
        with self.assertRaises(ValueError):self.fence.controls()

    def test_existing_owner_refuses_without_taking_lease(self):
        with self.lock.open('rb') as owner:
            fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                with self.fence.held():pass
    def test_real_lease_blocks_competitor_then_releases_on_error(self):
        with patch('vk_restart_writer_fence.frozen',return_value=self.before):
            with self.assertRaisesRegex(RuntimeError,'owned abort'):
                with self.fence.held() as check:
                    check()
                    with self.lock.open('rb') as other:
                        with self.assertRaises(BlockingIOError):fcntl.flock(other,fcntl.LOCK_EX|fcntl.LOCK_NB)
                    raise RuntimeError('owned abort')
        with self.lock.open('rb') as other:fcntl.flock(other,fcntl.LOCK_EX|fcntl.LOCK_NB)
    def test_changed_state_route_or_database_refuses(self):
        for target,value in [(self.root/'state.json','{}'),(self.root/'route','blue')]:
            original=target.read_bytes();target.write_text(value)
            with self.assertRaises(ValueError):self.fence.controls()
            target.write_bytes(original)
        other=self.root/'other';other.write_text('replacement');other.replace(self.db)
        with self.assertRaises(ValueError):self.fence.controls()
    def test_unknown_durable_version_or_changed_initialization_data_refuses(self):
        for value in [dict(self.state,version=3),dict(self.state,goals={'new':{'initializationReceipt':'preserve'}})]:
            (self.root/'state.json').write_text(json.dumps(value))
            with self.assertRaises(ValueError):self.fence.controls()
        self.assertEqual(json.loads((self.root/'state.json').read_text()),value)
    def test_pending_input_changes_are_not_erased_or_acknowledged(self):
        with patch('vk_restart_writer_fence.frozen',side_effect=ValueError('new received input')):
            with self.assertRaisesRegex(ValueError,'new received input'):
                with self.fence.held():pass
        self.assertEqual(self.state,json.loads((self.root/'state.json').read_bytes()))

if __name__=='__main__':unittest.main()
