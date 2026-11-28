"""Reuse converter-owned immutable B graphs without recapture or re-deduplication.

The caller pins this source, contract SHA and the converter SDK, and supplies
its already-held normal B recovery context. No transport, lease acquisition,
source walk, object write, schedule mutation or local fallback is provided here.
"""
from collections import OrderedDict
from contextlib import contextmanager
import hashlib
import json
import os
import stat
from pathlib import PurePosixPath
import re
import zlib

MAGIC=b'VKLOGCAS1\n'
MAX_MANIFEST=16*1024**2
MAX_CHUNK=256*1024
MAX_CHUNKS=100000
UUID=r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}'
MEMBER=re.compile(rf'[0-9a-f]{{2}}/{UUID}/processes/(?:{UUID}\.(?:jsonl|capture\.json|recovered-final\.json)|\.log-objects/[0-9a-f]{{64}}\.gz)')
NOTE='Export is a dependency contract, not a Desktop B recovery receipt.'


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def checksum(value):return hashlib.sha256(canonical(value)).hexdigest()
def digest(value):
    if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{64}',value):raise ValueError('exact SHA256 required')
    return value

def member_name(value):
    if not isinstance(value,str) or not MEMBER.fullmatch(value) or value[:2]!=value.split('/')[1][:2]:
        raise ValueError('exact session-local history member required')
    return value


def prepare(operation,plan,original_request,records,result,*,archive_root):
    """Metadata-only adoption of one completed converter batch; not acceptance.

    Reconstruct the original graph exactly from retained checkpoint metadata.
    Missing retired staging is expected. Every byte will later come from B.
    """
    root=PurePosixPath(archive_root)
    if not root.is_absolute() or str(root)!=archive_root or '..' in root.parts or str(root)=='/':
        raise ValueError('exact archive namespace required')
    if (not re.fullmatch('[0-9a-f]{32}',operation) or not 1<=len(plan['files'])<=64
            or result.get('complete') is not True or result.get('normal_B_original_and_graph_verified') is not True
            or result.get('files')!=len(plan['files']) or not records):
        raise ValueError('completed exact converter batch required')
    originals={};logical={};members={};checkpoints=[]
    source=plan['source_root'].rstrip('/')
    if not source.startswith('/') or '..' in PurePosixPath(source).parts:raise ValueError('exact source root required')
    for row in original_request['files']:
        name=member_name(row['relative']);digest(row['sha256'])
        if name in originals or row['normal_namespace_name']!=source[1:]+'/'+name:
            raise ValueError('original namespace/uniqueness differs')
        originals[name]=row
    expected=set()
    for row in plan['files']:
        name=member_name(row['path']);digest(row['sha256'])
        if name in logical or name not in originals or any(originals[name][k]!=v for k,v in [('sha256',row['sha256']),('bytes',row['raw_bytes'])]):
            raise ValueError('original plan/request differs')
        logical[name]={'sha256':row['sha256'],'bytes':row['raw_bytes']};expected.add(name)
        for side in row['sidecars']:
            key=member_name(str(PurePosixPath(name).with_suffix('.'+side['extension'])))
            if key not in originals or originals[key]['sha256']!=side['sha256']:raise ValueError('required sidecar missing')
            expected.add(key)
    if set(originals)!=expected:raise ValueError('original request scope differs')
    for record in records:
        if record.get('format')!='vk-packed-archive-graph-v1':raise ValueError('supported immutable packed graph required')
        point=record['checkpoint'];ref=point['index_reference'];digest(ref['sha256'])
        if (ref['layer']!='nightly-controls-v1' or ref['selector']!=ref['sha256']+'.sqlite'
                or point['manifest_sha256']!=checksum(point['manifest'])):
            raise ValueError('immutable checkpoint binding differs')
        checkpoints.append(dict(ref))
        for row in record['members']['files']:
            name=member_name(row['path']);digest(row['sha256'])
            if name in members or type(row['bytes']) is not int or row['bytes']<0:raise ValueError('duplicate/invalid graph member')
            kind='object' if '/.log-objects/' in name else 'manifest' if name.endswith('.jsonl') else 'sidecar'
            members[name]={'path':name,'sha256':row['sha256'],'bytes':row['bytes'],'kind':kind}
    if {n for n,r in members.items() if r['kind']!='object'}!=expected:
        raise ValueError('graph omits/adds selected manifests or sidecars')
    graph=dict(version=1,root=archive_root,members=sorted(members.values(),key=lambda r:r['path']),
               logical_originals=logical,physical_members=len(members),physical_bytes=sum(r['bytes'] for r in members.values()),
               independent_backup_verified=False,note=NOTE)
    graph_sha=checksum(graph)
    if any(r['graph_sha256']!=graph_sha for r in records):raise ValueError('reconstructed graph SHA differs')
    return dict(format='vk-nightly-converter-reuse-v1',operation=operation,source_root=source,
                graph=graph,records=records,originals=originals,checkpoints=checkpoints,
                converter_result_sha256=checksum(result),prepared_only=True)


