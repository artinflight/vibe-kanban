"""Measured admission for bounded metadata-only jobs, never SQL/body capture.

Reserve the actual unused enforced cgroup allocation, counted once. A fixed
whole-capture RAM floor is not a memory model for a small metadata process.
An ordinary source/API/body worker must retain its own separate admission.
"""
from pathlib import Path


class MetadataDeferred(OSError):
    """No new metadata IO admitted; keep committed B cursors for resume."""


def actual_cgroup():
    name=next(v[3:] for v in Path('/proc/self/cgroup').read_text().splitlines()if v.startswith('0::'))
    folder=Path('/sys/fs/cgroup'+name)
    return dict(maximum=folder.joinpath('memory.max').read_text().strip(),
        current=int(folder.joinpath('memory.current').read_text()),
        swap=folder.joinpath('memory.swap.max').read_text().strip(),
        events={k:int(v)for k,v in (line.split()for line in folder.joinpath('memory.events').read_text().splitlines())})


def check(*,maximum_memory_bytes,maximum_frame_bytes,metadata_only,
          cgroup=actual_cgroup,memory=None):
    if metadata_only is not True or type(maximum_memory_bytes)is not int or type(maximum_frame_bytes)is not int or not 0<maximum_frame_bytes<maximum_memory_bytes:
        raise ValueError('explicit bounded metadata-only scope required')
    state=cgroup();limit=state['maximum']
    if not str(limit).isdigit()or not 0<int(limit)<=maximum_memory_bytes or state['swap']!='0':
        raise ValueError('actual finite metadata cgroup/zero-swap enforcement required')
    if state['events'].get('oom',0)or state['events'].get('oom_kill',0):
        raise ValueError('actual owned metadata cgroup OOM event; preserve evidence')
    remaining=int(limit)-state['current']
    if remaining<maximum_frame_bytes:
        raise MetadataDeferred('owned metadata cgroup lacks next-frame headroom')
    available=(int(next(v.split()[1]for v in Path('/proc/meminfo').read_text().splitlines()if v.startswith('MemAvailable:')))*1024 if memory is None else memory())
    # Current resident bytes are already charged to the host. Reserve the rest
    # of this enforced allocation, including its bounded next protocol frame.
    if available<remaining:
        raise MetadataDeferred('host cannot admit remaining enforced metadata allocation')
    return dict(actual_cgroup_limit=int(limit),already_resident_bytes=state['current'],
        additional_peak_reserved_bytes=remaining,maximum_frame_bytes=maximum_frame_bytes,
        body_or_SQL_admitted=False)
