"""Disposable synthetic sidechat HTTP fixture for project browser acceptance.
Never opens production sidechat state, sessions, subscriptions or agent APIs.
"""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import signal
import tempfile
import uuid
from http.server import HTTPServer

from browser_api import BrowserAPI, WorkspaceResolver, handler
from sidechat import Store, Principal

parser = argparse.ArgumentParser()
parser.add_argument('--output', required=True)
parser.add_argument('--project', action='append', required=True)
parser.add_argument('--issue', required=True)
args = parser.parse_args()
def terminate(*_):
    raise SystemExit(0)
signal.signal(signal.SIGTERM, terminate)
os.umask(0o077)
with tempfile.TemporaryDirectory(prefix='project-sidechat-', dir=args.output) as directory:
    root = Path(directory)
    path = root/'vibe.sqlite'
    with sqlite3.connect(path) as db:
        db.executescript('CREATE TABLE projects(id BLOB,name TEXT); CREATE TABLE tasks(id BLOB,project_id BLOB,title TEXT);')
        for project in args.project:
            db.execute('INSERT INTO projects VALUES (?,?)',(uuid.UUID(project).bytes,'Acceptance project'))
        db.execute('INSERT INTO tasks VALUES (?,?,?)',(uuid.UUID(args.issue).bytes,uuid.UUID(args.project[0]).bytes,'Canonical task reference'))
    store = Store(root/'threads.sqlite')
    api = BrowserAPI(store,WorkspaceResolver(path))
    token, session = api.auth.pair(api.auth.grant('synthetic-project-owner',args.project)['pairing_code'])
    base_handler = handler(api,'https://fixture.invalid')

    class Handler(base_handler):
        def dispatch(self):
            if self.path == '/__qa/reply' and self.command == 'POST':
                args = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                page = api.project_page(session,args['project'])
                owner_message = next(m for m in reversed(page['messages']) if m['role']=='owner')
                reply = store.append(Principal('synthetic-project-owner','dot'),page['thread']['id'],page['scope']['workspace'],str(uuid.uuid4()),'Project reply needs your decision',owner_message['id'],'sidechat_'+owner_message['id'],attention='question')
                return self.output(200,{'message':reply['id']})
            if self.path == '/__qa/conflict' and self.command == 'POST':
                args = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                entries = api.project_plan(session,args['project'])['entries']
                entry = next(e for e in entries if e['id']==args['entry'])
                exact = {k:entry[k] for k in ('id','revision','kind','title','body','issue_ids','resolved','target_date')}
                exact['body']='Edited concurrently by dot'
                result = api.project_write(session,{'project':args['project'],'request':str(uuid.uuid4()),'entry':exact})
                return self.output(200,result)
            return super().dispatch()
    server = HTTPServer(('127.0.0.1',0),Handler)
    # Private child pipe only. Never emit even synthetic session material to logs.
    with os.fdopen(3,'w') as ready:
        json.dump({'port':server.server_port,'token':token},ready)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        store.close()
