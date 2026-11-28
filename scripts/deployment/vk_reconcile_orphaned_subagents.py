"""Reconcile only hash-bound, proven pre-boot child activity into failed jobs.

No automatic inventory selection, native thread closure, transcript edit, queue
mutation, or service action. A future native turn supersedes the boot-boundary
failure through the existing application reconciliation rule.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid

ACTIVE = {'running', 'unresolved', 'not_found'}
TERMINAL = {'completed', 'failed', 'killed'}


def utc(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)


def encoded(row):
    return {key: value.hex() if isinstance(value, bytes) else value for key, value in dict(row).items()}


def validate_record(row, boot):
    job = row['job']
    if job['status'] not in ACTIVE or row['parent_status'] not in TERMINAL:
        raise ValueError('Only inactive-parent nonterminal child records may be reconciled')
    if not row['parent_completed_at'] or utc(row['parent_completed_at']) >= boot:
        raise ValueError('Parent did not finish before this host boot')
    native = row.get('native_thread')
    if not native or native['id'] != job['agent_id']:
        raise ValueError('Exact native thread evidence required')
    for field in ('created_at_ms', 'updated_at_ms'):
        if native.get(field) is None or native[field] >= boot.timestamp() * 1000:
            raise ValueError('New or unknown native activity must be preserved')
    proof = row.get('rollout_proof')
    if proof and (not proof['latest_timestamp'] or utc(proof['latest_timestamp']) >= boot):
        raise ValueError('Native transcript contains new or unproven activity')
    if row.get('rollout_exists') and not proof:
        raise ValueError('Existing transcript has not been verified')
    for previous in row['existing_rows']:
        if previous['status'] not in ACTIVE:
            raise ValueError('Never replace terminal job evidence')


def apply(database, audit, *, verify_external, expected_sha256):
    """Atomic insert/update with exact-row comparisons and an inverse receipt."""
    raw = Path(audit).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('Reviewed reconciliation plan changed')
    plan = json.loads(raw)
    boot = utc(plan['boot_UTC'])
    if plan['active_execution_count'] or plan['matching_live_owners']:
        raise ValueError('Plan has active or unowned work')
    records = plan['records']
    keys = {(r['job']['execution_process_id'], r['job']['agent_id']) for r in records}
    if not records or len(keys) != len(records):
        raise ValueError('Nonempty unique execution/agent plan required')
    for row in records:
        validate_record(row, boot)
    verify_external(plan)
    db = sqlite3.connect(database, timeout=2)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    changes = []
    observed = datetime.now(timezone.utc).isoformat()
    # This is a proven upper bound on loss of the old runtime, not an invented
    # successful completion. Ordering it at boot ensures ANY new native turn
    # after boot overrides the acknowledgement, including a concurrent resume.
    failed_before = boot.isoformat()
    try:
        db.execute('BEGIN IMMEDIATE')
        if db.execute("SELECT count(*) FROM execution_processes WHERE status='running'").fetchone()[0]:
            raise ValueError('Active execution appeared; preserve current work')
        for row in records:
            job = row['job']; execution = uuid.UUID(job['execution_process_id']).bytes
            session = uuid.UUID(job['session_id']).bytes
            actual = db.execute('SELECT status,completed_at,session_id FROM execution_processes WHERE id=?', (execution,)).fetchone()
            if not actual or actual['session_id'] != session or actual['status'] != row['parent_status'] or actual['completed_at'] != row['parent_completed_at']:
                raise ValueError('Parent identity or lifecycle changed')
            before = db.execute('SELECT * FROM subagent_jobs WHERE session_id=? AND agent_id=? ORDER BY id', (session, job['agent_id'])).fetchall()
            previous = sorted(row['existing_rows'], key=lambda x: x['id'])
            if [encoded(x) for x in before] != previous:
                raise ValueError('Subagent records changed since audit')
            if before:
                for current in before:
                    original_parent = db.execute('SELECT status,completed_at,session_id FROM execution_processes WHERE id=?', (current['execution_process_id'],)).fetchone()
                    pinned_parent = row.get('existing_parents', {}).get(current['execution_process_id'].hex())
                    if (not original_parent or encoded(original_parent) != pinned_parent
                            or original_parent['session_id'] != session
                            or original_parent['status'] not in TERMINAL
                            or not original_parent['completed_at']
                            or utc(original_parent['completed_at']) >= boot):
                        raise ValueError('Original persisted parent is not proven terminal before boot')
                    db.execute("UPDATE subagent_jobs SET status='failed',completed_at=?,updated_at=? WHERE id=?", (failed_before, observed, current['id']))
                    after = db.execute('SELECT * FROM subagent_jobs WHERE id=?', (current['id'],)).fetchone()
                    changes.append(dict(before=encoded(current), after=encoded(after)))
            else:
                identity = uuid.uuid5(uuid.NAMESPACE_URL, 'vk-preboot-orphan:' + expected_sha256 + ':' + job['execution_process_id'] + ':' + job['agent_id']).bytes
                db.execute('''INSERT INTO subagent_jobs(id,session_id,execution_process_id,agent_id,nickname,status,completed_at,created_at,updated_at)
                    VALUES(?,?,?,?,?,'failed',?,?,?)''', (identity, session, execution, job['agent_id'], job['nickname'], failed_before, job['created_at'], observed))
                after = db.execute('SELECT * FROM subagent_jobs WHERE id=?', (identity,)).fetchone()
                changes.append(dict(before=None, after=encoded(after)))
        verify_external(plan)
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()
    return dict(format='vk-preboot-subagent-reconciliation-v1', plan_sha256=expected_sha256,
                boot_boundary_UTC=failed_before, observed_UTC=observed,
                status='failed', reason='No surviving runtime for pre-boot child; successful completion is unproven',
                history_modified=False, native_threads_modified=False, changes=changes)
