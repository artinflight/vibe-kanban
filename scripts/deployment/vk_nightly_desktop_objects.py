"""Pinned native Desktop B object session; sole-writer lease lives with SSH.

Trusted installed configuration supplies exact current MM code/hash, hardware
baseline and the already-reviewed identity probe. Nothing executable is taken
from a recovery descriptor. No mounts, credentials, OS policies or retention
are changed. The local controller supplies actual host admission throughout.
"""
import base64
import fcntl
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import select
import subprocess
import sys

from vk_nightly_objects import ObjectClient,read_control
from vk_nightly_transport_diagnostics import Diagnostics,finish
from vk_nightly_window import seconds_left


NATIVE = r'''
import base64,contextlib,datetime,hashlib,json,os,pathlib,shutil,subprocess,sys,time,types
mm=types.ModuleType('current_MM_guard');exec(MM_SOURCE,mm.__dict__)
job=pathlib.Path(CONFIG['B_root']);baseline=CONFIG['baseline']
admitted_identity=None
health_timeout_used=False
health_observations=0
health_query_seconds=0.0
def time_budget(maximum=None):
 deadline=CONFIG.get('whole_cycle_deadline_UTC')
 if deadline is None:return maximum
 end=datetime.datetime.fromisoformat(deadline)
 if end.tzinfo is None:raise ValueError('aware native hard deadline required')
 left=(end-datetime.datetime.now(datetime.timezone.utc)).total_seconds()
 if left<=0:raise TimeoutError('hard backup deadline reached; retain all completed B objects')
 return left if maximum is None else min(left,maximum)
def kernel_identity():
 import ctypes,ctypes.wintypes as wt
 api=ctypes.WinDLL('kernel32',use_last_error=True)
 api.CreateFileW.argtypes=[wt.LPCWSTR,wt.DWORD,wt.DWORD,ctypes.c_void_p,wt.DWORD,wt.DWORD,wt.HANDLE]
 api.CreateFileW.restype=wt.HANDLE
 api.DeviceIoControl.argtypes=[wt.HANDLE,wt.DWORD,ctypes.c_void_p,wt.DWORD,ctypes.c_void_p,wt.DWORD,ctypes.POINTER(wt.DWORD),ctypes.c_void_p]
 api.DeviceIoControl.restype=wt.BOOL
 api.CloseHandle.argtypes=[wt.HANDLE];api.CloseHandle.restype=wt.BOOL
 api.GetVolumeNameForVolumeMountPointW.argtypes=[wt.LPCWSTR,wt.LPWSTR,wt.DWORD]
 api.GetVolumeNameForVolumeMountPointW.restype=wt.BOOL
 handle=api.CreateFileW('\\\\.\\B:',0,3,None,3,0,None)
 if handle==wt.HANDLE(-1).value:raise ctypes.WinError(ctypes.get_last_error())
 try:
  number=(wt.DWORD*3)();returned=wt.DWORD()
  if not api.DeviceIoControl(handle,0x2d1080,None,0,number,ctypes.sizeof(number),ctypes.byref(returned),None):
   raise ctypes.WinError(ctypes.get_last_error())
  assert returned.value==ctypes.sizeof(number) and number[0]==7,'native disk device identity differs'
 finally:
  if not api.CloseHandle(handle):raise ctypes.WinError(ctypes.get_last_error())
 guid=ctypes.create_unicode_buffer(1024)
 if not api.GetVolumeNameForVolumeMountPointW('B:\\',guid,len(guid)):raise ctypes.WinError(ctypes.get_last_error())
 import re
 match=re.fullmatch(r'\\\\\?\\Volume\{([0-9a-fA-F-]{36})\}\\',guid.value)
 assert match,'native B volume GUID malformed'
 return dict(disk_number=int(number[1]),partition_number=int(number[2]),volume_guid=match[1].lower())
@contextlib.contextmanager
def health_gate():
 # Control and object sessions poll the SAME drive. Serialize our native
 # commands without a disk cache, stale health receipt or another worker.
 import ctypes,ctypes.wintypes as wt
 api=ctypes.WinDLL('kernel32',use_last_error=True)
 api.CreateMutexW.argtypes=[ctypes.c_void_p,wt.BOOL,wt.LPCWSTR];api.CreateMutexW.restype=wt.HANDLE
 api.WaitForSingleObject.argtypes=[wt.HANDLE,wt.DWORD];api.WaitForSingleObject.restype=wt.DWORD
 api.ReleaseMutex.argtypes=[wt.HANDLE];api.ReleaseMutex.restype=wt.BOOL
 api.CloseHandle.argtypes=[wt.HANDLE];api.CloseHandle.restype=wt.BOOL
 handle=api.CreateMutexW(None,False,'Local\\VK-Nightly-B-Health-ZFN13YZ8-2360624474')
 if not handle:raise ctypes.WinError(ctypes.get_last_error())
 acquired=False
 try:
  wait=api.WaitForSingleObject(handle,int(time_budget(CONFIG.get('native_health_read_timeout_seconds',90)+15)*1000))
  if wait==0x102:raise TimeoutError('finite native health observation ownership wait; no payload IO admitted')
  if wait not in (0,0x80):raise ctypes.WinError(ctypes.get_last_error())
  # An abandoned owner's result is never reused: always perform a fresh read.
  acquired=True;yield
 finally:
  try:
   if acquired and not api.ReleaseMutex(handle):raise ctypes.WinError(ctypes.get_last_error())
  finally:
   if not api.CloseHandle(handle):raise ctypes.WinError(ctypes.get_last_error())
def control_identity():
 global admitted_identity
 time_budget()
 records={p:mm.parse(mm.bounded_read(p)) for p in (mm.STOP_PATH,mm.STATE_PATH)}
 for record in records.values():mm.pause(record)
 assert mm.b_outside_monitor_scope(records[mm.STOP_PATH],records[mm.STATE_PATH]),'B scope changed'
 for row in records[mm.STATE_PATH].get('Drives',[]):
  if str(row.get('Letter','')).rstrip(':').upper()=='B':
   assert row.get('Status')=='CHECKED' and not row.get('Reasons'),'explicit B hold'
 try:(job/'STOP').stat()
 except FileNotFoundError:pass
 else:raise ValueError('own STOP present')
 if CONFIG.get('native_identity_mode')=='admission-plus-kernel-continuity-v1' and admitted_identity is not None:
  identity=dict(admitted_identity,**kernel_identity());mm.check_identity(identity)
 else:
  p=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',
     base64.b64encode(CONFIG['identity_ps'].encode('utf-16le')).decode()],capture_output=True,
     timeout=time_budget(CONFIG.get('identity_admission_timeout_seconds',15)))
  p.check_returncode();identity=json.loads(p.stdout.decode('utf-8-sig'));mm.check_identity(identity)
  if CONFIG.get('native_identity_mode')=='admission-plus-kernel-continuity-v1':
   actual=kernel_identity()
   assert all(identity[k]==v for k,v in actual.items()),'kernel/full admission identity mismatch'
   admitted_identity=dict(identity)
 time_budget();return identity
def actual_guard(remaining):
 global admitted_identity,health_timeout_used,health_observations,health_query_seconds
 # Observation patience is an implementation bound, not an owner safety
 # threshold. Keep data IO stopped while waiting for a successful fresh read.
 deadline=CONFIG.get('native_health_read_timeout_seconds',90)
 time_budget()
 try:
  with health_gate():
   identity=control_identity()
   query_started=time.monotonic()
   p=subprocess.run(['C:/ProgramData/MediaArchiveMonitor/smartctl/bin/smartctl.exe',
      '-j','-i','-H','-A','-l','sataphy','/dev/pd3'],capture_output=True,timeout=time_budget(deadline))
   query_seconds=time.monotonic()-query_started
 except subprocess.TimeoutExpired:
  time_budget() # An expired window never starts another observation.
  # A missing observation never authorizes I/O. One read-only requalification
  # per finite session may recover a transient command timeout. No work runs
  # between attempts: all STOP/MM/access checks and full identity run again.
  # Never retry an actual denied operation, changed counter or failed SMART.
  print(json.dumps(dict(event='native-health-observation-unavailable',
      timeout_seconds=deadline,reported_drive_fault=False,data_IO_permitted=False,
      final_failure=health_timeout_used,UTC=datetime.datetime.now(datetime.timezone.utc).isoformat())),file=sys.stderr,flush=True)
  if health_timeout_used:raise
  health_timeout_used=True;admitted_identity=None
  print(json.dumps(dict(event='native-health-read-timeout-requalification',
      timeout_seconds=deadline,UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
      data_IO_permitted=False,remaining_requalifications=0)),file=sys.stderr,flush=True)
  return actual_guard(remaining)
 p.check_returncode();j=json.loads(p.stdout)
 attrs={x['id']:x['raw']['value'] for x in j['ata_smart_attributes']['table'] if x['id'] in [5,187,188,197,198,199]}
 phy={x['id']:x['value'] for x in j['sata_phy_event_counters']['table']}
 assert j['serial_number']==baseline['NativeSerial'],'destination native serial changed'
 assert j['smart_status']['passed'] is True,'reported B SMART health failure'
 assert attrs=={x['id']:x['raw']['value'] for x in baseline['Attributes']},'B SMART counters changed'
 assert phy=={x['id']:x['value'] for x in baseline['Phy']},'B PHY counters changed'
 health=dict(serial=j['serial_number'],attributes={str(k):v for k,v in attrs.items()},
             phy={str(k):v for k,v in phy.items()},temperature=j.get('temperature',{}).get('current'),
             smart_passed=True,exit=0)
 mm.check_health(health)
 # STOP/MM and kernel identity may change during a slow read/ownership wait.
 # Recheck them before the caller may resume any data transfer.
 identity=control_identity()
 assert os.stat('B:/').st_dev==CONFIG['volume_device'] and identity['disk_number']==3
 free=shutil.disk_usage('B:/').free
 assert free>CONFIG['protected_B_bytes']+remaining+1048576,'actual B protected floor/commitment'
 health_observations+=1;health_query_seconds+=query_seconds
 metrics=dict(event='native-health-observation',query_seconds=query_seconds,
     health_observations=health_observations,health_query_seconds=health_query_seconds,
     reported_drive_fault=False,UTC=datetime.datetime.now(datetime.timezone.utc).isoformat())
 print(json.dumps(metrics),file=sys.stderr,flush=True)
 time_budget()
 return dict(identity=identity,health=health,free_bytes=free,health_timeout_requalification_used=health_timeout_used,
     health_poll_seconds=CONFIG.get('native_health_poll_seconds',5),**metrics)
assert hashlib.sha256(MM_SOURCE.encode()).hexdigest()==CONFIG['MM_sha256']
assert hashlib.sha256(OBJECT_SOURCE.encode()).hexdigest()==CONFIG['object_module_sha256']
mm.evidence();before=actual_guard(CONFIG['maximum_object_bytes']+1048576)
mm.no_reparse(str(job));job.mkdir(parents=True,exist_ok=True)
objects=types.ModuleType('nightly_objects');exec(OBJECT_SOURCE,objects.__dict__)
last_check=time.monotonic()
last_health_check=last_check
def progress_guard(remaining):
 global last_check,last_health_check
 time_budget()
 assert shutil.disk_usage('B:/').free>CONFIG['protected_B_bytes']+remaining+1048576
 now=time.monotonic()
 if now-last_health_check>=CONFIG.get('native_health_poll_seconds',5):
  # Full fresh health at admission, finite polling intervals and completion.
  # Slow/unavailable reads block IO; they are not reported drive faults.
  actual_guard(remaining);last_health_check=last_check=time.monotonic()
 elif now-last_check>=5:
  # Keep the original five-second STOP/MM/kernel-identity observation bound
  # independently of expensive SMART. Capacity remains checked on every call.
  identity=control_identity()
  assert os.stat('B:/').st_dev==CONFIG['volume_device'] and identity['disk_number']==3
  last_check=time.monotonic()
def final_guard(remaining):
 global admitted_identity
 # Full fresh MM identity/health again at the acceptance boundary. Only
 # intermediate polling avoids expensive repeated CIM enumeration.
 admitted_identity=None
 return actual_guard(remaining)
print(json.dumps(dict(status='ready',guard=before,object_module_sha256=CONFIG['object_module_sha256'])),flush=True)
objects.receive(job,sys.stdin.buffer,sys.stdout.buffer,guard=progress_guard,maximum_object_bytes=CONFIG['maximum_object_bytes'],retained_SQL_root='B:/vk-backups' if CONFIG.get('retained_SQL_reads') is True else None)
final_guard(1048576)
'''


