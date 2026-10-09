"""Disposable unprivileged installer models: never real root/sudo/config writes."""
import copy
from contextlib import redirect_stdout
import io
import hashlib
import importlib.util
import json
import os
import subprocess
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

SECURITY = Path(__file__).parent / 'security'
def load(name):
    spec = importlib.util.spec_from_file_location(name, SECURITY / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

install = load('vk_inspection_installer')
builder = load('build_inspection_installer')
BINARIES = [Path('/mnt/vk-storage/vk-retirement-preflight-tests') / name for name in
            ('vk-process-inspect-v1.proposal', 'vk-historical-archive-inspect-v1.proposal')]


class MockHost(install.Host):
    def __init__(self, root):
        super().__init__(root, os.getuid(), os.getgid(), os.getuid(), os.getgid())
        self.events, self.fail_at, self.after_publish = [], None, None
    def platform(self, plan):
        self.events.append(('platform',))  # UUID/namespace/OS/admin checks MODEL ONLY
    def run(self, *argv):
        self.events.append(argv)
        if self.fail_at and self.fail_at(argv):
            raise ValueError('modeled visudo failure')
    def publish_grant(self, path):
        self.events.append(('publish',))
        super().publish_grant(path)
        if self.after_publish:
            self.after_publish()


class InstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code = builder.build((SECURITY / 'vk_inspection_installer.py').read_text(), BINARIES)
        namespace = {'__name__': 'pinned_fixture_installer'}
        exec(compile(cls.code, '<verified fixture package>', 'exec'), namespace)
        cls.payload = namespace['PAYLOAD']

    def setUp(self):
        quiet = redirect_stdout(io.StringIO())
        quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)
        self.assertNotEqual(os.geteuid(), 0, 'fixtures must stay unprivileged')
        self.assertTrue(os.path.ismount('/mnt/vk-storage'))
        self.base = Path(tempfile.mkdtemp(prefix='installer-', dir='/mnt/vk-storage/vk-retirement-preflight-tests'))
        self.base.chmod(0o755)
        for path in ('etc/sudoers.d', 'usr/local/sbin', 'mnt/vk-storage'):
            (self.base / path).mkdir(parents=True)
        for directory in self.base.rglob('*'):
            if directory.is_dir(): directory.chmod(0o755)
        # Deliberately writable SSD parent; immutable check must not apply here.
        (self.base / 'mnt/vk-storage').chmod(0o777)
        (self.base / 'etc/sudoers').write_bytes(b'# existing unrelated sudo policy\n')
        self.host = MockHost(self.base)
        self.actor = install.Installer(self.host, copy.deepcopy(self.payload))
        self.metadata = patch.object(self.actor, 'historical_metadata', side_effect=lambda: self.host.events.append(('historical-metadata-model',)))
        self.metadata.start()
        self.addCleanup(self.metadata.stop)

    def path(self, absolute):
        return self.base / absolute.lstrip('/')

    def test_dry_run_has_no_writes_and_allows_writable_SSD_parent(self):
        before = sorted(str(p) for p in self.base.rglob('*'))
        self.assertTrue(self.actor.preflight()['preflight_passed'])
        self.assertEqual(before, sorted(str(p) for p in self.base.rglob('*')))
        self.assertEqual(self.path('/mnt/vk-storage').stat().st_mode & 0o777, 0o777)

    def test_exact_install_fresh_inode_grant_last_after_full_prospective_validation(self):
        result = self.actor.install()
        inode = self.path(install.ANCHOR).stat().st_ino
        for entry in self.actor.plan['files']:
            raw = self.path(entry['destination']).read_bytes()
            self.assertEqual(raw, self.actor.enrolled(entry, inode))
            self.assertEqual(self.path(entry['destination']).stat().st_mode & 0o7777, int(entry['mode'], 8))
        publish = self.host.events.index(('publish',))
        prior = self.host.events[:publish]
        self.assertTrue(any(row[:2] == ('/usr/sbin/visudo', '-c') for row in prior))
        self.assertTrue(any(row[1:2] == ('-cf',) and row[-1].endswith('.validation') for row in prior))
        self.assertFalse(result['adoption_enabled'])
        self.assertFalse(result['action_authorized'])
        self.assertTrue(self.path(install.EVIDENCE).exists())
        self.assertEqual(self.path('/mnt/vk-storage').stat().st_mode & 0o777, 0o777)
        self.assertEqual(self.path('/etc/sudoers').read_bytes(), b'# existing unrelated sudo policy\n')

    def test_real_unprivileged_visudo_parses_full_prospective_fixture(self):
        self.actor.install()
        wrapper = next(self.path('/etc/sudoers.d').glob('*.validation'))
        staged = wrapper.with_name(wrapper.name.removesuffix('.validation'))
        # Successful publication removes the inactive stage; recreate its exact
        # bytes ONLY in the disposable fixture, as another parser input.
        staged.write_bytes(self.path(install.GRANT).read_bytes())
        self.path('/etc/sudoers').write_text('@includedir ' + str(self.base / 'etc/sudoers.d') + '\n')
        self.path('/etc/sudoers.d/.ignored-malformed').write_text('INVALID SUDOERS CONTENT\n')
        rewritten = wrapper.read_text().replace('/etc/', str(self.base / 'etc') + '/')
        checked = self.base / 'prospective-parser-fixture'
        checked.write_text(rewritten)
        subprocess.run(['/usr/sbin/visudo', '-cf', str(checked)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def test_payload_plan_source_binary_tampering_rejects_before_any_write(self):
        for key in ('plan', 'sources', 'binaries'):
            bad = copy.deepcopy(self.payload)
            if key == 'plan': bad[key] = 'e30='
            else: bad[key][next(iter(bad[key]))] = 'Zml4dHVyZQ='
            with self.subTest(key=key), self.assertRaises(ValueError):
                install.Installer(self.host, bad)
        self.assertFalse(self.path(install.ANCHOR).exists())

    def test_existing_anchor_or_destination_never_overwritten(self):
        self.path(install.ANCHOR).mkdir()
        with self.assertRaises(ValueError): self.actor.install()
        self.assertFalse(self.path(install.GRANT).exists())

    def test_existing_grant_preserved(self):
        self.path(install.GRANT).write_bytes(b'UNRELATED EXISTING ENTRY')
        with self.assertRaises(ValueError): self.actor.install()
        self.assertEqual(self.path(install.GRANT).read_bytes(), b'UNRELATED EXISTING ENTRY')

    def test_symlink_privileged_parent_rejected(self):
        self.path('/usr/local/sbin').rmdir()
        self.path('/usr/local/sbin').symlink_to(self.path('/mnt/vk-storage'), target_is_directory=True)
        with self.assertRaises(OSError): self.actor.preflight()

    def test_mutable_privileged_ancestor_rejected(self):
        self.path('/usr/local').chmod(0o777)
        with self.assertRaises(ValueError): self.actor.preflight()

    def test_symlink_SSD_parent_rejected_without_changing_real_parent(self):
        self.path('/mnt/vk-storage').rmdir()
        elsewhere = self.base / 'retained-data'
        elsewhere.mkdir()
        self.path('/mnt/vk-storage').symlink_to(elsewhere, target_is_directory=True)
        with self.assertRaises(OSError): self.actor.preflight()
        self.assertEqual(list(elsewhere.iterdir()), [])

    def test_prepublication_validation_failure_never_grants_preserves_partial_evidence(self):
        self.host.fail_at = lambda row: row[-1].endswith('.validation')
        with self.assertRaises(ValueError): self.actor.install()
        self.assertFalse(self.path(install.GRANT).exists())
        self.assertTrue(self.path(install.ANCHOR + '/installation.failed.safe.json').exists())
        self.assertTrue(self.path('/usr/local/libexec/vk-process-inspection-v1.py').exists())
        self.assertTrue(self.path('/etc/vibe-kanban/process-inspection-v1.json').exists())
        self.assertNotIn(('publish',), self.host.events)

    def test_postpublication_failure_withdraws_only_new_grant(self):
        def fail(argv):
            return ('publish',) in self.host.events and argv == ('/usr/sbin/visudo', '-c')
        self.host.fail_at = fail
        self.path('/etc/sudoers.d/unrelated').write_bytes(b'preserve unrelated entry')
        with self.assertRaises(ValueError): self.actor.install()
        self.assertFalse(self.path(install.GRANT).exists())
        self.assertEqual(self.path('/etc/sudoers.d/unrelated').read_bytes(), b'preserve unrelated entry')
        self.assertTrue(self.path(install.ANCHOR + '/installation.failed.safe.json').exists())
        self.assertTrue(self.path('/usr/local/sbin/vk-process-inspect-v1').exists())

    def test_concurrent_destination_collision_not_overwritten_or_removed(self):
        original = self.host.publish_grant
        def collision(path):
            self.path(install.GRANT).write_bytes(b'other administrator grant')
            original(path)
        with patch.object(self.host, 'publish_grant', side_effect=collision), self.assertRaises(FileExistsError):
            self.actor.install()
        self.assertEqual(self.path(install.GRANT).read_bytes(), b'other administrator grant')

    def test_anchor_replacement_before_publication_fails_closed(self):
        original = self.host.run
        def changed(*argv):
            original(*argv)
            if argv[-1].endswith('.validation'):
                self.path(install.ANCHOR).rename(self.path(install.ANCHOR + '.retained'))
                self.path(install.ANCHOR).mkdir()
        with patch.object(self.host, 'run', side_effect=changed), self.assertRaises(ValueError):
            self.actor.install()
        self.assertFalse(self.path(install.GRANT).exists())
        self.assertTrue(self.path(install.ANCHOR + '.retained/installation.started.safe.json').exists())

    def test_rollback_removes_only_exact_grant_retains_code_policies_data_evidence(self):
        self.actor.install()
        retained = {str(p): p.read_bytes() for p in self.base.rglob('*') if p.is_file() and p != self.path(install.GRANT)}
        self.actor.rollback()
        self.assertFalse(self.path(install.GRANT).exists())
        for p, data in retained.items(): self.assertEqual(Path(p).read_bytes(), data)

    def test_rollback_uses_durable_prepublication_provenance_after_crash(self):
        self.actor.install()
        self.path(install.EVIDENCE).rename(self.path(install.EVIDENCE + '.retained'))
        self.actor.rollback()
        self.assertFalse(self.path(install.GRANT).exists())
        self.assertTrue(self.path(install.ANCHOR + '/installation.validated.safe.json').exists())

    def test_rollback_changed_grant_rejected(self):
        self.actor.install()
        self.path(install.GRANT).chmod(0o600)
        self.path(install.GRANT).write_bytes(b'new admin policy')
        self.path(install.GRANT).chmod(0o440)
        with self.assertRaises(ValueError): self.actor.rollback()
        self.assertEqual(self.path(install.GRANT).read_bytes(), b'new admin policy')

    def test_installed_policy_or_code_substitution_rejected(self):
        self.actor.install()
        path = self.path('/etc/vibe-kanban/historical-archive-inspection-v1.json')
        policy = json.loads(path.read_bytes())
        policy['target']['path'] = '/etc/shadow'
        path.write_text(json.dumps(policy))
        with self.assertRaises(ValueError): self.actor.verify_installed()

    def test_historical_metadata_function_never_reads_file_contents(self):
        self.metadata.stop()
        target = self.actor.plan['policy_scopes']['historical']['target']
        path = self.path(target['path'])
        path.parent.mkdir(parents=True)
        path.write_bytes(b'synthetic exact target')
        path.chmod(0o600)
        target['identity'] = {k: getattr(path.stat(), 'st_' + k) for k in target['identity']}
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('artifact read')):
            self.actor.historical_metadata()
        path.rename(path.with_name('retained'))
        path.symlink_to('/etc/shadow')
        with self.assertRaises(ValueError): self.actor.historical_metadata()


class AcceptanceTests(unittest.TestCase):
    def test_profiles_use_read_only_boundary_with_own_private_lease(self):
        import vk_inspection_acceptance as acceptance
        for profile in ('managed', 'historical'):
            with self.subTest(profile=profile):
                base = Path(tempfile.mkdtemp(prefix='acceptance-', dir='/mnt/vk-storage/vk-retirement-preflight-tests'))
                base.chmod(0o755)
                for kind in ('control', 'objects'):
                    (base / kind).mkdir(mode=0o700)
                anchor_info = base.stat()
                original = os.fstat
                def fstat(fd):
                    info = original(fd)
                    if (info.st_dev, info.st_ino) == (anchor_info.st_dev, anchor_info.st_ino):
                        return types.SimpleNamespace(st_uid=0, st_mode=info.st_mode,
                                                     st_dev=info.st_dev, st_ino=info.st_ino)
                    return info
                installation = {'approved_plan_head': install.PLAN_HEAD, 'plan_sha256': install.PLAN_SHA,
                     'adoption_enabled': False, 'anchor_identity': [anchor_info.st_dev, anchor_info.st_ino],
                     'installed_files': {entry['destination']: entry['sha256'] for entry in
                                         json.loads(builder.git_bytes(builder.PLAN))['files']}}
                calls = []
                def checked(**kwargs):
                    self.assertIsNone(kwargs['consume'])
                    self.assertTrue(kwargs['lease'].verify())
                    calls.append(kwargs['manifest'])
                    return {'action_authorized': False}
                with patch.object(acceptance, 'ANCHOR', base), patch.object(os, 'fstat', side_effect=fstat), \
                     patch.object(acceptance.boundary, 'at_held_boundary', side_effect=checked), \
                     patch.object(acceptance.historical, 'at_archive_boundary', side_effect=checked):
                    result = acceptance.run(profile, installation)
                self.assertTrue(result['acceptance_only'])
                self.assertFalse(result['operational_adoption_changed'])
                self.assertFalse(result['action_authorized'])
                self.assertEqual(len(calls), 1)
                leases = list((base / 'control').rglob('owner.lease'))
                self.assertEqual(len(leases), 1)
                self.assertTrue(leases[0].exists())

    def test_unknown_profile_rejects_before_scope_access(self):
        import vk_inspection_acceptance as acceptance
        with patch.object(os, 'open', side_effect=AssertionError('scope opened')), self.assertRaises(ValueError):
            acceptance.run('unknown', {})


if __name__ == '__main__':
    unittest.main()
