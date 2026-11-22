"""One-shot terminal recovery for unpublished partial graph backup; no restart.

The old converter must be dead. The serving backends remain untouched. The new
finite converter starts paused and independently reopens retained B receipts.
"""
import argparse
import os
from pathlib import Path
import subprocess
import time

from checkpoint_control import Controls, atomic, locked, process_identity, read, require
from controlled_conversion import checkpoint, reference, sha, verify_pins
from activate_checkpoint_controls import install_bytes
from upgrade_controlled_worker import UNIT, unit


def terminal(p):
    require(p['unit']==UNIT and p['authorization_ref'], 'exact finite unit and authorization required')
    require(unit(UNIT)==p['terminal_unit'] and p['terminal_unit']['MainPID']=='0'
            and p['terminal_unit']['ActiveState'] in ('failed','inactive'), 'converter is not the reconciled terminal unit')
    try: current=process_identity(p['old_process']['pid'])
    except FileNotFoundError: current=None
    require(current!=p['old_process'], 'old converter is still alive')
    for name,expected in p['serving_units'].items():
        require(unit(name)==expected, 'serving identity changed')
    root=Path(p['operation_root'])
    failure=read(root/'FAILURE.private.json')
    require(sha(root/'FAILURE.private.json')==p['failure_sha256']
            and failure['operation']==p['operation'] and failure['attempt']==p['old_attempt'], 'failure binding changed')
    cp=checkpoint(root,True,batch_override=p['batch_override'],pending_graph=p['pending_graph'])
    require(cp['next_batch']==p['pending_graph']['batch'] and
            cp['completed_batches']==failure['completed_batches'], 'failure checkpoint differs')
    return cp


def activate(path):
    p=read(path,8*1024**2);verify_pins(p['sources'])
    root=Path(p['operation_root']);new=Path(p['controls'])
    require(root.resolve()==root and new.parent==root and os.path.ismount('/mnt/vk-storage'), 'mounted exact operation required')
    terminal(p)
    fd=os.open(new/'ACTIVATION_ATTEMPT',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
    try:
        with locked(root.parents[1]/'production-owner.lock',nonblocking=True):
            cp=terminal(p);verify_pins(p['sources'])
            atomic(new/'HANDOFF.private.json',dict(verified=True,operation=p['operation'],
                old_process=p['old_process'],failure_sha256=p['failure_sha256'],checkpoint=cp,
                batch_override=p['batch_override'],pending_graph=p['pending_graph'],at=time.time(),
                all_prior_receipts_preserved=True,no_backend_restart=True))
            seal=dict(format='vk-controlled-conversion-v1',operation=p['operation'],attempt=p['attempt'],
                sources=p['runner_sources'],handoff=str(new/'HANDOFF.private.json'),
                backup_leases=p['backup_leases'],runtime_config=p['runtime_config'])
            atomic(new/'CONTROLLER_SEAL.private.json',seal)
        if p['terminal_unit']['ActiveState']=='failed':
            subprocess.run(['systemctl','--user','reset-failed',UNIT],check=True,timeout=10)
        command=['systemd-run','--user','--unit='+UNIT,'--collect']
        for key,value in p['unit_properties'].items():command+=['--property='+key+'='+str(value)]
        command+=['--property=StandardOutput=append:'+str(new/'controlled.log'),
                  '--property=StandardError=append:'+str(new/'controlled.log'),'/usr/bin/python3','-B','-u',
                  str(new/'source/controlled_conversion.py'),'--operation-root',str(root),'--controls',str(new),
                  '--seal',str(new/'CONTROLLER_SEAL.private.json')]
        atomic(new/'LAUNCH_INTENT.private.json',dict(at=time.time(),command=command))
        subprocess.run(command,check=True,timeout=20)
        deadline=time.monotonic()+120
        while True:
            live=unit(UNIT);value=Controls(new,p['operation']).status();worker=value['worker']
            if worker and value['worker_identity_live'] and worker['state']=='paused' and str(worker['process']['pid'])==live['MainPID']:break
            require(live['ActiveState'] not in ('failed','inactive'),'controller failed; inspect, never redispatch')
            require(time.monotonic()<deadline,'acknowledgement uncertain; never redispatch')
            time.sleep(1)
        for name,expected in p['serving_units'].items():require(unit(name)==expected,'serving identity changed')
        config_path=Path(p['watcher_config']['path']);config=read(config_path)
        with locked(Path(config['state_file']).parent/'incidents.lock'):
            verify_pins([p['watcher_config']]+[r['before'] for r in p['watcher_files'] if r.get('before')])
            config=read(config_path);require(config['checkpoint_controls']==p['old_controls'],'watcher control binding changed')
            atomic(new/'WATCHER_CONFIG_BEFORE.private.json',config)
            for row in p['watcher_files']:
                target=Path(row['destination'])
                if not row.get('before'):require(not target.exists(),'new watcher file already exists')
                verify_pins([row['candidate']])
                if target.exists():install_bytes(new/('BEFORE-'+target.name),target.read_bytes())
                install_bytes(target,Path(row['candidate']['path']).read_bytes(),row['mode'])
            config['checkpoint_controls']=str(new);atomic(config_path,config)
        result=dict(at=time.time(),unit=live,state='paused',checkpoint=cp['checkpoint_sha256'],no_backend_restart=True)
        atomic(new/'ACTIVE.private.json',result);return result
    except BaseException as error:
        atomic(new/'ACTIVATION_FAILURE.private.json',dict(at=time.time(),type=type(error).__name__,error=str(error),no_automatic_retry=True))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--preparation',required=True)
    parser.add_argument('--activate',action='store_true');args=parser.parse_args()
    if args.activate:print(activate(args.preparation))
    else:
        p=read(args.preparation,8*1024**2);verify_pins(p['sources']);print(terminal(p)['checkpoint_sha256'])
