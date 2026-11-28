"""Bounded native-B staging and recall for current-map metadata suffixes.

Only changed-name metadata is handled. Inputs live beside the map on B and
remain available after a transport/controller interruption; no SSD journal or
source body is staged. Caller holds normal index/source leases and admission.
"""
import hashlib
import json

from vk_nightly_inode_journal import require_full_coverage
from vk_nightly_outbox_export import verify_delivery


MAXIMUM_INPUT_BYTES=16*1024**2


def durable_report(store,instance,since,*,guard,maximum_paths=100000):
    """Use an independently delivered actual barrier, without a new live tail.

    The B provider lease pins the ledger cursor while the caller observes and
    applies changed metadata. Later source events remain in the local outbox
    and are explicitly the next suffix; no live report is called durable.
    """
    guard()
    row=store.db.execute('select cursor,sha256 from outbox_delivery where instance=?',(instance,)).fetchone()
    if row is None:raise ValueError('verified actual B delivery required')
    latest=verify_delivery(store.db,dict(instance=instance,sequence=row[0],report_sha256=row[1]))
    report=store.report(instance,since,maximum_paths=maximum_paths)
    if any(latest[k]!=report[k] for k in ('instance','sequence','scope_sha256','plan_sha256')):
        raise ValueError('actual B delivery and retained ledger differ')
    report['barrier']=latest['barrier'];require_full_coverage(report);guard()
    return report


def replay_cursor(database,instance,start_sequence):
    """Observer counters are per epoch; old larger counters remain history."""
    if not database.execute("select 1 from sqlite_master where name='namespace_replay_windows'").fetchone():return start_sequence
    value=database.execute("select max(through) from namespace_replay_windows where complete=1 and json_extract(summary,'$.instance')=?",(instance,)).fetchone()[0]
    return start_sequence if value is None else value


def stage_input(database,report,replay,*,guard):
    raw=json.dumps(dict(report=report,replay=replay),sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    if len(raw)>MAXIMUM_INPUT_BYTES:raise ValueError('bounded metadata replay input exceeded')
    sha=hashlib.sha256(raw).hexdigest()
    database.execute('create table if not exists namespace_replay_inputs(sha256 text,part integer,data blob,primary key(sha256,part)) without rowid')
    database.execute('begin immediate')
    try:
        for part,offset in enumerate(range(0,len(raw),65536)):
            guard();block=raw[offset:offset+65536]
            old=database.execute('select data from namespace_replay_inputs where sha256=? and part=?',(sha,part)).fetchone()
            if old is not None and old[0]!=block:raise ValueError('retained replay input collision')
            if old is None:database.execute('insert into namespace_replay_inputs values(?,?,?)',(sha,part,block))
        guard();database.execute('commit')
    except BaseException:
        if database.in_transaction:database.execute('rollback')
        raise
    actual=load_input(database,sha,guard=guard)
    if actual!=dict(report=report,replay=replay):raise ValueError('actual retained replay input readback differs')
    return sha


def load_input(database,sha,*,guard):
    if not isinstance(sha,str) or len(sha)!=64:raise ValueError('exact replay input SHA required')
    chunks=[];total=0
    for number,(part,data) in enumerate(database.execute('select part,data from namespace_replay_inputs where sha256=? order by part',(sha,))):
        guard()
        if number!=part or not isinstance(data,bytes) or not 0<len(data)<=65536:raise ValueError('retained replay part missing')
        chunks.append(data);total+=len(data)
        if total>MAXIMUM_INPUT_BYTES:raise ValueError('bounded retained replay input exceeded')
    raw=b''.join(chunks)
    if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('retained replay input SHA differs')
    return json.loads(raw)
