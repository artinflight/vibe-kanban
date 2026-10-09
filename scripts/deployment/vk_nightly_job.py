#!/usr/bin/env python3
"""Runnable user-level nightly composition; disabled production configuration.

Inventory is read-only. Enrollment/adoption and timer installation are separate
specific actions. CLI never enables a schedule, installs code or acquires root.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time

from vk_change_journal import scope
from vk_nightly_capture_adapter import run_capture, validate_socket_exclusions
from vk_prep_common import identity, storage
from vk_rolling_backup import Exclusions, scan


def checksum(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def inventory(plan):
    started=time.monotonic();exclusions=Exclusions(plan)
    missing=[raw for raw in plan['sources'] if not os.path.lexists(raw)]
    if missing:raise ValueError('missing source roots require reconciled scope review')
    paths=scan(plan['sources'],plan,exclusions)
    required=set(plan.get('sqlite_snapshots',[]))|set(plan.get('critical_sqlite',[]))
    files=0;logical=0;allocated=0;databases={};links=0;vanished=0
    for raw in sorted(paths):
        path=Path(raw)
        try:info=path.lstat()
        except FileNotFoundError:
            if raw in required or raw in plan['sources']:raise ValueError('required inventory member disappeared')
            vanished+=1;continue
        if stat.S_ISREG(info.st_mode):
            files+=1;logical+=info.st_size;allocated+=info.st_blocks*512
            try:
                with path.open('rb') as stream:header=stream.read(16)
            except FileNotFoundError:
                vanished+=1;continue
            if header==b'SQLite format 3\0':databases[str(path.resolve())]=info.st_size
        elif stat.S_ISLNK(info.st_mode):links+=1
    if required-databases.keys():raise ValueError('declared SQLite missing, aliased or invalid during inventory')
    exclusions.validate()
    return {'plan_identity':identity(plan),'source_scope_sha256':identity(scope(plan)),
            'roots':{raw:{'device':Path(raw).lstat().st_dev,'inode':Path(raw).lstat().st_ino,
                            'mode_type':stat.S_IFMT(Path(raw).lstat().st_mode),
                            'resolved_target':str(Path(raw).resolve())} for raw in plan['sources']},
            'exclusion_targets':[str(p) for p in exclusions.roots],
            'files':files,'paths':len(paths),'symlinks':links,'logical_file_bytes':logical,
            'allocated_file_bytes':allocated,'databases':databases,'maximum_DB_bytes':max(databases.values(),default=0),
            'elapsed_seconds':time.monotonic()-started,'read_only':True,'content_hashed':False,
            'consistency':'online metadata census, not an application-coherent backup','vanished_during_scan':vanished}


def validate(config,plan):
    if checksum(config['plan_path'])!=config['plan_file_sha256'] or identity(plan)!=config['plan_identity']:
        raise ValueError('current plan differs from reviewed binding')
    validate_socket_exclusions(config.get('socket_exclusions',[]))
    if identity(scope(plan))!=config['source_scope_sha256']:raise ValueError('source scope changed')
    if set(config['source_roots'])!=set(plan['sources']):raise ValueError('source root inventory incomplete')
    required={'vk_nightly_job.py','vk_nightly_capture_adapter.py','vk_nightly_b_job.py','vk_nightly_generation.py','vk_nightly_lifecycle.py','vk_b_disk_capture.py'}
    if not required<=config['source_sha256'].keys():raise ValueError('fixed handler pins incomplete')
    for raw,expected in config['source_sha256'].items():
        if checksum(Path(__file__).with_name(raw))!=expected:raise ValueError('fixed nightly source changed: '+raw)
    for raw,expected in config['binary_sha256'].items():
        if checksum(raw)!=expected:raise ValueError('nightly binary changed: '+raw)
    for raw,row in config['source_roots'].items():
        info=Path(raw).lstat()
        if stat.S_IFMT(info.st_mode)!=row['mode_type']:raise ValueError('source root type changed')
        if str(Path(raw).resolve())!=row['resolved_target']:raise ValueError('source root symlink target changed')
        if stat.S_ISDIR(info.st_mode) and [info.st_dev,info.st_ino]!=[row['device'],row['inode']]:
            raise ValueError('source directory substituted; review scope binding')
    if [str(p) for p in Exclusions(plan).roots]!=config['exclusion_targets']:raise ValueError('exclusion target changed')
    for key in ('capture_limit_bytes','changed_limit_bytes','initial_changed_limit_bytes','snapshot_limit_bytes','reserve_bytes','initial_reserve_bytes',
                'snapshot_timeout_seconds','readback_timeout_seconds','job_timeout_seconds'):
        if type(config[key]) is not int or config[key]<=0:raise ValueError('finite positive measured limits required')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path)
    parser.add_argument('--config-sha256')
    parser.add_argument('--check-config',action='store_true')
    parser.add_argument('--inventory-plan',type=Path)
    parser.add_argument('--inventory-output',type=Path)
    parser.add_argument('--enroll-fresh',action='store_true')
    parser.add_argument('--recover-only',action='store_true')
    args=parser.parse_args()
    if args.inventory_plan:
        value=inventory(json.loads(args.inventory_plan.read_text()))
        if args.inventory_output:
            with storage(args.inventory_output).open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')
        print(json.dumps({key:value[key] for key in ('files','paths','logical_file_bytes','allocated_file_bytes','maximum_DB_bytes','elapsed_seconds','read_only')}))
        return 0
    if not args.config:parser.error('--config or --inventory-plan required')
    if args.config_sha256 and checksum(args.config)!=args.config_sha256:raise ValueError('nightly configuration hash changed')
    config=json.loads(args.config.read_text());plan=json.loads(Path(config['plan_path']).read_text());validate(config,plan)
    if args.check_config:
        print(json.dumps({'passed':True,'configuration_valid':True,'adoption_authorized':config.get('adoption_authorized') is True,'schedule_enabled':False}))
        return 0
    if config.get('adoption_authorized') is not True or config.get('retention_adopted') is not True:
        raise ValueError('nightly enrollment/retention adoption remains disabled pending final review')
    result=run_capture(config,plan,enroll_fresh=args.enroll_fresh,recover_only=args.recover_only)
    print(json.dumps(result))
    return 0 if result['result']['passed'] else 1


if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,OSError,subprocess.SubprocessError) as error:
        print(json.dumps({'passed':False,'status':'nightly_blocked','reason':str(error),
                          'next':'preserve B current/evidence; review exact scope, route, capacity or producer failure'}),file=sys.stderr)
        raise SystemExit(1)
