import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import vk_nightly_service as service
from vk_typed_recovery import checksum


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir='/dev/shm');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.ref=dict(unit='vk-nightly-test.service',owner_pid=123,owner_start_ticks=456,
            config=str(self.root/'controller'),result=str(self.root/'result'),result_binding=dict(phase='complete'))

    def saved(self,name,value):
        p=self.root/name;raw=json.dumps(value).encode();p.write_bytes(raw);p.chmod(0o600)
        return str(p),hashlib.sha256(raw).hexdigest()

    def test_only_exact_successful_terminal_invocation_can_be_adopted(self):
        def show(**changes):
            value=dict(MainPID='0',ActiveState='inactive',ExecMainStatus='0',ControlGroup='',
                       ExecMainPID='123',ExecMainStartTimestampMonotonic='4560000')
            value.update(changes);return '\n'.join(k+'='+v for k,v in value.items())
        self.assertTrue(service.terminal(self.ref,inspect=lambda *a,**k:show()))
        self.assertFalse(service.terminal(self.ref,inspect=lambda *a,**k:show(MainPID='123',ActiveState='active')))
        for changes in [dict(MainPID='124',ActiveState='active'),dict(ActiveState='failed'),
                        dict(ExecMainStatus='1'),dict(ControlGroup='/still-populated'),
                        dict(ExecMainPID='124'),dict(ExecMainStartTimestampMonotonic='5550000')]:
            with self.assertRaises(ValueError):service.terminal(self.ref,inspect=lambda *a,**k:show(**changes))
        with self.assertRaises(subprocess.TimeoutExpired):
            service.terminal(self.ref,inspect=lambda *a,**k:(_ for _ in ()).throw(subprocess.TimeoutExpired('same unit',15)))
        collected=lambda *a,**k:show(LoadState='not-found',ExecMainPID='0',ExecMainStartTimestampMonotonic='0')
        self.assertFalse(service.terminal(self.ref,inspect=collected,process_check=lambda _:True))
        # This only establishes former process absence. Native result/leases
        # remain independently mandatory in execute/reopen_component.
        self.assertTrue(service.terminal(self.ref,inspect=collected,process_check=lambda _:False))

    def test_CLI_wrong_digest_refuses_without_source_or_B_work(self):
        path,_=self.saved('wrong-config',{'format':'vk-nightly-current-service-v1'})
        before=set(self.root.iterdir())
        result=subprocess.run([sys.executable,'-B',str(Path(service.__file__)),'--config',path,
            '--config-sha256','0'*64,'--preflight'],capture_output=True,text=True,timeout=10)
        self.assertNotEqual(result.returncode,0);self.assertIn('binding differs',result.stderr)
        self.assertEqual(set(self.root.iterdir()),before)

    def test_scheduled_cohort_is_deterministic_per_evening_with_new_next_day_and_DST_end(self):
        template=dict(cycle=dict(cycle_binding=dict(cycle_kind='incremental'),
            SQL=dict(SQL_phase_index=dict(index_name='template',checkpoint_sha256='3'*64)),finalize={}))
        first=service.scheduled_cycle(template,'2026-10-27','4'*64)
        self.assertEqual(first,service.scheduled_cycle(template,'2026-10-27','4'*64))
        cycle=first['cycle'];binding=cycle['cycle_binding']
        self.assertEqual(binding['deadline_UTC'],'2026-10-28T08:00:00+00:00')
        self.assertEqual(binding['started_UTC'],'2026-10-28T02:00:00+00:00')
        self.assertEqual(cycle['SQL']['SQL_phase_index'],cycle['finalize']['SQL_phase'])
        self.assertEqual(cycle['SQL']['cohort_tag'],binding['SQL_cohort_tag'])
        from vk_nightly_b_controls import name as index_name
        self.assertEqual(index_name(cycle['SQL']['SQL_phase_index']['index_name']),
                         cycle['SQL']['SQL_phase_index']['index_name'])
        later=service.scheduled_cycle(template,'2026-10-28','4'*64)
        self.assertNotEqual(later['cycle']['SQL']['cohort_tag'],cycle['SQL']['cohort_tag'])
        self.assertEqual(template['cycle']['SQL']['SQL_phase_index']['index_name'],'template')
        bad=dict(template,existing_components={'files':{}})
        with self.assertRaises(ValueError):service.scheduled_cycle(bad,'2026-10-27','4'*64)

    def test_adopted_components_cannot_be_relabelled_as_an_ordinary_timed_cycle(self):
        from vk_nightly_current_cycle import run
        workers={name:dict(B_controls={},B_index_name='current',B_checkpoint_sha256='1'*64) for name in service.PROOF}
        owner=dict(config='fixture',sha256='2'*64,instance='one')
        settings=dict(cycle_binding=dict(deadline_UTC='2099-01-01T00:00:00+00:00',cycle_kind='incremental',
            SQL_cohort_tag='one',SQL_phase_index={'index_name':'SQL','checkpoint_sha256':'3'*64}),
            files=dict(source_observer=owner),SQL=dict(source_observer=owner,cohort_tag='one',
            SQL_phase_index={'index_name':'SQL','checkpoint_sha256':'3'*64}),runtime=dict(source_observer=owner),
            finalize=dict(current_map=dict(index_name='current',checkpoint_sha256='1'*64)))
        with patch('vk_nightly_current_cycle.file_cycle') as capture:
            with self.assertRaisesRegex(ValueError,'masquerade'):
                run(settings,workers,None,consumer=None,guard=lambda:None,
                    completed_components={name:{} for name in service.PROOF})
            capture.assert_not_called()


if __name__=='__main__':unittest.main()