def ssh_command(config,remote_command):
    """Same existing Desktop identity; optional already-verified LAN placement.

    The trusted installed config, never a recovery manifest, selects the route.
    Host keys remain strict and use the existing Tailnet identity; no key,
    credential, SSH configuration, firewall or listener is changed. Normal
    native volume/MM/STOP/health admission still runs on the selected endpoint.
    """
    command=['ssh','-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
        '-o','UpdateHostKeys=no','-o','ConnectTimeout=15','-o','ControlMaster=no','-o','ControlPath=none',
        '-o','ServerAliveInterval=15','-o','ServerAliveCountMax=3']
    route=config.get('verified_SSH_route')
    if route is not None:
        if (not isinstance(route,dict) or set(route)!={'format','hostname','host_key_alias','identity_probe_sha256'}
                or route.get('format')!='vk-nightly-existing-Desktop-LAN-route-v1'
                or route.get('host_key_alias')!='100.70.23.123'
                or not isinstance(route.get('identity_probe_sha256'),str)
                or len(route['identity_probe_sha256'])!=64
                or any(c not in '0123456789abcdef' for c in route['identity_probe_sha256'])):
            raise ValueError('exact verified existing Desktop route required')
        try:address=ipaddress.IPv4Address(route['hostname'])
        except (ipaddress.AddressValueError,TypeError) as error:raise ValueError('canonical private Desktop IPv4 required') from error
        if (str(address)!=route['hostname'] or not address.is_private or address.is_loopback
                or address.is_link_local or address.is_multicast or address.is_unspecified):
            raise ValueError('canonical private Desktop IPv4 required')
        command.extend(['-o','Hostname='+str(address),'-o','HostKeyAlias='+route['host_key_alias']])
    return command+['desktop',remote_command]


