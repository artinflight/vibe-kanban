import copy
from datetime import datetime,timedelta,timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_vk_nightly_recovery_descriptor import fixture,reference
from vk_nightly_current_map import decode_member,encode_member
from vk_nightly_recovery_descriptor import build
from vk_nightly_composed_consumer import run,validation_arguments
from vk_typed_recovery import checksum


class ConsumerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir='/dev/shm');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);db,path,c,rows,body,controls=fixture(self.root,SQL=True);self.addCleanup(db.close)
        with sqlite3.connect(body/'state.sqlite') as image:
            schema=image.execute('select type,name,tbl_name,sql from sqlite_master order by type,name,tbl_name,sql').fetchall()
        image.close();name='home/state/state.sqlite'
        point=decode_member(db.execute('select row from members where name=?',(name,)).fetchone()[0])
        point['SQL_point']['independent']['schema_sha256']=hashlib.sha256(json.dumps(schema,separators=(',',':')).encode()).hexdigest()
        db.execute('update members set row=? where name=?',(encode_member(point),name))
        d=build(db,reference(path),c,checkpoint=lambda:None)
        files=[row for row in rows.values() if row['kind']=='file']
        # Native audit authentication is covered by actual BControlTests.
        # This is its explicit fixture boundary, not a production audit claim.
        proof=dict(format='vk-nightly-independent-composed-content-proof-v1',map_reference=d['indexes'][0],
            file_points=len(files),file_raw_bytes=sum(r['bytes'] for r in files),
            SQL_acceptance_records_independently_decoded=1,base_catalog_reference={'sha256':'1'*64},
            recipe_catalog_references=[],file_proof_chain_sha256='2'*64,segment_proof_chain_sha256='3'*64)
        roots={'accepted-base':str(body),'nightly-controls-v1':str(controls)}
        self.packet=dict(format='vk-nightly-composed-consumer-packet-v1',descriptor=d,descriptor_sha256=checksum(d),
            consumer_contract=c,consumer_contract_sha256=checksum(c),content_proof=proof,content_proof_sha256=checksum(proof),
            expected_catalogs=dict(base=proof['base_catalog_reference'],recipes=[]),
            provider_placement=dict(roots=roots,expected_uid=os.getuid(),expected_gid=os.getgid(),
                root_bindings={k:[Path(p).stat().st_dev,Path(p).stat().st_ino] for k,p in roots.items()},
                lease_paths={k:str(Path(p)/'RECOVERY_READ.lease') for k,p in roots.items()}),
            scratch_parent=str(self.root),maximum_scratch_bytes=17*1024**2,maximum_readback_bytes=1024**2,
            remaining_seconds=30,readback_sources=['/home/state/note','/home/state/state.sqlite'],
            whole_cycle_deadline_UTC=(datetime.now(timezone.utc)+timedelta(seconds=30)).isoformat(),
            Linux_resource_admission=dict(memory_floor_bytes=0,swap_floor_bytes=0))
        self.body=body;self.controls=controls

    def test_bound_readback_scope_includes_current_SQL_alias_and_all_pins(self):
        from vk_nightly_finalize_current import consumer_packet
        c={k:v for k,v in self.packet.items() if k in ('descriptor','descriptor_sha256','consumer_contract',
            'consumer_contract_sha256','content_proof','content_proof_sha256','expected_catalogs')}
        c['format']='vk-nightly-finalized-current-candidate-v1'
        args={k:self.packet[k] for k in ('provider_placement','scratch_parent','maximum_scratch_bytes',
            'maximum_readback_bytes','remaining_seconds','whole_cycle_deadline_UTC','Linux_resource_admission')}
        packet=consumer_packet(c,readback_sources=[],readback_scope_authority='effective-contract-mandatory-v1',**args)
        self.assertEqual(packet['readback_sources'],['/home/state/note','/home/state/state.sqlite'])
        self.assertTrue(run(packet,checksum(packet),guard=lambda:None)['independent_composed_restore_verified'])
        with self.assertRaisesRegex(ValueError,'unsupported composed readback'):
            consumer_packet(c,readback_sources=[],readback_scope_authority='ignore-required-SQL',**args)

    def test_real_entrypoint_returns_independent_SQL_metadata_and_timing(self):
        result=run(self.packet,checksum(self.packet),guard=lambda:None)
        self.assertTrue(result['independent_composed_restore_verified'])
        self.assertTrue(result['normal_leased_consumer_entrypoint_verified']);self.assertGreater(result['elapsed_seconds'],0)
        self.assertEqual(result['actual_normal_reader_restore'][1]['SQLite_integrity'],'ok')
        self.assertFalse(result['original_epoch_complete']);self.assertFalse(result['schedule_enabled'])
        self.assertEqual(list(self.root.glob('nightly-composed-consumer-*')),[])

    def test_actual_CLI_stdin_packet_without_OS_SSD_payload_or_backup_job(self):
        command=[sys.executable,'-B',str(Path(__file__).with_name('vk_nightly_composed_consumer.py')),
            '--packet-sha256',checksum(self.packet)]
        result=subprocess.run(command,input=json.dumps(self.packet)+'\n',text=True,capture_output=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
        records=[json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(records[-1]['event'],'composed-consumer-result')
        self.assertTrue(records[-1]['result']['independent_composed_restore_verified'])
        self.assertEqual(list(self.root.glob('nightly-composed-consumer-*')),[])

    def test_actual_memory_bootstrap_and_normal_streamed_consumer_without_install_or_payload_staging(self):
        from vk_nightly_remote_consumer import run as streamed,LOADER
        with patch('vk_nightly_remote_consumer.command',return_value=[sys.executable,'-B','-u','-c',LOADER]):
            value=streamed({},self.packet,guard=lambda:None)
        self.assertTrue(value['independent_composed_restore_verified'])
        self.assertEqual(value['consumer_packet_sha256'],checksum(self.packet))
        self.assertEqual(list(self.root.glob('nightly-composed-consumer-*')),[])

    def test_fixed_B_placement_bridge_refuses_other_distro_volume_before_consumer(self):
        import base64,re
        from types import SimpleNamespace
        from vk_nightly_remote_consumer import command
        value=command({})[-1]
        bridge=base64.b64decode(re.search("b64decode\\('([A-Za-z0-9+/=]+)'\\)",value)[1]).decode()
        compile(bridge,'existing-B-consumer-bridge','exec')
        good=dict(DistributionName='VK-Candidate-20261009',BasePath=r'\\?\B:\vk-backups\vk-safe-release-20261009\linux-candidate\distribution')
        for actual in (good,dict(good,BasePath=r'C:\wrong-placement')):
            with patch('subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps(actual))), \
                 patch('subprocess.call',return_value=0) as launch:
                if actual==good:
                    with self.assertRaises(SystemExit) as terminal:exec(bridge,{})
                    self.assertEqual(terminal.exception.code,0)
                    argv=launch.call_args.args[0];self.assertIn('setpriv',argv);self.assertIn('1000',argv)
                else:
                    with self.assertRaisesRegex(ValueError,'exact accepted B placement'):exec(bridge,{})
                    launch.assert_not_called()

    def test_wrong_packet_placement_contract_and_actual_STOP_refuse_before_scratch(self):
        with self.assertRaisesRegex(ValueError,'packet differs'):run(self.packet,'0'*64,guard=lambda:None)
        wrong=copy.deepcopy(self.packet);wrong['provider_placement']['root_bindings']['accepted-base'][1]+=1
        with self.assertRaisesRegex(ValueError,'placement changed'):run(wrong,checksum(wrong),guard=lambda:None)
        wrong=copy.deepcopy(self.packet);wrong['consumer_contract']['required_SQL']=[]
        wrong['consumer_contract_sha256']=checksum(wrong['consumer_contract'])
        with self.assertRaisesRegex(ValueError,'consumer contract differs'):run(wrong,checksum(wrong),guard=lambda:None)
        def stop():raise PermissionError('actual owner STOP')
        with self.assertRaisesRegex(PermissionError,'owner STOP'):run(self.packet,checksum(self.packet),guard=stop)
        self.assertEqual(list(self.root.glob('nightly-composed-consumer-*')),[])

    def test_root_and_wrong_UID_or_GID_are_rejected_without_creating_scratch(self):
        with patch('vk_nightly_composed_consumer.os.getuid',return_value=0):
            with self.assertRaisesRegex(ValueError,'root execution prohibited'):run(self.packet,checksum(self.packet),guard=lambda:None)
        for field in ('expected_uid','expected_gid'):
            wrong=copy.deepcopy(self.packet);wrong['provider_placement'][field]+=1
            with self.assertRaisesRegex(ValueError,'placement/owner differs'):run(wrong,checksum(wrong),guard=lambda:None)
        self.assertEqual(list(self.root.glob('nightly-composed-consumer-*')),[])

    def test_missing_lease_or_corrupt_SQL_preserves_provider_and_failed_output(self):
        # Only synthetic fixture files under this test's owned /dev/shm root.
        lease=self.body/'RECOVERY_READ.lease';lease.unlink()
        with self.assertRaises(FileNotFoundError) as failure:run(self.packet,checksum(self.packet),guard=lambda:None)
        self.assertTrue(Path(failure.exception.nightly_composed_consumer_preserved_scratch).is_dir())
        lease.touch();source=self.body/'state.sqlite';raw=source.read_bytes();source.write_bytes(b'X'+raw[1:])
        with self.assertRaises(ValueError) as failure:run(self.packet,checksum(self.packet),guard=lambda:None)
        kept=Path(failure.exception.nightly_composed_restore_preserved_path)
        self.assertTrue(kept.exists());self.assertEqual(source.read_bytes(),b'X'+raw[1:])

    def test_shared_deadline_and_RAM_denial_do_not_copy_or_recapture_originals(self):
        values=iter([0,31])
        with self.assertRaisesRegex(TimeoutError,'whole-cycle'):run(self.packet,checksum(self.packet),guard=lambda:None,clock=lambda:next(values))
        wrong=copy.deepcopy(self.packet);wrong['maximum_scratch_bytes']=10**15
        with self.assertRaisesRegex(ValueError,'RAM scratch'):run(wrong,checksum(wrong),guard=lambda:None)
        self.assertEqual(list(self.root.glob('nightly-composed-consumer-*')),[])

    def test_actual_selected_restore_peak_is_admitted_before_materialization(self):
        wrong=copy.deepcopy(self.packet);wrong['Linux_resource_admission']['memory_floor_bytes']=10**18
        before=(self.body/'state.sqlite').stat().st_ino
        with self.assertRaisesRegex(BlockingIOError,'selected restore peak plus installed memory floor') as stopped:
            run(wrong,checksum(wrong),guard=lambda:None)
        scratch=Path(stopped.exception.nightly_composed_consumer_preserved_scratch)
        self.assertEqual(list(scratch.iterdir()),[])
        self.assertEqual((self.body/'state.sqlite').stat().st_ino,before)

    def test_replaying_an_old_packet_cannot_reset_the_whole_cycle_deadline(self):
        wrong=copy.deepcopy(self.packet);wrong['whole_cycle_deadline_UTC']='2020-01-01T00:00:00+00:00'
        with self.assertRaisesRegex(TimeoutError,'already expired'):run(wrong,checksum(wrong),guard=lambda:None)
        self.assertEqual(list(self.root.glob('nightly-composed-consumer-*')),[])

    def test_SQL_qualification_comes_from_external_request_not_descriptor(self):
        c=copy.deepcopy(self.packet['consumer_contract']);d=copy.deepcopy(self.packet['descriptor'])
        request=dict(sources=['/home/state/state.sqlite'],SQL_scope_sources=c['required_SQL'],
            always_SQL_API_sources=c['required_SQL'],binding=dict(source_instance='fixture-current'))
        request['cohort_id']=checksum(request);c['current_SQL_request']=request;d['installed_consumer_contract_sha256']=checksum(c)
        args=validation_arguments(c,d)
        self.assertEqual(args['required_SQL_qualification']['cohort_id'],request['cohort_id'])
        c['current_SQL_request']['sources']=[];d['installed_consumer_contract_sha256']=checksum(c)
        with self.assertRaisesRegex(ValueError,'SQL cohort request differs'):validation_arguments(c,d)


if __name__=='__main__':unittest.main()
