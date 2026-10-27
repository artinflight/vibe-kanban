"""Consistent SQLite API points, bounded RAM working image, durable bodies on B.

The API needs a random-access destination. Use an actually admitted tmpfs file,
never OS/work-SSD staging, then stream new content-addressed chunks to B. Exact
accepted images are probed/reused without copying them. A failed working image
is retained; only a newly verified duplicate is released after B acceptance.
"""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time

from vk_b_disk_snapshot import metadata
from vk_nightly_file_version import fingerprint,attributes,stream_hash
from vk_nightly_objects import ChunkSink
from vk_nightly_checkpoints import digest


INDEPENDENT_SQL_CHECK = r'''
import hashlib,json,pathlib,sqlite3,sys
p=pathlib.Path(sys.argv[1]);expected=sys.argv[2];h=hashlib.sha256()
with p.open('rb') as source:
 for block in iter(lambda:source.read(65536),b''):h.update(block)
assert h.hexdigest()==expected,'independent restored SQL bytes differ'
with sqlite3.connect(p.as_uri()+'?mode=ro&immutable=1',uri=True) as db:
 db.execute('pragma temp_store=MEMORY');db.execute('pragma cache_size=-8192');db.execute('pragma mmap_size=0')
 assert db.execute('pragma integrity_check').fetchall()==[('ok',)]
 schema=db.execute('select type,name,tbl_name,sql from sqlite_master order by type,name,tbl_name,sql').fetchall()
print(json.dumps(dict(bytes=p.stat().st_size,sha256=h.hexdigest(),integrity='ok',schema_sha256=hashlib.sha256(json.dumps(schema,separators=(',',':')).encode()).hexdigest())))
'''


def ram_path(root):
    root=Path(root)
    if (root.resolve()!=root or not (root==Path('/dev/shm') or root.is_relative_to('/dev/shm'))
            or not any(s.split()[4]=='/dev/shm' and ' - tmpfs ' in s for s in Path('/proc/self/mountinfo').read_text().splitlines())):
        raise ValueError('actual admitted RAM-only SQLite working image required')
    return root


def restore_metadata(path,expected):
    # Hash/integrity probes precede restoring timestamps, including atime.
    os.chown(path,expected['uid'],expected['gid']);os.chmod(path,expected['mode'])
    for name,value in expected['xattrs'].items():os.setxattr(path,name,base64.b64decode(value))
    os.utime(path,ns=(expected['atime_ns'],expected['mtime_ns']))
    info=path.stat()
    if ((info.st_uid,info.st_gid,stat.S_IMODE(info.st_mode),info.st_atime_ns,info.st_mtime_ns)!=
            (expected['uid'],expected['gid'],expected['mode'],expected['atime_ns'],expected['mtime_ns'])
            or attributes(path)!=expected['xattrs']):raise ValueError('restored SQL Linux metadata differs')


def release_verified_ram(path,expected_identity):
    path=Path(path);info=path.lstat()
    if (path.resolve()!=path or not stat.S_ISREG(info.st_mode) or info.st_nlink!=1
            or info.st_uid!=os.getuid() or fingerprint(info)!=expected_identity):
        raise ValueError('owned verified RAM duplicate identity changed; preserve')
    path.unlink()


