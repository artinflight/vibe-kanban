import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import uuid

from browser_api import BrowserAPI, WorkspaceResolver
from events import Events
from project_collaboration import ProjectCollaboration, Conflict
from sidechat import Store, Principal, Rejected


def uid():
    return str(uuid.uuid4())


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'vibe.sqlite'
        self.project, self.other, self.issue, self.workspace = [uid() for _ in range(4)]
        with sqlite3.connect(self.path) as db:
            db.executescript('CREATE TABLE projects(id BLOB, name TEXT); CREATE TABLE tasks(id BLOB, project_id BLOB, title TEXT); CREATE TABLE workspaces(id BLOB,task_id BLOB,name TEXT);')
            for project in (self.project, self.other):
                db.execute('INSERT INTO projects VALUES (?,?)', (uuid.UUID(project).bytes, 'Project'))
            db.execute('INSERT INTO tasks VALUES (?,?,?)', (uuid.UUID(self.issue).bytes, uuid.UUID(self.project).bytes, 'Canonical issue'))
            db.execute('INSERT INTO workspaces VALUES (?,?,?)', (uuid.UUID(self.workspace).bytes, uuid.UUID(self.issue).bytes, 'Canonical workspace'))
        self.before = self.path.read_bytes()
        self.store = Store(Path(self.temp.name) / 'private.sqlite')
        self.resolver = WorkspaceResolver(self.path)
        self.api = BrowserAPI(self.store, self.resolver)
        self.session = self.pair('owner', [self.project, self.other])
        self.owner = Principal('owner', 'owner')
        self.dot = Principal('owner', 'dot')
        self.collaboration = ProjectCollaboration(self.store, self.resolver)

    def tearDown(self):
        self.assertEqual(self.before, self.path.read_bytes(), 'Vibe database must remain read-only')
        self.store.close()
        self.temp.cleanup()

    def pair(self, owner, projects):
        return self.api.auth.pair(self.api.auth.grant(owner, projects)['pairing_code'])[1]

    def entry(self, **updates):
        return dict(dict(id=uid(), revision=0, kind='checklist', title='Acceptance', body='', issue_ids=[], resolved=False, target_date=None), **updates)

    def write(self, entry, request=None, session=None):
        return self.api.project_write(session or self.session, {'project':self.project, 'request':request or uid(), 'entry':entry})

    def test_project_threads_are_private_and_distinct_from_issue_and_other_projects(self):
        page = self.api.project_page(self.session, self.project)
        self.assertEqual(page['thread']['scope_kind'], 'project')
        self.assertEqual(page['scope']['workspace'], 'project:' + self.project)
        self.assertEqual(page['thread']['id'], self.api.project_page(self.session, self.project)['thread']['id'])
        issue_page = self.api.page(self.session, self.workspace)
        self.assertNotEqual(issue_page['thread']['id'], page['thread']['id'])
        self.assertNotEqual(page['thread']['id'], self.api.project_page(self.session, self.other)['thread']['id'])
        second_owner = self.pair('other-owner', [self.project])
        other_page = self.api.project_page(second_owner, self.project)
        self.assertNotEqual(page['thread']['id'], other_page['thread']['id'])
        with self.assertRaises(Rejected): self.store.read(Principal('other-owner', 'dot'), page['thread']['id'])

    def test_existing_event_delivery_reply_receipts_and_notifications(self):
        page = self.api.project_page(self.session, self.project)
        request = {'project': self.project, 'request': uid(), 'body': 'Across all issues'}
        message = self.api.send(self.session, request)
        self.assertEqual(message['id'], self.api.send(self.session, request)['id'])
        event = self.store.pending(self.dot)['items'][0]['event']
        self.assertEqual(event['data']['project_id'], self.project)
        events = Events(self.store, lambda *args: (200,b''))
        # The already authorized project subscription matches new project threads.
        self.assertTrue(events._matches({'filters':json.dumps({'project_id':self.project})}, page['thread']))
        self.store.bind(self.owner, page['thread']['id'], 'existing-project-subscription')
        claim = self.store.claim(Principal('owner','publisher'))
        self.store.acknowledge(Principal('owner','publisher'), event['eventId'], claim['attempt'], 200)
        reply = self.store.tool(self.dot, 'append_dot_reply', {'thread': page['thread']['id'], 'workspace': page['scope']['workspace'], 'request': uid(), 'body': 'A decision?', 'reply_to': message['id'], 'event_id': event['eventId'], 'attention':'question'})
        self.assertTrue(self.store.receipt(self.owner, page['thread']['id'], message['id'])['reply_persisted'])
        notifications = self.api.notifications(self.session)
        self.assertEqual(notifications['issues'], [])
        self.assertEqual(notifications['projects'][0]['unread_count'], 1)
        self.api.project_page(self.session, self.project)  # polling cannot read
        self.assertEqual(self.api.notifications(self.session)['projects'][0]['unread_count'], 1)
        self.api.seen(self.session, {'project':self.project, 'messages':[reply['id']]})
        self.assertEqual(self.api.notifications(self.session)['projects'][0]['needs_attention_count'], 1)
        self.api.attention(self.session, {'project':self.project, 'message':reply['id'], 'action':'resolve'})
        self.assertEqual(self.api.notifications(self.session)['projects'], [])
        with self.assertRaises(Rejected): self.api.seen(self.session, {'project':self.other,'messages':[reply['id']]})

    def test_shared_entries_across_owners_and_dot_with_private_chat(self):
        created = self.write(self.entry())
        other_session = self.pair('other-owner', [self.project])
        self.assertEqual(self.api.project_plan(other_session, self.project)['entries'][0]['id'], created['id'])
        changed = self.collaboration.write(self.dot, self.project, uid(), {k:v for k,v in dict(created,title='Dot update').items() if k not in ('project','updated','updated_by')})
        self.assertEqual(changed['updated_by'], 'dot')
        self.assertEqual(self.api.project_plan(other_session, self.project)['entries'][0]['title'], 'Dot update')

    def test_revision_race_and_uncertain_retry(self):
        entry, request = self.entry(), uid()
        first = self.write(entry, request)
        self.assertEqual(first, self.write(entry, request))
        with self.assertRaises(Rejected): self.write(dict(entry, title='Changed'), request)
        with self.assertRaises(Conflict): self.write(entry)
        update = {key: first[key] for key in entry}
        self.write(dict(update,title='Latest'))
        with self.assertRaises(Conflict): self.write(dict(update,title='Stale'))
        self.assertEqual(self.api.project_plan(self.session,self.project)['entries'][0]['title'], 'Latest')

    def test_no_duplicate_task_state_and_cross_project_links(self):
        self.write(self.entry(issue_ids=[self.issue], kind='milestone'))
        with self.assertRaises(Rejected): self.write(self.entry(issue_ids=[self.issue], resolved=True))
        with self.assertRaises(Rejected): self.write(self.entry(issue_ids=[uid()]))
        with self.assertRaises(Rejected): self.write(self.entry(owner='dot'))
        with self.assertRaises(Rejected): self.write(self.entry(status='done'))
        self.write(self.entry(kind='decision', issue_ids=[self.issue], resolved=True))

    def test_access_future_projects_and_no_workspace_required(self):
        unknown = uid()
        with self.assertRaises(Rejected): self.api.project_page(self.session, unknown)
        with self.assertRaises(Rejected): self.collaboration.read(Principal('stranger','dot'),self.project)
        restricted = self.pair('restricted',[self.other])
        with self.assertRaises(Rejected): self.api.project_page(restricted,self.project)
        with self.assertRaises(Rejected): self.api.project_plan(restricted,self.project)
        page = self.api.project_page(self.session,self.other) # empty existing/future project
        self.assertEqual(page['messages'],[])

    def test_stable_project_pagination_and_reopen_durability(self):
        for n in range(51): self.api.send(self.session,{'project':self.project,'request':uid(),'body':str(n)})
        first = self.api.project_page(self.session,self.project)
        self.api.send(self.session,{'project':self.project,'request':uid(),'body':'new'})
        second = self.api.project_page(self.session,self.project,first['next_after'],first['through'])
        self.assertEqual(len(second['messages']),1)
        self.write(self.entry(kind='question',body='Keep after restart'))
        self.store.close()
        self.store = Store(Path(self.temp.name)/'private.sqlite')
        self.api = BrowserAPI(self.store,self.resolver)
        self.assertEqual(self.api.project_plan(self.session,self.project)['entries'][0]['body'],'Keep after restart')
        self.assertEqual(self.api.project_page(self.session,self.project)['through'],52)

    def test_input_validation_and_mixed_target_rejected(self):
        for changes in ({'title':''},{'title':'x'*241},{'kind':'task'},{'revision':True},{'target_date':'2026-02-30'},{'issue_ids':[self.issue,self.issue]}):
            with self.assertRaises((Rejected,ValueError)): self.write(self.entry(**changes))
        with self.assertRaises(Rejected): self.api.send(self.session, {'project':self.project,'workspace':self.workspace,'request':uid(),'body':'ambiguous'})

