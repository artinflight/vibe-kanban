"""Bounded byte-exact archive closure carriers, not a second producer.

Caller retains real writer/B custody. Normal Nightly control-body restore proves
carrier bytes; independent extraction proves every physical member and metadata.
No original, primary object, old epoch, settings, or service action here.
"""
from pathlib import Path
import base64,hashlib,json,os,stat,tarfile,tempfile
B=1024**2

def sha(p):
 with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def version(s):return(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_nlink)
def metadata(p):
 s=p.lstat();return dict(mode=stat.S_IMODE(s.st_mode),uid=s.st_uid,gid=s.st_gid,mtime_ns=s.st_mtime_ns,xattrs={k:base64.b64encode(os.getxattr(p,k,follow_symlinks=False)).decode()for k in os.listxattr(p,follow_symlinks=False)})
def apply(p,m):
 os.chown(p,m['uid'],m['gid']);os.chmod(p,m['mode'])
 for k,v in m['xattrs'].items():os.setxattr(p,k,base64.b64decode(v,validate=True))
 os.utime(p,ns=(m['mtime_ns'],m['mtime_ns']))
def bundles(rows,maximum=24*B):
 current=[];size=0
 for row in rows:
  demand=row['bytes']+4096
  if demand>maximum:raise ValueError('One closure body exceeds bounded carrier admission')
  if current and size+demand>maximum:yield current;current=[];size=0
  current.append(row);size+=demand
 if current:yield current

def pack_verify(root,rows,folder,guard,*,fragments=None,record=lambda value:None):
 root=Path(root);folder=Path(folder);carrier=folder/'closure.tar';manifest=folder/'members.json';actual=[]
 with tarfile.open(carrier,'x',format=tarfile.PAX_FORMAT)as tar:
  for index,row in enumerate(rows):
   guard();p=root/row['path'];before=p.lstat()
   if list(version(before))!=row['identity']or metadata(p)!=row['metadata']:raise ValueError('Frozen closure source changed')
   h=hashlib.sha256()
   with p.open('rb')as f:
    if version(os.fstat(f.fileno()))!=version(before):raise ValueError('Closure source changed on open')
    offset=row.get('source_offset',0);f.seek(offset);remaining=row['bytes']
    while remaining:
     block=f.read(min(B,remaining))
     if not block:raise ValueError('Closure body truncated')
     h.update(block);remaining-=len(block)
    f.seek(offset);info=tarfile.TarInfo(str(index));info.size=row['bytes'];info.mode=0o600;tar.addfile(info,f)
    if version(os.fstat(f.fileno()))!=version(before):raise ValueError('Closure source changed during read')
   if version(p.lstat())!=version(before):raise ValueError('Closure source replaced')
   if row.get('expected_sha256',h.hexdigest())!=h.hexdigest():raise ValueError('Qualified physical source hash changed')
   actual.append(dict(row,sha256=h.hexdigest(),member=str(index)))
   if (index+1)%64==0 or index+1==len(rows):record(dict(verified_members=index+1,total_members=len(rows)))
 with carrier.open('rb')as f:os.fsync(f.fileno())
 manifest.write_text(json.dumps(dict(format='vk-lossless-closure-carrier-v1',files=actual,carrier_sha256=sha(carrier)),sort_keys=True)+'\n');manifest.chmod(0o600);carrier.chmod(0o600)
 with manifest.open('rb')as f:os.fsync(f.fileno())
 proof=extract_verify(carrier,manifest,folder/'independent',guard,fragments=fragments)
 return dict(carrier=str(carrier),manifest=str(manifest),files=len(actual),physical_bytes=sum(r['bytes']for r in actual),carrier_sha256=sha(carrier),manifest_sha256=sha(manifest),independent_extraction=proof)

def extract_verify(carrier,manifest,destination,guard,*,fragments=None,record=lambda value:None):
 m=json.loads(Path(manifest).read_bytes());destination=Path(destination);destination.mkdir(mode=0o700)
 if sha(carrier)!=m['carrier_sha256']:raise ValueError('Closure carrier changed')
 verified=[]
 with tarfile.open(carrier,'r:')as tar:
  members=tar.getmembers()
  if len(members)!=len(m['files']):raise ValueError('Incomplete carrier')
  for row,member in zip(m['files'],members):
   guard()
   if not member.isfile()or member.name!=row['member']or member.size!=row['bytes']:raise ValueError('Unexpected carrier member')
   if 'source_offset'in row and fragments is None:raise ValueError('Full fragmented-body verifier required')
   if fragments is not None:fragments.begin(row)
   p=destination/row['member'];h=hashlib.sha256();size=0
   with tar.extractfile(member)as i,p.open('xb')as out:
    while block:=i.read(B):
     out.write(block);h.update(block);size+=len(block)
     if fragments is not None:fragments.update(row,block)
    out.flush();os.fsync(out.fileno())
   apply(p,row['metadata']);s=p.stat()
   if size!=row['bytes']or h.hexdigest()!=row['sha256']or sha(p)!=row['sha256']or metadata(p)!=row['metadata']or(s.st_dev,s.st_ino)==tuple(row['identity'][:2]):raise ValueError('Independent closure restore body/metadata/inode differs')
   if fragments is not None:fragments.end(row)
   verified.append(dict(path=row['path'],bytes=size,sha256=row['sha256'],Linux_metadata_verified=True,separate_restored_inode=[s.st_dev,s.st_ino]));p.unlink()
   if len(verified)%64==0 or len(verified)==len(m['files']):record(dict(verified_members=len(verified),total_members=len(m['files'])))
 destination.rmdir();return dict(passed=True,files=len(verified),physical_bytes=sum(r['bytes']for r in verified),members_sha256=hashlib.sha256(json.dumps(verified,sort_keys=True).encode()).hexdigest())

