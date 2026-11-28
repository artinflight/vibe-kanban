import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import upgrade_controlled_worker as upgrade
import checkpoint_control as cc


class UpgradeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.old=self.root/'old';self.old.mkdir(mode=0o700)
        cc.atomic(self.old/'CONTROLLER_SEAL.private.json',{'operation':'a'*32})
        self.process=cc.process_identity(os.getpid())
        self.expected={'MainPID':str(os.getpid()),'ControlGroup':'fixture','ActiveState':'active','InvocationID':'x'}
        self.cp={'checkpoint_sha256':'b'*64}
        self.value={'worker_identity_live':True,'observation_age_seconds':1,'command':{'action':'pause'},
                    'worker':{'state':'paused','process':self.process,'checkpoint':self.cp}}

    def run_check(self):
        with patch.object(upgrade,'unit',return_value=self.expected), \
             patch.object(cc.Controls,'status',return_value=self.value), \
             patch.object(upgrade,'checkpoint',return_value=self.cp), \
             patch.object(Path,'read_text',return_value=str(os.getpid())), \
             patch.object(upgrade,'assert_leases_closed') as leases:
            # Avoid mocking the normal file reader through Path.read_text;
            # checkpoint_control.read uses a real O_NOFOLLOW descriptor.
            result=upgrade.paused_owner(self.root,self.old,self.expected,[],None)
            leases.assert_called_once_with([],[os.getpid()])
            return result

    def test_exact_live_pause_and_checkpoint_are_required(self):
        self.assertEqual(self.run_check()[1],self.cp)
        for key,value in [('worker_identity_live',False),('observation_age_seconds',60)]:
            old=self.value[key];self.value[key]=value
            with self.assertRaises(ValueError):self.run_check()
            self.value[key]=old
        self.value['worker']['state']='running'
        with self.assertRaisesRegex(ValueError,'acknowledged'):self.run_check()

    def test_resumed_command_or_changed_prefix_is_refused(self):
        self.value['command']['action']='resume'
        with self.assertRaises(ValueError):self.run_check()
        self.value['command']['action']='pause';self.value['worker']['checkpoint']={'checkpoint_sha256':'c'*64}
        with self.assertRaisesRegex(ValueError,'checkpoint'):self.run_check()

    def test_backend_unit_can_never_be_stopped_by_this_upgrade(self):
        p=self.root/'prep.json';cc.atomic(p,{'sources':[],'unit':'vibe-kanban-native-review-20261015.service','authorization_ref':'fixture'})
        with patch.object(upgrade.subprocess,'run',side_effect=AssertionError('service action attempted')):
            with self.assertRaisesRegex(ValueError,'exact finite unit'):upgrade.activate(p)


if __name__=='__main__':unittest.main()
