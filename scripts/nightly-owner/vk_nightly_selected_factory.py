"""Metadata-only finite-request factory; actual normal EOF remains mandatory.

Uses the SAME held native clients and pinned owner request. Default preparation
only reuses accepted versions and reports missing points. Explicit measured
missing-source admission enables stable direct-B capture of those points alone.
No global inventory or whole-current-set/calendar acceptance is implied.
"""
import hashlib,json
from pathlib import Path,PurePosixPath
from datetime import datetime,timezone
from vk_nightly_current_map import decode_member,encode_member
from vk_nightly_selected_reader import qualify
from vk_nightly_typed_worker import source_closure
from vk_typed_recovery import checksum
from vk_nightly_objects import ChunkSink
from vk_nightly_file_version import capture_version


def validate_request(request):
    files=request['files'];root=request['source_root']
    if (not isinstance(files,list)or not 1<=len(files)<=128
            or not isinstance(root,str)or not root.startswith('/')or root=='/'
            or str(PurePosixPath(root))!=root or '..'in PurePosixPath(root).parts):
        raise ValueError('finite canonical selected namespace required')
    names=set()
    for row in files:
        relative=row['relative']
        if not isinstance(relative,str):raise ValueError('literal contained selected name required')
        path=PurePosixPath(relative)
        if path.is_absolute()or '..'in path.parts or str(path)!=relative or relative in ('','.'):
            raise ValueError('literal contained selected name required')
        name=root.lstrip('/')+'/'+relative
        if name!=row['normal_namespace_name']or name in names:
            raise ValueError('unique exact selected namespace required')
        if (type(row['bytes'])is not int or row['bytes']<0
                or not isinstance(row['sha256'],str)or len(row['sha256'])!=64
                or any(c not in '0123456789abcdef'for c in row['sha256'])):
            raise ValueError('exact selected digest/length required')
        names.add(name)


def capture_missing(recovery,request,carriers,dependencies,ledger,*,maximum_source_bytes,chunk_bytes):
    """Missing exact versions through SAME held B writer, resumable per file.

    No new transport, global inventory or source mutation. Root supplies a finite
    exact closed-file request, including sidecars/object-store closure as needed.
    Normal selected-reader recall remains required before conversion acceptance.
    """
    validate_request(request)
    if type(maximum_source_bytes)is not int or maximum_source_bytes<0:
        raise ValueError('explicit measured missing-source admission required')
    base=getattr(recovery,'original',recovery);client=getattr(base,'native_SQL_client',None)
    if client is None:raise ValueError('actual already-held native object client required')
    if 'nightly-objects-v1'not in dependencies:raise ValueError('normal B object provider required')
    guard=recovery.check;guard()
    ledger.execute('create table if not exists selected_captured_versions(name text primary key,row blob) without rowid')
    missing=[];reused=0;copied=0;captured_names=[]
    for wanted in request['files']:
        key=(wanted['sha256'],wanted['bytes'])
        if key in carriers:continue
        row=ledger.execute('select row from selected_captured_versions where name=?',(wanted['normal_namespace_name'],)).fetchone()
        if row:
            member=decode_member(row[0]);single=dict(request,files=[wanted])
            if not build_rows(single,{key:member},dependencies)['complete']:
                raise ValueError('retained request point dependencies unavailable')
            if any(member[k]!=wanted['Linux_metadata'][k]for k in ('mode','uid','gid','mtime_ns','xattrs')):
                raise ValueError('retained request metadata differs')
            carriers[key]=member;reused+=1
        else:missing.append(wanted)
    if sum(f['bytes']for f in missing)>maximum_source_bytes:
        raise ValueError('measured missing source bytes exceed admission')
    for wanted in missing:
        guard();key=(wanted['sha256'],wanted['bytes'])
        if key in carriers:continue
        class Readback:
            def __init__(self):self.hashed=hashlib.sha256();self.size=0
            def write(self,block):self.hashed.update(block);self.size+=len(block);return len(block)
        readback=Readback();sink=ChunkSink(client,chunk_bytes=chunk_bytes,readback_sink=readback)
        point=capture_version('/'+wanted['normal_namespace_name'],sink,
            maximum_bytes=max(1,wanted['bytes']),guard=guard)
        if (point['bytes']!=wanted['bytes']or point['sha256']!=wanted['sha256']
                or any(point['metadata'][k]!=wanted['Linux_metadata'][k]for k in ('mode','uid','gid','mtime_ns','xattrs'))):
            raise ValueError('source differs from requested exact version; partial B objects preserved')
        segments=sink.finish()
        if readback.size!=point['bytes']or readback.hashed.hexdigest()!=point['sha256']:
            raise ValueError('independent ordered B readback differs')
        member=dict(kind='file',bytes=point['bytes'],sha256=point['sha256'],segments=segments,
            **{k:point['metadata'][k]for k in ('mode','uid','gid','mtime_ns','xattrs')})
        guard();ledger.execute('begin immediate')
        try:
            ledger.execute('insert into selected_captured_versions values(?,?)',(wanted['normal_namespace_name'],encode_member(member)))
            ledger.execute('commit')
        except BaseException:
            if ledger.in_transaction:ledger.execute('rollback')
            raise
        carriers[key]=member;copied+=point['bytes'];captured_names.append(wanted['normal_namespace_name'])
    guard();return dict(source_bytes_captured=copied,completed_request_points_reused=reused,
        new_transport_or_body_writer=False,normal_selected_recall_still_required=True,captured_names=captured_names)


