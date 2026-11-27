"""Durable physical archive state and exact-message revival admission.

This module does not copy, retire, restore or dispatch. The integrated owner
must hold workspace custody and supply independently verified recovery before
advancing physical state. SQL transitions are short; no network work runs in a
transaction. Failed/stale transitions never confer Nightly exclusion.
"""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid


class Conflict(RuntimeError):
    pass


def identity(value):
    return uuid.UUID(str(value)).bytes


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


class Catalog:
    def __init__(self, database):
        self.db = sqlite3.connect(Path(database).resolve().as_uri() + '?mode=rw', uri=True, isolation_level=None, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        # Never migrate the live database implicitly from a helper process.
        self.db.execute('SELECT request_version FROM workspace_archive_state LIMIT 0')

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def state(self, workspace):
        row = self.db.execute('SELECT * FROM workspace_archive_state WHERE workspace_id=?',
                              (identity(workspace),)).fetchone()
        return dict(row) if row else None

    def _archive_current(self, workspace, version):
        row = self.db.execute('''SELECT w.archived,w.pinned,r.requested_state,r.request_version
            FROM workspaces w JOIN workspace_archive_requests r ON r.workspace_id=w.id
            WHERE w.id=?''', (identity(workspace),)).fetchone()
        if (row is None or not row['archived'] or row['pinned']
                or row['requested_state'] != 'archived' or row['request_version'] != version):
            raise Conflict('Archive generation is no longer eligible')
        wid = identity(workspace)
        checks = [
            ('SELECT 1 FROM workspace_archive_reads WHERE workspace_id=?', 'pending history restore'),
            ('''SELECT 1 FROM execution_processes e JOIN sessions s ON s.id=e.session_id
                WHERE s.workspace_id=? AND e.status='running' LIMIT 1''', 'running execution'),
            ('''SELECT 1 FROM workspace_archive_inputs WHERE workspace_id=?
                AND state NOT IN ('dispatched','cancelled') LIMIT 1''', 'retained revival input'),
            ('''SELECT 1 FROM turn_github_sync_incoming WHERE workspace_id=?
                AND state NOT IN ('handled','dismissed') LIMIT 1''', 'pending input'),
            ('SELECT 1 FROM turn_github_sync_user_queue WHERE workspace_id=? LIMIT 1', 'queued input'),
            ('''SELECT 1 FROM watcher_job_leases WHERE workspace_id=?
                AND closed_at IS NULL LIMIT 1''', 'open child lease'),
            ('''SELECT 1 FROM scratch d JOIN sessions s ON s.id=d.id
                WHERE s.workspace_id=? AND d.scratch_type='DRAFT_FOLLOW_UP'
                AND (NOT json_valid(d.payload) OR
                    coalesce(json_extract(d.payload,'$.type'),'') != 'DRAFT_FOLLOW_UP' OR
                    coalesce(json_type(d.payload,'$.data.message'),'null') NOT IN ('text','null') OR
                    trim(coalesce(json_extract(d.payload,'$.data.message'),'')) != '') LIMIT 1''', 'draft input'),
        ]
        for sql, reason in checks:
            if self.db.execute(sql, (wid,)).fetchone():
                raise Conflict('Archive held by ' + reason)

    def _owned(self, workspace, version, operation, phases):
        row = self.state(workspace)
        if (row is None or row['request_version'] != version
                or row['operation_id'] != operation or row['phase'] not in phases):
            raise Conflict('Physical archive operation differs or needs reconciliation')
        return row

    def _phase(self, workspace, phase):
        self.db.execute('''UPDATE workspace_archive_state SET phase=?,last_error=NULL,
            updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE workspace_id=?''',
                        (phase, identity(workspace)))

    def begin_archive(self, workspace, version, operation):
        operation = str(uuid.UUID(operation))
        with self.transaction():
            self._archive_current(workspace, version)
            prior = self.state(workspace)
            if prior and prior['phase'] != 'active':
                raise Conflict('Existing archive operation must be reconciled, not duplicated')
            self.db.execute('''INSERT INTO workspace_archive_state
                (workspace_id,request_version,operation_id,phase) VALUES (?,?,?,'preparing')
                ON CONFLICT(workspace_id) DO UPDATE SET request_version=excluded.request_version,
                operation_id=excluded.operation_id,phase='preparing',last_error=NULL,
                updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')''',
                            (identity(workspace), version, operation))

    def record_verified(self, workspace, version, operation, manifest, recovery_locator):
        """Record the owner's already-restored manifest; still no exclusion."""
        body = canonical(manifest)
        digest = hashlib.sha256(body.encode()).hexdigest()
        if (manifest.get('workspace_id') != str(uuid.UUID(workspace))
                or manifest.get('request_version') != version
                or manifest.get('operation_id') != operation):
            raise Conflict('Restored manifest does not bind this workspace generation')
        if not isinstance(recovery_locator, dict) or not recovery_locator:
            raise Conflict('An exact independently restorable recovery locator is required')
        with self.transaction():
            self._owned(workspace, version, operation, ('preparing',))
            self._archive_current(workspace, version)
            self.db.execute('''INSERT INTO workspace_archive_generations
                (workspace_id,request_version,operation_id,manifest_sha256,manifest,recovery_locator)
                VALUES (?,?,?,?,?,?)''',
                (identity(workspace), version, operation, digest, body, canonical(recovery_locator)))
            self._phase(workspace, 'verified')
        return digest

    def begin_retirement(self, workspace, version, operation):
        with self.transaction():
            self._owned(workspace, version, operation, ('verified',))
            self._archive_current(workspace, version)
            self._phase(workspace, 'retiring')

    def finish_retirement(self, workspace, version, operation):
        # Caller has verified actual retirement under exclusive workspace custody.
        with self.transaction():
            self._owned(workspace, version, operation, ('retiring',))
            self._archive_current(workspace, version)
            self._phase(workspace, 'cold')

    def recovery(self, workspace):
        row = self.db.execute('''SELECT g.* FROM workspace_archive_state s
            JOIN workspace_archive_generations g ON g.workspace_id=s.workspace_id
                AND g.request_version=s.request_version AND g.operation_id=s.operation_id
            WHERE s.workspace_id=?''', (identity(workspace),)).fetchone()
        if row is None:
            raise Conflict('No accepted recovery generation exists')
        if hashlib.sha256(row['manifest'].encode()).hexdigest() != row['manifest_sha256']:
            raise Conflict('Archive catalog manifest is damaged')
        return dict(row, manifest=json.loads(row['manifest']),
                    recovery_locator=json.loads(row['recovery_locator']))

    def io(self, workspace):
        state = self.state(workspace)
        if state is None:
            raise Conflict('No physical archive owner')
        row = self.db.execute('SELECT * FROM workspace_archive_io WHERE operation_id=? AND workspace_id=?',
                              (state['operation_id'], identity(workspace))).fetchone()
        return dict(row, journal=json.loads(row['journal'])) if row else None

    def save_io(self, workspace, operation, journal, revision=None):
        with self.transaction():
            state = self.state(workspace)
            if state is None or state['operation_id'] != operation:
                raise Conflict('Physical journal owner changed')
            if revision is None:
                self.db.execute('INSERT INTO workspace_archive_io(operation_id,workspace_id,journal) VALUES(?,?,?)',
                                (operation, identity(workspace), canonical(journal)))
            else:
                changed = self.db.execute("""UPDATE workspace_archive_io SET journal=?,revision=revision+1
                    WHERE operation_id=? AND workspace_id=? AND revision=?""",
                    (canonical(journal), operation, identity(workspace), revision)).rowcount
                if changed != 1:
                    raise Conflict('Physical journal changed; reconcile before continuing')

    def check_archive(self, workspace, version, operation, phases):
        with self.transaction():
            self._owned(workspace, version, operation, phases)
            self._archive_current(workspace, version)

    def cancel_preparation(self, workspace, operation):
        # Caller proves all original roots intact under exclusive custody. An
        # uncertain B capture remains recorded; no new operation is dispatched.
        with self.transaction():
            state = self.state(workspace)
            if state is None or state['operation_id'] != operation or state['phase'] != 'preparing':
                raise Conflict('Only intact preparation can be cancelled')
            self._phase(workspace, 'active')
            self.db.execute("UPDATE workspace_archive_inputs SET state='ready' WHERE workspace_id=? AND state='waiting_restore'",
                            (identity(workspace),))

    def retain_input(self, workspace, session, request, payload):
        """Commit exact input and invalidate exclusion before any restoration."""
        encoded = canonical(payload)
        wid, sid, rid = map(identity, (workspace, session, request))
        with self.transaction():
            old = self.db.execute('SELECT * FROM workspace_archive_inputs WHERE request_id=?',
                                  (rid,)).fetchone()
            if old:
                if (old['workspace_id'], old['session_id'], old['payload']) != (wid, sid, encoded):
                    raise Conflict('Request identity was reused with different input or settings')
                return dict(old)
            row = self.db.execute('SELECT workspace_id FROM sessions WHERE id=?', (sid,)).fetchone()
            if row is None or row[0] != wid:
                raise Conflict('Session does not belong to this workspace')
            state = self.state(workspace)
            waiting = 'ready' if state is None or state['phase'] == 'active' else 'waiting_restore'
            self.db.execute('''INSERT INTO workspace_archive_inputs
                (request_id,workspace_id,session_id,payload,state) VALUES (?,?,?,?,?)''',
                            (rid, wid, sid, encoded, waiting))
            # The existing outbox trigger advances its version in this transaction.
            self.db.execute('UPDATE workspaces SET archived=0 WHERE id=?', (wid,))
            return dict(self.db.execute('SELECT * FROM workspace_archive_inputs WHERE request_id=?',
                                        (rid,)).fetchone())

    def begin_restore(self, workspace):
        with self.transaction():
            row = self.state(workspace)
            if row is None or row['phase'] not in ('cold', 'verified', 'retiring'):
                raise Conflict('Existing restoration/copy needs explicit reconciliation')
            self.recovery(workspace)
            # A warm read also invalidates the old physical generation, even
            # when the UI archived flag stays set. A later rearchive gets a new
            # immutable recovery point instead of overwriting this one.
            self.db.execute('''UPDATE workspace_archive_requests
                SET request_version=request_version+1,
                    updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE workspace_id=?''',
                            (identity(workspace),))
            self._phase(workspace, 'restoring')

    def finish_restore(self, workspace, operation):
        # Caller verifies the complete restored tree and dependency closure first.
        with self.transaction():
            state = self.state(workspace)
            if not state or state['phase'] != 'restoring' or state['operation_id'] != operation:
                raise Conflict('Restoration ownership changed')
            self._phase(workspace, 'active')
            self.db.execute('''UPDATE workspace_archive_inputs SET state='ready',error=NULL,
                updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
                WHERE workspace_id=? AND state='waiting_restore' ''', (identity(workspace),))

    def reserve_dispatch(self, request):
        """Reserve once, before calling ordinary admission. Never retries unknown."""
        with self.transaction():
            row = self.db.execute('SELECT * FROM workspace_archive_inputs WHERE request_id=?',
                                  (identity(request),)).fetchone()
            if row is None or row['state'] != 'ready':
                raise Conflict('Input is not ready or dispatch is already reserved')
            state = self.state(str(uuid.UUID(bytes=row['workspace_id'])))
            if state is not None and state['phase'] != 'active':
                raise Conflict('Restored payloads are not ready')
            first = self.db.execute('''SELECT request_id FROM workspace_archive_inputs
                WHERE session_id=? AND state NOT IN ('dispatched','cancelled') ORDER BY rowid LIMIT 1''',
                                   (row['session_id'],)).fetchone()
            if first is None or first[0] != identity(request):
                raise Conflict('Earlier input must be dispatched or reconciled first')
            execution = uuid.uuid4()
            self.db.execute("UPDATE workspace_archive_inputs SET state='dispatching',execution_id=? WHERE request_id=?",
                            (execution.bytes, identity(request)))
            return dict(payload=json.loads(row['payload']), execution_id=str(execution),
                        request_id=str(uuid.UUID(request)))

    def dispatched(self, request, execution):
        with self.transaction():
            row = self.db.execute('''SELECT i.state,i.execution_id,e.session_id,i.session_id
                FROM workspace_archive_inputs i LEFT JOIN execution_processes e ON e.id=?
                WHERE i.request_id=?''', (identity(execution), identity(request))).fetchone()
            if (row is None or row[2] != row[3] or row[0] not in ('dispatching', 'dispatched')
                    or row[1] != identity(execution)):
                raise Conflict('Exact ordinary execution receipt required')
            self.db.execute("UPDATE workspace_archive_inputs SET state='dispatched',execution_id=? WHERE request_id=?",
                            (identity(execution), identity(request)))

    def cold_generations(self):
        """Candidates only; consumer must verify retired paths/normal B closure."""
        rows = self.db.execute('''SELECT s.workspace_id,s.request_version,s.operation_id
            FROM workspace_archive_state s JOIN workspace_archive_requests r USING(workspace_id)
            JOIN workspaces w ON w.id=s.workspace_id
            WHERE s.phase='cold' AND r.requested_state='archived'
                AND s.request_version=r.request_version AND w.archived=1 AND w.pinned=0''').fetchall()
        result = []
        for row in rows:
            workspace = str(uuid.UUID(bytes=row['workspace_id']))
            try:
                self._archive_current(workspace, row['request_version'])
            except Conflict:
                continue
            result.append(self.recovery(workspace))
        return result
