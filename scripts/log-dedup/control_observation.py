"""Explain verified cooperative holds without crediting them as conversion progress."""
from pathlib import Path
from checkpoint_control import Controls, process_identity, read
from controlled_conversion import assert_leases_closed


def supplement(row,config,service,now):
    root=config.get('checkpoint_controls')
    if not root or row.get('state') not in ('running','stalled'):
        return row
    try:
        value=read(Path(root)/'status.json')
        if (service['ActiveState']!='active' or str(value['process']['pid'])!=service['MainPID']
                or value['operation']!=row['operation'] or value['attempt']!=row.get('attempt')
                or process_identity(value['process']['pid'])!=value['process']):return row
        command=Controls(Path(root),row['operation']).command()
        if value['state']=='running' and command['action']=='pause':
            return dict(row,control_request='pause',control_message='Pause requested; waiting for a verified batch boundary')
        if value['state'] not in ('paused','waiting_for_backup') or not 0<=now-value['at']<=60:return row
        control=read(Path(root)/'CONTROLLER_SEAL.private.json',8*1024**2)
        if control['operation']!=row['operation'] or control['attempt']!=row['attempt']:return row
        pid=value['process']['pid']
        group=next(r.split(':',2)[2] for r in Path('/proc',str(pid),'cgroup').read_text().splitlines() if r.startswith('0::'))
        pids=[int(p) for p in (Path('/sys/fs/cgroup')/group.lstrip('/')/'cgroup.procs').read_text().split()]
        assert_leases_closed(control['backup_leases'],pids)
    except (OSError,ValueError,KeyError,StopIteration):return row
    result=dict(row,state=value['state'],needs_attention=False,
                phase='paused_at_verified_checkpoint' if value['state']=='paused' else 'waiting_for_backup_access',
                control_checked_at=value['at'],checkpoint=value['checkpoint'],
                control_request=command['action'])
    # progress_at intentionally remains the last real conversion progress.
    return result
