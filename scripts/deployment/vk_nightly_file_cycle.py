"""One finite normal file cycle over the retained B map and source journal.

This is the file dependency of commissioning, not whole SQL/runtime/restore
acceptance or a calendar. There is no bootstrap census or background collector.
The optional exact metadata predecessor is awaited only during commissioning.
All source delivery, qualification, body and readback operations are serial.
"""
import argparse
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from vk_change_journal import scope
from vk_nightly_desktop_controls import DesktopControls
from vk_nightly_incremental import advance_suffix
from vk_nightly_inode_journal import require_full_coverage
from vk_nightly_outbox_collector import copy_once
from vk_nightly_outbox_export import retained_prefix_report
from vk_nightly_tracking import TrackingStore
from vk_nightly_typed_worker import configuration,host_guard,run_B,source_closure
from vk_nightly_b_tracker import health_mirror,write_health
from vk_prep_common import identity


def read_owned(path,expected=None,*,pinned_group_data=False):
    path=Path(path)
    if not path.is_absolute() or path.resolve()!=path:raise ValueError('canonical owned control required')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    with os.fdopen(fd,'rb') as source:
        info=os.fstat(source.fileno())
        # Existing shared source plans are data, not executable configuration.
        # Their explicit full digest permits group-write mode without changing
        # filesystem permissions. Dynamic controls remain private and all data
        # still reject another owner, symlinks, world writes or a digest change.
        if pinned_group_data and (not isinstance(expected,str) or not re.fullmatch('[0-9a-f]{64}',expected)):
            raise ValueError('full source-plan digest required for shared data')
        mask=0o002 if pinned_group_data else 0o022
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&mask:
            raise ValueError('owned control file required')
        raw=source.read(1024**2+1)
    if len(raw)>1024**2 or expected is not None and hashlib.sha256(raw).hexdigest()!=expected:
        raise ValueError('bounded exact control binding differs')
    return json.loads(raw)


def optional_report(path,value):
    """No local payload fallback; authoritative active-cycle receipts live on B."""
    try:health_mirror(path,value)
    except OSError as error:
        if error.errno not in (errno.ENOSPC,errno.EDQUOT,errno.EROFS,errno.EEXIST):raise
        print(json.dumps(dict(optional_SSD_health_mirror_error=str(error),
            phase=value.get('phase'),all_completed_B_points_preserved=True)),file=sys.stderr,flush=True)


class Source:
    def __init__(self,reference,controls,*,guard):
        self.reference=reference;self.controls=controls;self.guard=guard
        self.config=read_owned(reference['config'],reference['sha256'])
        self.plan=read_owned(self.config['plan'],self.config['plan_sha256'],pinned_group_data=True)
        if self.config['B_delivery_target']['B_root']!=controls['B_root']:
            raise ValueError('source/consumer B recovery root differs')

    def check(self):
        self.guard();health=read_owned(self.config['status'])
        if (health.get('ready') is not True or health.get('raw_errors')
                or health.get('coverage_model')!='all-selected-inodes-v1'
                or health.get('instance')!=self.reference['instance']
                or health.get('plan_sha256')!=identity(self.plan)
                or health.get('scope_sha256')!=identity(scope(self.plan))
                or set(health.get('required_root_bindings',{}))!=set(self.plan['sources'])
                or not 0<=time.time()-health['heartbeat_utc']<=90):
            raise ValueError('current exact healthy source owner required')
        birth=int(Path('/proc/'+str(health['owner_pid'])+'/stat').read_text().rsplit(')',1)[1].split()[19])
        if birth!=health['owner_start_ticks']:raise ValueError('source process identity changed')
        return health

    def deliver(self):
        self.check()
        return copy_once(dict(source_health=self.config['status'],endpoint=self.config['endpoint'],
            B_delivery_target=self.config['B_delivery_target'],controls=self.controls,
            maximum_B_index_bytes=self.controls['maximum_index_bytes']),guard=self.guard)

    def report(self,client):
        health=self.check();target=self.config['B_delivery_target']
        db=client.connect(target['index_name'],target['checkpoint_sha256'],readonly=True,working=True)
        try:
            db.execute('begin')
            class ReadStore(TrackingStore):
                def check(self):db.request('check')
            store=ReadStore();store.db=db
            row=db.execute('select cursor from epochs where instance=?',(health['instance'],)).fetchone()
            if row is None:raise ValueError('actual delivered current B prefix required')
            value=retained_prefix_report(store,self.config['endpoint'],health['instance'],row[0],guard=self.guard)
            require_full_coverage(value)
            if any(value[k]!=health[k] for k in ('instance','plan_sha256','scope_sha256')):
                raise ValueError('source barrier/owner binding differs')
            db.execute('commit');self.check();return value
        finally:db.close()


