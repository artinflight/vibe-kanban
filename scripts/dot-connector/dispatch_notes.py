"""Dot-only accepted-dispatch receipts and private chat notes.

No prompt text, agent launch, HTTP request, polling provider or new credentials.
The caller supplies an already-returned acceptance; unknown dispatches are never
inferred from timing, identical prompts or an unrelated agent execution.
"""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid

PURPOSES = {'start_workspace': 'begin the requested work',
            'run_session_prompt': 'continue the requested work'}
VIBE_DB = '/home/mcp/.local/share/vibe-kanban-green-xdg/vibe-kanban/db.v2.sqlite'


class Blocked(ValueError):
    pass


def uid(value):
    if not isinstance(value, str): raise Blocked('invalid_identity')
    try: return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError): raise Blocked('invalid_identity') from None


def private_db(path):
    path = Path(path)
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    if path.is_symlink(): raise Blocked('unsafe_receipt_store')
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    os.close(fd)
    if path.stat().st_mode & 0o077: raise Blocked('unsafe_receipt_store')
    db = sqlite3.connect(path, timeout=3, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    return db


class Journal:
    def __init__(self, path):
        self.path = Path(path)
        self.db = private_db(path)
        self.db.execute('''CREATE TABLE IF NOT EXISTS dispatch_receipts(
            owner TEXT NOT NULL, execution TEXT NOT NULL, workspace TEXT,
            session TEXT NOT NULL, kind TEXT NOT NULL, project TEXT, issue TEXT,
            state TEXT NOT NULL DEFAULT 'pending', message TEXT, error TEXT,
            created REAL NOT NULL, updated REAL NOT NULL,
            PRIMARY KEY(owner,execution))''')

    def close(self): self.db.close()

    def accept(self, owner, receipt):
        values = {k: uid(receipt[k]) for k in ('execution', 'session')}
        values['workspace'] = uid(receipt['workspace']) if receipt.get('workspace') else None
        if receipt['kind'] not in PURPOSES: raise Blocked('invalid_dispatch_kind')
        project, issue = receipt.get('project'), receipt.get('issue')
        if project is not None: project, issue = uid(project), uid(issue)
        now = time.time()
        self.db.execute('BEGIN IMMEDIATE')
        try:
            old = self.db.execute('SELECT * FROM dispatch_receipts WHERE owner=? AND execution=?',
                                  (owner, values['execution'])).fetchone()
            if old:
                for k, v in dict(values, kind=receipt['kind'], project=project, issue=issue).items():
                    if k == 'workspace' and v is None: continue
                    if old[k] != v: raise Blocked('receipt_identity_conflict')
            else:
                self.db.execute('''INSERT INTO dispatch_receipts
                    (owner,execution,workspace,session,kind,project,issue,created,updated)
                    VALUES (?,?,?,?,?,?,?,?,?)''',
                    (owner, values['execution'], values['workspace'], values['session'], receipt['kind'], project, issue, now, now))
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK'); raise
        return dict(self.db.execute('SELECT * FROM dispatch_receipts WHERE owner=? AND execution=?',
                                   (owner, values['execution'])).fetchone())

    def bind_workspace(self, row, workspace):
        workspace = uid(workspace)
        self.db.execute('UPDATE dispatch_receipts SET workspace=? WHERE owner=? AND execution=? AND workspace IS NULL',
                        (workspace, row['owner'], row['execution']))
        found = dict(self.db.execute('SELECT * FROM dispatch_receipts WHERE owner=? AND execution=?',
                                    (row['owner'], row['execution'])).fetchone())
        if found['workspace'] != workspace: raise Blocked('execution_binding_mismatch')
        return found

    def mark(self, row, message=None, error=None):
        self.db.execute('''UPDATE dispatch_receipts SET state=?,message=?,error=?,updated=?
            WHERE owner=? AND execution=? AND (state!='noted' OR ? IS NOT NULL)''',
            ('noted' if message else 'pending', message, error, time.time(), row['owner'], row['execution'], message))

    def pending(self, owner, limit=20):
        return [dict(r) for r in self.db.execute('''SELECT * FROM dispatch_receipts
            WHERE owner=? AND state='pending' ORDER BY updated,created LIMIT ?''', (owner, limit))]


@dataclass(frozen=True)
class VerifiedDispatch:
    owner: str
    execution: str
    session: str
    workspace: str
    project: str
    issue: str
    kind: str


class NativeReader:
    def __init__(self, path=VIBE_DB): self.path = Path(path)

    def verify(self, row):
        with sqlite3.connect(self.path.resolve(strict=True).as_uri()+'?mode=ro', uri=True, timeout=0.1) as db:
            db.execute('PRAGMA query_only=ON')
            found = db.execute('''SELECT e.session_id,s.workspace_id,w.task_id,t.project_id,
                e.run_reason,e.dropped,e.status FROM execution_processes e
                JOIN sessions s ON s.id=e.session_id JOIN workspaces w ON w.id=s.workspace_id
                LEFT JOIN tasks t ON t.id=w.task_id LEFT JOIN projects p ON p.id=t.project_id
                WHERE e.id=? AND p.id IS NOT NULL''', (uuid.UUID(row['execution']).bytes,)).fetchone()
        if not found: raise Blocked('execution_or_issue_unavailable')
        def native(value): return str(uuid.UUID(bytes=value)) if isinstance(value, bytes) else uid(value)
        session, workspace, issue, project = map(native, found[:4])
        if (session, workspace) != (row['session'], row['workspace']): raise Blocked('execution_binding_mismatch')
        if row.get('project') and (project, issue) != (row['project'], row['issue']): raise Blocked('issue_context_changed')
        if found[4] != 'codingagent' or found[5] or found[6] not in ('running','completed','failed','killed'):
            raise Blocked('agent_execution_not_confirmed')
        return VerifiedDispatch(row['owner'], row['execution'], session, workspace, project, issue, row['kind'])


def record_dispatch_note(store, principal, receipt):
    """Explicit internal note path. Never fabricates owner/event/reply authority.

    Only a verified connector dispatch can use this trusted role. Native/manual
    requests do not pass through it. Existing grants are checked before creating
    a first thread, and existing workspace scopes can never be silently relinked.
    """
    from sidechat import Rejected
    if principal.role != 'dispatch' or not isinstance(receipt, VerifiedDispatch) or principal.owner != receipt.owner:
        raise Rejected('Verified dispatch principal required')
    if receipt.kind not in PURPOSES: raise Rejected('Unsupported dispatch purpose')
    key = str(uuid.uuid5(uuid.NAMESPACE_URL, 'vibe-dot-dispatch:'+receipt.owner+':'+receipt.execution))
    body = 'Dot prompted this workspace\'s agent to '+PURPOSES[receipt.kind]+'.\n\nAccepted execution: '+receipt.execution
    digest = hashlib.sha256(body.encode()).hexdigest()
    with store.transaction():
        db = store.db
        allowed = db.execute('''SELECT 1 FROM owner_project_policies WHERE owner=? AND enabled=1
            UNION SELECT 1 FROM project_grants WHERE owner=? AND project=?
            UNION SELECT 1 FROM scopes WHERE owner=? AND workspace=? AND project=? AND issue=?''',
            (receipt.owner, receipt.owner, receipt.project, receipt.owner, receipt.workspace, receipt.project, receipt.issue)).fetchone()
        if not allowed: raise Rejected('Project is not authorized for dispatch notes')
        scope = db.execute('SELECT project,issue FROM scopes WHERE owner=? AND workspace=?',
                           (receipt.owner, receipt.workspace)).fetchone()
        if scope and tuple(scope) != (receipt.project, receipt.issue): raise Rejected('Workspace history scope changed')
        db.execute('''CREATE TABLE IF NOT EXISTS dispatch_notes(
            owner TEXT NOT NULL,execution TEXT NOT NULL,workspace TEXT NOT NULL,
            session TEXT NOT NULL,kind TEXT NOT NULL,thread TEXT NOT NULL,message TEXT NOT NULL,
            PRIMARY KEY(owner,execution),UNIQUE(message))''')
        old = db.execute('SELECT * FROM dispatch_notes WHERE owner=? AND execution=?', (receipt.owner, receipt.execution)).fetchone()
        if old:
            if (old['workspace'], old['session'], old['kind']) != (receipt.workspace, receipt.session, receipt.kind):
                raise Rejected('Dispatch note identity conflict')
            return dict(old)
        db.execute('INSERT OR IGNORE INTO scopes VALUES (?,?,?,?)', (receipt.owner, receipt.project, receipt.issue, receipt.workspace))
        db.execute('INSERT OR IGNORE INTO threads VALUES (?,?,?,?,?)',
                   (str(uuid.uuid4()), receipt.owner, receipt.project, receipt.issue, store.clock()))
        thread = db.execute('SELECT id FROM threads WHERE owner=? AND project=? AND issue=?',
                            (receipt.owner, receipt.project, receipt.issue)).fetchone()[0]
        seq = db.execute('SELECT COALESCE(MAX(seq),0)+1 FROM messages WHERE thread=?', (thread,)).fetchone()[0]
        mid, now = str(uuid.uuid4()), store.clock()
        db.execute('INSERT INTO messages VALUES (?,?,?,?,?,?,?,?,?,?)',
                   (mid, thread, seq, 'dot', body, receipt.workspace, key, None, digest, now))
        db.execute('INSERT INTO dot_reply_state(message,updated) VALUES (?,?)', (mid, now))
        db.execute('INSERT INTO dispatch_notes VALUES (?,?,?,?,?,?,?)',
                   (receipt.owner, receipt.execution, receipt.workspace, receipt.session, receipt.kind, thread, mid))
        return dict(db.execute('SELECT * FROM dispatch_notes WHERE owner=? AND execution=?', (receipt.owner, receipt.execution)).fetchone())


def receipt_from_result(kind, args, result):
    if kind not in PURPOSES or result.get('isError'): return None
    try:
        data = json.loads(result['content'][0]['text'])
        if kind == 'start_workspace':
            execution, workspace = data['execution_process'], data['workspace']
            return {'execution': uid(execution['id']), 'workspace': uid(workspace['id']),
                    'session': uid(execution['session_id']), 'kind': kind,
                    'project': uid(args['project_id']), 'issue': uid(args['issue_id'])}
        if data.get('status') == 'queued': return None
        execution = data['execution']
        if uid(execution['id']) != uid(data['execution_id']) or uid(execution['session_id']) != uid(args['session_id']):
            raise Blocked('execution_binding_mismatch')
        # The exact workspace is verified from the authoritative session below.
        return {'execution': uid(data['execution_id']), 'session': uid(args['session_id']), 'kind': kind}
    except (KeyError, TypeError, ValueError, IndexError):
        return None


def open_note_store(path):
    """Bounded existing-DB writer; avoid schema/backfill work on the dispatch path."""
    from sidechat import Store
    path = Path(path)
    if path.is_symlink() or path.stat().st_mode & 0o077: raise Blocked('unsafe_chat_store')
    store = Store.__new__(Store)
    store.clock = time.time
    store.db = sqlite3.connect(path.resolve().as_uri()+'?mode=rw', uri=True,
                               timeout=0.1, isolation_level=None)
    store.db.row_factory = sqlite3.Row
    store.db.execute('PRAGMA foreign_keys=ON')
    return store


class Runtime:
    def __init__(self):
        import sidechat_connector  # Installs the fixed current bundle on sys.path.
        from connector import ROOT, owner
        self.owner = owner()
        self.opened = lambda: open_note_store(ROOT/'threads.sqlite')
        self.journal = Journal(ROOT/'dispatch-receipts.sqlite')
        self.native = NativeReader(os.environ.get('VK_SIDECHAT_VIBE_DB', VIBE_DB))

    def close(self): self.journal.close()

    def session_workspace(self, session):
        with sqlite3.connect(self.native.path.resolve(strict=True).as_uri()+'?mode=ro', uri=True, timeout=0.1) as db:
            db.execute('PRAGMA query_only=ON')
            row = db.execute('SELECT workspace_id FROM sessions WHERE id=?', (uuid.UUID(session).bytes,)).fetchone()
        if not row: raise Blocked('session_unavailable')
        return str(uuid.UUID(bytes=row[0])) if isinstance(row[0], bytes) else uid(row[0])

    def deliver(self, row):
        from sidechat import Principal
        try:
            if not row['workspace']:
                row = self.journal.bind_workspace(row, self.session_workspace(row['session']))
            verified = self.native.verify(row)
            store = self.opened()
            try: note = record_dispatch_note(store, Principal(self.owner, 'dispatch'), verified)
            finally: store.close()
            self.journal.mark(row, message=note['message'])
            return {'state': 'noted', 'execution_id': row['execution'], 'workspace_id': row['workspace'], 'message_id': note['message']}
        except Exception as error:
            code = str(error) if isinstance(error, Blocked) else 'note_write_unavailable'
            self.journal.mark(row, error=code)
            return {'state': 'pending', 'execution_id': row['execution'], 'workspace_id': row['workspace'], 'code': code}


def observe(kind, args, result, origin='dot', factory=None):
    """Receipt integration after a successful dispatch, before its MCP response.

    Exceptions from the actual dispatch never enter this function. Native user
    origin is a no-op. Notes are independently retryable; agent POSTs are not.
    """
    if origin != 'dot' or kind not in PURPOSES or result.get('isError'): return result
    factory = factory or Runtime
    receipt = receipt_from_result(kind, args, result)
    if receipt is None:
        status = {'state': 'awaiting_execution_receipt', 'code': 'no_verified_agent_execution_id'}
    else:
        runtime = None
        try:
            runtime = factory()
            row = runtime.journal.accept(runtime.owner, receipt)
            if row['state'] == 'noted':
                status = {'state': 'noted', 'execution_id': row['execution'], 'workspace_id': row['workspace'], 'message_id': row['message']}
            else: status = runtime.deliver(row)
        except Exception:
            status = {'state': 'pending', 'code': 'receipt_or_scope_unavailable', 'execution_id': receipt['execution']}
        finally:
            if runtime: runtime.close()
    # Preserve the original result/data block and PR271 errors byte-for-byte.
    output = dict(result, content=list(result.get('content', [])))
    output['content'].append({'type': 'text', 'text': json.dumps({'dispatch_note': status}, sort_keys=True)})
    return output


def recover_pending(factory=None, budget_seconds=0.5):
    runtime = (factory or Runtime)()
    try:
        deadline = time.monotonic()+budget_seconds
        results = []
        for row in runtime.journal.pending(runtime.owner):
            if time.monotonic() >= deadline: break
            results.append(runtime.deliver(row))
        return results
    finally: runtime.close()


def workspace_status(workspace):
    import sidechat_connector
    from connector import ROOT, owner
    path = ROOT/'dispatch-receipts.sqlite'
    if not path.exists(): return {'status': 'no_recorded_dispatch', 'receipts': []}
    try:
        if path.is_symlink() or path.stat().st_mode & 0o077: raise Blocked('unsafe_receipt_store')
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True, timeout=0.1) as db:
            db.execute('PRAGMA query_only=ON'); db.row_factory = sqlite3.Row
            rows = [dict(r) for r in db.execute('''SELECT execution,session,kind,state,message,error
                FROM dispatch_receipts WHERE owner=? AND workspace=? ORDER BY created DESC LIMIT 10''', (owner(), uid(workspace)))]
        return {'status': 'recorded', 'receipts': rows}
    except Exception: return {'status': 'unavailable', 'receipts': []}
