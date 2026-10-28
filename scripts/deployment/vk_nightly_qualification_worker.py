"""Finite qualification of unresolved map names; all growing state stays on B.

The caller owns map/catalog/source leases, current normal journal barriers,
resource admission and native adoption. Completed map states are never scanned
or hashed again. A resumed controller supplies its committed exact-name cursor;
a failed batch may retry only its still-unadopted points.
"""
import hashlib
import io
from pathlib import Path

from vk_nightly_current_map import decode_member
from vk_nightly_inode_journal import require_full_coverage
from vk_nightly_qualification import qualify_file


def qualify_selected(current,*,journal,adopt,guard,maximum_paths,maximum_source_bytes,
                     after='',checkpoint_cursor=lambda _:None,on_progress=lambda _:None,qualified_snapshots=None):
    if (type(maximum_paths) is not int or maximum_paths<1
            or type(maximum_source_bytes) is not int or maximum_source_bytes<1):
        raise ValueError('finite qualification path/read admission required')
    current.check();db=current.db
    if not db.execute('select complete from metadata').fetchone()[0]:raise ValueError('finish namespace before selected qualification')
    last=after;processed=hashed=read_ceiling=retained=pending=deferred=SQL=0
    def result(more):
        return dict(processed=processed,last_name=last,more_names=more,completed_source_hash_bytes=hashed,
            admitted_source_read_upper_bound=read_ceiling,retained_body_matches=retained,qualified_pending_bodies=pending,
            deferred_points=deferred,SQL_API_sources_discovered=SQL,source_namespace_paths_enumerated=0,
            backup_payload_bytes_copied=0,current_baseline_accepted=False)
    while processed<maximum_paths:
        guard();current.check()
        batch=db.execute("select name,row from members where state in ('file-needs-qualification','current-namespace-replay-required') and name>? order by name limit ?",
                         (last,min(64,maximum_paths-processed))).fetchall()
        if not batch:break
        report=journal();require_full_coverage(report);records=[];budget_stop=False
        for name,raw in batch:
            guard();path=Path('/'+name)
            try:size=path.lstat().st_size
            except FileNotFoundError:size=0
            # This ceiling counts an unsuccessful full hash attempt too. The
            # separately reported successful-hash bytes are not called total IO.
            read_bound=size*(2 if path.suffix=='.jsonl' else 1)
            if read_ceiling+read_bound>maximum_source_bytes:budget_stop=True;break
            read_ceiling+=read_bound
            try:
                prior=decode_member(raw)
                cached=(qualified_snapshots is not None and size<=65536 and len(qualified_snapshots)<16
                    and (prior.get('transfer_deferred') or prior.get('qualification',{}).get('state')=='current-version-deferred'))
                snapshot=io.BytesIO() if cached else None
                point=qualify_file(path,maximum_bytes=max(1,size),journal=report,carriers=lambda *_:[],guard=guard,
                    **({'payload_sink':snapshot} if cached else {}))
                if snapshot is not None:
                    from vk_typed_recovery import checksum
                    body=snapshot.getvalue()
                    if len(body)!=point['row']['bytes'] or hashlib.sha256(body).hexdigest()!=point['row']['sha256']:
                        raise ValueError('bounded stable RAM point differs from qualification')
                    qualified_snapshots[name]=(checksum(point),body)
            except (ValueError,FileNotFoundError) as error:
                namespace=decode_member(raw).get('namespace',{})
                if isinstance(error,FileNotFoundError) and namespace.get('kind')=='file' and namespace.get('bytes')==0:
                    # The authenticated recorded namespace completely determines
                    # zero content. Native adoption independently checks this
                    # observation AND requires a verified retained empty carrier;
                    # this never claims that the vanished pathname exists now.
                    row={k:namespace[k] for k in ('mode','uid','gid','mtime_ns','xattrs')}
                    row.update(kind='file',bytes=0,sha256=hashlib.sha256(b'').hexdigest())
                    point=dict(source=str(path),state='qualified-pending-body',row=row,
                        source_identity=namespace['identity'],recorded_empty_namespace=namespace,
                        source_observed_at='authenticated-recorded-namespace',source_payload_bytes_hashed=0,
                        current_path_absent=True,original_epoch_repaired=False,
                        journal={k:report[k] for k in ('instance','sequence','scope_sha256','plan_sha256')})
                else:
                    point=dict(source=str(path),state='current-version-deferred',reason=str(error),
                        journal={k:report[k] for k in ('instance','sequence','scope_sha256','plan_sha256')},original_epoch_repaired=False)
            else:hashed+=point['source_payload_bytes_hashed']
            records.append(dict(name=name,original_sha256=hashlib.sha256(raw).hexdigest(),version=point,source_read_upper_bound=read_bound))
        if records:
            accepted=adopt(records);processed+=len(records);last=records[-1]['name']
            retained+=accepted['retained_body_matches'];pending+=accepted['qualified_pending_bodies']
            deferred+=accepted['deferred_points'];SQL+=accepted['SQL_API_sources_discovered']
            value=result(True);checkpoint_cursor(value);on_progress(value)
        if budget_stop:return result(True)
    more=db.execute("select 1 from members where state in ('file-needs-qualification','current-namespace-replay-required') and name>? limit 1",(last,)).fetchone() is not None
    return result(more)


