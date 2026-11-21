"""Finalize a completed tail, leaving the old staging directory and consumers untouched.

Unlike the original recovery, this never moves, removes, reuses or writes inside
the old next-batch directory. The unchanged worker prepares a fresh independent
path, explicitly pinned to one batch. Existing-data consumer checks remain intact.
"""
import os
from pathlib import Path
import time
from checkpoint_control import atomic,locked,require
from controlled_conversion import checkpoint,load_legacy,sha,verify_pins,batch_folder
from boundary_handoff import alive
from terminal_checkpoint_recovery import inspect


def reconcile(root,controls,preparation):
    root=Path(root);controls=Path(controls)
    require(not alive(preparation['old_process']),'old controller is alive')
    verify_pins(preparation['sources'])
    require((root.parents[1]/'production-owner.lock').exists(),'existing production ownership lock required')
    with locked(root.parents[1]/'production-owner.lock',nonblocking=True):
        value=inspect(root,preparation['terminal_failure_sha256'])
        original=Path(value['next_folder'])
        parent=controls/'isolated-preparations'
        require(controls.parent==root and not parent.exists(),'fresh isolated preparation parent required')
        override=dict(batch=value['batch']+1,path=str(parent/original.name))
        replacement=batch_folder(root,override['batch'],override)
        require(replacement!=original and not replacement.exists(),'replacement must be fresh and separate')
        fd=os.open(controls/'TERMINAL_RECOVERY_ATTEMPT',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
        atomic(controls/'TERMINAL_RECOVERY_PLAN.private.json',dict(value,at=time.time(),
            original_directory_left_untouched=True,batch_override=override))
        parent.mkdir(mode=0o700)
        base=load_legacy(root)
        # This existing routine uses B proofs, exact hashes/inodes and exclusive
        # kernel file leases before retiring its own backed-up duplicate carriers.
        base.retire_carriers(Path(value['folder']))
        require([original.stat().st_dev,original.stat().st_ino]==value['next_directory_identity'],
                'original directory identity changed during read-only reconciliation')
        require(sha(root/'COMMITTED.private.json')==value['committed_sha256'],'committed record changed under custody')
        base.committed=value['committed']['batches'];base.skipped=value['committed'].get('skipped',[])
        result=value['result'];base.committed.append(dict(batch=value['batch'],files=result['files'],raw_bytes=result['raw_bytes'],
            allocated_release=result['allocated_release_including_objects_and_directories'],result=str(Path(value['folder'])/'RESULT.private.json')))
        base.w.save(root/'COMMITTED.private.json',base.metadata())
        base.w.progress('recovered_completed_batch_committed',dict(batch=value['batch']+1,files=base.metadata()['completed_files']))
        cp=checkpoint(root,True,batch_override=override)
        proof=dict(verified=True,operation=value['operation'],old_process=preparation['old_process'],checkpoint=cp,
            failure_sha256=value['failure_sha256'],at=time.time(),all_prior_receipts_preserved=True,
            no_signal_or_forced_unlock=True,reason='terminal_prefetch_failure_fresh_isolated_staging',
            recovered_completed_batch=value['batch'],original_directory_left_untouched=str(original),
            original_directory_identity=value['next_directory_identity'],batch_override=override)
        atomic(controls/'HANDOFF.private.json',proof)
        return proof
