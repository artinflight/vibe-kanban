"""Exact-ID acknowledgement of verified dispatch notes; never general chat read.

The trusted connector supplies the owner. Inventory is a true SQLite read-only
snapshot. Only selected, unchanged, non-manual, non-actionable dispatch notes can
be acknowledged. No browser identity, grant, migration, event or agent operation.
"""
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time
import uuid

from sidechat import Store, Rejected

INVENTORY = 'list_workspace_dot_notifications'
ACKNOWLEDGE = 'acknowledge_dot_dispatch_notes'
NAMES = {INVENTORY, ACKNOWLEDGE}
MAX_IDS = 50


def canonical_id(value):
    if not isinstance(value, str):
        raise Rejected('Canonical UUID required')
    try:
        if str(uuid.UUID(value)) != value:
            raise ValueError()
    except (ValueError, AttributeError):
        raise Rejected('Canonical UUID required') from None
    return value


def opened(path, write=False):
    """Existing fixed private store only; no creation, schema/backfill or grants."""
    path = Path(path)
    if path.is_symlink() or path.stat().st_mode & 0o077:
        raise Rejected('Private notification store unavailable')
    store = Store.__new__(Store)
    store.clock = time.time
    store.db = sqlite3.connect(path.resolve(strict=True).as_uri()+('?mode=rw' if write else '?mode=ro'),
                               uri=True, timeout=1, isolation_level=None)
    store.db.row_factory = sqlite3.Row
    store.db.execute('PRAGMA foreign_keys=ON')
    if not write:
        store.db.execute('PRAGMA query_only=ON')
    return store


def scope(store, principal, workspace):
    store._principal(principal, ('dot',))
    row = store.db.execute('''SELECT t.* FROM scopes s JOIN threads t
        ON t.owner=s.owner AND t.project=s.project AND t.issue=s.issue
        WHERE s.owner=? AND s.workspace=?''', (principal.owner, canonical_id(workspace))).fetchone()
    if not row:
        raise Rejected('Workspace conversation unavailable')
    return row


SELECT = '''SELECT m.id,m.thread,m.workspace,m.seq,m.hash,m.role,
    s.seen,s.manual_unread,s.attention_kind,s.resolved,s.updated,
    d.execution,d.session,d.kind,d.workspace AS dispatch_workspace
    FROM messages m JOIN dot_reply_state s ON s.message=m.id
    LEFT JOIN dispatch_notes d ON d.message=m.id AND d.thread=m.thread
        AND d.owner=? AND d.workspace=m.workspace'''


def protected(row):
    if not row['execution']:
        return 'genuine_conversation'
    if row['manual_unread']:
        return 'manual_unread'
    if row['attention_kind'] and not row['resolved']:
        return 'unresolved_attention'
    return None


def metadata(row, owner):
    # A compare token, not a credential or authorization. Include the complete
    # immutable binding and mutable read state, not message/prompt bodies.
    token = hashlib.sha256(json.dumps([owner]+list(row), separators=(',', ':')).encode()).hexdigest()
    return {'thread_id': row['thread'], 'message_id': row['id'], 'workspace_id': row['workspace'],
            'sequence': row['seq'], 'execution_id': row['execution'],
            'seen': bool(row['seen']), 'manual_unread': bool(row['manual_unread']),
            'attention': {'kind': row['attention_kind'], 'resolved': bool(row['resolved'])},
            'protected_reason': protected(row), 'state_token': token}


def inventory(store, principal, workspace_id, after=0, limit=50, through=None):
    if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= MAX_IDS:
        raise Rejected('Bounded notification pagination required')
    store.db.execute('BEGIN')
    try:
        thread = scope(store, principal, workspace_id)['id']
        high = store.db.execute('SELECT COALESCE(MAX(seq),0) FROM messages WHERE thread=?', (thread,)).fetchone()[0]
        if through is None:
            through = high
        if type(through) is not int or not after <= through <= high:
            raise Rejected('Invalid notification snapshot')
        rows = store.db.execute(SELECT+''' WHERE m.thread=? AND m.role='dot'
            AND m.seq>? AND m.seq<=? AND m.workspace=?
            ORDER BY m.seq LIMIT ?''', (principal.owner, thread, after, through, workspace_id, limit+1)).fetchall()
        selected = rows[:limit]
        result = {'workspace_id': workspace_id, 'thread_id': thread, 'through': through,
                  'notifications': [metadata(r, principal.owner) for r in selected],
                  'next_after': selected[-1]['seq'] if len(rows) > limit else None,
                  'observed_at': store.clock()}
        store.db.execute('COMMIT')
        return result
    except BaseException:
        store.db.execute('ROLLBACK')
        raise


def acknowledge(store, principal, workspace_id, items):
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_IDS:
        raise Rejected('1..50 exact notification selections required')
    for item in items:
        if not isinstance(item, dict) or set(item) != {'thread_id', 'message_id', 'state_token'}:
            raise Rejected('Exact thread/message/state_token selection required')
        canonical_id(item['thread_id']); canonical_id(item['message_id'])
        if not isinstance(item['state_token'], str) or not re.fullmatch('[0-9a-f]{64}', item['state_token']):
            raise Rejected('Inventory state_token required')
    if len({i['message_id'] for i in items}) != len(items):
        raise Rejected('Distinct notification selections required')
    with store.transaction():
        thread = scope(store, principal, workspace_id)['id']
        rows = []
        # Entire batch is owner/thread/workspace validated before any update.
        for item in items:
            row = store.db.execute(SELECT+''' WHERE m.thread=? AND m.id=? AND m.role='dot'
                AND m.workspace=?''',
                (principal.owner, thread, item['message_id'], workspace_id)).fetchone()
            if item['thread_id'] != thread or not row:
                raise Rejected('Selected notification unavailable in this workspace')
            rows.append(row)
        outcomes = []
        for item, row in zip(items, rows):
            reason = protected(row)
            if reason:
                outcome = reason
            elif row['seen']:
                outcome = 'already_seen'  # Never touch timestamps on retries.
            elif metadata(row, principal.owner)['state_token'] != item['state_token']:
                outcome = 'state_changed'
            else:
                store.db.execute('UPDATE dot_reply_state SET seen=1,updated=? WHERE message=?',
                                 (store.clock(), row['id']))
                outcome = 'acknowledged'
            current = store.db.execute(SELECT+' WHERE m.thread=? AND m.id=?',
                                       (principal.owner, thread, row['id'])).fetchone()
            outcomes.append(dict(metadata(current, principal.owner), outcome=outcome))
        high = store.db.execute('SELECT COALESCE(MAX(seq),0) FROM messages WHERE thread=?', (thread,)).fetchone()[0]
        result = {'workspace_id': workspace_id, 'outcomes': outcomes, 'through': high,
                  'observed_at': store.clock(), 'scope': 'selected_ids_only'}
    return result


def call(path, principal, name, args):
    allowed = {'workspace_id', 'after', 'limit', 'through'} if name == INVENTORY else {'workspace_id', 'items'}
    required = {'workspace_id'} if name == INVENTORY else allowed
    if name not in NAMES or not isinstance(args, dict) or not required <= set(args) <= allowed:
        raise Rejected('Exact notification tool arguments required')
    # Validate before opening even the existing store.
    canonical_id(args['workspace_id'])
    store = opened(path, write=name == ACKNOWLEDGE)
    try:
        operation = inventory if name == INVENTORY else acknowledge
        return operation(store, principal, **args)
    finally:
        store.close()
