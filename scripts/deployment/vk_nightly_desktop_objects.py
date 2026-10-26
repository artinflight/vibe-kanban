"""Pinned native Desktop B object session; sole-writer lease lives with SSH.

Trusted installed configuration supplies exact current MM code/hash, hardware
baseline and the already-reviewed identity probe. Nothing executable is taken
from a recovery descriptor. No mounts, credentials, OS policies or retention
are changed. The local controller supplies actual host admission throughout.
"""
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import sys

from vk_nightly_objects import ObjectClient,read_control


NATIVE = r'''
import base64,datetime,hashlib,json,os,pathlib,shutil,subprocess,sys,time,types
mm=types.ModuleType('current_MM_guard');exec(MM_SOURCE,mm.__dict__)
job=pathlib.Path(CONFIG['B_root']);baseline=CONFIG['baseline']
def actual_guard(remaining):
 records={p:mm.parse(mm.bounded_read(p)) for p in (mm.STOP_PATH,mm.STATE_PATH)}
 for record in records.values():mm.pause(record)
 assert mm.b_outside_monitor_scope(records[mm.STOP_PATH],records[mm.STATE_PATH]),'B scope changed'
 for row in records[mm.STATE_PATH].get('Drives',[]):
  if str(row.get('Letter','')).rstrip(':').upper()=='B':
   assert row.get('Status')=='CHECKED' and not row.get('Reasons'),'explicit B hold'
 try:(job/'STOP').stat()
 except FileNotFoundError:pass
 else:raise ValueError('own STOP present')
 p=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',
    base64.b64encode(CONFIG['identity_ps'].encode('utf-16le')).decode()],capture_output=True,timeout=15)
 p.check_returncode();identity=json.loads(p.stdout.decode('utf-8-sig'));mm.check_identity(identity)
 p=subprocess.run(['C:/ProgramData/MediaArchiveMonitor/smartctl/bin/smartctl.exe',
    '-j','-i','-H','-A','-l','sataphy','/dev/pd3'],capture_output=True,timeout=15)
 p.check_returncode();j=json.loads(p.stdout)
 attrs={x['id']:x['raw']['value'] for x in j['ata_smart_attributes']['table'] if x['id'] in [5,187,188,197,198,199]}
 phy={x['id']:x['value'] for x in j['sata_phy_event_counters']['table']}
 assert j['serial_number']==baseline['NativeSerial'] and j['smart_status']['passed'] is True
 assert attrs=={x['id']:x['raw']['value'] for x in baseline['Attributes']},'B SMART counters changed'
 assert phy=={x['id']:x['value'] for x in baseline['Phy']},'B PHY counters changed'
 health=dict(serial=j['serial_number'],attributes={str(k):v for k,v in attrs.items()},
             phy={str(k):v for k,v in phy.items()},temperature=j.get('temperature',{}).get('current'),
             smart_passed=True,exit=0)
 mm.check_health(health)
 assert os.stat('B:/').st_dev==CONFIG['volume_device'] and identity['disk_number']==3
 free=shutil.disk_usage('B:/').free
 assert free>CONFIG['protected_B_bytes']+remaining+1048576,'actual B protected floor/commitment'
 return dict(identity=identity,health=health,free_bytes=free,UTC=datetime.datetime.now(datetime.timezone.utc).isoformat())
assert hashlib.sha256(MM_SOURCE.encode()).hexdigest()==CONFIG['MM_sha256']
assert hashlib.sha256(OBJECT_SOURCE.encode()).hexdigest()==CONFIG['object_module_sha256']
mm.evidence();before=actual_guard(CONFIG['maximum_object_bytes']+1048576)
mm.no_reparse(str(job));job.mkdir(parents=True,exist_ok=True)
objects=types.ModuleType('nightly_objects');exec(OBJECT_SOURCE,objects.__dict__)
last_check=time.monotonic()
def progress_guard(remaining):
 global last_check
 assert shutil.disk_usage('B:/').free>CONFIG['protected_B_bytes']+remaining+1048576
 if time.monotonic()-last_check>=5:
  actual_guard(remaining);last_check=time.monotonic()
print(json.dumps(dict(status='ready',guard=before,object_module_sha256=CONFIG['object_module_sha256'])),flush=True)
objects.receive(job,sys.stdin.buffer,sys.stdout.buffer,guard=progress_guard,maximum_object_bytes=CONFIG['maximum_object_bytes'],retained_SQL_root='B:/vk-backups' if CONFIG.get('retained_SQL_reads') is True else None)
actual_guard(1048576)
'''