class LogicalReader:
    """Bounded streaming reconstruction over actual normal-B physical members."""
    def __init__(self,provider,graph,originals,*,cache_bytes=4*1024**2):
        if type(cache_bytes) is not int or not 0<=cache_bytes<=4*1024**2:raise ValueError('bounded B-derived cache required')
        self.provider=provider;self.members={r['path']:r for r in graph['members']}
        self.originals=originals;self.cache=OrderedDict();self.cache_bytes=cache_bytes;self.cached=0
    def read_member(self,name,limit):
        row=self.members[name]
        if row['bytes']>limit:raise ValueError('physical history member exceeds bound')
        self.provider.check()
        with self.provider.open_member(name,row['sha256']) as stream:
            data=bytearray()
            while True:
                block=stream.read(min(1024**2,limit-len(data)+1))
                if not block:break
                data.extend(block)
                if len(data)>limit:raise ValueError('physical history member exceeds bound')
        if len(data)!=row['bytes'] or hashlib.sha256(data).hexdigest()!=row['sha256']:
            raise ValueError('physical history hash/length differs')
        return bytes(data)
    def blocks(self,name):
        member_name(name);expected=self.originals[name]
        if not name.endswith('.jsonl'):
            row=self.members[name]
            if row['kind']!='sidecar' or any(row[k]!=expected[k] for k in ('sha256','bytes')):
                raise ValueError('original sidecar binding differs')
            self.provider.check();h=hashlib.sha256();total=0
            with self.provider.open_member(name,row['sha256']) as stream:
                while True:
                    self.provider.check();body=stream.read(1024**2)
                    if not body:break
                    total+=len(body)
                    if total>row['bytes']:raise ValueError('sidecar length exceeded')
                    h.update(body);yield body
            self.provider.check()
            if total!=row['bytes'] or h.hexdigest()!=row['sha256']:raise ValueError('sidecar EOF differs')
            return
        raw=self.read_member(name,MAX_MANIFEST+len(MAGIC))
        if not raw.startswith(MAGIC):raise ValueError('new historical backup requires converted manifest')
        manifest=json.loads(raw[len(MAGIC):])
        if (set(manifest)!={'version','raw_bytes','sha256','chunks'} or manifest['version']!=1
                or type(manifest['raw_bytes']) is not int or manifest['raw_bytes']!=expected['bytes']
                or manifest['sha256']!=expected['sha256'] or not isinstance(manifest['chunks'],list)
                or len(manifest['chunks'])>MAX_CHUNKS):raise ValueError('logical manifest differs from original')
        h=hashlib.sha256();total=0
        for chunk in manifest['chunks']:
            if (set(chunk)!={'bytes','sha256'} or type(chunk['bytes']) is not int
                    or not 0<chunk['bytes']<=MAX_CHUNK):raise ValueError('bounded logical chunk required')
            digest(chunk['sha256']);key=str(PurePosixPath(name).parent/'.log-objects'/(chunk['sha256']+'.gz'))
            self.provider.check()
            if key not in self.members or self.members[key]['kind']!='object':raise ValueError('missing shared object dependency')
            if key in self.cache:
                body=self.cache.pop(key);self.cache[key]=body
            else:
                compressed=self.read_member(key,MAX_CHUNK+1024);decoder=zlib.decompressobj(31)
                body=decoder.decompress(compressed,chunk['bytes']+1)
                if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:raise ValueError('invalid bounded gzip object')
                if len(body)<=self.cache_bytes:
                    while self.cached+len(body)>self.cache_bytes:
                        _,old=self.cache.popitem(last=False);self.cached-=len(old)
                    self.cache[key]=body;self.cached+=len(body)
            if len(body)!=chunk['bytes'] or hashlib.sha256(body).hexdigest()!=chunk['sha256']:raise ValueError('decoded object hash/length differs')
            total+=len(body)
            if total>manifest['raw_bytes']:raise ValueError('logical history exceeds original length')
            h.update(body)
            yield body
        self.provider.check()
        if total!=expected['bytes'] or h.hexdigest()!=expected['sha256']:raise ValueError('logical original EOF differs')
    def restore(self,name,sink):
        for body in self.blocks(name):
            view=memoryview(body)
            while view:
                self.provider.check();n=sink.write(view)
                if type(n) is not int or not 0<n<=len(view):raise OSError('logical restore short write')
                view=view[n:]
        expected=self.originals[name]
        return dict(relative=name,bytes=expected['bytes'],sha256=expected['sha256'],Linux_metadata=expected['Linux_metadata'],
                    original_byte_stream_verified=True,metadata_restored=False)


