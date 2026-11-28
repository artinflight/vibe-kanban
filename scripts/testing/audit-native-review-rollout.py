"""Read-only coverage audit of active Vibe Codex saved reviewer contexts.

Reads only selected SQLite columns and turn_context records, never credentials,
conversation text, approval responses or history mutations. Large non-context
records are skipped in bounded chunks. Private identities belong in private output.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import uuid


def read_only(path):
    return sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)


def last_context(path):
    latest = None
    limit = 1024 * 1024
    with path.open('rb') as source:
        remaining = os.fstat(source.fileno()).st_size
        while remaining > 0:
            chunk = source.readline(min(limit, remaining))
            remaining -= len(chunk)
            if not chunk: break
            context = re.search(rb'"type"\s*:\s*"turn_context"', chunk[:256]) is not None
            if not chunk.endswith(b'\n'):
                if context: raise ValueError('context record exceeds audit limit or is incomplete')
                while remaining > 0 and not chunk.endswith(b'\n'):
                    chunk = source.readline(min(limit, remaining))
                    remaining -= len(chunk)
                continue
            if context:
                record = json.loads(chunk)
                if record.get('type') != 'turn_context': continue
                value = record['payload']
                latest = {'turnId': value.get('turn_id'), 'reviewer': value.get('approvals_reviewer'),
                          'approvalPolicy': value.get('approval_policy'), 'sandbox': value.get('sandbox_policy', {}).get('type')}
    return latest


def audit(database, home):
    indexes = sorted(home.glob('state_*.sqlite'), key=lambda p: int(p.stem.split('_')[-1]))
    if not indexes: raise ValueError('native index unavailable; no guessed history path')
    results = []
    with read_only(database) as vibe, read_only(indexes[-1]) as native:
        for execution, session, action in vibe.execute("SELECT id,session_id,executor_action FROM execution_processes WHERE status='running'"):
            payload = json.loads(action).get('typ', {})
            if payload.get('executor_config', {}).get('executor') != 'CODEX': continue
            binding = vibe.execute('SELECT agent_session_id FROM coding_agent_turns WHERE execution_process_id=? ORDER BY rowid DESC LIMIT 1', [execution]).fetchone()
            row = {'executionId': str(uuid.UUID(bytes=execution)), 'sessionId': str(uuid.UUID(bytes=session))}
            if not binding or not binding[0]:
                row['unverified'] = 'native thread not registered';results.append(row);continue
            row['threadId'] = binding[0]
            indexed = native.execute('SELECT rollout_path FROM threads WHERE id=?', [binding[0]]).fetchone()
            if not indexed:
                row['unverified'] = 'native index binding unavailable';results.append(row);continue
            path = Path(indexed[0]).resolve()
            if not path.is_relative_to(home.resolve()):
                row['unverified'] = 'native history is outside selected home';results.append(row);continue
            try:
                row['context'] = last_context(path)
                if row['context'] is None: row['unverified'] = 'no saved context'
                elif (row['context'].get('reviewer') not in {'user', 'auto_review', 'guardian_subagent'}
                      or row['context'].get('approvalPolicy') not in {'never', 'on-request', 'on-failure', 'untrusted'}
                      or row['context'].get('sandbox') not in {'read-only', 'workspace-write', 'danger-full-access'}):
                    row['unverified'] = 'unknown saved policy shape'
            except (OSError, ValueError) as error:
                row['unverified'] = type(error).__name__
            results.append(row)
    return {'readOnly': True, 'observedAt': datetime.now(timezone.utc).isoformat(), 'activeCodexExecutions': len(results), 'executions': results,
            'autoReviewContexts': sum(r.get('context', {}).get('reviewer') == 'auto_review' for r in results if r.get('context')),
            'unknownContexts': sum(bool(r.get('unverified')) for r in results),
            'appLinkPolicy': 'verify entry policy/config separately; reviewer-only audit does not prove sandbox safety'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--codex-home', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(args.codex_home.resolve()) or args.output.resolve().is_relative_to(args.database.resolve().parent):
        raise ValueError("audit output must be outside live native and Vibe data directories")
    value = audit(args.database, args.codex_home)
    args.output.write_text(json.dumps(value, indent=2) + '\n');args.output.chmod(0o600)
    print('Read-only audit:', value['activeCodexExecutions'], 'active Codex executions;', value['autoReviewContexts'], 'saved auto_review;', value['unknownContexts'], 'unverified.')


if __name__ == '__main__': main()
