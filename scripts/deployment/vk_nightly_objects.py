"""Finite direct-to-B, content-addressed objects with interrupted-readback reuse.

The installed controller supplies the existing authenticated Desktop process,
store lease, native B health/STOP/capacity guard and source admission. No source
commands or paths come from a recovery manifest. Payload lives only on B or in
bounded RAM. A candidate survives interruption; completed accepted objects are
never recopied. No retention, deletion, scheduler or baseline publication here.
"""
import hashlib
from contextlib import contextmanager
import json
import os
from pathlib import Path
import stat
import struct
import tempfile
import zlib
import re

BLOCK=65536
MAX_CONTROL=65536


def control(stream, value):
    raw=json.dumps(value,sort_keys=True,separators=(',', ':'),allow_nan=False).encode()+b'\n'
    if len(raw)>MAX_CONTROL:raise ValueError('object control bound exceeded')
    stream.write(raw);stream.flush()


def read_control(stream):
    raw=stream.readline(MAX_CONTROL+1)
    if not raw:return None
    if len(raw)>MAX_CONTROL or not raw.endswith(b'\n'):raise ValueError('incomplete object control')
    return json.loads(raw)


def exact(stream, size):
    result=bytearray()
    while len(result)<size:
        block=stream.read(size-len(result))
        if not block:raise EOFError('object stream interrupted; candidate/partials retained')
        result.extend(block)
    return bytes(result)


def fingerprint(info, fd=None):
    value=[info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns]
    if os.name=='nt':
        # Windows st_ctime is creation time. Bind actual NTFS ChangeTime too,
        # so a same-size rewrite followed by mtime restoration cannot reuse an
        # old receipt merely because its creation timestamp stayed unchanged.
        import ctypes
        import msvcrt
        if fd is None:raise ValueError('opened native file change-time required')
        class BasicInfo(ctypes.Structure):
            _fields_=[('CreationTime',ctypes.c_int64),('LastAccessTime',ctypes.c_int64),
                      ('LastWriteTime',ctypes.c_int64),('ChangeTime',ctypes.c_int64),
                      ('FileAttributes',ctypes.c_uint32)]
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        query=kernel.GetFileInformationByHandleEx
        query.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p,ctypes.c_uint32]
        query.restype=ctypes.c_int
        basic=BasicInfo()
        if not query(msvcrt.get_osfhandle(fd),0,ctypes.byref(basic),ctypes.sizeof(basic)):
            raise ctypes.WinError(ctypes.get_last_error())
        value.append(basic.ChangeTime)
    return value


def file_identity(path):
    before=regular(path)
    with Path(path).open('rb') as stream:
        info=os.fstat(stream.fileno())
        if (info.st_dev,info.st_ino)!=(before.st_dev,before.st_ino):raise ValueError('object path changed')
        return fingerprint(info,stream.fileno())


def write_new(path,value):
    with Path(path).open('x',encoding='utf-8') as out:
        json.dump(value,out,sort_keys=True);out.write('\n');out.flush();os.fsync(out.fileno())


def object_paths(root, sha):
    if not isinstance(sha,str) or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):
        raise ValueError('exact content SHA256 required')
    return root/(sha+'.zlib'),root/(sha+'.candidate.json'),root/(sha+'.accepted.json')


def regular(path):
    info=Path(path).lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink!=1
            or getattr(info,'st_file_attributes',0)&0x400):
        raise ValueError('unique regular non-reparse store file required')
    return info


