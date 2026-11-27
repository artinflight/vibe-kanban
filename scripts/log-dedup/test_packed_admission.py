import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest

import log_dedup as logs
import packed_objects as packed
from packed_admission import CheckpointCatalog, NormalPreparedRecovery
from packed_plan import compile_group
from nightly_graph import canonical


class Cursor:
    def __init__(self,value):self.value=value
    def fetchall(self):return self.value
    def fetchone(self):return self.value[0]if self.value else None


class RemoteFixture:
    def __init__(self,receipt,bodies):self.receipt=receipt;self.bodies=bodies;self.closed=False
    def request(self,name):assert name=='check'
    def close(self):self.closed=True
    def execute(self,sql,args=()):
        cp=self.receipt
        if sql=='begin':return Cursor([])
        if sql=='select sha256,row from owner_control_manifest':return Cursor([(cp['manifest_sha256'],canonical(cp['manifest']).decode())])
        point=next(r for r in cp['manifest']['files']if r['source']==args[0])
        if sql.startswith('select point '):return Cursor([(canonical(point).decode(),)])
        body=self.bodies[args[0]]
        if sql.startswith('select count'):return Cursor([((len(body)+1024**2-1)//1024**2,)])
        if sql.startswith('select data '):return Cursor([(body[args[1]*1024**2:(args[1]+1)*1024**2],)])
        raise AssertionError(sql)


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)/'prepared';self.folder.mkdir();(self.folder/'.log-packs').mkdir()
        body=b'exact historical bytes';encoded=gzip.compress(body,mtime=0);pack=packed.PACK_MAGIC+encoded;key=logs.sha(pack)
        m=dict(version=2,raw_bytes=len(body),sha256=logs.sha(body),packs=[key],chunks=[dict(sha256=logs.sha(body),bytes=len(body),pack=0,offset=len(packed.PACK_MAGIC),encoded_bytes=len(encoded))])
        self.path=self.folder/'history.jsonl';self.path.write_bytes(packed.encode(m));(self.folder/'.log-packs'/(key+'.pack')).write_bytes(pack)
        files=[];points=[];restored=[];self.bodies={}
        for p in [self.path,self.folder/'.log-packs'/(key+'.pack')]:
            st=p.stat();digest=logs.sha(p.read_bytes());files.append(dict(path=str(p),bytes=st.st_size,sha256=digest,version=logs.version(st)))
            member=dict(kind='file',bytes=st.st_size,sha256=digest,uid=st.st_uid,gid=st.st_gid,mode=st.st_mode&0o777,mtime_ns=st.st_mtime_ns,xattrs={})
            points.append(dict(source=str(p),member=member));restored.append(dict(source=str(p),bytes=st.st_size,sha256=digest,Linux_metadata_verified=True));self.bodies[str(p)]=p.read_bytes()
        manifest=dict(files=points,operation='fixture',plan_sha256='0'*64)
        self.cp=dict(manifest=manifest,manifest_sha256=logs.sha(canonical(manifest)),index_reference=dict(sha256='1'*64))
        actual=dict(independent_owner_controls_restore_verified=True,normal_leased_consumer_entrypoint_verified=True,manifest_sha256=self.cp['manifest_sha256'],files=2,actual_normal_reader_restore=restored)
        self.proof=dict(checkpoint=self.cp,actual_independent_normal_restore=actual)
        self.index=dict(packed_files=files,checkpoints=[dict(name='PACKED_0000',path='fixture',sha256='2'*64,index_reference=self.cp['index_reference'])])
        self.sealed=dict(plan_sha256='3'*64,prepared=str(self.folder),files=[dict(path='aa/session/processes/history.jsonl',original=[1,2,3,4],original_sha256='4'*64,packed_sha256=logs.sha(self.path.read_bytes()),metadata=dict(uid=1000,gid=1000,mode=0o600,mtime_ns=4,atime_ns=5,xattrs={}))],packs={key+'.pack':dict(sha256=key,bytes=len(pack))})
        self.mapping=dict(groups={'3'*64:copy.deepcopy(self.sealed)})
        self.calls=[];self.checks=0
        def connect(name,reference,readonly):
            self.assertEqual(reference,'1'*64);self.assertTrue(readonly);self.calls.append(name);return RemoteFixture(self.cp,self.bodies)
        self.recovery=SimpleNamespace(location='desktop:B:/vk-backups/fixture',check=self.check,handle=SimpleNamespace(db=SimpleNamespace(client=SimpleNamespace(connect=connect))))

    def check(self):self.checks+=1
    def adapter(self):return NormalPreparedRecovery(CheckpointCatalog(self.index,lambda _:self.proof),self.recovery,self.mapping,lambda:None)

    def test_real_B_body_path_and_cached_proof_keep_current_owner_checks(self):
        a=self.adapter();r=a(self.sealed);self.assertEqual(r['members'],2);self.assertFalse(r['local_body_fallback']);self.assertEqual(len(self.calls),1)
        before=self.checks;self.assertEqual(a(self.sealed),r);self.assertGreater(self.checks,before);self.assertEqual(len(self.calls),1)

    def test_corrupt_B_body_refuses_even_when_local_preparation_is_good(self):
        self.bodies[str(self.path)]=b'x'*len(self.bodies[str(self.path)])
        with self.assertRaisesRegex(ValueError,'EOF differs'):self.adapter()(self.sealed)
        self.assertTrue(packed.verify(self.path)['full_EOF_verified'])

    def test_missing_catalog_member_or_duplicate_restore_refuses(self):
        self.index['packed_files'].pop()
        with self.assertRaises(ValueError):self.adapter()

    def test_missing_B_part_refuses_without_local_fallback(self):
        self.bodies[str(self.path)]=b''
        with self.assertRaises(ValueError):self.adapter()(self.sealed)

    def test_changed_metadata_mapping_and_foreign_source_identity_refuse(self):
        for field,value in [('original',[1,99,3,4]),('metadata',dict(uid=1000,gid=1000,mode=0o644,mtime_ns=4,atime_ns=5,xattrs={}))]:
            bad=copy.deepcopy(self.sealed);bad['files'][0][field]=value
            with self.assertRaises(ValueError):self.adapter()(bad)
        self.assertFalse(self.calls)

    def test_prepared_replacement_is_not_adopted(self):
        replacement=self.path.with_suffix('.new');replacement.write_bytes(self.path.read_bytes());replacement.replace(self.path)
        with self.assertRaisesRegex(ValueError,'Prepared input changed'):self.adapter()(self.sealed)

    def test_owner_loss_is_not_hidden_by_cached_proof(self):
        a=self.adapter();a(self.sealed)
        def lost():raise ValueError('owner lost')
        self.recovery.check=lost
        with self.assertRaisesRegex(ValueError,'owner lost'):a(self.sealed)

    def test_mapping_comes_from_the_checkpoint_not_a_local_file(self):
        name=str(self.path);raw=json.dumps(self.mapping).encode();point=self.cp['manifest']['files'][0]
        point['member']['bytes']=len(raw);point['member']['sha256']=logs.sha(raw);self.bodies[name]=raw
        self.cp['manifest_sha256']=logs.sha(canonical(self.cp['manifest']))
        actual=NormalPreparedRecovery.read_mapping(self.recovery,self.cp,name,logs.sha(raw));self.assertEqual(actual,self.mapping)


class PlanTests(unittest.TestCase):
    def test_large_preparation_is_partitioned_without_duplicates_or_larger_transactions(self):
        from packed_plan import split_group
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'group.json'
            rows=[dict(path=str(n),raw_bytes=300*1024**2)for n in range(37)]
            rows += [dict(path=str(n),raw_bytes=1)for n in range(37,160)]
            path.write_text(json.dumps({'source_rows':rows}));ref={'path':str(path),'sha256':logs.sha(path.read_bytes())}
            parts=split_group(ref);sizes={r['path']:r['raw_bytes']for r in rows}
            self.assertEqual([p for part in parts for p in part],[r['path']for r in rows])
            self.assertTrue(all(len(part)<=64 and sum(sizes[p]for p in part)<=2*1024**3 for part in parts))
            rows[0]['raw_bytes']=2*1024**3+1;path.write_text(json.dumps({'source_rows':rows}));ref['sha256']=logs.sha(path.read_bytes())
            with self.assertRaises(ValueError):split_group(ref)

    def test_migration_cannot_use_a_different_serving_root(self):
        from packed_plan import migrate_group
        from online_owner import LiveReaders
        readers=object.__new__(LiveReaders);readers.source=Path('/actual')
        recovery=object.__new__(NormalPreparedRecovery);recovery.mapping={'groups':{}}
        with self.assertRaisesRegex(ValueError,'actual reader root'):
            migrate_group(dict(plan={'source_root':'/foreign'},plan_sha256='0'*64),Path('/unused'),readers,recovery,reserve_bytes=3*1024**3)

    def test_compiler_binds_source_sidecars_metadata_and_both_SQL_owners(self):
        from test_packed_publication import PublicationTests
        t=PublicationTests();t.setUp();self.addCleanup(t.doCleanups);t.loose()
        rows=[]
        for entry in t.plan['files']:
            p=t.root/entry['path'];m=logs.load_manifest(p)
            rows.append(dict(path=entry['path'],version=logs.version(p.stat()),sha256=logs.sha(p.read_bytes()),raw_sha256=m['sha256'],raw_bytes=m['raw_bytes'],sidecars=[dict(path=str(p.with_suffix('.'+ext)),version=identity,sha256=logs.sha(raw))for ext,raw,identity in logs.sidecars(p)],bindings=[dict(owner=o,workspace=t.workspace,session=t.session,status='completed',completed_at='closed')for o in ['main','protected']]))
        p=t.base/'group.json';p.write_text(json.dumps(dict(number=0,destination=str(t.prepared),source_rows=rows)))
        ref=dict(path=str(p),sha256=logs.sha(p.read_bytes()));dbs=dict(main=str(t.db),protected=str(t.db))
        compiled=compile_group(ref,str(t.root),dbs);self.assertEqual(len(compiled['files']),2);self.assertEqual(len(compiled['sidecar_recovery']),2)
        with sqlite3.connect(t.db)as db:db.execute("update execution_processes set status='running'")
        with self.assertRaisesRegex(ValueError,'SQL binding changed'):compile_group(ref,str(t.root),dbs)


if __name__=='__main__':unittest.main()
