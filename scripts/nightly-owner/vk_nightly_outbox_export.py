"""Copy a bounded observer report to its B-native durable consumer ledger.

The source observer never waits for this transport. No source inventory/body
is read. This helper does not prune local changes: local compaction needs its
separate verified-delivery acknowledgement and retained-prefix reader contract.
"""
import hashlib
import json


def export(binding,report,store,*,guard):
    guard()
    report={k:v for k,v in report.items() if k!='delivery'}
    if (report.get('instance')!=binding['instance'] or not report.get('ready')
            or report.get('errors') or report.get('terminal')
            or report.get('scope_sha256')!=binding['scope_sha256']
            or report.get('plan_sha256')!=binding['plan_sha256']
            or report.get('barrier',{}).get('durable_sequence')!=report['sequence']
            or report.get('barrier',{}).get('kernel_drain_completed') is not True):
        raise ValueError('actual complete observer barrier required')
    old=store.db.execute('select cursor from epochs where instance=?',(binding['instance'],)).fetchone()
    if old is None:store.start(binding);cursor=0
    else:cursor=old[0]
    if report['since']!=cursor:
        # A lost acknowledgement may replay the exact just-committed report.
        # Never rewind or silently accept a missing intermediate delivery.
        if cursor!=report['sequence']:raise ValueError('B/source delivery cursor differs; retain both')
    elif old is None or cursor!=report['sequence']:store.commit(report)
    verified=store.report(binding['instance'],report['since'])
    if (not verified['ready'] or verified['sequence']!=report['sequence']
            or verified['errors'] or verified.get('terminal')
            or any(verified['events'].get(path,0)&mask!=mask for path,mask in report['events'].items())):
        raise ValueError('independent B ledger readback differs')
    raw=json.dumps(report,sort_keys=True,separators=(',',':'),allow_nan=False)
    digest=hashlib.sha256(raw.encode()).hexdigest()
    store.db.execute('create table if not exists outbox_delivery(instance text primary key,cursor integer,sha256 text,row text) without rowid')
    store.db.execute('create table if not exists outbox_report_parts(instance text,part integer,data blob,primary key(instance,part)) without rowid')
    # Complete reports can exceed one RPC frame. Keep them in bounded64KiB
    # native-B parts in one FULL transaction, with only a tiny final receipt.
    store.db.execute('begin immediate')
    try:
        store.db.execute('delete from outbox_report_parts where instance=?',(binding['instance'],))
        encoded=raw.encode()
        for part,offset in enumerate(range(0,len(encoded),65536)):
            store.db.execute('insert into outbox_report_parts values(?,?,?)',(binding['instance'],part,encoded[offset:offset+65536]))
        store.db.execute('insert into outbox_delivery values(?,?,?,NULL) on conflict(instance) do update '
            'set cursor=excluded.cursor,sha256=excluded.sha256,row=NULL',
            (binding['instance'],report['sequence'],digest))
        store.db.execute('commit')
    except BaseException:
        if store.db.in_transaction:store.db.execute('rollback')
        raise
    guard()
    return dict(instance=binding['instance'],sequence=report['sequence'],report_sha256=digest,
                changed_paths=len(report['changed']),B_readback_verified=True,local_changes_pruned=False,
                source_paths_scanned=0,source_payload_bytes_read=0,whole_baseline_accepted=False)


def verify_delivery(db,proof):
    """Call after closing the writer and reopening the normal B provider."""
    row=db.execute('select cursor,sha256,row from outbox_delivery where instance=?',(proof['instance'],)).fetchone()
    if row is None or row[:2]!=(proof['sequence'],proof['report_sha256']):raise ValueError('B delivery receipt differs')
    if row[2] is not None:raw=row[2].encode()  # retained v1 receipt remains readable
    else:
        blocks=[];size=0
        for number,(part,data) in enumerate(db.execute('select part,data from outbox_report_parts where instance=? order by part',(proof['instance'],))):
            if part!=number or not isinstance(data,bytes) or not 0<len(data)<=65536:
                raise ValueError('B delivery part missing or malformed')
            blocks.append(data);size+=len(data)
            if size>16*1024**2:raise ValueError('bounded source report exceeded')
        raw=b''.join(blocks)
    if hashlib.sha256(raw).hexdigest()!=proof['report_sha256']:raise ValueError('independent B report readback differs')
    actual=json.loads(raw)
    if actual['instance']!=proof['instance'] or actual['sequence']!=proof['sequence']:
        raise ValueError('independent B report epoch/cursor differs')
    return actual


def retained_prefix_report(store,endpoint,instance,since,*,guard,maximum_paths=100000):
    """Consumer holds the B ledger's provider lease; merge its retained prefix
    with an actual local barrier. Local compaction never appears as no changes.
    This reads changed-name metadata only, even for an unchanged large workspace.
    """
    from vk_nightly_tracking import request
    guard();row=store.db.execute('select cursor from epochs where instance=?',(instance,)).fetchone()
    if row is None:raise ValueError('retained B source epoch unavailable')
    through=row[0]
    prefix=store.report(instance,min(since,through),maximum_paths=maximum_paths)
    live=request(endpoint,instance,max(since,through),maximum_paths=maximum_paths,barrier=True)
    if (not prefix['ready'] or not live['ready'] or prefix['errors'] or live['errors']
            or any(prefix[k]!=live[k] for k in ('instance','scope_sha256','plan_sha256'))):
        raise ValueError('B prefix/live source coverage differs; reconcile explicitly')
    events=dict(prefix['events'])
    for path,mask in live['events'].items():events[path]=events.get(path,0)|mask
    if len(events)>maximum_paths:raise ValueError('complete combined delta exceeds consumer budget')
    guard()
    return dict(live,since=since,changed=sorted(events),events=events,
                retained_B_prefix_through=through,source_paths_scanned=0,source_payload_bytes_read=0)
