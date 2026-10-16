"""Real-B fixed-adapter acceptance, fresh synthetic scope only; no adoption."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import time
import uuid
from unittest.mock import patch

from rehearse_vk_nightly_real_b import desktop
from vk_change_journal import scope
from vk_nightly_capture_adapter import RegisteredWorkspace, run_capture
from vk_prep_common import identity, storage
from rehearse_vk_nightly_parent_death import parent_death_case


def recovery_cases(config,plan,source,verify):
    from vk_nightly_b_fault_fixture import instrument
    from vk_nightly_capture_adapter import Resident
    read_text=Path.read_text;cases={}
    original_db=source/'state.sqlite'
    for stage,expected_exit in [('before_publication',81),('after_publication',82),('during_retention',83),
                                ('candidate_objects_removed',84),('rename_before_fsync',85)]:
        case={**config,'wsl_root':config['wsl_root']+'-'+stage}
        with sqlite3.connect(original_db) as db:db.execute("DELETE FROM retained WHERE value='second'")
        (source/'deleted').write_bytes(b'owned removable fixture')
        first=run_capture(case,plan,enroll_fresh=True)
        if not first['result']['passed']:raise ValueError('first fixture capture failed: '+str(first))
        with sqlite3.connect(original_db) as db:db.execute("INSERT INTO retained VALUES('second')")
        (source/'deleted').unlink()
        def patched(path,*args,**kwargs):
            raw=read_text(path,*args,**kwargs)
            return instrument(raw,stage) if path.name=='vk_nightly_b_job.py' else raw
        error=None;exits=[];close=Resident.close
        def record_exit(resident):
            close(resident);exits.append(resident.process.returncode)
        with patch.object(Path,'read_text',patched),patch.object(Resident,'close',record_exit):
            try:run_capture(case,plan)
            except (ValueError,OSError) as exc:error=str(exc)
        if error is None or exits!=[expected_exit]:raise AssertionError('fixture exit mismatch: '+str(exits))
        def recovering(path,*args,**kwargs):
            raw=read_text(path,*args,**kwargs)
            return instrument(raw,stage,recover=True) if path.name=='vk_nightly_b_job.py' else raw
        with patch.object(Path,'read_text',recovering):
            recovered=run_capture(case,plan,recover_only=True)
        if not recovered['result']['passed']:raise AssertionError('B recovery failed: '+str(recovered))
        remote='B:/'+case['wsl_root'].removeprefix('/mnt/b/')
        # Read ONLY the current objects in a separate native Windows process.
        expected=verify
        if stage in ('before_publication','candidate_objects_removed'):
            expected=expected.replace("[('before',),('second',)]","[('before',)]").replace("assert 'deleted' not in m['entries']","assert 'deleted' in m['entries']")
        recovery=desktop('ROOT='+repr(remote)+'\n'+expected)
        retry=run_capture(case,plan)
        if not retry['result']['passed']:raise AssertionError('recovered fixture retry failed')
        final=desktop('ROOT='+repr(remote)+'\n'+verify)
        cases[stage]={'process_interrupted':True,'actual_fixture_exit':exits[0],'channel_error':error,
                      'reconciliation':recovered,'independent_current_recovery':recovery,'retry':retry,'final':final}
        print('Real B lifecycle recovery accepted:',stage,flush=True)
    return cases


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-synthetic-fixtures',action='store_true',required=True);parser.parse_args()
    local=storage('/mnt/vk-storage/vk-restart-safeguards-20261009')/('B-lifecycle-'+uuid.uuid4().hex);local.mkdir()
    source=local/'source';source.mkdir();dbpath=source/'state.sqlite'
    with sqlite3.connect(dbpath) as db:
        db.execute('PRAGMA journal_mode=WAL');db.execute('CREATE TABLE retained(value TEXT)')
        db.execute("INSERT INTO retained VALUES('before')")
    (source/'unchanged').write_bytes(b'unchanged fixture content')
    os.link(source/'unchanged',source/'unchanged-alias')
    (source/'deleted').write_bytes(b'owned removable fixture')
    plan={'sources':[str(source)],'sqlite_snapshots':[str(dbpath)],'excluded_rebuildable_directories':[]}
    remote='B:/vk-backups/vk-nightly-lifecycle-20261009-'+uuid.uuid4().hex
    ready=desktop("import json,os,shutil\nprint(json.dumps({'volume_device':os.stat('B:/').st_dev,'free':shutil.disk_usage('B:/').free}))")
    config={'wsl_root':'/mnt/b/'+remote[3:],'scope_sha256':identity(plan),'plan_identity':identity(plan),
            'source_scope_sha256':identity(scope(plan)),'source_prefix':str(source),'volume_device':ready['volume_device'],
            'retention_adopted':True,'capture_limit_bytes':32*1024**2,'changed_limit_bytes':16*1024**2,
            'reserve_bytes':320*1024**2,'snapshot_limit_bytes':16*1024**2,'snapshot_timeout_seconds':30,
            'readback_timeout_seconds':30,'job_timeout_seconds':120,'staging':str(local/'control'),
            'sshfs_binary':'/mnt/vk-storage/vk-runtime-backup-20261009/sshfs-tool/usr/bin/sshfs',
            'fusermount_binary':'/usr/bin/fusermount','inventoried_databases':[str(dbpath)]}
    report={'remote':remote,'local':str(local),'config':config,'production_changes':False,'schedule_enabled':False,'runs':[],'hardlink_fixture':True}
    started=time.monotonic()
    try:
        unchanged_inode=None
        for number in range(2):
            if number:
                with sqlite3.connect(dbpath) as db:db.execute("INSERT INTO retained VALUES('second')")
                (source/'deleted').unlink()
            run_started=time.monotonic();result=run_capture(config,plan,enroll_fresh=number==0)
            report['runs'].append({'result':result,'seconds':time.monotonic()-run_started})
            if not result['result']['passed']:raise ValueError(str(result))
            inode=desktop("import json,pathlib\np=pathlib.Path("+repr(remote)+");q=json.loads((p/'store/current.json').read_text());g=p/'store'/q['generation'];m=json.loads((g/'manifest.json').read_text());r=m['entries']['unchanged'];assert m['entries']['unchanged-alias']['kind']=='hardlink';print(json.dumps((g/'objects'/r['sha256']).stat().st_ino))")
            if unchanged_inode is not None and inode!=unchanged_inode:raise AssertionError('unchanged B inode not preserved')
            unchanged_inode=inode
        verify='''
import hashlib,json,pathlib,sqlite3
p=pathlib.Path(ROOT)/'store';q=json.loads((p/'current.json').read_text());g=p/q['generation']
m=json.loads((g/'manifest.json').read_text());assert m['parent'] is None
for h in {r['sha256'] for r in m['entries'].values() if r['kind']=='file'}:
 with (g/'objects'/h).open('rb') as f:
  digest=hashlib.sha256()
  for block in iter(lambda:f.read(1048576),b''):digest.update(block)
  assert digest.hexdigest()==h
with sqlite3.connect((g/'objects'/m['entries']['state.sqlite']['sha256']).as_uri()+'?mode=ro&immutable=1',uri=True) as db:
 assert db.execute('SELECT value FROM retained ORDER BY rowid').fetchall()==[('before',),('second',)]
 assert db.execute('PRAGMA integrity_check').fetchall()==[('ok',)]
assert 'deleted' not in m['entries']
assert len([x for x in p.iterdir() if x.name.startswith('generation-')])==1
assert {x.name for x in (pathlib.Path(ROOT)/'jobs').iterdir()}=={'job-scope.json','job.lock'}
files=[x for x in pathlib.Path(ROOT).rglob('*') if x.is_file()];unique={}
for x in files:s=x.stat();unique[(s.st_dev,s.st_ino)]=s.st_size
print(json.dumps({'passed':True,'independent_recovery':True,'current_generations':1,'input_archives_retained':0,
 'B_logical_file_bytes':sum(x.stat().st_size for x in files),'B_unique_inode_bytes':sum(unique.values()),'files':len(files)}))
'''
        reserve=RegisteredWorkspace.reserve_file
        def interrupted(workspace,path,size):
            if Path(path).name.endswith('.tar.zst') and size:raise ValueError('fixture MCP producer interruption')
            return reserve(workspace,path,size)
        with patch.object(RegisteredWorkspace,'reserve_file',interrupted):
            try:run_capture(config,plan)
            except ValueError as error:
                if 'producer interruption' not in str(error):raise
            else:raise AssertionError('producer interruption not exercised')
        report['producer_retry']=run_capture(config,plan)
        if not report['producer_retry']['result']['passed']:raise AssertionError('closed-producer retry failed')
        report['native_recovery']=desktop('ROOT='+repr(remote)+'\n'+verify)
        report['parent_only_SIGKILL']=parent_death_case(config,plan,local)
        report['parent_only_SIGKILL']['independent_current_recovery']=desktop('ROOT='+repr(remote)+'\n'+verify)
        report['recovery_cases']=recovery_cases(config,plan,source,verify)
        report['passed']=True
    except Exception as error:
        import traceback
        report['passed']=False;report['error']=str(error);report['fixture_traceback']=traceback.format_exc()
    report['elapsed_seconds']=time.monotonic()-started
    report['source_head']=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    report['source_sha256']={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in
        ('vk_nightly_capture_adapter.py','vk_nightly_b_job.py','vk_b_disk_capture.py','vk_nightly_generation.py','vk_nightly_lifecycle.py')}
    path=local/'acceptance.safe.json';path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2));print('RECEIPT',path,'SHA256',hashlib.sha256(path.read_bytes()).hexdigest())
    return 0 if report['passed'] else 1


if __name__=='__main__':
    from vk_nightly_capture_adapter import Resident
    popen=subprocess.Popen;call=Resident.call;mounts=[];finished=[]
    def tracked_process(command,*args,**kwargs):
        process=popen(command,*args,**kwargs)
        if Path(command[0]).name=='sshfs':mounts.append(process)
        return process
    def checked_finish(resident,action,**kwargs):
        if action=='finish':
            if not mounts or mounts[-1].returncode is None:
                raise AssertionError('actual mount transport not reaped before completion')
            finished.append(mounts[-1].pid)
        return call(resident,action,**kwargs)
    with patch('subprocess.Popen',tracked_process),patch.object(Resident,'call',checked_finish):
        raise SystemExit(main())
