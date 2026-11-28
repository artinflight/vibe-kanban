import copy
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
import zlib

from vk_backup_rebuild_proof import certify


def directory():
    return {'kind': 'directory', 'mode': 0o700, 'uid': 1000, 'gid': 1000, 'mtime_ns': 1, 'xattrs': {}}


def file(data):
    return {**directory(), 'kind': 'file', 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


class ExactRebuildProof(unittest.TestCase):
    def setUp(self):
        self.dependency = b'pristine offline dependency\n' * 100
        self.payloads = {'recipes/rebuild-v1.py': b'fixture fixed offline recipe v1',
                         'inputs/package.zlib': zlib.compress(self.dependency),
                         'package-lock.json': b'fixture package integrity v1',
                         'src/dirty.py': b'uncommitted source', 'notes/untracked': b'untracked user work',
                         'sessions/old.jsonl': b'complete historic session',
                         'node_modules/pkg/main.py': self.dependency}
        self.entries = {key: file(value) for key, value in self.payloads.items()}
        self.entries.update({key: directory() for key in ('recipes', 'inputs', 'src', 'notes', 'sessions', 'node_modules', 'node_modules/pkg')})
        self.rebuilt = {key: copy.deepcopy(row) for key, row in self.entries.items() if key.startswith('node_modules/') or key == 'node_modules'}
        self.protected = {'src/dirty.py', 'notes/untracked', 'sessions/old.jsonl'}
        self.recipes = {'node_modules': {'id': 'offline-package-v1', 'source': 'recipes/rebuild-v1.py',
                        'inputs': {key: self.entries[key]['sha256'] for key in ('recipes/rebuild-v1.py', 'inputs/package.zlib', 'package-lock.json')}}}

    def prove(self, **kwargs):
        args = dict(approved_roots=['node_modules'], protected=self.protected,
                    read_rebuilt_file=lambda key: io.BytesIO(self.dependency),
                    read_rebuilt_link=lambda _: self.fail('no link expected'),
                    readback_budget_bytes=len(self.dependency))
        args.update(kwargs)
        return certify(self.entries, self.rebuilt, self.recipes, **args)

    def test_physical_independent_rebuild_restores_full_catalog_and_user_work(self):
        with tempfile.TemporaryDirectory(prefix='vk-offline-rebuild-') as raw:
            root = Path(raw)
            retained = root / 'retained'
            retained.mkdir()
            # Persist only retained recipe/input/work bytes. The omitted tree
            # is rebuilt from these independently recovered input files.
            for key, data in self.payloads.items():
                if not key.startswith('node_modules/'):
                    path = retained / key
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
            # Independently rebuild from the retained compressed input, not from
            # original node_modules or a previous backup generation.
            rebuilt = root / 'rebuilt/node_modules/pkg/main.py'
            rebuilt.parent.mkdir(parents=True)
            rebuilt.write_bytes(zlib.decompress((retained / 'inputs/package.zlib').read_bytes()))
            proof = self.prove(read_rebuilt_file=lambda _: rebuilt.open('rb'))
            self.assertNotIn('node_modules/pkg/main.py', proof['capture_projection']['entries'])
            self.assertIn('node_modules/pkg/main.py', proof['complete_restore_catalog'])
            for key, row in proof['complete_restore_catalog'].items():
                path = retained / key
                if row['kind'] == 'directory':
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    data = rebuilt.read_bytes() if key.startswith('node_modules/') else self.payloads[key]
                    path.write_bytes(data)
                    self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), row['sha256'])
            for key in self.protected:
                self.assertEqual((retained / key).read_bytes(), self.payloads[key])
            self.assertFalse(proof['adoption_authorized'])

    def test_ignored_patch_untracked_extra_and_deleted_output_each_reject_root(self):
        for case in ('patch', 'extra', 'deleted'):
            original = copy.deepcopy(self.entries)
            if case == 'patch':
                self.entries['node_modules/pkg/main.py'] = file(b'locally patched unpublished source')
            elif case == 'extra':
                self.entries['node_modules/local-note.py'] = file(b'ignored unique source')
            else:
                del self.entries['node_modules/pkg/main.py']
            with self.subTest(case=case), self.assertRaisesRegex(ValueError, 'rebuild differs'):
                self.prove()
            self.entries = original

    def test_protected_work_even_if_byte_identical_may_not_be_excluded(self):
        with self.assertRaisesRegex(ValueError, 'protected'):
            self.prove(protected=self.protected | {'node_modules/pkg/main.py'})
        with self.assertRaisesRegex(ValueError, 'protected'):
            self.prove(protected=iter(self.protected | {'node_modules/pkg/main.py'}))

    def test_malformed_recipe_fails_without_invoking_readback(self):
        for recipe in ([], {'id': 'x', 'source': 'a', 'inputs': []},
                       {'id': 'x', 'source': [], 'inputs': {}}):
            with self.subTest(recipe=recipe), self.assertRaises(ValueError):
                certify(self.entries, self.rebuilt, {'node_modules': recipe},
                        approved_roots=['node_modules'], protected=self.protected,
                        read_rebuilt_file=lambda _: self.fail('malformed recipe read'),
                        read_rebuilt_link=lambda _: self.fail('malformed recipe read'),
                        readback_budget_bytes=len(self.dependency))

    def test_manifest_claim_cannot_replace_actual_rebuilt_readback(self):
        for data in (b'corrupt', self.dependency[:-1], self.dependency + b'x'):
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                self.prove(read_rebuilt_file=lambda _: io.BytesIO(data))

    def test_changed_input_recipe_scope_overlap_and_budget_rejected(self):
        self.entries['inputs/package.zlib'] = file(b'wrong pinned input')
        with self.assertRaises(ValueError):
            self.prove()
        self.setUp()
        for roots in (['../node_modules'], ['node_modules', 'node_modules/pkg'], ['/node_modules']):
            with self.assertRaises(ValueError):
                self.prove(approved_roots=roots)
        with self.assertRaisesRegex(ValueError, 'byte budget'):
            self.prove(readback_budget_bytes=len(self.dependency) - 1)

    def test_root_substitution_during_readback_rejected(self):
        def substitute(_):
            self.entries['package-lock.json'] = file(b'changed after proof began')
            return io.BytesIO(self.dependency)
        with self.assertRaisesRegex(ValueError, 'changed during proof'):
            self.prove(read_rebuilt_file=substitute)

    def test_symlink_literal_is_checked_without_reading_its_target(self):
        row = {**directory(), 'kind': 'symlink', 'target': '../../src/dirty.py'}
        self.entries['node_modules/pkg/local-link'] = row
        self.rebuilt['node_modules/pkg/local-link'] = copy.deepcopy(row)
        self.assertEqual(self.prove(read_rebuilt_link=lambda _: '../../src/dirty.py')['readback_bytes'], len(self.dependency))
        with self.assertRaisesRegex(ValueError, 'symlink literal'):
            self.prove(read_rebuilt_link=lambda _: '/unexpected/target')

    def test_retained_hardlink_alias_still_owns_recoverable_bytes(self):
        row = {**file(self.dependency), 'kind': 'hardlink', 'target': 'node_modules/pkg/main.py'}
        self.entries['src/retained-alias'] = row
        proof = self.prove(protected=self.protected | {'src/retained-alias'})
        self.assertEqual(proof['capture_projection']['entries']['src/retained-alias']['kind'], 'file')
        self.assertEqual(proof['complete_restore_catalog']['src/retained-alias']['kind'], 'hardlink')


if __name__ == '__main__':
    unittest.main()