def build_rows(request,carriers,dependencies):
    validate_request(request)
    rows={};missing=[]
    if not 1<=len(request['files'])<=128:raise ValueError('finite selected scope exceeds protocol')
    for wanted in request['files']:
        name=wanted['normal_namespace_name'];candidate=carriers.get((wanted['sha256'],wanted['bytes']))
        if candidate is None:missing.append(dict(name=name,sha256=wanted['sha256'],bytes=wanted['bytes']));continue
        member=dict(candidate,**{k:wanted['Linux_metadata'][k]for k in ('mode','uid','gid','mtime_ns','xattrs')})
        if any(member.get(k)!=wanted[k]for k in ('sha256','bytes')):raise ValueError('retained exact body differs')
        if {s['layer']for s in member['segments']}-set(dependencies):
            missing.append(dict(name=name,reason='actual retained provider binding required'));continue
        rows[name]=dict(member=member,qualification=dict(source='/'+name,state='qualified-retained-body',row=member),
            supplemental_metadata_epoch=dict(request_sha256=checksum(request),old_body_epochs_preserved=True,
                original_archive_name_inclusion_not_claimed=True,source_body_recaptured=False))
    if missing:return dict(missing_versions=missing,complete=False,body_bytes_read=0)
    qualify(request,rows,dependencies)
    return dict(rows=rows,missing_versions=[],complete=True,body_bytes_read=0)


def retained_map_candidate(name,wanted,found):
    """Exact accepted map recipe, not a whole-set or new readback acceptance."""
    if found is None or found[0]!='verified-file':return None
    value=decode_member(found[1]);member=value.get('member',{});point=value.get('qualification',{})
    if (member.get('kind')!='file' or point.get('state')!='qualified-retained-body'
            or point.get('source')!='/'+name or point.get('row')!=member
            or any(member.get(k)!=wanted[k]for k in ('sha256','bytes'))):return None
    return member


