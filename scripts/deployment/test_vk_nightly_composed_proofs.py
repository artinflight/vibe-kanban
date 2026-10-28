import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import vk_nightly_objects as objects
from vk_nightly_composed_proofs import audit,canonical
from vk_nightly_current_map import encode_member


class ComposedProofTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir='/dev/shm');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.db=sqlite3.connect(':memory:');self.addCleanup(self.db.close)
        self.db.execute('create table members(name text,state text,row blob)')
        self.base=sqlite3.connect(':memory:');self.addCleanup(self.base.close)
        self.base.execute('create table provenance(source_catalog_sha256 text,restore_proof_sha256 text)')
        self.base.execute('insert into provenance values(?,?)',('1'*64,'2'*64))
        self.base.execute('create table bodies(sha256 text,bytes integer,name text)')
        self.catalog=sqlite3.connect(':memory:');self.addCleanup(self.catalog.close)
        self.catalog.execute('create table components(id text,definition text)')
        self.catalog.execute('create table versions(name text,layer text,row text)')
        self.reference=dict(sha256='3'*64,bytes=1,selector='3'*64+'.sqlite')
        self.meta=dict(mode=0o600,uid=os.getuid(),gid=os.getgid(),mtime_ns=123,xattrs={})
    def use(self):
        return audit(self.db,self.reference,base_catalog=self.base,recipe_catalogs=[self.catalog],
            objects=objects,objects_root=self.root,guard=lambda:None)
    def put(self,name,member,**extras):
        self.db.execute('insert into members values(?,?,?)',(name,'verified-file',encode_member(dict(member=member,**extras))))
    def base_file(self,name='home/note',data=b'accepted'):
        sha=hashlib.sha256(data).hexdigest();segment=dict(layer='accepted-base',selector='original',bytes=len(data),sha256=sha)
        self.base.execute('insert into bodies values(?,?,?)',(sha,len(data),'original'))
        row=dict(self.meta,kind='file',bytes=len(data),sha256=sha,segments=[segment]);self.put(name,row);return row
    def test_actual_base_provenance_and_exact_selector_no_body_scan(self):
        row=self.base_file()
        with patch.object(objects,'decoded',side_effect=AssertionError('proven body reread')):
            result=self.use()
        self.assertEqual(result['file_points'],1);self.assertEqual(result['file_raw_bytes'],row['bytes'])
        self.assertEqual(result['accepted_base_references'],1);self.assertFalse(result['current_baseline_accepted'])
        self.base.execute('update bodies set name=?',('another-original',))
        with self.assertRaisesRegex(ValueError,'absent from accepted restore'):self.use()
    def test_unresolved_and_multisegment_without_ordered_proof_refused(self):
        row=self.base_file();row['segments']*=2;row['bytes']*=2
        self.db.execute('update members set row=?',(encode_member(dict(member=row)),))
        with self.assertRaisesRegex(ValueError,'full ordered readback'):self.use()
        proof=dict(independent_ordered_B_readback_sha256=row['sha256'],independent_ordered_B_readback_bytes=row['bytes'],source_metadata=self.meta)
        self.db.execute('update members set row=?',(encode_member(dict(member=row,independent_file_proof=proof)),))
        self.assertEqual(self.use()['ordered_file_readback_proofs_reused'],1)
        proof['source_metadata']=dict(self.meta,mode=0o777)
        self.db.execute('update members set row=?',(encode_member(dict(member=row,independent_file_proof=proof)),))
        with self.assertRaisesRegex(ValueError,'Linux metadata'):self.use()
        self.db.execute("update members set state='file-needs-capture'")
        with self.assertRaisesRegex(ValueError,'unresolved'):self.use()
    def test_retained_archive_identity_and_exact_member_record_both_required(self):
        component=dict(encoding='zip-member',archive=dict(name='old.zip',native_path='B:/vk-backups/fixture/old.zip',
            bytes=100,sha256='4'*64,file_identity=[1,2,100,4]),records=dict(name='old.jsonl',native_path='B:/vk-backups/fixture/old.jsonl',
            bytes=10,sha256='5'*64,file_identity=[1,3,10,4]),raw_bytes=3,members=1)
        identifier=hashlib.sha256(canonical(component)).hexdigest();layer='retained-'+identifier
        segment=dict(layer=layer,selector='old.zip',member='home/old',encoding='zip-member',bytes=3,sha256='6'*64,encoded_bytes=100,encoded_sha256='4'*64)
        row=dict(self.meta,kind='file',bytes=3,sha256='6'*64,segments=[segment]);self.put('home/current',row)
        self.catalog.execute('insert into components values(?,?)',(identifier,canonical(component).decode()))
        self.catalog.execute('insert into versions values(?,?,?)',('home/old',layer,canonical(row).decode()))
        def run(probe):
            return audit(self.db,self.reference,base_catalog=self.base,recipe_catalogs=[self.catalog],objects=objects,
                objects_root=self.root,guard=lambda:None,native_carrier=probe)
        seen=[];self.assertEqual(run(lambda value:seen.append(value))['retained_component_references'],1)
        self.assertEqual(len(seen),2)
        def denied(value):raise PermissionError('actual archived carrier access denied')
        with self.assertRaises(PermissionError):run(denied)
        self.catalog.execute('delete from versions')
        with self.assertRaisesRegex(ValueError,'exact independently verified catalog record'):run(lambda _:None)
    def test_actual_v8i_schema_coexists_with_old_catalog_without_rehashing_carriers(self):
        newer=sqlite3.connect(':memory:');self.addCleanup(newer.close)
        newer.execute('create table components(layer text,archive_path text,archive_identity text,records_sha text,members integer,raw_bytes integer)')
        newer.execute('create table versions(name text,layer text,row text)')
        layer='v8i-file-'+'4'*24
        identity=[1,2,100,4]
        newer.execute('insert into components values(?,?,?,?,?,?)',
            (layer,'B:/vk-backups/fixture/new.zip',json.dumps(identity),'5'*64,1,3))
        segment=dict(layer=layer,selector='new.zip',member='old/name',encoding='zip-member',
            bytes=3,sha256='6'*64,encoded_bytes=100,encoded_sha256='4'*64)
        row=dict(self.meta,kind='file',bytes=3,sha256='6'*64,segments=[segment],
            component_provenance=dict(archive_sha256='4'*64,record_sha256='5'*64,
                current_source_qualified=False,parent_backup_accepted=False))
        newer.execute('insert into versions values(?,?,?)',('old/name',layer,canonical(row).decode()))
        self.put('home/current',row);seen=[]
        def run():
            return audit(self.db,self.reference,base_catalog=self.base,recipe_catalogs=[self.catalog,newer],
                objects=objects,objects_root=self.root,guard=lambda:None,native_carrier=seen.append)
        with patch.object(objects,'decoded',side_effect=AssertionError('unnecessary payload replay')):
            self.assertEqual(run()['retained_component_references'],1)
        self.assertEqual(len(seen),1);self.assertEqual(seen[0]['file_identity'],identity)
        self.assertEqual(seen[0]['sha256'],'4'*64)
        row['component_provenance']['record_sha256']='7'*64
        newer.execute('update versions set row=?',(canonical(row).decode(),))
        with self.assertRaisesRegex(ValueError,'v8i member provenance'):run()
        newer.execute('delete from components')
        with self.assertRaisesRegex(ValueError,'absent or ambiguous'):run()

    def test_named_ZIP_contract_actual_decode_and_fail_closed(self):
        import zipfile
        path=self.root/'component.zip';data=b'verified archived specimen'
        with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:z.writestr('old/name',data)
        sha=hashlib.sha256(data).hexdigest();encoded=path.read_bytes()
        archive=dict(name=path.name,native_path=str(path),bytes=len(encoded),sha256=hashlib.sha256(encoded).hexdigest())
        segment=dict(layer='named-fixture-v1',selector=path.name,member='old/name',encoding='zip-member',
            bytes=len(data),sha256=sha,encoded_bytes=len(encoded),encoded_sha256=archive['sha256'])
        self.put('home/current',dict(self.meta,kind='file',bytes=len(data),sha256=sha,segments=[segment]))
        definition=dict(format='vk-nightly-named-ZIP-component-v1',encoding='zip-member',archive=archive,
            independent_restore_proof_sha256='7'*64,members={'old/name':dict(self.meta,kind='file',bytes=len(data),sha256=sha)})
        def run():
            return audit(self.db,self.reference,base_catalog=self.base,recipe_catalogs=[self.catalog],
                objects=objects,objects_root=self.root,guard=lambda:None,native_carrier=lambda _:None,
                named_components={'named-fixture-v1':definition})
        self.assertEqual(run()['retained_component_references'],1)
        with self.assertRaisesRegex(ValueError,'undeclared'):self.use()
        definition['members']['old/name']['sha256']='8'*64
        with self.assertRaisesRegex(ValueError,'member full hash'):run()
        definition['members']['old/name']['sha256']=sha
        definition['archive']['sha256']='9'*64
        with self.assertRaisesRegex(ValueError,'archive full hash'):run()

    def test_SQL_acceptance_must_decode_identical_record_not_trust_copied_flags(self):
        row=self.base_file();source='/home/note'
        point=dict(source=source,status='consistent_SQL_point_verified',method='SQLite-backup-API',member=row,
            bytes=row['bytes'],sha256=row['sha256'],independent=dict(integrity='ok',bytes=row['bytes'],sha256=row['sha256']))
        data=canonical(point);sha=hashlib.sha256(data).hexdigest()
        seal=dict(layer='nightly-objects-v1',selector=sha+'.zlib',encoding='zlib',bytes=len(data),sha256=sha,encoded_bytes=10,encoded_sha256='7'*64)
        selected=dict(point,B_acceptance_object=seal,new_B_total_encoded_bytes_including_control=10)
        self.db.execute('update members set row=?',(encode_member(dict(member=row,SQL_point=selected)),))
        receipt=dict(encoded_bytes=10,encoded_sha256='7'*64)
        with patch.object(objects,'accepted_object_receipt',return_value=receipt),patch.object(objects,'decoded',return_value=iter([data])):
            result=self.use()
        self.assertEqual(result['SQL_acceptance_records_independently_decoded'],1)
        self.assertEqual(result['SQL_control_bytes_read'],len(data))
        corrupt=dict(point,method='unaccepted-source-copy')
        with patch.object(objects,'accepted_object_receipt',return_value=receipt),patch.object(objects,'decoded',return_value=iter([canonical(corrupt)])):
            with self.assertRaisesRegex(ValueError,'decoded B SQL acceptance record differs'):self.use()
        selected['member']=dict(row,mode=0o777)
        self.db.execute('update members set row=?',(encode_member(dict(member=row,SQL_point=selected)),))
        with self.assertRaisesRegex(ValueError,'restored SQL API point'):self.use()


if __name__=='__main__':unittest.main()
