#!/usr/bin/env python3
"""Execute the real migration and model SQL using fake SQLite rows only.
No live database/provider, backend compilation, new dependencies or credentials.
"""
import pathlib, re, sqlite3, unittest
ROOT=pathlib.Path(__file__).resolve().parents[2]
MIGRATION=ROOT/'crates/db/migrations/20261021140000_provider_handoff_reservations.sql'
MODEL=ROOT/'crates/db/src/models/provider_handoff.rs'
QUERIES=re.findall(r'sqlx::query\("([^"\n]+)"\)',MODEL.read_text())
SESSION=next(q for q in QUERIES if q.startswith('INSERT INTO sessions'))
RESERVE=next(q for q in QUERIES if q.startswith('INSERT INTO provider_handoff'))
DISPATCH=next(q for q in QUERIES if "SET state='dispatching'" in q)
OUTCOME=next(q for q in QUERIES if 'SET state=CASE' in q)
ACTION='{"typ":{"type":"CodingAgentInitialRequest","executor_config":{"executor":"CLAUDE_CODE"}},"next_action":null}'
class Fence(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.executescript('''PRAGMA foreign_keys=ON;
            CREATE TABLE workspaces(id BLOB PRIMARY KEY);
            CREATE TABLE sessions(id BLOB PRIMARY KEY,workspace_id BLOB,executor TEXT,name TEXT,agent_working_dir TEXT);
            CREATE TABLE execution_processes(id BLOB PRIMARY KEY,session_id BLOB,status TEXT,run_reason TEXT,executor_action TEXT);
            INSERT INTO workspaces VALUES('ws'),('other');
            INSERT INTO sessions VALUES('parent','ws','CODEX',NULL,NULL),('ordinary','ws','CODEX',NULL,NULL),('other-session','other','CODEX',NULL,NULL);
            INSERT INTO execution_processes VALUES('initial','parent','failed','codingagent','{}');''')
        self.db.executescript(MIGRATION.read_text())
    def tearDown(self):self.db.close()
    def reserve(self,transition='transfer',session='child',execution='next'):
        with self.db:
            self.db.execute(SESSION,(session,'ws','CLAUDE_CODE',None))
            self.db.execute(RESERVE,(transition,'ws','initial',session,execution,ACTION,'snapshot','verified-fence'))
    def insert(self,execution='next',session='child',action=ACTION):
        self.db.execute('INSERT INTO execution_processes VALUES(?,?,\'running\',\'codingagent\',?)',(execution,session,action))
    def test_exact_reserved_initial_execution_is_admitted_once(self):
        self.reserve();self.assertEqual(self.db.execute(DISPATCH,('transfer',)).rowcount,1)
        self.assertEqual(self.db.execute(DISPATCH,('transfer',)).rowcount,0)
        self.insert()
        with self.assertRaises(sqlite3.IntegrityError):self.insert()
    def test_all_ordinary_callers_are_fenced_even_after_an_earlier_idle_read(self):
        self.assertEqual(self.db.execute("SELECT count(*) FROM execution_processes WHERE status='running'").fetchone()[0],0)
        self.reserve()
        with self.assertRaises(sqlite3.IntegrityError):self.insert('other-id','ordinary')
    def test_running_predecessor_or_other_worker_rejects_reservation_atomically(self):
        self.db.execute("UPDATE execution_processes SET status='running' WHERE id='initial'");self.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):self.reserve()
        self.assertIsNone(self.db.execute("SELECT id FROM sessions WHERE id='child'").fetchone())
        self.db.execute("UPDATE execution_processes SET status='failed' WHERE id='initial'")
        self.insert('other-worker','ordinary');self.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):self.reserve()
    def test_second_owner_and_same_transition_cannot_reserve_again(self):
        self.reserve()
        with self.assertRaises(sqlite3.IntegrityError):self.reserve('second','child2','next2')
        with self.assertRaises(sqlite3.IntegrityError):self.reserve('transfer','child3','next3')
    def test_changed_model_action_id_or_session_cannot_use_the_fence(self):
        self.reserve();self.db.execute(DISPATCH,('transfer',))
        for execution,session,action in [('next','child','{}'),('different','child',ACTION),('next','ordinary',ACTION)]:
            with self.assertRaises(sqlite3.IntegrityError):self.insert(execution,session,action)
    def test_lost_reply_hold_and_elapsed_time_never_release_ownership(self):
        self.reserve();self.db.execute(DISPATCH,('transfer',));self.insert()
        self.db.execute(next(q for q in QUERIES if 'terminal monitor:' in q),('held','next'))
        self.db.execute("UPDATE execution_processes SET status='failed' WHERE id='next'")
        with self.assertRaises(sqlite3.IntegrityError):self.insert('retry','ordinary')
        self.assertEqual(self.db.execute(DISPATCH,('transfer',)).rowcount,0)
    def test_existing_stopped_execution_cannot_reactivate_behind_reserved_child(self):
        self.reserve()
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE execution_processes SET status='running' WHERE id='initial'")
    def test_other_workspace_is_untouched(self):
        self.reserve();self.insert('unrelated','other-session')
    def test_unreserved_ordinary_work_is_unchanged(self):
        self.insert('ordinary-work','ordinary')
    def test_child_completion_keeps_checkpoint_ownership(self):
        self.reserve();self.db.execute(DISPATCH,('transfer',));self.insert()
        self.db.execute("UPDATE execution_processes SET status='completed' WHERE id='next'")
        self.db.execute(next(q for q in QUERIES if 'terminal monitor:' in q),('checkpoint_required','next'))
        with self.assertRaises(sqlite3.IntegrityError):self.insert('retry','ordinary')
    def test_fast_child_terminal_receipt_cannot_be_overwritten_by_late_launch_reply(self):
        self.reserve();self.db.execute(DISPATCH,('transfer',));self.insert()
        terminal=next(q for q in QUERIES if "terminal monitor:" in q)
        self.db.execute(terminal,('checkpoint_required','next'))
        self.db.execute(OUTCOME,('running','late successful launch reply','transfer'))
        state,reason=self.db.execute("SELECT state,reason FROM provider_handoff_reservations").fetchone()
        self.assertEqual(state,'checkpoint_required');self.assertIn('terminal monitor:',reason)
    def test_schema_has_no_time_based_release_or_paid_route(self):
        sql=MIGRATION.read_text()
        self.assertNotIn('expires_at',sql);self.assertNotIn('DELETE FROM',sql)

    def activation(self):
        q=next(q for q in QUERIES if q.startswith('INSERT INTO provider_failover_activations'))
        self.db.execute(q,('ws','work-1','initial','/synthetic/private-journal','authority-receipt','owner-generation'))
        self.db.commit()
    def test_activated_owner_blocks_normal_starts_before_first_handoff(self):
        self.activation()
        with self.assertRaises(sqlite3.IntegrityError):self.insert('ordinary-start','ordinary')
        self.reserve();self.db.execute(DISPATCH,('transfer',));self.insert()
    def test_activation_cannot_claim_another_running_owner(self):
        self.insert('other-running','ordinary');self.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):self.activation()
    def test_activation_does_not_change_other_workspaces(self):
        self.activation();self.insert('other-running','other-session')
    def test_checkpoint_return_uses_fresh_codex_session_with_atomic_ownership(self):
        self.activation();self.reserve();self.db.execute(DISPATCH,('transfer',));self.insert()
        self.db.execute("UPDATE execution_processes SET status='completed' WHERE id='next'")
        self.db.execute(next(q for q in QUERIES if 'terminal monitor:' in q),('checkpoint_required','next'));self.db.commit()
        rollover=next(q for q in QUERIES if "atomic verified-checkpoint successor" in q)
        with self.db:
            self.assertEqual(self.db.execute(rollover,('transfer','ws','next')).rowcount,1)
            self.db.execute(SESSION,('return-session','ws','CODEX',None))
            self.db.execute(RESERVE,('return','ws','next','return-session','return-exec',ACTION,'new-snapshot','new-fence'))
        self.db.execute(DISPATCH,('return',))
        self.insert('return-exec','return-session')
        self.assertEqual(self.db.execute("SELECT state FROM provider_handoff_reservations WHERE transition_id='transfer'").fetchone()[0],'released')
        with self.assertRaises(sqlite3.IntegrityError):self.insert('parallel','ordinary')
    def test_failed_successor_rolls_back_release_and_keeps_previous_owner(self):
        self.reserve();self.db.execute(DISPATCH,('transfer',));self.insert()
        self.db.execute("UPDATE execution_processes SET status='completed' WHERE id='next'")
        self.db.execute(next(q for q in QUERIES if 'terminal monitor:' in q),('checkpoint_required','next'));self.db.commit()
        rollover=next(q for q in QUERIES if "atomic verified-checkpoint successor" in q)
        with self.assertRaises(sqlite3.IntegrityError):
            with self.db:
                self.assertEqual(self.db.execute(rollover,('transfer','ws','next')).rowcount,1)
                self.db.execute(RESERVE,('return','ws','next','missing-session','return-exec',ACTION,'snapshot','fence'))
        self.assertEqual(self.db.execute("SELECT state FROM provider_handoff_reservations").fetchone()[0],'checkpoint_required')
    def test_running_or_held_owner_cannot_release_for_return(self):
        self.reserve();rollover=next(q for q in QUERIES if "atomic verified-checkpoint successor" in q)
        self.assertEqual(self.db.execute(rollover,('transfer','ws','next')).rowcount,0)
        self.db.execute(OUTCOME,('held','uncertain launch','transfer'))
        self.assertEqual(self.db.execute(rollover,('transfer','ws','next')).rowcount,0)
    def test_recovery_queries_preserve_missing_or_terminal_identity_and_never_launch(self):
        self.reserve();self.db.execute(DISPATCH,('transfer',))
        query=next(q for q in QUERIES if "reconciled exact execution" in q)
        self.db.execute(query,('held','transfer','wrong-exec'))
        self.assertEqual(self.db.execute("SELECT state FROM provider_handoff_reservations").fetchone()[0],'dispatching')
        self.db.execute(query,('held','transfer','next'))
        self.assertEqual(self.db.execute(DISPATCH,('transfer',)).rowcount,0)
        with self.assertRaises(sqlite3.IntegrityError):self.insert('retry','ordinary')
    def test_activation_fences_stopped_execution_reactivation_even_without_reservation(self):
        self.activation()
        with self.assertRaises(sqlite3.IntegrityError):self.db.execute("UPDATE execution_processes SET status='running' WHERE id='initial'")

    def test_explicit_completion_releases_without_deleting_recovery_history(self):
        self.activation();self.reserve();self.db.execute(DISPATCH,('transfer',));self.insert()
        self.db.execute("UPDATE execution_processes SET status='completed' WHERE id='next'")
        self.db.execute(next(q for q in QUERIES if 'terminal monitor:' in q),('checkpoint_required','next'));self.db.commit()
        release=next(q for q in QUERIES if "state='released',reason=?" in q and 'provider_handoff' in q)
        deactivate=next(q for q in QUERIES if "state='released',reason=?" in q and 'provider_failover_activations' in q)
        with self.db:
            self.db.execute(release,('accepted-result','ws','next'))
            self.db.execute(deactivate,('accepted-result','ws','work-1'))
        self.insert('new-independent-task','ordinary')
        self.assertEqual(self.db.execute('SELECT count(*) FROM provider_handoff_reservations').fetchone()[0],1)
    def test_completion_query_detects_unsettled_or_wrong_owner(self):
        self.reserve()
        source=MODEL.read_text()
        check=re.search(r'sqlx::query_as\("(SELECT count\(\*\) FROM provider_handoff_reservations[^"\n]+)"',source).group(1)
        self.assertEqual(self.db.execute(check,('ws','next')).fetchone()[0],1)
        self.db.execute("UPDATE provider_handoff_reservations SET state='checkpoint_required'")
        self.assertEqual(self.db.execute(check,('ws','wrong-exec')).fetchone()[0],1)
        self.assertEqual(self.db.execute(check,('ws','next')).fetchone()[0],0)
if __name__=='__main__':unittest.main(verbosity=2)
