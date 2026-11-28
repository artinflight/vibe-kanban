"""Bind original replies separately from authenticated checkpoint annotations.

Read-only: never rewrite summaries, history, checkpoint state or review flags.
"""
import hashlib
import json
import sqlite3
import uuid
from pathlib import Path
from urllib.parse import urlencode

MARKER = '\n\n[Automatic GitHub checkpoint]\n'
OBSERVATION_REASON = 'completed-turn observation is unproven; original obligation retained; scoped reconciliation required'


def digest(text):
    return hashlib.sha256(text.strip().encode()).hexdigest()


def checkpoint_message(report):
    coverage = ''
    for repo in report.get('repositories', []):
        path = repo.get('path', 'unknown repository')
        receipt = repo.get('receipt') or {}
        if isinstance(receipt.get('commit'), str):
            coverage += '\nRepository: ' + path + '. Commit: ' + receipt['commit'] + '. ' + (receipt.get('pr') or {}).get('url', 'Exact base coverage; no new PR.')
        else:
            coverage += '\nRepository: ' + path + '. Remote coverage unverified.'
    return ('Git preservation ' + report.get('state', 'blocked') + '. Workspace: ' + report.get('workspace', 'unknown') + '. Turn: ' + report.get('turn', 'unknown') + '. ' + report.get('reason', 'unverifiable receipt') + '. Excluded files are not Git-protected.' + coverage)


def bind_summary(summary, *, execution, workspace, report=None, observation_state=None):
    """Strip only a trailing notice reproducible from this turn's durable state."""
    messages = []
    if report:
        if report.get('turn') != execution or report.get('workspace') != workspace:
            raise ValueError('Checkpoint report belongs to another turn/workspace')
        messages.append(checkpoint_message(report))
    if observation_state in ('pending', 'observing', 'failed'):
        messages.append(checkpoint_message(dict(state='blocked', workspace=workspace, turn=execution, reason=OBSERVATION_REASON)))
    final = summary
    removed = []
    # Reconciliation can append more than one distinct, authenticated notice.
    while True:
        found = next((MARKER + value for value in messages if final.endswith(MARKER + value)), None)
        if found is None:
            break
        final = final[:-len(found)]
        removed.append(hashlib.sha256(found.encode()).hexdigest())
    if not final.strip():
        raise ValueError('Nonempty original selected final required')
    return dict(execution=execution, selected_final_sha256=digest(final), summary_sha256=digest(summary), checkpoint_annotation_sha256=removed)


def bind_database(database, executions):
    result = []
    with sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True, timeout=2) as db:
        db.execute('BEGIN')
        for execution in executions:
            row = db.execute('''SELECT t.summary, lower(hex(s.workspace_id)), g.report, g.observation_state
                FROM coding_agent_turns t JOIN execution_processes e ON e.id=t.execution_process_id
                JOIN sessions s ON s.id=e.session_id LEFT JOIN turn_github_sync g ON g.execution_process_id=e.id
                WHERE lower(hex(e.id))=? AND e.status='completed' AND e.exit_code=0''', (execution.replace('-', ''),)).fetchone()
            if not row or not row[0]:
                raise ValueError('Completed selected final unavailable: ' + execution)
            result.append(bind_summary(row[0], execution=execution, workspace=str(uuid.UUID(row[1])), report=json.loads(row[2]) if row[2] else None, observation_state=row[3]))
    return result


def verify_history(read_api, expected):
    """Follow real cursors; capture failures never become successful acceptance."""
    before = None
    cursors = set()
    found = 0
    entries = 0
    for page_number in range(1000):
        query = dict(limit=100)
        if before is not None:
            query['before'] = before
        page = read_api('execution-processes/' + expected['execution'] + '/log-history?' + urlencode(query))
        data = page.get('data') or {}
        if not page.get('success') or data.get('capture_error') or data.get('capture_pending'):
            raise ValueError('History capture unavailable: ' + expected['execution'])
        for row in data.get('entries', []):
            content = row.get('entry', {}).get('content')
            entries += 1
            if isinstance(content, dict) and content.get('entry_type', {}).get('type') == 'assistant_message':
                if digest(content['content']) == expected['selected_final_sha256']:
                    found += 1
        before = data.get('next_before')
        if before is None:
            if not found:
                raise ValueError('Selected final absent from complete history: ' + expected['execution'])
            return dict(execution=expected['execution'], pages=page_number + 1, entries=entries, exact_final_matches=found, capture_verified=True)
        encoded = json.dumps(before, sort_keys=True)
        if encoded in cursors:
            raise ValueError('History pagination cursor did not advance')
        cursors.add(encoded)
    raise ValueError('History pagination exceeds acceptance bound')