def validate(config,objects,*,check_deadline=True):
    if 'whole_cycle_deadline_UTC' in config:
        if check_deadline:seconds_left(config['whole_cycle_deadline_UTC'])
        else:
            # Immutable completed artifacts remain authentic after their phase
            # expires. This validates shape only; DesktopObjects and live
            # transport admission always enforce the actual caller deadline.
            from datetime import datetime
            if datetime.fromisoformat(config['whole_cycle_deadline_UTC']).tzinfo is None:
                raise ValueError('aware artifact deadline required')
    ssh_command(config,'true')
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
    if config.get('native_identity_mode') not in (None,'admission-plus-kernel-continuity-v1'):
        raise ValueError('unknown native identity continuity mode')
    if config.get('native_identity_mode') and config.get('identity_admission_timeout_seconds') not in (15,45):
        raise ValueError('finite reviewed identity admission deadline required')
    if type(config.get('native_health_read_timeout_seconds',90)) is not int or config.get('native_health_read_timeout_seconds',90) not in (15,90):
        raise ValueError('finite native health observation deadline required')
    if type(config.get('native_health_poll_seconds',5)) is not int or config.get('native_health_poll_seconds',5) not in (5,60):
        raise ValueError('finite reviewed native health polling interval required')
    if config.get('native_health_poll_seconds',5)==60 and config.get('native_identity_mode')!='admission-plus-kernel-continuity-v1':
        raise ValueError('separate health cadence requires live kernel identity continuity')


