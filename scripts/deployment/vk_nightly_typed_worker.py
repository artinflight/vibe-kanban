"""Installed finite typed-file capture phase; calendar adoption stays separate.

This executable processes an explicitly prepared member map with actual host
and native B guards. It is also the capture phase for the final incremental
cycle. Successful phase exit is not baseline/SQL/journal/runtime acceptance;
an unaccepted bootstrap configuration cannot be called a commissioned nightly.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
import io
import fcntl

from vk_nightly_current_map import CurrentMap
from vk_nightly_desktop_objects import DesktopObjects,validate as validate_desktop
from vk_nightly_typed_capture import capture_pending
from vk_nightly_prefix_reader import read_prefix
from vk_nightly_sql_point import capture_SQL_point,release_verified_ram
from vk_prep_common import save


class ResourceDeferred(OSError):pass


def checksum(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda:source.read(65536),b''):digest.update(block)
    return digest.hexdigest()


def source_closure(folder):
    """Finite installed Python dependency closure, never a source-tree walk."""
    pending=['vk_nightly_typed_worker'];found=set()
    while pending:
        name=pending.pop()
        if name in found:continue
        if not re.fullmatch('vk_[a-z0-9_]+',name):raise ValueError('fixed worker module name required')
        found.add(name)
        for node in ast.walk(ast.parse((Path(folder)/(name+'.py')).read_text())):
            names=([node.module] if isinstance(node,ast.ImportFrom) else
                   [a.name for a in node.names] if isinstance(node,ast.Import) else [])
            pending.extend(n for n in names if n and n.startswith('vk_') and n not in found)
    return {name+'.py' for name in found}


def configuration(path,expected):
    path=Path(path)
    if not path.is_absolute() or path.resolve()!=path:raise ValueError('canonical installed configuration required')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as source:
        info=os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o022:
            raise ValueError('owned non-writable-by-others installed configuration required')
        raw=source.read(1024**2+1)
    if len(raw)>1024**2 or hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('installed configuration differs')
    value=json.loads(raw)
    if value.get('format') not in ('vk-nightly-typed-file-worker-v1','vk-nightly-typed-worker-v1'):
        raise ValueError('unknown typed worker configuration')
    for name,digest in value['source_sha256'].items():
        if not re.fullmatch(r'vk_[a-z0-9_]+\.py',name) or checksum(Path(__file__).with_name(name))!=digest:
            raise ValueError('installed worker source differs: '+name)
    required=source_closure(Path(__file__).parent)
    if not required<=value['source_sha256'].keys():raise ValueError('worker source binding incomplete')
    for name in ('maximum_map_bytes','maximum_members','maximum_source_bytes','chunk_bytes','timeout_seconds'):
        if type(value[name]) is not int or value[name]<1:raise ValueError('positive finite worker budget required: '+name)
    if value['chunk_bytes']>value['desktop']['maximum_object_bytes']:raise ValueError('chunk exceeds admitted object RAM')
    for name in ('ssd_floor_bytes','root_floor_bytes','control_margin_bytes','memory_floor_bytes','swap_floor_bytes'):
        if type(value[name]) is not int or value[name]<0:raise ValueError('actual nonnegative resource binding required')
    for name in ('map','status'):
        p=Path(value[name])
        if not p.is_absolute() or p.resolve()!=p or not p.is_relative_to('/mnt/vk-storage'):
            raise ValueError('canonical SSD control path required')
    if value.get('schedule_enabled') is True or value.get('baseline_accepted') is True:
        raise ValueError('file-phase configuration cannot claim whole-cycle acceptance or calendar adoption')
    validate_desktop(value['desktop'],Path(__file__).with_name('vk_nightly_objects.py').read_text())
    if value.get('phase_kind','file-points') not in ('file-points','SQL-points'):raise ValueError('unknown prepared phase')
    if value.get('phase_kind')=='SQL-points':
        sources=value['SQL_sources']
        if (not isinstance(sources,list) or not sources or len(sources)>1024 or len(sources)!=len(set(sources))
                or type(value['maximum_SQL_image_bytes']) is not int or value['maximum_SQL_image_bytes']<1
                or any(not isinstance(p,str) or not p.startswith('/') or str(Path(p))!=p or '..' in Path(p).parts for p in sources)):
            raise ValueError('finite exact prepared SQL source queue required')
        catalog=Path(value['SQL_catalog'])
        if (not catalog.is_relative_to('/mnt/vk-storage') or catalog.resolve()!=catalog
                or checksum(catalog)!=value['SQL_catalog_sha256']):raise ValueError('retained SQL catalog binding differs')
    return value


def host_guard(config,started):
    if not os.path.ismount('/mnt/vk-storage'):raise ResourceDeferred('actual secondary SSD mount unavailable')
    for path,floor in [('/mnt/vk-storage',config['ssd_floor_bytes']),('/',config['root_floor_bytes'])]:
        fs=os.statvfs(path)
        if fs.f_bavail*fs.f_frsize<=floor+config['control_margin_bytes']:
            raise ResourceDeferred('actual free space below preserved floor/control margin: '+path)
    m={row.split(':')[0]:int(row.split()[1])*1024 for row in Path('/proc/meminfo').read_text().splitlines()}
    if m['MemAvailable']<config['memory_floor_bytes'] or m['SwapFree']<config['swap_floor_bytes']:
        raise ResourceDeferred('actual memory/swap headroom unavailable')
    if time.monotonic()-started>config['timeout_seconds']:raise ResourceDeferred('finite worker phase expired; retain completed chunks and pending point')


def run(config):
    if config.get('phase_kind')=='SQL-points':return run_SQL(config)
    started=time.monotonic();guard=lambda:host_guard(config,started)
    def report(value):
        save(Path(config['status']),dict(value,worker_PID=os.getpid(),elapsed_seconds=time.monotonic()-started,
             baseline_accepted=False,schedule_enabled=False,OS_SSD_payload_bytes=0))
    guard();report(dict(phase='acquiring-prepared-map-and-existing-native-writer-lane'))
    with CurrentMap.held(config['map'],binding=config['map_binding'],maximum_bytes=config['maximum_map_bytes']) as current:
        with DesktopObjects(config['desktop'],guard=guard) as remote:
            result=capture_pending(current,remote.client,guard=guard,maximum_members=config['maximum_members'],
                maximum_source_bytes=config['maximum_source_bytes'],chunk_bytes=config['chunk_bytes'],
                read_prefix=lambda prefix,sink:read_prefix(remote,prefix,sink),
                on_progress=lambda value:report(dict(value,phase='qualified-file-capture-and-independent-readback')))
            result['native_admission']=remote.ready
        report(dict(result,phase='prepared-file-phase-complete' if not result['more_pending'] else 'bounded-prepared-file-phase-retained'))
    return result


def run_SQL(config):
    """One frozen prepared cohort, resuming points rather than live recapture."""
    started=time.monotonic();guard=lambda:host_guard(config,started)
    folder=Path(config['status']).parent;state_path=folder/'SQL_STATE.private.json'
    binding=dict(sources=config['SQL_sources'],catalog_sha256=config['SQL_catalog_sha256'],B_root=config['desktop']['B_root'])
    # Resource ceilings/code versions may be reviewed for a successor phase;
    # the source cohort and B recovery identity cannot silently change.
    fd=os.open(folder/'SQL_PHASE.lease',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_NONBLOCK,0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):raise ValueError('owned SQL phase lease required')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        state=json.loads(state_path.read_text()) if state_path.exists() else dict(binding=binding,completed={},partial={},deferred={})
        if state['binding']!=binding:raise ValueError('retained SQL phase input binding changed')
        images=json.loads(Path(config['SQL_catalog']).read_text())['sql_images']
        old={(v['sha256'],v['bytes']):v for v in images.values()}
        def report(phase):
            save(state_path,state)
            save(Path(config['status']),dict(phase=phase,worker_PID=os.getpid(),completed_SQL_images=len(state['completed']),
                requested_SQL_images=len(config['SQL_sources']),deferred_SQL_images=len(state['deferred']),
                pending_SQL_partial_images=len(state['partial']),baseline_accepted=False,schedule_enabled=False,
                new_B_SQL_payload_encoded_bytes=sum(v.get('new_B_encoded_payload_bytes',0) for v in state['completed'].values()),
                source_API_image_bytes=sum(v.get('source_API_image_bytes',0) for v in state['completed'].values()),
                old_native_images_reused=sum(v.get('independent',{}).get('reused_accepted_independent_SQL_image',False) for v in state['completed'].values()),
                OS_SSD_payload_bytes=0,elapsed_seconds=time.monotonic()-started))
        def check_accepted(client,record):
            output=io.BytesIO();client.verify(record['B_acceptance_object'],output)
            actual=json.loads(output.getvalue())
            expected={k:v for k,v in record.items() if k not in ('B_acceptance_object','new_B_total_encoded_bytes_including_control')}
            if actual!=expected:raise ValueError('cached SQL acceptance differs from durable B record')
            for copy in record.get('verified_RAM_duplicates',[]):
                p=Path(copy['path'])
                if p.exists():
                    if p.parent!=Path('/dev/shm') or not p.name.startswith(('nightly-sql-api-','nightly-sql-independent-')):
                        raise ValueError('unknown cached RAM duplicate; preserve')
                    release_verified_ram(p,copy['identity'])
        guard();report('acquiring-current-SQL-source-cohort-and-existing-B-writer-lane')
        with DesktopObjects(config['desktop'],guard=guard) as remote:
            for source in config['SQL_sources']:
                guard()
                record=state['completed'].get(source) or state['partial'].get(source,{}).get('accepted')
                if record is not None:
                    check_accepted(remote.client,record);state['completed'][source]=record;state['partial'].pop(source,None)
                    report('reused-completed-SQL-point-without-source-recapture');continue
                def prepared(value):
                    state['partial'].setdefault(source,{}).update(value);report('SQL-API-point-retained-before-next-step')
                retained=state['partial'].get(source,{}).get('captured_RAM_point')
                result=capture_SQL_point(source,remote.client,allowed_sources=set(config['SQL_sources']),guard=guard,
                    retained_by_sha=lambda sha,size:old.get((sha,size)),ram_root='/dev/shm',
                    maximum_image_bytes=config['maximum_SQL_image_bytes'],chunk_bytes=config['chunk_bytes'],
                    timeout_seconds=config['SQL_image_timeout_seconds'],on_prepared=prepared,resume=retained)
                if result['status']=='larger_SQL_working_window_required':state['deferred'][source]=result
                else:
                    state['completed'][source]=result;state['partial'].pop(source,None);state['deferred'].pop(source,None)
                report('prepared-SQL-cohort-advancing')
        result=dict(completed_members=len(state['completed']),more_pending=len(state['completed'])!=len(config['SQL_sources']),
                    deferred_SQL=state['deferred'],baseline_accepted=False)
        report('prepared-SQL-cohort-complete' if not result['more_pending'] else 'larger-measured-SQL-window-pending')
        return result
    finally:os.close(fd)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True);parser.add_argument('--config-sha256',required=True)
    parser.add_argument('--check-config',action='store_true');args=parser.parse_args()
    if os.getuid()==0:raise ValueError('existing unprivileged owner required')
    config=configuration(args.config,args.config_sha256)
    if args.check_config:
        print(json.dumps(dict(configuration_verified=True,capture_started=False,baseline_accepted=False,schedule_enabled=False)))
        return 0
    result=run(config);print(json.dumps(result),flush=True)
    return 75 if result['more_pending'] else 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (ResourceDeferred,BlockingIOError) as error:
        print(json.dumps(dict(status='resource_or_owner_deferred',reason=str(error),completed_objects_preserved=True)),file=sys.stderr)
        raise SystemExit(75)
    except (OSError,ValueError,KeyError,RuntimeError) as error:
        print(json.dumps(dict(status='typed_file_worker_blocked',reason=str(error),
            reader_diagnostic=getattr(error,'nightly_reader_diagnostic',None),all_recovery_preserved=True)),file=sys.stderr)
        raise SystemExit(1)
