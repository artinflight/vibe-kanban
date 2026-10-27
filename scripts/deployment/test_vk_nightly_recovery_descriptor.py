import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
import unittest

from vk_nightly_current_map import FORMAT as MAP_FORMAT,CurrentMap,encode_member,decode_member
from vk_nightly_recovery_descriptor import build,journal_evidence,sample_runtime_files
from vk_typed_recovery import HeldRecoverySet,LocalDependencies,canonical,checksum,held_index


def fixture(root,*,SQL=False):
    root=Path(root);controls=root/'controls';body=root/'body';controls.mkdir();body.mkdir()
    for folder in (controls,body):(folder/'RECOVERY_READ.lease').touch()
    metadata=dict(mode=0o600,uid=os.getuid(),gid=os.getgid(),mtime_ns=123,xattrs={})
    rows={'home/state':dict(metadata,kind='directory')}
    note=b'verified retained body';(body/'note').write_bytes(note)
    rows['home/state/note']=dict(metadata,kind='file',bytes=len(note),sha256=hashlib.sha256(note).hexdigest(),segments=[
        dict(layer='accepted-base',selector='note',bytes=len(note),sha256=hashlib.sha256(note).hexdigest())])
    path=controls/'current.sqlite';db=sqlite3.connect(path,isolation_level=None)
    db.execute('create table metadata(format text,complete integer)');db.execute('insert into metadata values(?,1)',(MAP_FORMAT,))
    db.execute('create table members(name text primary key,state text,row blob)')
    db.execute('create table SQL_sources(path text primary key)')
    points={}
    if SQL:
        live=sqlite3.connect(':memory:');live.execute('create table retained(value text)');live.execute("insert into retained values('current')");live.commit()
        image=sqlite3.connect(body/'state.sqlite');live.backup(image);image.close();live.close()
        raw=(body/'state.sqlite').read_bytes();sha=hashlib.sha256(raw).hexdigest();source='/home/state/state.sqlite'
        member=dict(metadata,kind='file',bytes=len(raw),sha256=sha,segments=[dict(layer='accepted-base',selector='state.sqlite',bytes=len(raw),sha256=sha)])
        point=dict(source=source,status='consistent_SQL_point_verified',method='SQLite-backup-API',bytes=len(raw),sha256=sha,
            source_API_point_qualifies_later_epoch_not_original=True,original_source_API_point_at=time.time(),
            independent=dict(integrity='ok',bytes=len(raw),sha256=sha),B_acceptance_object=dict(sha256='4'*64))
        rows[source[1:]]=member;points[source[1:]]=point
        rows['home/state/live.sqlite']=dict(metadata,kind='symlink',target=source)
        db.executemany('insert into SQL_sources values(?)',[(source,),('/home/state/live.sqlite',)])
        db.execute('insert into members values(?,?,?)',('home/state/state.sqlite-wal','SQLite-sidecar',encode_member(dict(required_SQL_source=source))))
    for name,member in rows.items():
        value=dict(member=member)
        if name in points:value['SQL_point']=points[name]
        db.execute('insert into members values(?,?,?)',(name,'verified-file' if member['kind']=='file' else member['kind'],encode_member(value)))
    binding=dict(instance='fixture-current',start_sequence=10,plan_sha256='1'*64,scope_sha256='2'*64,
        required_root_bindings={'/home/state':dict(resolved='/home/state',literal=None)})
    db.execute('create table namespace_reconciliation(id integer primary key,binding text,complete integer,suffix_complete integer)')
    db.execute('insert into namespace_reconciliation values(1,?,1,1)',(json.dumps(binding),))
    db.execute('create table namespace_replay_windows(sha256 text primary key,since integer,through integer,last_name text,complete integer,summary text)')
    db.execute('create table namespace_replay_inputs(sha256 text,part integer,data blob,primary key(sha256,part))')
    report=dict(instance=binding['instance'],plan_sha256=binding['plan_sha256'],scope_sha256=binding['scope_sha256'],
        since=10,sequence=20,coverage_model='all-selected-inodes-v1',ready=True,errors=[],changed=[],events={},
        barrier=dict(instance=binding['instance'],kernel_drain_completed=True,durable_sequence=20))
    replay=dict(since=10,through=20,required_root_bindings=binding['required_root_bindings'])
    raw=json.dumps(dict(report=report,replay=replay),sort_keys=True,separators=(',',':')).encode();sha=hashlib.sha256(raw).hexdigest()
    summary=dict(window_sha256=sha,instance=binding['instance'],since=10,through=20,journal_suffix_complete_through=20,original_epoch_repaired=False)
    db.execute('insert into namespace_replay_windows values(?,10,20,?,1,?)',(sha,'',json.dumps(summary)))
    db.execute('insert into namespace_replay_inputs values(?,0,?)',(sha,raw))
    contract=dict(format='vk-nightly-current-recovery-contract-v1',plan_sha256='1'*64,scope_sha256='2'*64,
        sources=['/home/state'],original_sources=['/home/state'],required_SQL=['/home/state/state.sqlite'] if SQL else [],
        required_pins={'/home/state/note':dict(bytes=len(note),sha256=hashlib.sha256(note).hexdigest())},
        original_source_dispositions={'/home/state':dict(original_gaps_retained=True)},
        original_epoch=dict(complete=False,original_gaps_repaired=False,unresolved_gap_count=7,gap_manifest_sha256='5'*64,accepted_restore_proof_sha256='6'*64),
        dependencies={'accepted-base':dict(accepted_proof_sha256='7'*64),'nightly-controls-v1':dict(native_root=str(controls))})
    return db,path,contract,rows,body,controls