def predecessor(reference,source,*,maximum_seconds,report,clock=time.monotonic,sleep=time.sleep):
    """Await only the named existing controller; never launch or restart it."""
    if not re.fullmatch(r'vk-nightly-[A-Za-z0-9-]+\.service',reference['unit']):
        raise ValueError('exact existing Nightly predecessor unit required')
    if type(maximum_seconds) is not int or maximum_seconds<1:raise ValueError('finite predecessor wait required')
    proof_field=reference.get('verification_field','actual_independent_normal_B_composition_reopen_verified')
    if proof_field not in ('actual_independent_normal_B_composition_reopen_verified',
                           'actual_independent_B_file_cycle_receipt_reopen_verified'):
        raise ValueError('fixed independent predecessor acceptance field required')
    started=clock()
    while True:
        source.check()
        text=subprocess.check_output(['systemctl','--user','show',reference['unit'],
            '-p','MainPID','-p','ExecMainStatus','-p','ActiveState'],text=True,timeout=15)
        state=dict(line.split('=',1) for line in text.splitlines())
        if state.get('MainPID')=='0':
            if state.get('ActiveState')!='inactive' or state.get('ExecMainStatus')!='0':
                raise ValueError('metadata predecessor did not complete successfully; preserve its cursor')
            value=read_owned(reference['result'])
            instance=value.get('source_instance',value.get('final_B_delivery',{}).get('instance'))
            if (value.get(proof_field) is not True
                    or instance!=source.reference['instance']
                    or any(value.get(k)!=v for k,v in reference['result_binding'].items())):
                raise ValueError('actual independent metadata predecessor result differs')
            return value
        if state.get('ActiveState')!='active':raise ValueError('unexpected predecessor state; no duplicate launch')
        if clock()-started>=maximum_seconds:raise TimeoutError('finite predecessor wait expired; preserve all work')
        report(dict(phase='awaiting-existing-metadata-predecessor',unit=reference['unit'],
                    elapsed_seconds=clock()-started,source_payload_bytes_read=0,backup_payload_bytes_copied=0))
        sleep(max(0,min(30,maximum_seconds-(clock()-started))))


def run(config,worker,*,report):
    started=time.monotonic();guard=lambda:host_guard(worker,started)
    source=Source(config['source_observer'],worker['B_controls'],guard=guard)
    source.check()
    if config.get('metadata_predecessor'):
        predecessor(config['metadata_predecessor'],source,maximum_seconds=config['maximum_predecessor_seconds'],report=report)
    # Waiting does not consume the admitted finite body-phase wall time.
    started=time.monotonic();source.deliver();last_delivery=time.monotonic()
    with DesktopControls(worker['B_controls'],guard=guard) as remote:
        target=source.config['B_delivery_target']
        delta=advance_suffix(remote.client,index_name=worker['B_index_name'],checkpoint_sha256=worker['B_checkpoint_sha256'],
            journal_name=target['index_name'],journal_checkpoint_sha256=target['checkpoint_sha256'],plan=source.plan,
            maximum_paths=config['maximum_delta_paths'],maximum_journal_bytes=worker['B_controls']['maximum_index_bytes'],
            guard=guard,on_progress=report)
        def boundary():
            nonlocal last_delivery
            source.check()
            if time.monotonic()-last_delivery>=120:
                source.deliver();last_delivery=time.monotonic()
        result=run_B(worker,at_component_boundary=boundary,source_report=lambda:source.report(remote.client))
    delivered=source.deliver()
    value=dict(result,phase='finite-current-file-cycle-complete',metadata_delta=delta,final_B_delivery=delivered,
        baseline_accepted=False,schedule_enabled=False,remaining_SQL_runtime_composed_restore_required=True)
    # Verify the phase receipt through a new normal native B reader. This is
    # an independent receipt reopen; each new file already has full readback.
    with DesktopControls(worker['B_controls'],guard=guard) as remote:
        db=remote.client.connect(worker['B_index_name'],worker['B_checkpoint_sha256'])
        try:write_health(db,Path(worker['status']),value)
        finally:db.close()
    with DesktopControls(worker['B_controls'],guard=guard) as remote:
        db=remote.client.connect(worker['B_index_name'],worker['B_checkpoint_sha256'],readonly=True,working=True)
        try:
            actual=json.loads(db.execute('select row from tracking_health where id=1').fetchone()[0])
            if any(actual.get(k)!=v for k,v in value.items()):raise ValueError('normal independent B file-cycle receipt differs')
        finally:db.close()
    source.check();return dict(value,actual_independent_B_file_cycle_receipt_reopen_verified=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True);parser.add_argument('--sha256',required=True)
    parser.add_argument('--preflight',action='store_true');args=parser.parse_args()
    config=read_owned(args.config,args.sha256);folder=Path(__file__).parent
    required=source_closure(folder,'vk_nightly_file_cycle')
    if not required<=config['source_sha256'].keys():raise ValueError('complete file-cycle source binding required')
    for name,sha in config['source_sha256'].items():
        if not re.fullmatch(r'vk_[a-z0-9_]+\.py',name) or hashlib.sha256((folder/name).read_bytes()).hexdigest()!=sha:
            raise ValueError('file-cycle source changed')
    worker=configuration(config['worker_config'],config['worker_config_sha256'])
    output=Path(worker['status']).parent
    def report(value,name='CYCLE_STATUS.private.json'):
        optional_report(output/name,dict(value,at_EDT=datetime.now(ZoneInfo('America/Toronto')).isoformat()))
    if args.preflight:
        Source(config['source_observer'],worker['B_controls'],guard=lambda:host_guard(worker,time.monotonic())).check()
        print(json.dumps(dict(source_and_config_verified=True,no_new_capture_started=True)));return 0
    try:
        value=run(config,worker,report=report);report(value,'RESULT.private.json');report(value)
        print(json.dumps(value),flush=True);return 0
    except BaseException as error:
        report(dict(phase='current-file-cycle-stopped',type=type(error).__name__,reason=str(error),
            all_completed_B_points_and_partials_preserved=True,no_automatic_retry=True,
            baseline_accepted=False,schedule_enabled=False,error_notes=[str(n)[:8192] for n in getattr(error,'__notes__',[])[:4]]),'STOP.private.json')
        raise


if __name__=='__main__':raise SystemExit(main())
