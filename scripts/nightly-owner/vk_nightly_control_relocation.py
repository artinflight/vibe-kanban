"""Reversible SSD-cache retirement after B-copy and consumer acceptance.

An atomic small pointer replaces only a verified replica under an exclusive
kernel lease. It is intentionally not an SSHFS SQLite symlink. Legacy direct
SQLite callers fail closed on its header instead of creating a fresh empty DB.
Normal consumers use authenticated B references; optional legacy recall uses
admitted RAM only, full independent readback, Linux metadata then immutable SQL.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import sqlite3
import stat

from vk_nightly_file_version import fingerprint,attributes
from vk_nightly_sql_point import ram_path,restore_metadata

MAGIC=b'VK_NIGHTLY_B_CONTROL_POINTER_V1\n'


def retire_replica(result,*,allowed_root,B_root,index_name,consumer_proof,guard):
    source=Path(result['source']);root=Path(allowed_root)
    if (not source.is_absolute() or source.resolve()!=source or not source.is_relative_to(root)
            or root.resolve()!=root or not B_root.startswith('B:/vk-backups/')):
        raise ValueError('exact authorized owned index relocation scope required')
    proof=result['B_checkpoint']
    if (proof.get('sha256')!=result['sha256'] or proof.get('bytes')!=result['bytes']
            or proof.get('native_integrity')!='ok' or proof.get('independent_readback') is not True
            or proof.get('Linux_metadata')!=result['Linux_metadata']
            or consumer_proof.get('checkpoint_sha256')!=result['sha256']
            or consumer_proof.get('B_working_name')!=index_name or consumer_proof.get('B_root')!=B_root):
        raise ValueError('actual verified B checkpoint and accepted consumer binding required')
    guard();before=source.lstat()
    if (not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_uid!=os.getuid()
            or fingerprint(before)!=result['original_identity']):raise ValueError('original index identity changed; preserve')
    fd=os.open(source,os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_NOATIME)
    changed=[];prior=signal.getsignal(signal.SIGIO);signal.signal(signal.SIGIO,lambda *_:changed.append(True));leased=False
    temporary=source.with_name(source.name+'.B-pointer.new')
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        # Unlike a shared read lease, this refuses even an active reader.
        fcntl.fcntl(fd,fcntl.F_SETLEASE,fcntl.F_WRLCK);leased=True
        reference=dict(format='vk-nightly-B-control-reference-v1',source=str(source),B_root=B_root,
            index_name=index_name,checkpoint_sha256=result['sha256'],bytes=result['bytes'],
            original_Linux_metadata=result['Linux_metadata'],original_identity=result['original_identity'],
            native_B_checkpoint_independently_verified=True,
            restore_policy='B-native consumer; optional verified RAM recall only; never SQLite over SSHFS')
        raw=MAGIC+json.dumps(reference,sort_keys=True,separators=(',',':')).encode()+b'\n'
        if len(raw)>65536:raise ValueError('fixed-size location pointer exceeded')
        with temporary.open('xb') as f:
            os.chmod(temporary,0o400);f.write(raw);f.flush();os.fsync(f.fileno())
        guard()
        if (changed or fingerprint(os.fstat(fd))!=result['original_identity']
                or fingerprint(source.lstat())!=result['original_identity']
                or attributes(source)!=result['Linux_metadata']['xattrs']):
            raise ValueError('index reader/writer or metadata changed before adoption; preserve both')
        os.replace(temporary,source)
        directory=os.open(source.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(directory)
        finally:os.close(directory)
        return dict(reference,source_replica_retired=True,retired_allocated_bytes=before.st_blocks*512,
                    pointer_allocated_bytes=source.stat().st_blocks*512,pointer_sha256=hashlib.sha256(raw).hexdigest())
    finally:
        if leased:fcntl.fcntl(fd,fcntl.F_SETLEASE,fcntl.F_UNLCK)
        os.close(fd);signal.signal(signal.SIGIO,prior)


def reference(path,*,expected_sha256):
    path=Path(path)
    with path.open('rb') as f:raw=f.read(65537)
    if len(raw)>65536 or hashlib.sha256(raw).hexdigest()!=expected_sha256 or not raw.startswith(MAGIC):
        raise ValueError('authenticated B index pointer required')
    return json.loads(raw[len(MAGIC):])


def recall(client,reference,*,destination,guard):
    target=Path(destination);root=ram_path(target.parent)
    if target.resolve()!=target or not target.name.startswith('nightly-index-recall-'):
        raise ValueError('new admitted RAM-only index recall path required')
    guard();fs=os.statvfs(root)
    if fs.f_bavail*fs.f_frsize<reference['bytes']+1024**2:raise ValueError('actual RAM recall scratch unavailable')
    with target.open('xb') as out:
        count=client.readback(reference['checkpoint_sha256'],sink=out)
        out.flush();os.fsync(out.fileno())
    if count!=reference['bytes']:raise ValueError('B recall size differs; preserve partial')
    h=hashlib.sha256()
    with target.open('rb') as f:
        for block in iter(lambda:f.read(65536),b''):guard();h.update(block)
    if h.hexdigest()!=reference['checkpoint_sha256']:raise ValueError('independent RAM index recall hash differs')
    db=sqlite3.connect(target.as_uri()+'?mode=ro&immutable=1',uri=True)
    try:
        db.execute('pragma temp_store=MEMORY');db.execute('pragma cache_size=-8192');db.execute('pragma mmap_size=0')
        if db.execute('pragma integrity_check').fetchall()!=[('ok',)]:raise ValueError('recalled index integrity differs')
    finally:db.close()
    restore_metadata(target,reference['original_Linux_metadata']);guard()
    return target