def validate(config,objects):
    root=config['B_root']
    if (not isinstance(root,str) or not root.startswith('B:/vk-backups/') or '\\' in root
            or any(p in ('','.','..') for p in root[3:].split('/'))):
        raise ValueError('exact native B backup root required')
    if (type(config['maximum_object_bytes']) is not int or not 0<config['maximum_object_bytes']<=32*1024**2
            or type(config['protected_B_bytes']) is not int or config['protected_B_bytes']<0
            or type(config['volume_device']) is not int or config['volume_device']<=0):
        raise ValueError('finite actual native admission required')
    if hashlib.sha256(objects.encode()).hexdigest()!=config['object_module_sha256']:
        raise ValueError('installed object module differs')
    if (not isinstance(config['identity_ps'],str) or len(config['identity_ps'])>65536
            or hashlib.sha256(config['identity_ps'].encode()).hexdigest()!=config['identity_probe_sha256']):
        raise ValueError('reviewed native identity probe changed')


class DesktopObjects:
    def __init__(self,config,*,guard,ram_root='/dev/shm'):
        self.config=config;self.guard=guard;self.ram_root=ram_root
        self.lease=None;self.process=None;self.ready=None

    def __enter__(self):
        self.guard()
        objects=Path(__file__).with_name('vk_nightly_objects.py').read_text()
        validate(self.config,objects)
        mm=Path(self.config['MM_source']).read_text()
        if hashlib.sha256(mm.encode()).hexdigest()!=self.config['MM_sha256']:
            raise ValueError('current MM code changed; reconcile its actual rule before writing')
        # Existing shared lane, never an alternate lock. Inheritance preserves
        # exclusion if this Python parent dies before its SSH child does.
        fd=os.open(self.config['writer_lease'],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        self.lease=os.fdopen(fd,'rb')
        try:
            import stat
            if not stat.S_ISREG(os.fstat(fd).st_mode):raise ValueError('existing regular writer lease required')
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            native='CONFIG='+repr(self.config)+'\nMM_SOURCE='+repr(mm)+'\nOBJECT_SOURCE='+repr(objects)+'\n'+NATIVE
            command=['ssh','-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15',
                '-o','ControlMaster=no','-o','ControlPath=none','desktop',
                'python -B -u -c "import sys,base64;exec(base64.b64decode(sys.stdin.buffer.readline()))"']
            self.process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                          pass_fds=(fd,))
            self.process.stdin.write(base64.b64encode(native.encode())+b'\n');self.process.stdin.flush()
            if not select.select([self.process.stdout],[],[],90)[0]:raise TimeoutError('native B readiness')
            self.ready=read_control(self.process.stdout)
            if not self.ready:raise RuntimeError(self.process.stderr.read(4096).decode(errors='replace'))
            if self.ready.get('status')!='ready' or self.ready.get('object_module_sha256')!=self.config['object_module_sha256']:
                raise ValueError('native installed code readiness differs')
            self.client=ObjectClient(self.process.stdout,self.process.stdin,guard=self.guard,ram_root=self.ram_root,
                                     maximum_object_bytes=self.config['maximum_object_bytes'])
            return self
        except BaseException:
            self.__exit__(*sys.exc_info());raise

    def __exit__(self,kind,value,tb):
        try:
            if self.process is not None:
                p=self.process
                if p.stdin and not p.stdin.closed:p.stdin.close()
                # A receiver may be blocked sending readback when this owner
                # aborts. Close our own output transport so it can observe
                # the disconnect; waiting on a full pipe would deadlock.
                if kind is not None and p.stdout and not p.stdout.closed:p.stdout.close()
                # Never kill a foreign/native worker or release its inherited
                # lease on a guessed terminal state. A timeout is explicit.
                code=p.wait(timeout=60)
                if code and kind is None:raise RuntimeError(p.stderr.read(4096).decode(errors='replace'))
                if not p.stdout.closed:p.stdout.close()
                p.stderr.close()
        finally:
            if self.lease is not None:self.lease.close()
