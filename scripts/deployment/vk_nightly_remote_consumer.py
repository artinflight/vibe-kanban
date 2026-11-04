"""Existing Desktop-B WSL normal consumer, with code/packet streamed in memory.

No install, mount, source payload staging, arbitrary command, root execution or
new distro. The controller retains its normal native B guard while the existing
UID1000 consumer holds the actual provider/metadata leases through readback.
"""
import base64
import hashlib
import json
from pathlib import Path
import select
import subprocess
import time

from vk_nightly_desktop_objects import ssh_command
from vk_nightly_transport_diagnostics import Diagnostics,finish
# Static dependency discovery must pin the executable reader too; the wire
# loader below still executes only the authenticated in-memory closure.
import vk_nightly_composed_consumer
from vk_nightly_typed_worker import source_closure
from vk_typed_recovery import checksum


MAX_LINE=2*1024**2
LOADER=r'''
import hashlib,importlib.abc,importlib.util,json,re,sys
raw=sys.stdin.buffer.readline(1048577)
if len(raw)>1048576 or not raw.endswith(b'\n'):raise ValueError('bounded source bootstrap required')
value=json.loads(raw);sources=value['sources']
if not isinstance(sources,dict) or not 1<=len(sources)<=64:raise ValueError('finite exact consumer closure required')
for name,row in sources.items():
 if not re.fullmatch('vk_[a-z0-9_]+',name) or hashlib.sha256(row['source'].encode()).hexdigest()!=row['sha256']:raise ValueError('consumer source binding differs')
class Loader(importlib.abc.MetaPathFinder,importlib.abc.Loader):
 def find_spec(self,fullname,path=None,target=None):
  if fullname in sources:return importlib.util.spec_from_loader(fullname,self)
  if fullname.startswith('vk_'):raise ImportError('undeclared normal-consumer dependency')
 def create_module(self,spec):return None
 def exec_module(self,module):
  name=module.__name__;module.__file__='<pinned-memory-consumer>/'+name+'.py'
  exec(compile(sources[name]['source'],module.__file__,'exec'),module.__dict__)
sys.meta_path.insert(0,Loader());sys.argv=['vk_nightly_composed_consumer','--packet-sha256',value['packet_sha256']]
import vk_nightly_composed_consumer
raise SystemExit(vk_nightly_composed_consumer.main())
'''


def bundle(packet,*,folder=None):
    folder=Path(folder or Path(__file__).parent)
    sources={}
    for filename in sorted(source_closure(folder,'vk_nightly_composed_consumer')):
        source=(folder/filename).read_text()
        sources[filename[:-3]]=dict(source=source,sha256=hashlib.sha256(source.encode()).hexdigest())
    raw=json.dumps(dict(sources=sources,packet_sha256=checksum(packet)),separators=(',',':')).encode()+b'\n'
    encoded=json.dumps(packet,separators=(',',':')).encode()+b'\n'
    if len(raw)>1024**2 or len(encoded)>MAX_LINE:raise ValueError('bounded source/consumer packet required')
    return raw+encoded


def command(controls):
    # Query existing distro placement before reading providers; no registry or
    # guest mutation. The fixed source owns this already authorized distro.
    bridge=r'''
import json,subprocess,sys
query="Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Lxss\\*' | Where-Object DistributionName -eq 'VK-Candidate-20261009' | Select-Object DistributionName,BasePath | ConvertTo-Json -Compress"
p=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',query],capture_output=True,text=True,timeout=30)
if p.returncode:raise ValueError('actual B-backed normal-consumer placement unavailable')
actual=json.loads(p.stdout)
if not isinstance(actual,dict) or actual.get('DistributionName')!='VK-Candidate-20261009' or actual.get('BasePath')!=r'\\?\B:\vk-backups\vk-safe-release-20261009\linux-candidate\distribution':raise ValueError('existing consumer is not the exact accepted B placement')
raise SystemExit(subprocess.call(['wsl.exe','-d','VK-Candidate-20261009','--exec','setpriv','--reuid','1000','--regid','1000','--clear-groups','python3','-B','-u','-c',LOADER],stdin=sys.stdin.buffer,stdout=sys.stdout.buffer,stderr=sys.stderr.buffer))
'''
    bridge='LOADER='+repr(LOADER)+'\n'+bridge
    encoded=base64.b64encode(bridge.encode()).decode()
    return ssh_command(controls,'python -B -u -c "import base64;exec(base64.b64decode(\''+encoded+'\'))"')


PLACEMENT_PROBE = r"""
import os,json,pathlib,re,stat,sys
assert os.getuid()==1000 and os.getgid()==1000
raw=sys.stdin.buffer.readline(65537)
if len(raw)>65536:raise ValueError('bounded provider roots required')
paths=json.loads(raw);result={}
if not isinstance(paths,list) or not 1<=len(paths)<=64:raise ValueError('finite unique physical providers required')
mount=None
if any(p.startswith('/mnt/b/') for p in paths):
 for line in pathlib.Path('/proc/self/mountinfo').read_text().splitlines():
  left,right=line.split(' - ',1);fields=left.split();detail=right.split()
  if fields[4]=='/mnt/b':
   source=re.sub(r'\\([0-7]{3})',lambda m:chr(int(m[1],8)),detail[1]).rstrip('\\/').upper()
   mount=dict(source=source,filesystem=detail[0])
 if not mount or mount['source']!='B:' or mount['filesystem'] not in ('9p','drvfs'):raise ValueError('actual Windows B drvfs mount required')
for path in paths:
 p=pathlib.Path(path);info=p.lstat()
 if not p.is_absolute() or p.resolve()!=p or not stat.S_ISDIR(info.st_mode):raise ValueError('canonical provider root required')
 result[path]=[info.st_dev,info.st_ino]
print(json.dumps(dict(uid=os.getuid(),gid=os.getgid(),bindings=result,B_mount=mount)))
"""


