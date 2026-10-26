"""Durable, single-owner source change queue for Nightly and restart consumers.

One enrollment per observer lifetime; ordinary consumers query changed names,
not the filesystem. Every new process starts an explicit new epoch. Previously
committed epochs/faults remain evidence and cannot certify continuity across a
crash. No backup body, schedule, automatic repair or source mutation occurs here.
"""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import socket
import sqlite3
import stat
import threading
import time

from vk_change_journal import scope
from vk_nightly_move_journal import Journal
from vk_nightly_journal_store import canonical, validate_report
from vk_prep_common import identity, save

FORMAT='vk-nightly-tracking-v1'
MAX_RESPONSE=16*1024**2


def source_bindings(plan):
    """Bind required aliases as well as their resolved watch targets.

    Inotify on a resolved target alone cannot observe retargeting of its source
    symlink. Check this small root set; do not rescan their contents.
    """
    result={}
    for raw in plan['sources']:
        path=Path(raw)
        try:
            before=path.lstat();resolved=path.resolve(strict=True);target=resolved.stat()
            result[raw]=dict(identity=[before.st_dev,before.st_ino,stat.S_IFMT(before.st_mode)],
                             resolved=str(resolved),target_identity=[target.st_dev,target.st_ino,stat.S_IFMT(target.st_mode)],
                             literal=os.readlink(path) if path.is_symlink() else None)
        except FileNotFoundError:result[raw]=None
    return result


