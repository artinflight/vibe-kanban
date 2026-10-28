"""Qualify exact existing SQLite images for unchanged, cold current sources.

This is qualification, not raw-main-file backup. A normal read-only SQLite API
transaction owns the read point; any WAL/SHM/journal presence refuses this fast
path. Exact complete source bytes must match an already independently accepted
consistent image. Otherwise use the ordinary bounded direct-to-B backup API.
No immutable flag is used on a live source and no source PRAGMA is changed.
"""
import datetime
import hashlib
import os
from pathlib import Path
import sqlite3
import stat
import time

from vk_nightly_file_version import fingerprint,attributes
from vk_nightly_checkpoints import digest


def qualify_cold_image(source,image,*,allowed_sources,guard,maximum_bytes,timeout_seconds):
    path=Path(source)
    if (str(path) not in allowed_sources or not path.is_absolute() or path.resolve()!=path
            or type(maximum_bytes) is not int or maximum_bytes<1
            or type(timeout_seconds) not in (int,float) or timeout_seconds<=0):
        raise ValueError('explicit finite consistent-SQL qualification required')
    digest(image['sha256']);proof=image['proof']
    for independent in (proof['native'],proof['Linux_reopen']):
        if (independent.get('sha256')!=image['sha256'] or independent.get('bytes')!=image['bytes']
                or independent.get('integrity')!='ok'):
            raise ValueError('two accepted identical SQL image/integrity proofs required')
    def sidecar():
        return next((str(path)+s for s in ('-wal','-shm','-journal') if os.path.lexists(str(path)+s)),None)
    guard();before=path.lstat();started=time.monotonic()
    result=dict(source=str(path),retained_image_sha256=image['sha256'],retained_image_bytes=image['bytes'],
                reusable=False,source_payload_bytes_hashed=0,new_backup_payload_bytes=0,
                source_observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                current_baseline_accepted=False,original_image_epoch_preserved=True)
    if not stat.S_ISREG(before.st_mode):raise ValueError('consistent-SQL source must be regular')
    if before.st_size>maximum_bytes:return dict(result,reason='source exceeds bounded cold qualification; use backup API')
    found=sidecar()
    if found:return dict(result,reason='live SQLite sidecar requires backup API',sidecar=found)
    attrs=attributes(path);connection=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,isolation_level=None,timeout=1)
    try:
        connection.execute('BEGIN');connection.execute('SELECT name FROM sqlite_master LIMIT 1').fetchone()
        found=sidecar()
        if found:return dict(result,reason='sidecar appeared at SQL read point; use backup API',sidecar=found)
        size=connection.execute('PRAGMA page_count').fetchone()[0]*connection.execute('PRAGMA page_size').fetchone()[0]
        if size!=before.st_size or fingerprint(path.lstat())!=fingerprint(before):
            return dict(result,reason='SQL read point/main identity changed; use backup API')
        checksum=hashlib.sha256();total=0
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
        with os.fdopen(fd,'rb',buffering=0) as stream:
            if fingerprint(os.fstat(stream.fileno()))!=fingerprint(before):raise ValueError('SQL source changed before hash')
            while block:=stream.read(65536):
                guard()
                if time.monotonic()-started>timeout_seconds:raise TimeoutError('finite cold SQL read point expired')
                total+=len(block)
                if total>maximum_bytes or total>before.st_size:raise ValueError('SQL source grew during cold qualification')
                checksum.update(block)
            if (fingerprint(os.fstat(stream.fileno()))!=fingerprint(before)
                    or fingerprint(path.lstat())!=fingerprint(before) or attributes(path)!=attrs or sidecar()):
                raise ValueError('SQL source/read point changed; retain existing image and use backup API')
        guard()
        result.update(source_payload_bytes_hashed=total,source_sha256=checksum.hexdigest(),
                      source_identity=fingerprint(before),source_metadata=dict(mode=stat.S_IMODE(before.st_mode),
                          uid=before.st_uid,gid=before.st_gid,mtime_ns=before.st_mtime_ns,xattrs=attrs),
                      read_point='normal SQLite API transaction with no sidecars and unchanged complete main file',
                      elapsed_seconds=time.monotonic()-started)
        if total!=image['bytes'] or checksum.hexdigest()!=image['sha256']:
            return dict(result,reason='current consistent bytes differ from retained image; use backup API')
        return dict(result,reusable=True,reason='exact current consistent image reuses accepted native/independent bytes')
    finally:
        if connection.in_transaction:connection.rollback()
        connection.close()
