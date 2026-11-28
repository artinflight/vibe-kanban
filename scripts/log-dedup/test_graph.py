from contextlib import contextmanager
import io
import unittest

import graph
import test_reclaim as fixture_module


class GraphTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.ReclaimTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_exact_graph_includes_manifests_unique_shared_objects_and_sidecars(self):
        value = graph.inventory(self.fixture.archive, self.fixture.plan)
        kinds = [row['kind'] for row in value['members']]
        self.assertEqual(kinds.count('manifest'), 2)
        self.assertEqual(kinds.count('sidecar'), 2)
        self.assertEqual(len(value['logical_originals']), 2)
        self.assertEqual(len({row['path'] for row in value['members']}), len(value['members']))
        self.assertGreater(kinds.count('object'), 0)
        self.assertFalse(value['independent_backup_verified'])

    def test_missing_referenced_object_cannot_be_declared_a_complete_backup(self):
        value = graph.inventory(self.fixture.archive, self.fixture.plan)
        value['members'] = [row for row in value['members'] if row['kind'] != 'object']
        value['physical_members'] = len(value['members'])
        root = self.fixture.archive
        class Provider:
            location = 'desktop:B:/vk-backups/fixture'
            @contextmanager
            def open_member(self, relative, sha):
                yield io.BytesIO((root / relative).read_bytes())
        with self.assertRaisesRegex(ValueError, 'referenced object'):
            graph.verify_provider(value, Provider(), lambda: None)

    def test_independent_provider_must_supply_every_exact_physical_body(self):
        value = graph.inventory(self.fixture.archive, self.fixture.plan)
        root = self.fixture.archive
        class Provider:
            location = 'desktop:B:/vk-backups/fixture'
            bad = False
            @contextmanager
            def open_member(self, relative, sha):
                yield io.BytesIO(b'corrupt' if self.bad else (root / relative).read_bytes())
        provider = Provider()
        self.assertTrue(graph.verify_provider(value, provider, lambda: None)['independent_backup_verified'])
        provider.bad = True
        with self.assertRaises(ValueError):
            graph.verify_provider(value, provider, lambda: None)


if __name__ == '__main__':
    unittest.main()
