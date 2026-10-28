"""One-time exact-package Nightly adoption after actual ordinary restore proof.

No capture, backend action, retention deletion or alternative transport. The
owner invokes this finite installer after the initial current set and an actual
ordinary incremental cycle have completed. Evidence is reopened on native B;
configuration Booleans or an isolated rehearsal cannot satisfy this gate.
"""
import argparse
import copy
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path

from vk_nightly_calendar import settings,decision,load as calendar_state,held as calendar_lease,checkpoint as calendar_checkpoint
from vk_nightly_window import ZONE,bounds,night
from vk_nightly_capture_adapter import mcp_lease
from vk_nightly_cycle_state import CycleState,PHASES
from vk_nightly_desktop_controls import DesktopControls
from vk_nightly_desktop_objects import DesktopObjects
from vk_nightly_file_cycle import Source,read_owned
from vk_nightly_schedule import block,apply,END
from vk_nightly_journal_delivery import cron_line
from vk_nightly_outbox_export import verify_delivery
from vk_nightly_service import load as load_service,scheduled_cycle
from vk_nightly_typed_worker import host_guard
from vk_typed_recovery import checksum
from vk_prep_common import storage


def qualification(store,value,service_sha256,*,guard):
    """Read-only native evidence gate for this exact ordinary source/config."""
    guard();accepted=store.accepted()
    if not accepted:raise ValueError('actual accepted ordinary incremental baseline is missing')
    cycle_id=accepted['cycle_id'];phases=store.phases(cycle_id)
    if (len(phases)!=len(PHASES) or accepted.get('current_recoverable_set_accepted') is not True
            or accepted['phase_chain_sha256']!=checksum(phases[-1])):
        raise ValueError('complete independently reopened accepted phase chain required')
    with store.opened(readonly=True) as db:
        row=db.execute('select binding from nightly_cycles where cycle_id=?',(cycle_id,)).fetchone()
    if not row:raise ValueError('accepted cycle binding missing')
    binding=json.loads(row[0])
    if (checksum(binding)!=cycle_id or binding.get('cycle_kind')!='incremental'
            or binding.get('schedule_template_sha256')!=service_sha256):
        raise ValueError('accepted commissioning or other package is not ordinary exact-package evidence')
    expected=scheduled_cycle(value,binding['scheduled_night'],service_sha256)['cycle']['cycle_binding']
    expected['previous_accepted_sha256']=binding['previous_accepted_sha256']
    if (binding!=expected or not binding['previous_accepted_sha256']
            or accepted['previous_accepted_sha256']!=binding['previous_accepted_sha256']
            or accepted['original_epoch']!=accepted['descriptor']['original_epoch']):
        raise ValueError('ordinary source/cohort/deadline/predecessor binding differs')
    # Exact canonical Toronto bounds were checked by scheduled_cycle. Recheck
    # completion and every component rather than trusting an enabled flag.
    start=datetime.fromisoformat(binding['started_UTC']);end=datetime.fromisoformat(binding['deadline_UTC'])
    finished=datetime.fromisoformat(accepted['completed_UTC'])
    if (not start<=finished<end or type(accepted['elapsed_seconds']) not in (int,float)
            or not math.isclose(accepted['elapsed_seconds'],(finished-start).total_seconds(),rel_tol=0,abs_tol=1e-6)):
        raise ValueError('actual whole-cycle completion is outside its overnight window')
    proof=('actual_independent_B_file_cycle_receipt_reopen_verified',
           'actual_independent_B_SQL_cycle_receipt_reopen_verified',
           'actual_independent_B_runtime_component_reopen_verified')
    for item,field in zip(phases,proof):
        result=item['result']
        if (result.get(field) is not True or result.get('more_pending',False) is not False
                or result.get('deferred_SQL')):
            raise ValueError('current file/SQL/runtime completion is incomplete')
    candidate=phases[3]['result'];current=candidate['candidate'];packet=candidate['packet'];restored=phases[4]['result']
    if (current.get('format')!='vk-nightly-finalized-current-candidate-v1'
            or accepted['descriptor_sha256']!=checksum(accepted['descriptor'])
            or current['descriptor']!=accepted['descriptor']
            or current['descriptor_sha256']!=accepted['descriptor_sha256']
            or accepted['consumer_contract_sha256']!=checksum(accepted['consumer_contract'])
            or current['consumer_contract']!=accepted['consumer_contract']
            or current['consumer_contract_sha256']!=accepted['consumer_contract_sha256']
            or current['content_proof_sha256']!=accepted['content_proof_sha256']
            or packet['descriptor_sha256']!=accepted['descriptor_sha256']
            or packet['consumer_contract_sha256']!=accepted['consumer_contract_sha256']
            or checksum(restored)!=accepted['restore_receipt_sha256']
            or restored.get('normal_leased_consumer_entrypoint_verified') is not True
            or restored.get('independent_composed_restore_verified') is not True
            or restored.get('actual_existing_B_backed_consumer_route_verified') is not True
            or restored.get('consumer_packet_sha256')!=checksum(packet)
            or any(restored.get(k)!=accepted[k] for k in
                   ('descriptor_sha256','consumer_contract_sha256','content_proof_sha256'))):
        raise ValueError('actual normal B-backed composed restore and accepted dependencies differ')
    guard()
    return dict(format='vk-nightly-exact-package-commissioning-qualification-v1',
        service_configuration_sha256=service_sha256,accepted_baseline_sha256=checksum(accepted),
        accepted_cycle_id=cycle_id,scheduled_night=binding['scheduled_night'],completed_UTC=accepted['completed_UTC'],
        elapsed_seconds=accepted['elapsed_seconds'],descriptor_sha256=accepted['descriptor_sha256'],
        restore_receipt_sha256=accepted['restore_receipt_sha256'],
        actual_ordinary_incremental_and_normal_restore_verified=True,schedule_enabled=False)


