"""Move a closed index's authority to B, with a preserved immutable checkpoint.

This creates and verifies B copies only. SSD replica retirement is a separate
explicit adoption step, after consumers and the independent readback pass.
All partial objects/checkpoints stay recoverable. At most one object-sized RAM
buffer and its independent restore are needed; no growing SSD temporary file.
"""
import fcntl
import hashlib
import os
from pathlib import Path
import signal
import stat

from vk_b_disk_snapshot import metadata
from vk_nightly_file_version import fingerprint,attributes


def migrate_checkpoint(source,objects,controls,*,guard,on_progress=lambda _:None,chunk_bytes=16*1024**2):
    path=Path(source)
    if not path.is_absolute() or path.resolve()!=path:raise ValueError('canonical owned source index required')
    before=path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_uid!=os.getuid() or before.st_nlink!=1:
        raise ValueError('owned unique regular source index required')
    if type(chunk_bytes) is not int or not 0<chunk_bytes<=objects.maximum:raise ValueError('finite control chunk required')
    guard();fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_NOATIME)
    changed=[];prior=signal.getsignal(signal.SIGIO)
    signal.signal(signal.SIGIO,lambda *_:changed.append(True));leased=False
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if fingerprint(os.fstat(fd))!=fingerprint(before):raise ValueError('source changed before index lease')
        fcntl.fcntl(fd,fcntl.F_SETLEASE,fcntl.F_RDLCK);leased=True
        original=metadata(path)
        for suffix in ('-wal','-shm','-journal'):
            if Path(str(path)+suffix).exists():raise ValueError('live SQLite sidecar; API checkpoint required instead')
        def unchanged():
            guard()
            if (changed or fingerprint(path.lstat())!=fingerprint(before)
                    or fingerprint(os.fstat(fd))!=fingerprint(before) or attributes(path)!=original['xattrs']):
                raise ValueError('source index/lease changed; preserve all copies')
        uploaded_before=objects.payload_bytes_sent
        h=hashlib.sha256();segments=[];total=0
        with os.fdopen(os.dup(fd),'rb') as stream:
            while True:
                unchanged();block=stream.read(chunk_bytes)
                if not block:break
                h.update(block);total+=len(block);segments.append(objects.ensure(block))
                on_progress(dict(phase='index-chunks-direct-B-and-independent-RAM-readback',source=str(path),
                                 source_bytes=total,expected_bytes=before.st_size,chunks=len(segments)))
        unchanged()
        if total!=before.st_size:raise ValueError('source checkpoint size changed')
        digest=h.hexdigest()
        result=controls.call(op='import',sha256=digest,bytes=total,segments=segments,Linux_metadata=original)
        if result['status']=='already_verified':receipt=result['receipt']
        elif result['status']=='needs_independent_readback':
            if controls.readback(digest)!=total:raise ValueError('independent index byte count differs')
            receipt=controls.call(op='acknowledge',sha256=digest,independent_stream_sha256=digest,Linux_metadata=original)
        else:raise ValueError('native index import did not reach a verified checkpoint')
        unchanged()
        return dict(source=str(path),original_identity=fingerprint(before),Linux_metadata=original,bytes=total,
            sha256=digest,B_checkpoint=receipt,SSD_replica_retired=False,body_or_source_recaptured=False,
            segments=segments,new_B_encoded_chunk_bytes=objects.payload_bytes_sent-uploaded_before)
    finally:
        if leased:fcntl.fcntl(fd,fcntl.F_SETLEASE,fcntl.F_UNLCK)
        os.close(fd);signal.signal(signal.SIGIO,prior)