def prepare(recovery,*,request_path,request_sha256,base_config,retained_map,source_folder,save,
            maximum_missing_source_bytes=None,chunk_bytes=1024**2):
    raw=Path(request_path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=request_sha256:raise ValueError('exact external request differs')
    request=json.loads(raw);validate_request(request);plan=json.loads(Path(request['plan_path']).read_bytes())
    if checksum(plan)!=request['plan_sha256']:raise ValueError('canonical requested plan differs')
    recovery.check();base=getattr(recovery,'original',recovery);client=base.handle.db.client
    if base.prefix!=request['source_root'].lstrip('/')+'/':raise ValueError('requested source namespace differs from actual held context')
    carriers={(m['sha256'],m['bytes']):m for m in base.handle.rows.values()}
    old=client.connect(retained_map['index_name'],retained_map['checkpoint_sha256'],readonly=True,working=True)
    try:
        # An exact qualified map member can come from an accepted cold carrier,
        # not the later incremental-file history. A missing history locator is
        # not missing body data. Normal full-body EOF remains mandatory below.
        if old.execute("select 1 from sqlite_master where name='members'").fetchone():
            for wanted in request['files']:
                name=wanted['normal_namespace_name']
                found=old.execute('select state,row from members where name=?',(name,)).fetchone()
                candidate=retained_map_candidate(name,wanted,found)
                if candidate is not None:carriers[(candidate['sha256'],candidate['bytes'])]=candidate
                recovery.check()
        if old.execute("select 1 from sqlite_master where name='completed_file_carriers'").fetchone():
            pairs=sorted({(r['sha256'],r['bytes'])for r in request['files']})
            for start in range(0,len(pairs),64):
                batch=pairs[start:start+64];place=','.join('(?,?)'for _ in batch)
                rows=old.execute('select sha256,bytes,row from completed_file_carriers where (sha256,bytes) in (values '+place+')',tuple(v for pair in batch for v in pair)).fetchall()
                for sha,size,row in rows:carriers[(sha,size)]=decode_member(row)
                recovery.check()
    finally:old.close()
    capture=None
    if maximum_missing_source_bytes is not None:
        ledger=client.connect('selected-capture-'+request_sha256[:24],
            '295adaa7a96156ecb42cb882734ab52b98cf03494919718a365d86181fe56660')
        try:
            capture=capture_missing(recovery,request,carriers,base_config['dependencies'],ledger,
                maximum_source_bytes=maximum_missing_source_bytes,chunk_bytes=chunk_bytes)
        finally:ledger.close()
    selected=build_rows(request,carriers,base_config['dependencies'])
    if not selected['complete']:save('MISSING_VERSIONS.private.json',selected);return selected
    if capture:
        for name in capture['captured_names']:
            selected['rows'][name]['supplemental_metadata_epoch']['source_body_recaptured']=True
    key='selected-request-'+request_sha256[:24];db=client.connect(key,'295adaa7a96156ecb42cb882734ab52b98cf03494919718a365d86181fe56660')
    try:
        db.execute('create table if not exists selected_recovery_request(format text,request_sha256 text)')
        db.execute('create table if not exists selected_recovery_members(name text primary key,row blob) without rowid')
        existing=db.execute('select format,request_sha256 from selected_recovery_request').fetchall()
        if not existing:
            db.execute('begin immediate')
            try:
                for name,row in sorted(selected['rows'].items()):db.execute('insert into selected_recovery_members values(?,?)',(name,encode_member(row)))
                db.execute('insert into selected_recovery_request values(?,?)',('vk-nightly-selected-original-versions-v1',checksum(request)));db.execute('commit')
            except BaseException:
                if db.in_transaction:db.execute('rollback')
                raise
        elif existing!=[('vk-nightly-selected-original-versions-v1',checksum(request))]:raise ValueError('conflicting retained selected request')
        sealed=client.seal_checkpoint(db.key,dict(external_request_sha256=request_sha256,canonical_plan_sha256=request['plan_sha256']))
    finally:db.close()
    config=json.loads(json.dumps(base_config));folder=Path(source_folder)
    files=source_closure(folder,'vk_nightly_owned_context')
    config.update(source_folder=str(folder),source_sha256={n:hashlib.sha256((folder/n).read_bytes()).hexdigest()for n in files},
        request_file=str(request_path),request_file_sha256=request_sha256,canonical_plan_sha256=request['plan_sha256'],
        index=dict(index_name=key+'-reader',checkpoint_sha256=sealed['sha256']),
        index_reference=dict(format='vk-nightly-selected-original-versions-v1',layer='nightly-controls-v1',selector=sealed['sha256']+'.sqlite',sha256=sealed['sha256'],bytes=sealed['bytes']))
    result=dict(configuration=config,request_sha256=request_sha256,canonical_plan_sha256=request['plan_sha256'],versions=len(selected['rows']),
        native_immutable_index_verified=True,body_bytes_read=0,
        source_bytes_captured=0 if capture is None else capture['source_bytes_captured'],missing_capture=capture,
        actual_normal_body_EOF_recall_still_required=True,whole_current_set_or_calendar_accepted=False)
    save('CONFIGURATION.private.json',config);save('PREPARED.private.json',result);recovery.check();return result
