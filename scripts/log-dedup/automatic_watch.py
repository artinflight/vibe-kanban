"""Observe recurring conversion through the same installed WakeWatch tick."""
import hashlib
import html
import os
import re
import time
import uuid
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
    values = cumulative_payload(config,dict(result,source=row))
    # Keep the already-installed Rainmeter parser compatible. Its WAITING
    # presentation accepts this token; a new idle token would look OFFLINE.
    if values['state'] == 'idle':values['state'] = 'waiting_for_current_turn'
    return values


def observe_with_initial(config, observe, store, registry, row, now, activated_at,
                         initial_reader=finite_snapshot):
    # Keep the already-authorized finite success fresh until the SAME ledger
    # accepts it. An active owner can defer delivery across monitor replacement.
    # Original observe() preserves accepted/queued/uncertain dispatches exactly.
    initial = config['initial_operation']
    folder = Path(config['incremental_state_root'])/'runs'/initial
    if row['operation'] != initial and (folder/'RESULT.private.json').exists():
        if config.get('initial_acceptance'):
            import checkpoint_watch
            checkpoint_watch.acknowledge_initial(config, store, registry, now)
            return observe(store, registry, row, now, activated_at)
        effective = dict(config, operation=initial, operation_root=str(folder),
                         attempt_label='catchup-r2', terminal_only=True,
                         **config['initial_controller'])
        previous = initial_reader(effective, now)
        if previous['state'] != 'success':
            raise ValueError('initial catch-up terminal acceptance changed')
        observe(store, registry, previous, now, activated_at)
    return observe(store, registry, row, now, activated_at)


def public_html(values, result):
    labels = dict(idle='Automatic conversion is ready for its next daily run.',
                  waiting_for_current_turn='Automatic conversion is ready for its next daily run.',
                  running='Closed logs are being converted.',
                  success='Selected conversion finished; final checks are pending.',
                  stalled='Conversion needs attention: no recent verified progress.',
                  failure_recovery_pending='Conversion stopped and needs review.',
                  controller_stopped='Conversion stopped and needs review.',
                  unavailable='Current progress is unavailable.')
    state = values.get('state', 'unavailable')
    if any(not re.fullmatch('[a-z][a-z0-9_]*',str(k)) or
           not re.fullmatch('[a-z0-9_]+',str(v)) for k,v in values.items()):
        raise ValueError('bounded public HUD tokens required')
    resolved,total,converted = (values.get(k,0) for k in ('resolved_files','total_files','completed_files'))
    if not 0 <= converted <= resolved <= total:
        raise ValueError('inconsistent cumulative public counts')
    recovered = values.get('reclaimed_bytes',0)/1024**3
    checked = time.strftime('%Y-%m-%d %H:%M:%S UTC',time.gmtime(values['observed']))
    alert = '<p>Alert delivery needs attention.</p>' if result.get('event_error') else ''
    block = '<!-- VK_DEDUP_HUD_V1\n' + '\n'.join(f'{k}={v}' for k,v in values.items()) + '\nEND_VK_DEDUP_HUD -->'
    return ('<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Deduplication progress</title><style>body{font:18px system-ui;'
        'max-width:750px;margin:7vh auto;padding:24px;background:#101725;color:#e7edf6}'
        'dt{color:#aebed4;margin-top:18px}dd{margin:5px 0}</style>'
        '<h1>Deduplication progress</h1><p>'+html.escape(labels.get(state,'Progress needs review.'))+'</p>'
        +alert+'<dl><dt>Logs resolved / selected</dt><dd>'+str(resolved)+' / '+str(total)+'</dd>'
        '<dt>Logs converted and verified</dt><dd>'+str(converted)+'</dd>'
        '<dt>Space released from logs</dt><dd>'+format(recovered,'.2f')+' GiB</dd>'
        '<dt>Last monitoring check</dt><dd>'+checked+'</dd></dl>'
        '<p>These savings are before retained working copies and other staging. '
        'Final disk-space checks and Nightly backup qualification are still pending.</p>'
        '<p>Active logs and pending inputs are preserved. The original conversion '
        'and subsequent catch-up are included in these totals.</p>'
        '<p id="stale"></p><script>if(Date.now()/1000-'+str(values['observed'])+
        '>150)document.getElementById("stale").textContent="Monitoring is stale.";'
        'setTimeout(()=>location.replace(location.pathname+"?refresh="+Date.now()),10000);</script>'
        +block+'</html>')


def publish_status(config, result):
    raw = public_html(payload(config,result),result)
    target = Path(config['public_status'])
    temporary = target.with_name('.status-'+uuid.uuid4().hex)
    temporary.write_text(raw)
    temporary.chmod(0o644)
    os.replace(temporary,target)


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
    original_observe=module.observe
    def observe_all(store,registry,row,now,activated_at):
        result=observe_with_initial(config,original_observe,store,registry,row,now,activated_at)
        if config.get('checkpoint_jobs'):
            import checkpoint_watch
            result['checkpoints']=[original_observe(store,registry,
                checkpoint_watch.snapshot(job,now),now,activated_at)
                for job in config['checkpoint_jobs']]
        return result
    module.observe=observe_all
    if config.get('checkpoint_jobs'):
        original_bridge=module.make_bridge
        def make_bridge(config,store):
            import checkpoint_watch
            bridge=original_bridge(config,store)
            previous_prompt=bridge.event_prompt
            def prompt(rows,samples,batch):
                if any(samples[r['volume']]['event']['values'].get('job_kind')=='nightly_checkpoint' for r in rows):
                    return checkpoint_watch.checkpoint_prompt(rows,samples,batch,config['checkpoint_handoff'])
                return previous_prompt(rows,samples,batch)
            bridge.event_prompt=prompt
            return bridge
        module.make_bridge=make_bridge
    module.publish_status=publish_status
    module.control_observation.retirement_supplement=lambda config,row,previous,now:(row,None)
    module.rainmeter_feed.payload=payload
    module.main()


if __name__=='__main__':main()
