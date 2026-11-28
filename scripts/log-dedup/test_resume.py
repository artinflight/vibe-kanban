import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, main

import audit
import log_dedup as logs
import resume
import test_operation


class ResumeTests(TestCase):
    def setUp(self):
        self.operation = test_operation.OperationTests()
        self.operation.setUp()
        self.addCleanup(self.operation.doCleanups)
        self.f = self.operation.fixture
        self.first, self.next = self.operation.split_plans()
        self.journal = self.f.base / 'committed'
        with self.f.fence.held():
            self.operation.additional(self.first, self.journal)
        self.state = json.loads((self.journal / 'state.json').read_bytes())
        self.proof = dict(independent_normal_B_full_EOF_hash_and_Linux_metadata_verified=True,
                          actual_restores=[])
        for row in self.first['files']:
            names = [(row['path'], row['sha256'], row['raw_bytes'])]
            for side in row['sidecars']:
                name = str(Path(row['path']).with_suffix('.' + side['extension']))
                names.append((name, side['sha256'], len(self.f.store.bodies[name])))
            for name, digest, size in names:
                self.proof['actual_restores'].append(dict(relative=name, sha256=digest, bytes=size,
                    Linux_metadata_verified=True, separate_restored_inode=[999, len(self.proof['actual_restores'])]))
        self.proof['files'] = len(self.proof['actual_restores'])
        self.proof['bytes'] = sum(r['bytes'] for r in self.proof['actual_restores'])

    def verify(self):
        return resume.completed_batch(self.first, self.state, self.proof)

    def test_resume_converts_only_remaining_batch_preserving_prior_journal(self):
        preserved = (self.journal / 'state.json').read_bytes()
        original_manifest = (self.f.source / self.first['files'][0]['path']).read_bytes()
        verified = self.verify()
        observation = audit.inventory(self.f.source, self.f.db)
        remaining = resume.remaining(observation, [verified])
        self.assertEqual(remaining['remaining_paths'], [self.next['files'][0]['path']])
        self.assertFalse(remaining['writer_fence_established'])
        with self.f.fence.held():
            self.operation.additional(self.next, self.f.base / 'successor-journal')
        self.assertEqual((self.journal / 'state.json').read_bytes(), preserved)
        self.assertEqual((self.f.source / self.first['files'][0]['path']).read_bytes(), original_manifest)
        self.assertNotIn('activate', self.operation.events)
        self.assertFalse(self.operation.recovery_called)

    def test_resume_after_failed_next_batch_keeps_completed_manifest(self):
        with self.f.fence.held():
            self.operation.failure = 'manifest_readback_complete'
            with self.assertRaises(RuntimeError):
                self.operation.additional(self.next, self.f.base / 'failed-next')
        self.assertTrue(self.verify()['verified'])
        self.assertEqual(logs.sha((self.f.source / self.next['files'][0]['path']).read_bytes()),
                         self.next['files'][0]['sha256'])
        self.assertFalse(self.operation.recovery_called)

    def test_incomplete_journal_rejected(self):
        self.state['complete'] = False
        with self.assertRaisesRegex(ValueError, 'reconcile partial'):
            self.verify()

    def test_mutated_completed_manifest_rejected(self):
        path = self.f.source / self.first['files'][0]['path']
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'identity/content'):
            self.verify()

    def test_missing_object_rejected(self):
        path = self.f.source / self.first['files'][0]['path']
        chunk = logs.load_manifest(path)['chunks'][0]['sha256']
        (path.parent / '.log-objects' / (chunk + '.gz')).unlink()
        with self.assertRaises(FileNotFoundError):
            self.verify()

    def test_sidecar_replacement_rejected(self):
        path = (self.f.source / self.first['files'][0]['path']).with_suffix('.capture.json')
        path.write_bytes(b'{"capture_state":"pending"}\n')
        with self.assertRaisesRegex(ValueError, 'sidecar changed'):
            self.verify()

    def test_incomplete_original_proof_rejected(self):
        self.proof['actual_restores'].pop()
        with self.assertRaisesRegex(ValueError, 'B proof incomplete'):
            self.verify()

    def test_completed_evidence_from_another_root_is_rejected(self):
        verified = self.verify()
        observation = audit.inventory(self.f.source, self.f.db)
        verified['source_root'] = str(self.f.base)
        with self.assertRaisesRegex(ValueError, 'another source root'):
            resume.remaining(observation, [verified])

    def test_unaccounted_archive_and_repeated_first_batch_rejected(self):
        verified = self.verify()
        observation = audit.inventory(self.f.source, self.f.db)
        observation['eligible_closed_inactive_files'].append(self.first['files'][0]['path'])
        with self.assertRaisesRegex(ValueError, 'again'):
            resume.remaining(observation, [verified])
        observation['eligible_closed_inactive_files'].pop()
        observation['files'][self.next['files'][0]['path']]['archived'] = True
        with self.assertRaisesRegex(ValueError, 'Unexpected'):
            resume.remaining(observation, [verified])


