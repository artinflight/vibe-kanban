"""Small operational recovery control on the existing native Desktop B store.

No source data, review projection or credentials are discovered here. Callers
supply exact bounded source/packet bytes, real native admission and (for final
release) the physical writer fence. Every record is independently reopened.
"""
import hashlib
import json
import re

MAX_RECORD_BYTES = 2 * 1024**2
MAX_TOTAL_BYTES = 8 * 1024**2


def records(payloads):
    if not payloads or len(payloads)>128:
        raise ValueError('Finite recovery source/packet bundle required')
    output=[];total=0
    for name,raw in sorted(payloads.items()):
        if name in ('.','..') or not re.fullmatch(r'[A-Za-z0-9_.-]+',name) or not isinstance(raw,bytes):
            raise ValueError('Literal source/packet name and exact bytes required')
        if len(raw)>MAX_RECORD_BYTES:
            raise ValueError('Recovery control record exceeds admitted bound')
        total+=len(raw)
        output.append((name,hashlib.sha256(raw).hexdigest(),raw))
    if total>MAX_TOTAL_BYTES:
        raise ValueError('Recovery control bundle exceeds admitted bound')
    return output


def write_control(client,key,seed_digest,payloads,binding,*,guard,report=lambda _:None):
    """The caller holds original native guards and final fence where required."""
    rows=records(payloads);guard()
    db=client.connect(key,seed_digest)
    try:
        if db.execute("select 1 from sqlite_master where type='table' and name='release_recovery_control'").fetchone():
            raise ValueError('Existing recovery control preserved; reconcile before retry')
        db.execute('begin immediate')
        try:
            db.execute('create table release_recovery_control(name text primary key,sha256 text not null,data blob not null) without rowid')
            for row in rows:guard();db.execute('insert into release_recovery_control values(?,?,?)',row)
            guard();db.execute('commit')
        except BaseException:
            if db.in_transaction:db.execute('rollback')
            raise
        sealed=client.seal_checkpoint(key,binding,on_progress=lambda n:report(dict(phase='recovery-control-independent-stream-readback',bytes_read=n)))
    finally:db.close()
    if sealed.get('independent_stream_readback_verified') is not True:
        raise ValueError('Native independent stream acceptance missing')
    return dict(format='vk-release-native-B-recovery-control-v1',index_name=key,
        sha256=sealed['sha256'],bytes=sealed['bytes'],binding=binding,
        records=[dict(name=n,sha256=sha,bytes=len(raw)) for n,sha,raw in rows],
        independent_stream_readback_verified=sealed.get('independent_stream_readback_verified') is True)


def independently_reopen(client,reference,payloads,*,guard):
    expected=records(payloads)
    if reference.get('independent_stream_readback_verified') is not True:
        raise ValueError('Previously accepted native stream reference required')
    db=client.connect('reopen-'+reference['index_name'],reference['sha256'],readonly=True)
    try:
        actual=db.execute('select name,sha256,length(data) from release_recovery_control order by name').fetchall()
        if actual!=[(n,sha,len(raw)) for n,sha,raw in expected]:
            raise ValueError('Independent native recovery-control manifest differs')
        for name,sha,raw in expected:
            guard();row=db.execute('select data from release_recovery_control where name=?',(name,)).fetchone()
            if not row or row[0]!=raw or hashlib.sha256(row[0]).hexdigest()!=sha:
                raise ValueError('Independent native recovery-control body differs')
        db.request('check')
    finally:db.close()
    return dict(reference,independent_native_reopen_verified=True,
                source_or_backup_payload_bytes_copied=0,control_bytes=sum(len(raw) for _,_,raw in expected))
