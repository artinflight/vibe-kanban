"""Tiny copied SQLite cases. No server/agent, acknowledgements or cancellation."""
from pathlib import Path
import hashlib
import sqlite3
import tempfile
import unittest
import restart_queue_boundary as boundary


class QueueBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/'db.sqlite'
        with sqlite3.connect(self.db) as c:
            c.executescript('''CREATE TABLE sessions(id BLOB PRIMARY KEY);
            CREATE TABLE execution_processes(id BLOB PRIMARY KEY,status TEXT,completed_at TEXT);
            CREATE TABLE turn_github_sync_user_queue(session_id BLOB PRIMARY KEY,state TEXT,data TEXT);
            CREATE TABLE turn_github_sync_incoming(id BLOB PRIMARY KEY,session_id BLOB,state TEXT,data TEXT);''')
            c.execute('INSERT INTO sessions VALUES(?)',(b'a'*16,))

    def write(self,sql,args=()):
        with sqlite3.connect(self.db) as c:c.execute(sql,args)

    def api(self):return {'complete':True,'pending_sessions':[]}

    def test_empty_consistent_boundary_and_verified_freeze(self):
        before=boundary.live(self.db,self.api)
        self.assertEqual(boundary.frozen(self.db,before,incumbent_frozen=True,consumers_quiet=True)['fingerprint'],before['fingerprint'])
        self.assertFalse(before['writer_fence_established'])

    def test_queued_and_uncertain_work_is_held_without_content_change(self):
        for state in ['queued','dispatching']:
            self.write('INSERT OR REPLACE INTO turn_github_sync_user_queue VALUES(?,?,?)',(b'a'*16,state,'private exact prompt'))
            old=hashlib.sha256(self.db.read_bytes()).hexdigest()
            with self.assertRaises(boundary.BoundaryHeld):boundary.live(self.db,self.api)
            self.assertEqual(hashlib.sha256(self.db.read_bytes()).hexdigest(),old)

    def test_uncertainty_receipt_is_retained_not_a_dispatch_veto(self):
        self.write('INSERT INTO turn_github_sync_incoming VALUES(?,?,?,?)',(b'b'*16,b'a'*16,'received','private'))
        before=boundary.live(self.db,self.api)
        self.assertEqual(before['unresolved_incoming_preserved_not_resumed'],1)
        self.assertFalse(before['incoming_automatic_replay'])
        self.assertEqual(before['incoming_pending'][0]['payload_sha256'],hashlib.sha256(b'private').hexdigest())
        boundary.frozen(self.db,before,incumbent_frozen=True,consumers_quiet=True)

    def test_handled_and_dismissed_receipts_are_retained_not_pending(self):
        for i,state in enumerate(['handled','dismissed']):
            self.write('INSERT INTO turn_github_sync_incoming VALUES(?,?,?,?)',(bytes([i])*16,b'a'*16,state,'private'))
        result=boundary.live(self.db,self.api)
        self.assertEqual(result['counts']['incoming'],2);self.assertEqual(result['incoming_pending'],[])

    def test_running_process_blocks(self):
        self.write('INSERT INTO execution_processes VALUES(?,?,?)',(b'c'*16,'running',None))
        with self.assertRaises(boundary.BoundaryHeld):boundary.live(self.db,self.api)

    def test_partial_API_or_unknown_state_blocks(self):
        with self.assertRaises(boundary.BoundaryHeld):boundary.live(self.db,lambda:{'complete':False,'pending_sessions':[]})
        self.write('INSERT INTO turn_github_sync_user_queue VALUES(?,?,?)',(b'a'*16,'unknown','private'))
        with self.assertRaises(boundary.BoundaryHeld):boundary.live(self.db,self.api)

    def test_in_memory_queue_blocks(self):
        with self.assertRaises(boundary.BoundaryHeld):boundary.live(self.db,lambda:{'complete':True,'pending_sessions':['fixture']})

    def test_arrival_during_API_probe_blocks(self):
        def arrival():
            self.write('INSERT INTO turn_github_sync_incoming VALUES(?,?,?,?)',(b'b'*16,b'a'*16,'received','private'))
            return self.api()
        with self.assertRaises(boundary.BoundaryHeld):boundary.live(self.db,arrival)

    def test_late_completed_work_not_silently_dropped(self):
        before=boundary.live(self.db,self.api)
        self.write('INSERT INTO execution_processes VALUES(?,?,?)',(b'c'*16,'completed','fixture-time'))
        with self.assertRaises(boundary.BoundaryHeld):boundary.frozen(self.db,before,incumbent_frozen=True,consumers_quiet=True)

    def test_missing_table_and_fake_fence_block(self):
        before=boundary.live(self.db,self.api)
        with self.assertRaises(boundary.BoundaryHeld):boundary.frozen(self.db,before,incumbent_frozen=False,consumers_quiet=True)
        self.write('DROP TABLE turn_github_sync_incoming')
        with self.assertRaises(boundary.BoundaryHeld):boundary.live(self.db,self.api)

    def test_same_length_uncertain_input_change_is_detected(self):
        self.write('INSERT INTO turn_github_sync_incoming VALUES(?,?,?,?)',(b'b'*16,b'a'*16,'received','private'))
        before=boundary.live(self.db,self.api)
        self.write('UPDATE turn_github_sync_incoming SET data=?',('changed',))
        with self.assertRaises(boundary.BoundaryHeld):boundary.frozen(self.db,before,incumbent_frozen=True,consumers_quiet=True)
