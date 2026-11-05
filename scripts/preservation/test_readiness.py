"""Small isolated Git fixtures; never launches a model or touches live records."""
import copy
import subprocess
import sys
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_turn_git as fixtures

m = fixtures.m


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.PreservationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.engine = self.fixture.engine
        self.request = dict(self.fixture.request, turn='readiness-owner', session='session',
                            expected_branch='feat/fixture', source_heads={'repo': self.fixture.base})

    def test_readiness_is_read_only_and_never_remote_or_provider_proof(self):
        before = sorted((str(p.relative_to(self.fixture.state)), p.read_bytes())
                        for p in self.fixture.state.rglob('*') if p.is_file())
        with patch.object(self.engine, 'remote', side_effect=AssertionError('network forbidden')):
            report = self.engine.preflight(self.request)
        self.assertEqual(report['code'], 'git_ready', report)
        self.assertFalse(report['provider_started'])
        self.assertFalse(report['coverage_verified'])
        self.assertFalse(report['reusable'])
        after = sorted((str(p.relative_to(self.fixture.state)), p.read_bytes())
                       for p in self.fixture.state.rglob('*') if p.is_file())
        self.assertEqual(before, after)
        self.assertFalse(self.engine.state_path(self.request).exists())

    def test_cli_rejection_is_structured_and_nonzero_without_launch(self):
        self.fixture.config['repositories'].clear()
        config = self.fixture.root / 'policy.json'
        config.write_text(json.dumps(self.fixture.config))
        result = subprocess.run([sys.executable, str(Path(m.__file__)), 'preflight', '--config', str(config)],
                                input=json.dumps(self.request), capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        report = json.loads(result.stdout)
        self.assertEqual(report['code'], 'publication_policy_missing')
        self.assertFalse(report['provider_started'])
        self.assertFalse(self.engine.state_path(self.request).exists())

    def test_missing_policy_fails_before_any_admission_side_effect(self):
        self.fixture.config['repositories'].clear()
        report = self.engine.preflight(self.request)
        self.assertEqual(report['code'], 'publication_policy_missing')
        self.assertFalse(self.engine.state_path(self.request).exists())

    def test_duplicate_canonical_paths_and_missing_root_refuse(self):
        aliased = dict(self.request['repositories'][0], id='alias', path=str(self.fixture.repo / '..' / 'repo'))
        self.request['repositories'].append(aliased)
        self.assertEqual(self.engine.preflight(self.request)['code'], 'inventory_invalid')
        self.request['repositories'] = [dict(id='repo', path=str(self.fixture.root / 'missing'))]
        self.assertEqual(self.engine.preflight(self.request)['state'], 'blocked')

    def test_native_head_and_expected_branch_are_not_reconstructed(self):
        for key, value in [('source_heads', {'repo': '0' * 40}), ('expected_branch', 'other')]:
            request = dict(self.request, **{key: value})
            self.assertEqual(self.engine.preflight(request)['code'], 'source_binding_changed')

    def test_untracked_denied_source_and_hidden_index_flags_stay_closed(self):
        (self.fixture.repo / '.env').write_text('fixture only')
        self.assertEqual(self.engine.preflight(self.request)['state'], 'blocked')
        (self.fixture.repo / '.env').unlink()
        fixtures.git(self.fixture.repo, 'update-index', '--assume-unchanged', 'src/main.txt')
        self.assertEqual(self.engine.preflight(self.request)['state'], 'blocked')

    def test_alias_canonicalization_is_retained_through_capture_and_launch_validation(self):
        self.request['repositories'][0]['path'] = str(self.fixture.repo / '..' / 'repo')
        record = self.engine.begin(self.request)
        self.assertEqual(record['inventory_version'], 1)
        stored = m.read_json(self.engine.state_path(self.request))
        self.assertEqual(stored['admitted_inventory'], [dict(id='repo', path=str(self.fixture.repo))])
        self.assertTrue(self.engine.validate_admission(self.request)['admission_validated'])
        result = self.engine.observe_finished(self.request)
        self.assertTrue(result['observation_complete'])
        self.assertEqual(result['terminal_inventory'], stored['admitted_inventory'])

    def test_request_order_is_not_an_inventory_change(self):
        a = dict(id='a', path=str(self.fixture.repo))
        other = self.fixture.root / 'second'
        other.mkdir()
        b = dict(id='b', path=str(other))
        self.assertEqual(m.inventory_identity([a, b]), m.inventory_identity([b, a]))

    def test_post_admission_changes_or_session_change_cannot_start_provider(self):
        self.engine.begin(self.request)
        changed_owner = dict(self.request, session='different-owner')
        with self.assertRaisesRegex(m.Blocked, 'owner binding'):
            self.engine.validate_admission(changed_owner)
        changed_scope = copy.deepcopy(self.request)
        changed_scope['repositories'][0]['required_files'] = ['src/main.txt']
        with self.assertRaisesRegex(m.Blocked, 'owner binding'):
            self.engine.validate_admission(changed_scope)
        changed_source = dict(self.request, source_heads={'repo': '0' * 40})
        with self.assertRaisesRegex(m.Blocked, 'owner binding'):
            self.engine.validate_admission(changed_source)
        self.fixture.changed(value='concurrent owner content\n')
        with self.assertRaisesRegex(m.Blocked, 'changed between admission'):
            self.engine.validate_admission(self.request)
        record = m.read_json(self.engine.state_path(self.request))
        self.assertFalse(record.get('observation_complete', False))

    def context(self):
        return dict(permissions='granted', toolchain_ready=True,
                    permissions_digest='1' * 64, toolchain_digest='2' * 64,
                    checkpoint_digest='3' * 64, profile_digest='4' * 64,
                    ownership_fence='owner-fence', allowed_actions=['read'], required_actions=['read'])

    def test_missing_permissions_and_toolchain_return_actionable_no_launch(self):
        request = dict(self.request, require_dispatch_context=True)
        report = self.engine.preflight(request)
        self.assertEqual(report['code'], 'permissions_required')
        self.assertTrue(report['human_needed'])
        context = self.context()
        context['required_actions'] = ['write']
        request['dispatch_context'] = context
        self.assertEqual(self.engine.preflight(request)['code'], 'permissions_required')
        context['required_actions'] = ['read']
        context['toolchain_ready'] = False
        self.assertEqual(self.engine.preflight(request)['code'], 'toolchain_unavailable')

    def test_bounded_receipt_reuse_rechecks_source_context_policy_and_expiry(self):
        request = dict(self.request, require_dispatch_context=True, dispatch_context=self.context())
        receipt = self.engine.preflight(request)
        self.assertTrue(receipt['reusable'])
        request['readiness_receipt'] = receipt
        self.assertEqual(self.engine.preflight(request)['code'], 'git_ready')
        changed_scope = copy.deepcopy(request)
        changed_scope['repositories'][0]['required_files'] = ['src/main.txt']
        self.assertEqual(self.engine.preflight(changed_scope)['code'], 'readiness_stale')
        for key in ['permissions_digest', 'toolchain_digest', 'checkpoint_digest', 'profile_digest', 'ownership_fence']:
            changed = copy.deepcopy(request)
            changed['dispatch_context'][key] = 'changed'
            self.assertEqual(self.engine.preflight(changed)['code'], 'readiness_stale')
        with patch.object(m.time, 'time', return_value=receipt['valid_until'] + 1):
            self.assertEqual(self.engine.preflight(request)['code'], 'readiness_stale')
        self.fixture.changed(value='concurrent source\n')
        self.assertEqual(self.engine.preflight(request)['code'], 'readiness_stale')

    def test_failed_snapshot_keeps_exact_inventory_and_does_not_claim_admitted_snapshot(self):
        (self.fixture.repo / 'src/link').symlink_to('main.txt')
        record = self.engine.begin(self.request)
        self.assertEqual(record['state'], 'blocked')
        self.assertTrue(record['observation_inventory'])
        self.assertNotIn('admitted_inventory', record)
        with self.assertRaises(m.Blocked):
            self.engine.validate_admission(self.request)
        self.fixture.changed(value='B after failed snapshot\n')
        result = self.engine.observe_finished(self.request)
        self.assertTrue(result['observation_complete'])
        saved = m.read_json(self.engine.state_path(self.request))
        self.assertEqual(saved['admission_failure'], record['admission_failure'])
        self.assertEqual(saved['repositories'], [])

    def test_malformed_cached_receipt_cannot_escape_structured_rejection(self):
        request = dict(self.request, require_dispatch_context=True, dispatch_context=self.context())
        receipt = self.engine.preflight(request)
        for broken in [[], dict(receipt, issued_at='not-a-time'), dict(receipt, valid_until=True)]:
            report = self.engine.preflight(dict(request, readiness_receipt=broken))
            self.assertEqual(report['code'], 'readiness_stale')
            self.assertFalse(report['provider_started'])

    def test_prior_nonversioned_capture_is_not_silently_assigned_an_owner(self):
        record = self.engine.begin(self.request)
        record.pop('session')
        record.pop('inventory_version')
        record.pop('admitted_inventory')
        m.atomic_json(self.engine.state_path(self.request), record)
        observed = self.engine.observe_finished(self.request)
        self.assertTrue(observed['observation_complete'])
        self.assertNotIn('session', observed)
        with self.assertRaisesRegex(m.Blocked, 'owner binding'):
            self.engine.validate_admission(self.request)

    def test_missing_expired_review_or_protected_branch_is_known_blocked(self):
        policy = self.fixture.config['repositories']['repo']
        saved = copy.deepcopy(policy)
        for field in ['publication_review', 'review_expires']:
            policy.pop(field)
            report = self.engine.preflight(self.request)
            self.assertEqual(report['state'], 'blocked')
            self.assertTrue(report['human_needed'])
            policy.update(saved)
        policy['review_expires'] = 0
        self.assertEqual(self.engine.preflight(self.request)['state'], 'blocked')
        policy.update(saved)
        policy['protected_branches'] = ['feat/fixture']
        self.assertEqual(self.engine.preflight(self.request)['state'], 'blocked')
