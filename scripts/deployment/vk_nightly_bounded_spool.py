"""Small preallocated local change outbox, independent of Desktop transport.

Growing version indexes and all backup bodies remain on B. This necessary
local metadata has a finite SQLite page limit and a reserved PERSIST rollback
journal. Desktop-off/failed B probes cannot terminate this source observer.
No source payload, automatic deletion, baseline acceptance or scheduler here.
"""
from contextlib import contextmanager
import ctypes
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import stat

from vk_nightly_tracking import TrackingStore


class BoundedStore(TrackingStore):
    def report(self,instance,since,*,maximum_paths=100000):
        row=self.db.execute('select cursor from delivered where instance=?',(instance,)).fetchone()
        if row and since<row[0]:raise ValueError('retained B journal prefix required through '+str(row[0]))
        return super().report(instance,since,maximum_paths=maximum_paths)

    def offer(self,report):
        if not report['ready'] or report['errors'] or report.get('terminal') or not report.get('barrier'):
            raise ValueError('complete actual barrier required for delivery')
        raw=json.dumps(report,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        delivery=dict(sequence=report['sequence'],report_sha256=hashlib.sha256(raw).hexdigest(),nonce=secrets.token_hex(32))
        self.db.execute('insert into offered values(?,?) on conflict(instance) do update set row=excluded.row',
                        (report['instance'],json.dumps(delivery,sort_keys=True)))
        return dict(report,delivery=delivery)

    def acknowledge(self,instance,proof):
        if getattr(self,'replica',None) is None or any(proof.get(k)!=v for k,v in self.replica.items()):
            raise ValueError('exact configured B delivery target required')
        if len(json.dumps(proof))>4096:raise ValueError('bounded delivery proof required')
        old=self.db.execute('select cursor,row from delivered where instance=?',(instance,)).fetchone()
        if old and proof==json.loads(old[1]):return dict(acknowledged=old[0],duplicate=True)
        row=self.db.execute('select row from offered where instance=?',(instance,)).fetchone()
        if row is None:raise ValueError('no issued source report; retain local changes')
        offered=json.loads(row[0]);through=offered['sequence']
        if (type(proof.get('sequence')) is not int or proof['sequence']!=through
                or proof.get('report_sha256')!=offered['report_sha256']
                or not isinstance(proof.get('nonce'),str)
                or not hmac.compare_digest(proof['nonce'],offered['nonce'])
                or proof.get('actual_native_B_reopen_verified') is not True):
            raise ValueError('exact issued report and verified B reopen required')
        self.check();self.db.execute('begin immediate')
        try:
            # Events arriving after the exported barrier keep their newer
            # sequence and survive acknowledgement of the old generation.
            self.db.execute('delete from changes where instance=? and sequence<=?',(instance,through))
            self.db.execute('insert into delivered values(?,?,?) on conflict(instance) do update '
                'set cursor=excluded.cursor,row=excluded.row',(instance,through,json.dumps(proof,sort_keys=True)))
            self.db.execute('delete from offered where instance=?',(instance,));self.db.execute('commit')
        except BaseException:
            if self.db.in_transaction:self.db.execute('rollback')
            raise
        return dict(acknowledged=through,duplicate=False)


def reserve(fd,size):
    # KEEP_SIZE allocates extents without appending invalid SQLite pages or
    # changing the rollback header. No privileged mount or OS setting changes.
    api=ctypes.CDLL(None,use_errno=True).fallocate
    api.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.c_longlong,ctypes.c_longlong]
    api.restype=ctypes.c_int
    if api(fd,1,0,size):
        code=ctypes.get_errno();raise OSError(code,os.strerror(code))
    os.fsync(fd)


@contextmanager
def held(path,*,maximum_bytes,guard,replica=None):
    path=Path(path)
    if type(maximum_bytes) is not int or not 256*1024<=maximum_bytes<=8*1024**2:
        raise ValueError('bounded256KiB--8MiB change metadata required')
    guard()
    journal_limit=maximum_bytes+1024**2
    journal=path.with_name(path.name+'-journal')
    # SQLite may inspect a hot rollback journal at connect(), so reject an
    # aliased/unowned sidecar before opening the database, not just at reserve.
    try:
        info=journal.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid()
                or info.st_nlink!=1 or journal.resolve()!=journal or info.st_size>journal_limit):
            raise ValueError('owned bounded rollback journal required')
    except FileNotFoundError:pass
    with TrackingStore.held(path,maximum_bytes=maximum_bytes,journal_mode='PERSIST') as store:
        store.db.execute('pragma temp_store=MEMORY')
        store.db.execute('pragma journal_size_limit='+str(journal_limit))
        # Reserve physical blocks once. SQLite alone grows its valid page
        # count within max_page_count; the reservation does not fabricate pages.
        reserve(store.fd,maximum_bytes)
        fd=os.open(journal,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
        try:
            info=os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_nlink!=1
                    or journal.resolve()!=journal or info.st_size>journal_limit):
                raise ValueError('owned bounded rollback journal required')
            reserve(fd,journal_limit)
        finally:os.close(fd)
        store.db.execute('create table if not exists tracking_health(id integer primary key,row text not null)')
        store.db.execute('create table if not exists offered(instance text primary key,row text) without rowid')
        store.db.execute('create table if not exists delivered(instance text primary key,cursor integer,row text) without rowid')
        store.__class__=BoundedStore;store.replica=replica
        guard();yield store;guard()