def native_admission_timeout(config):
    """Cover the same two finite, serialized guard attempts, without IO grace.

    Transport patience cannot expire before the child's admitted health wait.
    No attempt extends the caller's whole-job/resource deadline.
    """
    health=config.get('native_health_read_timeout_seconds',90)
    identity=config.get('identity_admission_timeout_seconds',15)
    if type(health) is not int or health not in (15,90) or type(identity) is not int or identity not in (15,45):
        raise ValueError('finite native observation budgets required')
    maximum=2*((health+15)+identity+health)+30
    return min(maximum,seconds_left(config['whole_cycle_deadline_UTC'])) if 'whole_cycle_deadline_UTC' in config else maximum


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
            command=ssh_command(self.config,'python -B -u -c "import sys,base64;exec(base64.b64decode(sys.stdin.buffer.readline()))"')
            self.process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                          pass_fds=(fd,))
            self.diagnostics=Diagnostics(self.process.stderr)
            self.process.stdin.write(base64.b64encode(native.encode())+b'\n');self.process.stdin.flush()
            if not select.select([self.process.stdout],[],[],native_admission_timeout(self.config))[0]:raise TimeoutError('native B readiness')
            self.ready=read_control(self.process.stdout)
            if not self.ready:raise RuntimeError('native B readiness stream ended')
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
                finish(self.process,original=value,diagnostics=getattr(self,'diagnostics',None))
        finally:
            if self.lease is not None:self.lease.close()
