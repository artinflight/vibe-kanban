"""Finite between-run journal delivery; never a file/SQL capture or census.

The continuous observer stays unchanged. This one-shot yields to the shared
controller/body lanes and exact still-running legacy producers. Only an actual
independently reopened B commit may acknowledge/prune the bounded local outbox.
A failed delivery preserves both the outbox and last successful receipt.
"""
import argparse
from contextlib import ExitStack
from datetime import datetime,timedelta,timezone
import copy
import hashlib
import json
from pathlib import Path
import re
import time

from vk_nightly_capture_adapter import mcp_lease
from vk_nightly_file_cycle import Source,optional_report,read_owned
from vk_nightly_service import load as load_service,original_process_present,failure_exit_code
from vk_nightly_typed_worker import host_guard


def deliver(source,*,binding,previous=None,guard):
    """An unchanged authenticated source needs no B connection/health query."""
    guard();health=source.check()
    if previous is not None:
        if previous.get('binding')!=binding:raise ValueError('journal receipt belongs to another installed binding')
        old=previous['delivery']
        if (old.get('instance')==health['instance'] and old.get('sequence',-1)>=health['sequence']):
            return dict(phase='unchanged-source-no-B-query',last_success=previous,B_probed=False)
    proof=source.deliver()
    if (proof.get('instance')!=health['instance'] or proof.get('sequence',-1)<health['sequence']
            or proof.get('actual_native_B_reopen_verified') is not True
            or proof.get('local_acknowledged')!=proof['sequence']
            or proof.get('local_changes_pruned') is not True):
        raise ValueError('actual independent B delivery and exact source ACK required')
    guard()
    return dict(format='vk-nightly-between-run-journal-delivery-v1',binding=binding,
        completed_UTC=datetime.now(timezone.utc).isoformat(),delivery=proof,
        phase='journal-delivery-verified',B_probed=True,source_body_bytes_read=0,
        global_namespace_audits_started=0,whole_baseline_accepted=False)


def serial_delivery(leases,legacy,action,*,present=original_process_present):
    """Nonblocking real flock exclusion, including inherited old body owners."""
    def busy():return any(present(ref) for ref in legacy)
    if busy():return dict(phase='existing-legacy-component-owns-delivery',B_probed=False)
    with ExitStack() as stack:
        try:
            for path in leases:stack.enter_context(mcp_lease(Path(path)))
        except BlockingIOError:return dict(phase='existing-backup-owns-delivery',B_probed=False)
        if busy():return dict(phase='existing-legacy-component-owns-delivery',B_probed=False)
        return action()


def checked_delivery(action,review,*,binding):
    """Use the existing service failure policy; never minute-retry a denial."""
    if review.exists():
        read_owned(review)
        raise ValueError('retained journal failure requires owner reconciliation; no B retry')
    try:return action()
    except Exception as error:
        if failure_exit_code(error)!=75:
            optional_report(review,dict(format='vk-nightly-journal-review-required-v1',binding=binding,
                type=type(error).__name__,reason=str(error)[:4096],
                reported_drive_fault_not_inferred_from_timeout=True,
                previous_delivery_and_outbox_preserved=True))
        raise


def cron_line(script,script_sha,package,service,service_sha,receipt,legacy,legacy_sha,log):
    """One bounded minute pulse in the same owned Nightly cron block."""
    import os
    for path in (script,package,service,receipt,legacy,log):
        if not re.fullmatch('/[A-Za-z0-9_./-]+',str(path)) or '..' in str(path).split('/'):
            raise ValueError('fixed canonical journal paths required')
    for sha in (script_sha,service_sha,legacy_sha):
        if not re.fullmatch('[0-9a-f]{64}',sha):raise ValueError('exact journal pins required')
    if os.getuid()==0:raise ValueError('normal unprivileged journal owner required')
    return ('* * * * * /usr/bin/env XDG_RUNTIME_DIR=/run/user/'+str(os.getuid())
        +' PYTHONPATH='+str(package)+' /usr/bin/systemd-run --user --scope --quiet --collect '
        '--property=CPUQuota=5\\% --property=MemoryHigh=128M --property=MemoryMax=256M '
        '--property=MemorySwapMax=0 --property=TasksMax=32 '
        '/usr/bin/timeout --signal=TERM --kill-after=5 55 '
        '/usr/bin/nice -n 19 /usr/bin/ionice -c 3 /usr/bin/python3 -B -S '+str(script)
        +' --service '+str(service)+' --sha256 '+service_sha+' --self-sha256 '+script_sha
        +' --receipt '+str(receipt)+' --legacy-owners '+str(legacy)+' --legacy-sha256 '+legacy_sha
        +' 2>&1 | /usr/bin/tail -c 65536 > '+str(log)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--service',type=Path,required=True);p.add_argument('--sha256',required=True)
    p.add_argument('--self-sha256',required=True);p.add_argument('--receipt',type=Path,required=True)
    p.add_argument('--legacy-owners',type=Path,required=True);p.add_argument('--legacy-sha256',required=True)
    args=p.parse_args()
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=args.self_sha256:
        raise ValueError('installed journal entrypoint differs')
    value,workers=load_service(args.service,args.sha256)
    if value.get('existing_components'):raise ValueError('ordinary service binding required')
    legacy=read_owned(args.legacy_owners,args.legacy_sha256)
    if not isinstance(legacy,list) or len(legacy)>8:raise ValueError('bounded exact legacy birth records required')
    for ref in legacy:
        if set(ref)!={'owner_pid','owner_start_ticks'} or any(type(v) is not int or v<=0 for v in ref.values()):
            raise ValueError('exact legacy owner birth required')
    receipt=args.receipt
    if (not receipt.is_absolute() or receipt.resolve()!=receipt or not receipt.is_relative_to('/mnt/vk-storage')
            or receipt.parent!=args.service.parent):raise ValueError('fixed mounted SSD receipt beside service required')
    worker=copy.deepcopy(workers['files']);started=time.monotonic()
    # This separate metadata operation has its own finite observation deadline;
    # it never extends or changes the backup body's Toronto hard04 window.
    deadline=(datetime.now(timezone.utc)+timedelta(seconds=50)).isoformat()
    worker.update(timeout_seconds=50,whole_cycle_deadline_UTC=deadline)
    controls=dict(worker['B_controls'],whole_cycle_deadline_UTC=deadline)
    guard=lambda:host_guard(worker,started)
    source=Source(value['cycle']['files']['source_observer'],controls,guard=guard)
    binding=dict(service_sha256=args.sha256,entrypoint_sha256=args.self_sha256,
        source_observer=source.reference,B_delivery_target=source.config['B_delivery_target'],
        legacy_owners_sha256=args.legacy_sha256)
    def action():
        previous=read_owned(receipt) if receipt.exists() else None
        result=deliver(source,binding=binding,previous=previous,guard=guard)
        if result['phase']=='journal-delivery-verified':optional_report(receipt,result)
        return result
    result=serial_delivery([value['controller_lease'],worker['desktop']['writer_lease']],legacy,lambda:checked_delivery(action,receipt.with_suffix('.review.private.json'),binding=binding))
    print(json.dumps(result));return 0


if __name__=='__main__':raise SystemExit(main())
