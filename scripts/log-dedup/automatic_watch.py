"""Observe recurring conversion through the same installed WakeWatch tick."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

from incremental_watch import read, snapshot as finite_snapshot, cumulative_payload


def unit(name):
    raw = subprocess.check_output(['systemctl','--user','show',name,'-p','ActiveState',
        '-p','MainPID','-p','InvocationID','-p','Result'],text=True,timeout=5)
    return dict(line.split('=',1) for line in raw.splitlines() if '=' in line)



def read_rollup(config):
    path=Path(config['incremental_state_root'])/'ROLLUP.private.json'
    try:raw=path.read_bytes()
    except FileNotFoundError:return None,dict(resolved_paths=config['historically_resolved_paths'],runs=[])
    if len(raw)>4*1024**2:raise ValueError('bounded cumulative receipt required')
    return hashlib.sha256(raw).hexdigest(),json.loads(raw)


def snapshot(config, now, service_reader=unit):
    root = Path(config['incremental_state_root'])
    rollup_pin,cumulative=read_rollup(config)
    active = read(root/'ACTIVE.private.json') if (root/'ACTIVE.private.json').exists() else None
    automatic = read(root/'AUTOMATIC_STATUS.private.json') if (root/'AUTOMATIC_STATUS.private.json').exists() else None
    if active:
        operation = active['operation']
        folder = root/'runs'/operation
        if Path(active['folder']) != folder or len(operation) != 32 or any(c not in '0123456789abcdef' for c in operation):
            raise ValueError('foreign active converter run')
        if operation in {r['operation'] for r in cumulative['runs']}:
            raise ValueError('active run was already included in cumulative totals')
        if operation == config['initial_operation']:
            binding = config['initial_controller']
            attempt = 'catchup-r2'
        else:
            if not automatic or automatic['controller_unit'] != config['automatic_controller_unit']:
                raise ValueError('new active run lacks its automatic owner')
            binding = {k:automatic[k] for k in ('controller_unit','controller_pid','controller_invocation')}
            attempt = 'automatic'
        effective = dict(config,operation=operation,operation_root=str(folder),
                         historically_resolved_paths=cumulative['resolved_paths'],attempt_label=attempt,**binding)
        return dict(finite_snapshot(effective,now,service_reader),cumulative_rollup_sha256=rollup_pin)
    status = service_reader(config['automatic_controller_unit'])
    hold_path = root/'AUTOMATIC_HOLD.private.json'
    hold = read(hold_path) if hold_path.exists() else None
    row = dict(operation=config['automatic_activation_id'],attempt='automatic-preflight',
               state='idle',phase='automatic_waiting_for_next_daytime_run',needs_attention=False,
               checked_at=now,progress_at=automatic.get('at',0) if automatic else 0,
               recovered=False,cutover_only=False,completed_files=0,resolved_files=0,total_files=0,
               completed_batches=0,total_batches=0,completed_raw_bytes=0,allocated_recovery_bytes=0,
               historically_resolved_overlap=0,historically_resolved_completed=0,
               cumulative_rollup_sha256=rollup_pin)
    if hold:
        if hold['phase'] != 'needs_review':
            raise ValueError('invalid automatic review hold')
        row.update(operation=hold['operation'],attempt='automatic',state='failure_recovery_pending',
                   phase='automatic_conversion_requires_review',needs_attention=True,progress_at=hold['at'])
    elif status.get('ActiveState') == 'failed' or status.get('Result') not in (None,'success'):
        # One deployment-bound preflight incident, even if the timer encounters
        # the same changed/missing package again. No blind billed retries.
        row.update(state='failure_recovery_pending',phase='automatic_preflight_failed',needs_attention=True)
    elif automatic and automatic['phase'] == 'starting':
        matches = (status['ActiveState']=='active' and status['MainPID']==str(automatic['controller_pid'])
                   and status['InvocationID']==automatic['controller_invocation'])
        row.update(operation=automatic['operation'],attempt='automatic',state='running' if matches else 'controller_stopped',
                   phase='automatic_preflight_or_final_index_verification',needs_attention=not matches)
        if matches and now-automatic['started_at']>=600:
            row.update(state='stalled',needs_attention=True)
    elif automatic and automatic['phase'] == 'idle':
        if hashlib.sha256((root/'ROLLUP.private.json').read_bytes()).hexdigest()!=automatic['rollup_sha256']:
            raise ValueError('automatic cumulative result changed')
    return row


def payload(config, result):
    row = dict(result.get('source') or {})
    root = Path(config['incremental_state_root'])
    pin,totals=read_rollup(config)
    if pin != row.get('cumulative_rollup_sha256'):
        return dict(version=1,observed=int(result['at']),state='unavailable')
    if pin and not result.get('source_error'):
        mapping = dict(completed_files='converted_files',resolved_files='resolved_files',
                       total_files='resolved_files',completed_batches='completed_batches',
                       total_batches='total_batches',completed_raw_bytes='raw_bytes',
                       allocated_recovery_bytes='allocated_recovery_bytes')
        for target,key in mapping.items():row[target]=row.get(target,0)+totals[key]
    return cumulative_payload(config,dict(result,source=row))


def main():
    if '--config' not in sys.argv:raise ValueError('exact existing-owner config required')
    config = read(sys.argv[sys.argv.index('--config')+1])
    for ref in config['automatic_monitor_sources']:
        if hashlib.sha256(Path(ref['path']).read_bytes()).hexdigest()!=ref['sha256']:
            raise ValueError('automatic monitor dependency changed')
    ref=config['existing_watcher_source'];source=Path(ref['path']);raw=source.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=ref['sha256']:raise ValueError('existing watcher changed')
    sys.path.insert(0,str(source.parent))
    module=importlib.util.module_from_spec(importlib.util.spec_from_loader('existing_dedup_watch',loader=None))
    module.__file__=str(source);exec(compile(raw,str(source),'exec'),module.__dict__)
    module.snapshots=snapshot
    module.control_observation.retirement_supplement=lambda config,row,previous,now:(row,None)
    module.rainmeter_feed.payload=payload
    module.main()


if __name__=='__main__':main()
