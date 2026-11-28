"""Bounded source-change outbox; Desktop transport is never an observer input.

The local allocation is at most 8MiB of database, 9MiB rollback reservation
plus native filesystem allocation metadata and two 64KiB optional health files. Growing catalogs and backup bodies stay
on B. A full outbox fails closed, retaining its cursor and an explicit gap;
it never silently drops events or fabricates continuity across owner epochs.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import signal
import threading

from vk_nightly_bounded_spool import held
from vk_nightly_b_tracker import write_health
from vk_nightly_tracking import serve
from vk_nightly_inode_journal import Journal as InodeJournal,check_watch_demand


def admit_inode_observation(config,*,read_limit=lambda:int(Path('/proc/sys/fs/inotify/max_user_watches').read_text())):
    if config.get('watch_all_selected_inodes') is True:
        # A retained namespace supplies a lower bound, not a policy threshold
        # or substitute for real enrollment. Reject a known impossible launch
        # before allocating another spool or consuming any kernel watches.
        check_watch_demand(config.get('retained_inode_watch_minimum'),read_limit())


def observer_guard(config, *, mounted=lambda:os.path.ismount('/mnt/vk-storage'),
                   memory=lambda:{s.split(':')[0]:int(s.split()[1])*1024
                       for s in Path('/proc/meminfo').read_text().splitlines()},
                   cgroup_limits=None,metadata_admission=None):
    """Admission may defer enrollment; transient host pressure must not drop watches.

    Opt-in steady operation requires actual existing per-cgroup memory/swap
    limits. No larger allocator, body reader or capture runs in this daemon.
    Kernel/outbox overflow, root changes and other real faults still terminate
    the epoch. A transient global floor remains a capture admission condition,
    not evidence that an already bounded observer must close its inotify FD.
    """
    policy=config.get('steady_resource_policy')
    if policy not in (None,'bounded-cgroup-preserve-inode-drain-v1'):
        raise ValueError('unknown observer steady-resource policy')
    def actual_limits():
        rows=Path('/proc/self/cgroup').read_text().splitlines()
        name=next((s[3:] for s in rows if s.startswith('0::')),None)
        if name is None:raise ValueError('actual unified observer cgroup required')
        root=Path('/sys/fs/cgroup'+name)
        return root.joinpath('memory.max').read_text().strip(),root.joinpath('memory.swap.max').read_text().strip()
    limits=cgroup_limits or actual_limits
    enrolled=[False]
    def guard():
        if not mounted():raise ValueError('metadata SSD unavailable; no OS fallback')
        if policy is not None:
            maximum,swap=limits();bound=config['maximum_observer_memory_bytes']
            if (type(bound) is not int or bound<=0 or not maximum.isdigit()
                    or not 0<int(maximum)<=bound or swap!='0'):
                raise ValueError('actual bounded observer memory/zero-swap enforcement required')
        if not enrolled[0] or policy is None:
            allocation=config.get('allocation_admission_policy')
            if allocation is not None:
                if allocation!='actual-enforced-unused-cgroup-budget-v1' or policy is None:
                    raise ValueError('explicit bounded observer allocation policy required')
                from vk_nightly_metadata_admission import check
                (metadata_admission or check)(maximum_memory_bytes=config['maximum_observer_memory_bytes'],
                    maximum_frame_bytes=config['maximum_outbox_bytes']+16*1024**2,
                    metadata_only=True,memory=lambda:memory()['MemAvailable'])
                return
            available=memory()
            if (available['MemAvailable']<config['minimum_mem_available_bytes']
                    or available['SwapFree']<config['minimum_swap_available_bytes']):
                raise ValueError('actual host memory/swap headroom unavailable before enrollment')
    def on_enrolled():
        if policy is not None:
            enrolled[0]=True;guard()
        else:
            guard();enrolled[0]=True
    guard.on_enrolled=on_enrolled
    return guard

def run(config, *, guard):
    admit_inode_observation(config)
    stop=threading.Event()
    signal.signal(signal.SIGTERM,lambda *_:stop.set())
    signal.signal(signal.SIGINT,lambda *_:stop.set())
    @contextmanager
    def factory():
        with held(config['outbox'],maximum_bytes=config['maximum_outbox_bytes'],guard=guard,
                  replica=config.get('B_delivery_target')) as store:
            def status(value):
                value=dict(value,control_storage='bounded-local-source-outbox',
                    Desktop_connection_required=False,baseline_accepted=False,
                    maximum_outbox_bytes=config['maximum_outbox_bytes'],
                    maximum_rollback_bytes=config['maximum_outbox_bytes']+1024**2)
                write_health(store.db,config['status'],value)
            factory.status=status
            yield store
    options={'journal_factory':InodeJournal} if config.get('watch_all_selected_inodes') is True else {}
    serve(json.loads(Path(config['plan']).read_text()),None,Path(config['endpoint']),
          guard=guard,status_path=None,stop=stop,store_factory=factory,
          status_writer=lambda value:factory.status(value),on_enrolled=getattr(guard,'on_enrolled',lambda:None),**options)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True,type=Path)
    parser.add_argument('--sha256',required=True)
    args=parser.parse_args();p=args.config
    if (not p.is_absolute() or p.resolve()!=p or p.is_symlink()
            or p.stat().st_uid!=os.getuid() or p.stat().st_mode&0o022):
        raise ValueError('canonical owned tracker configuration required')
    raw=p.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=args.sha256:raise ValueError('tracker configuration changed')
    config=json.loads(raw)
    for name,digest in config['source_sha256'].items():
        if Path(name).name!=name or hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()!=digest:
            raise ValueError('tracker source binding changed')
    if hashlib.sha256(Path(config['plan']).read_bytes()).hexdigest()!=config['plan_sha256']:
        raise ValueError('source plan changed')
    for key in ('outbox','status'):
        path=Path(config[key])
        if not path.is_absolute() or path.resolve()!=path or not path.is_relative_to('/mnt/vk-storage'):
            raise ValueError('canonical bounded secondary-SSD metadata path required')
    endpoint=Path(config['endpoint'])
    if endpoint.parent!=Path('/dev/shm') or not endpoint.name.startswith('vk-nightly-tracking-'):
        raise ValueError('bounded private RAM socket required')
    guard=observer_guard(config)
    guard();run(config,guard=guard)


if __name__=='__main__':main()
