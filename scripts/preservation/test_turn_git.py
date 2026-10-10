#!/usr/bin/env python3
"""Real local Git/remotes, deterministic PR/scanner adapters. Never accesses live VK."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('turn_git', Path(__file__).with_name('turn_git.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def git(repo, *args):
    return m.git(repo, *args).decode().strip()


class FixtureEngine(m.Engine):
    def remote(self, repo, policy):
        m.require(git(repo, 'remote', 'get-url', policy['remote']) == policy['url'],
                  'fixture remote differs')
        return policy['remote']


class PreservationTests(unittest.TestCase):
    def setUp(self):
        root = os.environ.get('VK_PRESERVATION_TEST_ROOT')
        if not root or not Path(root).is_dir():
            raise RuntimeError('Set VK_PRESERVATION_TEST_ROOT to approved mounted fixture storage')
        self.temp = tempfile.TemporaryDirectory(dir=root, prefix='turn-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.remote = self.root / 'remote.git'
        git(self.repo, 'init', '-q', '-b', 'staging')
        git(self.repo, 'config', 'user.name', 'Fixture')
        git(self.repo, 'config', 'user.email', 'fixture@example.invalid')
        (self.repo / 'src').mkdir()
        (self.repo / 'src/main.txt').write_text('base\n')
        (self.repo / '.gitignore').write_text('runtime/\n')
        git(self.repo, 'add', '.')
        git(self.repo, 'commit', '-qm', 'fixture base')
        self.base = git(self.repo, 'rev-parse', 'HEAD')
        subprocess.run(['git', 'init', '-q', '--bare', str(self.remote)], check=True)
        git(self.repo, 'remote', 'add', 'origin', str(self.remote))
        git(self.repo, 'push', '-q', 'origin', 'staging')
        git(self.repo, 'switch', '-qc', 'feat/fixture')
        git(self.repo, 'push', '-q', 'origin', 'feat/fixture')
        self.state = self.root / 'state'
        self.state.mkdir()
        # Adapter fails on a sentinel anywhere in outgoing history, including deletions.
        self.scanner = self.root / 'scanner'
        self.scanner.write_text('''#!/usr/bin/env python3
import subprocess,sys
if sys.argv[1] == 'stdin':
    sys.exit(1 if b'FIXTURE_SECRET' in sys.stdin.buffer.read() else 0)
r=subprocess.run(['git','-C',sys.argv[2],'log','-p',*next(a.split('=',1)[1] for a in sys.argv if a.startswith('--log-opts=')).split()],capture_output=True)
if b'FIXTURE_SECRET' in r.stdout:
    print('FIXTURE_SECRET must never escape subprocess output')
    sys.exit(1)
sys.exit(r.returncode)
''')
        self.scanner.chmod(0o755)
        self.prfile = self.root / 'pr.json'
        self.gh = self.root / 'gh'
        self.gh.write_text('''#!/usr/bin/env python3
import json,subprocess,sys
from pathlib import Path
p=Path(%r)
args=sys.argv
if args[2]=='list' and not p.exists():
    print('[]')
    sys.exit(0)
head=subprocess.check_output(['git','--git-dir',%r,'rev-parse','refs/heads/feat/fixture']).decode().strip()
pr=dict(number=1,url='https://github.com/fixture/repo/pull/1',headRefName='feat/fixture',headRefOid=head,baseRefName='staging',state='OPEN',isDraft=True,headRepository={'name':'repo'},headRepositoryOwner={'login':'fixture'})
if args[2]=='create':
    if p.exists(): sys.exit(1)
    p.write_text(json.dumps(pr))
    print(pr['url'])
elif args[2]=='list': print(json.dumps([dict(json.loads(p.read_text()),headRefOid=head)] if p.exists() else []))
elif args[2]=='view': print(json.dumps(dict(json.loads(p.read_text()),headRefOid=head)))
else: sys.exit(1)
''' % (str(self.prfile), str(self.remote)))
        self.gh.chmod(0o755)
        mount = self.state
        while not mount.is_mount():
            mount = mount.parent
        self.config = dict(storage_mount=str(mount), state_root=str(self.state), scanner=str(self.scanner),
                           scanner_sha256=hashlib.sha256(self.scanner.read_bytes()).hexdigest(),
                           repositories={'repo': dict(common_dir=str(self.repo / '.git'), remote='origin',
                              url=str(self.remote), repository='fixture/repo', base_branch='staging',
                              base_commit=self.base, allowed=['src/main.txt', 'src/new file.txt', 'src/renamed.txt', 'src/link'],
                              workflow_digest=m.workflows(self.repo, self.base),
                              automation_branch='staging', automation_commit=self.base,
                              automation_workflow_digest=m.workflows(self.repo, self.base),
                              publication_review='fixture review, no network', review_expires=time.time()+3600)})
        self.engine = FixtureEngine(self.config, str(self.gh))
        self.request = dict(workspace='workspace', turn='turn', writers_fenced=True,
                            outcome='completed', repositories=[dict(id='repo', path=str(self.repo))])
        self.assertEqual(self.engine.begin(self.request)['state'], 'pending')

    def end(self):
        return self.engine.end(self.request)

    def changed(self, name='src/main.txt', value='changed\n'):
        (self.repo / name).write_text(value)

    def assertBlocked(self, contains):
        result = self.end()
        self.assertEqual(result['state'], 'blocked', result)
        self.assertIn(contains, result['reason'])
        return result

    def test_changed_tracked_and_untracked_exact_history_and_draft(self):
        self.changed()
        self.changed('src/new file.txt', 'untracked source\n')
        result = self.end()
        self.assertEqual(result['state'], 'verified', result)
        self.assertTrue(self.prfile.exists())
        self.assertEqual(git(self.repo, 'status', '--porcelain'), '')
        self.assertEqual(self.engine.check(self.request)['state'], 'verified')
        head = git(self.repo, 'rev-parse', 'HEAD')
        self.assertEqual(git(self.remote, 'rev-parse', 'refs/heads/feat/fixture'), head)
        self.assertEqual(git(self.repo, 'rev-list', '--count', self.base+'..HEAD'), '1')
        self.assertEqual(self.end()['state'], 'verified')
        self.assertEqual(git(self.repo, 'rev-parse', 'HEAD'), head)

    def test_read_only_no_empty_commit_or_pr(self):
        self.assertEqual(self.end()['state'], 'verified')
        self.assertFalse(self.prfile.exists())
        self.assertEqual(git(self.repo, 'rev-parse', 'HEAD'), self.base)

    def test_failed_and_interrupted_turns_preserve_work_without_success_claim(self):
        for outcome in ['failed', 'killed']:
            with self.subTest(outcome=outcome):
                # Separate turns; failure outcome belongs to executor, not Git coverage.
                if outcome == 'killed':
                    self.request['turn'] = 'turn2'
                    self.assertEqual(self.engine.begin(self.request)['state'], 'pending')
                self.request['outcome'] = outcome
                self.changed(value=outcome)
                result = self.end()
                self.assertEqual(result['state'], 'verified', result)
                self.assertEqual(result['outcome'], outcome)

    def test_missing_end_blocks_controller(self):
        with self.assertRaisesRegex(m.Blocked, 'pending'):
            self.engine.check(self.request)

    def test_new_edit_after_receipt_blocks(self):
        self.changed()
        self.assertEqual(self.end()['state'], 'verified')
        self.changed(value='later edit')
        with self.assertRaisesRegex(m.Blocked, 'after earlier receipt'):
            self.engine.check(self.request)
        self.assertBlocked('after earlier receipt')

    def test_excluded_untracked_does_not_upload(self):
        self.changed('.env', 'not a credential, excluded anyway')
        self.assertBlocked('excluded')
        self.assertEqual(git(self.repo, 'rev-parse', 'HEAD'), self.base)
        self.assertEqual(git(self.remote, 'rev-parse', 'refs/heads/feat/fixture'), self.base)

    def test_ignored_delta_is_unprotected_and_blocked(self):
        (self.repo / 'runtime').mkdir()
        self.changed('runtime/state.txt', 'ignored data')
        self.assertBlocked('ignored files changed')

    def test_unchanged_ignored_inventory_explicitly_unprotected(self):
        (self.repo / 'runtime').mkdir()
        self.changed('runtime/state.txt', 'ignored data')
        self.request['turn'] = 'with-ignored'
        self.engine.begin(self.request)
        result = self.end()
        self.assertEqual(result['state'], 'verified')
        self.assertEqual(result['repositories'][0]['receipt']['ignored_not_git_protected'], ['runtime/state.txt'])

    def test_private_intermediate_commit_cannot_be_hidden_by_deletion(self):
        self.changed('customer.csv', 'private fixture')
        git(self.repo, 'add', 'customer.csv')
        git(self.repo, 'commit', '-qm', 'private')
        (self.repo / 'customer.csv').unlink()
        git(self.repo, 'add', 'customer.csv')
        git(self.repo, 'commit', '-qm', 'remove')
        self.assertBlocked('excluded')

    def test_secret_in_eligible_source_never_pushed_and_output_redacted(self):
        self.changed(value='FIXTURE_SECRET')
        result = self.assertBlocked('scanner stdin failed')
        self.assertNotIn('FIXTURE_SECRET', json.dumps(result))
        self.assertEqual(git(self.repo, 'rev-parse', 'HEAD'), self.base)

    def test_missing_remote_and_network_failure(self):
        git(self.repo, 'remote', 'remove', 'origin')
        self.changed()
        self.assertBlocked('git remote failed')

    def test_unavailable_remote_stays_blocked(self):
        url = str(self.root / 'nonexistent.git')
        git(self.repo, 'remote', 'set-url', 'origin', url)
        self.config['repositories']['repo']['url'] = url
        # Re-admit with this valid but unavailable fixture destination.
        self.request['turn'] = 'offline'
        self.engine.begin(self.request)
        self.changed()
        self.assertBlocked('git ls-remote failed')

    def test_existing_local_commits_verified_exactly(self):
        self.changed()
        git(self.repo, 'add', 'src/main.txt')
        git(self.repo, 'commit', '-qm', 'agent-authored commit')
        head = git(self.repo, 'rev-parse', 'HEAD')
        self.assertEqual(self.end()['state'], 'verified')
        self.assertEqual(git(self.remote, 'rev-parse', 'refs/heads/feat/fixture'), head)

    def test_read_only_unsynced_history_blocks_without_manufacturing_pr(self):
        self.changed()
        git(self.repo, 'add', 'src/main.txt')
        git(self.repo, 'commit', '-qm', 'pre-existing unsynced work')
        self.request['turn'] = 'read-only'
        self.engine.begin(self.request)
        self.assertBlocked('remote branch does not equal')
        self.assertFalse(self.prfile.exists())

    def test_changed_remote_after_receipt_blocks(self):
        self.changed()
        self.assertEqual(self.end()['state'], 'verified')
        git(self.remote, 'update-ref', 'refs/heads/feat/fixture', self.base)
        with self.assertRaisesRegex(m.Blocked, 'remote branch does not equal'):
            self.engine.check(self.request)

    def test_inventory_omission_or_wrong_turn_cannot_clear_gate(self):
        self.assertEqual(self.end()['state'], 'verified')
        bad = copy.deepcopy(self.request)
        bad['repositories'] = []
        with self.assertRaisesRegex(m.Blocked, 'empty affected'):
            self.engine.check(bad)
        bad = copy.deepcopy(self.request)
        bad['turn'] = 'unknown-turn'
        with self.assertRaisesRegex(m.Blocked, 'missing'):
            self.engine.check(bad)

    def test_policy_change_invalidates_old_receipt(self):
        self.assertEqual(self.end()['state'], 'verified')
        self.config['repositories']['repo']['allowed'].append('other/*')
        with self.assertRaisesRegex(m.Blocked, 'policy differs'):
            self.engine.check(self.request)

    def test_unfenced_writer_and_index_lock_block(self):
        self.request['writers_fenced'] = False
        self.assertBlocked('writers are not fenced')
        self.request['writers_fenced'] = True
        self.changed()
        (self.repo / '.git/index.lock').write_text('other Git writer')
        self.assertBlocked('index is locked')
        self.assertTrue((self.repo / '.git/index.lock').exists())

    def test_compare_snapshot_detects_writer_during_scanning(self):
        original = self.engine.scan
        def scan(repo, policy, head):
            original(repo, policy, head)
            self.changed(value='concurrent writer')
        self.engine.scan = scan
        self.changed()
        self.assertBlocked('concurrent writer')
        self.assertEqual(git(self.repo, 'rev-parse', 'HEAD'), self.base)

    def test_closed_pr_after_receipt_blocks(self):
        self.changed()
        self.assertEqual(self.end()['state'], 'verified')
        pr = json.loads(self.prfile.read_text())
        pr['state'] = 'CLOSED'
        self.prfile.write_text(json.dumps(pr))
        with self.assertRaisesRegex(m.Blocked, 'PR does not cover'):
            self.engine.check(self.request)

    def test_protected_branch_symlink_and_unreviewed_workflow_block(self):
        git(self.repo, 'switch', '-q', 'staging')
        self.assertBlocked('branch changed')
        git(self.repo, 'switch', '-q', 'feat/fixture')
        (self.repo / 'src/link').symlink_to('/etc/passwd')
        self.assertBlocked('symlink')
        (self.repo / 'src/link').unlink()
        self.config['repositories']['repo']['publication_review'] = ''
        self.request['turn'] = 'no-review'
        self.engine.begin(self.request)
        self.changed()
        self.assertBlocked('automation review absent')

    def test_rename_deletion_and_staged_unstaged_source(self):
        git(self.repo, 'mv', 'src/main.txt', 'src/renamed.txt')
        self.changed('src/renamed.txt', 'unstaged over staged rename')
        result = self.end()
        self.assertEqual(result['state'], 'verified', result)
        self.assertFalse((self.repo / 'src/main.txt').exists())
        self.assertEqual(git(self.repo, 'show', 'HEAD:src/renamed.txt'), 'unstaged over staged rename')

    def test_newer_pending_turn_invalidates_old_verified_receipt(self):
        self.assertEqual(self.end()['state'], 'verified')
        newer = dict(self.request, turn='later-turn')
        self.assertEqual(self.engine.begin(newer)['state'], 'pending')
        with self.assertRaisesRegex(m.Blocked, 'newer turn'):
            self.engine.check(self.request)

    def test_read_only_new_branch_uses_exact_base_witness(self):
        git(self.remote, 'update-ref', '-d', 'refs/heads/feat/fixture')
        result = self.end()
        self.assertEqual(result['state'], 'verified', result)
        self.assertEqual(result['repositories'][0]['receipt']['ref'], 'refs/heads/staging')
        self.assertFalse(self.prfile.exists())
        self.assertEqual(self.engine.check(self.request)['state'], 'verified')

    def test_source_only_receipt_is_not_original_history_evidence(self):
        self.assertEqual(self.end()['state'], 'verified')
        path = self.engine.state_path(self.request)
        record = m.read_json(path)
        record['repositories'][0]['receipt']['proof'] = 'source-only-checkpoint'
        m.atomic_json(path, record)
        with self.assertRaisesRegex(m.Blocked, 'source-only'):
            self.engine.check(self.request)

    def test_missing_original_commit_is_not_replaced_with_source_checkpoint(self):
        self.request['turn'] = 'requires-original'
        self.request['repositories'][0]['required_commits'] = ['a' * 40]
        self.engine.begin(self.request)
        self.changed()
        self.assertBlocked('merge-base failed')
        self.assertEqual(git(self.remote, 'rev-parse', 'refs/heads/feat/fixture'), self.base)

    def test_history_secret_removed_later_is_still_blocked(self):
        self.changed(value='FIXTURE_SECRET')
        git(self.repo, 'add', 'src/main.txt')
        git(self.repo, 'commit', '-qm', 'intermediate secret')
        self.changed(value='safe current bytes')
        git(self.repo, 'add', 'src/main.txt')
        git(self.repo, 'commit', '-qm', 'remove secret')
        self.assertBlocked('scanner stdin failed')
        self.assertEqual(git(self.remote, 'rev-parse', 'refs/heads/feat/fixture'), self.base)

    def test_existing_pr_is_reused_and_ambiguous_create_is_reconciled(self):
        self.changed()
        self.assertEqual(self.end()['state'], 'verified')
        newer = dict(self.request, turn='next-turn')
        self.engine.begin(newer)
        self.request = newer
        self.changed(value='new source')
        self.assertEqual(self.end()['state'], 'verified')
        self.assertEqual(json.loads(self.prfile.read_text())['number'], 1)
        self.assertEqual(self.engine.check_all(dict(writers_fenced=True, turns=[self.request]))['state'], 'verified')
        with self.assertRaisesRegex(m.Blocked, 'empty affected turn'):
            self.engine.check_all(dict(writers_fenced=True, turns=[]))

    def test_index_flags_conflicts_and_binary_are_not_silently_ignored(self):
        git(self.repo, 'update-index', '--assume-unchanged', 'src/main.txt')
        self.assertBlocked('hidden index flags')
        git(self.repo, 'update-index', '--no-assume-unchanged', 'src/main.txt')
        self.changed(value='binary\0fixture')
        self.assertBlocked('binary source')

    def test_expired_or_changed_automation_review_blocks_before_upload(self):
        self.config['repositories']['repo']['review_expires'] = 0
        self.request['turn'] = 'expired-review'
        self.engine.begin(self.request)
        self.changed()
        self.assertBlocked('automation review absent')
        self.assertEqual(git(self.remote, 'rev-parse', 'refs/heads/feat/fixture'), self.base)

    def test_multiple_repositories_recheck_earlier_workspace_during_gate(self):
        second = PreservationTests()
        second.setUp()
        self.addCleanup(second.doCleanups)
        self.config['repositories']['second'] = second.config['repositories']['repo']
        self.request['turn'] = 'multi-repo'
        self.request['repositories'].append(dict(id='second', path=str(second.repo)))
        self.engine.begin(self.request)
        self.assertEqual(self.end()['state'], 'verified')
        original = self.engine.check_repo
        def check(entry, policy):
            original(entry, policy)
            if entry['id'] == 'second':
                self.changed(value='writer appeared after first repo check')
        self.engine.check_repo = check
        with self.assertRaisesRegex(m.Blocked, 'earlier repository changed'):
            self.engine.check(self.request)

    def test_required_ignored_private_file_cannot_claim_git_protection(self):
        (self.repo / 'runtime').mkdir()
        self.changed('runtime/state.txt', 'private fixture')
        self.request['turn'] = 'requires-private-file'
        self.request['repositories'][0]['required_files'] = ['runtime/state.txt']
        self.engine.begin(self.request)
        self.assertBlocked('excluded')

    def test_runtime_visibility_failure_invalidates_controller_receipt(self):
        self.assertEqual(self.end()['state'], 'verified')
        self.engine.block(dict(self.request, reason='summary persistence failed'))
        with self.assertRaisesRegex(m.Blocked, 'blocked'):
            self.engine.check(self.request)

    def test_later_turn_cannot_drop_observed_original_history(self):
        self.changed(value='FIXTURE_SECRET')
        git(self.repo, 'add', 'src/main.txt')
        git(self.repo, 'commit', '-qm', 'withheld original commit')
        self.assertBlocked('scanner stdin failed')
        # Model a source-only replacement in this disposable fixture; never a live operation.
        git(self.repo, 'update-ref', 'refs/heads/feat/fixture', self.base)
        git(self.repo, 'read-tree', self.base)
        self.changed(value='base\n')
        self.request['turn'] = 'source-only-replacement'
        self.engine.begin(self.request)
        self.assertBlocked('merge-base failed')

    def test_missing_expected_storage_mount_blocks_without_fallback(self):
        config = dict(self.config, storage_mount=str(self.root / 'unmounted'))
        with self.assertRaisesRegex(m.Blocked, 'not mounted'):
            FixtureEngine(config, str(self.gh))

    def test_existing_pr_wrong_base_blocks_before_pushing_new_work(self):
        self.changed()
        self.assertEqual(self.end()['state'], 'verified')
        old = git(self.remote, 'rev-parse', 'refs/heads/feat/fixture')
        pr = json.loads(self.prfile.read_text())
        pr['baseRefName'] = 'main'
        self.prfile.write_text(json.dumps(pr))
        self.request['turn'] = 'wrong-pr-base'
        self.engine.begin(self.request)
        self.changed(value='later source')
        self.assertBlocked('PR does not cover')
        self.assertEqual(git(self.remote, 'rev-parse', 'refs/heads/feat/fixture'), old)

    def test_push_network_failure_stays_blocked_then_retries_same_commit(self):
        self.changed()
        original = m.git
        def offline(repo, *args, **kwargs):
            if args[0] == 'push':
                raise m.Blocked('fixture network failed during push')
            return original(repo, *args, **kwargs)
        m.git = offline
        try:
            self.assertBlocked('network failed during push')
        finally:
            m.git = original
        local = git(self.repo, 'rev-parse', 'HEAD')
        self.assertNotEqual(local, self.base)
        self.assertEqual(git(self.remote, 'rev-parse', 'refs/heads/feat/fixture'), self.base)
        with self.assertRaisesRegex(m.Blocked, 'blocked'):
            self.engine.check(self.request)
        self.assertEqual(self.end()['state'], 'verified')
        self.assertEqual(git(self.repo, 'rev-parse', 'HEAD'), local)
        self.assertEqual(git(self.remote, 'rev-parse', 'refs/heads/feat/fixture'), local)

    def test_uncertain_pr_creation_is_reconciled_without_duplicate_create(self):
        self.changed()
        original = m.run
        calls = []
        def uncertain(args, *rest, **kwargs):
            result = original(args, *rest, **kwargs)
            if args[:3] == [str(self.gh), 'pr', 'create']:
                calls.append('created')
                raise m.Blocked('fixture PR response lost after server created draft')
            return result
        m.run = uncertain
        try:
            self.assertBlocked('response lost')
            self.assertEqual(self.end()['state'], 'verified')
            self.assertEqual(calls, ['created'])
        finally:
            m.run = original

    def test_cli_malformed_or_missing_receipt_exits_blocked(self):
        config = self.root / 'config.json'
        config.write_text(json.dumps(self.config))
        for payload in ['{invalid', json.dumps(dict(self.request, turn='unknown'))]:
            result = subprocess.run(['python3', str(Path(__file__).with_name('turn_git.py')),
                                     'check', '--config', str(config)], input=payload,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)['state'], 'blocked')

    def use_real_scanner(self):
        scanner = os.environ.get('VK_TEST_GITLEAKS')
        if not scanner:
            self.skipTest('set VK_TEST_GITLEAKS to the approved real binary')
        self.config.update(scanner=scanner,
                           scanner_sha256=hashlib.sha256(Path(scanner).read_bytes()).hexdigest())
        self.request['turn'] = 'real-review'
        self.engine.begin(self.request)

    def synthetic_secret(self):
        return 'FIXTURE_SECRET github_token = "ghp_' + 'x7H4q2N9p5Z8s3V6r1L0a4B7c9D2e5F8g0J3' + '"\n'

    def commit_secret(self):
        self.changed(value=self.synthetic_secret())
        git(self.repo, 'add', 'src/main.txt')
        git(self.repo, 'commit', '-qm', 'withheld synthetic original')
        return git(self.repo, 'rev-parse', 'HEAD')

    def fixture_return_to_base(self):
        # Only this owned disposable repository. No reset/rewrites of development work.
        git(self.repo, 'update-ref', 'refs/heads/feat/fixture', self.base)
        git(self.repo, 'read-tree', self.base)
        self.changed(value='base\n')

    def assert_not_published(self):
        self.assertEqual(git(self.remote, 'rev-parse', 'refs/heads/feat/fixture'), self.base)
        self.assertFalse(self.prfile.exists())
        with self.assertRaises(m.Blocked):
            self.engine.check(self.request)

    def replacement_attack(self):
        original = self.commit_secret()
        git(self.repo, 'replace', original, self.base)
        self.assertBlocked('failed')
        self.assert_not_published()

    def test_replacement_objects_do_not_hide_original_blobs(self):
        self.replacement_attack()

    def test_real_scanner_replacement_objects_do_not_hide_original_blobs(self):
        self.use_real_scanner()
        self.replacement_attack()

    def attribute_attack(self, attribute):
        (self.repo / '.git/info/attributes').write_text('src/main.txt ' + attribute + '\n')
        git(self.repo, 'config', 'diff.fixture.command', '/bin/true')
        git(self.repo, 'config', 'diff.fixture.textconv', '/bin/true')
        self.changed(value=self.synthetic_secret())
        self.assertBlocked('failed')
        self.assert_not_published()
        self.assertEqual(git(self.repo, 'rev-parse', 'HEAD'), self.base)

    def test_diff_attributes_do_not_hide_automatic_commit_blobs(self):
        self.attribute_attack('-diff')

    def test_real_scanner_diff_attributes_do_not_hide_automatic_commit_blobs(self):
        self.use_real_scanner()
        self.attribute_attack('-diff')

    def test_real_scanner_custom_diff_driver_cannot_hide_blobs(self):
        self.use_real_scanner()
        self.attribute_attack('diff=fixture')

    def retry_original_attack(self):
        original = self.commit_secret()
        self.assertBlocked('failed')
        self.fixture_return_to_base()
        self.assertBlocked('merge-base failed')
        self.assert_not_published()
        self.assertIn(original, json.dumps(m.read_json(self.engine.state_path(self.request))))

    def test_same_turn_retry_retains_original_head(self):
        self.retry_original_attack()

    def test_real_scanner_same_turn_retry_retains_original_head(self):
        self.use_real_scanner()
        self.retry_original_attack()

    def test_failed_admission_retains_original_before_snapshot_failure(self):
        original = self.commit_secret()
        git(self.repo, 'update-index', '--assume-unchanged', 'src/main.txt')
        self.request['turn'] = 'failed-admission'
        self.assertEqual(self.engine.begin(self.request)['state'], 'blocked')
        git(self.repo, 'update-index', '--no-assume-unchanged', 'src/main.txt')
        self.fixture_return_to_base()
        self.request['turn'] = 'after-failed-admission'
        self.engine.begin(self.request)
        self.assertBlocked('merge-base failed')
        self.assert_not_published()
        self.assertIn(original, json.dumps(m.read_json(self.engine.state_path(self.request))))

    def test_failed_empty_admission_cannot_erase_prior_originals(self):
        self.commit_secret()
        self.assertBlocked('failed')
        original_inventory = self.request['repositories']
        self.request['turn'] = 'failed-empty'
        self.request['repositories'] = []
        self.assertEqual(self.engine.begin(self.request)['state'], 'blocked')
        self.fixture_return_to_base()
        self.request['turn'] = 'after-empty'
        self.request['repositories'] = original_inventory
        self.engine.begin(self.request)
        self.assertBlocked('merge-base failed')
        self.assert_not_published()

    def test_legacy_receipt_is_rejected_by_check_and_end(self):
        self.assertEqual(self.end()['state'], 'verified')
        path = self.engine.state_path(self.request)
        record = m.read_json(path)
        record['version'] = 1
        m.atomic_json(path, record)
        for action in [self.engine.check, self.engine.end]:
            with self.assertRaisesRegex(m.Blocked, 'unsupported'):
                action(self.request)

    def test_real_scanner_environment_and_allow_comments_cannot_weaken_scan(self):
        self.use_real_scanner()
        self.changed(value=self.synthetic_secret().rstrip() + ' # gitleaks:allow\n')
        with patch.dict(os.environ, {
            'GITLEAKS_CONFIG': str(self.root / 'missing-config'),
            'GITLEAKS_CONFIG_TOML': '[allowlist]\nregexes = [".*"]\n',
            'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'diff.external',
            'GIT_CONFIG_VALUE_0': '/bin/true', 'GIT_DIR': str(self.remote),
            'GIT_WORK_TREE': str(self.root), 'GIT_NO_REPLACE_OBJECTS': '0',
        }):
            self.assertBlocked('gitleaks stdin failed')
        self.assert_not_published()

    def test_real_scanner_deleted_intermediate_secret_cannot_be_hidden(self):
        self.use_real_scanner()
        self.commit_secret()
        self.changed(value='safe current source\n')
        git(self.repo, 'add', 'src/main.txt')
        git(self.repo, 'commit', '-qm', 'remove intermediate synthetic secret')
        self.assertBlocked('gitleaks stdin failed')
        self.assert_not_published()

    def test_real_scanner_raw_blob_covers_secret_in_unchanged_lines(self):
        self.use_real_scanner()
        # A fixture base with a secret demonstrates that scanning only added diff
        # lines is insufficient when publishing a modified original blob.
        self.changed(value=self.synthetic_secret() + 'old line\n')
        git(self.repo, 'add', 'src/main.txt')
        git(self.repo, 'commit', '-qm', 'fixture secret base')
        base = git(self.repo, 'rev-parse', 'HEAD')
        policy = self.config['repositories']['repo']
        policy.update(base_commit=base, automation_commit=base,
                      workflow_digest=m.workflows(self.repo, base),
                      automation_workflow_digest=m.workflows(self.repo, base))
        git(self.repo, 'push', '-q', 'origin', 'HEAD:staging')
        self.request['turn'] = 'changed-unchanged-line'
        self.engine.begin(self.request)
        self.changed(value=self.synthetic_secret() + 'new line\n')
        self.assertBlocked('gitleaks stdin failed')
        self.assert_not_published()

    def test_real_scanner_binary_attributes_do_not_admit_binary_source(self):
        self.use_real_scanner()
        (self.repo / '.git/info/attributes').write_text('src/main.txt -diff\n')
        self.changed(value=self.synthetic_secret() + '\0')
        self.assertBlocked('binary source')
        self.assert_not_published()

    def test_real_scanner_binary_intermediate_history_blocks(self):
        self.use_real_scanner()
        self.changed(value='binary\0fixture')
        git(self.repo, 'add', 'src/main.txt')
        git(self.repo, 'commit', '-qm', 'binary original')
        self.changed(value='safe current source\n')
        git(self.repo, 'add', 'src/main.txt')
        git(self.repo, 'commit', '-qm', 'text replacement')
        self.assertBlocked('binary outgoing')
        self.assert_not_published()

    def test_real_scanner_fresh_check_rescans_receipt_original_objects(self):
        self.use_real_scanner()
        # Produce a deliberately false scanner receipt, then restore the approved
        # real scanner before check. This models a suspect receipt, not a bypass.
        original_scan = self.engine.scan
        self.engine.scan = lambda *args: None
        self.commit_secret()
        self.assertEqual(self.end()['state'], 'verified')
        self.engine.scan = original_scan
        head = git(self.repo, 'rev-parse', 'HEAD')
        git(self.repo, 'replace', head, self.base)
        (self.repo / '.git/info/attributes').write_text('src/main.txt -diff\n')
        with self.assertRaisesRegex(m.Blocked, 'gitleaks stdin failed'):
            self.engine.check(self.request)
        self.assertBlocked('gitleaks stdin failed')

    def test_receipt_without_original_ledger_is_unsupported(self):
        self.assertEqual(self.end()['state'], 'verified')
        path = self.engine.state_path(self.request)
        record = m.read_json(path)
        del record['obligations']
        m.atomic_json(path, record)
        with self.assertRaisesRegex(m.Blocked, 'missing original'):
            self.engine.check(self.request)

    def test_auto_commit_original_is_durable_before_branch_update(self):
        self.changed()
        original = m.git
        def stop_before_exposing_head(repo, *args, **kwargs):
            if args[0] == 'update-ref':
                record = m.read_json(self.engine.state_path(self.request))
                self.assertIn(args[2], record['obligations']['repo']['commits'])
                raise m.Blocked('fixture branch update interrupted')
            return original(repo, *args, **kwargs)
        with patch.object(m, 'git', stop_before_exposing_head):
            self.assertBlocked('branch update interrupted')
        # The generated original is still required even if CAS never exposed it.
        self.fixture_return_to_base()
        self.assertBlocked('merge-base failed')
        self.assert_not_published()

    def test_multi_repository_end_failure_keeps_all_observed_originals(self):
        second = PreservationTests()
        second.setUp()
        self.addCleanup(second.doCleanups)
        self.config['repositories']['second'] = second.config['repositories']['repo']
        self.request['turn'] = 'multi-originals'
        self.request['repositories'].append(dict(id='second', path=str(second.repo)))
        self.engine.begin(self.request)
        self.commit_secret()
        second_head = second.commit_secret()
        self.assertBlocked('scanner stdin failed')
        record = m.read_json(self.engine.state_path(self.request))
        self.assertIn(second_head, record['obligations']['second']['commits'])
        self.fixture_return_to_base()
        second.fixture_return_to_base()
        self.assertBlocked('merge-base failed')

    def test_failed_multi_repository_admission_keeps_later_original(self):
        second = PreservationTests()
        second.setUp()
        self.addCleanup(second.doCleanups)
        self.config['repositories']['second'] = second.config['repositories']['repo']
        second_head = second.commit_secret()
        git(self.repo, 'update-index', '--assume-unchanged', 'src/main.txt')
        self.request['turn'] = 'multi-failed-admission'
        self.request['repositories'].append(dict(id='second', path=str(second.repo)))
        self.assertEqual(self.engine.begin(self.request)['state'], 'blocked')
        record = m.read_json(self.engine.state_path(self.request))
        self.assertIn(second_head, record['obligations']['second']['commits'])
        git(self.repo, 'update-index', '--no-assume-unchanged', 'src/main.txt')
        second.fixture_return_to_base()
        self.request['turn'] = 'multi-after-failure'
        self.engine.begin(self.request)
        self.assertBlocked('merge-base failed')

    def test_unverifiable_original_observation_cannot_be_cleared_by_retry(self):
        original = m.git
        def missing_head(repo, *args, **kwargs):
            if args[:3] == ('rev-parse', '--verify', 'HEAD^{commit}'):
                raise m.Blocked('fixture original head unavailable')
            return original(repo, *args, **kwargs)
        with patch.object(m, 'git', missing_head):
            self.assertBlocked('unverifiable')
        with self.assertRaisesRegex(m.Blocked, 'unverifiable'):
            self.end()
        self.request['turn'] = 'after-unverifiable'
        self.assertEqual(self.engine.begin(self.request)['state'], 'blocked')

    def test_original_obligations_survive_repeated_blocked_retries(self):
        first = self.commit_secret()
        self.assertBlocked('scanner stdin failed')
        self.fixture_return_to_base()
        self.changed(value='another original\n')
        git(self.repo, 'add', 'src/main.txt')
        git(self.repo, 'commit', '-qm', 'divergent second original')
        second = git(self.repo, 'rev-parse', 'HEAD')
        self.assertBlocked('merge-base failed')
        self.fixture_return_to_base()
        self.assertBlocked('merge-base failed')
        record = m.read_json(self.engine.state_path(self.request))
        self.assertIn(first, record['obligations']['repo']['commits'])
        self.assertIn(second, record['obligations']['repo']['commits'])
        self.assert_not_published()

    def test_later_admission_cannot_omit_an_original_repository(self):
        second = PreservationTests()
        second.setUp()
        self.addCleanup(second.doCleanups)
        self.config['repositories']['second'] = second.config['repositories']['repo']
        self.request['turn'] = 'complete-inventory'
        self.request['repositories'].append(dict(id='second', path=str(second.repo)))
        self.engine.begin(self.request)
        second.commit_secret()
        self.assertBlocked('scanner stdin failed')
        self.request['turn'] = 'omitted-original'
        self.request['repositories'].pop()
        result = self.engine.begin(self.request)
        self.assertEqual(result['state'], 'blocked')
        self.assertIn('original repository inventory omitted', result['reason'])
        with self.assertRaises(m.Blocked):
            self.engine.check(self.request)

    def test_real_scanner_scans_original_commit_messages(self):
        self.use_real_scanner()
        self.changed()
        git(self.repo, 'add', 'src/main.txt')
        git(self.repo, 'commit', '-qm', self.synthetic_secret())
        self.assertBlocked('gitleaks stdin failed')
        self.assert_not_published()

    def test_real_scanner_rejects_large_single_line_and_non_utf8_objects(self):
        self.use_real_scanner()
        self.changed(value='safe ' * 20000 + self.synthetic_secret())
        self.assertBlocked('gitleaks stdin failed')
        self.assert_not_published()
        (self.repo / 'src/main.txt').write_bytes(b'non-utf8 \xff')
        self.assertBlocked('non-text source')
        self.assert_not_published()

    def test_scanner_binary_hash_change_invalidates_fresh_receipt(self):
        self.assertEqual(self.end()['state'], 'verified')
        self.scanner.write_text('#!/bin/sh\nexit 0\n')
        with self.assertRaisesRegex(m.Blocked, 'scanner missing or changed'):
            self.engine.check(self.request)

    def graft_attack(self):
        self.commit_secret()
        self.changed(value='safe latest bytes\n')
        git(self.repo, 'add', 'src/main.txt')
        git(self.repo, 'commit', '-qm', 'hide intermediate secret with legacy graft')
        head = git(self.repo, 'rev-parse', 'HEAD')
        (self.repo / '.git/info/grafts').write_text(head + ' ' + self.base + '\n')
        self.assertBlocked('failed')
        self.assert_not_published()

    def test_legacy_grafts_cannot_hide_intermediate_originals(self):
        self.graft_attack()

    def test_real_scanner_legacy_grafts_cannot_hide_intermediate_originals(self):
        self.use_real_scanner()
        self.graft_attack()

    def test_batch_check_invalidates_any_receipt_or_history_mutation(self):
        self.assertEqual(self.end()['state'], 'verified')
        path = self.engine.state_path(self.request)
        original_record = m.read_json(path)
        original_check = self.engine.check
        for field, value in [('version', 1), ('obligations', {}),
                             ('config', 'changed'), ('reason', 'new evidence')]:
            with self.subTest(field=field):
                m.atomic_json(path, original_record)
                calls = []
                def check(request):
                    result = original_check(request)
                    calls.append(True)
                    if len(calls) == 2:
                        changed = m.read_json(path)
                        changed[field] = value
                        m.atomic_json(path, changed)
                    return result
                with patch.object(self.engine, 'check', check):
                    with self.assertRaisesRegex(m.Blocked, 'changed during batch check'):
                        self.engine.check_all(dict(writers_fenced=True,
                                                   turns=[self.request, self.request]))
        m.atomic_json(path, original_record)

    def test_changed_receipt_without_pr_cannot_verify(self):
        self.changed()
        self.assertEqual(self.end()['state'], 'verified')
        path = self.engine.state_path(self.request)
        record = m.read_json(path)
        del record['repositories'][0]['receipt']['pr']
        m.atomic_json(path, record)
        with self.assertRaisesRegex(m.Blocked, 'no covering PR'):
            self.engine.check(self.request)

    def test_clean_filter_cannot_claim_unpublished_worktree_bytes(self):
        (self.repo / '.git/info/attributes').write_text('src/main.txt filter=fixture\n')
        git(self.repo, 'config', 'filter.fixture.clean', "cat >/dev/null; printf 'base\\n'")
        self.changed(value=self.synthetic_secret())
        git(self.repo, 'add', 'src/main.txt')
        self.assertEqual(git(self.repo, 'status', '--porcelain'), '')
        self.assertBlocked('working bytes or modes differ')
        self.assert_not_published()

    def test_disabled_filemode_cannot_claim_unpublished_executable_change(self):
        git(self.repo, 'config', 'core.filemode', 'false')
        (self.repo / 'src/main.txt').chmod(0o755)
        self.assertEqual(git(self.repo, 'status', '--porcelain'), '')
        self.assertBlocked('working bytes or modes differ')
        self.assert_not_published()

    def test_real_scanner_clean_work_publishes_and_fresh_check_verifies(self):
        self.use_real_scanner()
        self.changed(value='safe original source with real scanner\n')
        self.changed('src/new file.txt', 'safe untracked source\n')
        result = self.end()
        self.assertEqual(result['state'], 'verified', result)
        self.assertEqual(self.engine.check(self.request)['state'], 'verified')
        self.assertEqual(self.engine.check_all(dict(writers_fenced=True,
                                                   turns=[self.request]))['state'], 'verified')
        self.assertEqual(git(self.remote, 'rev-parse', 'refs/heads/feat/fixture'),
                         git(self.repo, 'rev-parse', 'HEAD'))
        self.assertTrue(self.prfile.exists())

    def test_scanner_configuration_in_repo_cannot_weaken_real_scan(self):
        scanner = os.environ.get('VK_TEST_GITLEAKS')
        if not scanner:
            self.skipTest('optional installed Gitleaks acceptance; fixture adapter covers contract')
        self.config.update(scanner=scanner, scanner_sha256=hashlib.sha256(Path(scanner).read_bytes()).hexdigest())
        self.request['turn'] = 'real-scanner'
        self.engine.begin(self.request)
        # Deliberately invalid config would crash or suppress scanning if loaded.
        (self.repo / '.gitleaks.toml').write_text('invalid configuration')
        self.config['repositories']['repo']['allowed'].append('.gitleaks.toml')
        self.request['turn'] = 'real-scanner2'
        self.engine.begin(self.request)
        self.changed(value='github_token = "ghp_' + 'x7H4q2N9p5Z8s3V6r1L0a4B7c9D2e5F8g0J3' + '"\n')
        self.assertBlocked('gitleaks stdin failed')


if __name__ == '__main__':
    unittest.main(verbosity=2)
