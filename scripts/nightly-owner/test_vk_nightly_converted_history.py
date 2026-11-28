import copy
from contextlib import contextmanager
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

from vk_nightly_converted_history import LogicalReader,OriginalHandle,canonical,checksum,MAGIC,open_reused,prepare,verify_component
from vk_nightly_composed_restore import restore_sample

NAME='aa/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/processes/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb.jsonl'
ROOT='/fixture/sessions'


class Provider:
    location='desktop:B:/vk-backups/fixture'
    def __init__(self,bodies):self.bodies=bodies;self.reads=0;self.active=True;self.checks=0
    def check(self):
        self.checks+=1
        if not self.active:raise PermissionError('held owner/STOP revoked')
    @contextmanager
    def open_member(self,name,sha):
        self.check();self.reads+=1;data=self.bodies[name]
        if hashlib.sha256(data).hexdigest()!=sha:raise ValueError('normal B hash mismatch')
        stream=io.BytesIO(data);yield stream
        if stream.tell()!=len(data):raise ValueError('normal B stream not fully consumed')
        self.check()


def fixture(repeats=2,chunk_bytes=262144):
    body=b'x'*chunk_bytes;rawhash=hashlib.sha256()
    for _ in range(repeats):rawhash.update(body)
    chunk=hashlib.sha256(body).hexdigest();obj=NAME.rsplit('/',1)[0]+'/.log-objects/'+chunk+'.gz'
    data={obj:gzip.compress(body,mtime=0)}
    data[NAME]=MAGIC+canonical(dict(version=1,raw_bytes=len(body)*repeats,sha256=rawhash.hexdigest(),chunks=[dict(bytes=len(body),sha256=chunk)]*repeats))
    side=NAME[:-6]+'.capture.json';data[side]=b'{"capture_state":"closed"}'
    originals={NAME:dict(relative=NAME,normal_namespace_name=ROOT[1:]+'/'+NAME,bytes=len(body)*repeats,sha256=rawhash.hexdigest(),Linux_metadata=dict(uid=os.getuid(),gid=os.getgid(),mode=0o640,mtime_ns=123456789000,xattrs={})),side:dict(relative=side,normal_namespace_name=ROOT[1:]+'/'+side,bytes=len(data[side]),sha256=hashlib.sha256(data[side]).hexdigest(),Linux_metadata={})}
    members=[dict(path=k,bytes=len(v),sha256=hashlib.sha256(v).hexdigest(),kind='object' if k==obj else 'manifest' if k==NAME else 'sidecar') for k,v in sorted(data.items())]
    graph=dict(version=1,root='/retired/staging',members=members,physical_members=len(members),physical_bytes=sum(r['bytes'] for r in members),logical_originals={NAME:dict(bytes=len(body)*repeats,sha256=rawhash.hexdigest())},independent_backup_verified=False,note='Export is a dependency contract, not a Desktop B recovery receipt.')
    return Provider(data),graph,originals


