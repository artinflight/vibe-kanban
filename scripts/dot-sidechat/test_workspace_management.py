"""Isolated management lifecycle; no real auth, conversations or dispatches."""
import json
from pathlib import Path
import tempfile
import sqlite3
import subprocess
import sys
import unittest
import uuid

from browser_api import BrowserAPI
from sidechat import Principal, Rejected, Store
from workspace_management import WorkspaceManagement


def uid():
    return str(uuid.uuid4())


class ManagementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'private.sqlite'
        self.store = Store(self.path)
        self.scope = dict(zip(('project', 'issue', 'workspace'), (uid(), uid(), uid())))
        self.sibling = dict(self.scope, workspace=uid())
        self.scopes = {s['workspace']: s for s in (self.scope, self.sibling)}
        def resolve(workspace):
            if workspace not in self.scopes:
                raise Rejected('Unavailable')
            return self.scopes[workspace]
        self.resolver = resolve
        self.api = BrowserAPI(self.store, resolve)
        grant = self.api.auth.grant('owner', [self.scope['project']])
        _, self.session = self.api.auth.pair(grant['pairing_code'])
        self.api.page(self.session, self.scope['workspace'])
        self.api.page(self.session, self.sibling['workspace'])

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def change(self, state='managed', scope=None, owner='owner'):
        return self.api.management.change(owner, scope or self.scope, state,
                                          'Explicit owner confirmation fixture', self.resolver)

    def managed(self, session=None):
        return self.api.notifications(session or self.session)['managed_workspaces']

    def reply(self):
        owner = self.api.send(self.session, {'workspace': self.scope['workspace'], 'request': uid(), 'body': 'Fixture'})
        thread = self.api.page(self.session, self.scope['workspace'])['thread']['id']
        message = self.store.append(Principal('owner', 'dot'), thread, self.scope['workspace'], uid(),
                                    'Retained question', owner['id'], 'sidechat_' + owner['id'], attention='question')
        return thread, message['id']

    def test_reads_scope_and_generic_dispatch_never_establish_management(self):
        thread, message = self.reply()
        self.store.db.execute('INSERT INTO dispatch_notes VALUES (?,?,?,?,?,?,?)',
            ('owner', uid(), self.scope['workspace'], uid(), 'run_session_prompt', thread, message))
        self.assertEqual([], self.managed())
        self.api.seen(self.session, {'workspace': self.scope['workspace'], 'messages': [message]})
        self.assertEqual([], self.managed())
        self.assertEqual(0, self.store.db.execute('SELECT count(*) FROM dot_workspace_management').fetchone()[0])

    def test_read_clear_manual_unread_and_reopen_do_not_change_management(self):
        self.change()
        thread, message = self.reply()
        before = [tuple(r) for r in self.store.db.execute('SELECT * FROM dot_workspace_management')]
        for action in ('unread', 'read', 'read', 'unread'):
            self.api.read_state(self.session, {'workspace': self.scope['workspace'], 'message': message, 'action': action})
            self.assertEqual(1, len(self.managed()))
        self.api.read_state(self.session, {'workspace': self.scope['workspace'], 'message': message, 'action': 'read'})
        self.api.attention(self.session, {'workspace': self.scope['workspace'], 'message': message, 'action': 'resolve'})
        self.assertEqual([], self.api.notifications(self.session)['issues'])
        self.assertEqual([self.scope['workspace']], [r['workspace_id'] for r in self.managed()])
        self.api.attention(self.session, {'workspace': self.scope['workspace'], 'message': message, 'action': 'reopen'})
        self.assertEqual(before, [tuple(r) for r in self.store.db.execute('SELECT * FROM dot_workspace_management')])
        self.store.close()
        self.store = Store(self.path)
        self.api = BrowserAPI(self.store, self.resolver)
        self.assertEqual([self.scope['workspace']], [r['workspace_id'] for r in self.managed()])
        self.assertFalse(self.api.page(self.session, self.scope['workspace'])['messages'][-1]['attention']['resolved'])

    def test_exact_target_only_no_sibling_or_subordinate_inheritance(self):
        self.change()
        self.assertEqual([dict(project_id=self.scope['project'], issue_id=self.scope['issue'],
            workspace_id=self.scope['workspace'], manager='dot', state='managed')], self.managed())
        self.assertNotIn(self.sibling['workspace'], [m['workspace_id'] for m in self.managed()])

    def test_management_change_does_not_change_messages_attention_auth_or_scopes(self):
        self.reply()
        tables = ('messages', 'dot_reply_state', 'outbox', 'scopes', 'browser_sessions', 'browser_grants')
        before = {t: [tuple(r) for r in self.store.db.execute('SELECT * FROM ' + t)] for t in tables}
        self.change()
        self.change('released')
        self.assertEqual(before, {t: [tuple(r) for r in self.store.db.execute('SELECT * FROM ' + t)] for t in tables})

    def test_explicit_release_and_reassignment_idempotency_retain_audit(self):
        self.assertFalse(self.change('released')['changed'])
        self.assertTrue(self.change()['changed'])
        self.assertFalse(self.change()['changed'])
        self.assertTrue(self.change('released')['changed'])
        self.assertFalse(self.change('released')['changed'])
        self.assertEqual([], self.managed())
        self.assertTrue(self.change()['changed'])
        self.assertEqual(['managed', 'released', 'managed'], [r[0] for r in self.store.db.execute('SELECT state FROM dot_workspace_management ORDER BY seq')])

    def test_missing_owner_scope_mismatch_and_relink_fail_closed(self):
        for scope, owner in ((dict(self.scope, issue=uid()), 'owner'), (self.scope, 'other')):
            with self.assertRaises(Rejected):
                self.change(scope=scope, owner=owner)
        self.change()
        self.scopes[self.scope['workspace']] = dict(self.scope, issue=uid())
        self.assertEqual([], self.managed())
        with self.assertRaises(Rejected):
            self.change()
        del self.scopes[self.scope['workspace']]
        self.assertEqual([], self.managed())

    def test_owner_role_project_grants_and_no_browser_enrollment(self):
        self.change()
        self.assertEqual([], self.managed(dict(self.session, projects='[]')))
        self.assertEqual([], self.managed(dict(self.session, owner='other')))
        for role in ('dot', 'publisher', 'unknown'):
            with self.assertRaises(Rejected):
                self.api.management.visible(Principal('owner', role), [self.scope['project']], self.resolver)
        with self.assertRaises(Rejected):
            self.api.send(self.session, {'workspace': self.scope['workspace'], 'request': uid(), 'body': 'x', 'managed': True})
        with self.assertRaises(Rejected):
            self.api.management.change('owner', self.scope, 'managed', '', self.resolver)

    def test_trusted_cli_validates_authoritative_scope_and_requires_apply(self):
        vibe = Path(self.temp.name) / 'vibe.sqlite'
        with sqlite3.connect(vibe) as db:
            db.executescript('CREATE TABLE projects(id BLOB);CREATE TABLE tasks(id BLOB,project_id BLOB,title TEXT);CREATE TABLE workspaces(id BLOB,task_id BLOB,name TEXT);')
            db.execute('INSERT INTO projects VALUES (?)', (uuid.UUID(self.scope['project']).bytes,))
            db.execute('INSERT INTO tasks VALUES (?,?,?)', (uuid.UUID(self.scope['issue']).bytes, uuid.UUID(self.scope['project']).bytes, 'Fixture'))
            db.execute('INSERT INTO workspaces VALUES (?,?,?)', (uuid.UUID(self.scope['workspace']).bytes, uuid.UUID(self.scope['issue']).bytes, 'Fixture'))
        before = vibe.read_bytes()
        command = [sys.executable, '-B', str(Path(__file__).parent / 'workspace_management.py'),
                   '--data', str(self.path), '--vibe-db', str(vibe), '--owner', 'owner',
                   '--project', self.scope['project'], '--issue', self.scope['issue'],
                   '--workspace', self.scope['workspace'], '--state', 'managed',
                   '--approval-ref', 'Explicit fixture owner approval']
        denied = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(0, denied.returncode)
        self.assertEqual([], self.managed())
        accepted = subprocess.run(command + ['--apply'], capture_output=True, text=True, check=True)
        self.assertTrue(json.loads(accepted.stdout)['changed'])
        self.assertEqual(1, len(self.managed()))
        self.assertEqual(before, vibe.read_bytes(), 'Authoritative Vibe database stays read-only')

    def test_only_verified_t89_backfill_is_provided_not_automatically_applied(self):
        target = json.loads((Path(__file__).parent / 'management-backfill-t89.json').read_text())
        self.assertEqual('811828af-f58f-48b3-ab51-0d594a1c4f4e', target['workspace'])
        self.assertEqual('c34993a6-c342-44be-873d-95ec42bb7a05', target['issue'])
        self.assertEqual('48c03c77-4207-48c1-86ed-686262c1116a', target['project'])
        self.assertEqual([], self.managed())


if __name__ == '__main__':
    unittest.main()