def journal_qualification(client,source,receipt,*,service_sha,script_sha,legacy_sha):
    """Reopen the actual last journal commit, never trust a local success flag."""
    health=source.check();binding=dict(service_sha256=service_sha,entrypoint_sha256=script_sha,
        source_observer=source.reference,B_delivery_target=source.config['B_delivery_target'],
        legacy_owners_sha256=legacy_sha)
    if (receipt.get('format')!='vk-nightly-between-run-journal-delivery-v1'
            or receipt.get('binding')!=binding or receipt.get('phase')!='journal-delivery-verified'):
        raise ValueError('exact installed journal collector proof required')
    proof=receipt['delivery']
    if (proof.get('instance')!=health['instance'] or proof.get('actual_native_B_reopen_verified') is not True
            or proof.get('local_acknowledged')!=proof['sequence'] or proof.get('local_changes_pruned') is not True):
        raise ValueError('actual journal ACK and source epoch proof required')
    target=source.config['B_delivery_target']
    db=client.connect(target['index_name'],target['checkpoint_sha256'],readonly=True,working=True)
    try:actual=verify_delivery(db,proof)
    finally:db.close()
    if any(actual[k]!=health[k] for k in ('instance','scope_sha256','plan_sha256')):
        raise ValueError('actual B journal/source coverage differs')
    return dict(sequence=proof['sequence'],instance=proof['instance'],
        report_sha256=proof['report_sha256'],actual_B_journal_reopen_verified=True)


def enabled_configuration(disabled):
    settings(disabled)
    if (disabled['schedule'].get('enabled') is not False or disabled.get('adoption_authorized') is not False
            or disabled.get('retention_adopted') is not False):
        raise ValueError('exact previously disabled adoption template required')
    value=copy.deepcopy(disabled);value['schedule']['enabled']=True
    value.update(adoption_authorized=True,retention_adopted=True)
    return value


def adopt_completed_night(state,evidence,configuration_sha256):
    """Carry actual ordinary acceptance into cron without a same-night rerun.

    Called only after native qualification under controller/body/calendar leases.
    This records zero cron attempts: the verified run was invoked directly.
    A differing incumbent is retained for exact reconciliation, never cleared.
    """
    if evidence.get('actual_ordinary_incremental_and_normal_restore_verified') is not True:
        raise ValueError('actual ordinary restore qualification required for calendar adoption')
    day=datetime.fromisoformat(evidence['scheduled_night']).date()
    if day.isoformat()!=evidence['scheduled_night']:raise ValueError('canonical accepted evening required')
    start,end=bounds(day);finished=datetime.fromisoformat(evidence['completed_UTC'])
    if not start<=finished<end:raise ValueError('late or out-of-window completion cannot suppress a backup')
    value=dict(day=day.isoformat(),attempts=0,status='completed',finished_utc=finished.isoformat(),
        configuration_sha256=configuration_sha256,adopted_ordinary_cycle_id=evidence['accepted_cycle_id'],
        accepted_baseline_sha256=evidence['accepted_baseline_sha256'])
    if state is not None and state!=value:
        raise ValueError('existing calendar state differs from actual adoption; preserve it for reconciliation')
    return value


