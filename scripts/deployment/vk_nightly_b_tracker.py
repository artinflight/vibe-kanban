"""Durable B-native tracking with fixed-size optional SSD health mirrors.

The journal and full status live on B. A missing/full SSD health mirror cannot
silently disable observation: the durable status records its failure instead.
The RAM socket is bounded and ephemeral; a lost B connection fails closed and
a new process always starts an explicit new epoch requiring reconciliation.
"""
import argparse
from contextlib import contextmanager
import errno
import hashlib
import json
import os
from pathlib import Path
import signal
import threading

from vk_nightly_b_controls import tracking_store,seed
from vk_nightly_desktop_controls import DesktopControls
from vk_nightly_tracking import serve
from vk_prep_common import save


def write_health(db,path,value,*,mirror=save):
    value=dict(value)
    if Path(path).is_relative_to('/mnt/vk-storage') and not os.path.ismount('/mnt/vk-storage'):
        value['optional_SSD_health_mirror_error']='secondary SSD unavailable; no local write attempted'
    elif len(json.dumps(value).encode())>65536:
        value['optional_SSD_health_mirror_error']='status exceeds fixed 64KiB mirror budget'
    else:
        try:mirror(path,value)
        except OSError as error:
            if error.errno not in (errno.ENOSPC,errno.EDQUOT,errno.EROFS):raise
            value['optional_SSD_health_mirror_error']=str(error)
    db.execute('insert into tracking_health values(1,?) on conflict(id) do update set row=excluded.row',
               (json.dumps(value,sort_keys=True,separators=(',',':')),))


def run(config,*,guard,mirror=save):
    stop=threading.Event()
    signal.signal(signal.SIGTERM,lambda *_:stop.set());signal.signal(signal.SIGINT,lambda *_:stop.set())
    with DesktopControls(config['controls'],guard=guard) as remote:
        digest=config.get('checkpoint_sha256') or seed(remote.client)
        @contextmanager
        def factory():
            with tracking_store(remote.client,config['index_name'],digest) as store:
                store.db.execute('create table if not exists tracking_health(id integer primary key,row text not null)')
                def status(value):
                    value=dict(value,control_storage='native-Desktop-B',checkpoint_sha256=digest,
                               work_SSD_index_or_journal_bytes=0)
                    write_health(store.db,Path(config['status']),value,mirror=mirror)
                factory.status=status
                yield store
        plan=json.loads(Path(config['plan']).read_text())
        serve(plan,None,Path(config['endpoint']),guard=guard,status_path=None,stop=stop,
              store_factory=factory,status_writer=lambda value:factory.status(value))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True,type=Path)
    parser.add_argument('--sha256',required=True);args=parser.parse_args()
    p=args.config
    if p.resolve()!=p or not p.is_absolute() or p.is_symlink() or p.stat().st_uid!=os.getuid() or p.stat().st_mode&0o022:
        raise ValueError('canonical owned B tracking config required')
    raw=p.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=args.sha256:raise ValueError('B tracker configuration differs')
    config=json.loads(raw)
    status=Path(config['status'])
    if not status.is_absolute() or status.resolve()!=status or not status.is_relative_to('/mnt/vk-storage'):
        raise ValueError('canonical fixed-size SSD status mirror path required')
    for module,digest in config['source_sha256'].items():
        if Path(module).name!=module or hashlib.sha256(Path(__file__).with_name(module).read_bytes()).hexdigest()!=digest:
            raise ValueError('B tracker source pin changed')
    if hashlib.sha256(Path(config['plan']).read_bytes()).hexdigest()!=config['plan_sha256']:
        raise ValueError('source plan pin changed')
    endpoint=Path(config['endpoint'])
    if endpoint.parent!=Path('/dev/shm') or not endpoint.name.startswith('vk-nightly-tracking-'):
        raise ValueError('fixed bounded RAM tracking socket required')
    def guard():
        m={s.split(':')[0]:int(s.split()[1])*1024 for s in Path('/proc/meminfo').read_text().splitlines()}
        if m['MemAvailable']<config['minimum_mem_available_bytes'] or m['SwapFree']<config['minimum_swap_available_bytes']:
            raise ValueError('actual host memory/swap headroom unavailable')
    guard();run(config,guard=guard)


if __name__=='__main__':main()
