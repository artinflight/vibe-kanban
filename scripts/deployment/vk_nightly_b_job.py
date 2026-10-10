"""Fixed unprivileged WSL B job; stdin protocol, never a shell/command broker.

Authenticated MCP code owns source inspection/capture. This handler registers
B inputs before writing and accepts completion only for its exact live attempt.
Same-account callbacks are operational controls, not a root security boundary.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import subprocess
import sys
import tarfile
import time

from vk_nightly_generation import MAX_INDEX, NightlyStore, encoded, regular, digest_stream
from vk_nightly_lifecycle import NightlyJob, sync_directory


MAX_CONTROL = 16384
WINDOWS_INPUT_METADATA = r'''
import json,os,pathlib,stat,sys
r=json.load(sys.stdin);assert os.stat('B:/').st_dev==r['volume_device']
p=pathlib.Path(r['path'])
def row(p):
 s=p.lstat();assert not s.st_file_attributes & 0x400
 return {'path':str(p),'device':s.st_dev,'inode':s.st_ino,'bytes':s.st_size,
         'mode':oct(s.st_mode),'Windows_attributes':s.st_file_attributes}
assert stat.S_ISREG(p.lstat().st_mode)
print(json.dumps({'file':row(p),'parent':row(p.parent),'metadata_only':True}))
'''
WINDOWS_READBACK = r'''
import hashlib,json,os,pathlib,sqlite3,sys
r=json.load(sys.stdin)
assert os.stat('B:/').st_dev==r['volume_device'],'B volume changed'
p=pathlib.Path(r['folder']);manifest_bytes=(p/'manifest.json').read_bytes();m=json.loads(manifest_bytes)
assert hashlib.sha256(manifest_bytes).hexdigest()==r['manifest_sha256']
assert m['scope_sha256']==r['scope'] and m['generation']==p.name
for h in {x['sha256'] for x in m['entries'].values() if x['kind']=='file'}:
 with (p/'objects'/h).open('rb') as f:
  before=os.fstat(f.fileno());digest=hashlib.sha256()
  for b in iter(lambda:f.read(1048576),b''):digest.update(b)
  after=os.fstat(f.fileno())
 assert digest.hexdigest()==h and (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)
for raw in r['databases']:
 key=pathlib.PurePosixPath(raw).relative_to(r['source_prefix']).as_posix()
 row=m['entries'][key];assert row['kind']=='file'
 f=p/'objects'/row['sha256']
 with sqlite3.connect(f.as_uri()+'?mode=ro&immutable=1',uri=True) as db:
  assert db.execute('PRAGMA integrity_check').fetchall()==[('ok',)]
print(json.dumps({'physical_b_verified':True,'generation':m['generation'],
 'scope_sha256':m['scope_sha256'],'manifest_sha256':hashlib.sha256(manifest_bytes).hexdigest()}))
'''


WINDOWS_SQLITE_INPUT = r"""
import hashlib,json,os,pathlib,sqlite3,sys
r=json.load(sys.stdin);assert os.stat('B:/').st_dev==r['volume_device']
p=pathlib.Path(r['path'])
with p.open('rb') as stream:
 before=os.fstat(stream.fileno());h=hashlib.sha256()
 for block in iter(lambda:stream.read(1048576),b''):h.update(block)
 after=os.fstat(stream.fileno())
assert before.st_size==r['bytes'] and h.hexdigest()==r['sha256']
assert (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)
with sqlite3.connect(p.as_uri()+'?mode=ro&immutable=1',uri=True) as db:
 assert db.execute('PRAGMA integrity_check').fetchall()==[('ok',)]