def closure_layout(root,converted):
 """Include every directory/link in every affected process namespace."""
 root=Path(root);stores={str(Path(n).parent)for n in converted}
 stores.update(str(p.parent.relative_to(root))for name in('.log-objects','.log-packs')for p in root.glob('*/*/processes/'+name))
 directories={'.'};links=[]
 for name in sorted(stores):
  parent=root/name
  if parent.resolve()!=parent or not stat.S_ISDIR(parent.lstat().st_mode):raise ValueError('Closure parent substituted')
  for q in [parent,*list(parent.parents)]:
   if q==root:break
   directories.add(str(q.relative_to(root)))
  pending=[parent]
  while pending:
   directory=pending.pop()
   for p in sorted(directory.iterdir()):
    mode=p.lstat().st_mode;relative=str(p.relative_to(root))
    if stat.S_ISDIR(mode):directories.add(relative);pending.append(p)
    elif stat.S_ISLNK(mode):
     if p.name in('.log-objects','.log-packs'):raise ValueError('Object store substituted')
     links.append(dict(path=relative,target=os.readlink(p),metadata=metadata(p)))
    elif not stat.S_ISREG(mode):raise ValueError('Unknown special closure member; preserve it')
 return dict(format='vk-complete-streamed-session-archive-closure-v3',root=str(root),complete_session_stores=sorted(stores),directories=[dict(path=n,metadata=metadata(root/n))for n in sorted(directories)],symlinks=sorted(links,key=lambda r:r['path']),includes_unreferenced_objects=True,includes_raw_and_adjacent_files=True,maximum_body_bytes=16*B)

def iter_rows(root,layout,*,maximum_body_bytes=16*B):
 """All regular bodies, including raw/pending/adjacent files; bounded fragments."""
 if type(maximum_body_bytes)is not int or maximum_body_bytes<=0:raise ValueError('Positive body bound required')
 root=Path(root);hardlinks={}
 for directory in layout['directories']:
  name=directory['path']
  if not any(name==store or name.startswith(store+'/') for store in layout['complete_session_stores']):continue
  folder=root/name
  if folder.resolve()!=folder or not stat.S_ISDIR(folder.lstat().st_mode):raise ValueError('Closure directory substituted')
  for p in sorted(folder.iterdir()):
   s=p.lstat()
   if stat.S_ISDIR(s.st_mode)or stat.S_ISLNK(s.st_mode):continue
   if not stat.S_ISREG(s.st_mode)or p.resolve()!=p:raise ValueError('Unknown closure member')
   relative=str(p.relative_to(root));row=dict(path=relative,bytes=s.st_size,identity=list(version(s)),metadata=metadata(p))
   if s.st_nlink>1:
    key=(s.st_dev,s.st_ino)
    if key in hardlinks:row['hardlink_to']=hardlinks[key]
    else:hardlinks[key]=relative
   if s.st_size<=maximum_body_bytes:yield row;continue
   full=sha(p)
   if version(p.lstat())!=version(s):raise ValueError('Large closure source changed')
   for offset in range(0,s.st_size,maximum_body_bytes):
    yield dict(row,bytes=min(maximum_body_bytes,s.st_size-offset),source_offset=offset,source_bytes=s.st_size,source_sha256=full)

class FragmentVerifier:
 """Hash the independently extracted fragment stream across bounded carriers."""
 def __init__(self):self.current=None;self.verified_files=0
 def begin(self,row):
  if 'source_offset'not in row:return
  key={k:row[k]for k in ['path','source_bytes','source_sha256','identity','metadata']}
  if self.current is None:
   if row['source_offset']!=0:raise ValueError('Fragment union starts with a gap')
   self.current=dict(key=key,offset=0,digest=hashlib.sha256())
  if self.current['key']!=key or self.current['offset']!=row['source_offset']:raise ValueError('Fragment union reordered, duplicated or changed')
 def update(self,row,block):
  if 'source_offset'in row:self.current['digest'].update(block);self.current['offset']+=len(block)
 def end(self,row):
  if 'source_offset'not in row:return
  current=self.current
  if current['offset']!=row['source_offset']+row['bytes']or current['offset']>row['source_bytes']:raise ValueError('Fragment length differs')
  if current['offset']==row['source_bytes']:
   if current['digest'].hexdigest()!=row['source_sha256']:raise ValueError('Full independently restored fragmented file differs')
   self.verified_files+=1;self.current=None
 def finish(self):
  if self.current is not None:raise ValueError('Incomplete fragmented closure body')
  return dict(whole_fragmented_files_verified=self.verified_files)
