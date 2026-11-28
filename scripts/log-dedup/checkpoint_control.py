"""Private operator controls for a finite worker, applied only between batches.

No signals, forced unlocks, subprocess launches, backup calls or implicit resumes.
The batch adapter is responsible for proving that its backup contexts are closed.
"""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import time
import uuid


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path, limit=1024*1024):
    path = Path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid()
                and before.st_nlink == 1 and not before.st_mode & 0o022
                and before.st_size <= limit, 'owned bounded control file required')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(limit+1)
        after = os.fstat(fd)
        require(len(raw) <= limit and (before.st_dev, before.st_ino, before.st_size,
                before.st_mtime_ns, before.st_ctime_ns) == (after.st_dev, after.st_ino,
                after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'control file changed')
        return json.loads(raw)
    finally:
        os.close(fd)


def atomic(path, value):
    path = Path(path)
    temporary = path.with_name('.'+path.name+'-'+uuid.uuid4().hex)
    try:
        fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(canonical(value)+b'\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)
    finally:
        if temporary.exists(): temporary.unlink()


def process_identity(pid):
    raw = Path('/proc', str(pid), 'stat').read_text()
    fields = raw[raw.rfind(')')+2:].split()
    return {'pid':pid, 'start_ticks':int(fields[19]),
            'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}


@contextmanager
def locked(path, nonblocking=False):
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
                and info.st_nlink == 1 and not info.st_mode & 0o077, 'private lock required')
        fcntl.flock(fd, fcntl.LOCK_EX | (fcntl.LOCK_NB if nonblocking else 0))
        yield fd
    finally:
        os.close(fd)


class Controls:
    def __init__(self, root, operation):
        self.root = Path(root)
        require(self.root.is_absolute() and self.root.resolve() == self.root, 'canonical control directory required')
        info = self.root.lstat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
                and not info.st_mode & 0o077, 'private owned controls required')
        self.identity = (info.st_dev, info.st_ino)
        self.operation = uuid.UUID(operation).hex

    def check(self):
        info = self.root.lstat()
        require((info.st_dev, info.st_ino) == self.identity and self.root.resolve() == self.root,
                'control directory replaced')

    def request(self, action, request_id, reason):
        require(action in ('pause','resume'), 'pause or resume required')
        require(isinstance(reason,str) and 0 < len(reason.encode()) <= 2048, 'bounded operator reason required')
        request_id = str(uuid.UUID(request_id))
        self.check()
        with locked(self.root/'commands.lock'):
            path = self.root/('request-'+request_id+'.json')
            intended = dict(operation=self.operation, request_id=request_id, action=action, reason=reason)
            if path.exists():
                prior = read(path)
                require(all(prior[k] == v for k,v in intended.items()), 'request ID reused for a different command')
                current = self.command()
                # Repair a crash after durable request creation, before pointer publication.
                if prior['sequence'] == current['sequence']+1:
                    atomic(self.root/'command.json',prior)
                else:
                    require(prior['sequence'] <= current['sequence'], 'unreconciled command sequence')
                # A repeated old request never supersedes a newer command.
                return prior
            current = self.command()
            value = dict(intended, sequence=current['sequence']+1, at=time.time())
            atomic(path,value)
            atomic(self.root/'command.json',value)
            return value

    def command(self):
        self.check()
        path = self.root/'command.json'
        if not path.exists():
            return dict(operation=self.operation, sequence=0, action='pause', request_id=None,
                        reason='Initial safe hold; explicit resume required')
        value = read(path)
        require(value['operation'] == self.operation and type(value['sequence']) is int
                and value['sequence'] > 0 and value['action'] in ('pause','resume'), 'foreign or invalid command')
        uuid.UUID(value['request_id'])
        saved = read(self.root/('request-'+value['request_id']+'.json'))
        require(saved == value, 'command has no exact retained request')
        return value

    def publish(self, state, checkpoint, *, attempt, detail=None):
        self.check()
        value = dict(operation=self.operation, attempt=attempt, state=state, at=time.time(),
                     process=process_identity(os.getpid()), checkpoint={k:v for k,v in checkpoint.items()
                         if k not in ('pins','committed_rows','skipped_rows')},
                     command=self.command(), detail=detail)
        atomic(self.root/'status.json', value)
        return value

    def status(self):
        self.check()
        path = self.root/'status.json'
        value = read(path) if path.exists() else None
        live = False
        if value is not None:
            require(value['operation'] == self.operation, 'foreign status')
            try: live = process_identity(value['process']['pid']) == value['process']
            except (OSError, ValueError): pass
        return dict(command=self.command(), worker=value, worker_identity_live=live,
                    observation_age_seconds=time.time()-value['at'] if value else None)

    def boundary(self, checkpoint, *, attempt, verify_released, identity_check,
                 sleep=time.sleep, heartbeat_seconds=5):
        """Called after durable commit AND context closure, never during a batch."""
        verify_released()
        while True:
            identity_check(); self.check()
            if self.command()['action'] == 'resume':
                self.publish('ready',checkpoint,attempt=attempt)
                return
            verify_released()
            self.publish('paused',checkpoint,attempt=attempt,
                         detail='Verified checkpoint; backup contexts released; explicit resume required')
            sleep(heartbeat_seconds)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True); parser.add_argument('--operation',required=True)
    parser.add_argument('action',choices=('status','pause','resume'))
    parser.add_argument('--request-id'); parser.add_argument('--reason')
    args=parser.parse_args(); controls=Controls(args.root,args.operation)
    if args.action=='status': result=controls.status()
    else:
        require(args.request_id is not None and args.reason is not None,'retain one request ID and reason')
        result=controls.request(args.action,args.request_id,args.reason)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__': main()
