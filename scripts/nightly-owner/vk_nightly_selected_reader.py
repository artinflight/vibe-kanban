"""Finite version reads through the ordinary leased B content decoder.

The native parent authenticates exact rows from its held normal B index. This
child retains Linux provider leases and verifies full encoded and decoded EOF.
It never invents complete HeldRecoverySet validation or opens live source files.
"""
import base64
from contextlib import contextmanager,ExitStack
import hashlib
import json
import os
import sys
import time
import sqlite3

from vk_typed_recovery import LocalDependencies, HeldRecoverySet, checksum, digest, validate_member, fingerprint
from vk_nightly_current_map import decode_member

PROTOCOL = 1
MAX_FRAME = 1024 * 1024


def send(output, value):
    raw = json.dumps(value, separators=(',', ':'), allow_nan=False).encode() + b'\n'
    if len(raw) > MAX_FRAME:
        raise ValueError('bounded selected-recovery frame required')
    output.write(raw)
    output.flush()


def receive(source):
    raw = source.readline(MAX_FRAME + 1)
    if not raw or len(raw) > MAX_FRAME or not raw.endswith(b'\n'):
        raise ValueError('complete bounded selected-recovery frame required')
    return json.loads(raw)


def qualify(request, rows, dependencies):
    """Qualify only externally named versions, never a whole recovery set."""
    files = request['files']
    if not isinstance(files, list) or not 1 <= len(files) <= 128:
        raise ValueError('finite explicit selected-version request required')
    expected = {f['normal_namespace_name']: f for f in files}
    if len(expected) != len(files) or set(rows) != set(expected):
        raise ValueError('exact selected namespace required')
    for name, value in rows.items():
        row, point, wanted = value['member'], value['qualification'], expected[name]
        if (request['source_root'].lstrip('/') + '/' + wanted['relative'] != name
                or row.get('kind') != 'file'
                or any(row.get(k) != wanted[k] for k in ('sha256', 'bytes'))
                or any(row.get(k) != wanted['Linux_metadata'][k]
                       for k in ('uid', 'gid', 'mode', 'mtime_ns', 'xattrs'))
                or point.get('source') != '/' + name
                or point.get('state') != 'qualified-retained-body'
                or point.get('row') != row):
            raise ValueError('selected B version or Linux metadata differs')
        validate_member(name, row, lambda p: rows[p]['member'])
        segments = row.get('segments')
        if not isinstance(segments, list) or not 1 <= len(segments) <= 100000:
            raise ValueError('explicit bounded retained recipe required')
        if sum(s['bytes'] for s in segments) != row['bytes']:
            raise ValueError('selected recipe does not cover the full body')
        for segment in segments:
            if segment.get('layer') not in dependencies:
                raise ValueError('selected recipe references an undeclared provider')
            digest(segment['sha256'])
    return {name: value['member'] for name, value in rows.items()}


class SelectedFiles:
    """Selected-file handle, deliberately without a whole-set verified flag."""
    def __init__(self, provider, rows, check):
        self.provider, self.rows, self.check = provider, rows, check

    def blocks(self, name):
        self.check()
        row = self.rows[name]
        size, hashed = 0, hashlib.sha256()
        for segment in row['segments']:
            # Same normal raw/zlib/ZIP decoder; never forge .verified to call
            # HeldRecoverySet.blocks on an unvalidated complete namespace.
            for block in HeldRecoverySet._segment(self, segment):
                self.check()
                size += len(block)
                if size > row['bytes']:
                    raise ValueError('selected body exceeds its exact version')
                hashed.update(block)
                yield block
        if size != row['bytes'] or hashed.hexdigest() != row['sha256']:
            raise ValueError('selected whole-body hash or length differs')
        self.check()