def capture_SQL_point(source,client,*,allowed_sources,guard,retained_by_sha,ram_root,
                      maximum_image_bytes,chunk_bytes,timeout_seconds,on_prepared=lambda _:None,resume=None,
                      resume_layout=None,cohort_id=None):
    """retained_by_sha returns only authenticated independent SQL image pairs.

    All image/chunk receipts remain distinct from final baseline/namespace
    acceptance. No WAL/main-file shortcut or source journal mode change occurs.
    """
    if cohort_id is not None:digest(cohort_id)
    if resume is not None and cohort_id is not None and resume.get('SQL_cohort_id')!=cohort_id:
        raise ValueError('retained SQL API point belongs to another qualification cohort')
    path=Path(source);root=ram_path(ram_root)
    if (str(path) not in allowed_sources or not path.is_absolute() or path.resolve()!=path
            or type(maximum_image_bytes) is not int or maximum_image_bytes<1
            or type(timeout_seconds) not in (int,float) or timeout_seconds<=0):
        raise ValueError('explicit finite SQLite API point admission required')
    if resume_layout is not None:
        return recover_SQL_layout(path,client,resume,resume_layout,root=root,guard=guard,
            maximum_image_bytes=maximum_image_bytes,timeout_seconds=timeout_seconds,on_prepared=on_prepared,cohort_id=cohort_id)
    guard();before=path.lstat() if resume is None else None
    if before is not None and not stat.S_ISREG(before.st_mode):raise ValueError('regular API source required')
    source_meta=metadata(path) if resume is None else resume['source_metadata_before']
    started=time.monotonic();src=dst=None;working=None
    initial_upload=client.payload_bytes_sent
    last_health=0
    def check():
        nonlocal last_health
        guard()
        if time.monotonic()-started>timeout_seconds:raise TimeoutError('finite SQL point; working data retained')
        if time.monotonic()-last_health>5:client.health();last_health=time.monotonic()
    try:
        if resume is None:
            src=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=1)
            src.execute('pragma temp_store=MEMORY');src.execute('pragma cache_size=-8192');src.execute('pragma mmap_size=0')
            data_version=src.execute('pragma data_version').fetchone()[0]
            src.execute('BEGIN');src.execute('select name from sqlite_master limit 1').fetchone()
            pages=src.execute('pragma page_count').fetchone()[0];page_size=src.execute('pragma page_size').fetchone()[0]
            point_bytes=pages*page_size
            if point_bytes>maximum_image_bytes:
                return dict(source=str(path),status='larger_SQL_working_window_required',measured_image_bytes=point_bytes,
                            RAM_image_limit=maximum_image_bytes,new_B_payload_bytes=0,baseline_accepted=False)
            fs=os.statvfs(root)
            if fs.f_bavail*fs.f_frsize<2*point_bytes+client.maximum+16*1024**2:
                raise OSError('actual RAM API+independent-restore scratch unavailable')
            fd,temp=tempfile.mkstemp(prefix='nightly-sql-api-',suffix='.sqlite',dir=root)
            os.close(fd);working=Path(temp)
            dst=sqlite3.connect(working)
            dst.execute('pragma temp_store=MEMORY');dst.execute('pragma cache_size=-8192');dst.execute('pragma mmap_size=0')
            dst.execute('pragma journal_mode=OFF')  # only this newly created private RAM image
            def progress(status,remaining,total):
                check()
                if total*page_size>maximum_image_bytes:raise ValueError('API point grew beyond admitted RAM image')
            src.backup(dst,pages=1024,progress=progress);dst.close();dst=None
            src.rollback();changed=src.execute('pragma data_version').fetchone()[0]!=data_version
            src.close();src=None;check()
            after=path.lstat()
            if (not stat.S_ISREG(after.st_mode) or path.resolve()!=path
                    or (after.st_dev,after.st_ino,after.st_uid,after.st_gid,stat.S_IMODE(after.st_mode))!=
                       (before.st_dev,before.st_ino,before.st_uid,before.st_gid,stat.S_IMODE(before.st_mode))
                    or attributes(path)!=source_meta['xattrs']):
                raise ValueError('SQL source inode/metadata replaced during API capture; preserve working image')
            with working.open('rb') as image:
                os.fsync(image.fileno());working_identity=fingerprint(os.fstat(image.fileno()))
                sha=stream_hash(image);size=os.fstat(image.fileno()).st_size
                if fingerprint(os.fstat(image.fileno()))!=working_identity:raise ValueError('API working image changed during hash')
            # Probe the actual separately allocated API file before accepting any
            # old/new body. The second child below uses a different restored inode.
            probe=subprocess.run([sys.executable,'-B','-c',INDEPENDENT_SQL_CHECK,str(working),sha],
                                 capture_output=True,text=True,timeout=max(1,timeout_seconds-(time.monotonic()-started)))
            if probe.returncode:raise ValueError('API working-image integrity failed: '+probe.stderr[-2048:])
            initial=json.loads(probe.stdout)
            captured=dict(source=str(path),working_RAM_path=str(working),working_identity=working_identity,
                bytes=size,sha256=sha,API_capture_completed=True,initial_SQL_integrity=initial,
                source_metadata_before=source_meta,source_metadata_after=metadata(path),
                source_identity_before=fingerprint(before),source_changed_online=changed,
                original_source_API_point_at=time.time())
            if cohort_id is not None:captured['SQL_cohort_id']=cohort_id
            on_prepared(dict(captured_RAM_point=captured))
        else:
            if (resume.get('API_capture_completed') is not True or resume.get('source')!=str(path)
                    or resume.get('initial_SQL_integrity',{}).get('integrity')!='ok'):
                raise ValueError('positive retained API-completion marker required')
            working=Path(resume['working_RAM_path'])
            if (working.parent!=root or not working.name.startswith('nightly-sql-api-')
                    or working.resolve()!=working or working.is_symlink()):
                raise ValueError('exact original RAM API image required')
            info=working.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_uid!=os.getuid()
                    or [info.st_dev,info.st_ino]!=resume['working_identity'][:2] or info.st_size!=resume['bytes']):
                raise ValueError('retained RAM API point inode/size changed')
            working_identity=fingerprint(info)
            with working.open('rb') as image:
                sha=stream_hash(image);size=os.fstat(image.fileno()).st_size
                if sha!=resume['sha256'] or fingerprint(os.fstat(image.fileno()))!=working_identity:
                    raise ValueError('retained API point bytes changed; preserve and reconcile')
            initial=resume['initial_SQL_integrity'];changed=resume['source_changed_online'];captured=resume
        legacy=retained_by_sha(sha,size)
        if legacy is not None:
            for part in (legacy['proof']['native'],legacy['proof']['Linux_reopen']):
                if part.get('sha256')!=sha or part.get('bytes')!=size or part.get('integrity')!='ok':
                    raise ValueError('authenticated retained SQL proof differs')
            native=client.probe_retained_SQL(legacy)
            layer='retained-SQL-'+hashlib.sha256(legacy['native_path'].encode()).hexdigest()[:24]
            segments=[dict(layer=layer,selector=legacy['name'],bytes=size,sha256=sha)]
            independent=dict(initial,reused_accepted_independent_SQL_image=True,current_native_probe=native)
            dependency=dict(layer=layer,native_root=str(Path(legacy['native_path']).parent),legacy_image=legacy)
            manifest=None;uploaded=0
            restore_metadata(working,source_meta);working_identity=fingerprint(working.stat())
            independent['current_Linux_metadata_verified']=True
        else:
            uploaded_before=client.payload_bytes_sent;sink=ChunkSink(client,chunk_bytes=chunk_bytes)
            with working.open('rb') as image:
                for block in iter(lambda:image.read(65536),b''):check();sink.write(block)
            segments=sink.finish();data_uploaded=client.payload_bytes_sent-uploaded_before
            prepared=dict(source=str(path),bytes=size,sha256=sha,segments=segments,source_metadata=source_meta,
                method='SQLite-backup-API',independent_SQL_restore_accepted=False)
            if cohort_id is not None:prepared['SQL_cohort_id']=cohort_id
            manifest=client.ensure(json.dumps(prepared,sort_keys=True,separators=(',',':')).encode())
            on_prepared(dict(layout=prepared,manifest=manifest,working_RAM_path=str(working)))
            restore_fd,restore_path=tempfile.mkstemp(prefix='nightly-sql-independent-',suffix='.sqlite',dir=root)
            restored=Path(restore_path)
            with os.fdopen(restore_fd,'wb') as output:
                for segment in segments:check();client.verify(segment,output)
                output.flush();os.fsync(output.fileno())
            result=subprocess.run([sys.executable,'-B','-c',INDEPENDENT_SQL_CHECK,str(restored),sha],
                                  capture_output=True,text=True,timeout=max(1,timeout_seconds-(time.monotonic()-started)))
            if result.returncode:raise ValueError('independent B SQL restore failed: '+result.stderr[-2048:])
            independent=json.loads(result.stdout)
            if independent!=initial:raise ValueError('independent SQLite schema/content differs')
            restore_metadata(restored,source_meta)
            restored_identity=fingerprint(restored.stat())
            independent.update(separate_restored_inode=restored_identity[:2],independent_Linux_metadata_verified=True)
            uploaded=data_uploaded;dependency=None
        row=dict(kind='file',bytes=size,sha256=sha,segments=segments,
                 **{k:source_meta[k] for k in ('mode','uid','gid','mtime_ns','xattrs')})
        record=dict(source=str(path),status='consistent_SQL_point_verified',method='SQLite-backup-API',
            source_identity_before=captured['source_identity_before'],source_metadata_before=source_meta,
            source_metadata_after=captured['source_metadata_after'],source_changed_online=changed,
            original_source_API_point_at=captured['original_source_API_point_at'],resumed_retained_SQL_point=resume is not None,bytes=size,sha256=sha,
            member=row,independent=independent,dependency=dependency,prepared_manifest=manifest,
            new_B_encoded_payload_bytes=uploaded,source_API_image_bytes=size,baseline_accepted=False,
            source_API_point_qualifies_later_epoch_not_original=True)
        if cohort_id is not None:record['SQL_cohort_id']=cohort_id
        record['verified_RAM_duplicates']=[dict(path=str(working),identity=working_identity)]
        if legacy is None:record['verified_RAM_duplicates'].append(dict(path=str(restored),identity=restored_identity))
        # Persist the complete acceptance on B before releasing only our newly
        # verified working duplicates. Failure retains all scratch/candidates.
        seal=client.ensure(json.dumps(record,sort_keys=True,separators=(',',':')).encode())
        record['B_acceptance_object']=seal;on_prepared(dict(accepted=record))
        record['new_B_total_encoded_bytes_including_control']=client.payload_bytes_sent-initial_upload
        if legacy is None:release_verified_ram(restored,restored_identity)
        release_verified_ram(working,working_identity)
        return record
    except BaseException as error:
        error.nightly_SQL_working_path=str(working) if working is not None else None
        raise
    finally:
        if dst is not None:dst.close()
        if src is not None:
            if src.in_transaction:src.rollback()
            src.close()


