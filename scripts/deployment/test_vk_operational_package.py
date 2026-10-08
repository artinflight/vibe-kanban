"""Portable seed fixtures prove next preparation loads fixes rather than stale copies."""
import ast
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from vk_operational_package import install, verify
from vk_operational_package import OLD_INTERLOCK, CURRENT_INTERLOCK

CONTROLLER = '''
def preflight(executing=False):
    assert digest(Path(baseline['folder'])/baseline['archive']) == baseline['receipt']['sha256']
    if executing:
        external.extend(additional)
        current['external']=external
        assert control.prop(CONFIG['candidate'],'LoadState') == 'loaded'
        assert str(ROOT/'production_guard.py')+' '+CONFIG['incumbent_color'] in control.prop(CONFIG['incumbent'],'ExecStartPre'), 'Install prepared reciprocal interlocks after approval'
        assert str(ROOT/'production_guard.py')+' '+CONFIG['candidate_color'] in control.prop(CONFIG['candidate'],'ExecStartPre')
        assert str(ROOT/'release/server') in control.prop(CONFIG['candidate'],'ExecStart')
def execute():
    if True:
        try:
            pass
        except BaseException:
            control.recovery(CONFIG,standby,configure_companion);raise
        # Future boots acquire normally; standby is only for this live handover.
        boot=Path(CONFIG['candidate_active_override'])
        boot.write_text('[Service]\\nEnvironment=VK_CAPACITY_START_PAUSED=0\\n')
        subprocess.run(['systemctl','--user','daemon-reload'],check=True)
        control.ctl('disable',CONFIG['incumbent']);control.ctl('enable',CONFIG['candidate'])
def emergency():
    CONFIG['receipt_directory']=str(folder)
    before=json.loads((folder/'before.json').read_text())
    standby=json.loads((folder/'standby.json').read_text())
    if (json.loads(Path(CONFIG['route']).read_text())['mode']==CONFIG['incumbent_color']
            and control.prop(CONFIG['incumbent'],'MainPID')!='0'
            and control.prop(CONFIG['incumbent'],'FreezerState')=='running'
            and (control.prop(CONFIG['candidate'],'MainPID') in ('','0') or control.prop(CONFIG['candidate'],'FreezerState')=='frozen')
            and control.rpc.request('http://127.0.0.1:'+str(CONFIG['incumbent_port']),Path(CONFIG['capacity_token']))['owned']):
        pass
'''
INSTALLER = '''
def install():
    try:
        for path,data in planned.items():
            path.parent.mkdir(parents=True,exist_ok=True)
            temporary=path.with_suffix(path.suffix+'.new')
            temporary.write_bytes(data);temporary.chmod(0o600);temporary.replace(path)
    except BaseException:
        raise
'''
CONTROLLER_TEST = '''
class ControllerTests:
    def test_original_maintenance_thread_is_preserved(self):
        self.assertEqual(c.continuity.SESSION,'75bc68d4-aa55-4914-a695-f20c46a13e4c')
        self.assertEqual(c.continuity.NATIVE,'01a03e74-2c1a-72f0-9e00-8e4293fe910d')
    def test_changed_staging_blocks_same_main_cutover(self):
        refs=self.config['source_commit']+'\\trefs/heads/main\\n'+'0'*40+'\\trefs/heads/staging\\n'
        with patch.object(c.subprocess,'check_output',return_value=refs):
            with self.assertRaisesRegex(AssertionError,'Staging changed'):c.verify_release_refs()
'''


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=os.environ['TMPDIR'])
        self.root=Path(self.tmp.name)
        self.source=self.root/'protected'
        self.source.mkdir()
        self.recopy=self.source/'new'
        self.recopy.mkdir()
        self.package=self.root/'package'
        self.package.mkdir()
        self.coverage={'recopy_roots':[str(self.recopy)],
            'move_sources':{str(self.recopy/'repo'):str(self.source/'old'/'repo')},
            'journal_identity':{'service':'fixture.service','pid':'123'}}
        (self.package/'backup-plan.json').write_text(json.dumps({'sources':[str(self.source)]}))
        (self.package/'cutover_controller.py').write_text(CONTROLLER)
        (self.package/'install_prepared.py').write_text(INSTALLER)
        (self.package/'test_controller.py').write_text(CONTROLLER_TEST)
        (self.package/'online_backup.py').write_text('import json\nfrom pathlib import Path\nROOT=Path(__file__).resolve().parent\nRECOPY_ROOTS=()\nEXTERNAL_MOVE_SOURCES={}\n')
        (self.package/'build_readiness.py').write_text("from pathlib import Path\nroot=Path(__file__).resolve().parent\nassert 'Ran 77 tests' in (root/'optimized-tool-tests.log').read_text()\n")

    def tearDown(self):self.tmp.cleanup()
    def install(self):return install(self.package,self.coverage,require_clean=False)

    def test_installed_modules_and_gate_are_bound_into_real_preparation(self):
        with (self.package/'build_readiness.py').open('a') as stream:
            stream.write(OLD_INTERLOCK+'\n')
        original_plan=(self.package/'backup-plan.json').read_bytes()
        result=self.install()
        self.assertTrue(result['passed'])
        self.assertEqual((self.package/'backup-plan.json').read_bytes(),original_plan)
        for name in ['cutover_controller.py','build_readiness.py']:
            code=(self.package/name).read_text()
            ast.parse(code)
            self.assertIn('from vk_operational_package import verify',code)
        online={}
        exec(compile((self.package/'online_backup.py').read_text(),str(self.package/'online_backup.py'),'exec'),
             {'__file__':str(self.package/'online_backup.py')},online)
        self.assertEqual(online['RECOPY_ROOTS'],tuple(self.coverage['recopy_roots']))
        self.assertEqual(online['EXTERNAL_MOVE_SOURCES'],self.coverage['move_sources'])
        self.assertIn("assert 'Ran '",(self.package/'build_readiness.py').read_text())
        self.assertIn(CURRENT_INTERLOCK,(self.package/'build_readiness.py').read_text())
        self.assertNotIn(OLD_INTERLOCK,(self.package/'build_readiness.py').read_text())
        code = (self.package/'cutover_controller.py').read_text()
        self.assertIn('Archive(reference(baseline), desktop_only=True).verify()', code)
        self.assertNotIn("digest(Path(baseline['folder'])/baseline['archive'])", code)

    def test_missing_desktop_resolver_prevents_package_verification(self):
        self.install()
        proof = json.loads((self.package/'operational-tools.json').read_text())
        del proof['sha256']['deployment-tools/vk_archive_store.py']
        (self.package/'operational-tools.json').write_text(json.dumps(proof))
        with self.assertRaisesRegex(ValueError, 'Required preparation tool missing'):
            verify(self.package)

    def test_missing_nested_boot_directory_is_created_without_a_restart(self):
        self.install()
        target=self.package/'missing.service.d'/'zz-active-owner.conf'
        controls=Mock()
        namespace={'Path':Path,'CONFIG':{'candidate_active_override':str(target),'incumbent':'old','candidate':'new'},
            'control':controls,'subprocess':Mock()}
        exec((self.package/'cutover_controller.py').read_text(),namespace)
        namespace['execute']()
        self.assertIn('VK_CAPACITY_START_PAUSED=0',target.read_text())
        self.assertEqual(controls.ctl.call_args_list[0].args,('disable','old'))
        self.assertFalse(any(call.args[0] in ('stop','restart','thaw') for call in controls.ctl.call_args_list))

    def test_healthy_owner_does_not_trigger_emergency_cutback(self):
        self.install()
        folder=self.package/'attempt'
        folder.mkdir()
        for name,value in [('before.json',{}),('standby.json',{'pid':'777'}),('preservation-check.json',{'passed':True})]:
            (folder/name).write_text(json.dumps(value))
        (folder/'continuation-submitted.json').touch()
        controls=Mock()
        controls.prop.side_effect=lambda unit,key:'777' if key=='MainPID' else 'frozen'
        thaw=Mock()
        namespace={'Path':Path,'json':json,'folder':folder,'ROOT':self.package,
            'CONFIG':{'candidate_port':9,'incumbent':'old'},'control':controls,
            'routed_owner':lambda:9,'thaw_external':thaw}
        exec((self.package/'cutover_controller.py').read_text(),namespace)
        namespace['emergency']()
        thaw.assert_called_once()
        controls.recovery.assert_not_called()
        controls.ctl.assert_not_called()

    def test_tampered_installed_backup_adapter_blocks_readiness(self):
        self.install()
        (self.package/'journal_compat.py').write_text('stale copied adapter')
        with self.assertRaisesRegex(ValueError,'Operational package changed'):verify(self.package)

    def test_changed_move_configuration_requires_new_package(self):
        self.install()
        coverage=json.loads((self.package/'move-coverage.json').read_text())
        coverage['move_sources']={}
        (self.package/'move-coverage.json').write_text(json.dumps(coverage))
        with self.assertRaises(ValueError):verify(self.package)

    def test_consumed_and_sealed_packages_are_not_modified(self):
        for name in ['cutover-attempt.json','readiness.json','cutover-approval.json']:
            with self.subTest(name=name):
                marker=self.package/name
                marker.write_text('{}')
                with self.assertRaisesRegex(ValueError,'fresh unconsumed'):self.install()
                self.assertEqual((self.package/'cutover_controller.py').read_text(),CONTROLLER)
                marker.unlink()

    def test_unknown_template_is_rejected_before_copying_tools(self):
        (self.package/'cutover_controller.py').write_text('unexpected_template=True\n')
        with self.assertRaises(Exception):self.install()
        self.assertFalse((self.package/'deployment-tools').exists())

    def test_unprotected_move_source_is_rejected_before_template_change(self):
        self.coverage['move_sources']={str(self.recopy/'repo'):'/unprotected/repo'}
        with self.assertRaisesRegex(ValueError,'outside protected scope'):self.install()
        self.assertEqual((self.package/'cutover_controller.py').read_text(),CONTROLLER)

    def test_linked_tool_tree_cannot_bypass_the_bound_package(self):
        self.install()
        tools=self.package/'deployment-tools'
        outside=self.root/'outside-tools'
        tools.rename(outside)
        tools.symlink_to(outside,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'Operational package changed'):verify(self.package)

    def test_module_enabled_package_rejects_missing_published_module(self):
        units=self.package/'prepared-units';units.mkdir()
        (units/'candidate.service').write_text('[Service]\nEnvironment=VK_CODEX_ROUTING_MODULE=/missing/current\n')
        with self.assertRaisesRegex(ValueError,'Publish the candidate routing module'):
            self.install()
        self.assertFalse((self.package/'operational-tools.json').exists())
        self.assertEqual((self.package/'cutover_controller.py').read_text(),CONTROLLER)

    def test_module_enabled_package_rejects_unknown_recovery_template(self):
        units=self.package/'prepared-units';units.mkdir()
        (units/'candidate.service').write_text('[Service]\nEnvironment=VK_CODEX_ROUTING_MODULE=/fixture/current\n')
        (self.package/'autoswitch-module/current').mkdir(parents=True)
        with self.assertRaises(Exception):self.install()
        self.assertFalse((self.package/'operational-tools.json').exists())
        self.assertEqual((self.package/'cutover_controller.py').read_text(),CONTROLLER)


if __name__=='__main__':unittest.main()
