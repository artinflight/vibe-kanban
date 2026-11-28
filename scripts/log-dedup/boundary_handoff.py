"""One-time legacy handoff through its normal nonblocking admission lock.

Default CLI only inspects. The explicit drain action waits for natural context
closure; it never sends a signal, edits active source, or forces an unlock. An
unexpected exit or partial batch leaves the job stopped for recovery, not resumed.
"""
import argparse
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import stat
import time

from checkpoint_control import atomic, process_identity, read, require
from controlled_conversion import checkpoint, sha, verify_pins


def alive(identity):
    try:return process_identity(identity['pid'])==identity
    except FileNotFoundError:return False


@contextmanager
def acquire_naturally(path,old_process,*,deadline,observe=lambda _:None,sleep=time.sleep):
    path=Path(path);before=path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid()
            and before.st_nlink==1 and not before.st_mode&0o022,'owned existing admission lock required')
    fd=os.open(path,os.O_RDWR|os.O_NOFOLLOW)
    try:
        require((os.fstat(fd).st_dev,os.fstat(fd).st_ino)==(before.st_dev,before.st_ino),'lock changed')
        while True:
            require(time.time()<deadline,'handoff deadline reached; existing job preserved')
            require(alive(old_process),'legacy owner ended before a verified handoff')
            require((path.lstat().st_dev,path.lstat().st_ino)==(before.st_dev,before.st_ino),'lock replaced')
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:observe('waiting_for_natural_release');sleep(1)
        observe('normal_admission_lock_acquired')
        yield fd
    finally:os.close(fd)


def verify_exit(root,request):
    root=Path(root)
    require(not alive(request['old_process']),'old process still running')
    require(not (root/'RESULT.private.json').exists(),'legacy completed naturally; no takeover needed')
    failure=read(root/'FAILURE.private.json')
    require(failure['operation']==request['operation'] and failure['attempt']==request['old_attempt']
            and failure['at']>=request['requested_at'] and failure['type']=='BlockingIOError'
            and failure['error']=='MCP producer lease still held by parent or inherited owned child; defer B reconciliation',
            'termination is not the expected pre-capture admission hold')
    cp=checkpoint(root,verify_installs=True)
    require(failure['completed_batches']==cp['completed_batches'],'failure/committed prefix differs')
    return dict(verified=True,operation=request['operation'],old_process=request['old_process'],
                checkpoint=cp,failure_sha256=sha(root/'FAILURE.private.json'),
                at=time.time(),all_prior_receipts_preserved=True,no_signal_or_forced_unlock=True)


def drain(root,controls,request):
    root=Path(root);controls=Path(controls)
    verify_pins(request['sources'])
    require(request['authorization_ref'],'explicit operator authorization reference required')
    require(request['deadline']>time.time()>=request['requested_at'],'fresh bounded handoff request required')
    require(not (controls/'HANDOFF.private.json').exists(),'existing handoff must be reconciled')
    fd=os.open(controls/'DRAIN_ATTEMPT',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
    def report(phase):atomic(controls/'handoff-status.json',dict(operation=request['operation'],phase=phase,at=time.time()))
    try:
        with acquire_naturally(request['controller_lease'],request['old_process'],deadline=request['deadline'],observe=report):
            # No next B context can open. The current batch's final local carrier
            # retirement and COMMITTED write still run normally before exit.
            report('waiting_for_legacy_admission_exit')
            while alive(request['old_process']):
                require(time.time()<request['deadline'],'handoff deadline reached; reconcile exact legacy state')
                time.sleep(1)
            result=verify_exit(root,request)
            atomic(controls/'HANDOFF.private.json',result)
        report('verified_checkpoint_backup_access_released')
        return result
    except BaseException as error:
        atomic(controls/'HANDOFF_FAILURE.private.json',dict(at=time.time(),type=type(error).__name__,error=str(error),
               no_automatic_resume=True,inspect_live_owner_before_any_retry=True))
        raise


if __name__=='__main__':
    import json
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operation-root',required=True);parser.add_argument('--controls',required=True)
    parser.add_argument('--request');parser.add_argument('--drain',action='store_true');args=parser.parse_args()
    if args.drain:
        require(args.request is not None,'explicit retained authorized request required')
        result=drain(args.operation_root,args.controls,read(args.request))
    else:result=dict(assessment_only=True,checkpoint=checkpoint(args.operation_root))
    print(json.dumps(result,sort_keys=True))