@contextmanager
def store_lease(root):
    path=root/'OBJECT_STORE.lease'
    fd=os.open(path,os.O_RDWR|os.O_CREAT|getattr(os,'O_NOFOLLOW',0),0o600)
    try:
        regular(path)
        if os.name=='nt':
            import msvcrt
            if os.fstat(fd).st_size==0:os.write(fd,b'\0')
            os.lseek(fd,0,os.SEEK_SET);msvcrt.locking(fd,msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield
    finally:os.close(fd)


def decoded(path, *, expected_size, expected_sha, encoded_sha=None, guard=lambda:None):
    """Independent bounded disk reopen/decode; no full-object allocation."""
    decoder=zlib.decompressobj();raw_hash=hashlib.sha256();encoded_hash=hashlib.sha256();count=0
    with Path(path).open('rb') as source:
        before=os.fstat(source.fileno());before_identity=fingerprint(before,source.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1:raise ValueError('unique regular object required')
        for block in iter(lambda:source.read(BLOCK),b''):
            guard();encoded_hash.update(block);pending=block
            while pending:
                value=decoder.decompress(pending,BLOCK);pending=decoder.unconsumed_tail
                count+=len(value)
                if count>expected_size or decoder.unused_data:raise ValueError('decoded object exceeds exact point')
                raw_hash.update(value)
                if value:yield value
        if fingerprint(os.fstat(source.fileno()),source.fileno())!=before_identity:raise ValueError('object changed during independent readback')
    if (count!=expected_size or raw_hash.hexdigest()!=expected_sha or not decoder.eof
            or encoded_sha is not None and encoded_hash.hexdigest()!=encoded_sha):
        raise ValueError('independent object decode/hash mismatch')


def receive(root, source, output, *, guard, maximum_object_bytes,retained_SQL_root=None):
    """Called only inside the controller's lifetime native B/store lease.

    guard(required_bytes) authenticates B, actual controls and capacity. Tests
    supply an isolated RAM directory and synthetic guard, never a live route.
    Existing immutable candidates need only readback; accepted receipts permit
    identity-bound reuse. Corrupt/missing sidecars never become a new overwrite.
    """
    root=Path(root)
    if not root.is_absolute() or root.resolve()!=root or not root.is_dir():raise ValueError('authenticated existing object directory required')
    if type(maximum_object_bytes) is not int or maximum_object_bytes<1:raise ValueError('finite object bound required')
    guard(1024**2)
    with store_lease(root):
        return _receive(root,source,output,guard=guard,maximum_object_bytes=maximum_object_bytes,retained_SQL_root=retained_SQL_root)


def retained_SQL_probe(path,expected,*,allowed_root,expected_sha256,guard):
    path=Path(path);base=Path(allowed_root)
    if (not base.is_absolute() or base.resolve()!=base or not path.is_relative_to(base)
            or path.resolve()!=path or not re.fullmatch('sqlite-consistent-[0-9a-f]{32}\\.sqlite',path.name)):
        raise ValueError('exact retained B SQL image path required')
    for parent in (path,*path.parents):
        info=parent.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:
            raise ValueError('retained SQL path crosses a reparse point')
    with path.open('rb') as stream:
        info=os.fstat(stream.fileno());before=fingerprint(info,stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or [info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns]!=expected):
            raise ValueError('retained native SQL image identity differs')
        h=hashlib.sha256()
        for block in iter(lambda:stream.read(BLOCK),b''):guard(0);h.update(block)
        if (h.hexdigest()!=expected_sha256 or fingerprint(os.fstat(stream.fileno()),stream.fileno())!=before
                or [path.stat().st_dev,path.stat().st_ino]!=expected[:2]):
            raise ValueError('retained SQL image content/identity changed')
    return dict(status='retained_SQL_verified',sha256=h.hexdigest(),bytes=info.st_size,identity=before)


def _receive(root,source,output,*,guard,maximum_object_bytes,retained_SQL_root=None):
    while True:
        query=read_control(source)
        if query is None:return
        if query.get('operation')=='health':
            guard(0);control(output,dict(status='health_passed'));continue
        if query.get('operation')=='probe-retained-SQL':
            if retained_SQL_root is None:raise ValueError('retained SQL provider not configured')
            receipt=retained_SQL_probe(query['path'],query['identity'],allowed_root=retained_SQL_root,
                expected_sha256=query['sha256'],guard=guard)
            control(output,receipt);continue
        sha=query.get('sha256');size=query.get('bytes');final,candidate,accepted=object_paths(root,sha)
        operation=query.get('operation','ensure')
        if operation not in ('ensure','verify'):raise ValueError('unknown object operation')
        if type(size) is not int or not 0<=size<=maximum_object_bytes:raise ValueError('object outside admitted RAM/byte bound')
        guard(size+1024**2)
        already_accepted=False
        if accepted.exists():
            regular(accepted)
            with accepted.open('rb') as f:raw=f.read(MAX_CONTROL+1)
            if len(raw)>MAX_CONTROL:raise ValueError('accepted object receipt excessive')
            receipt=json.loads(raw);info=regular(final)
            if (receipt.get('raw_sha256')!=sha or receipt.get('raw_bytes')!=size
                    or receipt.get('independent_RAM_reopened_hash_verified') is not True
                    or not stat.S_ISREG(info.st_mode) or info.st_nlink!=1
                    or file_identity(final)!=receipt.get('identity')):
                raise ValueError('accepted object/identity changed; preserve and reconcile')
            if operation=='ensure':
                control(output,dict(status='reused',receipt=receipt));continue
            already_accepted=True
        elif operation=='verify':
            raise ValueError('readback requires an already accepted object')
        elif candidate.exists():
            regular(candidate);regular(final)
            with candidate.open('rb') as f:raw=f.read(MAX_CONTROL+1)
            if len(raw)>MAX_CONTROL:raise ValueError('candidate receipt excessive')
            receipt=json.loads(raw)
            if receipt['raw_sha256']!=sha or receipt['raw_bytes']!=size or file_identity(final)!=receipt['identity']:
                raise ValueError('candidate point or identity differs')
        elif final.exists() or final.is_symlink():
            # Parent death between rename and candidate receipt must not force
            # a second completed body copy. Requalify these exact existing
            # bytes; a name/size alone never authenticates an orphan.
            info=regular(final)
            if info.st_size>size+1024**2:raise ValueError('unrecorded object exceeds exact encoding budget')
            before=file_identity(final);encoded_hash=hashlib.sha256()
            with final.open('rb') as stream:
                for block in iter(lambda:stream.read(BLOCK),b''):
                    guard(1024**2);encoded_hash.update(block)
            for _ in decoded(final,expected_size=size,expected_sha=sha,encoded_sha=encoded_hash.hexdigest(),
                             guard=lambda:guard(1024**2)):pass
            if file_identity(final)!=before:raise ValueError('unrecorded object changed during recovery')
            receipt=dict(raw_sha256=sha,raw_bytes=size,encoded_sha256=encoded_hash.hexdigest(),
                         encoded_bytes=info.st_size,identity=before,native_disk_decode_verified=True,
                         recovered_after_rename_before_receipt=True)
            write_new(candidate,receipt)
        else:
            partial=root/(sha+'.'+os.urandom(8).hex()+'.partial')
            control(output,dict(status='send'))
            encoded_hash=hashlib.sha256();encoded_bytes=0
            with partial.open('xb') as sink:
                while True:
                    length=struct.unpack('!I',exact(source,4))[0]
                    if length==0:break
                    if length>BLOCK:raise ValueError('bounded encoded object frame required')
                    block=exact(source,length);encoded_bytes+=length
                    if encoded_bytes>size+1024**2:raise ValueError('encoded object budget exceeded')
                    guard(size+1024**2-encoded_bytes);encoded_hash.update(block);sink.write(block)
                sink.flush();os.fsync(sink.fileno())
            for _ in decoded(partial,expected_size=size,expected_sha=sha,encoded_sha=encoded_hash.hexdigest(),guard=lambda:guard(1024**2)):pass
            # The lifetime store lease excludes other producers; Windows rename
            # also refuses an existing destination. No existing candidate/data
            # is overwritten or discarded, including failed stream partials.
            if final.exists() or final.is_symlink():raise ValueError('object collision')
            os.rename(partial,final)
            receipt=dict(raw_sha256=sha,raw_bytes=size,encoded_sha256=encoded_hash.hexdigest(),
                         encoded_bytes=encoded_bytes,identity=file_identity(final),native_disk_decode_verified=True)
            write_new(candidate,receipt)
        control(output,dict(status='readback',receipt=receipt))
        for block in decoded(final,expected_size=size,expected_sha=sha,encoded_sha=receipt['encoded_sha256'],guard=lambda:guard(1024**2)):
            output.write(block)
        output.flush()
        acknowledgement=read_control(source)
        if (acknowledgement!=dict(raw_sha256=sha,raw_bytes=size,independent_RAM_reopened_hash_verified=True)):
            raise ValueError('independent restore acknowledgement missing; candidate retained')
        guard(1024**2)
        receipt.update(independent_RAM_reopened_hash_verified=True)
        if not already_accepted:write_new(accepted,receipt)
        control(output,dict(status='accepted',receipt=receipt))


class ObjectClient:
    def __init__(self,source,output,*,guard,ram_root,maximum_object_bytes):
        self.source=source;self.output=output;self.guard=guard;self.ram_root=Path(ram_root)
        self.maximum=maximum_object_bytes
        self.payload_bytes_sent=0;self.native_receipts_reused=0;self.candidates_recovered=0
        if (not (self.ram_root==Path('/dev/shm') or self.ram_root.is_relative_to('/dev/shm'))
                or not any(s.split()[4]=='/dev/shm' and ' - tmpfs ' in s for s in Path('/proc/self/mountinfo').read_text().splitlines())):
            raise ValueError('actual admitted /dev/shm tmpfs restore required')

    def health(self):
        self.guard();control(self.output,dict(operation='health'));reply=read_control(self.source)
        if reply!=dict(status='health_passed'):raise ValueError('native real guard health reply unavailable')

    def probe_retained_SQL(self,image):
        self.guard();control(self.output,dict(operation='probe-retained-SQL',path=image['native_path'],
            identity=image['file_identity'],sha256=image['sha256']))
        reply=read_control(self.source)
        if (not reply or reply.get('status')!='retained_SQL_verified' or reply.get('sha256')!=image['sha256']
                or reply.get('bytes')!=image['bytes']):raise ValueError('retained SQL native proof differs')
        return reply

    def ensure(self,raw):
        if not isinstance(raw,bytes) or len(raw)>self.maximum:raise ValueError('bounded RAM object required')
        self.guard();sha=hashlib.sha256(raw).hexdigest();size=len(raw)
        fs=os.statvfs(self.ram_root)
        if fs.f_bavail*fs.f_frsize<size+1024**2:raise ValueError('actual RAM restore scratch unavailable')
        control(self.output,dict(sha256=sha,bytes=size));reply=read_control(self.source)
        if reply is None:raise EOFError('native object receiver ended')
        reused=reply['status']=='reused'
        if reused:self.native_receipts_reused+=1
        if reply['status']=='readback':self.candidates_recovered+=1
        if reply['status']=='send':
            encoder=zlib.compressobj(1)
            for start in range(0,size,BLOCK):
                self.guard();encoded=encoder.compress(raw[start:start+BLOCK])
                for offset in range(0,len(encoded),BLOCK):
                    part=encoded[offset:offset+BLOCK];self.output.write(struct.pack('!I',len(part))+part)
                    self.payload_bytes_sent+=len(part)
            encoded=encoder.flush()
            for offset in range(0,len(encoded),BLOCK):
                part=encoded[offset:offset+BLOCK];self.output.write(struct.pack('!I',len(part))+part)
                self.payload_bytes_sent+=len(part)
            self.output.write(struct.pack('!I',0));self.output.flush();reply=read_control(self.source)
        if not reused:
            if not reply or reply.get('status')!='readback':raise ValueError('native candidate readback unavailable')
            reply=self._restore(sha,size)
        receipt=reply['receipt']
        if (receipt.get('raw_sha256')!=sha or receipt.get('raw_bytes')!=size
                or receipt.get('independent_RAM_reopened_hash_verified') is not True):
            raise ValueError('native object receipt differs')
        return dict(layer='nightly-objects-v1',selector=sha+'.zlib',encoding='zlib',bytes=size,sha256=sha,
                    encoded_bytes=receipt['encoded_bytes'],encoded_sha256=receipt['encoded_sha256'],reused=reused)

    def _restore(self,sha,size,sink=None):
        # Independently allocate/reopen in verified tmpfs, one bounded chunk at
        # a time. Forward only fully hash-verified bytes to the file verifier.
        fd,path=tempfile.mkstemp(prefix='nightly-object-restore-',dir=self.ram_root)
        with os.fdopen(fd,'wb') as restored:
            left=size
            while left:
                self.guard();block=exact(self.source,min(left,BLOCK));restored.write(block);left-=len(block)
            restored.flush();os.fsync(restored.fileno())
        h=hashlib.sha256()
        with open(path,'rb') as restored:
            for block in iter(lambda:restored.read(BLOCK),b''):h.update(block)
            if h.hexdigest()!=sha:raise ValueError('independent RAM object hash mismatch')
            if sink is not None:
                restored.seek(0)
                for block in iter(lambda:restored.read(BLOCK),b''):
                    self.guard();view=memoryview(block)
                    while view:
                        written=sink.write(view)
                        if type(written) is not int or not 0<written<=len(view):raise OSError('verified restore sink short write')
                        view=view[written:]
        control(self.output,dict(raw_sha256=sha,raw_bytes=size,independent_RAM_reopened_hash_verified=True))
        reply=read_control(self.source)
        if not reply or reply.get('status')!='accepted':raise ValueError('independent object acceptance not persisted')
        os.unlink(path)  # only this freshly verified disposable RAM duplicate
        return reply

    def verify(self,segment,sink):
        """Compose file readback from accepted B chunks without body uploads."""
        sha=segment['sha256'];size=segment['bytes'];object_paths(Path('.'),sha)
        if (type(size) is not int or not 0<=size<=self.maximum
                or segment.get('selector')!=sha+'.zlib' or segment.get('encoding')!='zlib'):
            raise ValueError('exact admitted content object segment required')
        self.guard();fs=os.statvfs(self.ram_root)
        if fs.f_bavail*fs.f_frsize<size+1024**2:raise ValueError('actual RAM readback scratch unavailable')
        control(self.output,dict(operation='verify',sha256=sha,bytes=size));reply=read_control(self.source)
        if not reply or reply.get('status')!='readback':raise ValueError('accepted object readback unavailable')
        for field in ('encoded_bytes','encoded_sha256'):
            if reply['receipt'][field]!=segment[field]:raise ValueError('accepted encoded object binding differs')
        reply=self._restore(sha,size,sink)
        if reply['receipt']['raw_sha256']!=sha or reply['receipt']['raw_bytes']!=size:
            raise ValueError('verified object receipt differs')
        return size


class ChunkSink:
    """Bounded RAM chunker for the existing qualified-point source streamer."""
    def __init__(self,client,*,chunk_bytes):
        if type(chunk_bytes) is not int or not 0<chunk_bytes<=client.maximum:raise ValueError('admitted finite chunk size required')
        self.client=client;self.limit=chunk_bytes;self.buffer=bytearray();self.segments=[];self.raw_bytes=0

    def write(self,block):
        size=len(block);view=memoryview(block)
        while view:
            count=min(len(view),self.limit-len(self.buffer));self.buffer.extend(view[:count]);view=view[count:]
            if len(self.buffer)==self.limit:self._flush()
        self.raw_bytes+=size;return size

    def _flush(self):
        segment=self.client.ensure(bytes(self.buffer));segment.pop('reused',None)
        self.segments.append(segment);self.buffer.clear()

    def finish(self):
        if self.buffer or not self.segments:self._flush()
        return self.segments
