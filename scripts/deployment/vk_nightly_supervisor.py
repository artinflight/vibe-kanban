"""Unprivileged fixed nightly entrypoint with lifetime resource checks.

No timer/cron installation, service handover, root inspection or source cleanup.
The child is the pinned adjacent nightly job, never a manifest command. Global
lane/desktop maintenance coordination still belongs to its existing controller;
observing processes is not an atomic admission fence.
"""
import argparse
import json
import os
import re
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time
import urllib.request

from vk_archive_store import SSH
from vk_nightly_job import checksum, validate
from vk_prep_common import save, storage


MEMORY_FLOOR = 5 * 1024**3 // 2
SWAP_FLOOR = 512 * 1024**2
MAX_CODING_ENTRIES = 7


def exit_code(result):
    if result['passed']:return 0
    # The existing producer leases/reconciliation still gate the next attempt.
    # A lifetime resource abort must not silently disable future nightlies.
    return 75 if result['status'] in ('resource_deferred','guard_aborted','observation_blocked') else 1


def host_admission(meminfo, coding_entries):
    if meminfo['MemAvailable'] < MEMORY_FLOOR or meminfo['SwapFree'] < SWAP_FLOOR:
        return 'host memory/swap floor'
    if type(coding_entries) is not int or not 0 <= coding_entries <= MAX_CODING_ENTRIES:
        return 'tracked coding lane limit or unverifiable inventory'
    return None


def observe(config):
    settings = config['supervisor']
    mem = {k: int(v.split()[0]) * 1024 for k, v in
           (row.split(':', 1) for row in Path('/proc/meminfo').read_text().splitlines())
           if k in ('MemAvailable', 'SwapFree')}
    with sqlite3.connect(Path(settings['primary_database']).as_uri() + '?mode=ro', uri=True, timeout=2) as db:
        count = db.execute("SELECT count(*) FROM execution_processes WHERE status='running' AND dropped=0 AND run_reason='codingagent'").fetchone()[0]
    result = {'memory': mem, 'tracked_coding_entries': count, 'reason': host_admission(mem, count)}
    if result['reason']:
        return result  # Do not open another Desktop/health channel when deferred.
    unit=settings['live_unit']
    if not re.fullmatch('vibe-kanban-[A-Za-z0-9-]+[.]service',unit):
        raise ValueError('fixed current Vibe user unit required')
    state=subprocess.run(['systemctl','--user','show',unit,'-p','MainPID','-p','ActiveState','-p','FreezerState'],
                         capture_output=True,text=True,timeout=5)
    fields=dict(row.split('=',1) for row in state.stdout.splitlines() if '=' in row)
    if state.returncode or fields.get('ActiveState')!='active' or fields.get('FreezerState')!='running':
        raise ValueError('current runtime is unavailable or frozen; not a fallback adoption')
    pid=int(fields['MainPID'])
    info=Path('/proc',str(pid),'exe').stat()
    if [info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns]!=settings['backend_identity']:
        raise ValueError('live backend differs from captured release binding')
    env=Path('/proc',str(pid),'environ').read_bytes().split(b'\0')
    front=next((row.split(b'=',1)[1].decode() for row in env if row.startswith(b'VK_FRONTEND_DIST_DIR=')),None)
    if front is None or str(Path(front).resolve())!=settings['frontend_root']:
        raise ValueError('live frontend differs from captured release binding')
    result['current_runtime_pid']=pid
    url = settings['health_url']
    from urllib.parse import urlsplit
    parsed = urlsplit(url)
    if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or parsed.path != '/api/health'
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError('fixed loopback health endpoint required')
    started = time.monotonic()
    with urllib.request.urlopen(url, timeout=3) as response:
        if response.status != 200 or time.monotonic() - started > 1:
            result['reason'] = 'slow or failed current backend health'
    probe = subprocess.run(SSH, input="import json,os,shutil\nassert os.stat('B:/').st_dev==" +
                           repr(config['volume_device']) +
                           ";print(json.dumps(shutil.disk_usage('B:/').free))\n",
                           text=True, capture_output=True, timeout=20)
    if probe.returncode or len(probe.stdout) > 4096:
        raise ValueError('B volume/capacity observation unavailable')
    result['B_free_bytes'] = json.loads(probe.stdout)
    if type(result['B_free_bytes']) is not int or result['B_free_bytes'] < config['preserved_B_floor_bytes']:
        result['reason'] = 'B free-space floor'
    return result


