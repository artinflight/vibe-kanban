"""Exact physical final-update fence; inert until separately instructed.

No service actions, queue writes or state rewrites. The future service owner
must first drain work, release capacity and freeze/stop the named writers.
Holding the existing capacity file lease prevents competing acquisition while
Nightly's real final update runs. Release it before candidate acquisition.
"""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import stat
import subprocess

from restart_queue_boundary import frozen, require_dispatch_quiet


def unit_state(name):
    return dict(line.split('=',1) for line in subprocess.check_output([
        'systemctl','--user','show',name,'-p','MainPID','-p','InvocationID',
        '-p','ControlGroup','-p','FreezerState','-p','ActiveState','-p','RefuseManualStart'],text=True,timeout=10).splitlines())


def members(group):
    if not group.startswith('/user.slice/') or '..' in Path(group).parts:
        raise ValueError('Exact user service cgroup required')
    root=Path('/sys/fs/cgroup')/group.lstrip('/')
    paths=list(root.rglob('cgroup.procs'))
    if not paths:
        raise ValueError('Actual service cgroup unavailable')
    return {int(value) for path in paths for value in path.read_text().split()}


class WriterFence:
    def __init__(self,binding,before,released,*,inspect=unit_state,processes=members):
        self.binding=binding;self.before=require_dispatch_quiet(before)
        self.released=released;self.inspect=inspect;self.processes=processes
        self.fd=None;self.lock_identity=None
        if (released.get('owned') is not False or released.get('protocolVersion')!=1
                or released.get('state',{}).get('version')!=1
                or not released.get('state',{}).get('epoch')):
            raise ValueError('Actual authenticated released-ownership RPC receipt required')
        if any(goal.get('grant') is not None for goal in released['state']['goals'].values()):
            raise ValueError('Capacity grants not drained')

    def controls(self):
        for name,expected in self.binding['frozen_units'].items():
            value=self.inspect(name)
            if (value.get('ActiveState')!='active' or value.get('FreezerState')!='frozen'
                    or value.get('MainPID')!=str(expected['pid'])
                    or value.get('InvocationID')!=expected['invocation']
                    or self.processes(value['ControlGroup'])!={expected['pid']}):
                raise ValueError('Actual named writer not safely frozen/drained: '+name)
        for name in self.binding['stopped_units']:
            value=self.inspect(name)
            if (value.get('ActiveState')!='inactive' or value.get('MainPID')!='0'
                    or value.get('ControlGroup')):
                raise ValueError('Owned ingress writer not fully stopped/drained: '+name)
        if self.binding.get('stopped_unit_start_holds'):
            from vk_restart_ingress_hold import verify
            verify(self.binding['stopped_unit_start_holds'],state=self.inspect)
        route=Path(self.binding['route_path'])
        if route.read_bytes()!=self.binding['maintenance_bytes'].encode():
            raise ValueError('Exact maintenance ingress fence missing')
        database=Path(self.binding['database'])
        info=database.stat()
        if (str(database.resolve())!=self.binding['database_target']
                or [info.st_dev,info.st_ino]!=self.before['database_identity']):
            raise ValueError('Enrolled current database replaced')
        state_path=Path(self.binding['capacity_state'])
        if state_path.is_symlink():
            raise ValueError('Released capacity state is an alias')
        persisted=json.loads(state_path.read_bytes())
        # Actual routes/capacity.rs::wire_state changes ONLY version to1.
        # Keep the durable v2 record unchanged, including initialization data.
        if (persisted.get('version')!=self.binding['capacity_persisted_version']
                or dict(persisted,version=1)!=self.released['state']):
            raise ValueError('Released capacity epoch/revision/state changed')
        return True

    def check(self):
        if self.fd is None:
            raise ValueError('Actual retained capacity lease required')
        info=os.fstat(self.fd);current=Path(self.binding['capacity_lock']).lstat()
        if (info.st_dev,info.st_ino)!=(current.st_dev,current.st_ino) or self.lock_identity!=(info.st_dev,info.st_ino):
            raise ValueError('Capacity lease inode changed')
        self.controls()
        return frozen(self.binding['database'],self.before,incumbent_frozen=True,consumers_quiet=True)

    @contextmanager
    def held(self):
        if self.fd is not None:
            raise ValueError('One exact fence owner required')
        self.controls()  # No lease acquisition while current work is active.
        path=Path(self.binding['capacity_lock'])
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
        try:
            info=os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_nlink!=1:
                raise ValueError('Actual owned capacity lock required')
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.fd=fd;self.lock_identity=(info.st_dev,info.st_ino)
            self.check();yield self.check;self.check()
        finally:
            self.fd=None;self.lock_identity=None;os.close(fd)
