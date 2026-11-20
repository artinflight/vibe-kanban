"""Explicit one-time activation of prepared checkpoint controls; never stops Vibe.

Without --activate this only verifies preparation pins. A live activation needs a
retained operator authorization reference. Normal admission performs the legacy
handoff; the replacement starts PAUSED and retains the original finite selection.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
import uuid

from checkpoint_control import atomic, locked, process_identity, read, require
from controlled_conversion import assert_leases_closed, reference, verify_pins
from boundary_handoff import drain


def unit(name):
    text=subprocess.check_output(['systemctl','--user','show',name,'-p','MainPID','-p','InvocationID',
                                 '-p','ActiveState','-p','ControlGroup'],text=True,timeout=10)
    return dict(line.split('=',1) for line in text.splitlines())


def install_bytes(path,data,mode=0o600):
    path=Path(path);tmp=path.with_name('.control-install-'+uuid.uuid4().hex)
    try:
        fd=os.open(tmp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,mode)
        with os.fdopen(fd,'wb') as stream:
            stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.replace(tmp,path)
        fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
    finally:
        if tmp.exists():tmp.unlink()


def activate(preparation_path,authorization_ref):
    preparation=read(preparation_path,8*1024**2);verify_pins(preparation['sources'])
    root=Path(preparation['operation_root']);controls=Path(preparation['controls'])
    require(root.resolve()==root and controls.resolve()==controls and os.path.ismount('/mnt/vk-storage'),
            'exact mounted operation/control paths required')
    require(authorization_ref and len(authorization_ref)<=2048,'actual operator authorization reference required')
    require(unit(preparation['unit'])==preparation['old_unit'],'legacy unit identity changed; reconcile')
    terminal=preparation.get('mode')=='reconciled_terminal_prefetch_failure'
    if terminal:
        from boundary_handoff import alive
        require(not alive(preparation['old_process']),'terminal owner is still alive')
    else:
        require(process_identity(preparation['old_process']['pid'])==preparation['old_process'],'legacy process changed')
    require(not (controls/'ACTIVATION_ATTEMPT').exists(),'activation already attempted; reconcile, never replay')
    fd=os.open(controls/'ACTIVATION_ATTEMPT',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
    request=dict(operation=preparation['operation'],old_attempt=preparation['old_attempt'],
        old_process=preparation['old_process'],controller_lease=preparation['backup_leases'][0],
        requested_at=time.time(),deadline=time.time()+preparation['handoff_maximum_seconds'],
        authorization_ref=authorization_ref,sources=preparation['sources'])
    atomic(controls/'DRAIN_REQUEST.private.json',request)
    try:
        if terminal:
            from terminal_checkpoint_recovery import reconcile
            handoff=reconcile(root,controls,preparation)
        else:
            handoff=drain(root,controls,request)
        state=unit(preparation['unit'])
        require(state['ActiveState'] in ('failed','inactive') and state['MainPID']=='0',
                'legacy unit not terminal; do not launch a replacement')
        group=Path('/sys/fs/cgroup')/state['ControlGroup'].lstrip('/')
        if state['ControlGroup'] and (group/'cgroup.procs').exists():
            require(not (group/'cgroup.procs').read_text().strip(),'legacy cgroup has surviving children')
        verify_pins(preparation['sources'])
        for name,expected in preparation['serving_units'].items():
            require(unit(name)==expected,'serving identity changed during handoff')
        for path in ['ARMED.private.json','PROGRESS.private.json','COMMITTED.private.json']:
            target=controls/('BEFORE_'+path)
            require(not target.exists(),'existing activation evidence')
            install_bytes(target,(root/path).read_bytes())
        seal=dict(format='vk-controlled-conversion-v1',operation=preparation['operation'],
            attempt=preparation['new_attempt'],sources=preparation['runner_sources'],
            handoff=str(controls/'HANDOFF.private.json'),backup_leases=preparation['backup_leases'])
        atomic(controls/'CONTROLLER_SEAL.private.json',seal)
        watcher=preparation['watcher'];config_path=Path(watcher['config']['path'])
        config=read(config_path);state_root=Path(config['state_file']).parent
        with locked(state_root/'incidents.lock'):
            verify_pins([watcher['config'],watcher['source']])
            for name in ('checkpoint_control.py','controlled_conversion.py','control_observation.py'):
                destination=Path(watcher['source']['path']).parent/name
                require(not destination.exists(),'unexpected watcher control module; reconcile')
                install_bytes(destination,(controls/'source'/name).read_bytes())
            install_bytes(watcher['source']['path'],(controls/'conversion_source.candidate.py').read_bytes(),
                          Path(watcher['source']['path']).stat().st_mode&0o777)
            config['checkpoint_controls']=str(controls);atomic(config_path,config)
        # Reset only the now-terminal transient converter unit. No stop/restart
        # of any backend, proxy, frontend or unrelated service is issued.
        if state['ActiveState']=='failed':
            subprocess.run(['systemctl','--user','reset-failed',preparation['unit']],check=True,timeout=10)
        command=['systemd-run','--user','--unit='+preparation['unit'],'--collect']
        for key,value in preparation['unit_properties'].items():command+=['--property='+key+'='+str(value)]
        command+=['--property=StandardOutput=append:'+str(controls/'controlled.log'),
                  '--property=StandardError=append:'+str(controls/'controlled.log'),
                  '/usr/bin/python3','-B','-u',str(controls/'source/controlled_conversion.py'),
                  '--operation-root',str(root),'--controls',str(controls),
                  '--seal',str(controls/'CONTROLLER_SEAL.private.json')]
        atomic(controls/'LAUNCH_INTENT.private.json',dict(at=time.time(),command=command,prior_unit=state))
        subprocess.run(command,check=True,timeout=20)
        expires=time.monotonic()+120
        while True:
            live=unit(preparation['unit']);status_path=controls/'status.json'
            if status_path.exists():
                status=read(status_path)
                if (status['state']=='paused' and status['attempt']==preparation['new_attempt']
                        and str(status['process']['pid'])==live['MainPID']
                        and process_identity(status['process']['pid'])==status['process']):break
            require(live['ActiveState'] not in ('failed','inactive'),'controlled worker failed; inspect exact receipts')
            require(time.monotonic()<expires,'launch acknowledgement uncertain; do not dispatch again')
            time.sleep(1)
        group=Path('/sys/fs/cgroup')/live['ControlGroup'].lstrip('/')
        pids=[int(pid)for pid in (group/'cgroup.procs').read_text().split()]
        assert_leases_closed(preparation['backup_leases'],pids)
        for name,expected in preparation['serving_units'].items():
            require(unit(name)==expected,'serving identity changed')
        result=dict(at=time.time(),unit=live,operation=preparation['operation'],state='paused',
                    verified_checkpoint=handoff['checkpoint']['checkpoint_sha256'],backup_access_released=True,
                    no_backend_restart=True,explicit_resume_required=True)
        atomic(controls/'ACTIVE.private.json',result)
        return result
    except BaseException as error:
        atomic(controls/'ACTIVATION_FAILURE.private.json',dict(at=time.time(),type=type(error).__name__,
            error=str(error),no_automatic_retry=True,inspect_unit_and_exact_receipts_before_action=True))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preparation',required=True);parser.add_argument('--activate',action='store_true')
    parser.add_argument('--authorization-ref');args=parser.parse_args()
    if args.activate:
        require(args.authorization_ref is not None,'actual operator authorization reference required')
        result=activate(args.preparation,args.authorization_ref)
    else:
        preparation=read(args.preparation,8*1024**2);verify_pins(preparation['sources'])
        result=dict(prepared_sources_verified=True,activated=False,live_job_unchanged=True)
    print(json.dumps(result,sort_keys=True))
