"""Caller evidence and derived presentation, independent of managed ownership.

The current tunnel/stdio boundary has no verified initiating-actor attestation.
Neither tool args/_meta nor the access owner/transport channel prove a caller.
There is deliberately no path here that labels root Dot, a manager or a user.
"""
import json

CURRENT = 'runtime_caller_not_attested'
HISTORICAL = 'historical_caller_not_recorded'
PURPOSES = {'start_workspace': 'begin the requested work',
            'run_session_prompt': 'continue the requested work'}


def current_caller():
    """Trusted host observation: this runtime exposes no caller verification."""
    return {'kind': 'unknown', 'verification': 'unavailable', 'reason': CURRENT}


def caller_record(value=None):
    # Unknown is not an alias for Dot. No caller-controlled claim can upgrade it.
    if isinstance(value, dict) and value == current_caller():
        return current_caller()
    return {'kind': 'unknown', 'verification': 'unavailable', 'reason': HISTORICAL}


def note_body(kind, execution):
    purpose = PURPOSES.get(kind, 'perform the requested work')
    return ('The workspace agent was prompted to '+purpose+'.\n\n'
            'Caller: unknown (no verified initiating-caller identity).\n'
            'Accepted execution: '+execution)


def stored_caller(db, table, owner, execution):
    # Table names are fixed internal constants, never tool arguments.
    if table not in ('dispatch_receipt_callers', 'dispatch_note_callers'):
        raise ValueError('Unsupported caller record')
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    if not exists:
        return caller_record()
    row = db.execute('SELECT caller FROM '+table+' WHERE owner=? AND execution=?', (owner, execution)).fetchone()
    try:
        return caller_record(json.loads(row[0])) if row else caller_record()
    except (ValueError, TypeError):
        return caller_record()


def presentation(store, principal, message):
    """Read-only, exact-binding derivation; never replaces raw body/hash/ID."""
    store._principal(principal, ('owner', 'dot'))
    row = store.db.execute('''SELECT d.kind,d.execution FROM dispatch_notes d
        JOIN messages m ON m.id=d.message AND m.thread=d.thread AND m.workspace=d.workspace
        JOIN threads t ON t.id=m.thread AND t.owner=d.owner
        WHERE d.owner=? AND d.message=? AND d.thread=? AND d.workspace=? AND m.role='dot' ''',
        (principal.owner, message['id'], message['thread'], message['workspace'])).fetchone()
    if not row:
        return {}
    caller = stored_caller(store.db, 'dispatch_note_callers', principal.owner, row['execution'])
    return {'caller': caller, 'ownership_signal': False,
            'presentation': {'author_label': 'Dispatch', 'body': note_body(row['kind'], row['execution']),
                             'derived': True, 'stored_message_unchanged': True}}
