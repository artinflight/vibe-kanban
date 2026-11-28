"""Version owner journal/config bytes through the EXISTING held Nightly context.

No extra native B transport or body writer is opened for checkpointing. The
caller already owns normal B/controller/provider custody. Metadata snapshots
are immutable B SQLite checkpoints, with the ordinary independent normal
consumer reconstructing each exact file in RAM. No live state is replaced.
"""
from contextlib import ExitStack
from datetime import datetime,timezone
import hashlib,json,os,sqlite3,stat,tempfile,uuid
from pathlib import Path
from vk_nightly_file_version import attributes,fingerprint
from vk_nightly_composed_restore import restore_sample
from vk_nightly_sql_point import ram_path
# Retain this exact qualified transport object before an outer pinned-reader
# context temporarily installs its older module namespace.
from vk_nightly_remote_consumer import run as normal_restore
from vk_typed_recovery import LocalDependencies,checksum,digest,stream_checksum

FORMAT='vk-nightly-owner-controls-consumer-v1'


def source_point(path,*,maximum_bytes,guard):
    p=Path(path)
    if not p.is_absolute()or p.resolve()!=p:raise ValueError('canonical exact owner control path required')
    guard();fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb')as f:
        before=os.fstat(f.fileno());identity=fingerprint(before)
        if not stat.S_ISREG(before.st_mode)or before.st_size>maximum_bytes:raise ValueError('finite regular owner control required')
        xattrs=attributes(p);body=f.read(maximum_bytes+1)
        if (len(body)!=before.st_size or fingerprint(os.fstat(f.fileno()))!=identity
                or fingerprint(p.lstat())!=identity or attributes(p)!=xattrs):
            raise ValueError('owner control changed during checkpoint')
    row=dict(kind='file',bytes=len(body),sha256=hashlib.sha256(body).hexdigest(),uid=before.st_uid,gid=before.st_gid,
        mode=stat.S_IMODE(before.st_mode),mtime_ns=before.st_mtime_ns,xattrs=xattrs)
    guard();return dict(source=str(p),source_identity=identity,member=row),body


