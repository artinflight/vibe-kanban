"""Fixed MCP online capture into resident-registered B files; no local payload.

Only the fresh nightly attempt's B directory is mounted. Existing Desktop SSH
host verification is retained. The caller owns/reaps producers and the kernel
MCP lease before the resident accepts completion; no routine agent invocation.
"""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import sqlite3
import struct
import stat
import subprocess
import threading
import time
import traceback
import uuid

from vk_archive_stream import StreamingArchive, packet
from vk_b_disk_capture import capture
from vk_b_disk_snapshot import metadata
from vk_candidate_direct_b import DirectBProvider
from vk_change_journal import Journal, scope
from vk_nightly_generation import MAX_INDEX
from vk_prep_common import identity, storage


# Windows bridge streams existing SSH stdio into the existing UID1000 WSL
# process. No install, credentials, account changes or root operation.
WSL_LOADER = '''import hashlib,json,struct,sys,types
s=sys.stdin.buffer
h=s.read(4)
if len(h)!=4:raise ValueError('bootstrap header missing')
n=struct.unpack('!I',h)[0]
if n>1048576:raise ValueError('bootstrap bound exceeded')
b=s.read(n)
if len(b)!=n:raise ValueError('bootstrap truncated')
v=json.loads(b)
for name,source,expected in v['sources']:
 if name not in ('vk_nightly_generation','vk_nightly_lifecycle','vk_nightly_b_job'):raise ValueError('unknown fixed handler')
 if hashlib.sha256(source.encode()).hexdigest()!=expected:raise ValueError('handler hash mismatch')
 m=types.ModuleType(name);sys.modules[name]=m;exec(compile(source,name+'.py','exec'),m.__dict__)
raise SystemExit(sys.modules['vk_nightly_b_job'].run(v['config']))
'''


def remote_command():
    import base64
    loader=base64.b64encode(WSL_LOADER.encode()).decode()
    bridge="import subprocess,sys;raise SystemExit(subprocess.call(['wsl.exe','-d','VK-Candidate-20261009','--exec','setpriv','--reuid','1000','--regid','1000','--clear-groups','python3','-B','-S','-c',\"import base64;exec(base64.b64decode('"+loader+"'))\"],stdin=sys.stdin.buffer,stdout=sys.stdout.buffer,stderr=sys.stderr.buffer))"
    code=base64.b64encode(bridge.encode()).decode()
    return ['ssh','-T','-o','BatchMode=yes','-o','ConnectTimeout=15','-o','StrictHostKeyChecking=yes',
            '-o','ControlMaster=no','-o','ControlPath=none','-o','ServerAliveInterval=15',
            '-o','ServerAliveCountMax=3','desktop','python -c "import base64;exec(base64.b64decode(\''+code+'\'))"']


