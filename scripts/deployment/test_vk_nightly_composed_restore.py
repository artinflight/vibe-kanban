import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from test_vk_nightly_recovery_descriptor import fixture,reference
from vk_nightly_current_map import decode_member,encode_member
from vk_nightly_recovery_descriptor import build
from vk_nightly_composed_restore import verify
from vk_typed_recovery import HeldRecoverySet,LocalDependencies,held_index,checksum


class ComposedRestoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir='/dev/shm');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.scratch=self.root/'scratch';self.scratch.mkdir(mode=0o700)

    def setup(self,SQL=False,wrong_schema=False):
        db,path,c,rows,body,controls=fixture(self.root,SQL=SQL);self.addCleanup(db.close)
        if SQL:
            with sqlite3.connect(body/'state.sqlite') as image:
                schema=image.execute('select type,name,tbl_name,sql from sqlite_master order by type,name,tbl_name,sql').fetchall()
            image.close();sha=hashlib.sha256(json.dumps(schema,separators=(',',':')).encode()).hexdigest()
            name='home/state/state.sqlite';point=decode_member(db.execute('select row from members where name=?',(name,)).fetchone()[0])
            point['SQL_point']['independent']['schema_sha256']='a'*64 if wrong_schema else sha
            db.execute('update members set row=? where name=?',(encode_member(point),name))
        d=build(db,reference(path),c,checkpoint=lambda:None)
        args=dict(plan_sha256=c['plan_sha256'],scope_sha256=c['scope_sha256'],required_sources=c['sources'],
            original_sources=c['original_sources'],required_pins=c['required_pins'],required_SQL=c['required_SQL'])
        provider=LocalDependencies({'accepted-base':body,'nightly-controls-v1':controls},c['dependencies'],admission_check=lambda:None)
        # This unit fixture supplies an explicitly authenticated audit boundary.
        # The actual native API/capture/audit protocol is exercised separately
        # by BControlTests with genuine independently restored SQL records.
        files=[row for row in rows.values() if row['kind']=='file']
        proof=dict(format='vk-nightly-independent-composed-content-proof-v1',map_reference=d['indexes'][0],
            file_points=len(files),file_raw_bytes=sum(row['bytes'] for row in files),
            SQL_acceptance_records_independently_decoded=len(c['required_SQL']),
            base_catalog_reference={'sha256':'1'*64},recipe_catalog_references=[],
            file_proof_chain_sha256='2'*64,segment_proof_chain_sha256='3'*64)
        settings=dict(validation_arguments=args,content_proof=proof,expected_content_proof_sha256=checksum(proof),
            expected_catalogs=dict(base=proof['base_catalog_reference'],recipes=[]),
            readback_sources=['/home/state/note']+c['required_SQL'],scratch_parent=self.scratch,
            maximum_scratch_bytes=17*1024**2,maximum_readback_bytes=1024**2,guard=lambda:None)
        return d,provider,args,settings,body

    def test_actual_normal_reader_restore_hash_Linux_metadata_and_SQL_integrity(self):
        d,provider,args,settings,body=self.setup(SQL=True);progress=[]
        with provider.held(),held_index(provider,*d['indexes']) as index:
            result=verify(HeldRecoverySet(d,checksum(d),provider,index),**settings,report=progress.append)
        self.assertTrue(result['independent_composed_restore_verified']);self.assertFalse(result['original_epoch_complete'])
        self.assertFalse(result['writer_fence_verified']);self.assertFalse(result['schedule_enabled'])
        self.assertEqual(result['complete_file_points_verified'],2)
        self.assertEqual(result['actual_selected_restore_bytes'],len((body/'note').read_bytes())+(body/'state.sqlite').stat().st_size)
        self.assertEqual(result['actual_normal_reader_restore'][1]['SQLite_integrity'],'ok')
        self.assertTrue(all(r['Linux_metadata_verified'] for r in result['actual_normal_reader_restore']))
        self.assertEqual(list(self.scratch.iterdir()),[]);self.assertEqual(len(progress),2)

    def test_scope_proof_or_required_readback_cannot_be_dropped(self):
        d,provider,args,settings,_=self.setup(SQL=True)
        with provider.held(),held_index(provider,*d['indexes']) as index:
            handle=HeldRecoverySet(d,checksum(d),provider,index)
            with self.assertRaisesRegex(ValueError,'cannot be omitted'):
                verify(handle,**dict(settings,readback_sources=['/home/state/note']))
            bad=copy.deepcopy(settings['content_proof']);bad['file_points']=1
            with self.assertRaisesRegex(ValueError,'proof/map/SQL/catalog closure'):
                verify(handle,**dict(settings,content_proof=bad,expected_content_proof_sha256=checksum(bad)))
            with self.assertRaisesRegex(ValueError,'authenticated native content proof'):
                verify(handle,**dict(settings,expected_content_proof_sha256='f'*64))
        self.assertEqual(list(self.scratch.iterdir()),[])

    def test_measured_scratch_bound_fails_before_any_payload_write(self):
        d,provider,args,settings,_=self.setup()
        with provider.held(),held_index(provider,*d['indexes']) as index:
            with self.assertRaisesRegex(ValueError,'demand exceeds'):
                verify(HeldRecoverySet(d,checksum(d),provider,index),**dict(settings,maximum_scratch_bytes=16*1024**2))
        self.assertEqual(list(self.scratch.iterdir()),[])

    def test_SQL_schema_failure_preserves_exact_independent_RAM_recovery_point(self):
        d,provider,args,settings,body=self.setup(SQL=True,wrong_schema=True)
        with provider.held(),held_index(provider,*d['indexes']) as index:
            with self.assertRaisesRegex(ValueError,'schema differs') as failure:
                verify(HeldRecoverySet(d,checksum(d),provider,index),**settings)
        kept=Path(failure.exception.nightly_composed_restore_preserved_path)
        self.assertEqual(kept.read_bytes(),(body/'state.sqlite').read_bytes())
        self.assertEqual(list(self.scratch.iterdir()),[kept])


if __name__=='__main__':unittest.main()