class HistoryAndRecoveryTests(TestCase):
    def setUp(self):
        self.old = dict(job={'private_retained': {'unchanged': 'digest'}},
            canary_qualified_page_sha256={'main': {'execution': 'a' * 64},
                                         'protected5650': {'execution': 'c' * 64}})
        self.new = copy.deepcopy(self.old)
        self.new['canary_qualified_page_sha256']['main']['execution'] = 'b' * 64
        self.raw = {'execution': dict(raw='b' * 64, converted='b' * 64, exact=True)}
        self.live = {role: {execution: dict(actual=digest, expected=digest, exact=True)
                           for execution, digest in rows.items()}
                     for role, rows in self.new['canary_qualified_page_sha256'].items()}

    def qualify(self):
        return resume.qualify_history_inputs(self.old, self.new, self.raw, self.live)

    def test_context_qualified_raw_cas_live_page_exactness(self):
        self.assertTrue(self.qualify()['exact_page_comparison'])
        self.assertFalse(self.qualify()['normalization_applied'])

    def test_live_digest_alone_cannot_replace_baseline(self):
        self.raw['execution']['raw'] = 'a' * 64
        with self.assertRaisesRegex(ValueError, 'raw/CAS'):
            self.qualify()

    def test_protected_or_private_requirement_change_rejected(self):
        self.new['job']['private_retained'] = {}
        with self.assertRaisesRegex(ValueError, 'Noncanary'):
            self.qualify()
        self.new = copy.deepcopy(self.old)
        self.new['canary_qualified_page_sha256']['protected5650']['execution'] = 'd' * 64
        with self.assertRaisesRegex(ValueError, 'Protected'):
            self.qualify()

    def test_strict_failure_does_not_recur_during_independent_recovery(self):
        events = []
        def strict():
            events.append('strict')
            raise ValueError('Path rendering context differs')
        def independent():
            events.append('lossless-current-aware-queue-settings-review')
            return dict(lossless_compatible_service_verified=True)
        result = resume.recover_compatible(qualification=strict, verify_lossless_service=independent,
            release=lambda: events.append('release') or {'service_recovered': True},
            record=lambda phase, value: events.append(phase))
        self.assertTrue(result['service_recovered'])
        self.assertEqual(events.count('strict'), 1)
        self.assertLess(events.index('lossless-current-aware-queue-settings-review'), events.index('release'))
        self.assertIn('strict_acceptance_failed', events)

    def test_failed_lossless_recovery_holds_maintenance(self):
        released = []
        def refuse():
            raise ValueError('Current decoded history changed')
        with self.assertRaisesRegex(ValueError, 'decoded history'):
            resume.recover_compatible(qualification=lambda: None, verify_lossless_service=refuse,
                release=lambda: released.append(True), record=lambda *args: None)
        self.assertFalse(released)

    def test_health_alone_cannot_release(self):
        with self.assertRaisesRegex(ValueError, 'Independent compatible'):
            resume.recover_compatible(qualification=lambda: None,
                verify_lossless_service=lambda: {'http_success': True},
                release=lambda: self.fail('Unsafe release'), record=lambda *args: None)


