#!/usr/bin/env python3
"""Opt-in tiny real B chunk/SQLite restoration; never a whole-plan acceptance."""
import argparse
import ast
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import uuid

from vk_nightly_b_job import WINDOWS_READBACK, WINDOWS_SQLITE_INPUT
from vk_prep_common import save, storage


RESTORE = WINDOWS_READBACK + r'''
target=p.parent.parent/('restore-'+m['generation']);target.mkdir()
for key,row in m['entries'].items():
 assert not pathlib.PurePosixPath(key).is_absolute() and '..' not in pathlib.PurePosixPath(key).parts
 out=target/key;out.parent.mkdir(parents=True,exist_ok=True)
 if row['kind']=='file':
  with out.open('xb') as f:
   for b in decoded(p/'objects'/row['sha256'],row['sha256'],row['bytes'],encoding):f.write(b)
   f.flush();os.fsync(f.fileno())
  assert hashlib.sha256(out.read_bytes()).hexdigest()==row['sha256']
with sqlite3.connect((target/'fixture/state.sqlite').as_uri()+'?mode=ro&immutable=1',uri=True) as db:
 assert db.execute('PRAGMA integrity_check').fetchone()==('ok',)
 assert db.execute('SELECT value FROM settings').fetchone()==(r['expected'],)
print(json.dumps({'restored':True,'restored_files':sum(x['kind']=='file' for x in m['entries'].values()),
 'sqlite_value':r['expected'],'restored_path':str(target)}))
'''

