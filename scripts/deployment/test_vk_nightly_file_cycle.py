import hashlib
import errno
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import vk_nightly_file_cycle as cycle
from vk_change_journal import scope
from vk_prep_common import identity


class FileCycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir='/dev/shm');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.plan={'sources':[str(self.root/'source')]}
        def write(name,value):
            path=self.root/name;path.write_text(json.dumps(value));path.chmod(0o600)
            return str(path),hashlib.sha256(path.read_bytes()).hexdigest()
        self.write=write;plan,sha=write('plan',self.plan)
        self.health=dict(ready=True,raw_errors=[],coverage_model='all-selected-inodes-v1',instance='source-epoch',
            plan_sha256=identity(self.plan),scope_sha256=identity(scope(self.plan)),
            required_root_bindings={self.plan['sources'][0]:{}},heartbeat_utc=time.time(),
            owner_pid=os.getpid(),owner_start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]))
        status,_=write('status',self.health)
        config=dict(plan=plan,plan_sha256=sha,status=status,endpoint=str(self.root/'socket'),
            B_delivery_target=dict(B_root='B:/vk-backups/test/controls-v1'))
        path,sha=write('config',config)
        self.source=cycle.Source(dict(config=path,sha256=sha,instance='source-epoch'),
            {'B_root':'B:/vk-backups/test/controls-v1'},guard=lambda:None)

    def test_actual_current_process_owner_and_exact_source_bindings(self):
        self.assertEqual(self.source.check()['owner_pid'],os.getpid())
        for changes in [dict(ready=False),dict(raw_errors=[{'gap':'overflow'}]),dict(instance='old'),
                        dict(heartbeat_utc=time.time()-100),dict(owner_start_ticks=1),
                        dict(plan_sha256='a'*64),dict(scope_sha256='b'*64),dict(required_root_bindings={})]:
            self.write('status',dict(self.health,**changes))
            with self.subTest(changes=changes),self.assertRaises(ValueError):self.source.check()

    def test_owned_control_rejects_collision_permissions_and_hash_mismatch(self):
        path,sha=self.write('control',{'exact':True})
        self.assertEqual(cycle.read_owned(path,sha),{'exact':True})
        with self.assertRaisesRegex(ValueError,'binding'):cycle.read_owned(path,'0'*64)
        Path(path).chmod(0o666)
        with self.assertRaisesRegex(ValueError,'owned'):cycle.read_owned(path,sha)
        link=self.root/'link';link.symlink_to(path)
        with self.assertRaisesRegex(ValueError,'canonical'):cycle.read_owned(link,sha)

    def test_existing_group_writable_plan_requires_full_digest_without_permission_change(self):
        plan=Path(self.source.config['plan']);plan.chmod(0o664)
        self.assertEqual(cycle.read_owned(plan,self.source.config['plan_sha256'],pinned_group_data=True),self.plan)
        self.assertEqual(plan.stat().st_mode&0o777,0o664)
        with self.assertRaisesRegex(ValueError,'owned'):cycle.read_owned(plan,self.source.config['plan_sha256'])
        with self.assertRaisesRegex(ValueError,'binding'):cycle.read_owned(plan,'0'*64,pinned_group_data=True)
        with self.assertRaisesRegex(ValueError,'digest'):cycle.read_owned(plan,pinned_group_data=True)
        self.assertTrue(self.source.check()['ready'])

    def test_optional_low_SSD_mirror_never_becomes_payload_fallback_or_access_bypass(self):
        with patch.object(cycle,'health_mirror',side_effect=OSError(errno.ENOSPC,'fixture SSD full')),patch.object(cycle.sys,'stderr'):
            cycle.optional_report(self.root/'optional-cache',{'phase':'B work remains durable'})
        self.assertFalse((self.root/'optional-cache').exists())
        with patch.object(cycle,'health_mirror',side_effect=PermissionError(errno.EACCES,'fixture denied')):
            with self.assertRaises(PermissionError):cycle.optional_report(self.root/'status',{'phase':'denied'})

    def test_predecessor_is_only_observed_and_exact_terminal_receipt_required(self):
        result,_=self.write('result',dict(actual_independent_normal_B_composition_reopen_verified=True,
            source_instance='source-epoch',namespace_core_identity='a'*64))
        reference=dict(unit='vk-nightly-existing-metadata.service',result=result,result_binding={'namespace_core_identity':'a'*64})
        states=['MainPID=123\nExecMainStatus=0\nActiveState=active\n','MainPID=0\nExecMainStatus=0\nActiveState=inactive\n']
        reports=[]
        with patch.object(cycle.subprocess,'check_output',side_effect=states) as commands:
            got=cycle.predecessor(reference,self.source,maximum_seconds=60,report=reports.append,sleep=lambda _:None)
        self.assertEqual(got['source_instance'],'source-epoch');self.assertEqual(len(reports),1)
        for call in commands.call_args_list:self.assertEqual(call.args[0][:3],['systemctl','--user','show'])
        with patch.object(cycle.subprocess,'check_output',return_value='MainPID=0\nExecMainStatus=1\nActiveState=failed\n'):
            with self.assertRaisesRegex(ValueError,'not complete successfully'):
                cycle.predecessor(reference,self.source,maximum_seconds=60,report=reports.append)
        self.write('result',dict(actual_independent_normal_B_composition_reopen_verified=True,source_instance='other'))
        with patch.object(cycle.subprocess,'check_output',return_value=states[1]):
            with self.assertRaisesRegex(ValueError,'result differs'):
                cycle.predecessor(reference,self.source,maximum_seconds=60,report=reports.append)

    def test_failed_predecessor_never_delivers_or_captures(self):
        config=dict(source_observer=self.source.reference,metadata_predecessor={},maximum_predecessor_seconds=1)
        config['metadata_predecessor']={'unit':'vk-nightly-failed.service'}
        with patch.object(cycle,'host_guard'),patch.object(cycle,'predecessor',side_effect=ValueError('failed retained metadata')),\
             patch.object(cycle.Source,'deliver') as deliver,patch.object(cycle,'run_B') as capture:
            with self.assertRaisesRegex(ValueError,'failed retained metadata'):
                cycle.run(config,dict(B_controls=self.source.controls),report=lambda _:None)
            deliver.assert_not_called();capture.assert_not_called()

    def test_serial_SQL_followthrough_requires_actual_file_receipt_and_fixed_marker(self):
        result,_=self.write('file-result',dict(actual_independent_B_file_cycle_receipt_reopen_verified=True,
            final_B_delivery={'instance':'source-epoch'},phase='finite-current-file-cycle-complete'))
        reference=dict(unit='vk-nightly-existing-files.service',result=result,
            verification_field='actual_independent_B_file_cycle_receipt_reopen_verified',
            result_binding={'phase':'finite-current-file-cycle-complete'})
        with patch.object(cycle.subprocess,'check_output',return_value='MainPID=0\nExecMainStatus=0\nActiveState=inactive\n'):
            value=cycle.predecessor(reference,self.source,maximum_seconds=60,report=lambda _:None)
            self.assertEqual(value['phase'],'finite-current-file-cycle-complete')
        with patch.object(cycle.subprocess,'check_output') as commands:
            with self.assertRaisesRegex(ValueError,'fixed independent'):
                cycle.predecessor(dict(reference,verification_field='any_boolean'),self.source,maximum_seconds=60,report=lambda _:None)
            commands.assert_not_called()

    def test_observation_timeout_repolls_same_predecessor_and_never_proves_failure(self):
        result,_=self.write('result',dict(actual_independent_normal_B_composition_reopen_verified=True,
            source_instance='source-epoch'))
        reference=dict(unit='vk-nightly-existing-metadata.service',result=result,result_binding={})
        answers=[cycle.subprocess.TimeoutExpired('systemctl',15),
                 'MainPID=123\nExecMainStatus=0\nActiveState=deactivating\n',
                 'MainPID=0\nExecMainStatus=0\nActiveState=inactive\n']
        reports=[]
        with patch.object(cycle.subprocess,'check_output',side_effect=answers) as commands:
            value=cycle.predecessor(reference,self.source,maximum_seconds=60,report=reports.append,sleep=lambda _:None)
        self.assertEqual(value['source_instance'],'source-epoch');self.assertEqual(commands.call_count,3)
        self.assertFalse(reports[0]['producer_terminal_proven'])
        self.assertEqual([c.args[0][3] for c in commands.call_args_list],[reference['unit']]*3)


if __name__=='__main__':unittest.main()