def reference(path):
    raw=Path(path).read_bytes()
    return dict(format=MAP_FORMAT,layer='nightly-controls-v1',selector=Path(path).name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def runtime_fixture(root,body):
    from vk_nightly_file_version import fingerprint
    path=Path(root)/'controls/runtime.sqlite';source=body/'gateway.py';source.write_bytes(b'exact runtime dependency')
    st=source.stat();sha=hashlib.sha256(source.read_bytes()).hexdigest();metadata=dict(mode=stat.S_IMODE(st.st_mode),uid=st.st_uid,gid=st.st_gid,mtime_ns=st.st_mtime_ns,xattrs={})
    member=dict(metadata,kind='file',bytes=st.st_size,sha256=sha,segments=[dict(layer='accepted-base',selector=source.name,bytes=st.st_size,sha256=sha)])
    qualification=dict(source=str(source),state='qualified-retained-body',source_identity=fingerprint(st),row=member,source_observed_at='fixture-epoch')
    proof=dict(independent_ordered_B_readback_sha256=sha,independent_ordered_B_readback_bytes=st.st_size,source_metadata=metadata)
    accepted=dict(member=member,qualification=qualification,independent_file_proof=proof)
    binding=dict(format='vk-nightly-explicit-runtime-dependency-component-v1',complete_global_scope=False,
        kernel_journal_coverage_claimed=False,source_paths=[str(source)])
    db=sqlite3.connect(path,isolation_level=None);db.execute('create table metadata(format text,binding text,complete integer)')
    db.execute('insert into metadata values(?,?,1)',(MAP_FORMAT,json.dumps(binding)))
    db.execute('create table members(name text primary key,state text,row blob)');db.execute('insert into members values(?,?,?)',
        (str(source)[1:],'verified-file',encode_member(accepted)))
    return db,path,{str(source):dict(kind='file',bytes=st.st_size,sha256=sha,source_identity=fingerprint(st))},source,accepted


def current_view(db,path):
    value=CurrentMap();value.db=db;value.path=path;value.inode=(path.stat().st_dev,path.stat().st_ino);return value


class RecoveryDescriptorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir='/dev/shm');self.addCleanup(self.tmp.cleanup)

    def use(self,SQL=False):
        values=fixture(self.tmp.name,SQL=SQL);self.addCleanup(values[0].close);return values

    def test_finite_runtime_source_sample_actual_hash_attributes_and_budget(self):
        a=Path(self.tmp.name)/'gateway';a.write_bytes(b'gateway')
        b=Path(self.tmp.name)/'route';b.write_bytes(b'route')
        sampled=sample_runtime_files([str(a),str(b)],maximum_bytes=12,checkpoint=lambda:None)
        self.assertEqual(sampled['files_sampled'],2);self.assertEqual(sampled['source_payload_bytes_hashed'],12)
        self.assertFalse(sampled['kernel_journal_coverage_claimed']);self.assertEqual(sampled['backup_payload_bytes_copied'],0)
        self.assertEqual(sampled['files'][str(a)]['sha256'],hashlib.sha256(b'gateway').hexdigest())
        self.assertEqual(sampled['files'][str(a)]['Linux_metadata']['mode'],stat.S_IMODE(a.stat().st_mode))
        with self.assertRaisesRegex(ValueError,'admitted regular file'):
            sample_runtime_files([str(a),str(b)],maximum_bytes=5,checkpoint=lambda:None)
        alias=Path(self.tmp.name)/'alias';alias.symlink_to(a)
        with self.assertRaisesRegex(ValueError,'non-symlink'):
            sample_runtime_files([str(alias)],maximum_bytes=12,checkpoint=lambda:None)

    def test_fixed_portable_descriptor_closure_is_complete_and_hash_pinned(self):
        from vk_nightly_desktop_controls import validate_control
        folder=Path(__file__).parent
        core=('vk_nightly_control_format','vk_nightly_file_version','vk_nightly_checkpoints','vk_nightly_qualification','vk_nightly_current_map')
        optional=('vk_typed_recovery','vk_nightly_recovery_descriptor')
        config=dict(maximum_index_bytes=1024**2,control_module_sha256=hashlib.sha256((folder/'vk_nightly_b_controls.py').read_bytes()).hexdigest(),
            portable_source_sha256={name:hashlib.sha256((folder/(name+'.py')).read_bytes()).hexdigest() for name in core+optional})
        _,portable=validate_control(config,folder);self.assertEqual(tuple(portable),core+optional)
        incomplete=copy.deepcopy(config);del incomplete['portable_source_sha256'][optional[1]]
        with self.assertRaisesRegex(ValueError,'fixed portable descriptor source closure'):validate_control(incomplete,folder)
        changed=copy.deepcopy(config);changed['portable_source_sha256'][optional[1]]='f'*64
        with self.assertRaisesRegex(ValueError,'source pin changed'):validate_control(changed,folder)
        extended=copy.deepcopy(config)
        extended['portable_source_sha256']['vk_nightly_composed_proofs']=hashlib.sha256((folder/'vk_nightly_composed_proofs.py').read_bytes()).hexdigest()
        _,actual=validate_control(extended,folder)
        self.assertEqual(tuple(actual),core+optional+('vk_nightly_composed_proofs',))
        extended['portable_source_sha256']['vk_nightly_composed_proofs']='e'*64
        with self.assertRaisesRegex(ValueError,'source pin changed'):validate_control(extended,folder)

    def test_descriptor_metadata_import_does_not_fake_or_require_POSIX_leases(self):
        folder=str(Path(__file__).parent)
        code=("import sys,importlib.abc;sys.path.insert(0,"+repr(folder)+
            ");\nclass NoPOSIX(importlib.abc.MetaPathFinder):\n def find_spec(self,name,*args):\n  if name=='fcntl':raise ModuleNotFoundError('POSIX leases unavailable')\n"
            "sys.meta_path.insert(0,NoPOSIX());import vk_nightly_recovery_descriptor;print('portable metadata imported')")
        run=subprocess.run([sys.executable,'-B','-c',code],capture_output=True,text=True,timeout=10)
        self.assertEqual(run.returncode,0,run.stderr);self.assertEqual(run.stdout.strip(),'portable metadata imported')

    def test_complete_descriptor_normal_independent_reader_and_actual_bodies(self):
        db,path,contract,rows,body,controls=self.use(SQL=True)
        d=build(db,reference(path),contract,checkpoint=lambda:None)
        self.assertFalse(d['independent_current_restore_accepted']);self.assertFalse(d['original_epoch_complete'])
        self.assertEqual(d['original_epoch']['unresolved_gap_count'],7)
        self.assertEqual(d['always_SQL_API_sources'],['/home/state/state.sqlite'])
        provider=LocalDependencies({'accepted-base':body,'nightly-controls-v1':controls},contract['dependencies'],admission_check=lambda:None)
        with provider.held(),held_index(provider,*d['indexes']) as index:
            h=HeldRecoverySet(d,checksum(d),provider,index)
            actual=h.validate(plan_sha256=contract['plan_sha256'],scope_sha256=contract['scope_sha256'],
                required_sources=contract['sources'],original_sources=contract['original_sources'],
                required_pins=contract['required_pins'],required_SQL=contract['required_SQL'])
            self.assertEqual(actual['member_count'],len(rows))
            self.assertEqual(b''.join(h.blocks('home/state/note')),(body/'note').read_bytes())
            restored=b''.join(h.blocks('home/state/state.sqlite'))
            self.assertEqual(restored,(body/'state.sqlite').read_bytes())
            independent=sqlite3.connect(':memory:')
            try:
                independent.deserialize(restored)
                self.assertEqual(independent.execute('pragma integrity_check').fetchall(),[('ok',)])
                self.assertEqual(independent.execute('select value from retained').fetchall(),[('current',)])
            finally:independent.close()
            self.assertEqual(d['indexes'][0]['consistent_SQL_aliases']['home/state/live.sqlite']['source'],'/home/state/state.sqlite')

    def test_current_SQL_request_requires_actual_cohort_and_reader_contract(self):
        db,path,c,_,body,controls=self.use(SQL=True)
        binding=json.loads(db.execute('select binding from namespace_reconciliation').fetchone()[0])
        source=c['required_SQL'][0]
        request=dict(format='vk-nightly-current-SQL-cohort-request-v1',
            binding=dict(source_instance=binding['instance'],plan_sha256=c['plan_sha256'],
                scope_sha256=c['scope_sha256'],source_root_bindings=binding['required_root_bindings']),
            sources=[source],SQL_scope_sources=[source],always_SQL_API_sources=[source],unchanged_SQL_points_reused=0)
        request['cohort_id']=checksum(request);c['current_SQL_request']=request;c['always_SQL_API_sources']=[source]
        with self.assertRaisesRegex(ValueError,'does not belong'):build(db,reference(path),c,checkpoint=lambda:None)
        raw=db.execute('select row from members where name=?',(source[1:],)).fetchone()[0]
        point=decode_member(raw);point['SQL_point']['SQL_cohort_id']=request['cohort_id']
        db.execute('update members set row=? where name=?',(encode_member(point),source[1:]))
        d=build(db,reference(path),c,checkpoint=lambda:None)
        provider=LocalDependencies({'accepted-base':body,'nightly-controls-v1':controls},c['dependencies'],admission_check=lambda:None)
        args=dict(plan_sha256=c['plan_sha256'],scope_sha256=c['scope_sha256'],required_sources=c['sources'],
            original_sources=c['original_sources'],required_pins=c['required_pins'],required_SQL=c['required_SQL'])
        with provider.held(),held_index(provider,*d['indexes']) as index:
            h=HeldRecoverySet(d,checksum(d),provider,index)
            with self.assertRaisesRegex(ValueError,'qualification contract'):h.validate(**args)
            h.validate(**args,required_SQL_qualification=d['current_SQL_qualification'])
            self.assertEqual(b''.join(h.blocks(source[1:])),(body/'state.sqlite').read_bytes())
            old=copy.deepcopy(d);old['SQLite'][source]['SQL_cohort_id']='a'*64
            with self.assertRaisesRegex(ValueError,'cohort differs'):
                HeldRecoverySet(old,checksum(old),provider,index).validate(**args,
                    required_SQL_qualification=d['current_SQL_qualification'])
            missing=copy.deepcopy(d);del missing['current_SQL_qualification']
            with self.assertRaisesRegex(ValueError,'qualification contract'):
                HeldRecoverySet(missing,checksum(missing),provider,index).validate(**args,
                    required_SQL_qualification=d['current_SQL_qualification'])
        corrupt=copy.deepcopy(c);corrupt['current_SQL_request']['sources']=[]
        with self.assertRaisesRegex(ValueError,'request digest'):build(db,reference(path),corrupt,checkpoint=lambda:None)
        wrong=copy.deepcopy(c);wrong['current_SQL_request']['binding']['source_instance']='another'
        r=wrong['current_SQL_request'];r['cohort_id']=checksum({k:v for k,v in r.items() if k!='cohort_id'})
        with self.assertRaisesRegex(ValueError,'scope/epoch'):build(db,reference(path),wrong,checkpoint=lambda:None)

    def test_current_SQL_request_cannot_label_always_API_target_unchanged(self):
        db,path,c,_,_,_=self.use(SQL=True);source=c['required_SQL'][0]
        binding=json.loads(db.execute('select binding from namespace_reconciliation').fetchone()[0])
        request=dict(format='vk-nightly-current-SQL-cohort-request-v1',
            binding=dict(source_instance=binding['instance'],plan_sha256=c['plan_sha256'],
                scope_sha256=c['scope_sha256'],source_root_bindings=binding['required_root_bindings']),
            sources=[],SQL_scope_sources=[source],always_SQL_API_sources=[],unchanged_SQL_points_reused=1)
        request['cohort_id']=checksum(request);c['current_SQL_request']=request;c['always_SQL_API_sources']=[]
        with self.assertRaisesRegex(ValueError,'scope/epoch'):build(db,reference(path),c,checkpoint=lambda:None)

    def test_current_SQL_request_reuses_unchanged_point_with_original_API_epoch(self):
        db,path,c,_,_,_=self.use(SQL=True);source=c['required_SQL'][0]
        db.execute("delete from members where name='home/state/live.sqlite'")
        db.execute("delete from SQL_sources where path='/home/state/live.sqlite'")
        binding=json.loads(db.execute('select binding from namespace_reconciliation').fetchone()[0])
        point=decode_member(db.execute('select row from members where name=?',(source[1:],)).fetchone()[0])['SQL_point']
        request=dict(format='vk-nightly-current-SQL-cohort-request-v1',
            binding=dict(source_instance=binding['instance'],plan_sha256=c['plan_sha256'],
                scope_sha256=c['scope_sha256'],source_root_bindings=binding['required_root_bindings']),
            sources=[],SQL_scope_sources=[source],always_SQL_API_sources=[],unchanged_SQL_points_reused=1)
        request['cohort_id']=checksum(request);c['current_SQL_request']=request;c['always_SQL_API_sources']=[]
        d=build(db,reference(path),c,checkpoint=lambda:None)
        self.assertEqual(d['current_SQL_qualification']['unchanged_sources'],[source])
        self.assertEqual(d['SQLite'][source]['epoch']['original_source_API_point_at'],point['original_source_API_point_at'])
        self.assertNotIn('SQL_cohort_id',d['SQLite'][source])

    def test_normal_reader_derives_legacy_SQL_alias_dependency_and_rejects_explicit_drop(self):
        db,path,c,_,body,controls=self.use(SQL=True)
        d=build(db,reference(path),c,checkpoint=lambda:None)
        provider=LocalDependencies({'accepted-base':body,'nightly-controls-v1':controls},c['dependencies'],admission_check=lambda:None)
        args=dict(plan_sha256=c['plan_sha256'],scope_sha256=c['scope_sha256'],required_sources=c['sources'],
            original_sources=c['original_sources'],required_pins=c['required_pins'],required_SQL=c['required_SQL'])
        with provider.held(),held_index(provider,*d['indexes']) as index:
            removed=copy.deepcopy(d);removed['always_SQL_API_sources']=[]
            with self.assertRaisesRegex(ValueError,'alias targets'):
                HeldRecoverySet(removed,checksum(removed),provider,index).validate(**args)
            legacy=copy.deepcopy(d);del legacy['always_SQL_API_sources']
            handle=HeldRecoverySet(legacy,checksum(legacy),provider,index);handle.validate(**args)
            watched=lambda start:dict(ready=True,errors=[],instance=d['journal']['instance'],
                scope_sha256=d['journal']['scope_sha256'],sequence=d['journal']['end'])
            self.assertEqual(handle.catchup(watched)['always_SQL_API_sources'],['/home/state/state.sqlite'])
            seen=[]
            handle=HeldRecoverySet(d,checksum(d),provider,index);handle.validate(**args)
            result=handle.catchup(lambda since:(seen.append(since) or watched(since)))
            self.assertEqual(seen,[20]);self.assertEqual(result['baseline_journal_through'],20)
            invalid=copy.deepcopy(d);invalid['bounded_delta_start_sequence']=10
            with self.assertRaisesRegex(ValueError,'bounded delta'):
                HeldRecoverySet(invalid,checksum(invalid),provider,index).validate(**args)

    def test_separate_runtime_point_preserves_kernel_scope_and_requests_finite_restart_resample(self):
        db,path,c,_,body,controls=self.use()
        component,component_path,expected,source,accepted=runtime_fixture(self.tmp.name,body);self.addCleanup(component.close)
        result=current_view(db,path).adopt_runtime_component(component,reference(component_path),expected,checkpoint=lambda:None)
        c['always_runtime_files']=result['always_runtime_files'];self.assertFalse(result['kernel_journal_coverage_claimed'])
        d=build(db,reference(path),c,checkpoint=lambda:None)
        self.assertEqual(d['sources'],['/home/state']);self.assertEqual(d['journal']['scope_sha256'],'2'*64)
        provider=LocalDependencies({'accepted-base':body,'nightly-controls-v1':controls},c['dependencies'],admission_check=lambda:None)
        with provider.held(),held_index(provider,*d['indexes']) as index:
            h=HeldRecoverySet(d,checksum(d),provider,index)
            args=dict(plan_sha256=c['plan_sha256'],scope_sha256=c['scope_sha256'],required_sources=c['sources'],
                original_sources=c['original_sources'],required_pins=c['required_pins'],required_SQL=c['required_SQL'])
            with self.assertRaisesRegex(ValueError,'runtime component contract'):h.validate(**args)
            h.validate(**args,required_runtime_files=c['always_runtime_files'])
            self.assertEqual(b''.join(h.blocks(str(source)[1:])),source.read_bytes())
            delta=h.catchup(lambda since:dict(ready=True,errors=[],instance='fixture-current',scope_sha256='2'*64,sequence=22))
            self.assertEqual(delta['runtime_files_to_observe_always'],[str(source)])
            self.assertFalse(delta['kernel_coverage_for_runtime_files_claimed'])

    def test_runtime_component_bad_proof_and_commit_failure_keep_main_and_component(self):
        db,path,c,_,body,_=self.use();main=current_view(db,path)
        component,component_path,expected,source,accepted=runtime_fixture(self.tmp.name,body);self.addCleanup(component.close)
        before=db.execute('select name,state,row from members order by name').fetchall()
        calls=0
        def stop():
            nonlocal calls
            calls+=1
            if calls==2:raise PermissionError('actual STOP at runtime adoption commit')
        with self.assertRaisesRegex(PermissionError,'STOP'):
            main.adopt_runtime_component(component,reference(component_path),expected,checkpoint=stop)
        self.assertEqual(db.execute('select name,state,row from members order by name').fetchall(),before)
        bad=copy.deepcopy(accepted);bad['independent_file_proof']['independent_ordered_B_readback_sha256']='f'*64
        component.execute('update members set row=?',(encode_member(bad),))
        with self.assertRaisesRegex(ValueError,'read-back runtime file'):
            main.adopt_runtime_component(component,reference(component_path),expected,checkpoint=lambda:None)
        self.assertEqual(db.execute('select name,state,row from members order by name').fetchall(),before)

    def test_unresolved_member_missing_SQL_or_runtime_pin_cannot_build(self):
        db,path,c,_,_,_=self.use(SQL=True)
        db.execute("update members set state='file-needs-capture' where name='home/state/note'")
        with self.assertRaisesRegex(ValueError,'unresolved'):build(db,reference(path),c,checkpoint=lambda:None)
        db.execute('pragma query_only=off')  # RAM-only fixture mutation between independent cases.
        db.execute("update members set state='verified-file' where name='home/state/note'")
        wrong=copy.deepcopy(c);wrong['required_SQL'].append('/home/state/missing.sqlite')
        with self.assertRaisesRegex(ValueError,'cohort is incomplete'):build(db,reference(path),wrong,checkpoint=lambda:None)
        wrong=copy.deepcopy(c);wrong['required_pins']['/home/state/note']['sha256']='a'*64
        with self.assertRaisesRegex(ValueError,'runtime pin'):build(db,reference(path),wrong,checkpoint=lambda:None)

    def test_actual_journal_input_hash_gap_and_missing_barrier_fail_closed(self):
        db,path,c,_,_,_=self.use()
        sha,raw=db.execute('select sha256,data from namespace_replay_inputs').fetchone()
        db.execute('update namespace_replay_inputs set data=?',(raw+b' ',))
        with self.assertRaisesRegex(ValueError,'input hash differs'):build(db,reference(path),c,checkpoint=lambda:None)
        db.execute('update namespace_replay_inputs set data=?',(raw,));db.execute('update namespace_replay_windows set since=11')
        with self.assertRaisesRegex(ValueError,'gap or inconsistent'):build(db,reference(path),c,checkpoint=lambda:None)
        db.execute('update namespace_replay_windows set since=10');db.execute('update namespace_reconciliation set suffix_complete=0')
        with self.assertRaisesRegex(ValueError,'durable suffix'):build(db,reference(path),c,checkpoint=lambda:None)

    def test_original_gap_scope_and_undeclared_carrier_cannot_be_hidden(self):
        db,path,c,_,_,_=self.use()
        bad=copy.deepcopy(c);bad['original_epoch']['complete']=True
        with self.assertRaisesRegex(ValueError,'original-epoch'):build(db,reference(path),bad,checkpoint=lambda:None)
        bad=copy.deepcopy(c);bad['sources'].append('/missing')
        with self.assertRaisesRegex(ValueError,'actual journal namespace'):build(db,reference(path),bad,checkpoint=lambda:None)
        bad=copy.deepcopy(c);del bad['dependencies']['accepted-base']
        with self.assertRaisesRegex(ValueError,'carrier dependency'):build(db,reference(path),bad,checkpoint=lambda:None)
        def stopped():raise PermissionError('actual owner STOP')
        with self.assertRaisesRegex(PermissionError,'owner STOP'):build(db,reference(path),c,checkpoint=stopped)


if __name__=='__main__':unittest.main()