class ConvertedHistoryTests(unittest.TestCase):
    def test_600MiB_history_streams_with_one_object_read_and_bounded_cache(self):
        provider,graph,originals=fixture(2400);reader=LogicalReader(provider,graph,originals)
        class Sink:
            count=0
            def write(self,b):self.count+=len(b);return len(b)
        sink=Sink();proof=reader.restore(NAME,sink)
        self.assertEqual(sink.count,600*1024**2);self.assertEqual(proof['bytes'],sink.count)
        self.assertEqual(provider.reads,2);self.assertLessEqual(reader.cached,4*1024**2)
        self.assertFalse(proof['metadata_restored'])

    def test_large_manifest_exceeds_old_recipe_limit_without_large_index_row(self):
        provider,graph,originals=fixture(20000,16384)
        self.assertGreater(len(provider.bodies[NAME]),1024**2)
        reader=LogicalReader(provider,graph,originals);total=0
        for block in reader.blocks(NAME):total+=len(block)
        self.assertEqual(total,327680000);self.assertEqual(provider.reads,2)
        self.assertEqual(reader.cached,16384)

    def test_ordinary_restore_separate_inode_readback_and_metadata(self):
        provider,graph,originals=fixture();reader=LogicalReader(provider,graph,originals)
        with tempfile.TemporaryDirectory(dir='/dev/shm') as d:
            result=restore_sample(OriginalHandle(reader,ROOT),ROOT+'/'+NAME,Path(d),guard=provider.check)
            self.assertTrue(result['Linux_metadata_verified']);self.assertEqual(result['sha256'],originals[NAME]['sha256'])
            self.assertEqual(list(Path(d).iterdir()),[])

    def test_scope_traversal_missing_object_and_unconverted_raw_refused(self):
        provider,graph,originals=fixture();reader=LogicalReader(provider,graph,originals)
        with self.assertRaises(ValueError):reader.restore('../other',io.BytesIO())
        graph['members']=[r for r in graph['members'] if r['kind']!='object']
        with self.assertRaisesRegex(ValueError,'missing shared object'):LogicalReader(provider,graph,originals).restore(NAME,io.BytesIO())
        provider,graph,originals=fixture();provider.bodies[NAME]=b'raw duplicated log'
        for r in graph['members']:
            if r['path']==NAME:r.update(bytes=len(provider.bodies[NAME]),sha256=hashlib.sha256(provider.bodies[NAME]).hexdigest())
        with self.assertRaisesRegex(ValueError,'converted manifest'):LogicalReader(provider,graph,originals).restore(NAME,io.BytesIO())

    def test_cached_bytes_never_bypass_revoked_owner_and_retry_is_read_only(self):
        provider,graph,originals=fixture();reader=LogicalReader(provider,graph,originals)
        iterator=reader.blocks(NAME);next(iterator);provider.active=False
        with self.assertRaises(PermissionError):next(iterator)
        provider.active=True;out=io.BytesIO();reader.restore(NAME,out)
        self.assertEqual(len(out.getvalue()),originals[NAME]['bytes']);self.assertEqual(provider.reads,3)

    def test_corrupt_or_bomb_object_refused(self):
        provider,graph,originals=fixture();obj=next(r for r in graph['members'] if r['kind']=='object')
        provider.bodies[obj['path']]=gzip.compress(b'x'*262145,mtime=0)
        obj.update(bytes=len(provider.bodies[obj['path']]),sha256=hashlib.sha256(provider.bodies[obj['path']]).hexdigest())
        with self.assertRaises(ValueError):LogicalReader(provider,graph,originals).restore(NAME,io.BytesIO())

    def test_complete_contract_and_existing_normal_reopener_are_required(self):
        provider,graph,originals=fixture();called=[]
        contract=dict(format='vk-nightly-converter-reuse-v1',graph=graph,records=[],originals=originals)
        @contextmanager
        def reopen(recovery,g,r,**kw):called.append('normal_reopen');yield provider
        with open_reused(provider,contract,checksum(contract),packed=SimpleNamespace(reopen_graph=reopen),hook=None,normal={},scratch='/dev/shm',graph_verifier=lambda *a:dict(independent_backup_verified=True,physical_members=3)) as reader:
            reader.restore(NAME,io.BytesIO())
        self.assertEqual(called,['normal_reopen'])
        changed=copy.deepcopy(contract);changed['graph']['physical_members']=0
        with self.assertRaises(ValueError):
            with open_reused(provider,changed,checksum(contract),packed=None,hook=None,normal={},scratch='/dev/shm',graph_verifier=None):pass

    def test_metadata_preparation_requires_exact_retained_graph_and_complete_result(self):
        _,graph,originals=fixture();side=NAME[:-6]+'.capture.json'
        plan=dict(source_root=ROOT,files=[dict(path=NAME,sha256=originals[NAME]['sha256'],raw_bytes=originals[NAME]['bytes'],sidecars=[dict(extension='capture.json',sha256=originals[side]['sha256'])])])
        manifest={'files':[]};record=dict(format='vk-packed-archive-graph-v1',graph_sha256=checksum(graph),checkpoint=dict(index_reference=dict(layer='nightly-controls-v1',selector='a'*64+'.sqlite',sha256='a'*64),manifest=manifest,manifest_sha256=checksum(manifest)),members=dict(files=graph['members']))
        result=dict(complete=True,normal_B_original_and_graph_verified=True,files=1)
        value=prepare('a'*32,plan,{'files':list(originals.values())},[record],result,archive_root=graph['root'])
        self.assertTrue(value['prepared_only']);self.assertEqual(value['graph'],graph)
        record['members']['files']=record['members']['files'][:-1]
        with self.assertRaises(ValueError):prepare('a'*32,plan,{'files':list(originals.values())},[record],result,archive_root=graph['root'])