def next_launch(now,state,*,monotonic,boot_id):
    """First installed quarter-hour pulse that the Toronto gate can admit."""
    from datetime import timedelta
    answer,_=decision(now,state,monotonic=monotonic,boot_id=boot_id)
    if answer['status'] in ('needs_review','clock_before_recorded_day'):
        raise ValueError('existing calendar state requires reconciliation before adoption')
    if 'next_at' in answer:return answer,datetime.fromisoformat(answer['next_at'])
    earliest=now.timestamp()+answer.get('retry_in_seconds',0)
    pulse=datetime.fromtimestamp((int(earliest)//900+1)*900,timezone.utc)
    if pulse>=bounds(night(now))[1]:pulse=bounds(night(now)+timedelta(days=1))[0]
    return answer,pulse


def main():
    import os,time
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--calendar',type=Path,required=True);parser.add_argument('--sha256',required=True)
    parser.add_argument('--journal-script',type=Path,required=True)
    parser.add_argument('--journal-sha256',required=True)
    parser.add_argument('--journal-receipt',type=Path,required=True)
    parser.add_argument('--legacy-owners',type=Path,required=True);parser.add_argument('--legacy-sha256',required=True)
    parser.add_argument('--install',action='store_true');args=parser.parse_args()
    if hashlib.sha256(args.journal_script.read_bytes()).hexdigest()!=args.journal_sha256:
        raise ValueError('installed journal script differs')
    if args.journal_script.resolve()!=Path(__file__).with_name('vk_nightly_journal_delivery.py').resolve():
        raise ValueError('same versioned commissioning/journal implementation required')
    read_owned(args.legacy_owners,args.legacy_sha256)
    if args.journal_receipt.with_suffix('.review.private.json').exists():
        raise ValueError('retained journal failure needs owner reconciliation before adoption')
    disabled=read_owned(args.calendar,args.sha256);enabled=enabled_configuration(disabled)
    package=args.calendar.parent;staging=Path(disabled['staging'])
    if storage(package)!=package or storage(staging)!=staging or staging.is_symlink():
        raise ValueError('canonical mounted SSD code and bounded calendar controls required')
    for name,expected in disabled['source_sha256'].items():
        if Path(name).name!=name or not name.endswith('.py') or hashlib.sha256((package/name).read_bytes()).hexdigest()!=expected:
            raise ValueError('exact installed calendar source differs')
    reference=disabled['current_service'];value,workers=load_service(Path(reference['config']),reference['sha256'],folder=package)
    if value.get('existing_components') or value['cycle']['cycle_binding'].get('cycle_kind')!='incremental':
        raise ValueError('ordinary whole-cycle package required')
    started=time.monotonic();worker=workers['files']
    def guard():host_guard(worker,started)
    owner=Source(value['cycle']['files']['source_observer'],worker['B_controls'],guard=guard)
    with mcp_lease(Path(value['controller_lease'])),mcp_lease(package/'commissioning.lease'):
        owner.check()
        # Actual native identity/health/capacity/STOP checks and both capture
        # leases remain held through cron readback; no backup body is started.
        with DesktopObjects(worker['desktop'],guard=guard),DesktopControls(worker['B_controls'],guard=guard) as remote:
            store=CycleState(remote.client,value['ledger'],guard=guard)
            evidence=qualification(store,value,reference['sha256'],guard=owner.check)
            journal=journal_qualification(remote.client,owner,read_owned(args.journal_receipt),
                service_sha=reference['sha256'],script_sha=args.journal_sha256,legacy_sha=args.legacy_sha256)
            evidence['between_run_journal_delivery']=journal
            if not args.install:print(json.dumps(evidence));return 0
            target=package/'calendar.enabled.private.json'
            raw=(json.dumps(enabled,sort_keys=True,separators=(',',':'))+'\n').encode()
            if len(raw)>1024**2:raise ValueError('bounded enabled calendar configuration required')
            # Versioned no-replace configuration. An identical retry is safe;
            # a differing incumbent must be reconciled, never overwritten.
            if target.exists():read_owned(target,hashlib.sha256(raw).hexdigest())
            else:
                fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                # A failed write retains its partial inode for reconciliation.
                with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
                directory=os.open(package,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
                try:os.fsync(directory)
                finally:os.close(directory)
            enabled_sha=hashlib.sha256(raw).hexdigest();read_owned(target,enabled_sha)
            owned=block(package,target,enabled_sha,Path(disabled['staging'])/'calendar.log',
                        resource_limits=enabled['worker_resource_limits'])
            owned=owned[:-len(END)]+cron_line(args.journal_script,args.journal_sha256,package,
                Path(reference['config']),reference['sha256'],args.journal_receipt,args.legacy_owners,
                args.legacy_sha256,staging/'journal-delivery.log')+END
            def ready():
                owner.check()
                fresh=qualification(store,value,reference['sha256'],guard=owner.check)
                fresh['between_run_journal_delivery']=journal_qualification(remote.client,owner,
                    read_owned(args.journal_receipt),service_sha=reference['sha256'],
                    script_sha=args.journal_sha256,legacy_sha=args.legacy_sha256)
                if fresh!=evidence:raise ValueError('accepted baseline changed during commissioning')
            folder=staging/'calendar';folder.mkdir(mode=0o700,exist_ok=True)
            if folder.resolve()!=folder or folder.is_symlink():raise ValueError('canonical calendar state directory required')
            with calendar_lease(folder/'lease'):
                state=calendar_state(folder/'state.private.json')
                state=adopt_completed_night(state,evidence,enabled_sha)
                ready()
                calendar_checkpoint(folder/'state.private.json',state)
                # A failed cron update retains this truthful accepted-night
                # checkpoint. Identical retry is safe and cannot recapture it.
                now=datetime.now(timezone.utc)
                answer,next_run=next_launch(now,state,monotonic=time.monotonic(),
                    boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
                installed=apply(owned,ready,timezone=Path('/etc/timezone').read_text().strip())
            print(json.dumps(dict(evidence,installation=installed,enabled_configuration=str(target),
                enabled_configuration_sha256=enabled_sha,calendar_decision=answer,
                next_run_UTC=next_run.isoformat(),next_run_Toronto=next_run.astimezone(ZONE).isoformat(),schedule_enabled=True)))
    return 0


if __name__=='__main__':raise SystemExit(main())
