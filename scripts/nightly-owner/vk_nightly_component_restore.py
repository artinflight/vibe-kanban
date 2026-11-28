"""Independent NORMAL B restore of one explicit finite software component.

Uses the ordinary provider, held immutable member index and body decoders.
No current-global-set/calendar claim, source open, SQL capture or transport.
"""
from contextlib import ExitStack
import os
from pathlib import Path
import tempfile
from vk_typed_recovery import LocalDependencies,held_index,checksum
from vk_nightly_selected_reader import SelectedFiles
from vk_nightly_composed_restore import restore_sample
from vk_nightly_sql_point import ram_path

FORMAT='vk-nightly-finite-software-consumer-v1'


def run(packet,expected_sha256,*,guard,report=lambda _:None):
    if packet.get('format')!=FORMAT or checksum(packet)!=expected_sha256:
        raise ValueError('authenticated finite software packet required')
    files=packet['files'];placement=packet['provider_placement'];dependencies=packet['dependencies']
    if (not isinstance(files,dict)or not 1<=len(files)<=4096
            or set(placement['roots'])!=set(dependencies)
            or os.getuid()==0 or (os.getuid(),os.getgid())!=(placement['expected_uid'],placement['expected_gid'])):
        raise ValueError('finite owner-pinned normal software scope/identity required')
    if any(type(v.get('bytes'))is not int or v['bytes']<0 for v in files.values()):
        raise ValueError('exact nonnegative component sizes required')
    total=sum(v['bytes']for v in files.values());peak=max(v['bytes']for v in files.values())
    if total>packet['maximum_readback_bytes']or peak+16*1024**2>packet['maximum_scratch_bytes']:
        raise ValueError('software component exceeds actual admitted readback/scratch')
    def admission():
        guard();memory={s.split(':')[0]:int(s.split()[1])*1024 for s in Path('/proc/meminfo').read_text().splitlines()}
        if memory['MemAvailable']<packet['memory_floor_bytes']or memory['SwapFree']<packet['swap_floor_bytes']:
            raise OSError('normal software consumer memory admission unavailable')
    admission()
    if Path('/dev/shm').resolve()!=Path('/dev/shm') or not os.path.ismount('/dev/shm'):
        raise ValueError('actual RAM restore mount required')
    fs=os.statvfs('/dev/shm')
    if fs.f_bavail*fs.f_frsize<peak+16*1024**2:raise OSError('actual sequential RAM restore scratch unavailable')
    memory={s.split(':')[0]:int(s.split()[1])*1024 for s in Path('/proc/meminfo').read_text().splitlines()}
    if memory['MemAvailable']<packet['memory_floor_bytes']+peak+144*1024**2:
        raise OSError('actual software restore peak plus existing headroom unavailable')
    scratch=ram_path(Path(packet.get('scratch_parent','/dev/shm')))
    provider=LocalDependencies(placement['roots'],dependencies,admission_check=admission,
        lease_paths=placement['lease_paths'],expected_root_bindings=placement['root_bindings'])
    results=[];folder=None
    with ExitStack() as stack:
        stack.enter_context(provider.held())
        from vk_nightly_checkpoint_members import Dependencies
        provider=Dependencies(provider);stack.callback(provider.close)
        with held_index(provider,packet['index_reference'])as index:
            rows={}
            for name,row in index.entries():
                if '/'+name not in files:raise ValueError('software index contains undeclared member')
                expected=files['/'+name]
                if (row.get('kind')!='file' or any(row.get(k)!=expected[k]for k in ('bytes','sha256'))
                        or any(row.get(k)!=expected['Linux_metadata'][k]for k in ('mode','uid','gid','mtime_ns','xattrs'))):
                    raise ValueError('software index differs from independently pinned exact version')
                rows[name]=row
            if {'/'+n for n in rows}!=set(files):raise ValueError('software component omits declared dependency')
            selected=SelectedFiles(provider,rows,index.check)
            class Handle:
                descriptor={'SQLite':{}}
                def blocks(self,name):return selected.blocks(name)
                def check(self):index.check()
            handle=Handle();handle.index=index
            folder=Path(tempfile.mkdtemp(prefix='nightly-software-restore-',dir=scratch));ram_path(folder)
            for path in sorted(files):
                results.append(restore_sample(handle,path,folder,guard=admission))
                if len(results)%8==0 or len(results)==len(files):report(dict(phase='normal-software-independent-restore',
                    completed=len(results),files=len(files),verified_bytes=sum(r['bytes']for r in results)))
            handle.check();folder.rmdir() # only verified disposable outputs were released
    return dict(format='vk-nightly-finite-software-restore-acceptance-v1',consumer_packet_sha256=expected_sha256,
        descriptor_sha256=packet['descriptor_sha256'],normal_leased_consumer_entrypoint_verified=True,
        independent_software_component_restore_verified=True,files=len(results),raw_bytes=total,
        actual_sequential_scratch_peak_bytes=peak,actual_normal_reader_restore=results,
        complete_global_scope=False,current_baseline_accepted=False,schedule_enabled=False,OS_SSD_payload_bytes=0)
