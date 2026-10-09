"""Exact owner-approved single SSD copy retirement; no other deletion or activation.

Authorization: Seamus 'yes', Sentinel_3c972054e9688191900e38417fd55e00,
2026-10-09T12:38:25Z, directly answering Sentinel_2da02c6ad39c819184682474c2302ef4
at12:38:08Z: remove only the additional incident SSD archive after consumer
clearance, keeping its B copy and all other recovery evidence; exact decision
https://github.com/artinflight/vibe-kanban/blob/2b225068/VK_CATCHUP_CAPACITY_EXCEPTION_20261009.md.
The prior15:35 receipt is retained but is NOT accepted here.
All B/native hashing and SSH children finish before the final manual root check.
This resident waits for a NEW receipt hash and actual operator-confirmation ID
from the existing Staging execution; JSON euid:0 alone is not authentication.
The manual helper is unchanged; no privileged installation/access expansion.
Read-only clearance plus managed ownership is not an atomic global-open fence.
Brief interruption is separately approved14:40:34Z and is NOT performed here.
"""
from pathlib import Path
import sys,os,json,hashlib,fcntl,stat,datetime,subprocess,time
sys.path.insert(0,'/mnt/vk-storage/vk-safe-release-20261008/offline-integration/scripts/deployment')
from vk_archive_store import SSH,remote_code
from vk_candidate_owner import probe,notify
from vk_candidate_generation import require
b=Path('/mnt/vk-storage/vk-runtime-backup-20261009')
target=Path('/mnt/vk-storage/vk-combined-preparation-20261007/backups/checkpoint-/db5bb16b095241319a79e02e5fc8cdf6/checkpoint--db5bb16b095241319a79e02e5fc8cdf6.tar.zst')
expected=(2065,7340415,23441521918,1791409456129506845,1791409456129506845,1,1000,1000,0o600)
checksum='e994567edaacc75d8aa9a3497b8384a8dbacec462854a3f7f8c5760e1a9a0ce4'
clearance=b/'excluded-incident-archive-operator-consumer-clearance-after-preparation.private.json'
clearance_sha=None
ready_wall=None
operator_confirmation=None
preserve=b/'excluded-incident-archive-preservation-progress.json'
manifest_sha='27e8d486516ab818eee8376178badc9df3a5ddb6f42c6639c8021e5c7b893a2f'
def sig(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_nlink,s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode))
def seal_managed_orchestration():
 # Cooperative Python-path guard for this one managed actor; not a global
 # process/consumer fence. The approved root helper runs in the operator TTY.
 def audit(event,args):
  if event in {'subprocess.Popen','os.system','os.fork','os.forkpty','os.exec','os.posix_spawn'}:
   raise RuntimeError('process creation forbidden after preparation')
  if event=='socket.connect' and args[1]!='/mnt/vk-storage/vk-cutover-candidate-20261009/owner-097e1bfa.sock':
   raise RuntimeError('network/channel creation forbidden after preparation')
 sys.addaudithook(audit)

def check_receipt():
 s=clearance.lstat();require(stat.S_ISREG(s.st_mode) and s.st_uid==s.st_gid==1000 and stat.S_IMODE(s.st_mode)==0o600 and s.st_nlink==1,'unsafe operator receipt identity')
 raw=clearance.read_bytes();require(hashlib.sha256(raw).hexdigest()==clearance_sha,'operator receipt changed')
 r=json.loads(raw);require(operator_confirmation and datetime.datetime.fromisoformat(r['utc'].replace('Z','+00:00')).timestamp() >= ready_wall and r['euid']==0 and r['manifest_sha256']==manifest_sha and r['protected_inodes']==1 and r['consumer_clearance_passed'] is True and not r['matches'] and not r['inspection_denied'] and not r['compilers'] and r['deletion_performed'] is False,'independent clearance not passed')
 age=time.time()-datetime.datetime.fromisoformat(r['utc'].replace('Z','+00:00')).timestamp()
 require(0<=age<=60,'final manual receipt delivery exceeded bounded continuation window; no deletion')
 return r
require(os.path.ismount('/mnt/vk-storage'),'secondary SSD not mounted')
require(hashlib.sha256(preserve.read_bytes()).hexdigest()==manifest_sha,'B preservation manifest changed')
require(hashlib.sha256((b/'excluded-incident-archive-consumer-check-readonly.py').read_bytes()).hexdigest()=='3a93efd9504c632df1bce17ddb060d0bd3907e14193b1372ed9e399c7d2c507d','operator helper differs')
require(not clearance.exists() and not clearance.is_symlink(),'final receipt path already exists; preserve evidence and hold')
pres=json.loads(preserve.read_bytes())
require(pres['source']==str(target) and pres['sha256']==checksum and pres['bytes']==expected[2],'preservation binding differs')
plan=json.loads((b/'backup-plan.json').read_bytes());require(len(plan['sources'])==77 and not any(target==Path(p) or target.is_relative_to(Path(p)) for p in plan['sources']),'archive is a current capture dependency')
for descriptor in [b/'workflow-complete-backups/checkpoint-/b6977449efc74320bf5fbbe432ae06ef/result.json']:
 d=json.loads(descriptor.read_bytes());require(d['passed'] is True and str(target) not in json.dumps(d) and checksum not in json.dumps(d),'accepted checkpoint depends on excluded archive')
