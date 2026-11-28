"""Executable normal leased consumer of an authenticated complete current set.

The installed controller supplies the packet digest, actual provider placements,
existing leases and finite remaining resource/time admission. A descriptor may
not select its own consumer requirements or commands. Only selected readbacks
are materialized, sequentially in private tmpfs; all original providers remain
read-only. No capture, index copy, calendar or acceptance-pointer write occurs.
"""
from contextlib import ExitStack
import argparse
from datetime import datetime
import json
import io
import hashlib
import base64
import zlib
import math
import os
from pathlib import Path
import stat
import sys
import tempfile
import time

from vk_nightly_composed_restore import verify
from vk_nightly_sql_point import ram_path
from vk_typed_recovery import HeldRecoverySet,LocalDependencies,held_index,checksum,digest


MAX_PACKET=2*1024**2
MAX_DECODED_PACKET=16*1024**2
WIRE_FORMAT='vk-nightly-compressed-consumer-packet-v1'
STREAM_FORMAT='vk-nightly-framed-consumer-packet-v1'
PACKET_PART=32768


def encode_packet(packet):
    raw=json.dumps(packet,separators=(',',':'),sort_keys=True,allow_nan=False).encode()+b'\n'
    if len(raw)>MAX_DECODED_PACKET:raise ValueError('bounded decoded consumer packet required')
    if len(raw)<=MAX_PACKET:return raw
    value=dict(format=WIRE_FORMAT,bytes=len(raw),sha256=checksum(packet),
        data=base64.b64encode(zlib.compress(raw,6)).decode())
    wire=json.dumps(value,separators=(',',':')).encode()+b'\n'
    if len(wire)<=MAX_PACKET:return wire
    packed=zlib.compress(raw,6)
    if len(packed)>MAX_DECODED_PACKET:raise ValueError('bounded compressed consumer stream required')
    header=dict(format=STREAM_FORMAT,bytes=len(raw),sha256=checksum(packet),
        compressed_sha256=hashlib.sha256(packed).hexdigest(),compressed_bytes=len(packed),
        parts=(len(packed)+PACKET_PART-1)//PACKET_PART)
    frames=[json.dumps(header,separators=(',',':')).encode()+b'\n']
    for number,start in enumerate(range(0,len(packed),PACKET_PART)):
        frames.append(json.dumps(dict(part=number,data=base64.b64encode(packed[start:start+PACKET_PART]).decode()),
            separators=(',',':')).encode()+b'\n')
    return b''.join(frames)


def read_packet(stream):
    raw=stream.readline(MAX_PACKET+1)
    if len(raw)>MAX_PACKET or not raw.endswith(b'\n'):raise ValueError('bounded complete consumer packet required')
    value=json.loads(raw)
    if value.get('format')==STREAM_FORMAT:
        if (set(value)!={'format','bytes','sha256','compressed_sha256','compressed_bytes','parts'}
                or any(type(value[k]) is not int or not 0<value[k]<=MAX_DECODED_PACKET for k in ('bytes','compressed_bytes'))
                or type(value['parts']) is not int or value['parts']!=(value['compressed_bytes']+PACKET_PART-1)//PACKET_PART):
            raise ValueError('bounded complete consumer stream descriptor required')
        digest(value['compressed_sha256']);packed=bytearray()
        for number in range(value['parts']):
            line=stream.readline(65537)
            if len(line)>65536 or not line.endswith(b'\n'):raise ValueError('complete bounded consumer data frame required')
            frame=json.loads(line)
            if set(frame)!={'part','data'} or type(frame['part']) is not int or frame['part']!=number:
                raise ValueError('ordered complete consumer data frames required')
            data=base64.b64decode(frame['data'],validate=True)
            if len(data)!=min(PACKET_PART,value['compressed_bytes']-len(packed)):
                raise ValueError('consumer data frame length differs')
            packed.extend(data)
        if hashlib.sha256(packed).hexdigest()!=value['compressed_sha256']:
            raise ValueError('consumer compressed stream hash differs')
    elif value.get('format')==WIRE_FORMAT:
        if (set(value)!={'format','bytes','sha256','data'} or type(value['bytes']) is not int
                or not 0<value['bytes']<=MAX_DECODED_PACKET):raise ValueError('bounded compressed consumer descriptor required')
        packed=base64.b64decode(value['data'],validate=True)
    else:
        if stream.read(1):raise ValueError('trailing consumer wire bytes')
        return value
    digest(value['sha256']);decoder=zlib.decompressobj();decoded=decoder.decompress(packed,value['bytes']+1)
    if (len(decoded)!=value['bytes'] or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail):
        raise ValueError('consumer full decoded length differs')
    packet=json.loads(decoded)
    if checksum(packet)!=value['sha256']:raise ValueError('consumer full decoded hash differs')
    if stream.read(1):raise ValueError('trailing consumer wire bytes')
    return packet


def decode_packet(raw):return read_packet(io.BytesIO(raw))


def validation_arguments(contract,descriptor):
    """Derive external requirements from the pinned owner contract, not the map."""
    if (contract.get('format')!='vk-nightly-current-recovery-contract-v1'
            or descriptor.get('installed_consumer_contract_sha256')!=checksum(contract)
            or descriptor.get('dependencies')!=contract.get('dependencies')):
        raise ValueError('independently pinned installed consumer contract differs')
    if not set(contract.get('always_SQL_API_sources',[]))<=set(descriptor.get('always_SQL_API_sources',[])):
        raise ValueError('externally required always-API SQL source omitted')
    request=contract.get('current_SQL_request');qualification=None
    if request is not None:
        if checksum({k:v for k,v in request.items() if k!='cohort_id'})!=digest(request['cohort_id']):
            raise ValueError('independently pinned SQL cohort request differs')
        qualification=dict(format='vk-nightly-current-SQL-qualification-v1',cohort_id=request['cohort_id'],
            selected_sources=sorted(request['sources']),
            unchanged_sources=sorted(set(request['SQL_scope_sources'])-set(request['sources'])),
            always_SQL_API_sources=sorted(request['always_SQL_API_sources']),
            source_instance=request['binding']['source_instance'])
    return dict(plan_sha256=contract['plan_sha256'],scope_sha256=contract['scope_sha256'],
        required_sources=contract['sources'],original_sources=contract['original_sources'],
        required_pins=contract['required_pins'],required_SQL=contract['required_SQL'],
        required_root_aliases=contract.get('root_aliases',{}),
        required_runtime_files=contract.get('always_runtime_files',{}),
        required_SQL_qualification=qualification,
        required_retired_original_sources=contract.get('retired_original_sources',{}))


def run(packet,expected_sha256,*,guard,report=lambda _:None,clock=time.monotonic,wall_clock=time.time):
    """Use the real reader through all leases; caller retains native B admission."""
    if packet.get('format')=='vk-nightly-owner-controls-consumer-v1':
        from vk_nightly_owner_controls import run as restore_owner_controls
        return restore_owner_controls(packet,expected_sha256,guard=guard,report=report)
    if packet.get('format')=='vk-nightly-finite-software-consumer-v1':
        from vk_nightly_component_restore import run as restore_component
        return restore_component(packet,expected_sha256,guard=guard,report=report)
    # Reject root unconditionally; independently retain the exact admitted
    # UID/GID equality check below. This never elevates or changes identity.
    if os.getuid()==0:
        raise ValueError('root execution prohibited; existing unprivileged consumer required')
    if checksum(packet)!=digest(expected_sha256):raise ValueError('authenticated composed-consumer packet differs')
    packet=json.loads(json.dumps(packet))
    if packet.get('format')!='vk-nightly-composed-consumer-packet-v1':raise ValueError('fixed consumer packet required')
    descriptor=packet['descriptor'];contract=packet['consumer_contract']
    if (checksum(descriptor)!=digest(packet['descriptor_sha256'])
            or checksum(contract)!=digest(packet['consumer_contract_sha256'])):
        raise ValueError('external descriptor/consumer contract digest differs')
    args=validation_arguments(contract,descriptor)
    placement=packet['provider_placement'];roots=placement['roots'];bindings=placement['root_bindings']
    if (set(roots)!=set(contract['dependencies']) or set(roots)!=set(bindings)
            or set(roots)!=set(placement['lease_paths'])
            or os.getuid()!=placement['expected_uid'] or os.getgid()!=placement['expected_gid']):
        raise ValueError('actual admitted provider placement/owner differs')
    timeout=packet['remaining_seconds']
    if type(timeout) not in (int,float) or not math.isfinite(timeout) or timeout<=0:
        raise ValueError('finite remaining whole-cycle consumer time required')
    deadline=datetime.fromisoformat(packet['whole_cycle_deadline_UTC'])
    if deadline.tzinfo is None:raise ValueError('aware original whole-cycle deadline required')
    deadline_epoch=deadline.timestamp();timeout=min(timeout,deadline_epoch-wall_clock())
    if timeout<=0:raise TimeoutError('original whole-cycle deadline already expired; no readback started')
    started=clock()
    physical_roots={(path,tuple(bindings[name])) for name,path in roots.items()}
    def check():
        guard()
        if clock()-started>=timeout or wall_clock()>=deadline_epoch:
            raise TimeoutError('whole-cycle consumer time expired; preserve original set and failed readback')
    def placement_check():
        check()
        for path,expected in physical_roots:
            p=Path(path);info=p.lstat()
            if (not p.is_absolute() or p.resolve()!=p or not stat.S_ISDIR(info.st_mode)
                    or (info.st_dev,info.st_ino)!=expected):
                raise ValueError('independently admitted dependency placement changed: '+path)
    placement_check()
    scratch_parent=ram_path(packet['scratch_parent']);fs=os.statvfs(scratch_parent)
    budget=packet['maximum_scratch_bytes']
    if type(budget) is not int or budget<=0 or fs.f_bavail*fs.f_frsize<budget:
        raise ValueError('actual admitted consumer RAM scratch unavailable')
    provider=LocalDependencies(roots,contract['dependencies'],admission_check=check,lease_paths=placement['lease_paths'],
                               expected_root_bindings=bindings)
    # The private directory is the only new state. Its failed payloads survive
    # any exception. Existing lease files and provider/index paths are untouched.
    scratch=Path(tempfile.mkdtemp(prefix='nightly-composed-consumer-',dir=scratch_parent))
    scratch_id=(scratch.stat().st_dev,scratch.stat().st_ino)
    try:
        with ExitStack() as stack:
            stack.enter_context(provider.held())
            from vk_nightly_checkpoint_members import Dependencies
            provider=Dependencies(provider);stack.callback(provider.close)
            index=stack.enter_context(held_index(provider,*descriptor['indexes']))
            handle=HeldRecoverySet(descriptor,packet['descriptor_sha256'],provider,index)
            result=verify(handle,validation_arguments=args,content_proof=packet['content_proof'],
                expected_content_proof_sha256=packet['content_proof_sha256'],expected_catalogs=packet['expected_catalogs'],
                readback_sources=packet['readback_sources'],scratch_parent=scratch,
                required_deduplicated_roots=packet['consumer_contract'].get('deduplicated_roots',()),
                workspace_archive=packet['consumer_contract'].get('workspace_archive'),
                maximum_scratch_bytes=budget,maximum_readback_bytes=packet['maximum_readback_bytes'],
                guard=check,local_guard=check,report=report,memory_floor_bytes=packet['Linux_resource_admission']['memory_floor_bytes'])
            check();handle.check()
        check();info=scratch.lstat()
        if (info.st_dev,info.st_ino)!=scratch_id:raise ValueError('owned consumer scratch directory changed; preserve')
        scratch.rmdir() # Only this newly created, successfully verified empty RAM directory.
        placement_check()
        return dict(result,consumer_packet_sha256=expected_sha256,consumer_contract_sha256=packet['consumer_contract_sha256'],
            normal_leased_consumer_entrypoint_verified=True,elapsed_seconds=clock()-started,
            native_B_admission_required_from_controller=True,production_B_placement_claimed_by_this_entrypoint=False,
            new_OS_SSD_payload_bytes=0)
    except BaseException as error:
        error.nightly_composed_consumer_preserved_scratch=str(scratch)
        if hasattr(error,'add_note'):error.add_note('Consumer scratch preserved: '+str(scratch))
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet-sha256',required=True);args=parser.parse_args()
    packet=read_packet(sys.stdin.buffer);admission=packet['Linux_resource_admission']
    for name in ('memory_floor_bytes','swap_floor_bytes'):
        if type(admission[name]) is not int or admission[name]<0:raise ValueError('explicit actual Linux resource admission required')
    def guard():
        values={row.split(':')[0]:int(row.split()[1])*1024 for row in Path('/proc/meminfo').read_text().splitlines()}
        if values['MemAvailable']<admission['memory_floor_bytes'] or values['SwapFree']<admission['swap_floor_bytes']:
            raise OSError('actual consumer memory/swap headroom unavailable; retain all recovery')
    def report(value):print(json.dumps(dict(value,event='composed-consumer-progress')),flush=True)
    result=run(packet,args.packet_sha256,guard=guard,report=report)
    print(json.dumps(dict(event='composed-consumer-result',result=result)),flush=True)
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,KeyError,TimeoutError) as error:
        print(json.dumps(dict(event='composed-consumer-failed',type=type(error).__name__,reason=str(error),
            preserved_scratch=getattr(error,'nightly_composed_consumer_preserved_scratch',None),
            preserved_readback=getattr(error,'nightly_composed_restore_preserved_path',None))),file=sys.stderr,flush=True)
        raise SystemExit(1)