WSL = r'''
import hashlib,io,json,os,pathlib,shutil,sqlite3,subprocess,sys,types
from contextlib import contextmanager
r=json.loads(sys.stdin.read());assert os.getuid()==1000
assert hashlib.sha256(r['source'].encode()).hexdigest()==r['source_sha256']
module=types.ModuleType('vk_nightly_generation');sys.modules[module.__name__]=module
exec(compile(r['source'],'vk_nightly_generation.py','exec'),module.__dict__)
assert hashlib.sha256(r['lifecycle'].encode()).hexdigest()==r['lifecycle_sha256']
life=types.ModuleType('vk_nightly_lifecycle');sys.modules[life.__name__]=life
exec(compile(r['lifecycle'],'vk_nightly_lifecycle.py','exec'),life.__dict__)
root=pathlib.Path('/mnt/b/vk-backups/vk-nightly-efficiency-20261017')/r['fixture']
assert root.name.startswith('fixture-') and len(root.name)==40
mount=subprocess.check_output(['findmnt','-n','-T','/mnt/b','-o','SOURCE,FSTYPE'],text=True).split()
assert mount[0].rstrip(chr(92))=='B:' and mount[1]=='9p'
assert shutil.disk_usage('/mnt/b').free>6*1024**3+16*1024**2
root.parent.mkdir(exist_ok=True)
if not r['resume']:root.mkdir();(root/'store').mkdir()
store_root=root/'store'
proofs={};expected='before';readbacks=[]
def windows(code,request):
 completed=subprocess.run(['/mnt/c/Python310/python.exe','-B','-c',code],input=json.dumps(request),text=True,capture_output=True,timeout=120)
 if completed.returncode:raise RuntimeError('native Windows fixture verification failed: '+completed.stderr[-1000:])
 return [json.loads(x) for x in completed.stdout.splitlines() if x.strip()]
def win(path):return 'B:/'+path.relative_to('/mnt/b').as_posix()
def image(value):
 global expected
 expected=value
 target=root/('consistent-'+value+'.sqlite')
 if not target.exists():
  with sqlite3.connect(':memory:') as source:
   source.execute('CREATE TABLE settings(value TEXT)');source.execute('INSERT INTO settings VALUES(?)',(value,));source.commit()
   with sqlite3.connect(target) as destination:source.backup(destination)
 else:
  with sqlite3.connect(target.as_uri()+'?mode=ro&immutable=1',uri=True) as db:
   assert db.execute('SELECT value FROM settings').fetchone()==(value,)
 data=target.read_bytes();h=hashlib.sha256(data).hexdigest()
 proof=windows(r['sqlite_input'],{'path':win(target),'volume_device':r['volume_device'],'bytes':len(data),'sha256':h})[0]
 assert proof=={'sha256':h,'bytes':len(data),'integrity':'ok'}
 proofs['/fixture/state.sqlite']={**proof,'volume_device':r['volume_device']}
 return data
def readback(folder,manifest):
 request={'folder':win(folder),'volume_device':r['volume_device'],'manifest_sha256':hashlib.sha256(module.encoded(manifest)).hexdigest(),
          'scope':store.scope,'source_prefix':'/','databases':['/fixture/state.sqlite'],'expected':expected}
 rows=windows(r['restore'],request);assert rows[-1]['restored']
 readbacks.append(rows[-1]);return rows[0]
store=module.NightlyStore(store_root,'a'*64,lambda:pathlib.Path('/mnt/b'),independent_readback=readback,object_encoding=module.CHUNKED)
if not r['resume']:store.enroll_empty()
current=store.current()
if r['resume']:
 assert current is not None;store.verify(current)
 # Reconcile ONLY this fixture's verified earlier restore, preserving all bytes.
 old_restore=store_root/('restore-'+current['generation'])
 if old_restore.exists():
  assert old_restore.is_dir() and not old_restore.is_symlink()
  for key,item in current['entries'].items():
   if item['kind']=='file':
    original=old_restore/key
    assert original.is_file() and not original.is_symlink() and original.stat().st_size==item['bytes']
    assert hashlib.sha256(original.read_bytes()).hexdigest()==item['sha256']
  old_restore.rename(root/old_restore.name)
 item=current['entries']['fixture/history.jsonl']
 history=b''.join(module.object_blocks(store_root/current['generation']/'objects'/item['sha256'],item['sha256'],item['bytes'],module.CHUNKED))
else:history=os.urandom(2*module.CHUNK_BYTES)+b'partial binary tail\xff\x00'
def row(data):return {'kind':'file','bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),
                     'mode':0o600,'uid':1000,'gid':1000,'mtime_ns':123,'xattrs':{}}
files={'fixture/state.sqlite':image('before'),'fixture/history.jsonl':history,
       'fixture/dirty-untracked.txt':b'original local work','fixture/attachment.bin':b'exact attachment bytes'}
if r['resume']:first={'generation':current['generation']}
else:first=store.advance([(key,row(data),io.BytesIO(data)) for key,data in files.items()],(),expected_previous=None,
 reserve_bytes=8*1024**2,capture_context={'nightly_database_integrity':dict(proofs)})
history+=b'\noriginal complete next record\n';files['fixture/state.sqlite']=image('after');files['fixture/history.jsonl']=history
second=store.advance([(key,row(data),io.BytesIO(data)) for key,data in files.items()],(),expected_previous=first['generation'],
 reserve_bytes=8*1024**2,retention_adopted=True,capture_context={'nightly_database_integrity':dict(proofs)})
assert not (store_root/first['generation']).exists()
# The final native restore starts only after the predecessor is physically gone.
saved=root/('restore-'+second['generation']);assert saved.exists()
# Keep the earlier readback outputs. A distinct independent post-retirement path is used.
post=r['restore'].replace("'restore-'+m['generation']","'post-retirement-'+m['generation']")
m=store.current();request={'folder':win(store_root/m['generation']),'volume_device':r['volume_device'],
 'manifest_sha256':hashlib.sha256(module.encoded(m)).hexdigest(),'scope':store.scope,'source_prefix':'/',
 'databases':['/fixture/state.sqlite'],'expected':'after'}
last=windows(post,request)[-1];assert last['restored'] and second['stored_changed_bytes']<65536
def verify_only(folder,manifest):
 request={'folder':win(folder),'volume_device':r['volume_device'],'manifest_sha256':hashlib.sha256(module.encoded(manifest)).hexdigest(),
          'scope':store.scope,'source_prefix':'/','databases':['/fixture/state.sqlite'],'expected':'after'}
 return windows(r['verify'],request)[0]
store.independent_readback=verify_only
jobs=root/'jobs';jobs.mkdir();job=life.NightlyJob(jobs,store,capture_limit_bytes=1024**2,changed_limit_bytes=8*1024**2);job.enroll_empty()
files['fixture/history.jsonl']+=b'\nnext complete job record\n'
entries={key:row(data) for key,data in files.items()}
class Provider:
 records={'fixture':{'result':{'parent':None}}}
 def verify(self,capture_id):return {'scope_sha256':store.scope,'full_current_state':True,'entries':entries,'nightly_database_integrity':dict(proofs)}
 @contextmanager
 def file_members(self,capture_id,selected):yield ((key,io.BytesIO(files[key])) for key in selected)
def factory(folder,register,seal,*,parent):
 target=folder/'fixture-input.json'
 with target.open('xb') as f:register(target,f.fileno());f.write(b'owned fixture input');f.flush();os.fsync(f.fileno())
 seal(target);return Provider(),'fixture',{'parent':None}
link=os.link
def interrupted(source,target,**kwargs):
 link(source,target,**kwargs)
 if pathlib.Path(target).name.startswith('chunk-'):raise OSError('deliberate owned B chunk interruption')
try:
 os.link=interrupted
 failed=job.run(factory,retention_adopted=True,reserve_bytes=module.MAX_INDEX+16*1024**2)
 assert not failed['passed'] and not (store_root/job.read()['candidate']/'manifest.json').exists()
finally:os.link=link
job.reconcile(retention_adopted=True,inputs_quiescent=True)
completed=job.run(factory,retention_adopted=True,reserve_bytes=module.MAX_INDEX+16*1024**2);assert completed['passed']
m=store.current();request.update(folder=win(store_root/m['generation']),manifest_sha256=hashlib.sha256(module.encoded(m)).hexdigest())
last=windows(post,request)[-1];assert last['restored']
print(json.dumps({'passed':True,'fixture_root':win(root),'source_sha256':r['source_sha256'],
 'lifecycle_sha256':r['lifecycle_sha256'],'first_generation':first['generation'],'current_generation':m['generation'],
 'old_fixture_generation_removed':True,'post_retirement_restore':last,'stored_delta_bytes':second['stored_changed_bytes'],
 'full_history_bytes':len(files['fixture/history.jsonl']),'first_append_history_bytes':len(history),
 'real_B_interrupted_job_reconciled':True,'fixture_provider_only':True,
 'production_plan_or_backups_changed':False,'whole_plan_accepted':False}))
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--health',required=True,type=Path)
    parser.add_argument('--run-desktop-fixture',action='store_true')
    parser.add_argument('--resume-fixture')
    args=parser.parse_args()
    if not args.run_desktop_fixture:raise ValueError('explicit tiny Desktop fixture opt-in required')
    for script in (WSL,RESTORE,WINDOWS_SQLITE_INPUT):ast.parse(script)
    root=storage(args.root);root.mkdir(mode=0o700,exist_ok=True)
    health=json.loads(args.health.read_text())
    age=(datetime.now(timezone.utc)-datetime.fromisoformat(health['At'].replace('Z','+00:00'))).total_seconds()
    if not 0<=age<=300 or health.get('SmartPassed') is not True or health.get('NativeExit')!=0:
        raise ValueError('fresh successful passive B health evidence required')
    source=Path(__file__).with_name('vk_nightly_generation.py').read_text()
    lifecycle=Path(__file__).with_name('vk_nightly_lifecycle.py').read_text()
    if args.resume_fixture and not re.fullmatch('fixture-[0-9a-f]{32}',args.resume_fixture):
        raise ValueError('exact owned fixture selector required')
    payload={'source':source,'source_sha256':hashlib.sha256(source.encode()).hexdigest(),
             'fixture':args.resume_fixture or 'fixture-'+uuid.uuid4().hex,'resume':bool(args.resume_fixture),
             'restore':RESTORE,'verify':WINDOWS_READBACK,'sqlite_input':WINDOWS_SQLITE_INPUT,
             'lifecycle':lifecycle,'lifecycle_sha256':hashlib.sha256(lifecycle.encode()).hexdigest()}
    save(root/'desktop-fixture-attempt.private.json',{'fixture':payload['fixture'],'source_sha256':payload['source_sha256'],
         'resume':payload['resume'],'status':'starting; reconcile exact fixture after any transport uncertainty'})
    # Existing Desktop identity and existing unprivileged WSL boundary; no new
    # installation, account, daemon, mount, credential or security setting.
    remote='import json,os,subprocess,sys\nr='+repr(payload)+'\nr["volume_device"]=os.stat("B:/").st_dev\n'
    loader="import base64;exec(base64.b64decode('"+base64.b64encode(WSL.encode()).decode()+"'))"
    remote+='p=subprocess.run(["wsl.exe","-d","VK-Candidate-20261009","--exec","setpriv","--reuid","1000","--regid","1000","--clear-groups","python3","-B","-S","-c",'+repr(loader)+'],input=json.dumps(r),text=True,capture_output=True,timeout=600)\n'
    remote+='sys.stdout.write(p.stdout);sys.stderr.write(p.stderr);raise SystemExit(p.returncode)\n'
    result=subprocess.run(['ssh','-T','-o','BatchMode=yes','-o','ConnectTimeout=15','-o','StrictHostKeyChecking=yes',
                           '-o','ControlMaster=no','-o','ControlPath=none','desktop','python','-'],
                          input=remote,text=True,capture_output=True,timeout=660)
    (root/'desktop-fixture.stderr').write_text(result.stderr)
    if result.returncode:raise RuntimeError('Desktop fixture failed; retain its output and reconcile: '+result.stderr[-1000:])
    value=json.loads(result.stdout);save(root/'desktop-fixture-result.private.json',value)
    print(json.dumps(value))


if __name__=='__main__':main()
