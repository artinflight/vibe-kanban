"""Finite direct-B software closure using the existing Nightly component worker.

Exact sources/hashes are external owner pins. No global namespace, journal or
baseline adoption; no second transport, backend action, SQL copy or schedule.
"""
from datetime import datetime,timezone,timedelta
import hashlib,json,os
from pathlib import Path
import time
from vk_nightly_capture_adapter import mcp_lease
from vk_nightly_composed_consumer import encode_packet
from vk_nightly_current_map import decode_member
from vk_nightly_desktop_controls import DesktopControls
from vk_nightly_desktop_objects import DesktopObjects
from vk_nightly_recovery_descriptor import sample_runtime_files
from vk_nightly_runtime_cycle import prepare_current_points
from vk_nightly_remote_consumer import probe_placement,run as normal_restore
from vk_nightly_typed_worker import host_guard,run_B
from vk_typed_recovery import checksum


def validate_request(request):
    files=request['files']
    if not isinstance(files,list)or not 1<=len(files)<=4096:raise ValueError('finite explicit software manifest required')
    paths=[v['path']for v in files]
    if len(set(paths))!=len(paths):raise ValueError('duplicate software path')
    for row in files:
        path=Path(row['path'])
        if (not path.is_absolute()or path.resolve()!=path or type(row['bytes'])is not int or row['bytes']<0
                or len(row['sha256'])!=64 or any(c not in '0123456789abcdef'for c in row['sha256'])):
            raise ValueError('exact canonical software path/size/hash required')
    if sum(v['bytes']for v in files)>512*1024**2:raise ValueError('software manifest exceeds measured finite envelope')
    return {v['path']:v for v in files}


def qualify_sample(request,*,guard):
    files=validate_request(request);total=sum(v['bytes']for v in files.values())
    for path,wanted in files.items():
        if Path(path).stat().st_size!=wanted['bytes']:
            raise ValueError('owner source size changed before qualification: '+path)
    sample=sample_runtime_files(list(files),maximum_bytes=max(1,total),checkpoint=guard)
    for path,wanted in files.items():
        row=sample['files'][path]
        if any(row[k]!=wanted[k]for k in ('bytes','sha256')):raise ValueError('software source differs from owner pin: '+path)
    return sample