class ProjectConnectorTests(unittest.TestCase):
    setUp = ProjectTests.setUp
    tearDown = ProjectTests.tearDown
    pair = ProjectTests.pair
    entry = ProjectTests.entry
    def test_additive_connector_dispatch_preserves_existing_contracts(self):
        import connector
        import os
        from unittest.mock import patch
        self.api.project_plan(self.session, self.project)
        with patch.object(connector, 'ROOT', Path(self.temp.name)), patch.dict(os.environ, {'VK_APPROVAL_PRINCIPAL':'owner','VK_SIDECHAT_VIBE_DB':str(self.path)}):
            # Connector uses its own Store connection against the same private file.
            self.store.db.execute('PRAGMA wal_checkpoint(FULL)')
            # Reopen the fixture's exact DB filename used by the production adapter.
            self.store.close()
            Path(self.temp.name,'private.sqlite').rename(Path(self.temp.name,'threads.sqlite'))
            self.store = Store(Path(self.temp.name,'threads.sqlite'))
            result = connector.call('read_project_collaboration', {'project': self.project})
            self.assertEqual(result['entries'], [])
            connector.call('write_project_collaboration_entry', {'project':self.project,'request':uid(),'entry':self.entry()})
            self.assertEqual(len(connector.call('read_project_collaboration',{'project':self.project})['entries']),1)
            with self.assertRaises(Rejected): connector.call('read_project_collaboration', {'project':self.project,'owner':'stranger'})
            with self.assertRaises(Rejected): connector.call('read_project_collaboration', {'project':uid()})