def reconcile_placement(placement,observed):
    """Only B's transient Linux mount device may change; every inode stays pinned."""
    import copy
    value=copy.deepcopy(placement)
    if (observed.get('uid')!=value['expected_uid'] or observed.get('gid')!=value['expected_gid']
            or set(observed.get('bindings',{}))!=set(value['roots'].values())):
        raise ValueError('actual provider owner/root scope differs')
    if any(path.startswith('/mnt/b/') for path in value['roots'].values()):
        mount=observed.get('B_mount',{})
        if (not isinstance(mount,dict) or mount.get('source')!='B:'
                or mount.get('filesystem') not in ('9p','drvfs')):
            raise ValueError('actual Windows B mount identity required')
    for name,path in value['roots'].items():
        old=value['root_bindings'][name];new=observed['bindings'][path]
        if (not isinstance(new,list) or len(new)!=2 or any(type(x) is not int or x<=0 for x in new)
                or new[1]!=old[1] or (new[0]!=old[0] and not path.startswith('/mnt/b/'))):
            raise ValueError('pinned provider inode or non-B placement changed: '+path)
        value['root_bindings'][name]=new
    return value


def probe_placement(controls,placement,*,guard,deadline):
    """Fresh exact normal-B placement before packet sealing; no payload reads.

    Driver device numbers change across WSL mount generations. Query physical
    providers once (not once per logical alias), retaining pinned inodes, the
    native B guard, the existing B-backed distro and all normal reader leases.
    Both SSH and WSL data use stdin, avoiding Windows command-length limits.
    """
    from vk_nightly_window import seconds_left
    paths=sorted(set(placement['roots'].values()))
    raw=(json.dumps(paths,separators=(',',':'))+'\n').encode()
    if len(raw)>65536 or not 1<=len(paths)<=64:raise ValueError('bounded physical provider scope required')
    program=r'''import subprocess,json,sys
q="Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Lxss\\*' | Where-Object DistributionName -eq 'VK-Candidate-20261009' | Select-Object DistributionName,BasePath | ConvertTo-Json -Compress"
r=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',q],capture_output=True,text=True,timeout=30,check=True)
v=json.loads(r.stdout)
if not isinstance(v,dict) or v.get('DistributionName')!='VK-Candidate-20261009' or v.get('BasePath')!=r'\\?\B:\vk-backups\vk-safe-release-20261009\linux-candidate\distribution':raise ValueError('normal consumer B placement differs')
raw=sys.stdin.buffer.readline(65537)
if len(raw)>65536:raise ValueError('bounded root data required')
r=subprocess.run(['wsl.exe','-d','VK-Candidate-20261009','--exec','setpriv','--reuid','1000','--regid','1000','--clear-groups','python3','-B','-c',PROBE],input=raw,capture_output=True,timeout=60)
if r.returncode:raise ValueError('normal provider probe failed: '+r.stderr.decode(errors='replace')[-2048:])
sys.stdout.buffer.write(r.stdout)
'''
    program='PROBE='+repr(PLACEMENT_PROBE)+'\n'+program
    wire=base64.b64encode(program.encode())+b'\n'+raw
    command=ssh_command(controls,'python -B -u -c "import sys,base64;raw=sys.stdin.buffer.readline(65537);assert len(raw)<=65536;exec(base64.b64decode(raw))"')
    guard()
    result=subprocess.run(command,input=wire,capture_output=True,timeout=min(95,seconds_left(deadline)))
    if result.returncode:raise ValueError('normal provider placement unavailable: '+result.stderr.decode(errors='replace')[-2048:])
    if len(result.stdout)>65536:raise ValueError('bounded provider observation exceeded')
    guard();return reconcile_placement(placement,json.loads(result.stdout))


def run(controls,packet,*,guard,report=lambda _:None,clock=time.monotonic):
    guard();wire=bundle(packet)
    process=subprocess.Popen(command(controls),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    diagnostics=Diagnostics(process.stderr);result=None;buffer=b'';last_check=clock()
    try:
        process.stdin.write(wire);process.stdin.flush();process.stdin.close()
        while True:
            guard()
            if not select.select([process.stdout],[],[],5)[0]:
                report(dict(phase='same-normal-composed-consumer-active',elapsed_since_output_seconds=clock()-last_check))
                continue
            block=__import__('os').read(process.stdout.fileno(),65536)
            if not block:break
            buffer+=block
            if len(buffer)>MAX_LINE:raise ValueError('bounded composed-consumer output exceeded')
            while b'\n' in buffer:
                line,buffer=buffer.split(b'\n',1);value=json.loads(line);last_check=clock()
                if value.get('event')=='composed-consumer-result':
                    if result is not None:raise ValueError('duplicate normal-consumer final result')
                    result=value['result']
                elif value.get('event')=='composed-consumer-progress':report(value)
                else:raise ValueError('unexpected normal-consumer protocol record')
        if buffer or result is None:raise ValueError('normal composed-consumer terminal result missing; preserve all data')
        guard();finish(process,diagnostics=diagnostics)
        if (result.get('consumer_packet_sha256')!=checksum(packet)
                or result.get('descriptor_sha256')!=packet['descriptor_sha256']
                or result.get('normal_leased_consumer_entrypoint_verified') is not True
                or result.get('independent_composed_restore_verified') is not True):
            raise ValueError('actual normal composed-consumer binding differs')
        return dict(result,actual_existing_B_backed_consumer_route_verified=True)
    except BaseException as error:
        finish(process,original=error,diagnostics=diagnostics)
        raise