class PackedProviderIntegrationTests(unittest.TestCase):
    def test_existing_packed_SQL_checkpoints_restore_without_staging_or_new_capture(self):
        import sys
        from unittest.mock import patch
        shared=Path('/home/mcp/code/worktrees/0815-vk-deduplicate-c/_vibe_kanban_repo/scripts/log-dedup')
        if not shared.is_dir():self.skipTest('converter qualification source unavailable')
        sys.path.insert(0,str(shared));self.addCleanup(lambda:sys.path.remove(str(shared)))
        import packed_graph as packed
        import graph as graph_module
        from test_nightly_graph import GraphOwnerTests
        from vk_nightly_file_version import attributes
        owner=GraphOwnerTests();owner.setUp();self.addCleanup(owner.doCleanups)
        scratch=owner.f.base/'packed';scratch.mkdir(mode=0o700);records=[]
        with packed.checkpoint_graph(owner.recovery,owner.graph,hook=owner.hook,normal=owner.normal,
                operation='a'*32,plan_sha256='1'*64,seed='2'*64,save=lambda n,r:records.append(r),scratch=scratch):pass
        for r in records:
            ref=r['checkpoint']['index_reference'];ref.update(layer='nightly-controls-v1',selector=ref['sha256']+'.sqlite',bytes=owner.databases[ref['sha256']].stat().st_size)
        originals=[]
        for row in owner.f.plan['files']:
            names=[row['path']]+[str(Path(row['path']).with_suffix('.'+s['extension'])) for s in row['sidecars']]
            for name in names:
                path=owner.f.source/name;st=path.stat()
                originals.append(dict(relative=name,normal_namespace_name=str(path)[1:],bytes=st.st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),Linux_metadata=dict(mode=st.st_mode&0o7777,uid=st.st_uid,gid=st.st_gid,mtime_ns=st.st_mtime_ns,atime_ns=st.st_atime_ns,xattrs=attributes(path))))
        contract=prepare('a'*32,owner.f.plan,{'files':originals},records,dict(complete=True,normal_B_original_and_graph_verified=True,files=len(owner.f.plan['files'])),archive_root=str(owner.f.archive))
        owner.f.archive.rename(owner.f.base/'retired-fixture-staging')
        with patch.object(owner.hook,'checkpoint',side_effect=AssertionError('must not recapture')):
            with open_reused(owner.recovery,contract,checksum(contract),packed=packed,hook=owner.hook,normal=owner.normal,scratch=scratch,graph_verifier=graph_module.verify_provider) as reader:
                for row in owner.f.plan['files']:
                    output=io.BytesIO();proof=reader.restore(row['path'],output)
                    self.assertEqual(output.getvalue(),owner.f.original);self.assertTrue(proof['original_byte_stream_verified'])
                result=verify_component(reader,contract,checksum(contract),scratch_parent=scratch,
                    maximum_scratch_bytes=20*1024**2,maximum_readback_bytes=20*1024**2,guard=owner.recovery.check)
                self.assertTrue(result['component_restore_verified'])
                self.assertEqual(len(result['original_versions']),len(originals))
                self.assertFalse(result['whole_current_set_accepted'])
                for r in result['original_versions']:self.assertTrue(r['Linux_metadata_verified'])
                with self.assertRaisesRegex(ValueError,'admitted'):
                    verify_component(reader,contract,checksum(contract),scratch_parent=scratch,
                        maximum_scratch_bytes=1,maximum_readback_bytes=1,guard=owner.recovery.check)


