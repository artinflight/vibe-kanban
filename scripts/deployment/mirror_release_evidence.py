"""Stream an explicitly hash-bound release allowlist to the retained native B store.

No archive staging, source mutation, service controls, discovery or credential
reads. The existing native object client independently restores every segment.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise ValueError('Fresh output required')
    admitted=json.loads(args.manifest.read_text())
    def guard():
        if not os.path.ismount('/mnt/vk-storage'):raise ValueError('SSD mount required')
        for root in ['/',str(args.output.parent)]:
            space=os.statvfs(root)
            if space.f_bavail*space.f_frsize<2*1024**3:raise ValueError('Storage reserve')
    guard()
    total=0
    for row in admitted['files']:
        path=Path(row['path'])
        if not path.is_absolute() or not path.is_file() or path.is_symlink():raise ValueError('Explicit regular source required')
        if sha(path)!=row['sha256']:raise ValueError('Source hash differs')
        total+=path.stat().st_size
    if total>admitted['maximum_total_bytes']:raise ValueError('Backup admission bound exceeded')
    manifest=Path('/mnt/vk-storage/vk-staging-catchup-20261028/cutover-v5-20261029/MANIFEST.private.json')
    if sha(manifest)!='703488c3caa16d48336049e9be23e60967cccb95c4a48b10466b896200d0c961':raise ValueError('Pinned native B profile required')
    cfg=json.loads(manifest.read_text())
    if sha(cfg['plan']['path'])!=cfg['plan']['sha256']:raise ValueError('Pinned native B plan required')
    plan=json.loads(Path(cfg['plan']['path']).read_text());sys.path.insert(0,plan['source_folder'])
    from vk_nightly_desktop_objects import DesktopObjects
    control=copy.deepcopy(plan['workers']['files']['desktop']);control.pop('whole_cycle_deadline_UTC',None)
    records=[]
    with DesktopObjects(control,guard=guard)as remote:
        for row in admitted['files']:
            path=Path(row['path']);restored=hashlib.sha256();parts=[];size=0
            class Sink:
                def write(self,raw):restored.update(raw);return len(raw)
            with path.open('rb')as stream:
                while raw:=stream.read(control['maximum_object_bytes']):
                    parts.append(remote.client.ensure(raw,readback_sink=Sink()));size+=len(raw)
            if restored.hexdigest()!=row['sha256'] or sha(path)!=row['sha256']:raise ValueError('Source or independent B restore differs')
            descriptor=dict(format='vk-activation-release-recovery-v1',name=row['name'],source=str(path),bytes=size,sha256=row['sha256'],segments=parts)
            records.append(dict(name=row['name'],sha256=row['sha256'],bytes=size,descriptor=remote.client.ensure((json.dumps(descriptor,sort_keys=True)+'\n').encode()),independent_native_readback_verified=True))
            print(json.dumps(dict(file=row['name'],Desktop_B_verified=True)),flush=True)
        result=dict(complete=True,B_root=control['B_root'],files=records,disk_payload_bytes_written=0)
        result['index_descriptor']=remote.client.ensure((json.dumps(result,sort_keys=True)+'\n').encode())
    with os.fdopen(os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w')as stream:
        json.dump(result,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())


if __name__=='__main__':main()
