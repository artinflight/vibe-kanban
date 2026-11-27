from contextlib import contextmanager
import copy
import unittest
import uuid
from unittest.mock import patch, Mock

import graph
import packed_graph as pg
from test_nightly_graph import GraphOwnerTests


class PackedGraphTests(unittest.TestCase):
    def setUp(self):
        self.f = GraphOwnerTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.scratch = self.f.f.base / 'packed'
        self.scratch.mkdir(mode=0o700)

    @contextmanager
    def held(self):
        f = self.f
        with pg.checkpoint_graph(f.recovery, f.graph, hook=f.hook, normal=f.normal,
                operation=uuid.uuid4().hex, plan_sha256='1'*64, seed='2'*64,
                save=lambda n,r:f.saved.append(r), scratch=self.scratch) as provider:
            yield provider

    def partial(self):
        original = self.f.hook.checkpoint
        calls = [0]
        def fail_second(*args, **kwargs):
            calls[0] += 1
            if calls[0] == 2:
                raise ValueError('injected before checkpoint submission')
            return original(*args, **kwargs)
        with patch.object(pg.closure, 'bundles', side_effect=lambda rows, maximum: [[r] for r in rows]), \
                patch.object(self.f.hook, 'checkpoint', side_effect=fail_second):
            with self.assertRaisesRegex(ValueError, 'injected before'):
                with self.held():
                    pass
        self.assertEqual(len(self.f.saved), 1)
        return copy.deepcopy(self.f.saved)

    @contextmanager
    def resumed(self, retained):
        f = self.f
        with patch.object(pg.closure, 'bundles', side_effect=lambda rows, maximum: [[r] for r in rows]):
            with pg.checkpoint_graph(f.recovery, f.graph, hook=f.hook, normal=f.normal,
                    operation=uuid.uuid4().hex, plan_sha256='1'*64, seed='2'*64,
                    save=lambda n, r:f.saved.append(r), scratch=self.scratch,
                    retained=retained, attempt='resume3') as provider:
                yield provider

    def test_partial_prefix_reuses_old_checkpoint_and_restores_all_bytes(self):
        retained = self.partial()
        old = (self.scratch / 'pack-1' / 'closure.tar').read_bytes()
        with self.resumed(retained) as provider:
            proof = graph.verify_provider(self.f.graph, provider, lambda:None)
            self.assertTrue(proof['independent_backup_verified'])
        self.assertEqual(self.f.saved[0], retained[0])
        self.assertEqual(len(self.f.saved), len(self.f.graph['members']))
        self.assertEqual((self.scratch / 'pack-1' / 'closure.tar').read_bytes(), old)

    def test_changed_prefix_refuses_before_any_new_checkpoint(self):
        retained = self.partial()
        retained[0]['members']['files'][0]['sha256'] = 'f'*64
        with patch.object(self.f.hook, 'checkpoint') as call:
            with self.assertRaisesRegex(ValueError, 'exact prefix'):
                with self.resumed(retained): pass
            call.assert_not_called()

    def test_changed_graph_binding_refuses_before_any_new_checkpoint(self):
        retained = self.partial()
        retained[0]['graph_sha256'] = 'f'*64
        with patch.object(self.f.hook, 'checkpoint') as call:
            with self.assertRaisesRegex(ValueError, 'binding differs'):
                with self.resumed(retained): pass
            call.assert_not_called()

    def test_failed_old_restore_refuses_before_new_checkpoint(self):
        retained = self.partial()
        self.f.deny = True
        with patch.object(self.f.hook, 'checkpoint') as call:
            with self.assertRaisesRegex(ValueError, 'Retained normal B archive restore failed'):
                with self.resumed(retained): pass
            call.assert_not_called()

    def test_consumed_partial_attempt_is_not_replayed(self):
        retained = self.partial()
        with self.resumed(retained): pass
        with patch.object(self.f.hook, 'checkpoint') as call:
            with self.assertRaises(FileExistsError):
                with self.resumed(retained): pass
            call.assert_not_called()

    def test_remote_owner_failure_is_seen_at_next_poll(self):
        with self.held() as provider:
            handle=provider.handle
            handle.last_owner_check=0
            with patch.object(pg.time,'monotonic',return_value=.5), patch.object(handle.recovery,'check',side_effect=ValueError('owner lost')) as check:
                handle.check()
                check.assert_not_called()
            with patch.object(pg.time,'monotonic',return_value=1), patch.object(handle.recovery,'check',side_effect=ValueError('owner lost')):
                with self.assertRaisesRegex(ValueError,'owner lost'):handle.check()

    def test_bounded_read_checks_still_cover_both_boundaries_and_all_bytes(self):
        with self.held() as provider:
            guard=Mock()
            proof=graph.verify_provider(self.f.graph,provider,guard,guard_every=64)
            self.assertEqual(proof['physical_members'],len(self.f.graph['members']))
            self.assertGreaterEqual(guard.call_count,2)
            for interval in (0,65,True):
                with self.assertRaises(ValueError):graph.verify_provider(self.f.graph,provider,guard,guard_every=interval)

    def test_remote_bytes_survive_removing_staged_graph_and_carriers(self):
        with self.held() as provider:
            for row in self.f.graph['members']:
                path = self.f.f.archive / row['path']
                # Retain inode allocation, not a provider-visible fallback: a
                # historical inode number can otherwise be reused by extraction.
                held = path.open('rb')
                self.addCleanup(held.close)
                path.unlink()
            for path in self.scratch.glob('pack-*/*'):
                path.unlink()
            self.assertTrue(graph.verify_provider(self.f.graph, provider, lambda:None)['independent_backup_verified'])
        with pg.reopen_graph(self.f.recovery, self.f.graph, self.f.saved,
                hook=self.f.hook, normal=self.f.normal, scratch=self.scratch) as provider:
            self.assertTrue(graph.verify_provider(self.f.graph, provider, lambda:None)['independent_backup_verified'])
        self.assertGreater(self.f.closed, 0)

    def test_corrupt_remote_bytes_refused(self):
        self.f.corrupt = True
        with self.assertRaises(ValueError):
            with self.held():
                self.fail('Corrupt B data admitted')
        self.assertGreater(self.f.closed, 0)

    def test_failed_normal_restore_refused(self):
        self.f.deny = True
        with self.assertRaisesRegex(ValueError, 'Normal packed carrier restore failed'):
            with self.held():
                self.fail('Unverified normal restore admitted')

    def test_missing_receipt_union_refused(self):
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            pg.PackedGraph(self.f.recovery, self.f.graph, [], self.scratch)

    def test_duplicate_or_wrong_member_refused(self):
        with self.held():
            pass
        manifest = copy.deepcopy(self.f.saved[0]['members'])
        manifest['files'].append(manifest['files'][0])
        with self.assertRaisesRegex(ValueError, 'differs'):
            pg.validate_members(self.f.graph, manifest)
        manifest = copy.deepcopy(self.f.saved[0]['members'])
        manifest['files'][0]['sha256'] = 'f'*64
        with self.assertRaisesRegex(ValueError, 'differs'):
            pg.validate_members(self.f.graph, manifest)

    def test_foreign_namespace_refused(self):
        with self.held() as provider:
            with self.assertRaises(ValueError):
                provider.handle.entry('foreign/' + self.f.graph['members'][0]['path'])

    def test_body_bound_cannot_be_expanded(self):
        huge = dict(self.f.graph, members=[dict(self.f.graph['members'][0], bytes=2*1024**3+1)])
        with self.assertRaisesRegex(ValueError, 'Bounded archive graph'):
            with pg.checkpoint_graph(self.f.recovery, huge, hook=self.f.hook, normal=self.f.normal,
                    operation=uuid.uuid4().hex, plan_sha256='1'*64, seed='2'*64,
                    save=lambda n,r:None, scratch=self.scratch):
                pass


if __name__ == '__main__':
    unittest.main()
