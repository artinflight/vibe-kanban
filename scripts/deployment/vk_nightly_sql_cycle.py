"""Serial current SQL qualification, direct-B points and member-map adoption.

An actual metadata suffix fixes this cohort's exact source queue. Its durable B
request survives controller death; completed API points resume in that cohort
rather than being copied or relabeled as a different live epoch. Old native
images remain content candidates, never substitutes for current qualification.
This component does not accept a baseline, restore, runtime or schedule.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from vk_change_journal import scope
from vk_nightly_b_tracker import write_health
from vk_nightly_desktop_controls import DesktopControls
from vk_nightly_file_cycle import Source,predecessor,read_owned,optional_report
from vk_nightly_incremental import advance_suffix
from vk_nightly_typed_worker import configuration,host_guard,run_B,source_closure
from vk_nightly_sql_cohort import statistics
from vk_nightly_checkpoints import source_path
from vk_prep_common import identity


def request(config,worker,source,client,*,guard,report):
    """Reuse or durably create one explicit, immutable source-cohort request."""
    if not isinstance(config.get('cohort_tag'),str) or not re.fullmatch('[A-Za-z0-9._-]{1,128}',config['cohort_tag']):
        raise ValueError('bounded explicit current SQL cohort tag required')
    reference=config['SQL_phase_index']
    db=client.connect(reference['index_name'],reference['checkpoint_sha256'])
    try:
        db.execute('create table if not exists SQL_cycle_request(id integer primary key,row text not null)')
        row=db.execute('select row from SQL_cycle_request where id=1').fetchone()
    finally:db.close()
    binding=dict(tag=config['cohort_tag'],source_instance=source.reference['instance'],
        plan_sha256=identity(source.plan),scope_sha256=identity(scope(source.plan)),
        source_root_bindings=source.check()['required_root_bindings'],
        map_index=worker['B_index_name'],map_checkpoint_sha256=worker['B_checkpoint_sha256'],
        catalog_sha256=worker['SQL_catalog_sha256'],B_root=worker['desktop']['B_root'])
    if row:
        value=json.loads(row[0])
        if value['binding']!=binding:raise ValueError('retained current SQL request binding changed')
        if identity({k:v for k,v in value.items() if k!='cohort_id'})!=value['cohort_id']:
            raise ValueError('retained current SQL request digest differs')
        return value
    target=source.config['B_delivery_target']
    delta=advance_suffix(client,index_name=worker['B_index_name'],checkpoint_sha256=worker['B_checkpoint_sha256'],
        journal_name=target['index_name'],journal_checkpoint_sha256=target['checkpoint_sha256'],
        plan=source.plan,maximum_paths=config['maximum_delta_paths'],
        maximum_journal_bytes=worker['B_controls']['maximum_index_bytes'],guard=guard,on_progress=report)
    current=client.connect(worker['B_index_name'],worker['B_checkpoint_sha256'],readonly=True,working=True)
    try:
        raw=current.execute('select binding,complete,suffix_complete from namespace_reconciliation where id=1').fetchone()
        epoch=json.loads(raw[0]) if raw else {}
        if (not raw or raw[1:]!=(1,1) or epoch.get('instance')!=source.reference['instance']
                or any(epoch.get(k)!=binding[k] for k in ('plan_sha256','scope_sha256'))
                or epoch.get('required_root_bindings')!=source.check()['required_root_bindings']):
            raise ValueError('actual completed current SQL namespace/source binding required')
        sources=[p for p, in current.execute("select s.path from SQL_sources s join members m on s.path='/'||m.name where m.state!='symlink' order by s.path")]
        if not sources or len(sources)>1024:raise ValueError('finite actual current SQL queue required')
        roots=set(epoch['required_root_bindings'])|{v['resolved'] for v in epoch['required_root_bindings'].values() if v}
        for path in sources:
            source_path(path)
            if not any(path==root or path.startswith(root.rstrip('/')+'/') for root in roots):
                raise ValueError('SQL point is outside actual declared/resolved source roots')
    finally:current.close()
    value=dict(format='vk-nightly-current-SQL-cohort-request-v1',binding=binding,sources=sources,metadata_delta=delta,
        original_SQL_epochs_preserved=True,old_SQL_points_not_requalified_by_inheritance=True)
    value['cohort_id']=identity(value);encoded=json.dumps(value,sort_keys=True,separators=(',',':'))
    if len(encoded.encode())>1024**2:raise ValueError('current SQL request exceeds bounded control frame')
    db=client.connect(reference['index_name'],reference['checkpoint_sha256'])
    try:
        db.execute('begin immediate')
        try:
            # A competing owner or changed request must never overwrite it.
            db.execute('insert into SQL_cycle_request values(1,?)',(encoded,));guard();db.execute('commit')
        except BaseException:
            if db.in_transaction:db.execute('rollback')
            raise
    finally:db.close()
    db=client.connect(reference['index_name'],reference['checkpoint_sha256'],readonly=True,working=True)
    try:
        if db.execute('select row from SQL_cycle_request where id=1').fetchone()!=(encoded,):
            raise ValueError('independent normal B SQL request readback differs')
    finally:db.close()
    return value


def run(config,worker,*,report):
    started=time.monotonic();guard=lambda:host_guard(worker,started)
    source=Source(config['source_observer'],worker['B_controls'],guard=guard);source.check()
    if config.get('file_predecessor'):
        reference=config['file_predecessor']
        read_owned(reference['config'],reference['config_sha256'])
        predecessor(reference,source,maximum_seconds=config['maximum_predecessor_seconds'],report=report)
    started=time.monotonic();source.deliver();last_delivery=time.monotonic()
    with DesktopControls(worker['B_controls'],guard=guard) as remote:
        cohort=request(config,worker,source,remote.client,guard=guard,report=report)
    actual=dict(worker,phase_kind='SQL-points',SQL_sources=cohort['sources'],current_SQL_cohort_id=cohort['cohort_id'],
        SQL_sources_from_current_map=False,
        B_index_name=config['SQL_phase_index']['index_name'],B_checkpoint_sha256=config['SQL_phase_index']['checkpoint_sha256'])
    if actual.get('SQL_reuse_controls'):raise ValueError('current SQL cycle cannot inherit a historical completed cohort')
    def boundary():
        nonlocal last_delivery
        source.check()
        if time.monotonic()-last_delivery>=120:
            source.deliver();last_delivery=time.monotonic()
    points=run_B(actual,at_component_boundary=boundary)
    with DesktopControls(worker['B_controls'],guard=guard) as remote:
        db=remote.client.connect(actual['B_index_name'],actual['B_checkpoint_sha256'],readonly=True,working=True)
        try:
            state=json.loads(db.execute('select row from SQL_phase_state where id=1').fetchone()[0])
            if state['binding']['current_SQL_cohort_id']!=cohort['cohort_id']:raise ValueError('actual current SQL phase cohort differs')
        finally:db.close()
        current=remote.client.connect(worker['B_index_name'],worker['B_checkpoint_sha256'])
        try:
            adopted=0
            for source_name,record in sorted(state['completed'].items()):
                guard();source.check()
                if source_name not in cohort['sources'] or record.get('SQL_cohort_id')!=cohort['cohort_id']:
                    raise ValueError('old or unrelated SQL point cannot qualify the current map')
                remote.client.call(op='accept-SQL-point',name=worker['B_index_name'],record=record)
                adopted+=1;boundary()
        finally:current.close()
    delivery=source.deliver()
    result=dict(phase='current-SQL-cohort-points-integrated',cohort_id=cohort['cohort_id'],
        requested_SQL_sources=len(cohort['sources']),completed_current_SQL_points=adopted,
        more_pending=points['more_pending'],deferred_SQL=points['deferred_SQL'],cohort_statistics=statistics(state),
        final_B_delivery=delivery,baseline_accepted=False,schedule_enabled=False,
        OS_SSD_payload_bytes=0,OS_SSD_index_bytes=0,runtime_and_composed_restore_still_required=True)
    with DesktopControls(worker['B_controls'],guard=guard) as remote:
        db=remote.client.connect(actual['B_index_name'],actual['B_checkpoint_sha256'])
        try:write_health(db,Path(worker['status']),result)
        finally:db.close()
    with DesktopControls(worker['B_controls'],guard=guard) as remote:
        db=remote.client.connect(actual['B_index_name'],actual['B_checkpoint_sha256'],readonly=True,working=True)
        try:
            value=json.loads(db.execute('select row from tracking_health where id=1').fetchone()[0])
            if any(value.get(k)!=v for k,v in result.items()):raise ValueError('normal independent B SQL-cycle receipt differs')
        finally:db.close()
    source.check();return dict(result,actual_independent_B_SQL_cycle_receipt_reopen_verified=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True);parser.add_argument('--sha256',required=True)
    parser.add_argument('--preflight',action='store_true');args=parser.parse_args()
    config=read_owned(args.config,args.sha256);folder=Path(__file__).parent
    required=source_closure(folder,'vk_nightly_sql_cycle')
    if not required<=config['source_sha256'].keys():raise ValueError('complete SQL cycle source binding required')
    for name,sha in config['source_sha256'].items():
        if not re.fullmatch(r'vk_[a-z0-9_]+\.py',name) or hashlib.sha256((folder/name).read_bytes()).hexdigest()!=sha:
            raise ValueError('SQL cycle source changed')
    worker=configuration(config['worker_config'],config['worker_config_sha256']);output=Path(worker['status']).parent
    if (worker['phase_kind']!='SQL-points' or worker.get('SQL_reuse_controls')
            or worker.get('SQL_sources_from_current_map') is not True or worker['SQL_sources']):
        raise ValueError('prepared current SQL qualification config required')
    def report(value,name='CYCLE_STATUS.private.json'):
        optional_report(output/name,dict(value,at_EDT=datetime.now(ZoneInfo('America/Toronto')).isoformat()))
    if args.preflight:
        Source(config['source_observer'],worker['B_controls'],guard=lambda:host_guard(worker,time.monotonic())).check()
        print(json.dumps(dict(source_and_config_verified=True,SQL_capture_started=False)));return 0
    try:
        value=run(config,worker,report=report);report(value,'RESULT.private.json');report(value)
        print(json.dumps(value),flush=True);return 0
    except BaseException as error:
        report(dict(phase='current-SQL-cycle-stopped',type=type(error).__name__,reason=str(error),
            all_original_images_B_points_and_RAM_partials_preserved=True,no_automatic_retry=True,
            baseline_accepted=False,schedule_enabled=False,native_context=getattr(error,'native_context',None),
            error_notes=[str(n)[:8192] for n in getattr(error,'__notes__',[])[:4]]),'STOP.private.json')
        raise


if __name__=='__main__':raise SystemExit(main())
