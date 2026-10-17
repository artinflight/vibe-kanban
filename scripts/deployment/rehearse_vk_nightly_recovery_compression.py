"""Lossless B-only repack of the retained, CLOSED real-DB recovery fixture.

Independent bounded recovery/full hash/SQLite verification precedes optional
exact redundant-file retirement. This is not normal-backup adoption/cleanup.
The same restore implementation remains callable with --restore-only.
"""
import argparse
import json
from pathlib import Path
import subprocess

from vk_archive_store import SSH
from vk_prep_common import storage


NATIVE = r'''
import ctypes,hashlib,json,os,pathlib,re,shutil,sqlite3,subprocess,time,uuid
from contextlib import closing
ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x40)
started=time.monotonic(); expected=REQUEST['expected']; source=pathlib.Path(expected['restore_path'])
folder=source.parent
assert folder.as_posix().startswith('B:/vk-backups/vk-nightly-real-db-recovery-20261010-')
assert os.stat('B:/').st_dev==2360624474
for p in [folder,*folder.parents]:
 assert not p.lstat().st_file_attributes & 0x400,'reparse ancestor'
def pin(p):
 s=p.lstat();assert not s.st_file_attributes & 0x400,'reparse file';return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)
def digest(p):
 before=pin(p);h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1048576),b''):h.update(block)
 assert pin(p)==before,'file changed while hashing'
 return h.hexdigest()
def wsl(p):return '/mnt/b/'+p.relative_to('B:/').as_posix()
def command(args):
 return ['wsl.exe','-d','VK-Candidate-20261009','--exec','setpriv','--reuid','1000','--regid','1000','--clear-groups',
         '/usr/bin/nice','-n','19','/usr/bin/ionice','-c','3','/usr/bin/zstd',*args]
def verify_sqlite(target):
 with closing(sqlite3.connect(target.as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
  assert db.execute('PRAGMA integrity_check').fetchall()==[('ok',)]
  for key in ('page_count','page_size','schema_version'):
   assert db.execute('PRAGMA '+key).fetchone()[0]==expected[key]
def save_receipt(receipt,report,predecessor=None):
 stage=folder/('compression-'+uuid.uuid4().hex+'.new')
 with stage.open('x') as f:
  f.write(json.dumps(report,indent=2));f.flush();os.fsync(f.fileno())
 if predecessor is None:assert not receipt.exists(),'unexpected receipt'
 else:assert digest(receipt)==predecessor,'receipt substituted'
 os.replace(stage,receipt)
 return digest(receipt)
def recover(artifact,archive_hash,target):
 assert digest(artifact)==archive_hash,'compressed artifact hash mismatch'
 assert shutil.disk_usage('B:/').free>expected['bytes']+2*1024**3
 process=subprocess.Popen(command(['-d','-c','--',wsl(artifact)]),stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
 h=hashlib.sha256();size=0
 try:
  with target.open('xb') as out:
   for block in iter(lambda:process.stdout.read(1048576),b''):
    size+=len(block);assert size<=expected['bytes'],'decompression exceeds exact image bound'
    out.write(block);h.update(block)
   assert process.wait(timeout=30)==0,'decompression failed'
   out.flush();os.fsync(out.fileno())
  assert size==expected['bytes'] and h.hexdigest()==expected['sha256']
  assert digest(target)==expected['sha256'],'independent restore readback mismatch'
  verify_sqlite(target)
  return {'bytes':size,'sha256':h.hexdigest(),'integrity':'ok','identity':pin(target)}
 finally:
  if process.poll() is None:process.kill()
  process.wait();process.stdout.close()
if REQUEST['restore_only']:
 r=json.loads((folder/'compression.safe.json').read_text());artifact=pathlib.Path(r['artifact'])
 assert artifact.parent==folder and artifact.name.startswith('logs_2.private-') and artifact.suffix=='.zst'
 target=folder/('restored-'+uuid.uuid4().hex+'.sqlite')
 proof=recover(artifact,r['archive_sha256'],target)
 print(json.dumps({'passed':True,'restore_path':str(target),**proof}));raise SystemExit(0)
assert source.name=='logs_2.private.sqlite' and source.stat().st_size==expected['bytes']
source_pin=pin(source);assert digest(source)==expected['sha256']
assert not source.stat().st_file_attributes & 0x400
receipt=folder/'compression.safe.json';predecessor=None
if REQUEST['resume_temporary']:
 predecessor=digest(receipt);report=json.loads(receipt.read_text());temporary=pathlib.Path(REQUEST['resume_temporary']);artifact=pathlib.Path(report['artifact'])
 assert temporary.parent==folder and re.fullmatch('verified-restore-[0-9a-f]{32}\\.sqlite',temporary.name)
 assert artifact.parent==folder and re.fullmatch('logs_2.private-[0-9a-f]{32}\\.sqlite.zst',artifact.name)
 assert report['passed'] and report['retired']==[] and report['original_bytes']==expected['bytes'] and report['original_sha256']==expected['sha256']
 assert tuple(report['source_identity'])==source_pin
 proof=report['independent_recovery'];assert pin(temporary)==tuple(proof['identity']) and digest(temporary)==expected['sha256']
 verify_sqlite(temporary);archive_hash=report['archive_sha256'];assert digest(artifact)==archive_hash and artifact.stat().st_size==report['archive_bytes']
else:
 assert not receipt.exists(),'never overwrite existing receipt'
 artifact=folder/('logs_2.private-'+uuid.uuid4().hex+'.sqlite.zst');temporary=folder/('verified-restore-'+uuid.uuid4().hex+'.sqlite')
 assert shutil.disk_usage('B:/').free>2*expected['bytes']+2*1024**3
 with artifact.open('xb') as out:
  p=subprocess.run(command(['-T1','-3','--no-progress','-c','--',wsl(source)]),stdout=out,stderr=subprocess.PIPE,timeout=240)
  assert p.returncode==0,'compression failed'
  out.flush();os.fsync(out.fileno())
 assert pin(source)==source_pin and digest(source)==expected['sha256']
 archive_hash=digest(artifact);proof=recover(artifact,archive_hash,temporary)
 report={'passed':True,'artifact':str(artifact),'archive_bytes':artifact.stat().st_size,'archive_sha256':archive_hash,
  'original_bytes':expected['bytes'],'original_sha256':expected['sha256'],'normal_restore_command':'source harness --restore-only using unchanged original restore receipt',
  'independent_recovery':proof,'source_identity':source_pin,'source_mode':oct(source.stat().st_mode),
  'source_attributes':source.stat().st_file_attributes,'retired':[],'production_or_prior_backup_changed':False}
# Save the verified recovery binding BEFORE any exact redundant unlink.
report['verified_restore_path']=str(temporary)
predecessor=save_receipt(receipt,report,predecessor)
if REQUEST['retire']:
 assert digest(artifact)==archive_hash and digest(temporary)==expected['sha256']
 assert pin(source)==source_pin and digest(source)==expected['sha256']
 note=folder/'logs_2.private.sqlite.RESTORED-FROM-ZSTD.txt'
 with note.open('x') as f:
  f.write('Verified equivalent: '+str(artifact)+'\nSHA256 compressed: '+archive_hash+'\nRaw bytes/SHA256: '+str(expected['bytes'])+' / '+expected['sha256']+'\nRecovery: retained source harness --restore-only and original restore receipt. No production restore.\n');f.flush();os.fsync(f.fileno())
 # Only these two closed fixture copies, never an archive/backup glob.
 assert pin(source)==source_pin;source.unlink();report['retired'].append(str(source))
 assert pin(temporary)==tuple(proof['identity']);temporary.unlink();report['retired'].append(str(temporary))
 assert digest(artifact)==archive_hash,'verified equivalent must survive retirement'
report['elapsed_seconds']=time.monotonic()-started;report['free_bytes']=shutil.disk_usage('B:/').free
save_receipt(receipt,report,predecessor);print(json.dumps(report))
'''


