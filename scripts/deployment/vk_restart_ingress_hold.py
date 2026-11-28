"""Owned runtime-only start holds for deliberately stopped ingress writers.

No boot-recovery policy change. The controller installs and removes only its
exact operation-specific drop-ins; systemd rejects outside manual starts while
its ordinary stop/backup boundary is held. Import is inert.
"""
from pathlib import Path
import hashlib
import os
import stat
import subprocess


def inspect(unit):
    values=subprocess.check_output(['systemctl','--user','show',unit,'-p','RefuseManualStart','-p','MainPID','-p','ActiveState'],text=True,timeout=10)
    return dict(line.split('=',1) for line in values.splitlines())


def reload():subprocess.run(['systemctl','--user','daemon-reload'],check=True,timeout=20)


def verify(records,*,state=inspect):
    for row in records:
        path=Path(row['path']);info=path.lstat()
        if (path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid()
                or info.st_nlink!=1 or info.st_mode&0o077
                or hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']
                or state(row['unit']).get('RefuseManualStart')!='yes'):
            raise ValueError('Owned ingress start hold changed: '+row['unit'])


def install(records,*,record=lambda *_:None,state=inspect,refresh=reload):
    for row in records:
        if state(row['unit']).get('RefuseManualStart')!='no':
            raise ValueError('Unrelated preexisting service start hold')
        path=Path(row['path'])
        if path.exists() or path.is_symlink():raise ValueError('Preserve existing runtime drop-in')
    for row in records:
        path=Path(row['path']);path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        if path.parent.is_symlink() or path.parent.stat().st_uid!=os.getuid():raise ValueError('Owned literal runtime drop-in directory required')
        raw=row['body'].encode()
        if hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ValueError('Exact start-hold source required')
        record('ingress-start-hold-requested',row)  # durable intent precedes create
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    refresh();verify(records,state=state)


def release(records,*,refresh=reload):
    existing=[]
    for row in records:
        path=Path(row['path'])
        if not path.exists() and not path.is_symlink():continue
        info=path.lstat()
        if (path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid()
                or info.st_nlink!=1 or info.st_mode&0o077
                or hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']):
            raise ValueError('Unknown runtime start hold; preserve it')
        existing.append(path)
    for path in existing:path.unlink()
    if existing:refresh()