class OriginalHandle:
    """Ordinary restore_sample-compatible original-byte view of a held B graph.

    This is a component handle, not a forged whole-set HeldRecoverySet. Normal
    restore_sample performs separate-inode/readback/Linux-metadata acceptance.
    """
    def __init__(self,reader,source_root):
        self.reader=reader;self.prefix=source_root.lstrip('/')+'/'
        self.index=self;self.descriptor={'SQLite':{}}
    def relative(self,name):
        if not name.startswith(self.prefix):raise ValueError('original outside exact source root')
        relative=member_name(name[len(self.prefix):])
        if relative not in self.reader.originals:raise ValueError('selected original or sidecar required')
        return relative
    def entry(self,name):
        self.check();r=self.reader.originals[self.relative(name)]
        return dict(kind='file',bytes=r['bytes'],sha256=r['sha256'],**r['Linux_metadata'])
    def blocks(self,name):yield from self.reader.blocks(self.relative(name))
    def check(self):self.reader.provider.check()



@contextmanager
def open_reused(recovery,contract,expected_sha256,*,packed,hook,normal,scratch,graph_verifier,record=lambda _:None):
    """Executable bridge to the existing independently reopened NORMAL B path.

    packed/hook/verifier are from the caller's authenticated installed SDK, never
    imported from a path selected by this contract. They retain real B controls.
    """
    if checksum(contract)!=digest(expected_sha256) or contract.get('format')!='vk-nightly-converter-reuse-v1':
        raise ValueError('pinned converter reuse contract differs')
    if not recovery.location.startswith('desktop:B:/vk-backups/'):raise ValueError('canonical held B context required')
    recovery.check()
    with packed.reopen_graph(recovery,contract['graph'],contract['records'],hook=hook,normal=normal,scratch=scratch) as provider:
        proof=graph_verifier(contract['graph'],provider,recovery.check)
        if proof.get('independent_backup_verified') is not True:raise ValueError('complete normal-B graph proof required')
        record(dict(phase='converter-graph-independently-reopened',physical_members=proof['physical_members']))
        yield LogicalReader(provider,contract['graph'],contract['originals'])
        recovery.check()


