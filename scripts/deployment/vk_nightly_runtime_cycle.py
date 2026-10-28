"""Serial capture/adoption of explicit finite outside-journal runtime files.

Uses the already prepared component and normal capture/readback/seal protocols.
A changed source version fails qualification without rewriting its old point;
the installed controller must explicitly prepare a new component in that case.
No namespace scan, journal replacement, baseline acceptance or scheduling.
"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import time
from zoneinfo import ZoneInfo

from vk_nightly_b_tracker import write_health
from vk_nightly_current_map import decode_member,runtime_components
from vk_nightly_desktop_controls import DesktopControls
from vk_nightly_file_cycle import Source,predecessor,read_owned,optional_report
from vk_nightly_recovery_descriptor import sample_runtime_files
from vk_nightly_typed_worker import configuration,host_guard,run_B,source_closure


def verify_prepared(client,worker,sample):
    """Fresh exact qualification before any body work, including resumed points."""
    db=client.connect(worker['B_index_name'],worker['B_checkpoint_sha256'],readonly=True,working=True)
    try:
        actual={}
        for name,state,raw in db.execute('select name,state,row from members order by name'):
            point=decode_member(raw).get('qualification',{});source='/'+name
            expected=sample['files'].get(source)
            if (expected is None or state not in ('file-needs-capture','verified-file')
                    or point.get('source')!=source or point.get('source_identity')!=expected['source_identity']
                    or any(point.get('row',{}).get(k)!=expected[k] for k in ('kind','bytes','sha256'))
                    or any(point['row'].get(k)!=expected['Linux_metadata'][k] for k in ('mode','uid','gid','mtime_ns','xattrs'))):
                raise ValueError('prepared runtime point changed; preserve it and prepare a new explicit component')
            actual[source]=expected
        if set(actual)!=set(sample['files']):raise ValueError('prepared runtime scope incomplete')
    finally:db.close()


def run(config,worker,*,report):
    started=time.monotonic()
    # Waiting has its own already-declared finite allowance. Applying the
    # shorter capture timeout here killed a healthy queued one-hour runtime
    # phase after one hour of a sixteen-hour predecessor wait.
    guard_config=dict(worker,timeout_seconds=config['maximum_predecessor_seconds'])
    guard=lambda:host_guard(guard_config,started)
    source=Source(config['source_observer'],worker['B_controls'],guard=guard);source.check()
    ref=config['SQL_predecessor'];read_owned(ref['config'],ref['config_sha256'])
    predecessor(ref,source,maximum_seconds=config['maximum_predecessor_seconds'],report=report)
    started=time.monotonic();guard_config=worker
    return capture_component(config,worker,source,guard=guard,report=report)


def capture_component(config,worker,source,*,guard,report):
    """Fixed synchronous parent calls only after its actual SQL receipt.

    The standalone entrypoint still awaits its exact systemd predecessor.
    This core never invents a predecessor or resets the parent's deadline.
    """
    guard();source.check()
    paths=config['runtime_paths']
    if (not isinstance(paths,list) or not 1<=len(paths)<=16 or len(paths)!=len(set(paths))
            or set(paths)!=set(worker['map_binding'].get('source_paths',[]))
            or worker['map_binding'].get('format')!='vk-nightly-explicit-runtime-dependency-component-v1'
            or worker['map_binding'].get('kernel_journal_coverage_claimed') is not False
            or worker['maximum_source_bytes']>1024**2):
        raise ValueError('finite exact prepared runtime scope/read admission required')
    sample=sample_runtime_files(paths,maximum_bytes=worker['maximum_source_bytes'],checkpoint=guard)
    with DesktopControls(worker['B_controls'],guard=guard) as remote:verify_prepared(remote.client,worker,sample)
    captured=run_B(worker,at_component_boundary=source.check)
    if captured['more_pending']:raise ValueError('runtime component incomplete; preserve accepted points')
    # Reobserve only these finite dependencies after capture. Their exact
    # identity/metadata/hash must still equal the separately qualified points.
    fresh=sample_runtime_files(paths,maximum_bytes=worker['maximum_source_bytes'],checkpoint=guard)
    for path in paths:
        for key in ('source_identity','bytes','sha256'):
            if fresh['files'][path][key]!=sample['files'][path][key]:
                raise ValueError('runtime source changed during component capture; preserve old component')
    with DesktopControls(worker['B_controls'],guard=guard) as remote:
        client=remote.client;db=client.connect(worker['B_index_name'],worker['B_checkpoint_sha256'])
        try:
            sealed=client.seal_checkpoint(db.key,dict(runtime_files=sample['files']),on_progress=lambda n:report(
                dict(phase='runtime-component-independent-metadata-readback',bytes_read=n)))
        finally:db.close()
        reference=dict(format='vk-nightly-current-member-map-v1',layer=config['component_layer'],
            selector=sealed['sha256']+'.sqlite',sha256=sealed['sha256'],bytes=sealed['bytes'])
        component=client.connect('runtime-accepted-reader',sealed['sha256'],readonly=True)
        main=client.connect(config['main_map']['index_name'],config['main_map']['checkpoint_sha256'])
        try:
            adopted=main.request('adopt-runtime-component',component_index=component.key,
                component_reference=reference,expected_files=sample['files'])
        finally:main.close();component.close()
    # Independent normal B reopen, not the writer's returned mapping alone.
    with DesktopControls(worker['B_controls'],guard=guard) as remote:
        main=remote.client.connect(config['main_map']['index_name'],config['main_map']['checkpoint_sha256'],readonly=True,working=True)
        try:
            def entry(name):
                row=main.execute('select state,row from members where name=?',(name,)).fetchone()
                if not row or row[0]!='verified-file':raise ValueError('adopted runtime member missing')
                return decode_member(row[1])['member']
            if runtime_components(main,entry)!=adopted['always_runtime_files']:
                raise ValueError('independent normal runtime component mapping differs')
        finally:main.close()
    source.check();delivery=source.deliver()
    result=dict(phase='finite-runtime-component-integrated',captured=captured,
        component_reference=reference,always_runtime_files=adopted['always_runtime_files'],
        actual_independent_B_runtime_component_reopen_verified=True,final_B_delivery=delivery,
        source_hash_read_bytes=sample['source_payload_bytes_hashed']+fresh['source_payload_bytes_hashed'],
        kernel_journal_coverage_claimed=False,baseline_accepted=False,schedule_enabled=False,
        OS_SSD_payload_bytes=0,OS_SSD_index_bytes=0)
    with DesktopControls(worker['B_controls'],guard=guard) as remote:
        db=remote.client.connect(worker['B_index_name'],worker['B_checkpoint_sha256'])
        try:write_health(db,Path(worker['status']),result)
        finally:db.close()
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True);parser.add_argument('--sha256',required=True)
    parser.add_argument('--preflight',action='store_true');args=parser.parse_args()
    config=read_owned(args.config,args.sha256);folder=Path(__file__).parent
    required=source_closure(folder,'vk_nightly_runtime_cycle')
    if not required<=config['source_sha256'].keys():raise ValueError('complete runtime cycle source binding required')
    for name,sha in config['source_sha256'].items():
        if not re.fullmatch(r'vk_[a-z0-9_]+\.py',name) or hashlib.sha256((folder/name).read_bytes()).hexdigest()!=sha:
            raise ValueError('runtime cycle source changed')
    worker=configuration(config['worker_config'],config['worker_config_sha256']);output=Path(worker['status']).parent
    if worker.get('phase_kind','file-points')!='file-points' or 'qualification' in worker:
        raise ValueError('explicit prepared runtime component file worker required')
    def report(value,name='CYCLE_STATUS.private.json'):
        optional_report(output/name,dict(value,at_EDT=datetime.now(ZoneInfo('America/Toronto')).isoformat()))
    if args.preflight:
        Source(config['source_observer'],worker['B_controls'],guard=lambda:host_guard(worker,time.monotonic())).check()
        print(json.dumps(dict(source_and_config_verified=True,runtime_capture_started=False)));return 0
    try:
        result=run(config,worker,report=report);report(result,'RESULT.private.json');report(result)
        print(json.dumps(result),flush=True);return 0
    except BaseException as error:
        report(dict(phase='runtime-component-stopped',type=type(error).__name__,reason=str(error),
            all_source_and_component_points_preserved=True,no_automatic_retry=True,
            baseline_accepted=False,schedule_enabled=False),'STOP.private.json')
        raise


if __name__=='__main__':raise SystemExit(main())
