"""One daily bounded conversion; failures latch and never replay themselves."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import uuid
from zoneinfo import ZoneInfo

from incremental import read, save, source, digest


def verify_run(folder, *, require_complete=True):
    state = read(folder/'RESULT.private.json')
    selection = read(folder/'SELECTION.private.json')
    if (state['phase'] != 'complete' or Path(state['folder']) != folder
            or state['operation'] != folder.name
            or state['total_batches'] != len(selection)
            or state['selected_files'] != sum(len(b['rows']) for b in selection)
            or not 0 <= state['completed_batches'] <= len(selection)):
        raise ValueError('terminal selection binding differs')
    paths = set()
    converted = raw_bytes = reclaimed = 0
    controls = {str(folder/'INVENTORY.private.json'), str(folder/'SELECTION.private.json')}
    for number in range(state['completed_batches']):
        target = folder/('BATCH-%04d.private.json' % number)
        batch = read(target)
        chosen = {row['path'] for row in selection[number]['rows']}
        skipped = batch['nonbeneficial']
        if (batch.get('independent_recovery_verified') is not True
                or len(skipped) != len(set(skipped)) or not set(skipped).issubset(chosen)
                or batch['converted_files'] + len(skipped) != len(chosen)):
            raise ValueError('batch selection/recovery coverage differs')
        if paths & chosen:
            raise ValueError('duplicate selected path')
        paths.update(chosen)
        converted += batch['converted_files']
        controls.add(str(target))
        if batch['converted_files']:
            ref = batch['result']
            result_path = folder/('batch-%04d' % number)/'RESULT.private.json'
            if ref['path'] != str(result_path) or digest(result_path) != ref['sha256']:
                raise ValueError('batch result binding differs')
            result = read(result_path)
            if (result.get('complete') is not True
                    or result.get('normal_B_original_and_graph_verified') is not True
                    or result['files'] != batch['converted_files']):
                raise ValueError('converted batch lacks complete recovery')
            raw_bytes += result['raw_bytes']
            reclaimed += result['allocated_release_including_objects_and_directories']
    if converted != state['converted_files'] or len(paths)-converted != state['excluded_files']:
        raise ValueError('terminal counters differ')
    full = state['completed_batches'] == len(selection) and len(paths) == state['selected_files']
    if state['selected_scope_resolved'] != full or require_complete and not full:
        raise ValueError('finite selection remains unfinished')
    restored = set()
    for index in sorted(folder.glob('RUN_INDEX_*.private.json')):
        receipt = read(index)
        if receipt['actual_independent_normal_restore']['independent_owner_controls_restore_verified'] is not True:
            raise ValueError('run index lacks independent B restore')
        for row in receipt['checkpoint']['manifest']['files']:
            path = row['source']
            if path not in controls or digest(path) != row['member']['sha256']:
                raise ValueError('run index source binding differs')
            restored.add(path)
    if restored != controls:
        raise ValueError('sealed run indexes do not cover every control')
    return dict(operation=state['operation'], result_sha256=digest(folder/'RESULT.private.json'),
                converted_files=converted, resolved_paths=sorted(paths), raw_bytes=raw_bytes,
                allocated_recovery_bytes=reclaimed, completed_batches=state['completed_batches'],
                total_batches=len(selection), selected_scope_resolved=full)


def rollup(config):
    root = Path(config['state_root'])
    folders = sorted(p.parent for p in (root/'runs').glob('*/RESULT.private.json'))
    if len(folders) > 4096:
        raise ValueError('bounded run-ledger maintenance required')
    resolved = set(config['historically_resolved_paths'])
    result = dict(version=1, at=time.time(), runs=[], converted_files=0, resolved_files=0,
                  raw_bytes=0, allocated_recovery_bytes=0, completed_batches=0, total_batches=0)
    for folder in folders:
        value = verify_run(folder, require_complete=False)
        result['resolved_files'] += len(set(value['resolved_paths'])-resolved)
        resolved.update(value['resolved_paths'])
        for key in ('converted_files','raw_bytes','allocated_recovery_bytes','completed_batches','total_batches'):
            result[key] += value[key]
        result['runs'].append({key:value[key] for key in ('operation','result_sha256','selected_scope_resolved')})
    result['resolved_paths'] = sorted(resolved)
    save(root/'ROLLUP.private.json', result)
    return result


def allowed_window(timestamp):
    hour = datetime.fromtimestamp(timestamp, ZoneInfo('America/Toronto')).hour
    # A late Persistent timer may run after boot. Preserve the 22:00–04:00
    # Nightly window and four-hour conversion budget, including finish margin.
    return 5 <= hour < 17


def execute(config, invoke, *, now=time.time, initial_check=verify_run, summarize=rollup):
    root = Path(config['state_root'])
    hold = root/'AUTOMATIC_HOLD.private.json'
    status_path = root/'AUTOMATIC_STATUS.private.json'
    if hold.exists():
        raise ValueError('retained automatic failure requires exact review; no replay')
    if (root/'ACTIVE.private.json').exists():
        raise ValueError('existing converter operation retains custody; no duplicate')
    if not allowed_window(now()):
        value = dict(phase='waiting_for_daytime_window', at=now(), invocation_started=False)
        save(root/'AUTOMATIC_DEFERRED.private.json', value)
        return value
    attempt = uuid.uuid4().hex
    value = dict(operation=attempt, phase='starting', at=now(), started_at=now(),
                 controller_pid=os.getpid(), controller_invocation=os.environ.get('INVOCATION_ID'),
                 controller_unit=config['controller_unit'], provider_requests_created=0)
    save(status_path, value)
    try:
        initial_check(root/'runs'/config['initial_operation'])
        code = invoke()
        if code != 0:
            raise RuntimeError('pinned converter returned exit '+str(code))
        latest = read(root/'LATEST.private.json')
        if latest.get('phase') not in ('idle','complete') or latest.get('selected_scope_resolved') is not True:
            raise ValueError('converter did not finish its admitted selection')
        cumulative = summarize(config)
        value.update(phase='idle', finished_at=now(), at=now(), last_result=latest,
                     rollup_sha256=digest(root/'ROLLUP.private.json'),
                     cumulative_converted_files=cumulative['converted_files'])
        save(status_path, value)
        return value
    except BaseException as error:
        value.update(phase='needs_review', failed_at=now(), at=now(),
                     error_type=type(error).__name__, error=str(error))
        save(hold, value)
        save(status_path, value)
        raise


def main():
    import fcntl
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    args = parser.parse_args()
    config = json.loads(source(dict(path=str(args.config),sha256=args.sha256)))
    if config['format'] != 'vk-automatic-log-conversion-v1' or not os.path.ismount('/mnt/vk-storage'):
        raise ValueError('qualified mounted automatic package required')
    root = Path(config['state_root'])
    if root.resolve() != root or not root.is_relative_to('/mnt/vk-storage/vk-log-dedup-20261103-0815/production-20261117'):
        raise ValueError('canonical existing converter state required')
    if digest(__file__) != config['automatic_sha256']:
        raise ValueError('automatic source differs')
    for reference in config['sources']:
        source(reference)
    # Preserve the child's original production lock. This extra wrapper lock
    # merely serializes its status/rollup; it grants no source or B ownership.
    fd = os.open(root/'automatic.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    try:
        st = os.fstat(fd)
        if st.st_uid != os.getuid() or st.st_nlink != 1 or st.st_mode & 0o022:
            raise ValueError('automatic wrapper lock changed')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        runner = config['runner']
        configuration = config['runner_config']
        source(runner);source(configuration)
        command = ['/usr/bin/python3','-B',runner['path'],'--config',configuration['path'],
                   '--sha256',configuration['sha256']]
        result = execute(config,lambda:subprocess.run(command,check=False).returncode)
        print(json.dumps(result,sort_keys=True))
    finally:
        os.close(fd)


if __name__ == '__main__':
    main()
