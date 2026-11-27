"""Packed layout through existing recovery contracts using isolated fixture stores."""
import copy
import io
from pathlib import Path
import unittest
import uuid

import graph
import log_dedup as logs
import packed_graph
import packed_objects
import reclaim
import resume
import test_nightly_graph


class PackedRecoveryTests(unittest.TestCase):
    def setUp(self):
        owner = test_nightly_graph.GraphOwnerTests()
        owner.setUp()
        self.addCleanup(owner.doCleanups)
        self.owner = owner
        f = owner.f
        self.paths = [f.archive / row['path'] for row in f.plan['files']]
        result = f.base / 'packed-output'
        packed_objects.prepare(self.paths, result)
        (result / '.log-packs').rename(self.paths[0].parent / '.log-packs')
        for p in self.paths:
            (result / p.name).replace(p)  # Disposable fixture only.
        owner.graph = graph.inventory(f.archive, f.plan)

    def test_restored_packs_reconstruct_without_source_or_staged_carriers(self):
        o = self.owner
        scratch = o.f.base / 'carrier-staging'
        scratch.mkdir()
        dest = o.f.base / 'independent-restored'
        with packed_graph.checkpoint_graph(o.recovery, o.graph, hook=o.hook, normal=o.normal,
                operation=uuid.uuid4().hex, plan_sha256='1'*64, seed='2'*64,
                save=lambda n,r: o.saved.append(r), scratch=scratch) as provider:
            held = []
            try:
                # Keep allocation alive to avoid recycled-inode false positives in the fixture.
                for row in o.graph['members']:
                    p = o.f.archive / row['path']
                    held.append(p.open('rb'))
                    p.unlink()
                for p in scratch.glob('pack-*/*'):
                    p.unlink()
                self.assertTrue(graph.verify_provider(o.graph, provider, lambda: None)['independent_backup_verified'])
                for row in o.graph['members']:
                    p = dest / row['path']
                    p.parent.mkdir(parents=True, exist_ok=True)
                    with provider.open_member(row['path'], row['sha256']) as source, p.open('xb') as target:
                        while block := source.read(1024 * 1024):
                            target.write(block)
                for row in o.f.plan['files']:
                    out = io.BytesIO()
                    logs.reconstruct(dest / row['path'], out)
                    self.assertEqual(logs.sha(out.getvalue()), row['sha256'])
            finally:
                for stream in held:
                    stream.close()

    def test_missing_or_misidentified_pack_fails_before_acceptance(self):
        o = self.owner
        with o.held() as provider:
            graph.verify_provider(o.graph, provider, lambda: None)
            smaller = copy.deepcopy(o.graph)
            smaller['members'] = [r for r in smaller['members'] if r['kind'] != 'pack']
            smaller['physical_members'] = len(smaller['members'])
            with self.assertRaisesRegex(ValueError, 'referenced object or pack'):
                graph.verify_provider(smaller, provider, lambda: None)

    def test_snapshot_pins_pack_and_old_publication_path_refuses(self):
        o = self.owner
        plan = dict(o.f.plan, source_root=str(o.f.archive))
        members = resume.readback_members(plan)
        self.assertEqual(len([p for p in members if '/.log-packs/' in p]), 1)
        # Never allow old V1 mutation code to publish a V2 manifest without its packs.
        tx = object.__new__(reclaim.Batch)
        tx.plan, tx.root, tx.archive = o.f.plan, o.f.source, o.f.archive
        with self.assertRaisesRegex(ValueError, 'qualified separate migration'):
            tx.publication_peak()

    def test_archived_header_is_never_treated_as_new_raw_input(self):
        for p in self.paths:
            self.assertTrue(logs.is_archive_header(p.read_bytes()[:len(logs.MAGIC)]))
            with self.assertRaisesRegex(ValueError, 'already archived'):
                logs.manifest_for(p, {})
        for value in [None, [], dict(version=True), dict(version=2, raw_bytes=0, sha256='a'*64, packs=[{}], chunks=[])]:
            with self.assertRaises(ValueError):
                packed_objects.validate_manifest(value)


if __name__ == '__main__':
    unittest.main()
