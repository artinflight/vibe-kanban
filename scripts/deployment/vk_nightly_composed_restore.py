"""Independent ordinary-reader acceptance of a complete composed recovery set.

Run inside the existing admitted B-backed Linux consumer, with authenticated
provider/index leases held. Exact earlier body/SQLite proofs are reused through
the native immutable-map content audit. Required runtime and always-API samples
are actually materialized, reopened, hashed and metadata/SQLite checked, one at
a time in admitted tmpfs. Never a global source scan or a new baseline copy.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import tempfile

from vk_nightly_control_format import key
from vk_nightly_file_version import attributes,fingerprint,stream_hash
from vk_nightly_sql_point import ram_path,release_verified_ram
from vk_typed_recovery import checksum,digest


def restore_sample(handle,path,folder,*,guard):
    """Preserve any failed output; release only this successfully proved copy."""
    name=key(path.removeprefix('/'));row=handle.index.entry(name)
    fd,temporary=tempfile.mkstemp(prefix='nightly-composed-readback-',dir=folder);target=Path(temporary)
    try:
        with os.fdopen(fd,'wb') as sink:
            original=os.fstat(sink.fileno())
            if not stat.S_ISREG(original.st_mode) or original.st_nlink!=1:raise ValueError('independent private restore inode required')
            for block in handle.blocks(name):
                guard();view=memoryview(block)
                while view:
                    count=sink.write(view)
                    if type(count) is not int or not 0<count<=len(view):raise OSError('independent restore short write')
                    view=view[count:]
            sink.flush();os.fsync(sink.fileno())
        guard()
        with target.open('rb') as source:
            before=fingerprint(os.fstat(source.fileno()));actual=stream_hash(source)
            if (before!=fingerprint(os.fstat(source.fileno())) or before[:2]!=[original.st_dev,original.st_ino]
                    or before[2:4]!=[stat.S_IFREG|0o600,row['bytes']] or actual!=row['sha256']):
                raise ValueError('independent composed restore inode/length/hash differs')
        SQL=None
        if path in handle.descriptor['SQLite']:
            expected=handle.descriptor['SQLite'][path];digest(expected['schema_sha256'])
            with sqlite3.connect(target.as_uri()+'?mode=ro&immutable=1',uri=True) as db:
                db.execute('pragma temp_store=MEMORY');db.execute('pragma cache_size=-8192');db.execute('pragma mmap_size=0')
                def progress():guard();return 0
                db.set_progress_handler(progress,1000)
                if db.execute('pragma integrity_check').fetchall()!=[('ok',)]:raise ValueError('composed restored SQLite integrity failed')
                schema=db.execute('select type,name,tbl_name,sql from sqlite_master order by type,name,tbl_name,sql').fetchall()
                SQL=hashlib.sha256(json.dumps(schema,separators=(',',':')).encode()).hexdigest()
                if SQL!=expected['schema_sha256']:raise ValueError('composed restored SQLite schema differs')
            db.close()
        # All content reads precede final timestamp restoration. No source
        # inode or provider body is chowned/chmodded; only this new RAM file.
        info=target.lstat()
        if (info.st_dev,info.st_ino)!=(original.st_dev,original.st_ino):raise ValueError('restore output replaced before metadata')
        if (info.st_uid,info.st_gid)!=(row['uid'],row['gid']):os.chown(target,row['uid'],row['gid'],follow_symlinks=False)
        for field,value in row['xattrs'].items():os.setxattr(target,field,base64.b64decode(value,validate=True),follow_symlinks=False)
        os.chmod(target,row['mode'],follow_symlinks=False);os.utime(target,ns=(row['mtime_ns'],row['mtime_ns']),follow_symlinks=False)
        info=target.lstat();end=fingerprint(info)
        if ((info.st_dev,info.st_ino)!=(original.st_dev,original.st_ino)
                or (info.st_uid,info.st_gid,stat.S_IMODE(info.st_mode),info.st_mtime_ns)!=(row['uid'],row['gid'],row['mode'],row['mtime_ns'])
                or attributes(target)!=row['xattrs']):raise ValueError('composed restored Linux metadata differs')
        guard();handle.check();release_verified_ram(target,end)
        return dict(source=path,bytes=row['bytes'],sha256=actual,Linux_metadata_verified=True,
                    SQLite_integrity='ok' if SQL is not None else None,schema_sha256=SQL,
                    separate_restored_inode=[original.st_dev,original.st_ino],verified_RAM_duplicate_released=True)
    except BaseException as error:
        error.nightly_composed_restore_preserved_path=str(target)
        if hasattr(error,'add_note'):error.add_note('Unverified independent restore retained: '+str(target))
        raise


def verify(handle,*,validation_arguments,content_proof,expected_content_proof_sha256,
           expected_catalogs,readback_sources,scratch_parent,maximum_scratch_bytes,
           maximum_readback_bytes,guard,report=lambda _:None):
    """The caller pins the actual native audit, catalogs and consumer contract.

    Success covers the complete selected namespace/proof closure plus actual
    normal-reader integration samples. It does not assert original completeness,
    a host writer fence, live cutover or schedule installation.
    """
    if checksum(content_proof)!=digest(expected_content_proof_sha256):raise ValueError('authenticated native content proof differs')
    metadata=handle.validate(**validation_arguments);descriptor=handle.descriptor
    ref=descriptor['indexes'][0];actual=content_proof.get('map_reference',{})
    if (content_proof.get('format')!='vk-nightly-independent-composed-content-proof-v1'
            or any(actual.get(k)!=ref[k] for k in ('sha256','selector','bytes'))
            or content_proof.get('file_points')!=metadata['regular_file_count']
            or content_proof.get('file_raw_bytes')!=metadata['regular_file_bytes']
            or content_proof.get('SQL_acceptance_records_independently_decoded')!=len(validation_arguments['required_SQL'])
            or content_proof.get('base_catalog_reference')!=expected_catalogs['base']
            or content_proof.get('recipe_catalog_references')!=expected_catalogs['recipes']):
        raise ValueError('complete native proof/map/SQL/catalog closure differs')
    for field in ('file_proof_chain_sha256','segment_proof_chain_sha256'):digest(content_proof[field])
    if (not isinstance(readback_sources,list) or not 1<=len(readback_sources)<=256
            or len(readback_sources)!=len(set(readback_sources))
            or any(not isinstance(p,str) or p!='/'+key(p.removeprefix('/')) for p in readback_sources)):
        raise ValueError('finite explicit normal-reader restore selection required')
    mandatory=(set(validation_arguments['required_pins'])|set(validation_arguments.get('required_runtime_files',{}))
               |set(handle.always_SQL_API_sources))
    if not mandatory<=set(readback_sources):raise ValueError('runtime/always-API restore requirements cannot be omitted')
    if any(type(n) is not int or n<1 for n in (maximum_scratch_bytes,maximum_readback_bytes)):
        raise ValueError('finite measured restore scratch/readback admission required')
    rows=[handle.index.entry(p[1:]) for p in readback_sources]
    if any(r['kind'] not in ('file','hardlink') for r in rows):raise ValueError('selected restore must have normal regular content')
    total=sum(r['bytes'] for r in rows);peak=max(r['bytes'] for r in rows)
    if peak+16*1024**2>maximum_scratch_bytes or total>maximum_readback_bytes:
        raise ValueError('actual composed restore demand exceeds admitted RAM/readback window')
    folder=ram_path(scratch_parent);info=folder.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)&0o077:
        raise ValueError('existing private owned RAM restore directory required')
    root_identity=(info.st_dev,info.st_ino)
    def check():
        guard();handle.check();now=folder.lstat()
        if (now.st_dev,now.st_ino)!=root_identity or folder.resolve()!=folder:raise ValueError('RAM restore directory replaced')
        fs=os.statvfs(folder)
        if fs.f_bavail*fs.f_frsize<peak+16*1024**2:raise OSError('actual RAM restore capacity unavailable; preserve all proof/data')
    receipts=[]
    for path in readback_sources:
        check()
        receipts.append(restore_sample(handle,path,folder,guard=lambda:(guard(),handle.check())))
        report(dict(phase='normal-composed-restore-readback',completed=len(receipts),selected=len(rows),
                    verified_bytes=sum(r['bytes'] for r in receipts),last_source=path))
    check()
    return dict(format='vk-nightly-independent-composed-restore-v1',descriptor_sha256=handle.expected_sha256,
        metadata=metadata,content_proof_sha256=expected_content_proof_sha256,
        complete_file_points_verified=metadata['regular_file_count'],complete_logical_file_bytes=metadata['regular_file_bytes'],
        accepted_prior_body_and_SQL_proofs_reused=True,actual_normal_reader_restore=receipts,
        actual_selected_restore_bytes=total,actual_sequential_scratch_peak_bytes=peak,
        admitted_scratch_bytes=maximum_scratch_bytes,independent_composed_restore_verified=True,
        original_epoch_complete=False,writer_fence_verified=False,schedule_enabled=False,OS_SSD_payload_bytes=0)
