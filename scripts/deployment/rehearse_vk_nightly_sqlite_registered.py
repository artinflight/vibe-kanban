"""Bounded exact-adapter diagnostic: real RO source, fresh registered B inputs.

No production adoption, current publication, schedule, permissions or cleanup.
All diagnostic files are retained. Requires the existing pinned source package.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import time
import traceback
import uuid
from unittest.mock import patch

from vk_archive_store import SSH
from vk_nightly_capture_adapter import Resident, RegisteredWorkspace, disk_snapshot, mcp_lease, allowed_sqlite
from vk_nightly_job import validate
from vk_prep_common import storage


def native_metadata(directory, name):
    code = ('import json,os,pathlib\np=pathlib.Path(' + repr(directory + '/' + name) + ')\n'
            'assert os.stat("B:/").st_dev==2360624474\n'
            'def row(p):\n s=p.stat();return {"path":str(p),"device":s.st_dev,"inode":s.st_ino,'
            '"bytes":s.st_size,"mode":oct(s.st_mode),"attributes":s.st_file_attributes}\n'
            'print(json.dumps({"file":row(p),"parent":row(p.parent)}))\n')
    result = subprocess.run(SSH, input=code, text=True, capture_output=True, timeout=30)
    if result.returncode: raise RuntimeError(result.stderr[:500])
    return json.loads(result.stdout)


def run(package, source, output, repeat, *, native_after=False, inject_failure=False, async_writes=False):
    if not 1 <= repeat <= 5: raise ValueError('one to five allocations only')
    source = source.absolute()
    if source.resolve()!=source or source.is_symlink() or source.stat().st_size > 64 * 1024**2:
        raise ValueError('diagnostic source must be canonical and at most 64MiB')
    config = json.loads((package/'nightly-production.proposed-adoption.private.json').read_text())
    plan = json.loads(Path(config['plan_path']).read_text());validate(config, plan)
    allowed_sqlite(plan,str(source))
    output = storage(output);output.mkdir(exist_ok=False)
    token = uuid.uuid4().hex
    config = {**config, 'wsl_root':'/mnt/b/vk-backups/vk-nightly-registered-diagnostic-'+token,
              'scope_sha256':hashlib.sha256(('diagnostic:'+str(source)+':'+token).encode()).hexdigest(),
              'capture_limit_bytes':512*1024**2, 'initial_changed_limit_bytes':512*1024**2,
              'initial_reserve_bytes':2*1024**3, 'snapshot_timeout_seconds':90, 'job_timeout_seconds':450,
              'enroll_fresh':True, 'recover_only':False, 'mcp_producer_lease_held':True}
    events=[];report={'source':str(source),'allocations':[], 'production_changed':False,'schedule_enabled':False,
                     'async_writes':async_writes}
    def save(): (output/'registered-adapter.private.json').write_text(json.dumps(report,indent=2)+'\n')
    connect=sqlite3.connect
    class Observed(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            events.append({'call':'execute','sql':sql})
            return super().execute(sql,*args,**kwargs)
        def backup(self, target, *args, **kwargs):
            events.append({'call':'backup','pages':kwargs.get('pages')})
            if inject_failure:
                error=sqlite3.OperationalError('explicitly injected diagnostic test failure')
                error.sqlite_errorcode=1032;error.sqlite_errorname='SQLITE_READONLY_DBMOVED'
                raise error
            return super().backup(target,*args,**kwargs)
    def observed_connect(path,*args,**kwargs):
        events.append({'call':'connect','path':str(path)})
        return connect(path,*args,factory=Observed,**kwargs)
    with connect(source.as_uri()+'?mode=ro',uri=True) as src:
        report['source_pragmas']={'journal_mode':src.execute('PRAGMA journal_mode').fetchone()[0],
                                  'page_size':src.execute('PRAGMA page_size').fetchone()[0]}
    started=time.monotonic()
    with mcp_lease(output/'producer.lock') as lease_fd:
        resident=Resident(config);mount=output/'B-input';mount.mkdir();process=None;mounted=False
        try:
            if resident.ready.get('event')!='capture_ready':raise ValueError('fixed resident not ready')
            report['resident']=resident.ready
            process=subprocess.Popen([config['sshfs_binary'],'-f','desktop:/'+resident.ready['directory'],str(mount),'-o',
                'BatchMode=yes,ConnectTimeout=15,StrictHostKeyChecking=yes,ServerAliveInterval=15,ServerAliveCountMax=3,cache=no'+
                ('' if async_writes else ',sshfs_sync')],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,pass_fds=(lease_fd,))
            deadline=time.monotonic()+30
            while True:
                if process.poll() is not None:raise ValueError('mount process exited')
                try:
                    workspace=RegisteredWorkspace(mount,resident,lease_fd=lease_fd);mounted=True;break
                except ValueError:
                    if time.monotonic()>deadline:raise TimeoutError('mount readiness')
                    time.sleep(.1)
            report['mount']=json.loads(subprocess.check_output(['findmnt','-J','-T',str(mount)]))
            original=workspace.open_new
            def observe_allocate(path):
                stream=original(path)
                info=Path(path).stat()
                allocation={'destination':str(path),'linux':{'device':info.st_dev,'inode':info.st_ino,
                    'bytes':info.st_size,'mode':oct(info.st_mode),'uid':info.st_uid},
                    'windows':None if native_after else native_metadata(resident.ready['directory'],Path(path).name),
                    'no_preopen_native_roundtrip':native_after,'calls':events}
                report['allocations'].append(allocation);save()
                return stream
            workspace.open_new=observe_allocate
            for n in range(repeat):
                events=[]
                # Capture's ordinary RO reader remains open after its transaction
                # rollback when the disk factory opens the independent RO reader.
                with connect(source.as_uri()+'?mode=ro',uri=True,check_same_thread=False) as held:
                    held.execute('PRAGMA data_version');held.execute('BEGIN')
                    held.execute('SELECT name FROM sqlite_master LIMIT 1').fetchone();held.rollback()
                    try:
                        with patch('vk_nightly_capture_adapter.sqlite3.connect',observed_connect):
                            result=disk_snapshot(source,workspace,{str(source)},maximum_bytes=64*1024**2,timeout_seconds=90)
                        report['allocations'][-1]['result']=result
                    except Exception as error:
                        report['failure']={'allocation':n,'type':type(error).__name__,'reason':str(error),
                            'traceback':traceback.format_exc(),'sqlite_errorcode':getattr(error,'sqlite_errorcode',None),
                            'sqlite_errorname':getattr(error,'sqlite_errorname',None),'last_call':events[-1] if events else None}
                        report['failure']['injected']=inject_failure
                        report['failure']['runtime_diagnostic']=getattr(error,'nightly_sqlite_diagnostic',None)
                        save();raise
                report['allocations'][-1]['post_native']=native_metadata(resident.ready['directory'],result['snapshot']);save()
            report['passed']=True
        finally:
            try:
                if mounted:subprocess.run([config['fusermount_binary'],'-u',str(mount)],check=True,timeout=30)
            finally:
                if process is not None:
                    if process.poll() is None:process.terminate()
                    try:process.wait(timeout=30)
                    except subprocess.TimeoutExpired:process.kill();process.wait()
                resident.close()
                report['elapsed_seconds']=time.monotonic()-started;save()
    print(json.dumps({'passed':report.get('passed',False),'allocations':len(report['allocations']),
                      'seconds':report['elapsed_seconds'],'receipt':str(output/'registered-adapter.private.json')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--package',type=Path,required=True)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--repeat',type=int,default=5);p.add_argument('--native-metadata-after',action='store_true')
    p.add_argument('--inject-backup-failure',action='store_true')
    p.add_argument('--async-writes',action='store_true')
    a=p.parse_args();run(a.package,a.source,a.output,a.repeat,native_after=a.native_metadata_after,
                        inject_failure=a.inject_backup_failure,async_writes=a.async_writes)