def checkpoint(recovery,*,operation,plan_sha256,paths,maximum_bytes,seed_checkpoint_sha256):
    """Call at the owner's durable journal boundary; keep SAME B context held.

    paths are explicit trusted owner inputs, never discovered from log payloads.
    Repeated exact snapshots share one index name; earlier epochs remain intact.
    Root must retain its genuine WriterFence/custody whenever that is required.
    """
    operation=uuid.UUID(operation).hex;digest(plan_sha256);digest(seed_checkpoint_sha256)
    if (not isinstance(paths,list)or not 1<=len(paths)<=64 or len(set(paths))!=len(paths)
            or type(maximum_bytes)is not int or not 1<=maximum_bytes<=64*1024**2):
        raise ValueError('finite explicit control metadata admission required')
    recovery.check();base=getattr(recovery,'original',recovery);client=base.handle.db.client
    points=[];bodies=[];left=maximum_bytes
    for path in sorted(paths):
        point,body=source_point(path,maximum_bytes=left,guard=recovery.check)
        points.append(point);bodies.append(body);left-=len(body)
    manifest=dict(operation=operation,plan_sha256=plan_sha256,files=points)
    epoch=checksum(manifest);db=client.connect('owner-controls-'+operation[:16]+'-'+epoch[:16],seed_checkpoint_sha256)
    try:
        db.execute('create table if not exists owner_control_manifest(sha256 text primary key,row text)')
        db.execute('create table if not exists owner_control_files(source text primary key,point text) without rowid')
        db.execute('create table if not exists owner_control_parts(source text,part integer,data blob,primary key(source,part)) without rowid')
        old=db.execute('select sha256,row from owner_control_manifest').fetchall()
        if old:
            if old!=[(epoch,json.dumps(manifest,sort_keys=True,separators=(',',':')))]:raise ValueError('conflicting existing owner control epoch')
        else:
            db.execute('begin immediate')
            try:
                for point,body in zip(points,bodies):
                    recovery.check();db.execute('insert into owner_control_files values(?,?)',(point['source'],json.dumps(point,sort_keys=True,separators=(',',':'))))
                    for part,start in enumerate(range(0,len(body),1024**2)):
                        recovery.check();db.execute('insert into owner_control_parts values(?,?,?)',(point['source'],part,body[start:start+1024**2]))
                db.execute('insert into owner_control_manifest values(?,?)',(epoch,json.dumps(manifest,sort_keys=True,separators=(',',':'))));db.execute('commit')
            except BaseException:
                if db.in_transaction:db.execute('rollback')
                raise
        for point,body in zip(points,bodies):
            stored=db.execute('select point from owner_control_files where source=?',(point['source'],)).fetchone()
            if stored!=(json.dumps(point,sort_keys=True,separators=(',',':')),):raise ValueError('B control checkpoint point differs')
            hashed=hashlib.sha256();count=0
            for number,(part,data)in enumerate(db.execute('select part,data from owner_control_parts where source=? order by part',(point['source'],))):
                recovery.check()
                if part!=number or not 0<len(data)<=1024**2:raise ValueError('ordered bounded B control parts required')
                hashed.update(data);count+=len(data)
            if count!=len(body)or hashed.hexdigest()!=point['member']['sha256']:raise ValueError('B control checkpoint readback differs')
        sealed=client.seal_checkpoint(db.key,dict(owner_control_manifest_sha256=epoch,operation=operation,plan_sha256=plan_sha256))
    finally:db.close()
    recovery.check()
    return dict(format='vk-nightly-owner-control-checkpoint-v1',manifest=manifest,manifest_sha256=epoch,
        index_reference=dict(layer='nightly-controls-v1',selector=sealed['sha256']+'.sqlite',sha256=sealed['sha256'],bytes=sealed['bytes']),
        native_B_independent_checkpoint_readback=sealed,independent_normal_restore_pending=True,
        new_body_writer_or_transport=False,original_B_context_retained=True,OS_SSD_payload_bytes=0)


