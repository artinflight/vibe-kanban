"""Qualified duplicate-staging retirement with bounded directory flushes.

Every object retains fresh writer custody, primary/staging hashes, inode checks
and its exclusive kernel lease. Directory flushes precede result publication.
Only newly created private staging replicas can retire; primary/B bytes remain.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
from fast_online import DirectorySyncGroup

def sha(path):
 with Path(path).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write_new(path,value):
 path=Path(path);fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'w')as f:json.dump(value,f,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
 return dict(path=str(path),sha256=sha(path))

def retire_new_staging_objects(plan,archive,primary,folder,guard,*,complete_state,independent_B_proof,normal_control_proof):
 """Delete only this run's duplicate object replicas, after verified publication.

 Keep manifests/receipt/journal and all PRODUCTION objects. A future manual raw
 rollback must first rehydrate these staging replicas from the primary CAS,
 checking each chunk/hash, before invoking the existing guarded Batch again.
 Earlier successful batches are never automatically rolled back to old readers.
 """
 logs=sys.modules['log_dedup'];reclaim=sys.modules['reclaim'];archive=Path(archive);primary=Path(primary);folder=Path(folder)
 if (complete_state.get('complete')is not True or complete_state.get('outcome')!='installed'
     or independent_B_proof.get('independent_normal_B_full_EOF_hash_and_Linux_metadata_verified')is not True
     or normal_control_proof.get('actual_independent_normal_restore',{}).get('independent_owner_controls_restore_verified')is not True):
  raise ValueError('Actual completed conversion, B original restore and dynamic control recovery required')
 if not archive.resolve().is_relative_to(folder.resolve())or not folder.resolve().is_relative_to('/mnt/vk-storage/vk-log-dedup-20261103-0815/production-20261117'):
  raise ValueError('Only NEW task-owned private staging replicas can retire')
 created=json.loads((folder/'STAGING_CREATED_IDENTITIES.private.json').read_bytes());objects={};retained={}
 for row in plan['files']:
  source=archive/row['path'];target=primary/row['path']
  if reclaim.file_hash(source)!=reclaim.file_hash(target):raise ValueError('Actual installed manifest differs from own staging')
  for chunk in logs.load_manifest(source)['chunks']:
   name=chunk['sha256']+'.gz';p=source.parent/'.log-objects'/name;q=target.parent/'.log-objects'/name
   if p in objects or p in retained:continue
   guard();reclaim.object_bytes(q,chunk);reclaim.object_bytes(p,chunk)
   before=logs.regular(p)
   if created.get(str(p.relative_to(archive)))!=logs.version(before):raise ValueError('Foreign/newer staging object; preserve it')
   if before.st_uid!=os.getuid()or before.st_nlink!=1:raise ValueError('Staging ownership or link count changed')
   physical=reclaim.file_hash(p);primary_hash=reclaim.file_hash(q)
   if logs.version(logs.regular(p))!=logs.version(before):raise ValueError('Staging changed during verification')
   row=dict(path=str(p),identity=logs.version(before),physical_sha256=physical,primary=str(q))
   if physical!=primary_hash:
    # Different gzip implementations can encode identical logical CAS content.
    # Preserve the B-backed representation rather than treating it as an exact
    # physical duplicate regenerable from the primary object.
    retained[p]=dict(row,reason='different_valid_gzip_representation',chunk=chunk,
        primary_physical_sha256=primary_hash,allocated_bytes=before.st_blocks*512)
   else:objects[p]=row
 write_new(folder/'STAGING_RETIREMENT_PLAN.private.json',dict(objects=list(objects.values()),retained_objects=list(retained.values()),original_or_primary_deletion=False,regeneration='Copy exact listed primary CAS bytes back to deleted staging names only; retained alternate representations remain in place. Reverify full graph before a separately admitted raw rollback.'))
 syncs=DirectorySyncGroup(reclaim.sync_directory)
 previous=signal.getsignal(signal.SIGIO)
 def broken(*_):raise ValueError('Actual staging consumer appeared; preserve unretired replicas')
 signal.signal(signal.SIGIO,broken);removed=[]
 try:
  for p,row in objects.items():
   guard();fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
   try:
    if logs.version(os.fstat(fd))!=row['identity']or logs.version(logs.regular(p))!=row['identity']:raise ValueError('Owned staging replica replaced')
    fcntl.fcntl(fd,fcntl.F_SETOWN,os.getpid());fcntl.fcntl(fd,fcntl.F_SETLEASE,fcntl.F_WRLCK)
    # The exact primary object was verified above and remains independently
    # readable. Never unlink the primary or anything absent from this allowlist.
    if logs.version(logs.regular(p))!=row['identity']:raise ValueError('Staging changed at exact unlink boundary')
    p.unlink();syncs.removed(p.parent);removed.append(row['path'])
   finally:
    try:fcntl.fcntl(fd,fcntl.F_SETLEASE,fcntl.F_UNLCK)
    finally:os.close(fd)
 finally:
  signal.signal(signal.SIGIO,previous)
  syncs.flush()
  write_new(folder/'STAGING_RETIREMENT_RESULT.private.json',dict(removed_paths=removed,complete=len(removed)==len(objects),retained_objects=list(retained.values()),retained_allocated_bytes=sum(r['allocated_bytes'] for r in retained.values()),all_primary_objects_preserved=True,source_logs_or_old_epochs_deleted=False))
 return dict(duplicate_staging_objects_removed=len(removed),retained_alternate_representations=len(retained),retained_allocated_bytes=sum(r['allocated_bytes'] for r in retained.values()),all_primary_objects_preserved=True)