def stage_records(database,records,carriers,*,expected_epoch,job,guard):
    """Stage disjoint source qualifications while the body map has its writer.

    Only this separately leased B qualification index changes. Original points,
    complete batch receipts and a transactionally committed resume cursor are
    retained. The main map is refreshed later by its sole controller.
    """
    import json
    from vk_nightly_current_map import classify
    from vk_nightly_qualification import encode_observation
    from vk_nightly_checkpoints import digest
    from vk_nightly_control_format import key
    if (not isinstance(records,list) or not 1<=len(records)<=128 or not isinstance(job,str)
            or not job or len(job)>128):raise ValueError('finite named qualification batch required')
    names=[r['name'] for r in records]
    if names!=sorted(set(names)):raise ValueError('ordered unique qualification names required')
    raw=json.dumps(records,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    if len(raw)>4*1024**2:raise ValueError('bounded qualification input required')
    sha=hashlib.sha256(raw).hexdigest()
    database.execute('create table if not exists staged_qualification_batches(job text,sha256 text,result text,primary key(job,sha256)) without rowid')
    found=database.execute('select result from staged_qualification_batches where job=? and sha256=?',(job,sha)).fetchone()
    if found:return dict(json.loads(found[0]),already_staged=True)
    prepared=[];retained=pending=deferred=SQL=hashed=ceiling=0
    for request in records:
        name=key(request['name']);digest(request['original_sha256']);point=request['version'];anchor=point.get('journal',{})
        if (point.get('source')!='/'+name or any(anchor.get(k)!=expected_epoch[k] for k in ('instance','plan_sha256','scope_sha256'))
                or type(anchor.get('sequence')) is not int or anchor['sequence']<expected_epoch['start_sequence']):
            raise ValueError('current exact source epoch required for staged point')
        source_ceiling=request.get('source_read_upper_bound',point.get('source_payload_bytes_hashed',0))
        if type(source_ceiling) is not int or source_ceiling<0:raise ValueError('actual finite source read ceiling required')
        ceiling+=source_ceiling
        if point.get('state')=='qualified-pending-body':
            row=point['row'];identity=point['source_identity']
            if (len(identity)!=9 or type(point.get('source_payload_bytes_hashed')) is not int
                    or point['source_payload_bytes_hashed']!=row['bytes'] or row.get('segments')):
                raise ValueError('successful complete stable source hash required')
            observation=dict(row,identity=identity);classify(name,observation,point,SQL_sources=set())
            candidate=next(iter(carriers(row['sha256'],row['bytes'])),None)
            if candidate is not None:
                if (candidate.get('kind')!='file' or candidate.get('bytes')!=row['bytes']
                        or candidate.get('sha256')!=row['sha256']):raise ValueError('staged carrier differs from complete source hash')
                point=dict(point,state='qualified-retained-body',row=dict(row,segments=candidate['segments']))
                classify(name,observation,point,SQL_sources=set());retained+=1
            else:pending+=1
            hashed+=row['bytes']
        elif point.get('state')=='current-version-deferred':
            if not isinstance(point.get('reason'),str) or not point['reason']:raise ValueError('explicit source failure reason required')
            if 'SQLite requires' in point['reason']:SQL+=1
            else:deferred+=1
        else:raise ValueError('stable or explicit deferred source qualification required')
        prepared.append((name,encode_observation(point)))
    database.execute('create table if not exists staged_qualification_history(name text,sha256 text,row blob,primary key(name,sha256)) without rowid')
    database.execute('create table if not exists staged_qualification_progress(job text primary key,binding text,last_name text,result text) without rowid')
    binding=json.dumps(expected_epoch,sort_keys=True,separators=(',',':'))
    prior=database.execute('select binding,last_name,result from staged_qualification_progress where job=?',(job,)).fetchone()
    if prior and (prior[0]!=binding or names[0]<=prior[1]):raise ValueError('staged source binding/cursor gap or rewind')
    result=dict(staged=len(prepared),last_name=names[-1],retained_body_matches=retained,qualified_pending_bodies=pending,
        deferred_points=deferred,SQL_API_sources_discovered=SQL,completed_source_hash_bytes=hashed,
        admitted_source_read_upper_bound=ceiling,source_or_archive_payload_bytes_copied=0,main_map_mutated=False,baseline_accepted=False)
    totals=dict(json.loads(prior[2])) if prior else {k:0 for k in ('staged','retained_body_matches','qualified_pending_bodies','deferred_points','SQL_API_sources_discovered','completed_source_hash_bytes','admitted_source_read_upper_bound')}
    for key in totals:totals[key]+=result[key]
    guard();database.execute('begin immediate')
    try:
        for name,encoded in prepared:
            old=database.execute('select row from versions where name=?',(name,)).fetchone()
            if old:
                raw_old=old[0].encode() if isinstance(old[0],str) else old[0]
                database.execute('insert or ignore into staged_qualification_history values(?,?,?)',(name,hashlib.sha256(raw_old).hexdigest(),old[0]))
            database.execute('insert into versions values(?,?) on conflict(name) do update set row=excluded.row',(name,encoded))
        database.execute('insert into staged_qualification_batches values(?,?,?)',(job,sha,json.dumps(result,sort_keys=True,separators=(',',':'))))
        database.execute('insert into staged_qualification_progress values(?,?,?,?) on conflict(job) do update set last_name=excluded.last_name,result=excluded.result',
            (job,binding,names[-1],json.dumps(totals,sort_keys=True,separators=(',',':'))))
        guard();database.execute('commit')
    except BaseException:
        if database.in_transaction:database.execute('rollback')
        raise
    return result
