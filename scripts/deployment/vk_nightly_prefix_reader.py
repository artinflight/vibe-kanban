"""Read accepted prefix components on the existing B-backed Linux reader.

Only the installed controller supplies layer roots, distro/volume identity and
the existing recovery lease. The source manifest cannot select commands or
outside paths. Old bodies stream through bounded buffers; no new payload file,
mount, registration, security change or full baseline copy is made.
"""
import ast
import base64
import hashlib
import json
from pathlib import Path
import select
import subprocess

from vk_nightly_objects import exact,read_control


LINUX_READER = r'''
import base64,fcntl,hashlib,json,os,pathlib,stat,sys,zipfile,zlib
q=json.loads(sys.stdin.buffer.readline(1048577))
assert os.getuid()==q['expected_uid'] and os.getgid()==q['expected_gid'] and len(q['segments'])<=100000,'existing Linux reader UID/GID/segment bound differs'
rootbase=pathlib.Path(q['accepted_base_root'])
assert rootbase.resolve()==rootbase and rootbase.stat().st_ino==q['accepted_base_inode'],('accepted restore root changed',str(rootbase),rootbase.stat().st_ino)
lease=os.open(q['lease'],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
assert stat.S_ISREG(os.fstat(lease).st_mode),'existing recovery lease is not regular'
fcntl.flock(lease,fcntl.LOCK_SH|fcntl.LOCK_NB)
lease_identity=(os.fstat(lease).st_dev,os.fstat(lease).st_ino)
def identity(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def opened(root,selector):
 p=pathlib.PurePosixPath(selector)
 assert not p.is_absolute() and str(p)==selector and '..' not in p.parts and '\0' not in selector
 fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 try:
  for part in p.parts[:-1]:
   new=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=new
  file=os.open(p.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
 finally:os.close(fd)
 assert stat.S_ISREG(os.fstat(file).st_mode)
 return os.fdopen(file,'rb')
def emit(block,h,counter):
 assert counter[0]+len(block)<=segment['bytes']
 h.update(block);counter[0]+=len(block);sys.stdout.buffer.write(block)
sys.stdout.buffer.write(b'VK_PREFIX_READY_V1\n');sys.stdout.buffer.flush()
for segment in q['segments']:
 root=pathlib.Path(q['roots'][segment['layer']]);assert root.is_absolute() and root.resolve()==root
 assert root==rootbase or str(root).startswith('/mnt/b/vk-backups/')
 h=hashlib.sha256();count=[0];codec=segment.get('encoding','raw')
 with opened(root,segment['selector']) as f:
  before=identity(os.fstat(f.fileno()));encoded=hashlib.sha256();encoded_bytes=0
  assert before[2]==segment.get('encoded_bytes',segment['bytes'])
  if codec=='zip-member':
   for block in iter(lambda:f.read(65536),b''):encoded.update(block);encoded_bytes+=len(block)
   assert encoded_bytes==segment['encoded_bytes'] and encoded.hexdigest()==segment['encoded_sha256']
   f.seek(0)
   with zipfile.ZipFile(f) as archive:
    assert archive.namelist().count(segment['member'])==1 and archive.getinfo(segment['member']).file_size==segment['bytes']
    with archive.open(segment['member']) as member:
     for block in iter(lambda:member.read(65536),b''):emit(block,h,count)
  else:
   assert codec in ('raw','zlib');decoder=zlib.decompressobj() if codec=='zlib' else None
   for block in iter(lambda:f.read(65536),b''):
    encoded.update(block);encoded_bytes+=len(block);pending=block
    while pending:
     value=decoder.decompress(pending,65536) if decoder else pending
     pending=decoder.unconsumed_tail if decoder else b''
     assert count[0]+len(value)<=segment['bytes'] and (decoder is None or not decoder.unused_data)
     emit(value,h,count)
   assert encoded_bytes==segment.get('encoded_bytes',segment['bytes'])
   assert encoded.hexdigest()==segment.get('encoded_sha256',segment['sha256'])
   assert decoder is None or decoder.eof and not decoder.unused_data
  assert count[0]==segment['bytes'] and h.hexdigest()==segment['sha256']
  assert identity(os.fstat(f.fileno()))==before
assert (os.stat(q['lease']).st_dev,os.stat(q['lease']).st_ino)==lease_identity
assert rootbase.stat().st_ino==q['accepted_base_inode']
sys.stdout.buffer.flush();os.close(lease)
'''


