"""Upgrade only the finite converter at an acknowledged clean pause.

Never restarts a Vibe/backend/reader service. Preserves selected settings, old
seals, the complete committed prefix and the isolated batch37 mapping. A single
retained activation may be reconciled, never automatically replayed.
"""
import argparse
from pathlib import Path
import subprocess
import time

from checkpoint_control import Controls, atomic, locked, process_identity, read, require
from controlled_conversion import checkpoint, verify_pins, assert_leases_closed

UNIT='vk-online-dedup-bulk-20261119-v1.service'


def unit(name):
    out=subprocess.check_output(['systemctl','--user','show',name,'-p','MainPID','-p','InvocationID',
        '-p','ActiveState','-p','ControlGroup'],text=True,timeout=10)
    return dict(line.split('=',1)for line in out.splitlines())


def paused_owner(root,controls,expected,leases,override):
    require(unit(UNIT)==expected,'finite converter unit identity changed')
    value=Controls(controls,read(Path(controls)/'CONTROLLER_SEAL.private.json')['operation']).status()
    status=value['worker'];require(value['worker_identity_live'] and value['observation_age_seconds']<15,
        'fresh exact live pause required')
    require(status['state']=='paused' and value['command']['action']=='pause' and
        str(status['process']['pid'])==expected['MainPID'],'converter has not acknowledged pause')
    cp=checkpoint(root,verify_installs=True,batch_override=override)
    require(cp['checkpoint_sha256']==status['checkpoint']['checkpoint_sha256'],'pause checkpoint differs')
    group=Path('/sys/fs/cgroup')/expected['ControlGroup'].lstrip('/')
    pids=[int(x)for x in (group/'cgroup.procs').read_text().split()]
    require(pids==[status['process']['pid']],'unexpected surviving converter child at pause')
    assert_leases_closed(leases,pids)
    return status,cp


def activate(path):
    p=read(path,8*1024**2);verify_pins(p['sources'])
    require(p['unit']==UNIT and p['authorization_ref'],'exact finite unit and operator authorization required')
    root=Path(p['operation_root']);old=Path(p['old_controls']);new=Path(p['controls'])
    require(not (new/'ACTIVATION_ATTEMPT').exists(),'activation already attempted; reconcile')
    atomic(new/'ACTIVATION_ATTEMPT',dict(at=time.time(),authorization_ref=p['authorization_ref']))
    oldseal=read(old/'CONTROLLER_SEAL.private.json');oldhandoff=read(oldseal['handoff'])
    override=oldhandoff.get('batch_override');leases=oldseal['backup_leases']
    try:
        with locked(old/'commands.lock'):
            status,cp=paused_owner(root,old,p['old_unit'],leases,override)
            require(status['command']['request_id']==p['pause_request_id'],'another operator command superseded this handoff')
            for name,expected in p['serving_units'].items():require(unit(name)==expected,'serving identity changed')
            atomic(new/'PAUSED_BOUNDARY.private.json',dict(at=time.time(),status=status,checkpoint=cp,unit=p['old_unit']))
            require(process_identity(status['process']['pid'])==status['process'],'paused process changed')
            # Only this already-paused finite computation unit is stopped.
            subprocess.run(['systemctl','--user','stop',UNIT],check=True,timeout=30)
            terminal=unit(UNIT);require(terminal['MainPID']=='0' and terminal['ActiveState'] in ('inactive','failed'),'old unit not terminal')
            try:current=process_identity(status['process']['pid'])
            except FileNotFoundError:current=None
            require(current!=status['process'],'old controller survived')
            require(not (root/'FAILURE.private.json').exists(),'unexpected failure at clean checkpoint')
            after=checkpoint(root,verify_installs=True,batch_override=override)
            require(after['checkpoint_sha256']==cp['checkpoint_sha256'],'committed checkpoint changed during stop')
            atomic(new/'HANDOFF.private.json',dict(verified=True,clean_paused_boundary=True,operation=p['operation'],
                old_process=status['process'],pause_status=status,checkpoint=after,batch_override=override,
                all_prior_receipts_preserved=True,at=time.time(),no_backend_restart=True))
        verify_pins(p['sources'])
        seal=dict(format='vk-controlled-conversion-v1',operation=p['operation'],attempt=p['attempt'],
            sources=p['runner_sources'],handoff=str(new/'HANDOFF.private.json'),backup_leases=leases,
            runtime_config=p['runtime_config'])
        atomic(new/'CONTROLLER_SEAL.private.json',seal)
        config_path=Path(p['watcher_config']['path']);config=read(config_path)
        with locked(Path(config['state_file']).parent/'incidents.lock'):
            verify_pins([p['watcher_config']]);config=read(config_path)
            atomic(new/'WATCHER_CONFIG_BEFORE.private.json',config)
            require(config['checkpoint_controls']==str(old),'watcher controls changed')
            config['checkpoint_controls']=str(new);atomic(config_path,config)
        if terminal['ActiveState']=='failed':subprocess.run(['systemctl','--user','reset-failed',UNIT],check=True,timeout=10)
        command=['systemd-run','--user','--unit='+UNIT,'--collect']
        for key,value in p['unit_properties'].items():command+=['--property='+key+'='+str(value)]
        command+=['--property=StandardOutput=append:'+str(new/'controlled.log'),
                  '--property=StandardError=append:'+str(new/'controlled.log'),'/usr/bin/python3','-B','-u',
                  str(new/'source/controlled_conversion.py'),'--operation-root',str(root),'--controls',str(new),
                  '--seal',str(new/'CONTROLLER_SEAL.private.json')]
        atomic(new/'LAUNCH_INTENT.private.json',dict(at=time.time(),command=command,terminal_unit=terminal))
        subprocess.run(command,check=True,timeout=20)
        deadline=time.monotonic()+120
        while True:
            live=unit(UNIT);value=Controls(new,p['operation']).status();worker=value['worker']
            if worker and value['worker_identity_live'] and worker['state']=='paused' and str(worker['process']['pid'])==live['MainPID']:break
            require(live['ActiveState'] not in ('failed','inactive'),'new finite controller failed; reconcile retained evidence')
            require(time.monotonic()<deadline,'launch acknowledgement uncertain; never redispatch')
            time.sleep(1)
        for name,expected in p['serving_units'].items():require(unit(name)==expected,'serving identity changed')
        result=dict(at=time.time(),unit=live,state='paused',checkpoint=after['checkpoint_sha256'],no_backend_restart=True)
        atomic(new/'ACTIVE.private.json',result);return result
    except BaseException as error:
        atomic(new/'ACTIVATION_FAILURE.private.json',dict(at=time.time(),type=type(error).__name__,error=str(error),
            no_automatic_retry=True,inspect_exact_processes_and_receipts=True))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--preparation',required=True)
    parser.add_argument('--activate',action='store_true');args=parser.parse_args()
    if args.activate:print(activate(args.preparation))
    else:
        p=read(args.preparation,8*1024**2);verify_pins(p['sources']);print({'prepared_sources_verified':True,'activated':False})
