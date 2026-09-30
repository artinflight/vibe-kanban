#!/usr/bin/env python3
"""Local regression checks; no service changes, network calls, or model usage."""
import copy
import importlib.util
import json
from pathlib import Path
import shlex
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('deployment', Path(__file__).with_name('vk-capacity-deployment.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)

class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads(d.PROFILE.read_text())
        self.unit = 'vibe-kanban-next-generation.service'
        self.server = '/mnt/vk-storage/new-release/server'
        self.planned = d.plan(self.profile, self.unit, self.server)
        self.properties = {}
        for name, item in self.planned.items():
            self.properties[name, 'LoadState'] = 'loaded'
            self.properties[name, 'Environment'] = ' '.join(shlex.quote(k+'='+v) for k,v in item['environment'].items())
        cu = self.profile['cuUnit']
        self.properties[self.unit, 'Wants'] = cu
        self.properties[cu, 'PartOf'] = self.unit
        self.properties[cu, 'After'] = self.unit
        self.properties[self.unit, 'ExecStart'] = '{ path='+self.server+' ; argv[]='+self.server+' ; }'

    def check(self):
        with patch.object(d, 'prop', side_effect=lambda unit,key:self.properties.get((unit,key),'')):
            d.check(self.profile,self.unit,self.server,self.planned)

    def test_new_service_and_release_receive_both_settings(self):
        self.check()
        vk = self.planned[self.unit]
        self.assertEqual(vk['environment']['VK_CAPACITY_GUARD'], '/mnt/vk-storage/new-release/vk-capacity-guard')
        self.assertIn('PartOf='+self.unit, self.planned[self.profile['cuUnit']]['text'])
        self.assertNotIn('pr114',str(self.planned))

    def test_systemd_environment_round_trip(self):
        for item in self.planned.values():
            parsed = {}
            for line in item['text'].splitlines():
                if line.startswith('Environment='):
                    for value in shlex.split(line[len('Environment='):]):
                        k,v=value.split('=',1);parsed[k]=v
            self.assertEqual(parsed,item['environment'])

    def test_missing_capacity_configuration_fails(self):
        self.properties[self.unit,'Environment']=''
        with self.assertRaisesRegex(ValueError,'setting'):self.check()

    def test_wrong_guard_fails(self):
        self.properties[self.unit,'Environment']=self.properties[self.unit,'Environment'].replace('new-release/vk-capacity-guard','old-release/vk-capacity-guard')
        with self.assertRaisesRegex(ValueError,'VK_CAPACITY_GUARD'):self.check()

    def test_wrong_cu_backend_fails(self):
        cu=self.profile['cuUnit']
        self.properties[cu,'Environment']=self.properties[cu,'Environment'].replace(':4720',':4511')
        with self.assertRaisesRegex(ValueError,'CU_VK_ORIGIN'):self.check()

    def test_missing_lifecycle_dependency_fails(self):
        self.properties[self.profile['cuUnit'],'PartOf']='old.service'
        with self.assertRaisesRegex(ValueError,'dependency'):self.check()

    def test_wrong_service_executable_fails(self):
        self.properties[self.unit,'ExecStart']='{ path=/old/server ; }'
        with self.assertRaisesRegex(ValueError,'ExecStart'):self.check()

    def test_live_requires_loaded_process_not_just_unit_settings(self):
        with patch.object(d,'prop',side_effect=lambda u,k:'0' if k=='MainPID' else self.properties.get((u,k),'')):
            with self.assertRaisesRegex(ValueError,'not running'):
                d.check(self.profile,self.unit,self.server,self.planned,True)

    def test_injection_and_same_unit_rejected(self):
        for unit in ['../bad.service','x.service\nWants=evil.service',self.profile['cuUnit']]:
            with self.assertRaises(ValueError):d.plan(self.profile,unit,self.server)
        with self.assertRaises(ValueError):d.plan(self.profile,self.unit,'/mnt/%h/server')

    def test_failed_install_restores_both_files_without_restart(self):
        with tempfile.TemporaryDirectory(dir='/mnt/vk-storage/codexusage-capacity/test-readiness') as temporary:
            root=Path(temporary)
            old=root/(self.unit+'.d/capacity.conf')
            old.parent.mkdir();old.write_text('previous configuration')
            with patch.object(d,'prop',side_effect=lambda u,k:self.properties.get((u,k),'0')), \
                 patch.object(d,'check',side_effect=ValueError('rehearsed failure')), \
                 patch.object(d.subprocess,'run') as calls:
                with self.assertRaisesRegex(ValueError,'rehearsed failure'):
                    d.install(self.profile,self.unit,self.server,self.planned,root)
                self.assertEqual(old.read_text(),'previous configuration')
                self.assertFalse((root/(self.profile['cuUnit']+'.d/capacity.conf')).exists())
                self.assertEqual(calls.call_count,2)
                for call in calls.call_args_list:
                    self.assertEqual(call.args[0],['systemctl','--user','daemon-reload'])

    def test_profile_does_not_contain_token_or_auto_enable(self):
        self.assertNotIn('token',set(self.profile))
        self.assertNotIn('enabled',self.profile)
        self.assertEqual(self.planned[self.profile['cuUnit']]['environment']['CU_VK_TOKEN_FILE'],self.profile['tokenFile'])

if __name__ == '__main__':unittest.main()
