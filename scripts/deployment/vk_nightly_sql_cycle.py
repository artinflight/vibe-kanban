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
import stat
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
from vk_nightly_current_map import SQL_aliases,decode_member
from vk_prep_common import identity


def selected_SQL(rows,roots,aliases,excluded=()):
    """Actual dirty points plus SQL roots whose sidecars are not observed.

    The caller has advanced the authenticated complete journal suffix. A
    directory root covers its descendants' WAL/SHM names; an isolated file
    root does not. Retain unchanged accepted SQL points with their old epochs.
    """
    directories=set();excluded_paths=set(excluded)
    for path,binding in roots.items():
        if not binding:continue
        if binding.get('identity',[0,0,0])[2]==stat.S_IFDIR:directories.add(path)
        if binding.get('target_identity',[0,0,0])[2]==stat.S_IFDIR:directories.add(binding['resolved'])
        for entry in excluded:
            if entry==path or entry.startswith(path.rstrip('/')+'/'):
                excluded_paths.add(binding['resolved'].rstrip('/')+entry[len(path):])
    scope_sources=[];selected=[];always=set(aliases.values());unchanged=0
    for path,state,raw in rows:
        source_path(path);scope_sources.append(path)
        if (not any(path==root or path.startswith(root.rstrip('/')+'/') for root in directories)
                or any(path==root or path.startswith(root.rstrip('/')+'/') for root in excluded_paths)):
            always.add(path)
        if state=='SQLite-needs-image':selected.append(path);continue
        value=decode_member(raw);point=value.get('SQL_point');member=value.get('member',{})
        if (state!='verified-file' or not point or point.get('status')!='consistent_SQL_point_verified'
                or point.get('source')!=path or point.get('method')!='SQLite-backup-API'
                or point.get('independent',{}).get('integrity')!='ok'
                or not point.get('B_acceptance_object')
                or any(point.get(k)!=member.get(k) or point['independent'].get(k)!=member.get(k) for k in ('bytes','sha256'))):
            raise ValueError('actual accepted SQL point or explicit API demand required')
        if path in always:selected.append(path)
        else:unchanged+=1
    if not always<=set(scope_sources):raise ValueError('mandatory SQL target absent from selected namespace')
    return scope_sources,selected,sorted(always),unchanged


def recorded_namespace(client,old_reference,worker,*,guard):
    """Reuse an actual completed cohort's fixed namespace, never chase live IO.

    Later header discoveries may extend typed SQL membership without another
    namespace replay. Unchanged independently accepted images keep their epochs;
    newly discovered databases and mandatory alias targets still use the API.
    """
    guard();old=client.connect(old_reference['index_name'],old_reference['checkpoint_sha256'],readonly=True,working=True)
    try:
        request_row=old.execute('select row from SQL_cycle_request where id=1').fetchone()
        result_row=old.execute('select row from tracking_health where id=1').fetchone()
        if not request_row or not result_row:raise ValueError('actual completed predecessor SQL scope required')
        previous=json.loads(request_row[0]);result=json.loads(result_row[0])
        if (identity({k:v for k,v in previous.items() if k!='cohort_id'})!=previous['cohort_id']
                or result.get('cohort_id')!=previous['cohort_id'] or result.get('more_pending') is not False
                or result.get('deferred_SQL') or result.get('completed_current_SQL_points')!=len(previous['sources'])
                or result.get('phase')!='current-SQL-cohort-points-integrated'):
            raise ValueError('predecessor SQL scope has not completed')
    finally:old.close()
    current=client.connect(worker['B_index_name'],worker['B_checkpoint_sha256'],readonly=True,working=True)
    try:
        from vk_nightly_metadata_replay import replay_cursor
        namespace=json.loads(current.execute('select binding from namespace_reconciliation where id=1').fetchone()[0])
        if (current.execute('select complete,suffix_complete from namespace_reconciliation where id=1').fetchone()!=(1,1)
                or replay_cursor(current,namespace['instance'],namespace['start_sequence'])!=previous['metadata_delta']['through']
                or previous['binding']['map_index']!=worker['B_index_name']
                or previous['binding']['map_checkpoint_sha256']!=worker['B_checkpoint_sha256']
                or any(previous['binding'][k]!=namespace[k] for k in ('plan_sha256','scope_sha256'))):
            raise ValueError('recorded SQL closure cannot advance or change the fixed namespace')
        actual={p for p, in current.execute("select s.path from SQL_sources s join members m on s.path='/'||m.name where m.state!='symlink'")}
        if not set(previous['SQL_scope_sources'])<=actual:raise ValueError('recorded SQL closure dropped earlier SQL scope')
    finally:current.close()
    guard()
    return dict(previous['metadata_delta'],recorded_SQL_predecessor=dict(old_reference),
        predecessor_cohort_id=previous['cohort_id'],predecessor_request_sha256=identity(previous),
        new_namespace_replay_started=False)