def run(config,*,report,save):
    worker=dict(config['worker']);started=time.monotonic();guard=lambda:host_guard(worker,started)
    request=config['request'];sample=qualify_sample(request,guard=guard);save('SOURCE_POINTS.private.json',sample)
    with mcp_lease(Path(config['controller_lease'])):
        guard()
        with DesktopControls(worker['B_controls'],guard=guard)as remote:
            worker=prepare_current_points(remote.client,worker,sample,seed=worker['B_checkpoint_sha256'],guard=guard)
            db=remote.client.connect(worker['B_index_name'],worker['B_checkpoint_sha256'])
            reference=config.get('retained_completed_map');reused=0
            try:
                if reference:
                    old=remote.client.connect(reference['index_name'],reference['checkpoint_sha256'],readonly=True,working=True)
                    try:
                        if old.execute("select 1 from sqlite_master where name='completed_file_carriers'").fetchone():
                            db.execute('create table if not exists completed_file_carriers(sha256 text,bytes integer,row blob,history_name text,history_version text,primary key(sha256,bytes)) without rowid')
                            # Point lookups only: no old global inventory or body reread.
                            pairs=sorted({(r['sha256'],r['bytes'])for r in sample['files'].values()})
                            for start in range(0,len(pairs),64):
                                batch=pairs[start:start+64];place=','.join('(?,?)'for _ in batch)
                                rows=old.execute('select sha256,bytes,row,history_name,history_version from completed_file_carriers where (sha256,bytes) in (values '+place+')',tuple(v for pair in batch for v in pair)).fetchall()
                                accepted=[r for r in rows if {s['layer']for s in decode_member(r[2]).get('segments',[])}<=set(config['dependencies'])]
                                if accepted:
                                    db.execute('begin immediate')
                                    try:db.executemany('insert or ignore into completed_file_carriers values(?,?,?,?,?)',accepted);db.execute('commit')
                                    except BaseException:
                                        if db.in_transaction:db.execute('rollback')
                                        raise
                                    reused+=len(accepted)
                                guard()
                    finally:old.close()
            finally:db.close()
            save('PREPARED.private.json',dict(worker=worker,retained_exact_body_cache_matches=reused))
        captured=run_B(worker,status_sink=report)
        if captured['more_pending']:raise ValueError('finite software component remains pending; retain exact points')
        fresh=qualify_sample(request,guard=guard)
        if any(fresh['files'][p]['source_identity']!=s['source_identity']for p,s in sample['files'].items()):
            raise ValueError('software source version changed; old component retained')
        with DesktopControls(worker['B_controls'],guard=guard)as remote:
            db=remote.client.connect(worker['B_index_name'],worker['B_checkpoint_sha256'])
            try:
                sealed=remote.client.seal_checkpoint(db.key,dict(software_request_sha256=checksum(request),source_points_sha256=checksum(sample)),on_progress=lambda n:report(dict(phase='software-index-independent-readback',bytes=n)))
            finally:db.close()
            # Independently reopen through the normal native owner, not a writer return alone.
            db=remote.client.connect('software-component-accepted-reader',sealed['sha256'],readonly=True)
            try:
                count=db.execute("select count(*) from members where state='verified-file'").fetchone()[0]
                pending=db.execute("select count(*) from members where state!='verified-file'").fetchone()[0]
                if count!=len(sample['files'])or pending:raise ValueError('independent software index incomplete')
            finally:db.close()
        index=dict(format='vk-nightly-current-member-map-v1',layer='nightly-controls-v1',selector=sealed['sha256']+'.sqlite',sha256=sealed['sha256'],bytes=sealed['bytes'])
        save('B_COMPONENT_SEALED.private.json',dict(component_reference=index,captured=captured,source_points=sample,retained_map=reference,request_sha256=checksum(request)))
        # Same ordinary normal B consumer/leases; all explicit software bodies
        # are materialized, independently reopened/hash+Linux-metadata checked.
        peak=max(r['bytes']for r in sample['files'].values());total=sum(r['bytes']for r in sample['files'].values())
        packet=dict(format='vk-nightly-finite-software-consumer-v1',descriptor_sha256=checksum(request),files=sample['files'],index_reference=index,
            dependencies=config['dependencies'],provider_placement=config['provider_placement'],maximum_readback_bytes=total,
            maximum_scratch_bytes=peak+16*1024**2,memory_floor_bytes=worker['memory_floor_bytes'],swap_floor_bytes=worker['swap_floor_bytes'],
            Linux_resource_admission={k:worker[k]for k in ('memory_floor_bytes','swap_floor_bytes')})
        with DesktopObjects(worker['desktop'],guard=guard)as native:
            packet['provider_placement']=probe_placement(worker['B_controls'],packet['provider_placement'],guard=guard,
                deadline=(datetime.now(timezone.utc)+timedelta(seconds=95)).isoformat())
            save('RESTORE_PACKET.private.json',packet)
            def check():guard();native.client.health()
            restored=normal_restore(worker['B_controls'],packet,guard=check,report=report)
        result=dict(format='vk-nightly-finite-software-component-acceptance-v1',request_sha256=checksum(request),
            canonical_location='desktop:'+worker['B_controls']['B_root']+'/'+index['selector'],component_reference=index,
            captured=captured,independent_normal_restore=restored,files=len(sample['files']),raw_bytes=total,
            source_points=sample,elapsed_seconds=time.monotonic()-started,whole_current_set_accepted=False,schedule_enabled=False,OS_SSD_payload_bytes=0)
        save('RESULT.private.json',result);return result