class TypedCompositionTests(unittest.TestCase):
    def test_existing_typed_descriptor_restores_physical_graph_and_SQL_together(self):
        from test_vk_nightly_recovery_descriptor import fixture as map_fixture,reference
        from vk_nightly_recovery_descriptor import build
        from vk_nightly_current_map import encode_member
        from vk_typed_recovery import LocalDependencies,HeldRecoverySet,held_index
        from vk_nightly_converted_history import typed_entries,TypedGraphDependencies,ConvertedCarriers
        with tempfile.TemporaryDirectory(dir='/dev/shm') as d:
            root=Path(d);db,path,base_contract,rows,body,controls=map_fixture(root,SQL=True)
            self.addCleanup(db.close);scratch=root/'scratch';scratch.mkdir(mode=0o700)
            provider,graph,originals=fixture()
            metadata=dict(mode=0o640,uid=os.getuid(),gid=os.getgid(),mtime_ns=123456789000,xattrs={})
            contract=dict(format='vk-nightly-converter-reuse-v1',source_root='/home/state',graph=graph,
                originals=originals,checkpoints=[],records=[dict(members=dict(files=[dict(r,metadata=metadata) for r in graph['members']]))])
            sha=checksum(contract);entries=list(typed_entries(contract,sha))
            lookup=ConvertedCarriers(LogicalReader(provider,graph,originals),contract,sha)
            reads=provider.reads
            for _,row in entries:
                self.assertEqual(list(lookup(row['sha256'],row['bytes'])),[row])
            self.assertEqual(list(lookup('f'*64,99)),[]) # changed/pending remains for normal capture
            self.assertEqual(provider.reads,reads) # lookup reuses verified bytes; no source/B body read
            for name,member in entries:
                self.assertEqual(len(member['segments']),1)
                db.execute('insert into members values(?,?,?)',(name,'verified-file',encode_member(dict(member=member))))
            base=LocalDependencies({'accepted-base':body,'nightly-controls-v1':controls},base_contract['dependencies'],admission_check=lambda:None)
            with base.held():
                mixed=TypedGraphDependencies(base,LogicalReader(provider,graph,originals),contract,sha)
                base_contract['dependencies']=mixed.identities
                descriptor=build(db,reference(path),base_contract,checkpoint=lambda:None)
                with held_index(mixed,*descriptor['indexes']) as index:
                    handle=HeldRecoverySet(descriptor,checksum(descriptor),mixed,index)
                    self.assertFalse(handle.verified)
                    handle.validate(plan_sha256=base_contract['plan_sha256'],scope_sha256=base_contract['scope_sha256'],
                        required_sources=base_contract['sources'],original_sources=base_contract['original_sources'],
                        required_pins=base_contract['required_pins'],required_SQL=base_contract['required_SQL'])
                    for name,row in entries:
                        proof=restore_sample(handle,'/'+name,scratch,guard=mixed.check)
                        self.assertEqual(proof['sha256'],row['sha256']);self.assertTrue(proof['Linux_metadata_verified'])
                    provider.active=False
                    with self.assertRaises(PermissionError):list(handle.blocks(entries[0][0]))
                    provider.active=True # synthetic fixture only; permit orderly test-context teardown
            self.assertEqual(list(scratch.iterdir()),[])
