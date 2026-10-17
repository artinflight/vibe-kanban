"""Explicit bounded index-scale rehearsal; no production/remote payloads.

Run under the same 3GiB ceiling as the nightly producer on mounted SSD.
One shared byte models content deduplication; every named row remains distinct.
This verifies index scale, not actual production content or restore acceptance.
"""
import argparse
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import resource
import time

from vk_nightly_generation import CHUNKED, MAX_INDEX, NightlyStore, encoded, encoding_summary
from vk_nightly_json import load_index
from vk_nightly_lifecycle import NightlyJob
from vk_nightly_archive_index import validate_backup_entries
from vk_prep_common import storage


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--entries',type=int,default=1219860)
    args=parser.parse_args()
    if not 1219860<=args.entries<=1500000:raise ValueError('measured scope through reviewed finite ceiling required')
    source_names=('vk_nightly_generation.py','vk_nightly_lifecycle.py','vk_nightly_archive_index.py','vk_nightly_json.py','rehearse_vk_nightly_index_scale.py')
    source_pins={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in source_names}
    root=storage(args.root);root.mkdir(mode=0o700,exist_ok=False)
    (root/'store').mkdir();(root/'jobs').mkdir()
    started=time.monotonic();checks=[];runs=0
    def phase(name):
        value={'phase':name,'seconds':time.monotonic()-started,'max_RSS_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
        (root/'progress.safe.json').write_text(json.dumps(value)+'\n')
    phase('starting')
    def readback(folder,manifest):
        # Parse actual saved bytes afresh; inspect every row and hash the full
        # on-disk index, independently of the producer's in-memory dictionary.
        phase('independent index readback')
        with (folder/'manifest.json').open('rb') as f:
            read,checksum=load_index(f)
        validate_backup_entries(read['entries'])
        assert len(read['entries'])==args.entries
        assert all(row['bytes']==1 and row['sha256']==hashlib.sha256(b'x').hexdigest()
                   for row in read['entries'].values())
        checks.append({'generation':read['generation'],'entries':len(read['entries']),
                       'manifest_bytes':(folder/'manifest.json').stat().st_size,'sha256':checksum})
        return {'physical_b_verified':True,'generation':read['generation'],
                'scope_sha256':read['scope_sha256'],'manifest_sha256':checksum}
    store=NightlyStore(root/'store','a'*64,lambda:root,object_encoding=CHUNKED,independent_readback=readback)
    store.enroll_empty();job=NightlyJob(root/'jobs',store,capture_limit_bytes=1024,changed_limit_bytes=1024**2);job.enroll_empty()
    prefix='mnt/vk-storage/worktrees/604d-vk-nightly-backu/_vibe_kanban_repo/packages/web-core/node_modules/dependency/dist/'
    class Provider:
        records={'fixture':{'result':{'parent':None}}}
        def __init__(self,rows):self.rows=rows
        def verify(self,capture_id):return {'scope_sha256':store.scope,'full_current_state':True,'entries':self.rows}
        @contextmanager
        def file_members(self,capture_id,selected):yield ((key,io.BytesIO(b'x')) for key in selected)
    def factory(folder,register,seal,*,parent):
        nonlocal runs
        runs+=1;phase('building source proof '+str(runs))
        checksum=hashlib.sha256(b'x').hexdigest()
        rows={prefix+f'original-source-{i:07d}.js':{'kind':'file','mode':0o644,'uid':1000,'gid':1000,
            'mtime_ns':1792199000000000000+i+(1 if runs>1 and i==0 else 0),
            'xattrs':{},'bytes':1,'sha256':checksum} for i in range(args.entries)}
        validate_backup_entries(rows);phase('source proof validated '+str(runs))
        path=folder/'input'
        with path.open('xb') as f:register(path,f.fileno());f.write(b'owned');f.flush();os.fsync(f.fileno())
        seal(path);return Provider(rows),'fixture',{'parent':None}
    result=job.run(factory,retention_adopted=True,reserve_bytes=MAX_INDEX+2*1024**2)
    if not result['passed']:raise ValueError(result)
    current=store.current();assert len(current['entries'])==args.entries
    del current
    second=job.run(factory,retention_adopted=True,reserve_bytes=MAX_INDEX+2*1024**2)
    if not second['passed']:raise ValueError(second)
    assert source_pins=={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in source_names},'source changed during rehearsal'
    receipt={'passed':True,'entries':args.entries,'checks':checks,'seconds':time.monotonic()-started,
             'max_RSS_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
             'previous_retired':not (store.root/result['generation']).exists(),
             'production_or_B_changed':False,'synthetic_provider':True,
             'source_sha256':source_pins}
    (root/'result.safe.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))


if __name__=='__main__':main()
