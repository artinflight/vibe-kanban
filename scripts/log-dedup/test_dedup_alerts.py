import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

import dedup_alerts

SHARED=Path('/home/mcp/.local/lib/storage-alert-response')
if SHARED.is_dir():
    sys.path.insert(0,str(SHARED))
    import watch_events as events

class EventTests(unittest.TestCase):
    def test_legacy_keys_preserved_and_long_keys_bounded_distinct(self):
        identity='a'*32+'-resume3'
        self.assertEqual(dedup_alerts.event_resource('failure',identity),'failure-'+identity)
        keys=[dedup_alerts.event_resource(k,'a'*32+'-'+a) for k in ['issue','success','failure']
              for a in ['accelerated2','b'*1000]]
        self.assertEqual(len(set(keys)),6)
        self.assertTrue(all(len(k)<=48 for k in keys))

    @unittest.skipUnless(SHARED.is_dir(),'installed WakeWatch codec not available')
    def test_actual_registry_accepts_issue_success_failure_and_nested_pause(self):
        target=dict(enabled=True,workspace_id='081597f1-4a61-4f6a-8f56-95c2d6bc553c',
            session_id='036f0739-6fcc-4e30-911a-e4c6e7e1f388',executor_config_sha256='a'*64,
            max_validation_age_seconds=120,cooldown_seconds=60,vibe_db='/unused',owner_roots=['/unused'])
        config=dict(version=1,activation_approved=True,state_volume={},state_root='/unused',
            sources={'dedup-cutover':dict(enabled=True,max_age_seconds=120,driver='events-v1')},
            targets={'dedup-owner':target},rules={'completion':dict(source='dedup-cutover',target='dedup-owner',resource='*',
            trigger=dict(field='needs_attention',op='eq',value=True),recover=dict(field='needs_attention',op='eq',value=False),
            recovery_samples=3,min_sample_seconds=10,max_gap_seconds=600,instruction='Report exact conversion result')})
        registry=events.Registry(config)
        with tempfile.TemporaryDirectory() as tmp:
            store=events.EventStore(Path(tmp)/'events.sqlite');self.addCleanup(store.db.close)
            now=time.time()
            row=dict(operation='a'*32,attempt='accelerated2',state='stalled',needs_attention=True,checked_at=now)
            for state in ['stalled','failure_recovery_pending','success']:
                now+=1
                row['state']=state
                result=dedup_alerts.observe(store,registry,row,now)
                self.assertGreater(result['fresh_pending_observations'],0)
            now+=1
            row.update(state='paused',needs_attention=False,checkpoint={'next_batch':69})
            result=dedup_alerts.observe(store,registry,row,now)
            self.assertEqual(result['fresh_pending_observations'],3)
            samples=store.fresh(now)
            self.assertEqual(len(samples),3)
            with store.db:
                store.db.execute("INSERT INTO batches(id,status,created) VALUES ('accepted','completed',?)",(now,))
                store.db.execute("UPDATE incidents SET batch='accepted'")
            replay=dedup_alerts.observe(store,registry,row,now+1)
            self.assertEqual(replay['fresh_pending_observations'],0)
            self.assertEqual(store.db.execute('SELECT count(*) FROM incidents').fetchone()[0],3)
            for sample in samples.values():
                self.assertNotIn('checkpoint',sample['event']['values'])
                self.assertEqual(sample['event']['values']['attempt'],'accelerated2')

if __name__=='__main__':unittest.main()
