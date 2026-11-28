"""Observe one finite catch-up through the existing WakeWatch owner and ledger."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time


def read(path):
    path = Path(path)
    if path.stat().st_size > 4 * 1024**2:
        raise ValueError('bounded observer record required')
    return json.loads(path.read_bytes())


def unit(name):
    text = subprocess.check_output(['systemctl', '--user', 'show', name,
        '-p', 'ActiveState', '-p', 'MainPID', '-p', 'InvocationID'], text=True, timeout=5)
    return dict(line.split('=', 1) for line in text.splitlines() if '=' in line)


def snapshot(config, now, service_reader=unit):
    state_root = Path(config['incremental_state_root'])
    folder = Path(config['operation_root'])
    expected = config['operation']
    status = service_reader(config['controller_unit'])
    current = (read(state_root/'ACTIVE.private.json')
               if not config.get('terminal_only', False) and (state_root/'ACTIVE.private.json').exists()
               else read(folder/'RESULT.private.json'))
    if current['operation'] != expected or Path(current['folder']) != folder:
        raise ValueError('foreign incremental run')
    selection = read(folder/'SELECTION.private.json')
    if current['total_batches'] != len(selection) or current['selected_files'] != sum(len(b['rows']) for b in selection):
        raise ValueError('current finite selection differs')
    if not 0 <= current['completed_batches'] <= len(selection):
        raise ValueError('invalid committed batch count')
    converted = excluded = raw_bytes = reclaimed = prior_resolved = 0
    prior_paths = set(config.get('historically_resolved_paths', []))
    overlap = sum(r['path'] in prior_paths for b in selection for r in b['rows'])
    for number in range(current['completed_batches']):
        batch = read(folder/('BATCH-%04d.private.json' % number))
        if batch.get('independent_recovery_verified') is not True:
            raise ValueError('batch lacks independent recovery proof')
        selected_paths = {r['path'] for r in selection[number]['rows']}
        if (len(set(batch['nonbeneficial'])) != len(batch['nonbeneficial'])
                or not set(batch['nonbeneficial']).issubset(selected_paths)
                or batch['converted_files'] + len(batch['nonbeneficial']) != len(selected_paths)):
            raise ValueError('batch selection is not completely resolved')
        prior_resolved += sum(r['path'] in prior_paths for r in selection[number]['rows'])
        converted += batch['converted_files']
        excluded += len(batch['nonbeneficial'])
        if batch.get('result'):
            reference = batch['result']
            path = Path(reference['path'])
            if path.parent != folder/('batch-%04d' % number) or path.name != 'RESULT.private.json':
                raise ValueError('foreign batch result')
            if hashlib.sha256(path.read_bytes()).hexdigest() != reference['sha256']:
                raise ValueError('changed batch result')
            result = read(path)
            if not result['complete'] or not result['normal_B_original_and_graph_verified']:
                raise ValueError('batch is not complete')
            raw_bytes += result['raw_bytes']
            reclaimed += result['allocated_release_including_objects_and_directories']
    if (converted, excluded) != (current['converted_files'], current['excluded_files']):
        raise ValueError('committed counters differ')
    progress = read(folder/'PROGRESS.private.json') if (folder/'PROGRESS.private.json').exists() else {'at':current['started_at'], 'phase':current['phase']}
    if not 0 <= now-progress['at']:
        raise ValueError('invalid progress clock')
    state = 'running'
    phase = progress['phase']
    attention = False
    if current['phase'] == 'complete':
        if current['selected_scope_resolved']:
            if current['completed_batches'] != len(selection) or converted+excluded != current['selected_files']:
                raise ValueError('success claim lacks complete committed selection')
            state = 'success'
            phase = 'catchup_complete_final_acceptance_pending'
        else:
            state = 'controller_stopped'
            phase = 'finite_budget_boundary_remaining_selection'
        attention = True
    elif current['phase'] == 'needs_review':
        state = 'failure_recovery_pending'
        attention = True
    elif (status['ActiveState'] != 'active' or status['MainPID'] != str(config['controller_pid'])
          or status['InvocationID'] != config['controller_invocation']):
        state = 'controller_stopped'
        attention = True
    elif now-progress['at'] >= 600:
        state = 'stalled'
        attention = True
    return dict(operation=expected, attempt=config.get('attempt_label','catchup-r2'), state=state, phase=phase,
                needs_attention=attention, checked_at=now, progress_at=progress['at'],
                recovered=False, cutover_only=False, completed_files=converted,
                resolved_files=converted+excluded, total_files=current['selected_files'],
                completed_batches=current['completed_batches'], total_batches=len(selection),
                completed_raw_bytes=raw_bytes, allocated_recovery_bytes=reclaimed,
                historically_resolved_overlap=overlap, historically_resolved_completed=prior_resolved)


def cumulative_payload(config, result):
    row = result.get('source') or {}
    if result.get('source_error') or 'total_files' not in row:
        return dict(version=1, observed=int(result['at']), state='unavailable')
    old = read(Path(config['historical_operation_root'])/'COMMITTED.private.json')
    if old['operation'] != config['historical_operation']:
        raise ValueError('historical operation differs')
    keys = ['completed_files', 'resolved_files', 'total_files', 'completed_batches',
            'total_batches', 'completed_raw_bytes']
    payload = dict(version=1, observed=int(result['at']), progress=int(row['progress_at']),
                   state=row['state'].lower(), phase=row['phase'].lower())
    payload.update({key:int(old[key])+int(row[key]) for key in keys})
    payload['total_files'] -= row.get('historically_resolved_overlap', 0)
    payload['resolved_files'] -= row.get('historically_resolved_completed', 0)
    payload['reclaimed_bytes'] = (old.get('canary_live_log_allocated_recovery', 0)
        + sum(b['allocated_release'] for b in old['batches']) + row['allocated_recovery_bytes'])
    return payload


def main():
    # Only the sensor changes. The installed event ledger, queue/owner guard,
    # capacity/approval client and exactly-once delivery code remain in charge.
    if '--config' not in sys.argv:
        raise ValueError('exact existing-owner configuration required')
    config = read(sys.argv[sys.argv.index('--config')+1])
    source = Path(config['existing_watcher_source']['path'])
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != config['existing_watcher_source']['sha256']:
        raise ValueError('existing watcher source changed')
    sys.path.insert(0, str(source.parent))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader('existing_dedup_watch', loader=None))
    module.__file__ = str(source)
    exec(compile(raw, str(source), 'exec'), module.__dict__)
    module.snapshots = snapshot
    module.control_observation.retirement_supplement = lambda config,row,previous,now:(row,None)
    module.rainmeter_feed.payload = cumulative_payload
    module.main()


if __name__ == '__main__':
    main()
