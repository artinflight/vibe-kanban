"""DST-aware user-cron wake-up gate. No scheduler installation or cutover.

A fixed 15-minute cron pulse is interpreted using America/Toronto, independent
of the cron daemon's zone. Resource deferrals retry at most sixteen times in
02:00--10:00 local time. Unexpected capture failures require reconciliation;
no receipt, recovery success or remote notification is manufactured here.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, time as day_time, timedelta, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

from vk_nightly_capture_adapter import mcp_lease
from vk_nightly_job import checksum
from vk_prep_common import save, storage

ZONE = ZoneInfo('America/Toronto')
RETRY_SECONDS = 1800
MAX_ATTEMPTS = 16
POLL_SECONDS = 900
MAX_STATE = 65536


def scheduled(day):
    # Roundtrip resolves the nonexistent spring 02:00 to 03:00. Fall 02:00
    # occurs once in Toronto. No clock/host-zone setting is changed.
    return datetime.combine(day, day_time(2), ZONE).astimezone(timezone.utc)


def decision(now, state, *, monotonic, boot_id):
    if now.tzinfo is None:raise ValueError('aware real UTC clock required')
    local = now.astimezone(ZONE); day = local.date(); key = day.isoformat()
    next_night = scheduled(day + timedelta(days=1)).isoformat()
    if state and state.get('blocked'):
        return {'status':'needs_review','next_action':'review exact job receipt and recorded owned reconciliation; no blind retry'}, state
    if state and key < state['day']:
        return {'status':'clock_before_recorded_day','next_action':'wait for correct clock; preserve completed-day protection'}, state
    if local.hour < 2:
        return {'status':'not_due','next_at':scheduled(day).isoformat()}, state
    if local.hour >= 10:
        return {'status':'window_expired','next_at':next_night,'next_action':'automatic next-night attempt; scheduler remains enabled'}, state
    value = dict(state) if state and state['day'] == key else {'day':key,'attempts':0,'status':'pending'}
    if value['status'] == 'completed':
        return {'status':'already_completed','next_at':next_night}, value
    if value['attempts'] >= MAX_ATTEMPTS:
        return {'status':'retry_exhausted','next_at':next_night,'next_action':'automatic next-night attempt; preserve failure receipt'}, value
    if 'retry_utc' in value:
        if value.get('retry_boot') != boot_id or monotonic < value.get('retry_recorded_mono', 0):
            # Reboot/backward wall correction cannot impose an unbounded wait.
            remaining = max(0, min(RETRY_SECONDS, value['retry_utc'] - now.timestamp()))
            value.update(retry_boot=boot_id,retry_recorded_mono=monotonic,retry_mono=monotonic+remaining)
        if monotonic < value['retry_mono']:
            return {'status':'retry_wait','retry_in_seconds':value['retry_mono']-monotonic}, value
    return {'status':'due','day':key,'scheduled_utc':scheduled(day).isoformat()}, value


def finish(value, exit_code, now, *, monotonic, boot_id):
    value = dict(value)
    if exit_code == 0:
        value.update(status='completed',finished_utc=now.isoformat())
        for key in ('retry_utc','retry_boot','retry_recorded_mono','retry_mono'):value.pop(key,None)
    elif exit_code == 75:
        value.update(status='resource_deferred',retry_utc=now.timestamp()+RETRY_SECONDS,
                     retry_boot=boot_id,retry_recorded_mono=monotonic,retry_mono=monotonic+RETRY_SECONDS)
    else:
        value.update(status='needs_review',blocked=True,exit_code=exit_code)
    return value


@contextmanager
def held(path):
    fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK,0o600)
    try:
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid():raise ValueError('owned calendar lease required')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield fd
    finally:
        # close only: inherited supervisor FD keeps exclusion after parent death.
        os.close(fd)


def load(path):
    if not path.exists() and not path.is_symlink():return None
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        info=os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid():raise ValueError('owned calendar state required')
        raw=stream.read(MAX_STATE+1)
    if len(raw)>MAX_STATE:raise ValueError('calendar state bound exceeded')
    value=json.loads(raw)
    if (not isinstance(value,dict) or type(value.get('attempts')) is not int
            or not 0<=value['attempts']<=MAX_ATTEMPTS
            or value.get('status') not in ('pending','running','completed','resource_deferred','needs_review')
            or not isinstance(value.get('day'),str)
            or datetime.fromisoformat(value['day']).date().isoformat()!=value['day']):
        raise ValueError('malformed calendar state; preserve and review')
    if 'retry_utc' in value or value['status']=='resource_deferred':
        if any(type(value.get(k)) not in (int,float) or not math.isfinite(value[k]) or value[k]<0
               for k in ('retry_utc','retry_mono','retry_recorded_mono')) or not isinstance(value.get('retry_boot'),str):
            raise ValueError('malformed retry state; preserve and review')
    return value


def checkpoint(path, value):
    save(path,value)
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)


def tick(state_path, config_sha256, runner, producer_available, report, *, now, monotonic, boot_id):
    """Trusted fixed source callbacks; lease held by caller through child exit."""
    state=load(state_path)
    if state and state.get('configuration_sha256')!=config_sha256:
        raise ValueError('calendar configuration changed; reviewed controller rebinding required')
    answer,value=decision(now(),state,monotonic=monotonic(),boot_id=boot_id)
    if value is not None:
        value['configuration_sha256']=config_sha256;checkpoint(state_path,value)
    if answer['status']!='due':report(answer);return answer
    if not producer_available():
        answer={'status':'active_backup_deferred','next_check_seconds':POLL_SECONDS,
                'next_action':'wait for exact owned producer lease; do not kill or invent quiescence'}
        report(answer);return answer
    interrupted = value['status']=='running'
    value.update(status='running',attempts=value['attempts']+1,started_utc=now().isoformat())
    checkpoint(state_path,value)
    report({'status':'running','day':value['day'],'attempt':value['attempts'],
            'interrupted_previous_attempt':interrupted,
            'recovery':'existing B lifecycle reconciles only recorded owned resources under real leases'})
    failure=None
    try:
        code=runner()
        if type(code) is not int:raise ValueError('fixed child exit code unavailable')
    except (OSError,ValueError,subprocess.SubprocessError) as error:
        code=1;failure=type(error).__name__+': '+str(error)[:256]
    value=finish(value,code,now(),monotonic=monotonic(),boot_id=boot_id)
    checkpoint(state_path,value)
    answer={'status':value['status'],'day':value['day'],'attempts':value['attempts'],'child_exit':code,
            'next_action':'bounded resource retry / automatic next night' if code==75 else
                          'review exact job receipt; no automatic capture retry' if code else 'next Toronto night',
            'remote_notification_delivered':False}
    if code==75:answer['retry_after_seconds']=RETRY_SECONDS
    if failure:answer['reason']=failure
    report(answer);return answer


def settings(config):
    expected={'timezone':'America/Toronto','hour':2,'minute':0,'poll_minutes':15,
              'retry_minutes':30,'max_attempts_per_day':16,'window_end_hour':10}
    value=config['schedule']
    if any(value.get(k)!=v or type(value.get(k)) is not type(v) for k,v in expected.items()):
        raise ValueError('fixed reviewed Toronto calendar/retry settings required')
    return value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--config-sha256',required=True)
    parser.add_argument('--check-calendar',action='store_true')
    args=parser.parse_args()
    if os.getuid()==0:raise ValueError('existing unprivileged user required')
    if checksum(args.config)!=args.config_sha256:raise ValueError('calendar configuration changed')
    config=json.loads(args.config.read_text());schedule=settings(config)
    if checksum(Path(__file__))!=config['source_sha256'].get(Path(__file__).name):raise ValueError('calendar code pin changed')
    if args.check_calendar:
        current=datetime.now(timezone.utc)
        answer,_=decision(current,None,monotonic=time.monotonic(),boot_id='check-only')
        print(json.dumps({'settings':schedule,'decision':answer,'schedule_installed':False,'capture_executed':False}));return 0
    if (schedule.get('enabled') is not True or config.get('adoption_authorized') is not True
            or config.get('retention_adopted') is not True):raise ValueError('actual whole-plan acceptance and schedule adoption remain required')
    if config['job_timeout_seconds']!=7200 or config.get('initial_job_timeout_seconds',7200)!=7200:
        raise ValueError('adopted nightly whole-job timeout must be two hours; cold acceptance is separate')
    folder=storage(config['staging'])/'calendar';folder.mkdir(exist_ok=True)
    if folder.is_symlink():raise ValueError('calendar directory substituted')
    def report(value):
        checkpoint(folder/'status.private.json',dict(value,at=datetime.now(timezone.utc).isoformat(),
                    configuration_sha256=args.config_sha256,reporting='private local JSON and cron stdout only'))
        print(json.dumps(value),flush=True)
    def available():
        try:
            with mcp_lease(folder.parent/'producer.lock'):pass
            return True
        except BlockingIOError:return False
    try:
        with held(folder/'lease') as lease_fd:
            def run():
                argv=[sys.executable,'-B','-S',str(Path(__file__).with_name('vk_nightly_supervisor.py')),
                      '--config',str(args.config),'--config-sha256',args.config_sha256]
                # Fixed owned child, not a command/FD supplied by a manifest.
                return subprocess.Popen(argv,pass_fds=(lease_fd,)).wait()
            result=tick(folder/'state.private.json',args.config_sha256,run,available,report,
                        now=lambda:datetime.now(timezone.utc),monotonic=time.monotonic,
                        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    except BlockingIOError:
        # Do not race an active owner's status/checkpoint. Its running report and
        # the overlap stdout remain available; no producer is launched.
        print(json.dumps({'status':'calendar_overlap_deferred','next_check_seconds':POLL_SECONDS}));return 0
    return 1 if result['status']=='needs_review' else 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as error:
        print(json.dumps({'status':'calendar_blocked','reason':str(error)[:512],
                          'remote_notification_delivered':False}),file=sys.stderr)
        raise SystemExit(1)