class Resident:
    def __init__(self,config):
        self.process=subprocess.Popen(remote_command(),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        self.lock=threading.Lock();self.timeout=config['job_timeout_seconds'];self.config=config
        sources=[]
        for name in ('vk_nightly_generation','vk_nightly_lifecycle','vk_nightly_b_job'):
            source=Path(__file__).with_name(name+'.py').read_text()
            sources.append((name,source,hashlib.sha256(source.encode()).hexdigest()))
        raw=json.dumps({'config':config,'sources':sources}).encode()
        if len(raw)>1048576:raise ValueError('source bundle exceeded bounded bootstrap')
        try:
            self.process.stdin.write(struct.pack('!I',len(raw))+raw);self.process.stdin.flush()
            self.ready=self.response()
            self.binding=self.ready.get('binding')
        except BaseException:
            self.close();raise
    def response(self,timeout=None):
        if not select.select([self.process.stdout],[],[],self.timeout if timeout is None else timeout)[0]:raise TimeoutError('B resident response timed out')
        line=self.process.stdout.readline(16385)
        if not line.endswith(b'\n') or len(line)>16384:raise ValueError('B resident response missing or oversized')
        return json.loads(line)
    def call(self,action,*,response_timeout=None,**kwargs):
        with self.lock:
            packet(self.process.stdin,{'action':action,'binding':self.binding,**kwargs})
            return self.response(timeout=response_timeout)
    def close(self):
        if not self.process.stdin.closed:self.process.stdin.close()
        try:self.process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.process.kill();self.process.wait()
        self.process.stdout.close()


class RegisteredWorkspace:
    def __init__(self,root,resident,*,lease_fd=None):
        self.root=Path(root);self.resident=resident;self.names=set();self.bytes=0
        self.lease_fd=lease_fd
        self.limit=resident.config['capture_limit_bytes'];self.deadline=time.monotonic()+resident.timeout
        self.sealed={};self.reservations={};self.capacity_lock=threading.Lock();self.checked_root(root)
    def producer(self,command,**kwargs):
        # Share the LOCKED open-file description, never unlock it explicitly.
        # Parent SIGKILL cannot release the lease while an owned child lives.
        return subprocess.Popen(command,pass_fds=() if self.lease_fd is None else (self.lease_fd,),**kwargs)
    def checked_root(self,root):
        if Path(root)!=self.root:raise ValueError('workspace outside live input directory')
        mounted=json.loads(subprocess.check_output(['findmnt','-J','-T',str(root)]))['filesystems'][0]
        if (mounted['target']!=str(root) or mounted['fstype']!='fuse.sshfs'
                or mounted['source']!='desktop:/'+self.resident.ready['directory']):
            raise ValueError('live input is not the pinned fresh Desktop B mount')
        return self.root
    def remaining(self):
        if time.monotonic()>self.deadline:raise TimeoutError('capture exceeded fixed job deadline')
        return self.limit-sum(row['bytes'] for row in self.sealed.values())
    def reserve_file(self,path,size):
        with self.capacity_lock:
            self.remaining()
            prior=self.reservations.get(Path(path).name,0)
            if sum(self.reservations.values())-prior+max(prior,size)>self.limit:
                raise ValueError('aggregate registered B input bound exceeded')
            self.reservations[Path(path).name]=max(prior,size)
    def open_new(self,path):
        path=Path(path);self.checked_root(path.parent)
        if path.name in self.names:raise ValueError('input path is immutable')
        if self.resident.call('allocate',name=path.name)!={'allocated':path.name}:raise ValueError('B input not registered')
        self.names.add(path.name)
        fd=os.open(path,os.O_WRONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        if os.fstat(fd).st_size!=0:os.close(fd);raise ValueError('allocated input substituted')
        stream=os.fdopen(fd,'wb');workspace=self
        class BoundedWriter:
            def __enter__(self):return self
            def __exit__(self,*args):stream.close()
            def __getattr__(self,key):return getattr(stream,key)
            def write(self,data):
                workspace.reserve_file(path,stream.tell()+len(data))
                return stream.write(data)
        return BoundedWriter()
    def seal(self,path,*,sqlite=False):
        self.checked_root(Path(path).parent)
        value=self.resident.call('seal',name=Path(path).name,sqlite_integrity=sqlite)
        if sqlite and value.get('integrity')!='ok':raise ValueError('independent B SQLite integrity proof missing')
        if value.get('sealed')!=Path(path).name:raise ValueError('B input seal failed')
        self.sealed[Path(path).name]=value
        self.remaining()
        return value
    def inspect_failure(self,path):
        path=Path(path);self.checked_root(path.parent)
        if path.name not in self.names:raise ValueError('diagnostic input was not registered')
        value=self.resident.call('inspect',name=path.name,response_timeout=20)
        if value.get('name')!=path.name or value.get('native',{}).get('metadata_only') is not True:
            raise ValueError('registered input metadata response missing; original failure preserved')
        return value
    def save_json(self,path,value):
        data=(json.dumps(value,indent=2,sort_keys=True)+'\n').encode()
        if len(data)>MAX_INDEX or len(data)>self.remaining():raise ValueError('bounded B metadata limit exceeded')
        with self.open_new(path) as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        return self.seal(path)
    def save_proof(self,path,value):
        # Compact streaming JSON avoids duplicating a host-scale encoded buffer.
        total=0
        with self.open_new(path) as stream:
            for piece in json.JSONEncoder(separators=(',',':')).iterencode(value):
                data=piece.encode();total+=len(data)
                if total>MAX_INDEX:raise ValueError('bounded proof metadata exceeded')
                stream.write(data)
            stream.flush();os.fsync(stream.fileno())
        return self.seal(path)
    def mirror(self,source):
        if not isinstance(source,StreamingArchive):
            # Capture has already registered and sealed its recovery descriptor.
            value=self.sealed[Path(source).name]
            return {'desktop_verified':True,'desktop_directory':self.resident.ready['directory'],
                    'name':Path(source).name,'bytes':value['bytes'],'sha256':value['sha256']}
        compressor=None;producer=None;errors=[]
        target=self.root/source.name;checksum=hashlib.sha256();size=0
        try:
            with self.open_new(target) as out:
                compressor=self.producer(['zstd','-T1','-3','-c'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
                def produce():
                    try:source.produce(compressor.stdin)
                    except BaseException as error:errors.append(error);compressor.kill()
                    finally:
                        try:compressor.stdin.close()
                        except OSError:pass
                producer=threading.Thread(target=produce,name='nightly-owned-tar',daemon=True);producer.start()
                while block:=compressor.stdout.read(1048576):
                    size+=len(block)
                    allowance=self.remaining()
                    if size>allowance:
                        raise ValueError('bounded registered B archive exceeded reservation: '
                            f'archive attempted {size} bytes; archive allowance {allowance}; '
                            f'capture limit {self.limit}; sealed input bytes {self.limit-allowance}')
                    out.write(block);checksum.update(block)
                producer.join(timeout=30)
                if producer.is_alive():raise ValueError('owned capture producer has not completed')
                if errors:raise errors[0]
                if compressor.wait(timeout=30)!=0:raise ValueError('owned compressor failed')
                out.flush();os.fsync(out.fileno())
            value=self.seal(target);source.sha256=checksum.hexdigest();source.bytes=size
            if (value['bytes'],value['sha256'])!=(size,source.sha256):raise ValueError('B archive readback differs')
            return {'desktop_verified':True,'desktop_directory':self.resident.ready['directory'],'name':source.name,
                    'bytes':size,'sha256':source.sha256,'direct_stream':True}
        finally:
            if compressor:
                if compressor.poll() is None:compressor.kill()
                compressor.wait()
                for stream in (compressor.stdin,compressor.stdout):
                    if not stream.closed:stream.close()
            if producer:
                producer.join(timeout=30)
                if producer.is_alive():raise ValueError('producer still active; no completion attestation')


def validate_socket_exclusions(paths):
    for raw in paths:
        try:info=Path(raw).lstat()
        except FileNotFoundError:continue
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid!=os.getuid():
            raise ValueError('proposed socket omission changed type/owner; preserve and review scope')


def allowed_sqlite(plan,raw):
    # New DBs inside already approved roots are routine scope members. The
    # observed DB list sizes the proposal; it must not become a recurring grant.
    from vk_rolling_backup import Exclusions
    source=Path(raw)
    if not source.is_absolute() or source.resolve()!=source or Exclusions(plan)(source) or not any(
            source==Path(root).resolve() or source.is_relative_to(Path(root).resolve()) for root in plan['sources']):
        raise ValueError('SQLite source outside approved canonical backup roots')
    return {str(source)}


def disk_snapshot(source,workspace,allowed_sources,*,maximum_bytes,timeout_seconds):
    """Online SQLite backup API, bounded pages/cache, PRIVATE destination on B.

    Destination journaling is OFF only on this newly registered disposable
    snapshot, which is unaccepted until integrity/hash checks succeed. Live
    source journal/permissions are never changed; failures retain partials.
    """
    source=Path(source)
    if str(source) not in allowed_sources or source.is_symlink() or not source.is_file():raise ValueError('DB outside inventoried scope')
    before=metadata(source);started=time.monotonic();target=workspace.root/('sqlite-consistent-'+uuid.uuid4().hex+'.sqlite')
    with workspace.open_new(target):pass
    src=dst=None;stage='source.connect';page_size=None
    try:
        src=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)
        stage='source.temp_store';src.execute('PRAGMA temp_store=MEMORY')
        stage='source.cache_size';src.execute('PRAGMA cache_size=-8192')
        stage='source.mmap_size';src.execute('PRAGMA mmap_size=0')
        stage='source.begin';src.execute('BEGIN')
        stage='source.schema_read';src.execute('SELECT name FROM sqlite_master LIMIT 1').fetchone()
        stage='source.page_size'
        page_size=src.execute('PRAGMA page_size').fetchone()[0]
        def progress(status,remaining,pages):
            if pages*page_size>maximum_bytes:raise ValueError('bounded B SQLite image exceeds reservation')
            workspace.reserve_file(target,pages*page_size)
            if time.monotonic()-started>timeout_seconds:raise TimeoutError('SQLite snapshot deadline exceeded')
        stage='source.page_count';progress(None,None,src.execute('PRAGMA page_count').fetchone()[0])
        stage='destination.connect';dst=sqlite3.connect(target)
        stage='destination.temp_store';dst.execute('PRAGMA temp_store=MEMORY')
        stage='destination.cache_size';dst.execute('PRAGMA cache_size=-8192')
        stage='destination.mmap_size';dst.execute('PRAGMA mmap_size=0')
        stage='destination.journal_mode';dst.execute('PRAGMA journal_mode=OFF')
        stage='destination.progress_handler'
        dst.set_progress_handler(lambda: int(time.monotonic()-started>timeout_seconds),4096)
        stage='source.backup(destination)'
        src.backup(dst,pages=1024,progress=progress)
        stage='destination.close/source.rollback'
        dst.close();dst=None;src.rollback();src.close();src=None
        # Private-image integrity/full hash are independently checked by the
        # native B reader after SQLite destination close; no FUSE SQLite reopen.
        stage='native.seal';row=workspace.seal(target,sqlite=True)
        return {'source':str(source),'snapshot':target.name,'mount_root':str(workspace.root),'bytes':row['bytes'],
                'sha256':row['sha256'],'source_metadata_before':before,'backup_api_consistent_image':True,
                'physical_b_verified':True,'integrity':'ok','online_preparation_only':True,'writer_fenced':False,
                'local_snapshot_payload_bytes':0,'seconds':time.monotonic()-started}
    except sqlite3.Error as error:
        # Failure-only, metadata-only diagnostics. Preserve the ORIGINAL error,
        # transaction/backup semantics and unaccepted partial; never retry/seal.
        value={'source':str(source),'destination':str(target),'parent':str(target.parent),
               'stage':stage,'sqlite_errorcode':getattr(error,'sqlite_errorcode',None),
               'sqlite_errorname':getattr(error,'sqlite_errorname',None),'traceback':traceback.format_exc(),
               'source_page_size':page_size,'source_journal_mode':None,'diagnostic_errors':[]}
        for name,path in [('source_identity',source),('destination_identity',target),('parent_identity',target.parent)]:
            try:
                info=path.lstat();value[name]={'device':info.st_dev,'inode':info.st_ino,'bytes':info.st_size,
                    'mode':oct(info.st_mode),'uid':info.st_uid,'gid':info.st_gid,'mtime_ns':info.st_mtime_ns}
            except Exception as secondary:value['diagnostic_errors'].append({'operation':name,'type':type(secondary).__name__})
        if src is not None:
            try:value['source_journal_mode']=src.execute('PRAGMA journal_mode').fetchone()[0]
            except Exception as secondary:value['diagnostic_errors'].append({'operation':'source.journal_mode','type':type(secondary).__name__})
        try:value['registered_destination']=workspace.inspect_failure(target)
        except Exception as secondary:value['diagnostic_errors'].append({'operation':'registered_destination','type':type(secondary).__name__})
        error.nightly_sqlite_diagnostic=value
        raise
    finally:
        if dst:dst.close()
        if src:src.close()


@contextmanager
def mcp_lease(path):
    fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK,0o600)
    info=os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid():
        os.close(fd);raise ValueError('MCP producer lease is not an owned regular file')
    with os.fdopen(fd,'a+b') as stream:
        try:fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise BlockingIOError('MCP producer lease still held by parent or inherited owned child; defer B reconciliation') from error
        # close() only: LOCK_UN would also unlock the children's shared lease.
        yield stream.fileno()


def run_capture(config,plan,*,enroll_fresh=False,recover_only=False):
    validate_socket_exclusions(config.get('socket_exclusions',[]))
    staging=storage(config['staging']);staging.mkdir(parents=True,exist_ok=True)
    with mcp_lease(staging/'producer.lock') as lease_fd:
        resident=Resident({**config,'enroll_fresh':enroll_fresh,'recover_only':recover_only,'mcp_producer_lease_held':True})
        mount=staging/('B-input-'+uuid.uuid4().hex);mounted=False;mount_process=None
        try:
            if resident.ready['event']=='complete':return resident.ready
            if resident.ready.get('event')!='capture_ready':raise ValueError('B resident not prepared')
            mount.mkdir()
            mount_process=subprocess.Popen([config['sshfs_binary'],'-f','desktop:/'+resident.ready['directory'],str(mount),'-o',
                'BatchMode=yes,ConnectTimeout=15,StrictHostKeyChecking=yes,ServerAliveInterval=15,ServerAliveCountMax=3,cache=no,sshfs_sync'],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,pass_fds=(lease_fd,))
            ready_deadline=time.monotonic()+30
            while True:
                if mount_process.poll() is not None:raise ValueError('owned B mount process failed')
                try:
                    workspace=RegisteredWorkspace(mount,resident,lease_fd=lease_fd);mounted=True;break
                except ValueError:
                    if time.monotonic()>ready_deadline:raise TimeoutError('owned B mount readiness timed out')
                    time.sleep(.1)
            journal=Journal(plan)
            try:
                for raw in plan['sources']:journal.tree(raw)
                journal.ready=True
                result=capture(plan,mount,journal.report,workspace.mirror,parent=None,publish=workspace.mirror,
                    max_snapshot_bytes=1,disk_snapshot=lambda raw:disk_snapshot(raw,workspace,allowed_sqlite(plan,raw),
                        maximum_bytes=config['snapshot_limit_bytes'],timeout_seconds=config['snapshot_timeout_seconds']),
                    disk_inventory_root=mount,workspace=workspace)
            finally:journal.close()
            provider=DirectBProvider(config['scope_sha256'],[str(Path(raw).relative_to(config['source_prefix'])) for raw in result['databases']],
                                     metadata_budget_bytes=MAX_INDEX)
            capture_id=resident.binding['candidate']
            provider.register(capture_id,result,identity(plan),identity(scope(plan)),config['source_prefix'],origin_root_binding='nightly-current-source-inventory')
            proof=provider.verify(capture_id)
            validate_socket_exclusions(config.get('socket_exclusions',[]))
            # Carry only the verified index; B replay maps authenticated tar
            # headers itself, avoiding another host-scale path/location vector.
            descriptor={**result,'nightly_source_prefix':config['source_prefix']}
            payload={'result':descriptor,'proof':proof,'capture_id':capture_id}
            sealed=workspace.save_proof(mount/'nightly-proof.json',payload)
            # All SQLite readers, tar/zstd children and verification channels have
            # finished. Unmount the input before the B resident can publish/retire.
            subprocess.run([config['fusermount_binary'],'-u',str(mount)],check=True,timeout=30);mounted=False
            # Reap the foreground mount/SFTP transport before attesting producer
            # completion, rather than waiting until after B publication.
            try:mount_process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                mount_process.kill();mount_process.wait()
                raise ValueError('mount transport failed to finish; no completion attestation')
            mount_process=None
            complete=resident.call('finish',producer_closed=True,proof_name='nightly-proof.json',proof_sha256=sealed['sha256'])
            if complete.get('event')!='complete':raise ValueError('B lifecycle completion missing')
            return complete
        finally:
            try:
                if mounted:
                    subprocess.run([config['fusermount_binary'],'-u',str(mount)],check=True,timeout=30)
            finally:
                try:
                    if mount_process is not None:
                        if mount_process.poll() is None:mount_process.terminate()
                        try:mount_process.wait(timeout=30)
                        except subprocess.TimeoutExpired:mount_process.kill();mount_process.wait()
                finally:resident.close()