assert (p.stat().st_dev,p.stat().st_ino,p.stat().st_size,p.stat().st_mtime_ns)==(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)
print(json.dumps({'sha256':h.hexdigest(),'bytes':before.st_size,'integrity':'ok'}))
"""


def receive(stream):
    def exact(n):
        chunks=[]
        while n:
            block=stream.read(n)
            if not block:raise EOFError('MCP producer channel closed; preserve registered inputs')
            chunks.append(block);n-=len(block)
        return b''.join(chunks)
    size=struct.unpack('!I',exact(4))[0]
    if size>MAX_CONTROL:raise ValueError('oversized fixed-job control packet')
    return json.loads(exact(size))


def emit(value):
    data=json.dumps(value,separators=(',',':'))
    if len(data.encode())>MAX_CONTROL:raise ValueError('oversized job response')
    print(data,flush=True)


class LocalVerifiedProvider:
    """Authenticated, source-pinned MCP provider proof; bounded B-local replay.

    The full reviewed DirectBProvider checks have completed on MCP. This fixed
    adapter never accepts a user-built receipt as independent authorization.
    Input hashes/identities and live completion are checked by the resident job.
    """
    def __init__(self, folder, value, config):
        self.folder,self.value=folder,value
        result=value['result'];proof=value['proof']
        if (result.get('parent') is not None or not result.get('passed') or not result.get('direct_stream')
                or proof.get('fixture_only') is not False or proof.get('full_current_state') is not True
                or proof.get('scope_sha256')!=config['scope_sha256']
                or result.get('plan_sha256')!=config['plan_identity']
                or result.get('scope_sha256')!=config['source_scope_sha256']
                or result.get('nightly_source_prefix')!=config['source_prefix']
                or proof.get('capture_id')!=value['capture_id']):
            raise ValueError('capture proof does not match pinned live scope')
        self.records={value['capture_id']:{'result':result}}
        self.archive=folder/result['archive']
        if self.archive.parent!=folder:raise ValueError('unsafe local archive selector')
        self.verify(value['capture_id'])

    def verify(self,capture_id):
        if capture_id!=self.value['capture_id']:raise ValueError('wrong live capture')
        with regular(self.archive) as stream:
            if (os.fstat(stream.fileno()).st_size!=self.value['result']['receipt']['bytes']
                    or digest_stream(stream)!=self.value['result']['receipt']['sha256']):
                raise ValueError('registered B archive changed')
        return self.value['proof']

    @contextmanager
    def file_members(self,capture_id,selected):
        self.verify(capture_id)
        proof=self.value['proof'];result=self.value['result']
        prefix=PurePosixPath(result['nightly_source_prefix'])
        snapshots={'payload/'+row['path']:str(PurePosixPath(raw).relative_to(prefix))
                   for raw,row in result['sqlite_snapshots'].items()}
        def selected_key(member):
            if member.name=='payload/manifest.json':return None
            if member.name in snapshots:key=snapshots[member.name]
            else:
                raw=PurePosixPath('/'+member.name.lstrip('/'))
                if '..' in raw.parts or not raw.is_relative_to(prefix):raise ValueError('archive source prefix changed')
                key=str(raw.relative_to(prefix))
            row=proof['entries'].get(key,{})
            canonical=row.get('target') if row.get('kind')=='hardlink' else key
            return canonical if canonical in selected and member.isfile() else None
        with regular(self.archive) as source:
            process=subprocess.Popen(['zstd','-d','-c'],stdin=source,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
            def members():
                seen=set()
                with tarfile.open(fileobj=process.stdout,mode='r|') as archive:
                    for member in archive:
                        key=selected_key(member)
                        if key is not None:
                            if key in seen or not member.isfile():raise ValueError('local replay member changed')
                            with archive.extractfile(member) as payload:yield key,payload
                            seen.add(key)
                while process.stdout.read(1048576):pass
                if process.wait(timeout=30)!=0 or seen!=set(selected):raise ValueError('incomplete B-local archive replay')
            iterator=members()
            try:
                yield iterator
                for _ in iterator:pass
                self.verify(capture_id)
            finally:
                iterator.close()
                if process.poll() is None:process.kill()
                process.wait();process.stdout.close()


def run(config):
    started=time.monotonic()
    if os.getuid()!=1000:raise ValueError('existing unprivileged WSL writer required')
    root=Path(config['wsl_root'])
    if (not str(root).startswith('/mnt/b/vk-backups/vk-') or '..' in root.parts
            or config.get('retention_adopted') is not True):raise ValueError('explicit fresh operational scope/adoption required')
    def mount():
        row=subprocess.check_output(['findmnt','-n','-T','/mnt/b','-o','SOURCE,FSTYPE'],text=True).split()
        if row!=['B:\\','9p']:raise ValueError('existing B drvfs mount changed')
        return Path('/mnt/b')
    def readback(folder,manifest):
        databases=manifest.get('capture_context',{}).get('nightly_databases',[])
        request={'folder':'B:/'+str(folder.relative_to('/mnt/b')),'volume_device':config['volume_device'],
                 'manifest_sha256':hashlib.sha256(encoded(manifest)).hexdigest(),
                 'scope':config['scope_sha256'],'databases':databases,'source_prefix':config['source_prefix']}
        process=subprocess.run(['/mnt/c/Python310/python.exe','-B','-c',WINDOWS_READBACK],input=json.dumps(request),
                               capture_output=True,text=True,timeout=config['readback_timeout_seconds'])
        if process.returncode:raise ValueError('native Windows B readback failed: '+process.stderr[:500])
        return json.loads(process.stdout)
    mount()
    volume=subprocess.run(['/mnt/c/Python310/python.exe','-B','-c',
                           "import json,os;print(json.dumps(os.stat('B:/').st_dev))"],capture_output=True,text=True,timeout=30)
    if volume.returncode or json.loads(volume.stdout)!=config['volume_device']:raise ValueError('physical B volume substituted')
    if config.get('enroll_fresh') is True:
        root.mkdir()  # Never mkdir exist_ok or re-enroll an existing backup root.
        (root/'store').mkdir();(root/'jobs').mkdir()
    store=NightlyStore(root/'store',config['scope_sha256'],mount,independent_readback=readback)
    initial=store.current() is None
    changed_limit=config.get('initial_changed_limit_bytes',config['changed_limit_bytes']) if initial else config['changed_limit_bytes']
    reserve=config.get('initial_reserve_bytes',config['reserve_bytes']) if initial else config['reserve_bytes']
    job=NightlyJob(root/'jobs',store,capture_limit_bytes=config['capture_limit_bytes'],changed_limit_bytes=changed_limit)
    if config.get('enroll_fresh') is True:store.enroll_empty();job.enroll_empty();sync_directory(root)
    def factory(folder,register,seal,*,parent):
        attempt=job.read();binding={key:attempt[key] for key in ('candidate','input_name')}
        binding['scope_sha256']=store.scope
        emit({'event':'capture_ready','binding':binding,'directory':'B:/'+str(folder.relative_to('/mnt/b'))})
        while True:
            command=receive(sys.stdin.buffer)
            if command.get('binding')!=binding:raise ValueError('stale/wrong live producer binding')
            action=command.get('action');raw=command.get('name')
            if action in ('allocate','seal','inspect'):
                if not isinstance(raw,str) or not re.fullmatch('[A-Za-z0-9_.-]+',raw) or raw in ('.','..'):
                    raise ValueError('unsafe registered input name')
                path=folder/raw
                if action=='allocate':
                    with path.open('xb') as stream:register(path,stream.fileno())
                    emit({'allocated':raw})
                elif action=='inspect':
                    # Only an already registered exact live input, never a
                    # source selector or an arbitrary B path/content reader.
                    row=job.read()['inputs'].get(raw)
                    if row is None:raise ValueError('unknown diagnostic input')
                    # SQLite's still-open Windows-backed handle can deny a
                    # concurrent data open. Inspection needs only lstat: retain
                    # the exact registered identity/type/reparse guards.
                    info=path.lstat()
                    if not stat.S_ISREG(info.st_mode) or [info.st_dev,info.st_ino]!=row['identity']:
                        raise ValueError('diagnostic input substituted')
                    request={'path':'B:/'+str(path.relative_to('/mnt/b')),'volume_device':config['volume_device']}
                    checked=subprocess.run(['/mnt/c/Python310/python.exe','-B','-c',WINDOWS_INPUT_METADATA],
                        input=json.dumps(request),capture_output=True,text=True,timeout=15)
                    if checked.returncode:raise ValueError('native input metadata unavailable')
                    after=path.lstat()
                    if not stat.S_ISREG(after.st_mode) or [after.st_dev,after.st_ino]!=row['identity']:
                        raise ValueError('diagnostic input changed during native metadata read')
                    emit({'name':raw,'registered_identity':row['identity'],'native':json.loads(checked.stdout)})
                else:
                    with regular(path) as stream:os.fsync(stream.fileno())
                    sync_directory(folder);seal(path);row=job.read()['inputs'][raw]
                    receipt={'sealed':raw,'sha256':row['sha256'],'bytes':row['bytes']}
                    if command.get('sqlite_integrity') is True:
                        if not re.fullmatch('sqlite-consistent-[0-9a-f]{32}\\.sqlite',raw):raise ValueError('unknown snapshot selector')
                        request={'path':'B:/'+str(path.relative_to('/mnt/b')),'volume_device':config['volume_device'],
                                 'bytes':row['bytes'],'sha256':row['sha256']}
                        checked=subprocess.run(['/mnt/c/Python310/python.exe','-B','-c',WINDOWS_SQLITE_INPUT],
                            input=json.dumps(request),capture_output=True,text=True,timeout=config['snapshot_timeout_seconds'])
                        if checked.returncode or json.loads(checked.stdout)!={'bytes':row['bytes'],'sha256':row['sha256'],'integrity':'ok'}:
                            raise ValueError('independent private B snapshot readback failed')
                        receipt['integrity']='ok'
                    emit(receipt)
            elif action=='finish':
                if command.get('producer_closed') is not True:raise ValueError('producer completion missing')
                proof_name=command.get('proof_name')
                if proof_name!='nightly-proof.json':raise ValueError('unknown proof selector')
                with regular(folder/proof_name) as stream:
                    raw=stream.read(MAX_INDEX+1)
                if len(raw)>MAX_INDEX or hashlib.sha256(raw).hexdigest()!=command.get('proof_sha256'):
                    raise ValueError('proof size/digest mismatch')
                value=json.loads(raw);provider=LocalVerifiedProvider(folder,value,config)
                provider.value['proof']['nightly_databases']=value['result']['databases']
                return provider,value['capture_id'],value['result']
            else:raise ValueError('unsupported fixed job action')
    # The MCP kernel lease covers source producers; resident job.held covers B.
    # Recovery is requested only after the new MCP runner holds that same lease
    # and has reaped its channels. No inventory-only global fence is claimed.
    if config.get('recover_only') is True:
        result=job.reconcile(retention_adopted=True,inputs_quiescent=True)
    else:
        def quiescent(attempt):
            return {'candidate':attempt['candidate'],'input_name':attempt['input_name'],
                    'scope_sha256':store.scope,'quiescent':config.get('mcp_producer_lease_held') is True}
        result=job.tick(factory,quiescent,retention_adopted=True,reserve_bytes=reserve)
    emit({'event':'complete','result':result,'elapsed_seconds':time.monotonic()-started})
    return 0 if result['passed'] else 1
