import copy
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from vk_candidate_direct_b import archived_atime, DirectBProvider, hardlink_metadata
from vk_candidate_generation import Blocked, CandidateController, Layout, digest, inventory


class AtimeTests(unittest.TestCase):
    def test_operational_restore_cannot_skip_archive_timestamp_policy(self):
        from test_vk_candidate_direct_b import ContractTests
        fixture = ContractTests()
        fixture.setUp()
        try:
            fixture.capture('required-atime-policy')
            proof = fixture.provider.verify('required-atime-policy')
            proof['fixture_only'] = False
            with patch.object(fixture.provider, 'verify', return_value=proof):
                with self.assertRaisesRegex(Blocked, 'archived-atime policy'):
                    fixture.controller.authenticated('required-atime-policy')
            self.assertFalse(fixture.layout.tree.exists())
        finally:
            fixture.tearDown()

    def test_hardlink_headers_inherit_omitted_attrs_but_contradictions_block(self):
        row = {'mode': 0o644, 'uid': 1000, 'gid': 1000, 'mtime_ns': 123,
               'xattrs': {'user.fixture': 'YWJj'}}
        rows = {'file': row, 'alias': {**row, 'xattrs': {}}}
        hardlink_metadata(rows, 'file', ['file', 'alias'])
        for key, value in [('mode', 0o600), ('uid', 1001), ('gid', 1001),
                           ('mtime_ns', 124), ('xattrs', {'user.fixture': 'ZGVm'})]:
            bad = copy.deepcopy(rows)
            bad['alias'][key] = value
            with self.assertRaisesRegex(Blocked, 'conflict'):
                hardlink_metadata(bad, 'file', ['file', 'alias'])

    def test_archive_nanoseconds_are_exact_and_missing_or_ambiguous_times_block(self):
        member = tarfile.TarInfo('fixture')
        member.pax_headers = {'atime': '123.000000001'}
        self.assertEqual(archived_atime(member), 123000000001)
        for value in ('bad', 'NaN', 'Infinity', '-1', '0.0000000001'):
            member.pax_headers = {'atime': value}
            with self.assertRaises(Blocked):
                archived_atime(member)
        member.pax_headers = {}
        with self.assertRaisesRegex(Blocked, 'missing'):
            archived_atime(member)
        with self.assertRaisesRegex(Blocked, 'boolean'):
            DirectBProvider('a'*64, [], restore_archived_atime='yes')

    def prepared(self):
        base = Path(tempfile.mkdtemp(prefix='atime-private-',
                    dir='/mnt/vk-storage/vk-safe-release-20261008/direct-b-contract-tests'))
        protected = base / 'protected'
        protected.mkdir()
        (protected / 'sentinel').write_bytes(b'preserved')
        tree = base / 'candidate/tree'
        (tree / 'state').mkdir(parents=True)
        (tree / 'state/file').write_bytes(b'exact content')
        os.link(tree / 'state/file', tree / 'state/alias')
        (tree / 'state/link').symlink_to('file')
        controller = object.__new__(CandidateController)
        controller.layout = Layout(base / 'candidate', tree, base / 'candidate/evidence', (protected,))
        binding = controller.layout.binding()

        class StoppedFixture:
            def verify_stopped(self, observed):
                if observed != binding:
                    raise Blocked('wrong fixture root')
        controller.supervisor = StoppedFixture()
        rows = inventory(tree)  # Real content traversal precedes timestamp restoration.
        values = {name: 123000000001 for name in rows}
        return controller, {'entries': rows, 'restore_archived_atime': True,
                'archived_atime_ns': values, 'archived_atime_sha256': digest(values)}, protected

    def test_real_private_files_links_and_directories_retain_exact_archive_atime(self):
        controller, verified, protected = self.prepared()
        before = (protected / 'sentinel').stat()
        proof = controller.restore_atimes(verified)
        self.assertTrue(proof['archived_atime_restored'])
        self.assertFalse(proof['original_source_atime_verified'])
        for name, row in verified['entries'].items():
            info = (controller.layout.tree / name).lstat()
            self.assertEqual(info.st_atime_ns, 123000000001)
            self.assertEqual(info.st_mtime_ns, row['mtime_ns'])
        self.assertEqual((controller.layout.tree / 'state/file').stat().st_ino,
                         (controller.layout.tree / 'state/alias').stat().st_ino)
        self.assertEqual(os.readlink(controller.layout.tree / 'state/link'), 'file')
        after = (protected / 'sentinel').stat()
        self.assertEqual((before.st_mtime_ns, before.st_atime_ns, before.st_mode, before.st_ino),
                         (after.st_mtime_ns, after.st_atime_ns, after.st_mode, after.st_ino))

    def test_missing_or_changed_timestamp_inventory_fails_before_any_timestamp_write(self):
        controller, verified, _ = self.prepared()
        path = controller.layout.tree / 'state/file'
        before = path.stat().st_atime_ns
        for mode in ('missing', 'changed'):
            bad = copy.deepcopy(verified)
            if mode == 'missing':
                del bad['archived_atime_ns']['state/file']
            else:
                bad['archived_atime_ns']['state/file'] += 1
            with self.assertRaisesRegex(Blocked, 'binding mismatch'):
                controller.restore_atimes(bad)
            self.assertEqual(path.stat().st_atime_ns, before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
