"""Whole worker -> native B protocol -> audit -> ordinary consumer, RAM only.

The Windows transport and source stream are fixture boundaries; implementations
of worker, SQLite control RPC, object receiver, final audit and consumer are real.
No production B, converter process, source, leases or scheduler is touched.
"""
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from vk_nightly_current_map import encode_member,decode_member
from vk_nightly_objects import ObjectClient
from vk_typed_recovery import checksum
from vk_nightly_composed_consumer import run as consume
from vk_nightly_converted_history import prepare,checkpoint_imports
import vk_nightly_typed_worker as worker


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        from test_vk_nightly_b_controls import BControlTests
        self.b=BControlTests();self.b.setUp();self.addCleanup(self.b.doCleanups)
        self.root=self.b.root;self.children=[];self.addCleanup(self.close)
        self.source_dir=Path(__file__).parent;self.receivers=[]
    def close(self):
        for p in self.children:
            if not p.stdin.closed:p.stdin.close()
            if p.poll() is None:p.wait(timeout=10)
            p.stdout.close();p.stderr.close()
    @contextmanager
    def controls(self,*a,**kw):yield SimpleNamespace(client=self.b.client)
    @contextmanager
    def receiver(self,*a,**kw):
        code="import sys;sys.path.insert(0,"+repr(str(self.source_dir))+");from vk_nightly_objects import receive;receive("+repr(str(self.b.objects))+",sys.stdin.buffer,sys.stdout.buffer,guard=lambda n:None,maximum_object_bytes=262144)"
        p=subprocess.Popen([sys.executable,'-B','-u','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE);self.children.append(p)
        client=ObjectClient(p.stdout,p.stdin,guard=lambda:None,ram_root=self.root,maximum_object_bytes=262144);self.receivers.append(client)
        try:yield SimpleNamespace(client=client,ready={'fixture':True})
        finally:
            p.stdin.close();p.wait(timeout=10)
    def execute(self,config,**kw):
        with patch.object(worker,'DesktopControls',self.controls),patch.object(worker,'DesktopObjects',self.receiver),patch.object(worker,'host_guard',lambda *_:None):
            return worker.run_B(config,**kw)
    def fixture_map(self,SQL=False):
        from test_vk_nightly_recovery_descriptor import fixture
        folder=self.root/'map-fixture';folder.mkdir()
        db,path,contract,rows,body,controls=fixture(folder,SQL=SQL)
        self.addCleanup(db.close)
        db.execute('alter table metadata add column binding text')
        db.execute('update metadata set binding=?',(json.dumps({'fixture':'prepared'},sort_keys=True,separators=(',',':')),))
        # Native B archive placement and ordinary base provider are distinct.
        return db,path,contract,body
    def base_catalog(self,body):
        if hasattr(self,'base_sha'):return self.base_sha
        path=self.root/'base-catalog.sqlite';db=sqlite3.connect(path)
        db.execute('create table provenance(source_catalog_sha256 text,restore_proof_sha256 text)');db.execute('insert into provenance values(?,?)',('a'*64,'b'*64))
        db.execute('create table bodies(sha256 text,bytes integer,name text)')
        for source in (body/'note',body/'state.sqlite'):
            if source.exists():
                raw=source.read_bytes();db.execute('insert into bodies values(?,?,?)',(hashlib.sha256(raw).hexdigest(),len(raw),source.name))
        db.commit();db.close();self.base_sha=self.b.import_other(path);return self.base_sha
    def config(self,seed,refs=()):
        return dict(B_controls={},desktop={},B_index_name='prepared-main',B_checkpoint_sha256=seed,map_binding={'fixture':'prepared'},status=str(self.root/'status.json'),
            maximum_members=8192,maximum_source_bytes=256*1024**2,chunk_bytes=262144,converted_checkpoints=list(refs),file_chunking='content-defined-v1')
    def final(self,seed,contract,body,*,readbacks,dedup_roots):
        self.final_count=getattr(self,'final_count',0)+1
        current=self.b.client.connect('prepared-main',seed);seal=self.b.client.seal_checkpoint(current.key,{'fixture':'final','generation':self.final_count});current.close()
        base_sha=self.base_catalog(body);current=self.b.client.connect('final',seal['sha256'],readonly=True)
        base=self.b.client.connect('base-catalog',base_sha,readonly=True)
        try:
            ref=dict(format='vk-nightly-current-member-map-v1',layer='nightly-controls-v1',selector=seal['sha256']+'.sqlite',sha256=seal['sha256'],bytes=seal['bytes'])
            contract['dependencies']['nightly-controls-v1']={'native_root':str(self.b.controls)}
            contract['dependencies']['nightly-objects-v1']={'fixture':'accepted CAS'}
            contract['deduplicated_roots']=dedup_roots
            descriptor=current.request('build-current-descriptor',reference=ref,consumer_contract=contract)
            proof=current.request('audit-current-content',reference=ref,base_index=base.key,recipe_indexes=[],deduplicated_roots=dedup_roots)
        finally:current.close();base.close()
        roots={'accepted-base':str(body),'nightly-controls-v1':str(self.b.controls),'nightly-objects-v1':str(self.b.objects)}
        for p in roots.values():(Path(p)/'RECOVERY_READ.lease').touch(exist_ok=True)
        packet=dict(format='vk-nightly-composed-consumer-packet-v1',descriptor=descriptor,descriptor_sha256=checksum(descriptor),consumer_contract=contract,consumer_contract_sha256=checksum(contract),
            content_proof=proof,content_proof_sha256=checksum(proof),expected_catalogs=dict(base=proof['base_catalog_reference'],recipes=[]),
            provider_placement=dict(roots=roots,expected_uid=os.getuid(),expected_gid=os.getgid(),root_bindings={k:[Path(p).stat().st_dev,Path(p).stat().st_ino] for k,p in roots.items()},lease_paths={k:str(Path(p)/'RECOVERY_READ.lease') for k,p in roots.items()}),
            scratch_parent=str(self.root),maximum_scratch_bytes=160*1024**2,maximum_readback_bytes=256*1024**2,remaining_seconds=120,
            readback_sources=['/home/state/note']+readbacks,whole_cycle_deadline_UTC=(datetime.now(timezone.utc)+timedelta(seconds=120)).isoformat(),
            Linux_resource_admission=dict(memory_floor_bytes=0,swap_floor_bytes=0))
        result=consume(packet,checksum(packet),guard=lambda:None)
        self.assertTrue(result['independent_composed_restore_verified']);return proof,result
    @staticmethod
    def pending(name,row):
        row=dict(row);row.pop('segments',None)
        identity=[1,1,stat.S_IFREG|row['mode'],row['bytes'],row['mtime_ns'],123,row['uid'],row['gid'],1]
        point=dict(source='/'+name,state='qualified-pending-body',row=row,source_identity=identity)
        return dict(member=row,qualification=point)
    def test_worker_import_reuse_native_graph_audit_and_actual_composed_consumer(self):
        shared=Path('/home/mcp/code/worktrees/0815-vk-deduplicate-c/_vibe_kanban_repo/scripts/log-dedup')
        if not shared.is_dir():self.skipTest('source-pinned converter fixture SDK unavailable')
        sys.path.insert(0,str(shared));self.addCleanup(lambda:sys.path.remove(str(shared)))
        from test_nightly_graph import GraphOwnerTests
        import packed_graph
        from vk_nightly_file_version import attributes
        owner=GraphOwnerTests();owner.setUp();self.addCleanup(owner.doCleanups)
        scratch=owner.f.base/'packed';scratch.mkdir(mode=0o700);records=[]
        with packed_graph.checkpoint_graph(owner.recovery,owner.graph,hook=owner.hook,normal=owner.normal,operation='a'*32,plan_sha256='1'*64,seed='2'*64,save=lambda n,r:records.append(r),scratch=scratch):pass
        originals=[]
        for row in owner.f.plan['files']:
            for name in [row['path']]+[str(Path(row['path']).with_suffix('.'+s['extension'])) for s in row['sidecars']]:
                path=owner.f.source/name;st=path.stat();originals.append(dict(relative=name,normal_namespace_name=str(path)[1:],bytes=st.st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),Linux_metadata=dict(mode=st.st_mode&0o7777,uid=st.st_uid,gid=st.st_gid,mtime_ns=st.st_mtime_ns,xattrs=attributes(path))))
        for r in records:
            ref=r['checkpoint']['index_reference'];dbpath=owner.databases[ref['sha256']]
            actual=self.b.import_other(dbpath) # replace SDK fixture token with real independently read-back SQLite digest
            ref.update(sha256=actual,selector=actual+'.sqlite',layer='nightly-controls-v1',bytes=dbpath.stat().st_size)
        contract=prepare('a'*32,owner.f.plan,{'files':originals},records,dict(complete=True,files=len(owner.f.plan['files']),normal_B_original_and_graph_verified=True),archive_root=str(owner.f.archive))
        refs=list(checkpoint_imports(contract,checksum(contract)))
        from vk_nightly_checkpoint_members import import_checkpoint,NativeDependencies
        probe=sqlite3.connect(':memory:',isolation_level=None);self.addCleanup(probe.close)
        provider=NativeDependencies(self.b.controls,self.b.objects,lambda:None)
        def fail_import():
            if probe.in_transaction:raise OSError('interrupted converter import')
        with self.assertRaisesRegex(OSError,'interrupted converter import'):
            import_checkpoint(probe,provider,refs[0]['reference'],refs[0]['source_root'],guard=fail_import)
        self.assertEqual(probe.execute('select count(*) from converted_checkpoints').fetchone(),(0,))
        self.assertEqual(probe.execute('select count(*) from converted_carriers').fetchone(),(0,))
        resumed=import_checkpoint(probe,provider,refs[0]['reference'],refs[0]['source_root'],guard=lambda:None)
        self.assertFalse(resumed['reused'])
        self.assertTrue(import_checkpoint(probe,provider,refs[0]['reference'],refs[0]['source_root'],guard=lambda:None)['reused'])
        from vk_nightly_converted_history import checkpoint_batches
        batches=list(checkpoint_batches([(contract,checksum(contract))]*4,maximum_bytes=2048))
        self.assertEqual(sum(map(len,batches)),len(refs)*4)
        self.assertTrue(all(len(json.dumps(b,separators=(',',':')).encode())<=2048 for b in batches))

        db,path,current_contract,body=self.fixture_map(SQL=True);readbacks=['/home/state/state.sqlite']
        # Actual SQLite API snapshot from fixture(), independently reopened for
        # schema/integrity, then its exact acceptance record goes through the
        # real native object protocol. Final audit decodes that record again.
        sql_name='home/state/state.sqlite'
        value=decode_member(db.execute('select row from members where name=?',(sql_name,)).fetchone()[0])
        with sqlite3.connect(body/'state.sqlite') as image:
            self.assertEqual(image.execute('pragma integrity_check').fetchall(),[('ok',)])
            schema=image.execute('select type,name,tbl_name,sql from sqlite_master order by type,name,tbl_name,sql').fetchall()
        image.close();point=value['SQL_point'];point.pop('B_acceptance_object')
        point['member']=value['member']
        point['independent']['schema_sha256']=hashlib.sha256(json.dumps(schema,separators=(',',':')).encode()).hexdigest()
        with self.receiver() as remote:
            seal=remote.client.ensure(json.dumps(point,sort_keys=True,separators=(',',':')).encode());seal.pop('reused',None)
        point['B_acceptance_object']=seal
        db.execute('update members set row=? where name=?',(encode_member(value),sql_name))
        # Current frontend selection is represented explicitly, alongside the
        # required executable pin, through the same normal typed consumer.
        alias=dict(value['member']);alias={k:v for k,v in alias.items() if k in ('mode','uid','gid','mtime_ns','xattrs')}
        alias.update(kind='symlink',target='/home/state/note')
        db.execute('insert into members values(?,?,?)',('home/state/frontend-current','symlink',encode_member(dict(member=alias))))
        self.receivers.clear()
        # A current qualified scope, not a new scan; input observations are fixtures.
        for r in records:
            for member in r['members']['files']:
                name='home/state/'+member['path'];row=dict(member['metadata'],kind='file',sha256=member['sha256'],bytes=member['bytes'])
                db.execute('insert into members values(?,?,?)',(name,'file-needs-capture',encode_member(self.pending(name,row))))
                readbacks.append('/'+name)
        for r in refs:r['source_root']='/home/state'
        seed=self.b.import_other(path);config=self.config(seed,refs)
        config['deduplicated_roots']=['/home/state/'+owner.f.paths[0].split('/')[0]]
        owner.f.archive.rename(owner.f.base/'retired-staging')
        with patch('vk_nightly_typed_capture.capture_qualified_version',side_effect=AssertionError('converted history recaptured')):
            first=self.execute(config)
            config['converted_checkpoints']=[] # independently imported catalog persists on B
            second=self.execute(config)
        self.assertEqual(first['completed_members'],0);self.assertEqual(second['completed_members'],0)
        self.assertEqual(sum(c.payload_bytes_sent for c in self.receivers),0)
        proof,result=self.final(seed,current_contract,body,readbacks=readbacks,dedup_roots=['/home/state/'+owner.f.paths[0].split('/')[0]])
        self.assertGreater(proof['deduplicated_file_points'],0)
        self.assertEqual(proof['SQL_acceptance_records_independently_decoded'],1)
        self.assertEqual(proof['converted_histories_verified'],2)
        self.assertEqual(proof['converted_original_bytes_verified'],sum(r['bytes'] for r in originals if r['relative'].endswith('.jsonl')))
        self.assertTrue(any(r.get('SQLite_integrity')=='ok' for r in result['actual_normal_reader_restore']))
        self.assertEqual(len(result['actual_normal_reader_restore']),len(readbacks)+1)
        current=self.b.client.connect('prepared-main',seed)
        victim=current.execute("select name from members where name like '%/.log-objects/%' limit 1").fetchone()[0]
        current.execute('delete from members where name=?',(victim,));current.close()
        # Separate names retain the first accepted fixture seal and readback.
        with self.assertRaisesRegex((ValueError,RuntimeError),'(object|dependency|missing|protocol)'):
            self.final(seed,current_contract,body,readbacks=readbacks,dedup_roots=['/home/state/'+owner.f.paths[0].split('/')[0]])

    def test_large_new_history_interruption_resume_reuse_native_audit_and_restore(self):
        from vk_nightly_qualification import qualify_file
        from vk_nightly_file_version import capture_qualified_version
        from vk_nightly_recipe_pages import leaves
        # 7000 min-sized CDC chunks would exceed the old 1MiB expanded row.
        n=0
        while True:
            tail=(str(n).encode()*64)[:62]+b'\\n'
            if hashlib.sha256(tail).digest()[0]&15==0:break
            n+=1
        chunk=b'x'*(16386-len(tail))+tail;count=7000
        self.assertGreater(count*300,1024**2)
        source=self.root/'large-fixture.data'
        with source.open('wb') as f:
            for _ in range(count):f.write(chunk)
        point=qualify_file(source,maximum_bytes=128*1024**2,journal=dict(ready=True,errors=[],instance='fixture-current',sequence=20,scope_sha256='2'*64,plan_sha256='1'*64),carriers=lambda *_:[],guard=lambda:None)
        point['source']='/home/state/large.jsonl';name=point['source'][1:]
        db,path,contract,body=self.fixture_map()
        db.execute('insert into members values(?,?,?)',(name,'file-needs-capture',encode_member(dict(member=point['row'],qualification=point))))
        seed=self.b.import_other(path);config=self.config(seed);config['deduplicated_roots']=['/'+name]
        def interrupted(p,sink,**kw):
            with source.open('rb') as f:sink.write(f.read(262144))
            raise RuntimeError('fixture interruption after independently accepted leaf')
        with patch('vk_nightly_typed_capture.capture_qualified_version',interrupted):
            with self.assertRaisesRegex(RuntimeError,'fixture interruption'):self.execute(config)
        accepted_before=len(list(self.b.objects.glob('*.accepted.json')))
        self.assertGreater(accepted_before,0)
        def capture(p,sink,**kw):return capture_qualified_version(dict(p,source=str(source)),sink,**kw)
        with patch('vk_nightly_typed_capture.capture_qualified_version',capture):result=self.execute(config)
        self.assertEqual(result['completed_members'],1)
        with patch('vk_nightly_typed_capture.capture_qualified_version',side_effect=AssertionError('unchanged source rescanned')):
            repeated=self.execute(config)
        self.assertEqual(repeated['completed_members'],0);self.assertEqual(self.receivers[-1].payload_bytes_sent,0)
        current=self.b.client.connect('prepared-main',seed)
        raw=current.execute('select row from members where name=?',(name,)).fetchone()[0]
        selected=decode_member(raw);self.assertEqual(len(selected['member']['segments']),1)
        self.assertEqual(selected['member']['segments'][0]['encoding'],'recipe-v1');self.assertLess(len(raw),16384)
        current.close()
        proof,restored=self.final(seed,contract,body,readbacks=['/'+name],dedup_roots=['/'+name])
        self.assertEqual(proof['deduplicated_file_points'],1)
        self.assertEqual(restored['actual_normal_reader_restore'][-1]['sha256'],point['row']['sha256'])
        self.assertEqual(restored['actual_normal_reader_restore'][-1]['bytes'],len(chunk)*count)
        # Metadata-only source change: requalified same bytes must reuse the
        # prior completed page and its authenticated full ordered proof.
        os.utime(source,ns=(source.stat().st_atime_ns,source.stat().st_mtime_ns+1000000))
        same=qualify_file(source,maximum_bytes=128*1024**2,journal=dict(point['journal'],ready=True,errors=[]),carriers=lambda *_:[],guard=lambda:None)
        same['source']='/'+name
        current=self.b.client.connect('prepared-main',seed)
        current.execute("update members set state='file-needs-capture',row=? where name=?",(encode_member(dict(member=same['row'],qualification=same)),name));current.close()
        with patch('vk_nightly_typed_capture.capture_qualified_version',side_effect=AssertionError('unchanged body recopied')):
            metadata_only=self.execute(config)
        self.assertEqual(metadata_only['completed_members'],0)
        self.final(seed,contract,body,readbacks=['/'+name],dedup_roots=['/'+name])
        with source.open('ab') as stream:stream.write(b'new active tail\n'*4096)
        changed=qualify_file(source,maximum_bytes=128*1024**2,journal=dict(point['journal'],ready=True,errors=[]),carriers=lambda *_:[],guard=lambda:None);changed['source']='/'+name
        current=self.b.client.connect('prepared-main',seed)
        current.execute("update members set state='file-needs-capture',row=? where name=?",(encode_member(dict(member=changed['row'],qualification=changed)),name));current.close()
        with patch('vk_nightly_typed_capture.capture_qualified_version',capture):incremental=self.execute(config)
        self.assertEqual(incremental['completed_members'],1)
        self.assertLess(incremental['encoded_payload_bytes_sent'],65536)
        _,later=self.final(seed,contract,body,readbacks=['/'+name],dedup_roots=['/'+name])
        self.assertEqual(later['actual_normal_reader_restore'][-1]['sha256'],changed['row']['sha256'])
        print(json.dumps(dict(large_bytes=len(chunk)*count,member_row_bytes=len(raw),completed_points=result['completed_members'],
            source_bytes=result['source_bytes_read'],new_encoded_payload=result['encoded_payload_bytes_sent'],repeat_payload=0,
            actual_native_audit=True,actual_normal_consumer=True,metadata_only_payload=metadata_only['encoded_payload_bytes_sent'],changed_tail_payload=incremental['encoded_payload_bytes_sent'])))

    def test_native_portable_modules_execute_without_checkout_or_posix_imports(self):
        names=('vk_nightly_control_format','vk_nightly_file_version','vk_nightly_checkpoints',
            'vk_nightly_qualification','vk_nightly_current_map','vk_typed_recovery','vk_nightly_recovery_descriptor',
            'vk_nightly_recipe_pages','vk_nightly_checkpoint_members','vk_nightly_composed_proofs')
        modules={n:(self.source_dir/(n+'.py')).read_text() for n in names}
        data=dict(objects=(self.source_dir/'vk_nightly_objects.py').read_text(),modules=modules,
                  controls=(self.source_dir/'vk_nightly_b_controls.py').read_text())
        program="""import sys,json,types,importlib.abc
class NoPOSIX(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname in ('fcntl','resource','pwd','grp'):raise ImportError('Windows unavailable: '+fullname)
sys.meta_path.insert(0,NoPOSIX());p=json.load(sys.stdin)
o=types.ModuleType('vk_nightly_objects');sys.modules[o.__name__]=o;exec(p['objects'],o.__dict__)
for name,code in p['modules'].items():
 m=types.ModuleType(name);sys.modules[name]=m;exec(code,m.__dict__)
c=types.ModuleType('native_controls');exec(p['controls'],c.__dict__)
import vk_nightly_recipe_pages as pages
s={'layer':'nightly-objects-v1','selector':'a'*64+'.zlib','encoding':'recipe-v1','bytes':0,'sha256':'a'*64,'page_bytes':1,'page_sha256':'a'*64,'encoded_bytes':9,'encoded_sha256':'b'*64}
pages.validate(s)
print('isolated portable closure passed')
"""
        result=subprocess.run([sys.executable,'-I','-B','-c',program],input=json.dumps(data),text=True,capture_output=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.strip(),'isolated portable closure passed')
