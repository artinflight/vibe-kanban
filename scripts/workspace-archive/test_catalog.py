"""Crash/concurrency contracts on disposable SQLite; no payload mutation."""
import concurrent.futures
import json
import sqlite3
import unittest
import uuid

from catalog import Catalog, Conflict, identity
import test_inventory as inventory_fixtures


class CatalogTests(unittest.TestCase):
    def setUp(self):
        # Reuse the application-metadata fixture; do not fake custody or B proof.
        self.fixture = inventory_fixtures.InventoryTests(methodName='test_missing_required_schema_fails_closed')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.migrate()
        self.fixture.conn.executescript((inventory_fixtures.ROOT / 'crates/db/migrations/20261127000000_workspace_archive_catalog.sql').read_text())
        self.path = self.fixture.db
        self.w = str(self.fixture.wid)
        self.s = str(self.fixture.sid)
        self.op = str(uuid.uuid4())
        self.catalog = Catalog(self.path)
        self.addCleanup(self.catalog.close)
        self.payload = {'prompt': 'exact private message\n', 'executor_config': {
            'model': 'chosen', 'permission': 'review', 'routing': {'mode': 'Recommend'}},
            'perform_git_reset': False, 'force_when_dirty': False, 'retry_process_id': None}

    def ordinary_receipt(self, request, reservation):
        # The later dispatch adapter must bind this reserved ID to the actual
        # ordinary execution; an older/unrelated same-session row is insufficient.
        eid = reservation['execution_id']
        self.catalog.db.execute('INSERT INTO execution_processes VALUES(?,?,?)',
                                (identity(eid), identity(self.s), 'running'))
        self.catalog.dispatched(request, eid)

    def archive(self, stop='cold'):
        c = self.catalog
        c.begin_archive(self.w, 1, self.op)
        if stop == 'preparing': return
        # This fixture exercises catalog transitions, not the B transport proof.
        c.record_verified(self.w, 1, self.op, {'workspace_id': self.w, 'request_version': 1,
            'operation_id': self.op, 'roots': []}, {'fixture_only': 'immutable-point'})
        if stop == 'verified': return
        c.begin_retirement(self.w, 1, self.op)
        if stop == 'retiring': return
        c.finish_retirement(self.w, 1, self.op)

    def test_requested_archived_flag_or_partial_transfer_never_excludes_payload(self):
        c = self.catalog
        self.assertEqual(c.cold_generations(), [])
        c.begin_archive(self.w, 1, self.op)
        self.assertEqual(c.cold_generations(), [])
        c.record_verified(self.w, 1, self.op, {'workspace_id': self.w, 'request_version': 1,
            'operation_id': self.op}, {'fixture_only': 'point'})
        self.assertEqual(c.cold_generations(), [])
        c.begin_retirement(self.w, 1, self.op)
        self.assertEqual(c.cold_generations(), [])
        c.finish_retirement(self.w, 1, self.op)
        self.assertEqual(len(c.cold_generations()), 1)

    def test_message_atomically_invalidates_exclusion_and_retains_all_settings(self):
        self.archive()
        request = str(uuid.uuid4())
        self.catalog.retain_input(self.w, self.s, request, self.payload)
        self.assertEqual(self.catalog.cold_generations(), [])
        self.catalog.close()
        self.catalog = Catalog(self.path)
        self.addCleanup(self.catalog.close)
        row = self.catalog.db.execute('SELECT payload,state FROM workspace_archive_inputs').fetchone()
        self.assertEqual(json.loads(row[0]), self.payload)
        self.assertEqual(row[1], 'waiting_restore')
        self.assertEqual(self.catalog.db.execute('SELECT archived FROM workspaces').fetchone()[0], 0)
        with self.assertRaises(Conflict): self.catalog.reserve_dispatch(request)

    def test_interrupted_restore_keeps_input_and_blocks_new_archive(self):
        self.archive()
        request = str(uuid.uuid4())
        self.catalog.retain_input(self.w, self.s, request, self.payload)
        self.catalog.begin_restore(self.w)
        with CatalogContext(self.path) as reopened:
            self.assertEqual(reopened.state(self.w)['phase'], 'restoring')
            self.assertEqual(reopened.cold_generations(), [])
            with self.assertRaises(Conflict): reopened.begin_restore(self.w)
            with self.assertRaises(Conflict): reopened.reserve_dispatch(request)
        self.catalog.db.execute('UPDATE workspaces SET archived=1 WHERE id=?', (identity(self.w),))
        version = self.catalog.db.execute('SELECT request_version FROM workspace_archive_requests').fetchone()[0]
        with self.assertRaises(Conflict): self.catalog.begin_archive(self.w, version, str(uuid.uuid4()))
        self.assertEqual(self.catalog.db.execute('SELECT count(*) FROM workspace_archive_inputs').fetchone()[0], 1)

    def test_exact_request_idempotence_but_changed_prompt_or_settings_refused(self):
        self.archive()
        request = str(uuid.uuid4())
        row = self.catalog.retain_input(self.w, self.s, request, self.payload)
        self.assertEqual(row, self.catalog.retain_input(self.w, self.s, request, self.payload))
        for changed in ({**self.payload, 'prompt': 'different'},
                        {**self.payload, 'executor_config': {'model': 'other'}}):
            with self.assertRaises(Conflict): self.catalog.retain_input(self.w, self.s, request, changed)
        self.assertEqual(self.catalog.db.execute('SELECT count(*) FROM workspace_archive_inputs').fetchone()[0], 1)

    def test_concurrent_identical_input_is_retained_once(self):
        self.archive()
        request = str(uuid.uuid4())
        def send(_):
            with CatalogContext(self.path) as c:
                return c.retain_input(self.w, self.s, request, self.payload)['request_id']
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(send, range(4)))
        self.assertEqual(set(results), {identity(request)})
        self.assertEqual(self.catalog.db.execute('SELECT count(*) FROM workspace_archive_inputs').fetchone()[0], 1)

    def test_unknown_dispatch_never_replays_after_reopen(self):
        self.archive()
        request = str(uuid.uuid4())
        self.catalog.retain_input(self.w, self.s, request, self.payload)
        self.catalog.begin_restore(self.w)
        self.catalog.finish_restore(self.w, self.op)
        reservation = self.catalog.reserve_dispatch(request)
        self.assertEqual(reservation['payload'], self.payload)
        with CatalogContext(self.path) as reopened:
            with self.assertRaises(Conflict): reopened.reserve_dispatch(request)
            self.assertEqual(reopened.db.execute('SELECT state FROM workspace_archive_inputs').fetchone()[0], 'dispatching')
        with self.assertRaises(Conflict): self.catalog.dispatched(request, str(self.fixture.eid))
        self.ordinary_receipt(request, reservation)
        self.catalog.dispatched(request, reservation['execution_id'])
        with self.assertRaises(Conflict): self.catalog.reserve_dispatch(request)

    def test_concurrent_sends_preserve_order_and_execution_session(self):
        self.archive()
        requests = [str(uuid.uuid4()), str(uuid.uuid4())]
        for n, request in enumerate(requests):
            self.catalog.retain_input(self.w, self.s, request, {**self.payload, 'prompt': f'message {n}'})
        self.catalog.begin_restore(self.w)
        self.catalog.finish_restore(self.w, self.op)
        with self.assertRaises(Conflict): self.catalog.reserve_dispatch(requests[1])
        reservation = self.catalog.reserve_dispatch(requests[0])
        self.assertEqual(reservation['payload']['prompt'], 'message 0')
        with self.assertRaises(Conflict): self.catalog.reserve_dispatch(requests[1])
        _, _, foreign_execution = self.fixture.workspace()
        with self.assertRaises(Conflict): self.catalog.dispatched(requests[0], str(foreign_execution))
        self.ordinary_receipt(requests[0], reservation)
        self.assertEqual(self.catalog.reserve_dispatch(requests[1])['payload']['prompt'], 'message 1')

    def test_message_during_retirement_cannot_certify_cold(self):
        self.archive('retiring')
        self.catalog.retain_input(self.w, self.s, str(uuid.uuid4()), self.payload)
        with self.assertRaises(Conflict): self.catalog.finish_retirement(self.w, 1, self.op)
        self.assertEqual(self.catalog.state(self.w)['phase'], 'retiring')
        self.assertEqual(self.catalog.cold_generations(), [])
        self.catalog.begin_restore(self.w)
        self.catalog.finish_restore(self.w, self.op)
        self.assertEqual(self.catalog.state(self.w)['phase'], 'active')

    def test_history_warming_advances_generation_and_keeps_old_epoch(self):
        self.archive()
        old = self.catalog.recovery(self.w)
        self.catalog.begin_restore(self.w)
        self.catalog.finish_restore(self.w, self.op)
        self.assertEqual(self.catalog.db.execute('SELECT request_version FROM workspace_archive_requests').fetchone()[0], 2)
        self.catalog.begin_archive(self.w, 2, str(uuid.uuid4()))
        self.assertEqual(self.catalog.db.execute('SELECT manifest_sha256 FROM workspace_archive_generations').fetchone()[0], old['manifest_sha256'])
        for sql in ('DELETE FROM workspace_archive_generations',
                    "UPDATE workspace_archive_generations SET manifest='{}'"):
            with self.assertRaises(sqlite3.IntegrityError): self.catalog.db.execute(sql)

    def test_stale_generation_and_duplicate_owner_are_refused(self):
        self.archive('preparing')
        with self.assertRaises(Conflict): self.catalog.begin_archive(self.w, 1, str(uuid.uuid4()))
        self.catalog.db.execute('UPDATE workspaces SET archived=0 WHERE id=?', (identity(self.w),))
        with self.assertRaises(Conflict):
            self.catalog.record_verified(self.w, 1, self.op,
                {'workspace_id': self.w, 'request_version': 1, 'operation_id': self.op}, {'fixture_only': 'point'})
        self.assertEqual(self.catalog.db.execute('SELECT count(*) FROM workspace_archive_generations').fetchone()[0], 0)

    def test_running_pinned_pending_and_foreign_sessions_stay_protected(self):
        self.catalog.db.execute("UPDATE execution_processes SET status='running'")
        with self.assertRaises(Conflict): self.catalog.begin_archive(self.w, 1, self.op)
        self.catalog.db.execute("UPDATE execution_processes SET status='completed'")
        self.catalog.db.execute('UPDATE workspaces SET pinned=1')
        with self.assertRaises(Conflict): self.catalog.begin_archive(self.w, 1, self.op)
        self.catalog.db.execute('UPDATE workspaces SET pinned=0')
        self.archive()
        _, foreign_session, _ = self.fixture.workspace()
        with self.assertRaises(Conflict): self.catalog.retain_input(self.w, str(foreign_session), str(uuid.uuid4()), self.payload)


class CatalogContext:
    def __init__(self, path): self.catalog = Catalog(path)
    def __enter__(self): return self.catalog
    def __exit__(self, *args): self.catalog.close()


if __name__ == '__main__': unittest.main()
