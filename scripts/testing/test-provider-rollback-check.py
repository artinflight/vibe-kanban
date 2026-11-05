#!/usr/bin/env python3
"""Production rollback planning guard + actual SQL DDL; no backend or real rows."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import sqlite3
import subprocess
import unittest
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('rollback',ROOT/'scripts/deployment/provider_rollback_check.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
MIGRATION=ROOT/'crates/db/migrations/20261021140000_provider_handoff_reservations.sql'
BASE={1:'a'*96};NEW={**BASE,m.VERSION:hashlib.sha384(MIGRATION.read_bytes()).hexdigest()}
def snapshot():
    return {'applied':[{'version':1,'success':1,'checksum':'a'*96}], 'tables':[],
            'owners':{t:None for t in m.TABLES}}
def codes(r):return {b['code'] for b in r['blockers']}
class Rollback(unittest.TestCase):
    def test_actual_old_catalog_must_not_start_after_planned_provider_migration(self):
        r=m.assess(snapshot(),NEW,BASE)
        self.assertIn('fallback_catalog_missing_planned_versions',codes(r))
        self.assertFalse(r['destructiveDownMigrationAllowed'])
        self.assertFalse(r['reservationReleaseAllowed'])
    def test_matching_metadata_never_claims_fallback_binary_or_latest_data_acceptance(self):
        r=m.assess(snapshot(),NEW,NEW)
        self.assertEqual(r['status'],'rehearsal_required')
        self.assertFalse(r['runtimeCompatibilityVerified']);self.assertTrue(r['latestDataRehearsalRequired'])
    def test_dirty_or_changed_existing_checksum_cannot_be_overwritten(self):
        s=snapshot();s['applied'][0]['success']=0
        self.assertIn('dirty_migration',codes(m.assess(s,NEW,NEW)))
        s['applied'][0]['checksum']='b'*96
        self.assertIn('fallback_migration_checksum_mismatch',codes(m.assess(s,NEW,NEW)))
        self.assertIn('candidate_migration_checksum_mismatch',codes(m.assess(s,NEW,NEW)))
    def test_existing_applied_unknown_version_and_planned_checksum_disagreement_hold(self):
        s=snapshot();s['applied'].append({'version':2,'success':1,'checksum':'c'*96})
        self.assertIn('fallback_catalog_missing_applied_version',codes(m.assess(s,NEW,NEW)))
        other=dict(NEW);other[m.VERSION]='d'*96
        self.assertIn('fallback_planned_checksum_mismatch',codes(m.assess(snapshot(),NEW,other)))
    def test_every_unreleased_owner_state_requires_actual_recovery_acceptance(self):
        for state in ['reserved','dispatching','running','held','checkpoint_required','active']:
            s=snapshot();s['tables']=list(m.TABLES);s['owners'][m.TABLES[0]]={state:1}
            self.assertIn('latest_data_owner_recovery_unverified',codes(m.assess(s,NEW,NEW)))
        s['owners'][m.TABLES[0]]={'released':2}
        self.assertNotIn('latest_data_owner_recovery_unverified',codes(m.assess(s,NEW,NEW)))
    def test_partial_schema_and_absent_evidence_are_not_empty_grants(self):
        s=snapshot();s['tables']=[m.TABLES[0]]
        self.assertIn('provider_schema_incomplete',codes(m.assess(s,NEW,NEW)))
        self.assertIsNone(snapshot()['owners'][m.TABLES[0]])
    def test_mutable_or_missing_fallback_pins_refuse_before_binary_or_database_access(self):
        for ref,sha in [('HEAD','a'*64),('a'*40,'not-a-hash')]:
            with self.assertRaisesRegex(ValueError,'immutable fallback'):
                m.inspect(Path('/never-open-db'),ROOT,Path('/never-run-binary'),sha,ref)
    def test_real_additive_migration_preserves_native_data_and_retains_reservation_fences(self):
        c=sqlite3.connect(':memory:');self.addCleanup(c.close)
        c.executescript("PRAGMA foreign_keys=ON; CREATE TABLE workspaces(id BLOB PRIMARY KEY); CREATE TABLE sessions(id BLOB PRIMARY KEY,workspace_id BLOB,executor TEXT); CREATE TABLE execution_processes(id BLOB PRIMARY KEY,session_id BLOB,status TEXT,run_reason TEXT,executor_action TEXT); INSERT INTO workspaces VALUES('ws'); INSERT INTO sessions VALUES('s','ws','CODEX'); INSERT INTO execution_processes VALUES('e','s','failed','codingagent','{}');")
        before={t:c.execute('SELECT * FROM '+t).fetchall() for t in ['workspaces','sessions','execution_processes']}
        c.executescript(MIGRATION.read_text())
        self.assertEqual(before,{t:c.execute('SELECT * FROM '+t).fetchall() for t in before})
        c.execute("INSERT INTO sessions VALUES('next','ws','CLAUDE_CODE')")
        c.execute("INSERT INTO provider_handoff_reservations(transition_id,workspace_id,previous_execution_id,next_session_id,next_execution_id,expected_action,snapshot_receipt,ownership_fence,state) VALUES('t','ws','e','next','new','{}','snapshot','fence','held')")
        with self.assertRaises(sqlite3.IntegrityError):c.execute("INSERT INTO execution_processes VALUES('duplicate','s','running','codingagent','{}')")
        c.execute('CREATE TABLE _sqlx_migrations(version BIGINT,success BOOLEAN,checksum BLOB)')
        c.execute('INSERT INTO _sqlx_migrations VALUES(1,1,?)',(bytes.fromhex('a'*96),))
        c.commit();c.execute('PRAGMA query_only=ON')
        observed=m.metadata(c)
        self.assertEqual(observed['owners'][m.TABLES[0]],{'held':1})
        self.assertIn('latest_data_owner_recovery_unverified',codes(m.assess(observed,NEW,NEW)))
        with self.assertRaises(sqlite3.OperationalError):c.execute("DELETE FROM provider_handoff_reservations")
        self.assertEqual(c.execute('SELECT state FROM provider_handoff_reservations').fetchone()[0],'held')
    def test_real_90_migration_fallback_schema_accepts_additive_sql_without_rewriting_old_ledger(self):
        # Exact source provenance of retained d4d73b39 binary, not another backend.
        ref='e7d0991298d19576b46b614e78ec4ddcfa91b3b6'
        entries=subprocess.check_output(['git','ls-tree','-r','--name-only',ref,'--','crates/db/migrations'],cwd=ROOT,text=True).splitlines()
        c=sqlite3.connect(':memory:');self.addCleanup(c.close)
        c.execute('CREATE TABLE _sqlx_migrations(version BIGINT PRIMARY KEY,success BOOLEAN,checksum BLOB)')
        for name in entries:
            if not name.endswith('.sql') or name.endswith('.down.sql'):continue
            sql=subprocess.check_output(['git','show',ref+':'+name],cwd=ROOT)
            c.executescript('BEGIN;\n'+sql.decode())
            c.execute('INSERT INTO _sqlx_migrations VALUES(?,1,?)',(int(Path(name).name.split('_')[0]),hashlib.sha384(sql).digest()))
            c.commit()
        before=c.execute('SELECT * FROM _sqlx_migrations ORDER BY version').fetchall()
        self.assertEqual(len(before),90)
        shared=c.execute("SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        c.executescript(MIGRATION.read_text())
        self.assertEqual(before,c.execute('SELECT * FROM _sqlx_migrations ORDER BY version').fetchall())
        after=dict(c.execute("SELECT name,sql FROM sqlite_master WHERE type='table'"))
        for name,sql in shared:self.assertEqual(after[name],sql)
        self.assertEqual(c.execute('PRAGMA foreign_key_check').fetchall(),[])
        self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        self.assertTrue(set(m.TABLES).issubset(after))
        # This only proves additive SQLite DDL on a synthetic empty baseline.
        # SQLx registration + real fallback/latest-data startup are still required.
if __name__=='__main__':unittest.main(verbosity=2)
