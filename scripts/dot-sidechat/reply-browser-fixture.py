"""Private stdin/stdout synthetic BrowserAPI fixture. No network/auth or live paths."""
import json
import sys
import tempfile
from pathlib import Path
import sqlite3
import uuid
from browser_api import BrowserAPI, WorkspaceResolver
from sidechat import Store, Principal

project = '11111111-1111-4111-8111-111111111111'
issue = '33333333-3333-4333-8333-333333333333'
workspaces = [project, '22222222-2222-4222-8222-222222222222']

def uid():
    return str(uuid.uuid4())

with tempfile.TemporaryDirectory(prefix='reply-browser-', dir=sys.argv[1]) as directory:
    root = Path(directory)
    with sqlite3.connect(root/'vibe.sqlite') as db:
        db.executescript('CREATE TABLE projects(id BLOB,name TEXT); CREATE TABLE tasks(id BLOB,project_id BLOB,title TEXT); CREATE TABLE workspaces(id BLOB,task_id BLOB,name TEXT);')
        db.execute('INSERT INTO projects VALUES (?,?)', (uuid.UUID(project).bytes, 'Fixture'))
        db.execute('INSERT INTO tasks VALUES (?,?,?)', (uuid.UUID(issue).bytes, uuid.UUID(project).bytes, 'Fixture issue'))
        for workspace in workspaces:
            db.execute('INSERT INTO workspaces VALUES (?,?,?)', (uuid.UUID(workspace).bytes, uuid.UUID(issue).bytes, 'Fixture workspace'))
    # Trusted fixture session only: never issue a credential or insert an auth row.
    session = {'owner':'reply-fixture', 'projects':json.dumps([project])}
    owner = Principal('reply-fixture', 'owner'); dot = Principal('reply-fixture', 'dot')
    store = Store(root/'threads.sqlite', clock=lambda: 1792281600.)
    api = BrowserAPI(store, WorkspaceResolver(root/'vibe.sqlite'))
    seeded = set(); supports = True
    try:
        for line in sys.stdin:
            try:
                args = json.loads(line); operation = args['operation']
                if operation == 'page':
                    query = args['query']; key = 'project' if 'project' in query else 'workspace'
                    page = api.project_page(session, query[key]) if key == 'project' else api.page(session, query[key])
                    thread = page['thread']['id']; workspace = page['scope']['workspace']
                    if thread not in seeded:
                        first = api.send(session, {key:query[key], 'request':uid(), 'body':'Original owner message'})
                        reply = store.append(dot, thread, workspace, uid(), 'Exact Dot context\n<not HTML>', first['id'], 'sidechat_' + first['id'], attention='question')
                        store.set_reply_read_state(owner, thread, workspace, reply['id'], 'unread')
                        seeded.add(thread)
                    result = api.project_page(session, query[key]) if key == 'project' else api.page(session, query[key])
                    result['capabilities']['message_replies'] = supports
                elif operation == 'send': result = api.send(session, args['body'])
                elif operation == 'inspect': result = {'pending':store.pending(dot), 'notifications':api.notifications(session), 'links':store.db.execute('SELECT count(*) FROM owner_reply_targets').fetchone()[0]}
                elif operation == 'reopen':
                    store.close(); store = Store(root/'threads.sqlite'); api = BrowserAPI(store, WorkspaceResolver(root/'vibe.sqlite')); result = {}
                elif operation == 'legacy': supports = args['value']; result = {}
                else: raise ValueError('Unknown fixture operation')
                print(json.dumps({'ok':True, 'result':result}), flush=True)
            except Exception as exc:
                print(json.dumps({'ok':False, 'error':str(exc)}), flush=True)
    finally:
        store.close()
