"""Bounded lookahead preparation; the existing converter alone publishes history."""
from concurrent.futures import Future, ThreadPoolExecutor
import fcntl
import json
import os
from pathlib import Path
import signal
import time

from checkpoint_control import atomic, read, require
from controlled_conversion import batch_folder
import remote_dispatch
from remote_pack import digest, MAX_BYTES
import remote_preparation


def retire_payloads(folder):
    """Only exact new transferred copies, after verified archive import and worker exit."""
    folder=Path(folder);evidence=read(folder/'SNAPSHOT.private.json',8*1024**2)
    imported=read(folder/'IMPORTED.private.json');receipt=read(folder/'RECEIVED.private.json')
    intent=read(folder/'DISPATCH_INTENT.private.json');result=json.loads((folder/'RESULT.json').read_bytes())
    require(imported['all_bodies_verified'] and imported['job_id']==receipt['job_id']==intent['job_id']==evidence['job_id'],
            'Verified imported archive and exact dispatch required')
    # Laptop cleanup requires an accepted queue-terminal receipt as well; no
    # assumption that a result file alone proves its owning job has exited.
    if intent['host']=='laptop-worker':
        terminal=read(folder/'QUEUE_TERMINAL.private.json')
        require(terminal['job_id']==evidence['job_id'],'Remote terminal receipt differs')
        remote_dispatch.successful_queue_job(terminal['job'],evidence['job_id'])
    pairs={'input.tar':intent['source_hashes']['input.tar'],'output.tar':result['output_sha256']}
    remote=intent['remote'].replace('/','\\');code=[]
    for name,expected in pairs.items():
        path=remote+'\\'+name
        code.append("$p="+remote_dispatch.quoted(path)+"\n$f=[IO.File]::Open($p,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)\ntry {$sha=[Security.Cryptography.SHA256]::Create();$h=([BitConverter]::ToString($sha.ComputeHash($f))).Replace('-','').ToLower();if($h -ne "+remote_dispatch.quoted(expected)+"){throw 'Payload identity differs'}} finally {$f.Dispose();if($sha){$sha.Dispose()}}\nRemove-Item -LiteralPath $p -ErrorAction Stop")
    remote_dispatch.powershell(intent['host'],'\n'.join(code),timeout=60)
    old=signal.getsignal(signal.SIGIO)
    def consumer(*_):raise ValueError('New preparation payload consumer; preserve remaining copies')
    signal.signal(signal.SIGIO,consumer);released=0
    try:
        for name,expected in pairs.items():
            p=folder/name;before=p.lstat();require(before.st_uid==os.getuid() and before.st_nlink==1,'owned copied payload required')
            fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
            try:
                require(digest(p)==expected,'Copied payload changed')
                require((os.fstat(fd).st_dev,os.fstat(fd).st_ino)==(before.st_dev,before.st_ino),'Copied payload inode changed')
                fcntl.fcntl(fd,fcntl.F_SETOWN,os.getpid());fcntl.fcntl(fd,fcntl.F_SETLEASE,fcntl.F_WRLCK)
                fingerprint=lambda st:(st.st_dev,st.st_ino,st.st_mode,st.st_size,st.st_mtime_ns,st.st_ctime_ns,st.st_uid,st.st_nlink)
                require(fingerprint(p.lstat())==fingerprint(before)==fingerprint(os.fstat(fd)),'Copied payload path or bytes changed')
                p.unlink();released+=before.st_blocks*512
            finally:
                try:fcntl.fcntl(fd,fcntl.F_SETLEASE,fcntl.F_UNLCK)
                finally:os.close(fd)
        fd=os.open(folder,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
    finally:signal.signal(signal.SIGIO,old)
    atomic(folder/'PAYLOADS_RETIRED.private.json',dict(at=time.time(),job_id=evidence['job_id'],
        local_allocated_bytes=released,exact_remote_payloads_removed=list(pairs),originals_and_archives_preserved=True))


class PreparationPool:
    def __init__(self,worker,selection,root,config,override=None):
        self.worker,self.selection,self.root=worker,selection,Path(root)
        self.config,self.override=config,override
        self.folder=Path(config['preparations']);self.folder.mkdir(mode=0o700,exist_ok=True)
        self.hosts=list(config['hosts']);require(len(self.hosts)==len(set(self.hosts)) and 1<=len(self.hosts)<=2,'bounded unique preparation hosts required')
        require(all(host in remote_dispatch.HOSTS for host in self.hosts),'unqualified host')
        self.executor=ThreadPoolExecutor(max_workers=len(self.hosts),thread_name_prefix='dedup-copy-preparation')
        self.jobs={};self.busy={};self.disabled=set()
        self.by_names={tuple(row['names']):i for i,row in enumerate(selection['batches'])}
        # A checkpoint handoff may retain already-returned, terminal preparation.
        # Adopt exact receipts, never dispatch that work again.
        for row in config.get('adopt_completed',[]):
            n=row['batch'];host=row['host'];folder=Path(row['folder'])
            require(type(n)is int and 0<=n<len(selection['batches']) and host in self.hosts
                    and host not in self.busy and n not in self.jobs,'Invalid preparation handoff')
            snapshot=read(folder/'SNAPSHOT.private.json',8*1024**2)
            intent=read(folder/'DISPATCH_INTENT.private.json');receipt=read(folder/'RECEIVED.private.json')
            result=read(folder/'RESULT.json',8*1024**2)
            require(snapshot['workspace']==selection['batches'][n]['workspace']
                    and [f['path']for f in snapshot['files']]==selection['batches'][n]['names']
                    and snapshot['job_id']==intent['job_id']==receipt['job_id']==result['job_id']
                    and host==intent['host']==receipt['host'] and result['complete']
                    and not(folder/'IMPORTED.private.json').exists()
                    and digest(folder/'output.tar')==result['output_sha256']==receipt['output_sha256'],
                    'Returned preparation does not match handoff')
            if host=='laptop-worker':
                terminal=read(folder/'QUEUE_TERMINAL.private.json')
                require(terminal['job_id']==snapshot['job_id'],'Terminal queue handoff differs')
                remote_dispatch.successful_queue_job(terminal['job'],snapshot['job_id'])
            future=Future();future.set_result(result)
            self.jobs[n]=dict(host=host,folder=folder,future=future);self.busy[host]=n

    def status(self):
        atomic(self.folder/'status.json',dict(at=time.time(),hosts=self.hosts,disabled=sorted(self.disabled),
            jobs={str(n):{'host':j['host'],'folder':str(j['folder']),'finished':j['future'].done(),
                         'consumed':j.get('consumed',False)}for n,j in self.jobs.items()}))

    def prepare_remote(self,number,host,folder):
        row=self.selection['batches'][number]
        self.worker.readers.check()
        # Two input/output payloads per admitted host plus the existing SSD floor.
        reserve=3*1024**3+len(self.hosts)*2*MAX_BYTES
        fs=os.statvfs('/mnt/vk-storage');require(fs.f_bavail*fs.f_frsize>=reserve,'Lookahead scratch admission refused')
        try:
            remote_preparation.snapshot(self.worker.C['source_root'],row['names'],row['workspace'],folder,self.worker.readers.check)
            return remote_dispatch.dispatch(host,folder,self.config['source_dir'],self.config['log_module'])
        except Exception as error:
            atomic(self.folder/('preparation-failed-'+str(number)+'.json'),dict(at=time.time(),batch=number,
                host=host,type=type(error).__name__,dispatch_recorded=(folder/'DISPATCH_INTENT.private.json').exists(),
                no_automatic_redispatch=True,converter_can_prepare_locally=True))
            raise

    def schedule(self,number):
        for host in self.hosts:
            if host in self.disabled or host in self.busy:continue
            # Skip small batches: measured remote setup/transfer exceeds their
            # local preparation cost. Two-batch lookahead overlaps substantial work.
            candidates=[n for n in range(number+2,min(number+5,len(self.selection['batches'])))
                if n not in self.jobs and self.selection['batches'][n]['raw_and_sidecar_bytes']>=64*1024**2
                and not batch_folder(self.root,n,self.override).exists()]
            if not candidates:continue
            n=candidates[0];folder=self.folder/('batch-'+str(n).zfill(4))
            require(not folder.exists(),'Prior preparation requires reconciliation; never redispatch')
            future=self.executor.submit(self.prepare_remote,n,host,folder)
            self.jobs[n]=dict(host=host,folder=folder,future=future);self.busy[host]=n
        self.status()

    def payload(self,folder,names,workspace):
        number=self.by_names.get(tuple(names));job=self.jobs.get(number)
        if job is None:return None
        require(self.selection['batches'][number]['workspace']==workspace,'Prepared workspace differs')
        try:
            job['future'].result()  # Only this exact finite already-dispatched job.
        except Exception as error:
            # Remote copies have no production authority. A failed optional
            # preparer is disabled; ordinary qualified local preparation continues.
            self.disabled.add(job['host']);self.busy.pop(job['host'],None)
            atomic(self.folder/('unavailable-'+str(number)+'.json'),dict(at=time.time(),batch=number,
                host=job['host'],type=type(error).__name__,no_redispatch=True,local_preparation_fallback=True))
            job['consumed']=True;self.status();return None
        snapshot=read(job['folder']/'SNAPSHOT.private.json',8*1024**2)
        require(snapshot['workspace']==workspace and [r['path']for r in snapshot['files']]==list(names),
                'Prepared input selection differs')
        plan=remote_preparation.import_archive(job['folder'],Path(folder)/'archive',self.worker.readers.check)
        try:retire_payloads(job['folder'])
        except Exception as error:
            self.disabled.add(job['host'])
            atomic(job['folder']/'PAYLOAD_RETIREMENT_PENDING.private.json',dict(at=time.time(),type=type(error).__name__,
                archive_verified=True,host_disabled_to_bound_scratch=True))
        job['consumed']=True;self.busy.pop(job['host'],None);self.status()
        self.worker.progress('remote_preparation_independently_verified',dict(batch=number,host=job['host'],files=len(plan['files'])))
        return plan

    def close(self):
        self.executor.shutdown(wait=True,cancel_futures=True);self.status()
