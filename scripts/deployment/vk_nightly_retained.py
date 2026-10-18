"""Reuse native-sealed SQL images from a terminal private capture, not live DBs.

The original job is held read-only. Only new NTFS names are created; its ledger,
failed stream and payloads remain intact. This grants no operational adoption.
"""
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess

from vk_nightly_generation import regular


def bounded_record(path, maximum=1024**2):
    with regular(path) as stream:
        before=os.fstat(stream.fileno())
        if before.st_size>maximum:raise ValueError('retained metadata exceeds bound')
        raw=stream.read(before.st_size+1);after=os.fstat(stream.fileno())
    if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(
            after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns) or len(raw)!=before.st_size:
        raise ValueError('retained metadata changed')
    return json.loads(raw),hashlib.sha256(raw).hexdigest()


def native_link(source, target, volume_device):
    source,target=Path(source),Path(target)
    request={'source':'B:/'+str(source.relative_to('/mnt/b')),
             'target':'B:/'+str(target.relative_to('/mnt/b')),'volume_device':volume_device}
    code="""
import json,os,pathlib,stat,sys
q=json.load(sys.stdin);assert os.stat('B:/').st_dev==q['volume_device']
a,b=pathlib.Path(q['source']),pathlib.Path(q['target'])
x=a.lstat();assert stat.S_ISREG(x.st_mode) and not x.st_file_attributes&0x400
assert not b.exists() and not b.is_symlink()
os.link(a,b)
y=b.lstat();assert stat.S_ISREG(y.st_mode) and not y.st_file_attributes&0x400
assert(x.st_dev,x.st_ino,x.st_size)==(y.st_dev,y.st_ino,y.st_size) and y.st_nlink>=2
print(json.dumps({'native_same_file_identity':True,'volume_device':x.st_dev}))
"""
    p=subprocess.run(['/mnt/c/Python310/python.exe','-B','-c',code],input=json.dumps(request),
                     text=True,capture_output=True,timeout=30)
    if p.returncode:raise ValueError('native retained alias failed: '+p.stderr[-800:])
    if json.loads(p.stdout)!={'native_same_file_identity':True,'volume_device':volume_device}:
        raise ValueError('native retained alias identity missing')


def retained_root(raw):
    if not re.fullmatch('/mnt/b/vk-backups/vk-nightly-capacity-[0-9a-f]{32}',str(raw)):
        raise ValueError('retained source must be an exact private capacity root')
    return Path(raw)


class RetainedSnapshots:
    def __init__(self, binding):
        self.binding=binding;self.lease=None
        root=retained_root(binding['root'])
        if root.resolve()!=root or not stat.S_ISDIR(root.lstat().st_mode):
            raise ValueError('retained root is not canonical')
        self.lease=os.open(root/'jobs/job.lock',os.O_RDONLY|os.O_NOFOLLOW)
        try:
            if not stat.S_ISREG(os.fstat(self.lease).st_mode):raise ValueError('retained lease is not regular')
            fcntl.flock(self.lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.attempt,_=bounded_record(root/'jobs/attempt.json')
            a=self.attempt
            if (a['candidate'],a['input_name'])!=(binding['candidate'],binding['input_name']):
                raise ValueError('wrong retained capture identity')
            if not re.fullmatch('input-[0-9a-f]{32}',a['input_name']):raise ValueError('unsafe retained input')
            self.folder=root/'jobs'/a['input_name']
            for path,expected in [(root/'jobs',a['binding']['root_identity']),
                                  (self.folder,a['input_identity'])]:
                info=path.lstat()
                if (not stat.S_ISDIR(info.st_mode) or path.resolve()!=path
                        or [info.st_dev,info.st_ino]!=expected):
                    raise ValueError('retained job/input directory substituted')
            manifest,h=bounded_record(self.folder/'manifest.json')
            row=a['inputs']['manifest.json']
            info=(self.folder/'manifest.json').lstat()
            if (not row['sealed'] or h!=row['sha256'] or h!=binding['manifest_sha256']
                    or [info.st_dev,info.st_ino]!=row['identity'] or info.st_size!=row['bytes']
                    or manifest['plan_sha256']!=binding['plan_sha256']
                    or manifest['scope_sha256']!=binding['source_scope_sha256']):
                raise ValueError('retained manifest binding differs')
            self.images=manifest['large_b_disk_snapshots']
            if (type(binding['snapshot_count']) is not int or not 0<binding['snapshot_count']<=1024
                    or len(self.images)!=binding['snapshot_count']):raise ValueError('retained SQL coverage differs')
            for raw,image in self.images.items():
                name=image['snapshot']
                if not re.fullmatch('sqlite-consistent-[0-9a-f]{32}\\.sqlite',name):
                    raise ValueError('unsafe retained SQL selector')
                self.check(raw)
        except BaseException:
            self.close();raise

    def check(self, raw):
        image=self.images[raw];row=self.attempt['inputs'][image['snapshot']]
        path=self.folder/image['snapshot'];info=path.lstat()
        if (not stat.S_ISREG(info.st_mode) or [info.st_dev,info.st_ino]!=row['identity']
                or not row['sealed'] or (info.st_size,row['bytes'],row['sha256'])!=(image['bytes'],image['bytes'],image['sha256'])
                or image['source']!=raw or not image['physical_b_verified'] or image['integrity']!='ok'
                or image.get('backup_api_consistent_image') is not True
                or image.get('writer_fenced') is not False or image.get('online_preparation_only') is not True):
            raise ValueError('retained image/seal/identity differs')
        return image,row,path

    def alias(self, raw, folder, job, register, *, link=native_link):
        if raw not in self.images:return None
        image,row,source=self.check(raw);target=Path(folder)/image['snapshot']
        link(source,target,self.binding['volume_device'])
        with regular(target) as stream:register(target,stream.fileno())
        origin={'root':self.binding['root'],'candidate':self.attempt['candidate'],
                'input_name':self.attempt['input_name'],'manifest_sha256':self.binding['manifest_sha256']}
        sealed=job.seal_retained_alias(target,source,row,origin)
        result=copy.deepcopy(image)
        result.update(mount_root=str(folder),local_snapshot_payload_bytes=0,
                      local_snapshot_cache_allocated_bytes=0,seconds=0,
                      retained_from=origin,new_SQLite_backup_api_capture=False)
        return result,{**sealed,'integrity':'ok','reused_native_integrity':True,'retained_from':origin}

    def close(self):
        if self.lease is not None:os.close(self.lease);self.lease=None
