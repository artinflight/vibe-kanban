"""Driver trust-boundary tests; source fixtures do not certify an installed helper."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import driver
import privileged_inspector as probe


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.scope = self.root / 'scope'
        self.scope.mkdir()
        info = self.scope.stat()
        self.policy = dict(abi=1, caller_uid=os.getuid(), scopes=[dict(
            path=str(self.scope), identity=[info.st_dev, info.st_ino])])
        self.payload = self.scope / 'workspace'
        self.payload.mkdir()
        self.file = self.payload / 'history'
        self.file.write_text('retained bytes')
        self.request = dict(roots=[str(self.payload)], identities=[])

    def collect(self):
        return probe.collect(self.policy, self.request, time.monotonic() + 10)

    def test_payload_metadata_and_absent_original_are_supported(self):
        expected = {probe.identity(p.stat()) for p in (self.payload, self.file)}
        self.assertEqual(self.collect(), expected)
        self.request['roots'].append(str(self.scope / 'absent' / 'history'))
        self.assertEqual(self.collect(), expected)

    def test_scope_substitution_and_parent_alias_are_rejected(self):
        self.scope.rename(self.root / 'old')
        self.scope.mkdir()
        with self.assertRaises(ValueError):
            self.collect()
        self.scope.rmdir()
        (self.root / 'old').rename(self.scope)
        self.payload.rename(self.scope / 'retired')
        self.payload.symlink_to(self.scope / 'retired')
        with self.assertRaises(ValueError):
            self.collect()
        self.request['roots'] = [str(self.payload / 'history')]
        with self.assertRaises(OSError):
            self.collect()

    def test_member_symlinks_are_metadata_never_followed(self):
        link = self.payload / 'outside'
        link.symlink_to('/root/private')
        self.assertIn(probe.identity(link.lstat()), self.collect())
        self.assertEqual(len(self.collect()), 3)

    def test_unbound_root_and_foreign_filesystem_identity_hold(self):
        self.request['roots'] = [str(self.root)]
        with self.assertRaises(ValueError):
            self.collect()
        self.request['roots'] = [str(self.payload)]
        self.request['identities'] = [[self.scope.stat().st_dev + 1, 99]]
        with self.assertRaises(ValueError):
            self.collect()

    def test_directory_symlink_swap_does_not_escape_scope(self):
        real = probe.os.open
        changed = []
        def opening(path, flags, *args, **kwargs):
            if path == 'workspace' and not changed:
                changed.append(True)
                self.payload.rename(self.scope / 'retired')
                self.payload.symlink_to(self.root)
            return real(path, flags, *args, **kwargs)
        with patch.object(probe.os, 'open', side_effect=opening):
            with self.assertRaises(OSError):
                self.collect()

    def test_live_open_file_is_blocked_even_for_reported_owner(self):
        child = subprocess.Popen([sys.executable, '-c',
            'import sys; f=open(sys.argv[1]); print("ready",flush=True); sys.stdin.read()',
            str(self.file)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.addCleanup(lambda: child.poll() is None and child.kill())
        self.assertEqual(child.stdout.readline().strip(), 'ready')
        proc = self.root / 'proc'
        proc.mkdir()
        (proc / str(child.pid)).symlink_to('/proc/' + str(child.pid))
        with self.assertRaises(ValueError):
            probe.scan(self.collect(), child.pid, time.monotonic() + 10, proc)
        child.communicate('', timeout=5)
        self.assertEqual(probe.scan(self.collect(), child.pid, time.monotonic() + 10, proc), 0)

    def test_ambiguous_duplicate_json_is_rejected(self):
        with self.assertRaises(ValueError):
            probe.unique_json('{"roots": [], "roots": ["/other"]}')


class DriverPinsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.config = self.root / 'config.json'
        self.driver = self.root / 'driver.py'
        self.driver.write_text('source')
        self.driver.chmod(0o600)
        self.value = dict(format='vk-workspace-archive-driver-v1', source_pins=[dict(
            path=str(self.driver), sha256=hashlib.sha256(b'source').hexdigest())])
        self.config.write_text(json.dumps(self.value))
        self.config.chmod(0o600)
        self.patch = patch.multiple(driver, __file__=str(self.driver), MODULES={'driver.py'})
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_exact_owned_closure_and_private_configuration(self):
        value, reference = driver.configuration(self.config)
        self.assertEqual(value, self.value)
        self.assertEqual(reference['sha256'], hashlib.sha256(self.config.read_bytes()).hexdigest())
        self.config.chmod(0o640)
        with self.assertRaises(ValueError):
            driver.configuration(self.config)

    def test_changed_or_aliased_source_cannot_be_imported(self):
        self.driver.write_text('different')
        with self.assertRaises(ValueError):
            driver.configuration(self.config)
        self.driver.rename(self.root / 'actual.py')
        self.driver.symlink_to(self.root / 'actual.py')
        with self.assertRaises(ValueError):
            driver.configuration(self.config)


if __name__ == '__main__':
    unittest.main()