def stop_owned(process, *, grace=30):
    # A live, unreaped Popen child is the leader of our newly created session.
    # Never signal an already-reaped numeric PGID or any production unit.
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
    return {'child_exit': process.returncode,
            'producer_quiescence': 'must still be attested by existing kernel leases and B job recovery'}


def supervise(launch, probe, record, *, timeout_seconds, interval=20, clock=time.monotonic, sleep=time.sleep):
    """Trusted source callbacks only; no execution callback comes from JSON."""
    started = clock()
    try:
        first = probe()
    except (OSError, ValueError, sqlite3.Error, subprocess.SubprocessError) as error:
        result = {'passed': False, 'status': 'observation_blocked', 'reason': type(error).__name__, 'job_started': False}
        record(result); return result
    record({'event': 'preflight', 'sample': first})
    if first.get('reason'):
        result = {'passed': False, 'status': 'resource_deferred', 'reason': first['reason'], 'job_started': False}
        record(result); return result
    process = launch()
    bad = 0
    try:
        while process.poll() is None:
            if clock() - started >= timeout_seconds:
                result = {'passed': False, 'status': 'job_timeout', 'reason': 'finite whole-job deadline'}
                break
            try:
                sample = probe()
                record({'event': 'lifetime_sample', 'sample': sample, 'seconds': clock() - started})
                bad = bad + 1 if sample.get('reason') else 0
            except (OSError, ValueError, sqlite3.Error, subprocess.SubprocessError) as error:
                # Losing visibility is a failure, not an assumed healthy host.
                sample = {'reason': 'observation unavailable: ' + type(error).__name__}; bad = 2
            if bad >= 2:
                result = {'passed': False, 'status': 'guard_aborted', 'reason': sample['reason']}
                break
            sleep(min(interval, max(0, timeout_seconds - (clock() - started))))
        else:
            result = {'passed': process.returncode == 0, 'status': 'job_completed', 'child_exit': process.returncode}
    finally:
        termination = stop_owned(process)
    result.update(job_started=True, seconds=clock() - started, termination=termination)
    record(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--config-sha256', required=True)
    parser.add_argument('--check-admission', action='store_true')
    parser.add_argument('--enroll-fresh', action='store_true')
    args = parser.parse_args()
    if os.getuid()==0:raise ValueError('existing unprivileged account required')
    if checksum(args.config) != args.config_sha256:
        raise ValueError('supervised nightly configuration changed')
    config = json.loads(args.config.read_text())
    if args.check_admission:
        result = observe(config)
        print(json.dumps(result)); return 0 if not result.get('reason') else 75
    # No disabled configuration can launch capture even if all host probes pass.
    if config.get('adoption_authorized') is not True or config.get('retention_adopted') is not True:
        raise ValueError('whole-plan acceptance and normal-nightly adoption required')
    first=observe(config)
    if first.get('reason'):
        print(json.dumps({'passed':False,'status':'resource_deferred','job_started':False,'sample':first}))
        return 75  # No full runtime hashing, metadata census or capture yet.
    plan = json.loads(Path(config['plan_path']).read_text()); validate(config, plan)
    if 'vk_nightly_supervisor.py' not in config['source_sha256']:
        raise ValueError('supervisor code pin missing')
    timeout = config.get('initial_job_timeout_seconds', config['job_timeout_seconds'])
    if type(timeout) is not int or not 0 < timeout <= 14400:
        raise ValueError('finite reviewed whole-job deadline required')
    folder = storage(config['staging']); folder.mkdir(parents=True, exist_ok=True)
    import uuid
    receipt = folder / ('supervisor-' + uuid.uuid4().hex + '.private.json')
    events = []
    def record(value):
        events.append(value)
        # At most one preflight/sample per 20s over the bounded four-hour job.
        if len(events) > 725: raise ValueError('supervisor observation bound exceeded')
        save(receipt, {'events': events, 'configuration_sha256': args.config_sha256})
    def launch():
        argv=[sys.executable, '-B', '-S', str(Path(__file__).with_name('vk_nightly_job.py')),
              '--config', str(args.config), '--config-sha256', args.config_sha256]
        if args.enroll_fresh:argv.append('--enroll-fresh')
        return subprocess.Popen(argv,start_new_session=True)
    result = supervise(launch, lambda: observe(config), record, timeout_seconds=timeout)
    print(json.dumps({'passed': result['passed'], 'status': result['status'], 'receipt': str(receipt)}))
    return exit_code(result)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, sqlite3.Error, subprocess.SubprocessError) as error:
        print(json.dumps({'passed': False, 'status': 'nightly_supervisor_blocked', 'reason': str(error)}), file=sys.stderr)
        raise SystemExit(1)
