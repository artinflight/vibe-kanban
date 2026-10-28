import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from vk_nightly_tracking import TrackingStore,FORMAT
from vk_nightly_outbox_export import export,verify_delivery,retained_prefix_report


class OutboxExportTests(unittest.TestCase):
    def test_lost_ack_reuses_durable_commit_and_full_prefix_survives_reopen(self):
        binding=dict(format=FORMAT,instance='one',plan_sha256='a'*64,scope_sha256='b'*64,owner_pid=os.getpid())
        def report(since,sequence,path):return dict(format=FORMAT,instance='one',since=since,sequence=sequence,
            plan_sha256='a'*64,scope_sha256='b'*64,ready=True,errors=[],terminal=None,
            changed=[path],events={path:2},barrier=dict(durable_sequence=sequence,kernel_drain_completed=True))
        with tempfile.TemporaryDirectory(dir='/dev/shm') as root:
            p=Path(root)/'B-fixture.sqlite'
            first=report(0,7,'/old')
            with TrackingStore.held(p) as store:
                empty=report(0,0,'/unused');empty['events']={};empty['changed']=[]
                self.assertEqual(export(binding,empty,store,guard=lambda:None)['sequence'],0)
                one=export(binding,first,store,guard=lambda:None)
            with TrackingStore.held(p) as store:
                self.assertEqual(export(binding,first,store,guard=lambda:None),one)
                self.assertEqual(verify_delivery(store.db,one),first)
                export(binding,report(7,9,'/new'),store,guard=lambda:None)
                self.assertEqual(store.report('one',0)['changed'],['/new','/old'])
                self.assertEqual(store.db.execute('select count(*) from outbox_delivery').fetchone(),(1,))
                with self.assertRaisesRegex(ValueError,'cursor differs'):
                    export(binding,report(1,10,'/gap'),store,guard=lambda:None)
                bad=report(9,10,'/bad');bad['barrier']['kernel_drain_completed']=False
                with self.assertRaisesRegex(ValueError,'barrier required'):export(binding,bad,store,guard=lambda:None)
                self.assertEqual(store.report('one',0)['sequence'],9)
                live=report(9,12,'/live')
                with patch('vk_nightly_tracking.request',return_value=live) as query:
                    merged=retained_prefix_report(store,'fixture-endpoint','one',0,guard=lambda:None)
                    self.assertEqual(merged['changed'],['/live','/new','/old'])
                    self.assertEqual(merged['sequence'],12);self.assertEqual(merged['source_paths_scanned'],0)
                    self.assertEqual(query.call_args.args[2],9)
                # More than one RPC part is preserved and independently read,
                # without using a giant SQL parameter/frame or SSD payload.
                many=report(9,13,'/many');many['changed']=['/'+('x'*90)+str(i) for i in range(900)]
                many['events']={path:2 for path in many['changed']}
                proof=export(binding,many,store,guard=lambda:None)
                self.assertEqual(verify_delivery(store.db,proof),many)
                self.assertGreater(store.db.execute('select count(*) from outbox_report_parts').fetchone()[0],1)
                store.db.execute('delete from outbox_report_parts where part=1')
                with self.assertRaises(ValueError):verify_delivery(store.db,proof)
