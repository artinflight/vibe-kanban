"""Resumable finite driver around the unchanged, qualified conversion worker.

Uses exactly the existing batch conversion/restore/custody implementation. Starts
paused after a separately verified legacy handoff. Never invokes legacy main(),
replays an uncertain batch, restarts Vibe, or clears a backup epoch.
"""
import argparse
import errno
import hashlib
import importlib.util
import json
import linecache
import os
from pathlib import Path
import sys
import time

from checkpoint_control import Controls, atomic, canonical, locked, process_identity, read, require


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def reference(path):
    return dict(path=str(path),sha256=sha(path))


def verify_pins(rows):
    for row in rows:
        path=Path(row['path']);info=path.lstat()
        require(path.is_absolute() and path.resolve()==path and info.st_uid==os.getuid()
                and info.st_nlink==1 and not info.st_mode&0o022, 'unsafe source pin')
        require(sha(path)==row['sha256'],'source pin changed: '+str(path))


def context_pids():
    """Use our existing systemd cgroup, never a global process/lock mutation."""
    rows=Path('/proc/self/cgroup').read_text().splitlines()
    path=next(row.split(':',2)[2] for row in rows if row.startswith('0::'))
    return [int(pid) for pid in (Path('/sys/fs/cgroup')/path.lstrip('/')/'cgroup.procs').read_text().split()]


def assert_leases_closed(paths,pids=None):
    identities={(Path(p).stat().st_dev,Path(p).stat().st_ino) for p in paths}
    for pid in context_pids() if pids is None else pids:
        folder=Path('/proc',str(pid),'fd')
        try: names=list(folder.iterdir())
        except FileNotFoundError: continue
        for name in names:
            try: info=name.stat()
            except FileNotFoundError: continue
            require((info.st_dev,info.st_ino) not in identities,
                    'backup lease descriptor still open in worker cgroup')


def checkpoint(root,verify_installs=False, trusted_prefix=None):
    """Completed prefix only; interrupted/uncertain next work is never adopted."""
    root=Path(root);selection=read(root/'FINITE_BATCHES.private.json',8*1024**2)
    committed=read(root/'COMMITTED.private.json',8*1024**2)
    require(committed['operation']==selection['operation'],'foreign committed operation')
    rows=committed['batches'];skipped=committed.get('skipped',[])
    numbers=[r['batch'] for r in rows]+[r['batch'] for r in skipped]
    require(sorted(numbers)==list(range(len(numbers))),'non-prefix or duplicate committed batches')
    require(committed['completed_batches']==len(rows),'committed batch count differs')
    require(committed['completed_files']==1+sum(r['files'] for r in rows),'committed file count differs')
    require(committed['resolved_files']==1+sum(len(selection['batches'][r['batch']]['names']) for r in rows)
            +sum(r['files'] for r in skipped),'resolved count differs')
    require(committed['total_files']==selection['files']+1 and committed['total_batches']==len(selection['batches']),
            'finite selection totals differ')
    pins=[reference(root/'COMMITTED.private.json'),reference(root/'FINITE_BATCHES.private.json')]
    canary=root/'canary/RESULT.private.json'
    trusted_count=trusted_prefix['next_batch'] if trusted_prefix else 0
    if trusted_prefix:
        require(not verify_installs and committed['batches'][:len(trusted_prefix['committed_rows'])]==trusted_prefix['committed_rows']
                and committed.get('skipped',[])[:len(trusted_prefix['skipped_rows'])]==trusted_prefix['skipped_rows'],
                'previous committed prefix was rewritten')
        require(pins[1]==trusted_prefix['pins'][1],'finite selection changed')
        pins.extend(trusted_prefix['pins'][2:])
    else:
        canary_result=read(canary)
        require(canary_result['complete'] and canary_result['normal_B_original_and_graph_verified'], 'canary checkpoint incomplete')
        pins.append(reference(canary))
    for row in rows:
        if row['batch']<trusted_count:continue
        folder=root/('batch-'+str(row['batch']).zfill(4))
        require(Path(row['result'])==folder/'RESULT.private.json','foreign result path')
        result=read(folder/'RESULT.private.json');journal=read(folder/'journal/state.json')
        retire=read(folder/'CARRIER_RETIREMENT_RESULT.private.json')
        dynamic=read(folder/'DYNAMIC_RECOVERY.private.json',4*1024**2)
        plan=read(folder/'PLAN.private.json',8*1024**2)
        expected=set(selection['batches'][row['batch']]['names'])
        beneficial={f['path']for f in plan['files']}
        excluded=read(folder/'NONBENEFICIAL.private.json')
        excluded_names={f['path']for f in excluded}
        require(beneficial==set(journal['files']) and beneficial.isdisjoint(excluded_names)
                and beneficial|excluded_names==expected
                and all(f['reason']=='no_positive_allocated_benefit' for f in excluded), 'batch scope differs')
        require(result['complete'] and result['normal_B_original_and_graph_verified']
                and result['files']==row['files'] and result['raw_bytes']==row['raw_bytes']
                and journal['complete'] and journal['outcome']=='installed'
                and retire['complete'] and retire['primary_objects_and_all_B_epochs_preserved']
                and dynamic['actual_independent_normal_restore']['independent_owner_controls_restore_verified'],
                'incomplete recovery/retirement checkpoint')
        for name,entry in journal['files'].items():
            require(entry['state']=='installed','uncertain installation')
            if verify_installs:
                path=Path(plan['source_root'])/name;s=path.stat()
                require([s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]==entry['installed_identity']
                        and sha(path)==entry['manifest_sha256'],'installed manifest changed')
        for rel in ['RESULT.private.json','journal/state.json','CARRIER_RETIREMENT_RESULT.private.json',
                    'DYNAMIC_RECOVERY.private.json','PLAN.private.json','NONBENEFICIAL.private.json']:
            pins.append(reference(folder/rel))
        for path in sorted((folder/'graph-recovery').glob('graph-checkpoint-*.json')):
            pins.append(reference(path))
    for row in skipped:
        if row['batch']<trusted_count:continue
        folder=root/('batch-'+str(row['batch']).zfill(4))
        skipped_result=read(folder/'SKIPPED.private.json')
        excluded=read(folder/'NONBENEFICIAL.private.json')
        require(skipped_result.get('all_nonbeneficial') is True and row['files']==len(selection['batches'][row['batch']]['names'])
                and {r['path']for r in excluded}==set(selection['batches'][row['batch']]['names'])
                and all(r['reason']=='no_positive_allocated_benefit'for r in excluded), 'incomplete skipped disposition')
        pins.extend([reference(folder/'SKIPPED.private.json'),reference(folder/'NONBENEFICIAL.private.json')])
    next_number=len(numbers)
    for folder in root.glob('batch-*'):
        if not folder.is_dir(): continue
        number=int(folder.name.removeprefix('batch-'))
        if number>=next_number:
            require(number==next_number and not (folder/'journal').exists()
                    and not (folder/'RESULT.private.json').exists()
                    and not list((folder/'graph-recovery').glob('graph-checkpoint-*.json')),
                    'unreconciled uncommitted batch; no automatic continuation')
    return dict(operation=committed['operation'],next_batch=next_number,
                completed_files=committed['completed_files'],completed_batches=len(rows),
                total_batches=len(selection['batches']),pins=pins,committed_rows=rows,skipped_rows=skipped,
                checkpoint_sha256=hashlib.sha256(canonical(pins)).hexdigest())


