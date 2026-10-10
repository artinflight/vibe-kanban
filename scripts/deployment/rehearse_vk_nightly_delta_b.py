"""Fresh real-B compressed/delta fixture. No production or schedule adoption."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid

from rehearse_vk_nightly_real_b import desktop
from vk_change_journal import scope
from vk_nightly_capture_adapter import run_capture
from vk_prep_common import identity, storage


def main():
    local=storage('/mnt/vk-storage/vk-restart-safeguards-20261009')/('B-delta-'+uuid.uuid4().hex);local.mkdir()
    source=local/'source';source.mkdir();dbpath=source/'state.sqlite'
    with sqlite3.connect(dbpath) as db:
        db.execute('CREATE TABLE retained(value TEXT)');db.execute("INSERT INTO retained VALUES('before')")
    (source/'history').write_bytes(b'preserved historical work\n'*50000)
    (source/'linked').write_bytes(b'linked content');os.link(source/'linked',source/'alias')
    (source/'deleted').write_bytes(b'fixture deletion')
    plan={'sources':[str(source)],'sqlite_snapshots':[str(dbpath)],'excluded_rebuildable_directories':[]}
    remote='B:/vk-backups/vk-nightly-delta-20261010-'+uuid.uuid4().hex
    volume=desktop("import json,os;print(json.dumps(os.stat('B:/').st_dev))")
    config={'wsl_root':'/mnt/b/'+remote[3:],'scope_sha256':identity(plan),'plan_identity':identity(plan),
        'source_scope_sha256':identity(scope(plan)),'source_prefix':str(source),'volume_device':volume,
        'retention_adopted':True,'capture_limit_bytes':32*1024**2,'changed_limit_bytes':16*1024**2,
        'reserve_bytes':320*1024**2,'snapshot_limit_bytes':16*1024**2,'snapshot_timeout_seconds':60,
        'readback_timeout_seconds':90,'job_timeout_seconds':240,'staging':str(local/'control'),
        'sshfs_binary':'/mnt/vk-storage/vk-runtime-backup-20261009/sshfs-tool/usr/bin/sshfs',
        'fusermount_binary':'/usr/bin/fusermount','inventoried_databases':[str(dbpath)],
        'object_encoding':'zlib-1-v1','transport':'content-delta-v1','async_writes':True}
    report={'local':str(local),'remote':remote,'production_changed':False,'schedule_enabled':False,'runs':[]}
    started=time.monotonic()
    try:
        for n in range(2):
            if n:
                with sqlite3.connect(dbpath) as db:db.execute("INSERT INTO retained VALUES('second')")
                (source/'deleted').unlink()
            result=run_capture(config,plan,enroll_fresh=n==0);report['runs'].append(result)
            if not result['result']['passed']:raise ValueError(str(result))
        verify=r'''
import hashlib,json,pathlib,sqlite3,zlib
p=pathlib.Path(ROOT);s=p/'store';q=json.loads((s/'current.json').read_text());g=s/q['generation'];m=json.loads((g/'manifest.json').read_text())
assert m['parent'] is None and m['object_encoding']=='zlib-1-v1'
assert m['capture_context']['reused_files']==1 and m['capture_context']['reused_content_bytes']==1300000
assert 'deleted' not in m['entries']
assert len([x for x in s.iterdir() if x.name.startswith('generation-')])==1
assert {x.name for x in (p/'jobs').iterdir()}=={'job-scope.json','job.lock'}
for h,size in {r['sha256']:r['bytes'] for r in m['entries'].values() if r['kind']=='file'}.items():
 decoder=zlib.decompressobj();count=0;digest=hashlib.sha256()
 with (g/'objects'/h).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):
   while b:
    data=decoder.decompress(b,1048576);b=decoder.unconsumed_tail;count+=len(data);assert count<=size;digest.update(data)
 assert decoder.eof and not decoder.unused_data and count==size and digest.hexdigest()==h
r=m['entries']['state.sqlite'];target=p/'recovered-fixture.sqlite'
with target.open('xb') as f:f.write(zlib.decompress((g/'objects'/r['sha256']).read_bytes()))
assert hashlib.sha256(target.read_bytes()).hexdigest()==r['sha256']
with sqlite3.connect(target.as_uri()+'?mode=ro&immutable=1',uri=True) as db:
 assert db.execute('SELECT value FROM retained ORDER BY rowid').fetchall()==[('before',),('second',)]
 assert db.execute('PRAGMA integrity_check').fetchall()==[('ok',)]
print(json.dumps({'passed':True,'independent_current_recovery':True,'generations':1,'reused_history_bytes':1300000,
 'restore':str(target),'B_bytes':sum(x.stat().st_size for x in p.rglob('*') if x.is_file())}))
'''
        report['recovery']=desktop('ROOT='+repr(remote)+'\n'+verify)
        report['passed']=True
    finally:
        report['seconds']=time.monotonic()-started
        (local/'acceptance.safe.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({'receipt':str(local/'acceptance.safe.json'),'passed':report.get('passed',False)}),flush=True)


if __name__=='__main__':main()