def run(packet,expected_sha256,*,guard,report=lambda _:None):
    if packet.get('format')!=FORMAT or checksum(packet)!=expected_sha256:raise ValueError('authenticated owner control recovery packet required')
    manifest=packet['checkpoint']['manifest'];epoch=packet['checkpoint']['manifest_sha256']
    if checksum(manifest)!=epoch:raise ValueError('exact externally pinned owner manifest differs')
    if (not isinstance(manifest.get('files'),list)or not 1<=len(manifest['files'])<=64
            or any(type(p['member'].get('bytes'))is not int or p['member']['bytes']<0 for p in manifest['files'])
            or sum(p['member']['bytes']for p in manifest['files'])>64*1024**2):
        raise ValueError('finite measured owner control scope required')
    placement=packet['provider_placement'];ref=packet['checkpoint']['index_reference']
    if not 0<ref['bytes']<=80*1024**2:raise ValueError('bounded immutable owner control image required')
    if os.getuid()==0 or (os.getuid(),os.getgid())!=(placement['expected_uid'],placement['expected_gid']):raise ValueError('normal unprivileged owner required')
    provider=LocalDependencies(placement['roots'],packet['dependencies'],admission_check=guard,
        lease_paths=placement['lease_paths'],expected_root_bindings=placement['root_bindings'])
    proofs=[]
    with provider.held(),ExitStack()as stack:
        source=stack.enter_context(provider.open(ref['layer'],ref['selector']));before=fingerprint(os.fstat(source.fileno()))
        if os.fstat(source.fileno()).st_size!=ref['bytes']or stream_checksum(source,checkpoint=guard)!=digest(ref['sha256']):raise ValueError('normal B owner checkpoint hash differs')
        db=sqlite3.connect('file:/proc/self/fd/'+str(source.fileno())+'?mode=ro&immutable=1',uri=True);stack.callback(db.close)
        db.execute('pragma temp_store=MEMORY');db.execute('pragma cache_size=-4096');db.execute('pragma mmap_size=0')
        if db.execute('pragma integrity_check').fetchall()!=[('ok',)]:raise ValueError('normal B owner checkpoint integrity failed')
        if db.execute('select sha256,row from owner_control_manifest').fetchall()!=[(epoch,json.dumps(manifest,sort_keys=True,separators=(',',':')))]:raise ValueError('normal B owner manifest differs')
        rows={p['source']:p for p in manifest['files']}
        if set(rows)!={r[0]for r in db.execute('select source from owner_control_files')}:raise ValueError('normal owner checkpoint scope differs')
        def check():
            guard();provider.check()
            if fingerprint(os.fstat(source.fileno()))!=before:raise ValueError('held owner checkpoint changed')
        class Index:
            def entry(self,name):check();return rows['/'+name]['member']
        class Handle:
            descriptor={'SQLite':{}};index=Index()
            def check(self):check()
            def blocks(self,name):
                check();point=db.execute('select point from owner_control_files where source=?',('/'+name,)).fetchone()[0]
                if json.loads(point)!=rows['/'+name]:raise ValueError('normal B owner point differs')
                total=0;hashed=hashlib.sha256()
                for number,(part,body)in enumerate(db.execute('select part,data from owner_control_parts where source=? order by part',('/'+name,))):
                    if part!=number or not 0<len(body)<=1024**2:raise ValueError('normal ordered control parts differ')
                    total+=len(body);hashed.update(body)
                    if total>rows['/'+name]['member']['bytes']:raise ValueError('normal B owner body exceeds exact length')
                    for start in range(0,len(body),65536):check();yield body[start:start+65536]
                if total!=rows['/'+name]['member']['bytes']or hashed.hexdigest()!=rows['/'+name]['member']['sha256']:raise ValueError('normal B owner body EOF differs')
                check()
        if not os.path.ismount('/dev/shm'):raise ValueError('actual RAM restore mount unavailable')
        folder=Path(tempfile.mkdtemp(prefix='nightly-owner-control-',dir=ram_path(Path(packet.get('scratch_parent','/dev/shm')))))
        peak=max(p['member']['bytes']for p in manifest['files']);fs=os.statvfs(folder)
        if fs.f_bavail*fs.f_frsize<peak+16*1024**2:raise OSError('actual owner control RAM scratch unavailable')
        for path in sorted(rows):proofs.append(restore_sample(Handle(),path,folder,guard=check))
        folder.rmdir();check()
    return dict(format='vk-nightly-owner-controls-restore-acceptance-v1',consumer_packet_sha256=expected_sha256,
        descriptor_sha256=packet['descriptor_sha256'],normal_leased_consumer_entrypoint_verified=True,
        independent_owner_controls_restore_verified=True,manifest_sha256=epoch,actual_normal_reader_restore=proofs,
        files=len(proofs),raw_bytes=sum(p['bytes']for p in proofs),actual_sequential_scratch_peak_bytes=peak,
        current_baseline_accepted=False,schedule_enabled=False,OS_SSD_payload_bytes=0)


def verify_checkpoint(recovery,controls,provider_placement,dependencies,accepted,*,resource_admission):
    """Normal B reopen/restore while the SAME original context/leases stay held."""
    if not recovery.location.startswith('desktop:'+controls['B_root']+'/'):
        raise ValueError('actual held recovery and supplied native B root differ')
    layer=accepted['index_reference']['layer']
    placement=json.loads(json.dumps(provider_placement))
    for field in ('roots','root_bindings','lease_paths'):placement[field]={layer:placement[field][layer]}
    packet=dict(format=FORMAT,descriptor_sha256=accepted['manifest_sha256'],checkpoint=accepted,
        dependencies={layer:dependencies[layer]},provider_placement=placement,
        Linux_resource_admission={k:resource_admission[k]for k in ('memory_floor_bytes','swap_floor_bytes')})
    recovery.check()
    result=normal_restore(controls,packet,guard=recovery.check)
    recovery.check()
    return dict(checkpoint=accepted,actual_independent_normal_restore=result,original_B_context_retained=True)
