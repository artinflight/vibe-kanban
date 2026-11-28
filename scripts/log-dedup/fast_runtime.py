"""Opt-in qualified acceleration hooks for one new finite controller attempt."""
from pathlib import Path
import fast_online
import fast_retirement
import parallel_prepare
import remote_preparation
import remote_dispatch
import remote_pack
from parallel_prepare import PreparationPool


def install(base,config,override=None):
    worker=base.w;owner=worker.online_owner
    source=Path(config['source_dir'])
    for module in [fast_online,fast_retirement,parallel_prepare,remote_preparation,remote_dispatch,remote_pack]:
        if Path(module.__file__)!=source/(module.__name__+'.py'):
            raise ValueError('Acceleration module is outside its pinned source directory')
    if fast_online.ClosedLogFence is not owner.ClosedLogFence:
        raise ValueError('Acceleration fence differs from the qualified parent')
    units=fast_online.FreshUnits(list(owner.UNITS.values()))
    for name in owner.UNITS.values():
        if units(name)!=owner.unit(name):raise ValueError('Fresh unit query differs from qualified service identity')
    owner.unit=units;owner.readonly_mount=fast_online.readonly_mount
    owner.ClosedLogFence=fast_online.FreshClosedLogFence
    worker.support.retire_new_staging_objects=fast_retirement.retire_new_staging_objects
    pool=PreparationPool(worker,base.selection,worker.D,config,override)
    worker._parallel_preparation=pool
    template=Path(config['source_dir'])/'fast_prepare_template.py'
    exec(compile(template.read_bytes(),str(template),'exec'),worker.__dict__)
    return pool