class TrackingStore:
    """Exact complete reports commit atomically before in-memory events drain."""
    @classmethod
    @contextmanager
    def held(cls,path,*,maximum_bytes=256*1024**2):
        path=Path(path)
        if path.resolve()!=path or not path.is_absolute():raise ValueError('canonical tracking path required')
        fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK,0o600)
        db=None
        try:
            before=os.fstat(fd)
            if (not stat.S_ISREG(before.st_mode) or before.st_uid!=os.getuid()
                    or before.st_nlink!=1 or before.st_size>maximum_bytes):
                raise ValueError('owned unique tracking control inode required')
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            db=sqlite3.connect(path,timeout=0,isolation_level=None)
            db.execute('pragma journal_mode=DELETE');db.execute('pragma synchronous=FULL')
            db.execute('pragma cache_size=-2048');db.execute('pragma mmap_size=0')
            if type(maximum_bytes) is not int or maximum_bytes<65536:raise ValueError('finite tracking budget required')
            page=db.execute('pragma page_size').fetchone()[0]
            if db.execute('pragma max_page_count='+str(maximum_bytes//page)).fetchone()[0]>maximum_bytes//page:
                raise ValueError('existing tracking control exceeds budget')
            db.execute('create table if not exists epochs(instance text primary key,binding text not null,cursor integer not null,ready integer not null,terminal text) without rowid')
            db.execute('create table if not exists changes(instance text,path text,sequence integer not null,mask integer not null,primary key(instance,path)) without rowid')
            db.execute('create index if not exists changed_cursor on changes(instance,sequence)')
            db.execute('create table if not exists faults(instance text,raw text,primary key(instance,raw)) without rowid')
            value=cls();value.path=path;value.fd=fd;value.db=db;value.inode=(before.st_dev,before.st_ino)
            value.check();yield value;value.check()
        finally:
            if db is not None:db.close()
            os.close(fd)

    def check(self):
        info=self.path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or self.path.resolve()!=self.path
                or (info.st_dev,info.st_ino)!=self.inode):raise ValueError('tracking control inode changed')

    def start(self,binding):
        self.check()
        if (binding.get('format')!=FORMAT or not binding.get('instance')
                or type(binding.get('owner_pid')) is not int or binding['owner_pid']<=0
                or len(binding.get('plan_sha256',''))!=64 or len(binding.get('scope_sha256',''))!=64):
            raise ValueError('explicit owner/plan/epoch binding required')
        self.db.execute('begin immediate')
        try:
            self.db.execute("update epochs set ready=0,terminal='prior owner no longer holds exclusive tracking lease' where terminal is NULL")
            self.db.execute('insert into epochs values(?,?,0,0,NULL)',(binding['instance'],canonical(binding).decode()))
            self.db.execute('commit')
        except BaseException:
            self.db.execute('rollback');raise

    def commit(self,report):
        self.check();epoch=self.db.execute('select binding,cursor,terminal from epochs where instance=?',(report['instance'],)).fetchone()
        if epoch is None or epoch[2] is not None:raise ValueError('inactive tracking epoch')
        binding=json.loads(epoch[0]);raw=canonical(report)
        value=validate_report(raw,instance=report['instance'],scope_sha256=binding['scope_sha256'],since=epoch[1])
        # Missing/interior event sequences may overselect. A backwards cursor or
        # unknown epoch never becomes an empty incremental result.
        self.db.execute('begin immediate')
        try:
            for path,mask in value['events'].items():
                self.db.execute('insert into changes values(?,?,?,?) on conflict(instance,path) '
                                'do update set sequence=excluded.sequence,mask=changes.mask|excluded.mask',
                                (value['instance'],path,value['sequence'],mask))
            for fault in value['errors']:
                self.db.execute('insert or ignore into faults values(?,?)',(value['instance'],canonical(fault).decode()))
            fault=self.db.execute('select 1 from faults where instance=? limit 1',(value['instance'],)).fetchone()
            ready=value['ready'] and not fault and not value.get('pending_directory_moves')
            self.db.execute('update epochs set cursor=?,ready=? where instance=?',(value['sequence'],int(ready),value['instance']))
            self.check();self.db.execute('commit')
        except BaseException:
            if self.db.in_transaction:self.db.execute('rollback')
            raise

    def terminate(self,instance,reason):
        self.check();self.db.execute('update epochs set terminal=?,ready=0 where instance=?',(reason,instance))

    def report(self,instance,since,*,maximum_paths=100000):
        self.check()
        if type(since) is not int or since<0 or type(maximum_paths) is not int or maximum_paths<1:
            raise ValueError('bounded actual cursor query required')
        epoch=self.db.execute('select binding,cursor,ready,terminal from epochs where instance=?',(instance,)).fetchone()
        if epoch is None or since>epoch[1]:raise ValueError('unknown epoch or future cursor; reconcile')
        changed={}
        for path,mask in self.db.execute('select path,mask from changes where instance=? and sequence>? order by path',(instance,since)):
            if len(changed)>=maximum_paths:raise ValueError('delta exceeds bounded consumer path budget; no truncated result')
            changed[path]=mask
        errors=[json.loads(raw) for raw, in self.db.execute('select raw from faults where instance=? order by raw',(instance,))]
        binding=json.loads(epoch[0])
        return dict(format=FORMAT,instance=instance,since=since,sequence=epoch[1],scope_sha256=binding['scope_sha256'],
                    plan_sha256=binding['plan_sha256'],ready=bool(epoch[2] and epoch[3] is None),
                    errors=errors,terminal=epoch[3],changed=list(changed),events=changed,
                    history_before_instance_proven=False,source_paths_scanned=0,source_payload_bytes_read=0)


def request(endpoint,instance,since,*,maximum_paths=100000):
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(30);client.connect(str(endpoint))
        client.sendall(canonical(dict(instance=instance,since=since,maximum_paths=maximum_paths)))
        blocks=[];total=0
        while block:=client.recv(65536):
            total+=len(block)
            if total>MAX_RESPONSE:raise ValueError('complete bounded tracking response required')
            blocks.append(block)
    value=json.loads(b''.join(blocks))
    if 'request_error' in value:raise ValueError(value['request_error'])
    return value


def serve(plan,path,endpoint,*,guard,status_path,stop=None):
    """Run one read-only observer. The caller owns package/plan/admission pins."""
    endpoint=Path(endpoint)
    if endpoint.exists() or endpoint.is_symlink():raise ValueError('existing tracking endpoint must not be replaced')
    stop=stop or threading.Event();journal=Journal(plan);pump=None;failure=[]
    roots=source_bindings(plan)
    binding=dict(format=FORMAT,instance=journal.instance,plan_sha256=identity(plan),
                 scope_sha256=identity(scope(plan)),owner_pid=os.getpid(),
                 owner_start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),
                 started_utc=time.time(),history_before_instance_proven=False,
                 required_root_bindings=roots)
    def drain():
        while not stop.is_set():
            try:
                select.select([journal.fd],[],[],.2)
                journal.read()
            except BaseException as error:
                failure.append(str(error));stop.set();return
    with TrackingStore.held(path) as store:
        store.start(binding);save(status_path,dict(binding,phase='enrolling',ready=False))
        pump=threading.Thread(target=drain,daemon=True);pump.start()
        try:
            for root in sorted(journal.roots):
                guard()
                if not os.path.lexists(root):journal.errors.append({'initial_required_root_absent':root})
                journal.tree(root)
            journal.ready=True
            with socket.socket(socket.AF_UNIX) as server:
                server.bind(str(endpoint));os.chmod(endpoint,0o600);server.listen(4);server.settimeout(.5)
                previous=-1;last_status=0
                while not stop.is_set():
                    guard()
                    with journal.lock:
                        current_roots=source_bindings(plan)
                        for raw,expected in roots.items():
                            if current_roots[raw]!=expected:
                                error={'required_source_binding_changed':raw}
                                if error not in journal.errors:journal.errors.append(error)
                        report=journal.report(0)
                        if report['sequence']!=previous or journal.errors or not previous:
                            store.commit(report);previous=report['sequence']
                            # Commit precedes discard. No source change is lost
                            # between snapshot/commit and clearing memory.
                            journal.changed.clear();journal.events.clear()
                    if time.monotonic()-last_status>10:
                        save(status_path,dict(binding,phase='tracking',sequence=previous,
                             watches=len(journal.watches),raw_errors=list(journal.errors),ready=report['ready'],
                             heartbeat_utc=time.time(),metadata_bytes=Path(path).stat().st_size,
                             baseline_accepted=False));last_status=time.monotonic()
                    try:connection,_=server.accept()
                    except socket.timeout:continue
                    with connection:
                        connection.settimeout(5)
                        try:
                            query=json.loads(connection.recv(4096))
                            if query['instance']!=journal.instance:
                                raise ValueError('observer epoch changed; current reconciliation required')
                            value=store.report(query['instance'],query['since'],maximum_paths=query.get('maximum_paths',100000))
                            raw=canonical(value)
                            if len(raw)>MAX_RESPONSE:raise ValueError('complete delta exceeds response budget')
                        except (ValueError,KeyError,TypeError) as error:raw=canonical(dict(request_error=str(error)))
                        try:connection.sendall(raw)
                        except (BrokenPipeError,ConnectionResetError,socket.timeout):pass
                if failure:raise RuntimeError(failure[0])
        except BaseException as error:
            store.terminate(journal.instance,type(error).__name__+': '+str(error))
            save(status_path,dict(binding,phase='failed',ready=False,reason=str(error),baseline_accepted=False))
            raise
        finally:
            stop.set()
            if pump:pump.join(timeout=3)
            journal.close()
            store.terminate(journal.instance,'owner terminal; new observer requires explicit reconciliation')
            # Preserve the socket pathname as evidence. A new epoch must choose
            # a distinct endpoint; no automatic unlink/replacement.


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True);parser.add_argument('--sha256',required=True)
    args=parser.parse_args();raw=args.config.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=args.sha256:raise ValueError('tracking configuration pin changed')
    config=json.loads(raw);planraw=Path(config['plan']).read_bytes()
    if hashlib.sha256(planraw).hexdigest()!=config['plan_sha256']:raise ValueError('tracking plan pin changed')
    for name,sha in config['source_sha256'].items():
        if Path(name).name!=name or hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()!=sha:
            raise ValueError('tracking source pin changed')
    def guard():
        if not os.path.ismount('/mnt/vk-storage'):raise ValueError('secondary SSD unavailable')
        fs=os.statvfs('/mnt/vk-storage')
        memory={line.split(':')[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines()}
        if fs.f_bavail*fs.f_frsize<=config['ssd_floor_bytes']+config['stop_margin_bytes']:
            raise ValueError('actual SSD floor reached; preserve tracking data')
        if memory['MemAvailable']<config['minimum_mem_available_bytes']:
            raise ValueError('actual memory headroom unavailable')
    stop=threading.Event()
    signal.signal(signal.SIGTERM,lambda *_:stop.set());signal.signal(signal.SIGINT,lambda *_:stop.set())
    guard();serve(json.loads(planraw),Path(config['database']),Path(config['endpoint']),guard=guard,
                  status_path=Path(config['status']),stop=stop)


if __name__=='__main__':main()
