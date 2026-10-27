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