def run(receipt,output,*,retire=False,restore_only=False,resume_temporary=None):
    expected=json.loads(receipt.read_text())
    if (expected.get('passed') is not True or expected.get('bytes')!=4734447616
            or expected.get('sha256')!='f95d0c03678ca475bee39ee5df548c3b4b255731c6611fb3f11af3d5fa164de4'):
        raise ValueError('exact accepted real-DB fixture binding required')
    if resume_temporary and (not retire or restore_only):raise ValueError('resume requires exact retirement mode')
    request={'expected':expected,'retire':retire,'restore_only':restore_only,'resume_temporary':resume_temporary}
    result=subprocess.run(SSH,input='REQUEST='+repr(request)+'\n'+NATIVE,text=True,capture_output=True,timeout=450)
    if result.returncode:raise RuntimeError('B-only fixture operation blocked: '+result.stderr[-2000:])
    report=json.loads(result.stdout)
    with storage(output).open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(report))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--receipt',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--retire-redundant-representations',action='store_true')
    p.add_argument('--restore-only',action='store_true');p.add_argument('--resume-verified-temporary');a=p.parse_args()
    if a.restore_only and a.retire_redundant_representations:p.error('restore-only cannot retire')
    run(a.receipt,a.output,retire=a.retire_redundant_representations,restore_only=a.restore_only,
        resume_temporary=a.resume_verified_temporary)