@contextmanager
def held(packet, guard):
    if checksum(packet['request']) != packet['request_sha256']:
        raise ValueError('authenticated selected request differs')
    placement = packet['provider_placement']
    if os.getuid() == 0 or (os.getuid(), os.getgid()) != (
            placement['expected_uid'], placement['expected_gid']):
        raise ValueError('existing unprivileged normal B reader required')
    dependencies = packet['dependencies']
    if set(placement['roots']) != set(dependencies):
        raise ValueError('exact selected provider scope required')
    provider = LocalDependencies(placement['roots'], dependencies,
        admission_check=guard, lease_paths=placement['lease_paths'],
        expected_root_bindings=placement['root_bindings'])
    with ExitStack() as stack:
        stack.enter_context(provider.held())
        from vk_nightly_checkpoint_members import Dependencies
        provider=Dependencies(provider);stack.callback(provider.close)
        ref = packet['index_reference']
        if type(ref['bytes']) is not int or not 0 < ref['bytes'] <= 2*1024**2:
            raise ValueError('bounded independently accepted selected index required')
        with provider.open(ref['layer'], ref['selector']) as stream:
            before = fingerprint(os.fstat(stream.fileno()))
            hashed = hashlib.sha256()
            for block in iter(lambda: stream.read(65536), b''):
                provider.check();hashed.update(block)
            if before[2] != ref['bytes'] or hashed.hexdigest() != ref['sha256']:
                raise ValueError('independently reopened selected index differs')
            db = sqlite3.connect('file:/proc/self/fd/'+str(stream.fileno())+'?mode=ro&immutable=1', uri=True)
            try:
                db.execute('pragma query_only=on');db.execute('pragma cache_size=-1024')
                if db.execute('select format,request_sha256 from selected_recovery_request').fetchall() != [
                        ('vk-nightly-selected-original-versions-v1', packet['request_sha256'])]:
                    raise ValueError('selected index request provenance differs')
                frozen = {name:decode_member(raw) for name,raw in db.execute('select name,row from selected_recovery_members')}
                if checksum(frozen) != checksum(packet['rows']):
                    raise ValueError('native and normal Linux selected index records differ')
                rows = qualify(packet['request'], frozen, dependencies)
                def check():
                    provider.check()
                    if fingerprint(os.fstat(stream.fileno())) != before:
                        raise ValueError('selected index changed during held recovery')
                handle = SelectedFiles(provider, rows, check)
                check();yield handle;check()
            finally:db.close()


def serve(packet, source, output, guard):
    with held(packet, guard) as handle:
        send(output, dict(ready=True, protocol=PROTOCOL, packet_sha256=checksum(packet)))
        while True:
            query = receive(source)
            if query == {'op': 'check'}:
                handle.check()
                send(output, dict(checked=True))
            elif query == {'op': 'close'}:
                handle.check()
                send(output, dict(closed=True))
                return
            elif set(query) == {'op', 'name', 'sha256'} and query['op'] == 'read':
                name = query['name']
                row = handle.rows[name]
                if row['sha256'] != digest(query['sha256']):
                    raise ValueError('selected body request version differs')
                send(output, dict(opened=True, name=name, bytes=row['bytes'], sha256=row['sha256']))
                for block in handle.blocks(name):
                    send(output, dict(data=base64.b64encode(block).decode()))
                send(output, dict(eof=True, bytes=row['bytes'], sha256=row['sha256']))
            else:
                raise ValueError('fixed selected-recovery operation required')


def main():
    packet = receive(sys.stdin.buffer)
    if checksum(packet) != sys.argv[1]:
        raise ValueError('independently pinned selected packet differs')
    def guard():
        if packet['deadline_epoch'] is not None and time.time() >= packet['deadline_epoch']:
            raise TimeoutError('finite selected recall ended; preserve all originals')
        with open('/proc/meminfo') as source:
            m = {r.split(':')[0]: int(r.split()[1])*1024 for r in source}
        if (m['MemAvailable'] < packet['memory_floor_bytes']
                or m['SwapFree'] < packet['swap_floor_bytes']):
            raise OSError('normal selected-reader memory admission unavailable')
    serve(packet, sys.stdin.buffer, sys.stdout.buffer, guard)


if __name__ == '__main__':
    main()
