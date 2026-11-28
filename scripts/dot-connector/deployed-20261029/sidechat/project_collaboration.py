"""Project planning and private project conversations, over the existing sidechat store.

The reserved project:<uuid> context is not a Vibe issue/workspace ID. It is used
only inside the sidechat protocol, so the existing exact-event reply/delivery
contract works without creating synthetic tasks or touching Vibe's database.
"""
import datetime
import json
import uuid

from sidechat import Principal, Rejected, canonical

class Conflict(Rejected):
    pass


KINDS = ('checklist', 'milestone', 'decision', 'question')


class ProjectCollaboration:
    def __init__(self, store, resolver):
        self.store, self.resolver = store, resolver
        store.db.executescript("""
          CREATE TABLE IF NOT EXISTS project_entries(
            project TEXT NOT NULL, id TEXT NOT NULL, kind TEXT NOT NULL,
            title TEXT NOT NULL, body TEXT NOT NULL, issue_ids TEXT NOT NULL,
            resolved INTEGER NOT NULL, target_date TEXT,
            revision INTEGER NOT NULL, updated REAL NOT NULL, updated_by TEXT NOT NULL,
            PRIMARY KEY(project,id));
          CREATE TABLE IF NOT EXISTS project_entry_requests(
            project TEXT NOT NULL, owner TEXT NOT NULL, request TEXT NOT NULL,
            payload TEXT NOT NULL, result TEXT NOT NULL,
            PRIMARY KEY(project,owner,request));
        """)

    def authorize(self, principal, project):
        self.store._principal(principal, ('owner', 'dot'))
        project = str(uuid.UUID(project))
        if not (self.store.db.execute('SELECT 1 FROM project_grants WHERE owner=? AND project=?', (principal.owner, project)).fetchone()
                or self.store.db.execute('SELECT 1 FROM scopes WHERE owner=? AND project=?', (principal.owner, project)).fetchone()):
            raise Rejected('Project is outside this owner\'s grant')
        return self.resolver.project(project)

    def thread(self, principal, project):
        scope = self.authorize(principal, project)
        context = 'project:' + scope['project']
        self.store.register_scope(principal.owner, scope['project'], context, context)
        thread = self.store.resolve(Principal(principal.owner, 'owner'), scope['project'], context, context)
        return thread, dict(scope, issue=context, workspace=context,
                            issue_label=scope['project_label'], workspace_label='Project-wide conversation', scope_kind='project')

    def read(self, principal, project):
        scope = self.authorize(principal, project)
        rows = self.store.db.execute('SELECT * FROM project_entries WHERE project=? ORDER BY updated DESC,id', (scope['project'],)).fetchall()
        return {'project': scope, 'entries': [self.entry(row) for row in rows]}

    @staticmethod
    def entry(row):
        return dict(dict(row), issue_ids=json.loads(row['issue_ids']), resolved=bool(row['resolved']))

    def write(self, principal, project, request, entry):
        scope = self.authorize(principal, project)
        project = scope['project']
        request = str(uuid.UUID(request))
        fields = {'id', 'revision', 'kind', 'title', 'body', 'issue_ids', 'resolved', 'target_date'}
        if not isinstance(entry, dict) or set(entry) != fields:
            raise Rejected('Exact planning entry fields required')
        eid = str(uuid.UUID(entry['id']))
        if type(entry['revision']) is not int or entry['revision'] < 0 or entry['kind'] not in KINDS:
            raise Rejected('Invalid revision or entry kind')
        if not isinstance(entry['title'], str) or not entry['title'].strip() or len(entry['title']) > 240:
            raise Rejected('Title must contain 1..240 characters')
        if not isinstance(entry['body'], str) or len(entry['body']) > 10000 or type(entry['resolved']) is not bool:
            raise Rejected('Invalid body or resolution')
        links = entry['issue_ids']
        if not isinstance(links, list) or len(links) > 50 or any(not isinstance(i, str) for i in links) or len(set(links)) != len(links):
            raise Rejected('At most 50 distinct issue links required')
        for issue in links:
            if not self.resolver.issue_in_project(project, str(uuid.UUID(issue))):
                raise Rejected('Linked issue is unavailable in this project')
        if links and entry['kind'] in ('checklist', 'milestone') and entry['resolved']:
            raise Rejected('Linked task completion belongs to Vibe, not the planning entry')
        if entry['target_date'] is not None:
            if not isinstance(entry['target_date'], str) or datetime.date.fromisoformat(entry['target_date']).isoformat() != entry['target_date']:
                raise Rejected('ISO calendar date required')
        payload = canonical(entry)
        with self.store.transaction():
            old_request = self.store.db.execute('SELECT * FROM project_entry_requests WHERE project=? AND owner=? AND request=?', (project, principal.owner, request)).fetchone()
            if old_request:
                if old_request['payload'] != payload:
                    raise Rejected('Idempotency key conflict')
                return json.loads(old_request['result'])
            old = self.store.db.execute('SELECT * FROM project_entries WHERE project=? AND id=?', (project, eid)).fetchone()
            if (old['revision'] if old else 0) != entry['revision']:
                raise Conflict('Entry changed elsewhere. Refresh and review before saving.')
            if old and old['kind'] != entry['kind']:
                raise Rejected('Entry kind cannot change')
            if not old and self.store.db.execute('SELECT count(*) FROM project_entries WHERE project=?', (project,)).fetchone()[0] >= 500:
                raise Rejected('Project entry limit reached')
            self.store.db.execute('''INSERT INTO project_entries VALUES (?,?,?,?,?,?,?,?,?,?,?)
              ON CONFLICT(project,id) DO UPDATE SET title=excluded.title,body=excluded.body,
              issue_ids=excluded.issue_ids,resolved=excluded.resolved,target_date=excluded.target_date,
              revision=excluded.revision,updated=excluded.updated,updated_by=excluded.updated_by''',
              (project, eid, entry['kind'], entry['title'], entry['body'], canonical(links), int(entry['resolved']),
               entry['target_date'], entry['revision'] + 1, self.store.clock(), principal.role))
            result = self.entry(self.store.db.execute('SELECT * FROM project_entries WHERE project=? AND id=?', (project, eid)).fetchone())
            self.store.db.execute('INSERT INTO project_entry_requests VALUES (?,?,?,?,?)', (project, principal.owner, request, payload, canonical(result)))
            return result