def verify_component(reader,contract,expected_sha256,*,scratch_parent,
                     maximum_scratch_bytes,maximum_readback_bytes,guard,report=lambda _:None):
    """Serial independent original/sidecar restore through the ordinary helper.

    Called inside open_reused, after full physical graph verification. Admission
    covers the largest logical original, not all original files simultaneously.
    Failed outputs survive; a caller must reconcile them before retry. This
    receipt qualifies only this exact component, never whole-current acceptance.
    """
    from vk_nightly_composed_restore import restore_sample
    from vk_nightly_sql_point import ram_path
    if checksum(contract)!=digest(expected_sha256) or reader.originals!=contract['originals']:
        raise ValueError('pinned component scope differs')
    rows=contract['originals']
    if not rows or any(type(r['bytes']) is not int or r['bytes']<0 for r in rows.values()):
        raise ValueError('finite complete component scope required')
    total=sum(r['bytes'] for r in rows.values());peak=max(r['bytes'] for r in rows.values())
    overhead=16*1024**2
    if (any(type(n) is not int or n<=0 for n in (maximum_scratch_bytes,maximum_readback_bytes))
            or peak+overhead>maximum_scratch_bytes or total>maximum_readback_bytes):
        raise ValueError('component exceeds admitted serial restore demand')
    folder=ram_path(scratch_parent);info=folder.lstat();identity=(info.st_dev,info.st_ino)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)&0o077:
        raise ValueError('private owned RAM restore directory required')
    handle=OriginalHandle(reader,contract['source_root'])
    def check():
        guard();handle.check();now=folder.lstat()
        if (now.st_dev,now.st_ino)!=identity or folder.resolve()!=folder:
            raise ValueError('component restore directory replaced')
    receipts=[]
    for name in sorted(rows):
        check();fs=os.statvfs(folder)
        if fs.f_bavail*fs.f_frsize<rows[name]['bytes']+overhead:
            raise OSError('actual component RAM restore capacity unavailable')
        receipt=restore_sample(handle,contract['source_root']+'/'+name,folder,guard=check)
        receipts.append(receipt)
        report(dict(phase='converter-original-independent-restore',completed=len(receipts),total=len(rows),receipt=receipt))
    check()
    return dict(format='vk-nightly-converted-component-restore-v1',contract_sha256=expected_sha256,
                operation=contract['operation'],checkpoints=contract['checkpoints'],
                original_versions=receipts,verified_bytes=total,serial_scratch_peak_bytes=peak,
                physical_dependencies_independently_reopened=True,component_restore_verified=True,
                whole_current_set_accepted=False,schedule_enabled=False,new_backup_payload_bytes=0)


def typed_entries(contract,expected_sha256):
    """Ordinary one-segment member rows; no expanded per-log chunk recipes.

    These are immutable converter-epoch physical versions. A current map may
    adopt them only after its usual current-version qualification; it must keep
    all unmatched/new/pending versions pending, never drop them from scope.
    """
    if checksum(contract)!=digest(expected_sha256):raise ValueError('pinned graph contract differs')
    layer='converted-graph-'+expected_sha256
    members={r['path']:r for r in contract['graph']['members']};seen=set()
    for record in contract['records']:
        for packed in record['members']['files']:
            name=member_name(packed['path']);r=members[name]
            if name in seen or any(packed[k]!=r[k] for k in ('bytes','sha256')):
                raise ValueError('physical member binding differs')
            seen.add(name)
            metadata={k:packed['metadata'][k] for k in ('mode','uid','gid','mtime_ns','xattrs')}
            yield contract['source_root'].lstrip('/')+'/'+name,dict(metadata,kind='file',bytes=r['bytes'],
                sha256=r['sha256'],segments=[dict(layer=layer,selector=name,bytes=r['bytes'],sha256=r['sha256'])])
    if seen!=set(members):raise ValueError('physical dependency scope incomplete')