def lease_busy_before_capture(error,nightly_root):
    """Recognize only the two pinned initial flock calls, never later I/O errors."""
    if not isinstance(error,BlockingIOError) or error.errno not in (None,errno.EAGAIN,errno.EACCES):return False
    trace=error.__traceback__
    while trace.tb_next:trace=trace.tb_next
    path=Path(trace.tb_frame.f_code.co_filename);name=trace.tb_frame.f_code.co_name
    line=linecache.getline(str(path),trace.tb_lineno).strip()
    return path.parent==Path(nightly_root) and (
        path.name=='vk_nightly_capture_adapter.py' and name=='mcp_lease'
        and (line.startswith('raise BlockingIOError(') or 'fcntl.flock('in line)
        or path.name=='vk_nightly_desktop_objects.py' and name=='__enter__' and 'fcntl.flock('in line)


def load_legacy(root):
    spec=importlib.util.spec_from_file_location('qualified_finite_legacy',root/'bulk_resume3.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def run(root,control_root,seal_path):
    root=Path(root);require(root.is_absolute() and root.resolve()==root,'canonical operation root required')
    seal=read(seal_path,8*1024**2);verify_pins(seal['sources'])
    handoff=read(seal['handoff']);require(handoff['operation']==seal['operation'] and handoff['verified'],
                                       'verified exact handoff required')
    require(handoff['checkpoint']['checkpoint_sha256']==checkpoint(root,True)['checkpoint_sha256'],
            'checkpoint changed since handoff')
    try: old=process_identity(handoff['old_process']['pid'])
    except FileNotFoundError: old=None
    require(old!=handoff['old_process'],'old controller is still alive')
    controls=Controls(control_root,seal['operation'])
    require(controls.command()['action']=='pause','controlled takeover must start paused')
    owner_lock=root.parents[1]/'production-owner.lock'
    require(owner_lock.exists(),'existing production owner lock required')
    with locked(owner_lock,nonblocking=True):
        # Validate before claiming the one-time attempt. No automatic restart.
        base=load_legacy(root);worker=base.w
        require(base.operation==seal['operation'],'foreign legacy operation')
        fd=os.open(Path(control_root)/'ATTEMPT',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
        state=read(root/'COMMITTED.private.json',8*1024**2)
        base.committed=state['batches'];base.skipped=state.get('skipped',[])
        attempt=seal['attempt'];started=time.time()
        failure=root/'FAILURE.private.json'
        require(sha(failure)==handoff['failure_sha256'],'legacy termination receipt changed')
        retained=Path(control_root)/'LEGACY_BOUNDARY_EXIT.private.json'
        require(not retained.exists(),'legacy receipt already archived')
        os.rename(failure,retained)
        atomic(root/'ARMED.private.json',dict(operation=base.operation,attempt=attempt,at=time.time(),
              admission_expires_at=time.time()+3600,scope='finite online conversion with checkpoint controls'))
        cp=checkpoint(root)
        closed=lambda:assert_leases_closed(seal['backup_leases'])
        try:
            for number in range(cp['next_batch'],len(base.selection['batches'])):
                controls.boundary(cp,attempt=attempt,verify_released=closed,identity_check=worker.readers.check_identities)
                row=base.selection['batches'][number];folder=root/('batch-'+str(number).zfill(4))
                next_batch=None
                if number+1<len(base.selection['batches']):
                    nxt=base.selection['batches'][number+1]
                    next_batch=(root/('batch-'+str(number+1).zfill(4)),nxt['names'],nxt['workspace'])
                while True:
                    controls.publish('running',cp,attempt=attempt,detail={'batch':number})
                    stage='preparation'
                    prior_progress=read(root/'PROGRESS.private.json') if (root/'PROGRESS.private.json').exists() else None
                    try:
                        if not folder.exists():worker.prepare(folder,row['names'],row['workspace'])
                        if (folder/'SKIPPED.private.json').exists():
                            base.skipped.append(dict(batch=number,files=len(row['names']),reason='no_positive_benefit'));break
                        require((folder/'PREPARATION_COMPLETE.private.json').exists(),'incomplete preparation; reconcile before continuation')
                        stage='conversion'
                        worker.convert(folder,next_batch=next_batch)
                        result=read(folder/'RESULT.private.json');base.retire_carriers(folder)
                        base.committed.append(dict(batch=number,files=result['files'],raw_bytes=result['raw_bytes'],
                            allocated_release=result['allocated_release_including_objects_and_directories'],
                            result=str(folder/'RESULT.private.json')))
                        break
                    except BlockingIOError as error:
                        if stage!='conversion' or not lease_busy_before_capture(error,worker.C['nightly']['folder']):raise
                        closed()
                        # No journal, capture or graph checkpoint may have appeared.
                        require(checkpoint(root,trusted_prefix=cp)['checkpoint_sha256']==cp['checkpoint_sha256'],
                                'busy admission changed checkpoint')
                        controls.publish('waiting_for_backup',cp,attempt=attempt,detail='Normal backup lane is occupied')
                        atomic(Path(control_root)/'ADMISSION_WAIT.private.json',dict(at=time.time(),operation=base.operation,
                               batch=number,reason='initial_backup_lease_busy',no_capture_or_conversion_dispatched=True))
                        if prior_progress is not None:
                            # The initial admission marker is not verified byte progress.
                            atomic(root/'PROGRESS.private.json',prior_progress)
                        time.sleep(5)
                        controls.boundary(cp,attempt=attempt,verify_released=closed,
                                          identity_check=worker.readers.check_identities)
                worker.save(root/'COMMITTED.private.json',base.metadata())
                worker.progress('finite_batch_committed',dict(batch=number+1,total_batches=len(base.selection['batches']),
                                                              files=base.metadata()['completed_files']))
                cp=checkpoint(root,trusted_prefix=cp);closed()
            worker.save(root/'PHYSICAL_WINDOW_AFTER.private.json',dict(at=time.time(),
                source=worker.physical_accounting.measure([worker.C['source_root']],guard=worker.readers.check),
                task=worker.physical_accounting.measure([str(root)],guard=worker.readers.check),
                filesystems={p:dict(available=os.statvfs(p).f_bavail*os.statvfs(p).f_frsize)
                             for p in [worker.C['source_root'],'/mnt/vk-storage']}))
            require(base.metadata()['resolved_files']==base.metadata()['total_files'],'finite selection unfinished')
            worker.save(root/'RESULT.private.json',dict(base.metadata(),complete=True,cutover_only=False,
                finite_conversion_complete=True,full_objective_verified=False,seconds=time.time()-started,
                normal_B_original_and_selected_graph_verified=True,
                final_archive_closure_SQL_UI_growth_handoff_pending=True))
            worker.progress('finite_conversion_complete_final_acceptance_pending')
            controls.publish('complete',cp,attempt=attempt)
        except BaseException as error:
            worker.save(root/'FAILURE.private.json',dict(operation=base.operation,attempt=attempt,at=time.time(),
                type=type(error).__name__,error=str(error),completed_batches=len(base.committed),
                no_service_actions=True,inspect_exact_batch_journal_before_recovery=True))
            controls.publish('failed',cp,attempt=attempt,detail=type(error).__name__+': '+str(error))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operation-root',required=True);parser.add_argument('--controls',required=True)
    parser.add_argument('--seal',required=True);args=parser.parse_args()
    run(args.operation_root,args.controls,args.seal)