def owner():return probe('/mnt/vk-storage/vk-cutover-candidate-20261009/owner-097e1bfa.sock',500933,'757986989',root_binding='cf07ddd1f356cd64ea9da1da5f053ff8ffa03ead9a53b6ae45091c45ac258a24',source='ba1a8c921c9bef2a6893f24683d0a39412cf965c867aec8d630a4e72c63c9015')
require(owner()['controller_phase']=='restored','preparation lease/phase changed')
require(target.resolve()==target and sig(target.lstat())==expected,'pinned archive changed or aliased')
parent=os.open(target.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
fd=os.open(target.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NOATIME,dir_fd=parent)
try:
 require(sig(os.fstat(fd))==expected,'opened archive differs')
 fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
 before_atime=os.fstat(fd).st_atime_ns
 with os.fdopen(os.dup(fd),'rb') as stream:require(hashlib.file_digest(stream,'sha256').hexdigest()==checksum,'native archive hash differs')
 require(sig(os.fstat(fd))==sig(os.stat(target.name,dir_fd=parent,follow_symlinks=False))==expected and os.fstat(fd).st_atime_ns==before_atime,'native identity/metadata changed')
 def Bcheck(path,h,size):
  p=subprocess.run(SSH,input=remote_code(path,h,size,False),text=True,capture_output=True,timeout=240)
  require(p.returncode==0,'existing SSH B readback failed; no alternate route')
  proof=json.loads(p.stdout);require(proof=={'sha256':h,'bytes':size,'remote':path},'B readback differs');return proof
 # The privileged helper permits no archive-holder exemption. Close our FD
 # after native hashing, before any final root check. Parent directory stays held.
 os.close(fd);fd=None
 Barchive=Bcheck(pres['desktop_target'],checksum,expected[2])
 meta=json.loads((b/'excluded-incident-metadata-preservation-B-receipt.json').read_bytes())
 Bmeta=Bcheck(meta['desktop_directory']+'/'+meta['name'],meta['sha256'],meta['bytes'])
 # Both SSH children have exited. Cache only exact results/identities; do not
 # rehash/open network/process callbacks after accepting final clearance.
 def inventory():
  result={}
  for pid in os.listdir('/proc'):
   if not pid.isdigit():continue
   try:result[int(pid)]=int(Path('/proc',pid,'stat').read_text().rpartition(') ')[2].split()[19])
   except FileNotFoundError:continue
  return result
 # Pin local dependency identities after their contents have been verified.
 dependency_paths=[preserve,b/'backup-plan.json',b/'excluded-incident-archive-consumer-check-readonly.py',b/'excluded-incident-metadata-preservation-B-receipt.json',descriptor]
 dependency_identities={p:sig(p.lstat()) for p in dependency_paths}
 before_scan=inventory()
 require(owner()['controller_phase']=='restored','preparation ownership changed before final check')
 require(sig(target.lstat())==expected,'target changed during preparation')
 seal_managed_orchestration()
 ready_wall=time.time()
 print(json.dumps({'phase':'prepared-awaiting-final-manual-clearance','owner_pid':os.getpid(),'target':str(target),'native_and_B_hashes_verified':True,'archive_fd_closed_for_helper':True,'SSH_children_exited':True,'receipt_path':str(clearance),'deletion_performed':False,'production_changed':False}),flush=True)
 # Staging supplies this ONLY after authenticating the actual operator action.
 # No automatic acceptance of a file whose JSON merely claims root identity.
 command=json.loads(sys.stdin.readline())
 require(set(command)=={'receipt_sha256','operator_confirmation'},'unexpected continuation input')
 clearance_sha=command['receipt_sha256'];operator_confirmation=command['operator_confirmation']
 require(isinstance(clearance_sha,str) and len(clearance_sha)==64 and all(c in '0123456789abcdef' for c in clearance_sha),'bad authenticated receipt digest')
 require(isinstance(operator_confirmation,str) and operator_confirmation.startswith('Sentinel_'),'actual operator confirmation reference required')
 r=check_receipt()
 # Fresh accessible-process check complements, never replaces, the authenticated
 # independent protected-process inspection. Any observed new consumer aborts.
 consumers=[];denied=[]
 local_scan_inventory=inventory()
 for pid_number in local_scan_inventory:
  pid=str(pid_number)
  if not pid.isdigit() or int(pid)==os.getpid():continue
  proc=Path('/proc',pid)
  for kind in ('exe','cwd','fd','maps'):
   try:
    if kind=='maps':
     for line in (proc/kind).read_text().splitlines():
      fields=line.split(None,5);major,minor=(int(x,16) for x in fields[3].split(':'))
      if (os.makedev(major,minor),int(fields[4]))==expected[:2]:consumers.append({'pid':int(pid),'kind':kind})
    else:
     entries=list((proc/'fd').iterdir()) if kind=='fd' else [proc/kind]
     for entry in entries:
      try:s=entry.stat()
      except FileNotFoundError:continue
      if (s.st_dev,s.st_ino)==expected[:2]:consumers.append({'pid':int(pid),'kind':kind})
   except FileNotFoundError:pass
   except PermissionError:
    if proc.exists():denied.append({'pid':int(pid),'kind':kind})
 require(set(inventory().items()).issubset(set(local_scan_inventory.items())),'process birth/reuse during final local inspection; retirement held')
 require(not consumers,'new observed archive consumers; retirement held')
 # A pre-existing opaque process was present before the root helper ran.
 # Any still-live newly born/reused opaque process is unproven, including kernel
 # threads: no name-based exemption and no weakening of consumer coverage.
 for item in denied:
  try:start=int(Path('/proc',str(item['pid']),'stat').read_text().rpartition(') ')[2].split()[19])
  except FileNotFoundError:continue
  require(before_scan.get(item['pid'])==start,'new protected process requires independent clearance; retirement held')
 check_receipt();require(owner()['controller_phase']=='restored','preparation ownership changed before retirement')
 require(all(sig(p.lstat())==identity for p,identity in dependency_identities.items()),'local dependency identity changed after preparation')
 # Reacquire the exact archive lease AFTER the independent consumer scan.
 fd=os.open(target.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NOATIME,dir_fd=parent)
 require(sig(os.fstat(fd))==expected,'post-clearance archive changed')
 fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
 second=os.open(target.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=parent)
 try:
  try:fcntl.flock(second,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:pass
  else:raise ValueError('archive lease not retained')
 finally:os.close(second)
 require(target.resolve()==target and sig(target.lstat())==expected and (target.parent.lstat().st_dev,target.parent.lstat().st_ino)==(os.fstat(parent).st_dev,os.fstat(parent).st_ino),'pinned visible path/parent changed')
 require(sig(os.fstat(fd))==sig(os.stat(target.name,dir_fd=parent,follow_symlinks=False))==expected,'held archive identity changed')
 before=os.statvfs(target.parent).f_bavail*os.statvfs(target.parent).f_frsize
 proof={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'approval_message':'Sentinel_3c972054e9688191900e38417fd55e00','approval_utc':'2026-10-09T12:38:25Z','scope':'only pinned incident SSD archive; retain B and every other file/directory','target':str(target),'identity':expected,'sha256':checksum,'operator_confirmation':operator_confirmation,'native_and_B_hashes_precede_final_clearance':True,'global_atomic_consumer_fence_claimed':False,'consumer_clearance_sha256':clearance_sha,'consumer_clearance_utc':r['utc'],'B_archive':Barchive,'B_metadata':Bmeta,'current_accessible_consumers':consumers,'protected_process_references_covered_by_fresh_operator_receipt':len(denied),'preparation_owner_lease_verified':True,'archive_exclusive_lease_held':True,'native_available_before':before,'production_changed':False,'cutover_performed':False,'cleanup_after_QA_available':False}
 with (b/'single-incident-retirement-prepared-boundary.private.json').open('x') as f:json.dump(proof,f,sort_keys=True,indent=2);f.flush();os.fsync(f.fileno())
 # The sole deletion authorized by the exact12:38 user reply.
 os.unlink(target.name,dir_fd=parent);os.fsync(parent)
finally:
 if fd is not None:os.close(fd)
 os.close(parent)
require(not os.path.lexists(target),'approved leaf remains')
fs=os.statvfs(target.parent);proof.update(deletion_performed=True,removed_regular_files=1,removed_directories=0,native_available_after=fs.f_bavail*fs.f_frsize,reserve_bytes=8589934592)
with (target.parent/'SSD-ARCHIVE-PRESERVED-ON-B-20261009.txt').open('x') as f:f.write('Only the owner-approved SSD incident archive copy was retired.\nB copy: '+pres['desktop_target']+'\nSHA256: '+checksum+'\nAll other local metadata/data and directory roots retained.\nThis failed incident archive is not an accepted recovery backup.\n')
with (b/'single-incident-archive-retirement-result.safe.json').open('x') as f:json.dump(proof,f,sort_keys=True,indent=2);f.flush();os.fsync(f.fileno())
notify(proof)  # Durable result is already fsynced; stdout closure is nonfatal.