class AdoptionTests(TestCase):
    verify = ResumeTests.verify
    def setUp(self):
        ResumeTests.setUp(self)
        self.observed = []
        self.units = {u: dict(MainPID=str(i), InvocationID='invocation-' + u,
                             ActiveState='active', FreezerState='frozen')
                      for i, u in enumerate(['main', 'reader', 'proxy'], 1)}
        self.base = SimpleNamespace(MAIN='main', READER='reader', PROXY='proxy',
            actual_fence=lambda f: f.check(), actual_recovery=lambda r: self.assertIs(r, self.f.store),
            state=lambda u: self.units[u])
        control = self.f.base / 'persistent-aware.conf'
        control.write_bytes(b'fixture compatible boot path')
        st = control.stat()
        self.prior = dict(completed=True, new_units=copy.deepcopy(self.units),
            actual_reader_custody={'main': {'pid': 1}, 'protected5650': {'pid': 2}},
            owned=[dict(path=str(control), identity=[st.st_dev, st.st_ino],
                        sha256=logs.sha(control.read_bytes()))])
        self.adapter = SimpleNamespace(check_readers=lambda s, c: self.observed.append(c))
        self.f.store.prefix = str(self.f.source).lstrip('/') + '/'

    def adopt(self):
        return resume.adopt_frozen_readers(base=self.base, adapter=self.adapter,
            spec={}, prior=self.prior, operation='12345678-0000-0000-0000-000000000099',
            fence=self.f.fence, recovery=self.f.store)

    def test_adoption_requires_held_fence_and_keeps_completed_batch(self):
        with self.assertRaises(ValueError):
            self.adopt()
        with self.f.fence.held():
            result = self.adopt()
            self.assertFalse(result['reader_restart_performed'])
            self.assertEqual(result['writer_binding'], self.f.fence.binding)
            self.assertEqual(result['capacity_released'], self.f.fence.released)
            self.assertTrue(self.verify()['verified'])
        self.assertEqual(len(self.observed), 1)

    def test_adoption_refuses_changed_or_thawed_owner(self):
        with self.f.fence.held():
            self.units['reader']['FreezerState'] = 'running'
            with self.assertRaisesRegex(ValueError, 'owner changed'):
                self.adopt()
            self.units['reader']['FreezerState'] = 'frozen'
            self.units['main']['InvocationID'] = 'foreign'
            with self.assertRaisesRegex(ValueError, 'owner changed'):
                self.adopt()

    def test_adoption_refuses_changed_persistent_boot_path(self):
        Path(self.prior['owned'][0]['path']).write_bytes(b'unknown boot path')
        with self.f.fence.held():
            with self.assertRaisesRegex(ValueError, 'boot configuration changed'):
                self.adopt()

    def test_adoption_propagates_real_reader_guard_failure(self):
        def refuse(*args):
            raise ValueError('namespace or binary changed')
        self.adapter.check_readers = refuse
        with self.f.fence.held():
            with self.assertRaisesRegex(ValueError, 'namespace or binary'):
                self.adopt()


class ReadbackSealTests(TestCase):
    setUp = ResumeTests.setUp
    def make_seal(self):
        def decode():
            for row in self.first['files']:
                self.assertEqual(logs.reconstruct(self.f.source / row['path'])['sha256'], row['sha256'])
        return resume.seal_readback(self.first, verify_decoded=decode, guard=self.f.fence.check)

    def test_seal_requires_real_custody_and_full_decoded_verifier(self):
        with self.assertRaises(ValueError):
            self.make_seal()
        with self.f.fence.held():
            seal = self.make_seal()
            self.assertTrue(resume.verify_readback_seal(self.first, seal, guard=self.f.fence.check)['lossless_versions_verified'])

    def test_object_corruption_invalidates_prior_verified_readback(self):
        with self.f.fence.held():
            seal = self.make_seal()
            path = self.f.source / self.first['files'][0]['path']
            key = logs.load_manifest(path)['chunks'][0]['sha256']
            obj = path.parent / '.log-objects' / (key + '.gz')
            raw = obj.read_bytes()
            obj.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
            with self.assertRaisesRegex(ValueError, 'seal changed'):
                resume.verify_readback_seal(self.first, seal, guard=self.f.fence.check)

    def test_concurrent_change_during_initial_decoded_check_refuses_seal(self):
        def changed():
            path = self.f.source / self.first['files'][0]['path']
            key = logs.load_manifest(path)['chunks'][0]['sha256']
            obj = path.parent / '.log-objects' / (key + '.gz')
            os.utime(obj, None)
        with self.f.fence.held():
            with self.assertRaisesRegex(ValueError, 'during decoded'):
                resume.seal_readback(self.first, verify_decoded=changed, guard=self.f.fence.check)

    def test_reader_failure_cannot_create_accepted_seal(self):
        def failed():
            raise ValueError('Decoded EOF refused')
        with self.f.fence.held():
            with self.assertRaisesRegex(ValueError, 'EOF refused'):
                resume.seal_readback(self.first, verify_decoded=failed, guard=self.f.fence.check)


if __name__ == '__main__':
    main()
