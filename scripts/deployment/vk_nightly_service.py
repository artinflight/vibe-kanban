"""Pinned direct-B whole-cycle executable and existing-chain finisher.

No scheduler installation or backend action. Configuration and complete source
closure are authenticated before leases or B access. A commissioning finisher
adopts only successful exact terminal components independently reopened on B;
it never restarts their units. Normal runs execute the fixed serial pipeline.
All actual drive/STOP/capacity controls remain in the normal native transport.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import copy
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

from vk_nightly_capture_adapter import mcp_lease
from vk_nightly_current_cycle import run
from vk_nightly_cycle_state import CycleState,window
from vk_nightly_desktop_controls import DesktopControls
from vk_nightly_desktop_objects import DesktopObjects
from vk_nightly_file_cycle import Source,read_owned,optional_report
from vk_nightly_remote_consumer import run as consume
from vk_nightly_typed_worker import configuration,source_closure,host_guard,ResourceDeferred
from vk_nightly_window import bounds,night,seconds_left
from vk_typed_recovery import checksum


PROOF={'files':'actual_independent_B_file_cycle_receipt_reopen_verified',
       'SQL':'actual_independent_B_SQL_cycle_receipt_reopen_verified',
       'runtime':'actual_independent_B_runtime_component_reopen_verified'}


def load(path,expected,*,folder=None):
    if os.getuid()==0:raise ValueError('normal unprivileged service identity required')
    folder=Path(folder or Path(__file__).parent);value=read_owned(path,expected)
    if value.get('format')!='vk-nightly-current-service-v1':raise ValueError('fixed current service configuration required')
    if set(value['phase_references'])!=set(PROOF):raise ValueError('exact file/SQL/runtime definitions required')
    required=source_closure(folder,'vk_nightly_service')
    if not required<=value['source_sha256'].keys():raise ValueError('complete installed service source closure required')
    for name,sha in value['source_sha256'].items():
        if (not re.fullmatch('vk_[a-z0-9_]+[.]py',name)
                or hashlib.sha256((folder/name).read_bytes()).hexdigest()!=sha):
            raise ValueError('installed service source differs: '+name)
    window(value['cycle']['cycle_binding'])
    if value['cycle']['cycle_binding'].get('cycle_kind') not in ('incremental','adopt-existing-commissioning'):
        raise ValueError('explicit timed incremental or existing commissioning cycle required')
    phases={};workers={}
    for name,reference in value['phase_references'].items():
        control=read_owned(reference['config'],reference['sha256'])
        phases[name]=control;workers[name]=configuration(control['worker_config'],control['worker_config_sha256'])
        if control['source_observer']!=value['cycle'][name]['source_observer']:
            raise ValueError('current service source owner differs from installed phase')
    if value['cycle']['cycle_binding']['cycle_kind']=='adopt-existing-commissioning':
        if set(value.get('existing_components',{}))!=set(PROOF):raise ValueError('exact existing chain required')
        for name,reference in value['existing_components'].items():
            old=read_owned(reference['config'],reference['config_sha256'])
            legacy=configuration(old['worker_config'],old['worker_config_sha256'],folder=Path(old['worker_config']).parent)
            fields=('B_index_name','B_checkpoint_sha256','map_binding')
            if (old['source_observer']!=phases[name]['source_observer']
                    or any(legacy.get(k)!=workers[name].get(k) for k in fields)
                    or legacy['B_controls']['B_root']!=workers[name]['B_controls']['B_root']
                    or any(old.get(k)!=phases[name].get(k) for k in ('cohort_tag','SQL_phase_index','runtime_component'))):
                raise ValueError('existing component data/source/cohort binding differs from installed adoption definition')
    elif value.get('existing_components'):raise ValueError('ordinary cycle cannot adopt earlier component timings')
    for field in ('controller_lease','status'):
        p=Path(value[field])
        if not p.is_absolute() or p.resolve()!=p or not p.is_relative_to('/mnt/vk-storage'):
            raise ValueError('canonical small SSD controller metadata required')
    # Execute definitions, never a callback or executable from a descriptor.
    for name in PROOF:
        if workers[name]['B_controls']!=workers['files']['B_controls']:
            raise ValueError('single admitted B recovery root/control binding required')
    return value,workers


def original_process_present(reference):
    try:raw=Path('/proc/'+str(reference['owner_pid'])+'/stat').read_text()
    except FileNotFoundError:return False
    return int(raw.rsplit(')',1)[1].split()[19])==reference['owner_start_ticks']


def terminal(reference,*,inspect=subprocess.check_output,process_check=original_process_present):
    unit=reference['unit']
    if not re.fullmatch('vk-nightly-[A-Za-z0-9-]+[.]service',unit):raise ValueError('fixed Nightly unit required')
    output=inspect(['systemctl','--user','show',unit,'-p','MainPID','-p','ActiveState',
                    '-p','ExecMainStatus','-p','ControlGroup','-p','ExecMainPID',
                    '-p','ExecMainStartTimestampMonotonic','-p','LoadState'],text=True,timeout=15)
    state=dict(line.split('=',1) for line in output.splitlines())
    if state.get('LoadState')=='not-found':
        # systemd may collect a successful transient unit. This is NOT proof
        # of success. The caller must still reopen its exact independently
        # verified terminal result on B under actual writer/object leases.
        return not process_check(reference)
    if state.get('MainPID')!='0':
        if state.get('MainPID')!=str(reference['owner_pid']):raise ValueError('existing unit process identity changed')
        return False
    if state.get('ActiveState') in ('active','activating','deactivating'):return False
    if state.get('ActiveState')!='inactive' or state.get('ExecMainStatus')!='0' or state.get('ControlGroup'):
        raise ValueError('existing exact component has not successfully quiesced; preserve all work')
    if (state.get('ExecMainPID')!=str(reference['owner_pid'])
            or abs(int(state['ExecMainStartTimestampMonotonic'])//10000-reference['owner_start_ticks'])>2):
        raise ValueError('terminal unit does not name the original component invocation')
    return True


def reopen_component(client,reference,kind,source,*,guard):
    guard()
    if not terminal(reference):raise BlockingIOError('existing component is still active; never start its replacement')
    control=read_owned(reference['config'],reference['config_sha256'])
    value=read_owned(reference['result']);proof=PROOF[kind]
    if (value.get(proof) is not True or any(value.get(k)!=v for k,v in reference['result_binding'].items())
            or value.get('final_B_delivery',{}).get('instance')!=source.reference['instance']):
        raise ValueError('actual exact independently reopened existing component result differs')
    worker=configuration(control['worker_config'],control['worker_config_sha256'],folder=Path(control['worker_config']).parent)
    index=(control['SQL_phase_index'] if kind=='SQL' else
           dict(index_name=worker['B_index_name'],checkpoint_sha256=worker['B_checkpoint_sha256']))
    db=client.connect(index['index_name'],index['checkpoint_sha256'],readonly=True,working=True)
    try:
        row=db.execute('select row from tracking_health where id=1').fetchone()
        if not row:raise ValueError('actual existing native B completion receipt missing')
        actual=json.loads(row[0]);local={k:v for k,v in value.items() if k not in ('at_EDT',proof)}
        # Runtime records its independent map verification before the final
        # status write. File/SQL add the receipt-reopen flag afterward.
        if kind=='runtime':local[proof]=True
        comparable={k:v for k,v in actual.items() if k!='optional_SSD_health_mirror_error'}
        if comparable!=local:raise ValueError('independent native B completion receipt differs from terminal result')
    finally:db.close()
    guard();source.check();result={k:v for k,v in value.items() if k!='at_EDT'}
    if 'optional_SSD_health_mirror_error' in actual:
        result['adoption_reopen_optional_mirror_error']=actual['optional_SSD_health_mirror_error']
    return result


def scheduled_cycle(template,evening,template_sha256):
    """Non-AI deterministic daily cohort, with one evening across midnight."""
    value=copy.deepcopy(template);cycle=value['cycle'];binding=cycle['cycle_binding']
    if value.get('existing_components') or binding['cycle_kind']!='incremental':
        raise ValueError('commissioning adoption cannot be launched by the recurring calendar')
    day=datetime.fromisoformat(evening).date()
    if day.isoformat()!=evening:raise ValueError('canonical Toronto evening date required')
    start,end=bounds(day);tag='nightly-'+day.strftime('%Y%m%d')+'-'+template_sha256[:16]
    reference=dict(cycle['SQL']['SQL_phase_index'],index_name=tag+'-SQL')
    binding.update(started_UTC=start.isoformat(),deadline_UTC=end.isoformat(),scheduled_night=evening,
        schedule_template_sha256=template_sha256,SQL_cohort_tag=tag,SQL_phase_index=reference)
    cycle['SQL'].update(cohort_tag=tag,SQL_phase_index=reference)
    cycle['finalize'].update(SQL_phase=reference,cycle_binding=dict(binding))
    return value


def execute(value,workers,*,report):
    cycle=value['cycle'];binding=cycle['cycle_binding'];started=time.monotonic()
    admitted=dict(workers['files'],whole_cycle_deadline_UTC=binding['deadline_UTC'],
        B_controls=dict(workers['files']['B_controls'],whole_cycle_deadline_UTC=binding['deadline_UTC']),
        desktop=dict(workers['files']['desktop'],whole_cycle_deadline_UTC=binding['deadline_UTC']))
    def guard():host_guard(admitted,started)
    owner=Source(cycle['files']['source_observer'],admitted['B_controls'],guard=guard)
    with mcp_lease(Path(value['controller_lease'])):
        owner.check()
        # Wait only on actual exact existing handles, before opening any B
        # index or competing with their metadata writes. Timeout is not death.
        if value.get('existing_components'):
            while True:
                owner.check();waiting=[]
                for name,ref in value['existing_components'].items():
                    try:done=terminal(ref)
                    except subprocess.TimeoutExpired:
                        done=False # Observation unavailable, never replace.
                    if not done:waiting.append(name)
                if not waiting:break
                report(dict(phase='awaiting-same-existing-component-chain',waiting=waiting,
                            new_capture_started=False,backup_payload_bytes_copied=0))
                time.sleep(30)
        owner.check()
        with DesktopControls(admitted['B_controls'],guard=guard) as remote:
            # Native readiness, every index request and final transport close
            # retain real STOP/MM/B identity/health/capacity admission.
            store=CycleState(remote.client,value['ledger'],guard=guard)
            if binding.get('scheduled_night'):
                binding=store.scheduled_binding(binding);cycle['cycle_binding']=binding
                cycle['finalize']['cycle_binding']=dict(binding)
            cycle_id=store.initialize(binding)
            retained={p['phase']:p['result'] for p in store.phases(cycle_id)}
            completed=None
            if value.get('existing_components'):
                # Absence of a former PID/unit cannot exclude a surviving
                # native child. Acquire BOTH real body lanes before adoption.
                with DesktopObjects(admitted['desktop'],guard=guard):
                    completed={name:(retained[name] if name in retained else
                        reopen_component(remote.client,ref,name,owner,guard=guard))
                        for name,ref in value['existing_components'].items()}
            def admitted_consumer(packet,*,guard,report):
                # Hold the actual capture lane and native object lease during
                # normal readback. Complete fresh native final health BEFORE
                # returning a result that can advance the accepted pointer.
                with DesktopObjects(admitted['desktop'],guard=guard):
                    with store.opened(readonly=True) as probe:
                        last=[0.0]
                        def check():
                            guard();owner.check()
                            if time.monotonic()-last[0]>=5:
                                probe.request('check');last[0]=time.monotonic()
                        result=consume(admitted['B_controls'],packet,guard=check,report=report)
                guard();return result
            return run(cycle,workers,store,consumer=admitted_consumer,guard=guard,report=report,
                       completed_components=completed)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True);parser.add_argument('--config-sha256',required=True)
    parser.add_argument('--preflight',action='store_true')
    parser.add_argument('--scheduled-night');parser.add_argument('--hard-deadline-utc')
    args=parser.parse_args()
    value,workers=load(args.config,args.config_sha256)
    if bool(args.scheduled_night)!=bool(args.hard_deadline_utc):raise ValueError('paired actual calendar bounds required')
    if args.scheduled_night:
        value=scheduled_cycle(value,args.scheduled_night,args.config_sha256)
        end=value['cycle']['cycle_binding']['deadline_UTC']
        if datetime.fromisoformat(args.hard_deadline_utc)!=datetime.fromisoformat(end):
            raise ValueError('calendar/service hard deadline differs')
        if night(datetime.now(timezone.utc)).isoformat()!=args.scheduled_night:
            raise ValueError('calendar names another evening')
        if datetime.now(timezone.utc)<datetime.fromisoformat(value['cycle']['cycle_binding']['started_UTC']):
            raise ValueError('recurring backup cannot start before 22:00 Toronto')
        seconds_left(end)
    def report(record,name='STATUS.private.json'):
        if record.get('current_recoverable_set_accepted') is True:
            record={k:record[k] for k in ('format','revision','cycle_id','descriptor_sha256',
                'consumer_contract_sha256','restore_receipt_sha256','completed_UTC','elapsed_seconds',
                'current_recoverable_set_accepted','schedule_enabled','OS_SSD_payload_or_index_bytes')}
        record=dict(record,at_EDT=datetime.now(ZoneInfo('America/Toronto')).isoformat(),configuration_sha256=args.config_sha256)
        if len(json.dumps(record,sort_keys=True,separators=(',',':')).encode())>65536:
            from vk_typed_recovery import checksum
            record=dict(phase=record.get('phase'),record_sha256=checksum(record),
                        optional_mirror_omitted='full record exceeds fixed64KiB health bound',
                        authoritative_results='native B cycle ledger',configuration_sha256=args.config_sha256)
        optional_report(Path(value['status']).parent/name,record);print(json.dumps(record),flush=True)
    if args.preflight:
        owner=Source(value['cycle']['files']['source_observer'],workers['files']['B_controls'],
                     guard=lambda:host_guard(workers['files'],time.monotonic()))
        owner.check();print(json.dumps(dict(installed_service_code_and_phase_configs_verified=True,
            new_capture_started=False,native_B_or_complete_restore_not_claimed_by_preflight=True,
            schedule_enabled=False)));return 0
    try:
        result=execute(value,workers,report=report);report(result,'RESULT.private.json');return 0
    except BaseException as error:
        report(dict(phase='whole-cycle-stopped',type=type(error).__name__,reason=str(error),
            all_components_and_failed_outputs_preserved=True,baseline_accepted=False,schedule_enabled=False),
            'STOP.private.json')
        raise


if __name__=='__main__':
    try:raise SystemExit(main())
    except (ResourceDeferred,BlockingIOError):raise SystemExit(75)