NATIVE_READER = r'''
settings=CONFIG['prefix_reader'];prefix=PREFIX
probe=r"$d=Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss'|ForEach-Object {Get-ItemProperty $_.PSPath}|Where-Object {$_.DistributionName -eq '"+settings['distribution']+r"'};if(@($d).Count -ne 1){throw 'Exact existing distro missing'};$d.BasePath|ConvertTo-Json -Compress"
p=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(probe.encode('utf-16le')).decode()],capture_output=True,timeout=15)
p.check_returncode();assert json.loads(p.stdout.decode('utf-8-sig'))==settings['registered_BasePath'],'B-backed reader registration changed'
query=dict(settings,segments=prefix['segments'])
# Exact retained provider route: the distro has numeric owner1000, no named
# mcp login. Drop UID/GID/groups before executing any reader code, as the
# accepted native_parent provider already did. No account/access change.
p=subprocess.Popen(['wsl.exe','-d',settings['distribution'],'--exec','setpriv','--reuid','1000','--regid','1000','--clear-groups','python3','-B','-S','-c',LINUX_READER],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
p.stdin.write(json.dumps(query,separators=(',', ':')).encode()+b'\n');p.stdin.close()
preamble=p.stdout.readline(1025)
if preamble!=b'VK_PREFIX_READY_V1\n':
 p.stdout.close();code=p.wait(timeout=30);diagnostic=p.stderr.read(4096)
 text=preamble.decode('utf-16' if preamble.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8',errors='replace')
 raise ValueError('Existing B reader returned nonprotocol startup output; exit='+str(code)+'; stdout='+repr(text[:512])+'; stderr='+diagnostic.decode(errors='replace'))
h=hashlib.sha256();total=0
while True:
 block=p.stdout.read(65536)
 if not block:break
 total+=len(block);assert total<=prefix['bytes'],'prefix reader exceeded exact body'
 progress_guard(0);h.update(block);sys.stdout.buffer.write(block)
sys.stdout.buffer.flush()
code=p.wait(timeout=30)
if code:raise ValueError('Existing B Linux reader failed: '+p.stderr.read(4096).decode(errors='replace'))
assert total==prefix['bytes'] and h.hexdigest()==prefix['sha256']
actual_guard(0)
print(json.dumps(dict(status='prefix_verified',bytes=total,sha256=h.hexdigest())),flush=True)
'''


def read_prefix(session,prefix,sink):
    """Run serially within the exact active DesktopObjects writer admission."""
    from vk_nightly_desktop_objects import NATIVE
    settings=session.config.get('prefix_reader')
    if (not isinstance(settings,dict) or settings.get('distribution')!='VK-Candidate-20261009'
            or settings.get('expected_uid')!=1000
            or settings.get('expected_gid')!=1000
            or not settings.get('registered_BasePath','').startswith('\\\\?\\B:\\vk-backups\\')
            or settings.get('accepted_base_inode')!=776107
            or not settings.get('accepted_base_root','').startswith('/var/tmp/vk-nightly-restored-set-')
            or not settings.get('lease','').startswith('/mnt/b/vk-backups/')
            or not prefix.get('segments')):
        raise ValueError('exact existing B-backed prefix reader binding required')
    for segment in prefix['segments']:
        if segment['layer'] not in settings['roots']:raise ValueError('undeclared accepted prefix layer')
    session.guard()
    # Retain the same first-party native health/admission setup, replacing only
    # the fixed object receiver with this fixed read-only component consumer.
    tree=ast.parse(NATIVE)
    receiver=next(n for n in tree.body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call)
        and isinstance(n.value.func,ast.Attribute) and isinstance(n.value.func.value,ast.Name)
        and n.value.func.value.id=='objects' and n.value.func.attr=='receive')
    setup='\n'.join(NATIVE.splitlines()[:receiver.lineno-1])+'\n'
    mm=Path(session.config['MM_source']).read_text();objects=Path(__file__).with_name('vk_nightly_objects.py').read_text()
    if hashlib.sha256(mm.encode()).hexdigest()!=session.config['MM_sha256']:raise ValueError('current MM pin changed')
    program='CONFIG='+repr(session.config)+'\nMM_SOURCE='+repr(mm)+'\nOBJECT_SOURCE='+repr(objects)+'\nPREFIX='+repr(prefix)+'\nLINUX_READER='+repr(LINUX_READER)+'\n'+setup+NATIVE_READER
    command=['ssh','-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15',
        '-o','ControlMaster=no','-o','ControlPath=none','desktop',
        'python -B -u -c "import sys,base64;exec(base64.b64decode(sys.stdin.buffer.readline()))"']
    p=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                       pass_fds=(session.lease.fileno(),))
    try:
        p.stdin.write(base64.b64encode(program.encode())+b'\n');p.stdin.close()
        if not select.select([p.stdout],[],[],90)[0]:raise TimeoutError('accepted-prefix reader admission')
        ready=read_control(p.stdout)
        if not ready or ready.get('status')!='ready':raise ValueError('accepted-prefix native readiness failed')
        left=prefix['bytes'];h=hashlib.sha256()
        while left:
            session.guard();block=exact(p.stdout,min(left,65536));h.update(block);view=memoryview(block)
            while view:
                written=sink.write(view)
                if type(written) is not int or not 0<written<=len(view):raise OSError('prefix consumer short write')
                view=view[written:]
            left-=len(block)
        final=read_control(p.stdout)
        if final!=dict(status='prefix_verified',bytes=prefix['bytes'],sha256=prefix['sha256']) or h.hexdigest()!=prefix['sha256']:
            raise ValueError('independent accepted-prefix readback differs')
        if p.wait(timeout=60):raise RuntimeError(p.stderr.read(4096).decode(errors='replace'))
    except BaseException as error:
        # Abort only our read transport, not a process or recovery file. This
        # releases producer backpressure and preserves the original error plus
        # the remote access/lease/protocol cause rather than reporting EOF only.
        if not p.stdout.closed:p.stdout.close()
        p.wait(timeout=60)
        diagnostic=p.stderr.read(4096).decode(errors='replace')
        error.nightly_reader_diagnostic=diagnostic
        if diagnostic and hasattr(error,'add_note'):error.add_note(diagnostic)
        raise
    finally:
        if p.stdin and not p.stdin.closed:p.stdin.close()
        if p.poll() is None:p.wait(timeout=60)
        if not p.stdout.closed:p.stdout.close()
        p.stderr.close()