def request(config,worker,source,client,*,guard,report):
    """Reuse or durably create one explicit, immutable source-cohort request."""
    if not isinstance(config.get('cohort_tag'),str) or not re.fullmatch('[A-Za-z0-9._-]{1,128}',config['cohort_tag']):
        raise ValueError('bounded explicit current SQL cohort tag required')
    reference=config['SQL_phase_index']
    db=client.connect(reference['index_name'],reference['checkpoint_sha256'])
    try:
        db.execute('create table if not exists SQL_cycle_request(id integer primary key,row text not null)')
        db.execute('create table if not exists tracking_health(id integer primary key,row text not null)')
        row=db.execute('select row from SQL_cycle_request where id=1').fetchone()
    finally:db.close()
    binding=dict(tag=config['cohort_tag'],source_instance=source.reference['instance'],
        plan_sha256=identity(source.plan),scope_sha256=identity(scope(source.plan)),
        source_root_bindings=source.check()['required_root_bindings'],
        map_index=worker['B_index_name'],map_checkpoint_sha256=worker['B_checkpoint_sha256'],
        catalog_sha256=worker['SQL_catalog_sha256'],B_root=worker['desktop']['B_root'])
    if config.get('recorded_SQL_scope_from'):
        binding['recorded_SQL_scope_from']=config['recorded_SQL_scope_from']
    if row:
        value=json.loads(row[0])
        if value['binding']!=binding:raise ValueError('retained current SQL request binding changed')
        if identity({k:v for k,v in value.items() if k!='cohort_id'})!=value['cohort_id']:
            raise ValueError('retained current SQL request digest differs')
        return value
    target=source.config['B_delivery_target']
    delta=(recorded_namespace(client,config['recorded_SQL_scope_from'],worker,guard=guard)
        if config.get('recorded_SQL_scope_from') else
        advance_suffix(client,index_name=worker['B_index_name'],checkpoint_sha256=worker['B_checkpoint_sha256'],
            journal_name=target['index_name'],journal_checkpoint_sha256=target['checkpoint_sha256'],
            plan=source.plan,maximum_paths=config['maximum_delta_paths'],
            maximum_journal_bytes=worker['B_controls']['maximum_index_bytes'],guard=guard,on_progress=report))
    current=client.connect(worker['B_index_name'],worker['B_checkpoint_sha256'],readonly=True,working=True)
    try:
        raw=current.execute('select binding,complete,suffix_complete from namespace_reconciliation where id=1').fetchone()
        epoch=json.loads(raw[0]) if raw else {}
        if (not raw or raw[1:]!=(1,1) or epoch.get('instance')!=source.reference['instance']
                or any(epoch.get(k)!=binding[k] for k in ('plan_sha256','scope_sha256'))
                or epoch.get('required_root_bindings')!=source.check()['required_root_bindings']):
            raise ValueError('actual completed current SQL namespace/source binding required')
        rows=current.execute("select s.path,m.state,m.row from SQL_sources s join members m on s.path='/'||m.name where m.state!='symlink' order by s.path").fetchall()
        if not rows or len(rows)>1024:raise ValueError('finite actual current SQL scope required')
        all_sources,sources,always,unchanged=selected_SQL(rows,epoch['required_root_bindings'],SQL_aliases(current),
            source.plan.get('excluded_rebuildable_directories',[]))
        roots=set(epoch['required_root_bindings'])|{v['resolved'] for v in epoch['required_root_bindings'].values() if v}
        for path in all_sources:
            source_path(path)
            if not any(path==root or path.startswith(root.rstrip('/')+'/') for root in roots):
                raise ValueError('SQL point is outside actual declared/resolved source roots')
    finally:current.close()
    value=dict(format='vk-nightly-current-SQL-cohort-request-v1',binding=binding,sources=sources,metadata_delta=delta,
        SQL_scope_sources=all_sources,always_SQL_API_sources=always,unchanged_SQL_points_reused=unchanged,
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
    points=(run_B(actual,at_component_boundary=boundary) if cohort['sources'] else
            dict(more_pending=False,deferred_SQL={}))
    with DesktopControls(worker['B_controls'],guard=guard) as remote:
        db=remote.client.connect(actual['B_index_name'],actual['B_checkpoint_sha256'],readonly=True,working=True)
        try:
            if cohort['sources']:
                state=json.loads(db.execute('select row from SQL_phase_state where id=1').fetchone()[0])
                if state['binding']['current_SQL_cohort_id']!=cohort['cohort_id']:raise ValueError('actual current SQL phase cohort differs')
            else:state=dict(completed={},partial={},deferred={})
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
        complete_SQL_scope_sources=len(cohort['SQL_scope_sources']),unchanged_SQL_points_reused=cohort['unchanged_SQL_points_reused'],
        always_SQL_API_sources=cohort['always_SQL_API_sources'],
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