class TypedGraphDependencies:
    """Add an already-reopened converter graph to ordinary typed dependencies.

    Existing base/index and normal-B graph leases stay held by the caller. The
    authenticated descriptor/consumer contract must include these identities.
    HeldRecoverySet.validate remains mandatory; this never sets handle.verified.
    """
    def __init__(self,base,reader,contract,expected_sha256):
        if checksum(contract)!=digest(expected_sha256) or reader.members!={r['path']:r for r in contract['graph']['members']}:
            raise ValueError('held graph differs from pinned contract')
        self.base=base;self.reader=reader;self.layer='converted-graph-'+expected_sha256
        self.admission_check=self.check
        if self.layer in base.identities:raise ValueError('duplicate component dependency')
        self.identities=dict(base.identities)
        self.identities[self.layer]=dict(format='vk-nightly-converter-reuse-v1',contract_sha256=expected_sha256,
            graph_sha256=checksum(contract['graph']),checkpoints=contract['checkpoints'])
        self.check()
    def check(self):
        self.base.check();self.reader.provider.check()
    @contextmanager
    def open(self,layer,selector):
        self.check()
        if layer==self.layer:
            name=member_name(selector);row=self.reader.members[name]
            with self.reader.provider.open_member(name,row['sha256']) as stream:yield stream
        else:
            with self.base.open(layer,selector) as stream:yield stream
        self.check()


class ConvertedCarriers:
    """Existing CurrentMap qualification's carriers(sha,bytes) interface.

    Construct only inside open_reused's independently verified graph context.
    Scope is one bounded converter batch. It supplies recipes, not source
    qualification: the existing current-epoch identity/journal checks remain.
    Publish the resulting metadata catalog on B for whole-backlog lookup; do
    not accumulate all batch dictionaries or create a growing SSD index.
    """
    def __init__(self,reader,contract,expected_sha256):
        if reader.members!={r['path']:r for r in contract['graph']['members']}:
            raise ValueError('current carrier graph differs')
        self.reader=reader;self.rows={}
        for _,row in typed_entries(contract,expected_sha256):
            self.rows.setdefault((row['sha256'],row['bytes']),row)
    def __call__(self,sha256,size):
        digest(sha256)
        if type(size) is not int or size<0:raise ValueError('exact current-version length required')
        self.reader.provider.check()
        row=self.rows.get((sha256,size))
        if row is not None:yield json.loads(canonical(row))
        self.reader.provider.check()


def checkpoint_imports(contract,expected_sha256):
    """Small pinned descriptors for the actual B-resident worker import path."""
    if checksum(contract)!=digest(expected_sha256):raise ValueError('pinned converter contract differs')
    for record in contract['records']:
        ref=record['checkpoint']['index_reference'];member=record['members']['files'][0]
        yield dict(source_root=contract['source_root'],reference=dict(encoding='control-tar-v1',
            layer='nightly-controls-v1',selector=ref['selector'],checkpoint_sha256=ref['sha256'],checkpoint_bytes=ref['bytes'],
            control_manifest_sha256=record['checkpoint']['manifest_sha256'],carrier_source=record['carrier_source'],
            manifest_source=record['manifest_source'],member_source=member['path'],bytes=member['bytes'],sha256=member['sha256']))


def checkpoint_batches(contracts,*,maximum_bytes=128*1024):
    """Stream final converter references into bounded existing worker configs.

    Each item is (contract, pinned_sha256). Reuse the SAME B index/seed between
    batches: native imports are atomic/idempotent and accumulated on B. No
    source body walk, backlog conversion, or all-catalog local dictionary.
    """
    if type(maximum_bytes) is not int or not 2048<=maximum_bytes<=128*1024:
        raise ValueError('bounded checkpoint metadata batch required')
    batch=[];size=2
    for contract,pinned in contracts:
        for reference in checkpoint_imports(contract,pinned):
            length=len(json.dumps(reference,separators=(',',':')).encode())+1
            if length+2>maximum_bytes:raise ValueError('single checkpoint reference exceeds metadata bound')
            if batch and (size+length>maximum_bytes or len(batch)==128):
                yield batch;batch=[];size=2
            batch.append(reference);size+=length
    if batch:yield batch
