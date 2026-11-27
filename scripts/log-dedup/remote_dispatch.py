"""Single recorded dispatch of a bounded preparer to an existing authorized host."""
import base64
import json
import os
import stat
from pathlib import Path
import subprocess
import time

from checkpoint_control import atomic, read, require
from remote_pack import digest

HOSTS = {
    'desktop': ('B:/vk-staging/vk-dedup-preparation-20261122', r'C:\Python310\python.exe'),
    'laptop-worker': ('C:/ProgramData/VibeWorker/work/dedup-preparation-20261122', r'C:\Program Files\Python314\python.exe'),
}


def quoted(value):return "'"+str(value).replace("'","''")+"'"


def powershell(host,source,timeout=30):
    require(host in HOSTS,'unqualified preparation host')
    code="$ProgressPreference='SilentlyContinue';$ErrorActionPreference='Stop';[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)\n"+source
    encoded=base64.b64encode(code.encode('utf-16le')).decode()
    return subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',host,
        'powershell.exe -NoProfile -NonInteractive -EncodedCommand '+encoded],
        capture_output=True,text=True,timeout=timeout,check=True).stdout


def copy(host,source,destination):
    subprocess.run(['scp','-C','-o','BatchMode=yes','-o','ConnectTimeout=10',str(source),
                    host+':'+destination],check=True,capture_output=True,timeout=600)


def fetch(host,source,destination):
    subprocess.run(['scp','-o','BatchMode=yes','-o','ConnectTimeout=10',host+':'+source,
                    str(destination)],check=True,capture_output=True,timeout=180)
    Path(destination).chmod(0o600)


def successful_queue_job(row,job_id):
    require(row.get('id')=='dedup-'+job_id and row.get('status')=='completed'
            and row.get('finished') and type(row.get('exit')) is int and row['exit']==0,
            'Exact successful native queue termination required')
    return row


def queue_completion(status,job_id):
    from datetime import datetime,timezone
    heartbeat=status['heartbeat']
    age=(datetime.now(timezone.utc)-datetime.fromisoformat(heartbeat['at'])).total_seconds()
    require(heartbeat['account']=='vibeworker' and heartbeat['administrator'] is False
            and -5<=age<=60,'Current standard-account worker heartbeat required')
    rows=[row for row in status['jobs'] if row['id']=='dedup-'+job_id]
    require(len(rows)<=1,'Duplicate queue identity')
    if not rows or rows[0]['status']=='running':return None
    return successful_queue_job(rows[0],job_id)


def release_copy_cache(path):
    """Drop only our durable copied transfer payload from page cache, never data."""
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        info=os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid() and info.st_nlink==1,
                'Owned transfer copy required for cache advice')
        os.fsync(fd)
        os.posix_fadvise(fd,0,0,os.POSIX_FADV_DONTNEED)
    finally:os.close(fd)


def dispatch(host,folder,source_dir,log_module):
    """No retry of a dispatched/uncertain job; callers reconcile its retained ID."""
    require(host in HOSTS,'unqualified preparation host')
    folder=Path(folder);evidence=read(folder/'SNAPSHOT.private.json',8*1024**2)
    intent=folder/'DISPATCH_INTENT.private.json'
    require(not intent.exists(),'Existing dispatch must be reconciled, never replayed')
    parent,python=HOSTS[host];remote=parent+'/'+evidence['job_id'];windows=remote.replace('/','\\')
    # Remote roots are dedicated to this task. Never modify an existing job folder.
    script=f"$p={quoted(windows)}\nif(Test-Path -LiteralPath $p){{throw 'Existing job requires reconciliation'}}\nNew-Item -ItemType Directory -Path $p | Out-Null\n"
    if host=='desktop':
        script+="$me=[Security.Principal.WindowsIdentity]::GetCurrent().Name\n& icacls.exe $p /inheritance:r /grant:r ($me+':(OI)(CI)F') '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' | Out-Null\nif($LASTEXITCODE -ne 0){throw 'Private staging ACL failed'}\n"
    powershell(host,script)
    for name in ['request.json','input.tar']:copy(host,folder/name,remote+'/'+name)
    copy(host,Path(source_dir)/'remote_pack.py',remote+'/remote_pack.py')
    copy(host,log_module,remote+'/log_dedup.py')
    hashes={name:digest(path)for name,path in [('request.json',folder/'request.json'),
            ('input.tar',folder/'input.tar'),('remote_pack.py',Path(source_dir)/'remote_pack.py'),('log_dedup.py',Path(log_module))]}
    check='\n'.join("if((Get-FileHash -Algorithm SHA256 -LiteralPath "+quoted(windows+'\\'+name)+
        ').Hash.ToLower() -ne '+quoted(value)+"){throw 'Remote transfer hash mismatch'}" for name,value in hashes.items())
    powershell(host,check)
    release_copy_cache(folder/'input.tar')
    atomic(intent,dict(at=time.time(),host=host,remote=remote,job_id=evidence['job_id'],
        request_sha256=evidence['request_sha256'],source_hashes=hashes,no_automatic_replay=True))
    args=['-B',windows+'\\remote_pack.py','--root',windows,'--request-sha256',evidence['request_sha256']]
    try:
        if host=='desktop':
            command='& '+quoted(python)+' '+ ' '.join(quoted(x)for x in args)+"\nif($LASTEXITCODE -ne 0){throw 'Preparation worker failed'}"
            powershell(host,command,timeout=3360)
        else:
            command='& vibe-worker '+ ' '.join(quoted(x)for x in ['submit','--id','dedup-'+evidence['job_id'],
                '--cwd',windows,'--timeout','3300','--',python,*args])+"\nif($LASTEXITCODE -ne 0){throw 'Worker submission was not accepted'}"
            acknowledgement=powershell(host,command)
            atomic(folder/'QUEUE_ACK.private.json',dict(at=time.time(),acknowledgement=acknowledgement))
            deadline=time.monotonic()+3360
            while True:
                status=json.loads(powershell(host,"& vibe-worker status\nif($LASTEXITCODE -ne 0){throw 'Queue status unavailable'}"))
                terminal=queue_completion(status,evidence['job_id'])
                if terminal is not None:
                    atomic(folder/'QUEUE_TERMINAL.private.json',dict(at=time.time(),job_id=evidence['job_id'],job=terminal))
                    break
                require(time.monotonic()<deadline,'Remote completion uncertain; do not replay')
                time.sleep(10)
        fetch(host,remote+'/RESULT.json',folder/'RESULT.json')
        result=json.loads((folder/'RESULT.json').read_bytes())
        require(result['complete'] and result['job_id']==evidence['job_id'] and
                result['request_sha256']==evidence['request_sha256'],'Remote receipt differs')
        fetch(host,remote+'/output.tar',folder/'output.tar')
        require(digest(folder/'output.tar')==result['output_sha256'],'Returned output checksum differs')
        release_copy_cache(folder/'output.tar')
        atomic(folder/'RECEIVED.private.json',dict(at=time.time(),host=host,remote=remote,
            job_id=evidence['job_id'],output_sha256=result['output_sha256']))
        return result
    except BaseException as error:
        atomic(folder/'DISPATCH_UNCERTAIN.private.json',dict(at=time.time(),type=type(error).__name__,
            job_id=evidence['job_id'],host=host,remote=remote,never_replay_without_reconciliation=True,
            transport_diagnostic=str(getattr(error,'stderr',''))[:8192]))
        raise
