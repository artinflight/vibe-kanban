import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import online_owner as owner


class OwnerTests(unittest.TestCase):
    def test_resource_wait_preserves_floors_and_rechecks_owner(self):
        live=owner.LiveReaders.__new__(owner.LiveReaders)
        live.resource_wait=600
        healthy=dict(ssd_available_bytes=8*1024**3,memory_available_bytes=8*1024**3,memory_full_avg10=0)
        for failed in (dict(healthy,ssd_available_bytes=2*1024**3),
                       dict(healthy,memory_available_bytes=3*1024**3),
                       dict(healthy,memory_full_avg10=.11)):
            with patch.object(owner,'resource_observation',side_effect=[failed,healthy]), patch.object(live,'check_identities') as identity, patch.object(owner.time,'sleep') as sleep, patch('builtins.print'):
                live.check()
                self.assertEqual(identity.call_count,2)
                sleep.assert_called_once()

    def test_wait_never_hides_changed_reader_or_mount(self):
        live=owner.LiveReaders.__new__(owner.LiveReaders);live.resource_wait=600
        failed=dict(ssd_available_bytes=0,memory_available_bytes=0,memory_full_avg10=1)
        with patch.object(owner,'resource_observation',return_value=failed), patch.object(live,'check_identities',side_effect=ValueError('reader changed')), patch.object(owner.time,'sleep') as sleep:
            with self.assertRaisesRegex(ValueError,'reader changed'):live.check()
            sleep.assert_not_called()
        with patch.object(owner,'resource_observation',side_effect=ValueError('mount missing')), patch.object(owner.time,'sleep') as sleep:
            with self.assertRaisesRegex(ValueError,'mount missing'):live.check()
            sleep.assert_not_called()

    def test_resource_timeout_keeps_exact_observation(self):
        live=owner.LiveReaders.__new__(owner.LiveReaders);live.resource_wait=600
        failed=dict(ssd_available_bytes=123,memory_available_bytes=456,memory_full_avg10=.11)
        with patch.object(owner,'resource_observation',return_value=failed), patch.object(live,'check_identities'), patch.object(owner.time,'monotonic',side_effect=[0,600]), patch.object(owner.time,'sleep') as sleep:
            with self.assertRaises(owner.ResourceAdmissionError) as error:live.check()
            self.assertEqual(error.exception.observation,failed)
            sleep.assert_not_called()

    def test_kernel_readonly_mount_is_required_including_nested_overrides(self):
        inside='/reader/sessions'
        readonly='1 0 0:1 / / rw - tmpfs tmpfs rw\n2 1 0:2 / /reader/sessions ro - ext4 disk rw\n'
        with patch.object(Path,'read_text',return_value=readonly):owner.readonly_mount(123,inside)
        with patch.object(Path,'read_text',return_value=readonly.replace('/reader/sessions ro','/reader/sessions rw')):
            with self.assertRaisesRegex(ValueError,'writable log mount'):owner.readonly_mount(123,inside)
        with patch.object(Path,'read_text',return_value=readonly+'3 2 0:3 / /reader/sessions/ab rw - ext4 disk rw\n'):
            with self.assertRaisesRegex(ValueError,'nested writable'):owner.readonly_mount(123,inside)

    def test_space_escaped_mount_paths_are_checked_as_actual_paths(self):
        value='1 0 0:1 / / rw - tmpfs tmpfs rw\n2 1 0:2 / /reader/with\\040space ro - ext4 disk rw\n'
        with patch.object(Path,'read_text',return_value=value):owner.readonly_mount(123,'/reader/with space/sessions')

    def test_selected_settings_cannot_be_omitted_to_bypass_owner_guard(self):
        with self.assertRaisesRegex(ValueError,'cleanup protection'):
            owner.LiveReaders({'readers':{'main':{'required_environment':{}},'protected5650':{}}},'/sessions')

    def test_source_pin_refuses_modified_bytes_and_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'owner.json';p.write_text('{"accepted":false}');p.chmod(0o600)
            ref=dict(path=str(p),sha256=owner.logs.sha(p.read_bytes()))
            self.assertEqual(json.loads(owner.pinned(ref)),{'accepted':False})
            p.write_text('{"accepted":true}')
            with self.assertRaisesRegex(ValueError,'changed'):owner.pinned(ref)
            alias=p.with_suffix('.alias');alias.symlink_to(p)
            with self.assertRaises(ValueError):owner.pinned(dict(ref,path=str(alias)))

    def test_protocol_process_outside_real_service_cannot_impersonate_writer(self):
        live=owner.LiveReaders.__new__(owner.LiveReaders)
        live.source=Path('/not-accessed')
        live.identities={'main':('birth','inode')}
        live.config={'readers':{'main':dict(unit=owner.UNITS['main'],server_pid=100,
            main_pid=100,invocation='current')}}
        state=dict(ActiveState='active',FreezerState='running',MainPID='100',
                   InvocationID='current',ControlGroup='/real-service')
        def contents(path,*args,**kwargs):
            if str(path)=='/proc/meminfo':return 'MemAvailable: 8388608 kB\n'
            if str(path)=='/proc/pressure/memory':return 'full avg10=0 avg60=0 avg300=0 total=0\n'
            if str(path)=='/proc/100/cgroup':return '0::/unrelated-helper\n'
            self.fail('Unexpected read '+str(path))
        with patch.object(owner,'unit',return_value=state), patch.object(owner,'process_identity',return_value=('birth','inode')), \
                patch.object(owner.os.path,'ismount',return_value=True), \
                patch.object(owner.os,'statvfs',return_value=SimpleNamespace(f_bavail=8*1024**3,f_frsize=1)), \
                patch.object(Path,'read_text',contents):
            with self.assertRaisesRegex(ValueError,'outside its actual serving unit'):live.check()

    def test_foreign_plan_is_refused_before_live_or_backup_actions(self):
        with patch.object(owner,'LiveReaders',side_effect=AssertionError('live access attempted')):
            with self.assertRaisesRegex(ValueError,'configuration'):
                with owner.admit_online(dict(format='vk-scoped-online-owner-v1',plan_sha256='0'*64,reserve_bytes=3*1024**3),{}):pass


if __name__=='__main__':unittest.main()
