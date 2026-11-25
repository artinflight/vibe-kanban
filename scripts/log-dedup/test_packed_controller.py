import fcntl
import json
from pathlib import Path
import sqlite3
import unittest

import log_dedup as logs
import packed_objects as packed
from packed_controller import execute
from packed_recovery import write_new
import reclaim
import test_packed_publication as fixtures


class FixtureAdapter:
    """Only fixture process/recovery qualification; kernel/SQL custody is real."""
    def __init__(self,fixture):
        self.fixture=fixture;self.calls=0;self.fail=False;self.fail_seal=False
    def check(self):pass
    def convert(self,group,journal,progress):
        self.calls+=1
        batch=self.fixture.make(journal=str(journal))
        with batch.fence.held():
            batch.publish(progress)
            if self.fail:raise InterruptedError('published fixture needs review')
            self.verify(group,journal)
            return batch.retire(progress)
    def verify(self,group,journal):
        for row in group['plan']['files']:
            proof=packed.verify(self.fixture.root/row['path'])
            if(proof['sha256'],proof['raw_bytes'])!=(row['sha256'],row['raw_bytes']):raise ValueError('EOF')
        return dict(plan_sha256=group['plan_sha256'],files=len(group['files']),full_EOF_verified=True)
    def seal(self,paths):
        if self.fail_seal:raise ValueError('fixture recovery unavailable')
        assert any(p.name=='RETIRED.json'for p in paths)
        return dict(independent_recovery_verified=True,fixture_only=True)


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.t=fixtures.PublicationTests();self.t.setUp();self.addCleanup(self.t.doCleanups);self.t.loose()
        key=logs.sha(reclaim.canonical(self.t.plan));self.mapping=dict(source_root=str(self.t.root),groups={key:dict(plan_sha256=key,plan=self.t.plan,files=self.t.plan['files'])})
        self.map_path=self.t.base/'mapping.json';self.pin()
        self.lock=self.t.base/'existing.lock';self.lock.write_bytes(b'owner record');self.lock.chmod(0o600)
        self.folder=self.t.base/'finite';self.adapter=FixtureAdapter(self.t)
    def pin(self):
        self.map_path.write_text(json.dumps(self.mapping));self.reference=dict(path=str(self.map_path),sha256=reclaim.file_hash(self.map_path))
    def run_it(self,**kwargs):
        return execute(self.reference,self.folder,self.lock,self.adapter,maximum_seconds=60,**kwargs)
    def test_real_two_file_transaction_preserves_history_and_seals_journals(self):
        result=self.run_it();self.assertTrue(result['complete']);self.assertEqual(result['source_files'],2)
        self.t.exact();self.assertTrue((self.folder/'batch-0000/RETIRED.json').exists())
        self.assertEqual(self.lock.read_bytes(),b'owner record')
        with self.assertRaises(FileExistsError):self.run_it()
        self.assertEqual(self.adapter.calls,1)
    def test_interrupted_publication_is_not_replayed_or_reported_complete(self):
        self.adapter.fail=True
        with self.assertRaises(InterruptedError):self.run_it()
        self.assertTrue((self.folder/'FAILURE.json').exists());self.assertFalse((self.folder/'RESULT.json').exists())
        self.assertTrue(list((self.t.root/self.t.names[0]).parent.glob('.log-retained-*/*.old')))
        with self.assertRaises(FileExistsError):self.run_it()
        self.assertEqual(self.adapter.calls,1)
    def test_busy_existing_owner_prevents_run_creation(self):
        with self.lock.open('rb')as owner:
            fcntl.flock(owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):self.run_it()
        self.assertFalse(self.folder.exists());self.assertEqual(self.adapter.calls,0)
    def test_duplicate_selection_refuses_before_mutation(self):
        group=next(iter(self.mapping['groups'].values()));group['plan']['files'].append(group['plan']['files'][0]);self.pin()
        with self.assertRaises(ValueError):self.run_it()
        self.assertFalse(self.folder.exists())
    def test_recovery_failure_after_retirement_remains_an_explicit_hold(self):
        self.adapter.fail_seal=True
        with self.assertRaises(ValueError):self.run_it()
        self.assertFalse((self.folder/'RESULT.json').exists());self.t.exact()
        with self.assertRaises(FileExistsError):self.run_it()
    def test_current_sql_running_state_refuses_before_publication(self):
        with sqlite3.connect(self.t.db)as db:db.execute("update execution_processes set status='running'")
        with self.assertRaises(ValueError):self.run_it()
        self.assertFalse((self.folder/'batch-0000/PUBLISHED.json').exists())
        self.assertTrue((self.t.root/self.t.names[0]).read_bytes().startswith(logs.MAGIC))
    def test_deadline_refuses_next_mutation_and_keeps_failure_evidence(self):
        times=iter([0,61])
        with self.assertRaises(TimeoutError):self.run_it(clock=lambda:next(times))
        self.assertEqual(self.adapter.calls,0);self.assertTrue((self.folder/'FAILURE.json').exists())


if __name__=='__main__':unittest.main()