def recover_SQL_layout(source,client,captured,retained,*,root,guard,maximum_image_bytes,
                       timeout_seconds,on_prepared,cohort_id=None):
    """Finish a durable uploaded API image after its volatile RAM file is lost.

    The original API bracket, manifest and accepted chunk identities must all
    agree. Only B is read; neither the later live DB nor an old RAM path is
    opened. The independently restored inode is removed only after acceptance
    has itself been persisted on B and in the caller's durable phase state.
    """
    if not isinstance(captured,dict) or captured.get('API_capture_completed') is not True:
        raise ValueError('retained complete original API proof required')
    if cohort_id is not None:
        digest(cohort_id)
        if captured.get('SQL_cohort_id')!=cohort_id:raise ValueError('retained SQL API qualification cohort differs')
    layout=retained['layout'];initial=captured['initial_SQL_integrity'];size=captured['bytes'];sha=captured['sha256']
    expected=dict(source=str(source),bytes=size,sha256=sha,segments=layout['segments'],
        source_metadata=captured['source_metadata_before'],method='SQLite-backup-API',
        independent_SQL_restore_accepted=False)
    if cohort_id is not None:expected['SQL_cohort_id']=cohort_id
    if (layout!=expected or captured['source']!=str(source) or initial.get('sha256')!=sha
            or initial.get('bytes')!=size or initial.get('integrity')!='ok'
            or type(size) is not int or not 0<size<=maximum_image_bytes
            or sum(s['bytes'] for s in layout['segments'])!=size):
        raise ValueError('durable SQL layout/original API proof differs')
    if type(retained['manifest'].get('bytes')) is not int or not 0<retained['manifest']['bytes']<=1024**2:
        raise ValueError('bounded durable SQL manifest required')
    guard();started=time.monotonic();uploaded=client.payload_bytes_sent
    def check():
        guard()
        if time.monotonic()-started>timeout_seconds:raise TimeoutError('finite SQL recovery; B layout retained')
        client.health()
    fs=os.statvfs(root)
    if fs.f_bavail*fs.f_frsize<size+client.maximum+16*1024**2:
        raise OSError('actual RAM independent SQL recovery scratch unavailable')
    manifest=io.BytesIO();client.verify(retained['manifest'],manifest)
    if len(manifest.getvalue())>1024**2 or json.loads(manifest.getvalue())!=expected:
        raise ValueError('authenticated B SQL manifest differs')
    fd,temp=tempfile.mkstemp(prefix='nightly-sql-independent-',suffix='.sqlite',dir=root);restored=Path(temp)
    with os.fdopen(fd,'wb') as out:
        for segment in layout['segments']:check();client.verify(segment,out)
        out.flush();os.fsync(out.fileno())
    check()
    probe=subprocess.run([sys.executable,'-B','-c',INDEPENDENT_SQL_CHECK,str(restored),sha],
        capture_output=True,text=True,timeout=max(1,timeout_seconds-(time.monotonic()-started)))
    if probe.returncode:raise ValueError('recovered SQL independent integrity failed: '+probe.stderr[-2048:])
    independent=json.loads(probe.stdout)
    if independent!=initial:raise ValueError('recovered SQL schema/content differs from original API point')
    metadata=captured['source_metadata_before'];restore_metadata(restored,metadata)
    restored_identity=fingerprint(restored.stat())
    independent.update(separate_restored_inode=restored_identity[:2],independent_Linux_metadata_verified=True)
    row=dict(kind='file',bytes=size,sha256=sha,segments=layout['segments'],
        **{k:metadata[k] for k in ('mode','uid','gid','mtime_ns','xattrs')})
    record=dict(source=str(source),status='consistent_SQL_point_verified',method='SQLite-backup-API',
        source_identity_before=captured['source_identity_before'],source_metadata_before=metadata,
        source_metadata_after=captured['source_metadata_after'],source_changed_online=captured['source_changed_online'],
        original_source_API_point_at=captured['original_source_API_point_at'],resumed_retained_SQL_point=True,
        recovered_from_durable_B_layout=True,bytes=size,sha256=sha,member=row,independent=independent,
        dependency=None,prepared_manifest=retained['manifest'],new_B_encoded_payload_bytes=0,
        source_API_image_bytes=0,original_API_point_bytes=size,baseline_accepted=False,
        source_API_point_qualifies_later_epoch_not_original=True,
        verified_RAM_duplicates=[dict(path=str(restored),identity=restored_identity)])
    if cohort_id is not None:record['SQL_cohort_id']=cohort_id
    check();record['B_acceptance_object']=client.ensure(json.dumps(record,sort_keys=True,separators=(',',':')).encode())
    on_prepared(dict(accepted=record));record['new_B_total_encoded_bytes_including_control']=client.payload_bytes_sent-uploaded
    release_verified_ram(restored,restored_identity)
    return record
