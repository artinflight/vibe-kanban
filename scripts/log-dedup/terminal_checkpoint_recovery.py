"""Reconcile the exact post-batch/pre-prefetch failure, without repeating conversion.

This narrow route is separate from the cooperative legacy drain. It refuses any
next-batch data/control files, incomplete current conversion, different failure,
changed installed manifest or live old process. Existing B proofs are retained;
only the qualified legacy routine may retire its already-backed-up carriers.
"""
import os
from pathlib import Path
import time

from checkpoint_control import atomic, locked, read, require
from controlled_conversion import checkpoint, load_legacy, reference, sha, verify_pins
from boundary_handoff import alive

ERROR="Command '['systemctl', '--user', 'show', 'vibe-kanban-native-review-20261015.service', '-p', 'MainPID', '-p', 'InvocationID', '-p', 'ActiveState', '-p', 'FreezerState', '-p', 'ControlGroup']' returned non-zero exit status 1."


def inspect(root,expected_failure_sha):
    root=Path(root)
    require(sha(root/'FAILURE.private.json')==expected_failure_sha,'terminal failure changed')
    failure=read(root/'FAILURE.private.json')
    require(failure['attempt']=='resume3' and failure['type']=='CalledProcessError' and failure['error']==ERROR,
            'different terminal failure; independent recovery required')
    try:checkpoint(root,True)
    except ValueError as error:
        require(str(error)=='unreconciled uncommitted batch; no automatic continuation',
                'completed prefix qualification failed: '+str(error))
    else:raise ValueError('no pending completed batch to reconcile')
    committed=read(root/'COMMITTED.private.json',8*1024**2)
    number=len(committed['batches'])+len(committed.get('skipped',[]))
    require(failure['operation']==committed['operation'] and failure['completed_batches']==len(committed['batches']),
            'terminal failure/prefix differs')
    folder=root/('batch-'+str(number).zfill(4));next_folder=root/('batch-'+str(number+1).zfill(4))
    require(next_folder.is_dir() and not list(next_folder.iterdir()),'next batch is not an empty unpublished preparation')
    require(not (folder/'CARRIER_RETIREMENT_RESULT.private.json').exists(),'carrier retirement already occurred; reconcile')
    plan=read(folder/'PLAN.private.json',8*1024**2);journal=read(folder/'journal/state.json')
    result=read(folder/'RESULT.private.json');conversion=read(folder/'CONVERSION.private.json')
    dynamic=read(folder/'DYNAMIC_RECOVERY.private.json',4*1024**2)
    selected=read(root/'FINITE_BATCHES.private.json',8*1024**2)['batches'][number]['names']
    excluded=read(folder/'NONBENEFICIAL.private.json')
    require({r['path']for r in plan['files']}==set(journal['files'])
            and set(journal['files'])|{r['path']for r in excluded}==set(selected)
            and all(r['reason']=='no_positive_allocated_benefit'for r in excluded),'pending batch scope differs')
    require(result['complete'] and result['normal_B_original_and_graph_verified']
            and result['files']==len(plan['files']) and result['raw_bytes']==sum(r['raw_bytes']for r in plan['files'])
            and result['staging_retirement']['all_primary_objects_preserved']
            and conversion['complete'] and conversion['outcome']=='installed'
            and journal['complete'] and journal['outcome']=='installed'
            and dynamic['actual_independent_normal_restore']['independent_owner_controls_restore_verified'],
            'pending batch recovery or conversion incomplete')
    for name,entry in journal['files'].items():
        path=Path(plan['source_root'])/name;info=path.stat()
        require(entry['state']=='installed' and sha(path)==entry['manifest_sha256']
                and [info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns]==entry['installed_identity'],
                'installed manifest differs')
    for row in plan['files']:
        for side in row.get('sidecars',[]):
            path=(Path(plan['source_root'])/row['path']).with_suffix('.'+side['extension'])
            require(sha(path)==side['sha256'],'required sidecar differs')
    return dict(operation=committed['operation'],batch=number,folder=str(folder),next_folder=str(next_folder),
                result=result,committed=committed,committed_sha256=sha(root/'COMMITTED.private.json'),
                failure_sha256=expected_failure_sha,validated_installs=len(journal['files']),
                next_directory_identity=[next_folder.stat().st_dev,next_folder.stat().st_ino])


def no_consumers(path):
    """Only inspect consumers of the one empty task-created staging directory."""
    path=str(path)
    for process in Path('/proc').iterdir():
        if not process.name.isdigit():continue
        try:
            if process.stat().st_uid!=os.getuid():continue
            links=[process/'cwd']+list((process/'fd').iterdir())
        except FileNotFoundError:continue
        for link in links:
            try:target=os.readlink(link)
            except FileNotFoundError:continue
            require(target!=path and not target.startswith(path+'/'),'unpublished directory has an active consumer')


def reconcile(root,controls,preparation):
    root=Path(root);controls=Path(controls)
    require(not alive(preparation['old_process']),'old controller is alive')
    verify_pins(preparation['sources'])
    require((root.parents[1]/'production-owner.lock').exists(),'existing production ownership lock required')
    with locked(root.parents[1]/'production-owner.lock',nonblocking=True):
        value=inspect(root,preparation['terminal_failure_sha256'])
        next_folder=Path(value['next_folder']);no_consumers(next_folder)
        target=controls/'preserved-empty-next-batch'
        require(not target.exists(),'prior recovery move exists; reconcile')
        fd=os.open(controls/'TERMINAL_RECOVERY_ATTEMPT',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
        atomic(controls/'TERMINAL_RECOVERY_PLAN.private.json',dict(value,at=time.time(),retained_empty_directory=str(target)))
        base=load_legacy(root)
        # The exact previously qualified routine checks B recovery receipts,
        # hashes/inodes and an exclusive kernel file lease for each carrier.
        base.retire_carriers(Path(value['folder']))
        require([next_folder.stat().st_dev,next_folder.stat().st_ino]==value['next_directory_identity']
                and not list(next_folder.iterdir()),'unpublished directory changed')
        os.rename(next_folder,target)
        require([target.stat().st_dev,target.stat().st_ino]==value['next_directory_identity'] and not list(target.iterdir()),
                'preserved directory identity differs')
        note=root/(next_folder.name+'.PRESERVED-LOCATION.json')
        atomic(note,dict(original=str(next_folder),preserved=str(target),reason='empty preparation at terminal pre-backup failure'))
        require(sha(root/'COMMITTED.private.json')==value['committed_sha256'],'committed record changed under custody')
        base.committed=value['committed']['batches'];base.skipped=value['committed'].get('skipped',[])
        result=value['result'];base.committed.append(dict(batch=value['batch'],files=result['files'],raw_bytes=result['raw_bytes'],
            allocated_release=result['allocated_release_including_objects_and_directories'],result=str(Path(value['folder'])/'RESULT.private.json')))
        base.w.save(root/'COMMITTED.private.json',base.metadata())
        base.w.progress('recovered_completed_batch_committed',dict(batch=value['batch']+1,files=base.metadata()['completed_files']))
        cp=checkpoint(root,True)
        handoff=dict(verified=True,operation=value['operation'],old_process=preparation['old_process'],checkpoint=cp,
            failure_sha256=value['failure_sha256'],at=time.time(),all_prior_receipts_preserved=True,
            no_signal_or_forced_unlock=True,reason='independently_reconciled_terminal_prefetch_failure',
            recovered_completed_batch=value['batch'],preserved_empty_preparation=str(target))
        atomic(controls/'HANDOFF.private.json',handoff)
        return handoff
