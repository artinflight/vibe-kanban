"""Qualify selected current versions against authenticated retained carriers.

One stable source hash closes an otherwise unqualified version. Matching content
reuses its accepted carrier with current Linux metadata, without copying it.
The old carrier epoch and the later source observation remain distinct. This is
not a namespace scan, SQL snapshot, complete descriptor or activation receipt.
"""
from pathlib import Path
import hashlib
import json
import zlib

from vk_nightly_file_version import capture_version,qualify_jsonl_point
from vk_nightly_checkpoints import digest,source_path


def reanchor_unchanged(version, report, *, guard):
    """Adopt an existing hashed point under a new, independently ready observer.

    This is a new identity observation, never a repair of the old journal. The
    exact inode, size, mtime, kernel ctime, owner, mode, link count and xattrs
    must still match the successful hash bracket. A changed version needs its
    own qualification; no content is inferred from mtime/length alone.
    """
    from vk_nightly_file_version import fingerprint, attributes
    import os
    import stat
    if version.get('state') not in ('qualified-retained-body', 'qualified-pending-body'):
        raise ValueError('successful original point qualification required')
    anchor=version['journal']
    if (report.get('ready') is not True or report.get('errors') or report.get('terminal')
            or report.get('scope_sha256')!=anchor['scope_sha256']
            or report.get('plan_sha256')!=anchor['plan_sha256']
            or type(report.get('since')) is not int or report['since']!=0
            or type(report.get('sequence')) is not int or report['sequence']<0
            or not report.get('instance')):
        raise ValueError('complete ready new observer window with unchanged plan/scope required')
    path=Path(version['source']);source_path(str(path));guard()
    if path.resolve()!=path:raise ValueError('qualified source alias changed')
    if any(str(path)==p or str(path).startswith(p.rstrip('/')+'/') for p in report['changed']):
        raise ValueError('new observer records a source/ancestor change')
    before=path.lstat()
    if not stat.S_ISREG(before.st_mode) or fingerprint(before)!=version['source_identity']:
        raise ValueError('qualified source identity changed; requalification required')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    try:
        if (fingerprint(os.fstat(fd))!=version['source_identity']
                or attributes(path)!=version['row']['xattrs']
                or fingerprint(path.lstat())!=version['source_identity']):
            raise ValueError('qualified source metadata changed during handover')
    finally:os.close(fd)
    guard()
    old_hash=hashlib.sha256(json.dumps(version,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    return dict(version,journal={k:report[k] for k in ('instance','sequence','scope_sha256','plan_sha256')},
                observer_handover=dict(original_qualification_sha256=old_hash,original_journal=anchor,
                    source_identity_reobserved=True,source_payload_bytes_reread=0,
                    original_journal_gap_repaired=False))


class HashOnly:
    def write(self,block):return len(block)


def encode_observation(value):
    """Compress only control JSON, never source/backup content."""
    raw=json.dumps(value,sort_keys=True,separators=(',', ':'),allow_nan=False).encode()
    if len(raw)>1024**2:raise ValueError('bounded source observation required')
    return b'VKQ1\0'+zlib.compress(raw,1)


def decode_observation(raw):
    # Existing committed plain-JSON observations retain their original bytes.
    if isinstance(raw,str):
        if len(raw.encode())>1024**2:raise ValueError('observation exceeds bound')
        return json.loads(raw)
    if not isinstance(raw,bytes) or not raw.startswith(b'VKQ1\0'):raise ValueError('unknown observation encoding')
    decoder=zlib.decompressobj();value=decoder.decompress(raw[5:],1024**2+1)
    if len(value)>1024**2 or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ValueError('incomplete/excessive observation')
    return json.loads(value)


def index_accepted_base(source,output,*,source_catalog_sha256,restore_proof_sha256,checkpoint=lambda:None):
    """Index hashes already bound to the accepted independent restored set.

    The controller authenticates the immutable input catalog and its derivation
    from the accepted restore. Null old hashes (including original missing
    bodies) cannot become carriers. A hash match at a new current path reuses
    the original raw member; it does not assert old inclusion of that new name.
    """
    digest(source_catalog_sha256);digest(restore_proof_sha256)
    output.execute('begin immediate')
    try:
        output.execute('create table provenance(source_catalog_sha256 text not null,restore_proof_sha256 text not null)')
        output.execute('insert into provenance values(?,?)',(source_catalog_sha256,restore_proof_sha256))
        output.execute('create table bodies(sha256 text,bytes integer,name text not null,primary key(sha256,bytes)) without rowid')
        count=0
        for name,sha,size in source.execute('select name,old_sha256,old_bytes from current where old_sha256 is not NULL order by name'):
            source_path('/'+name);digest(sha)
            if type(size) is not int or size<0:raise ValueError('accepted base body length missing')
            output.execute('insert or ignore into bodies values(?,?,?)',(sha,size,name));count+=1
            if count%2048==0:checkpoint()
        checkpoint();output.execute('commit')
    except BaseException:
        if output.in_transaction:output.execute('rollback')
        raise
    return dict(accepted_original_paths_indexed=count,
                unique_verified_content_bodies=output.execute('select count(*) from bodies').fetchone()[0],
                source_or_archive_payload_bytes_read=0,backup_payload_bytes_copied=0,
                original_epoch_gaps_repaired=False,current_baseline_accepted=False)


def accepted_base_carrier(index,sha,size):
    digest(sha)
    row=index.execute('select name from bodies where sha256=? and bytes=?',(sha,size)).fetchone()
    if row is None:return None
    return dict(kind='file',sha256=sha,bytes=size,segments=[dict(
        layer='accepted-base',selector=row[0],sha256=sha,bytes=size)])


def still_covered(version,report,*,coverage=None):
    """A resumed qualifier reuses only a continuously observed exact version."""
    anchor=version['journal']
    if (report.get('terminal') or report.get('instance')!=anchor['instance']
            or report.get('scope_sha256')!=anchor['scope_sha256']
            or report.get('plan_sha256')!=anchor['plan_sha256']
            or type(report.get('since')) is not int or not 0<=report['since']<=anchor['sequence']
            or type(report.get('sequence')) is not int or report['sequence']<anchor['sequence']):return False
    if report.get('ready') is not True or report.get('errors'):
        from vk_nightly_scoped_coverage import ScopedCoverage
        if not isinstance(coverage,ScopedCoverage):return False
        try:coverage.check(report,[version['source']])
        except (ValueError,OSError):return False
    path=Path(version['source'])
    return not any(str(path)==changed or str(path).startswith(changed.rstrip('/')+'/')
                   for changed in report['changed'])


def qualify_file(path,*,maximum_bytes,journal,carriers,guard,coverage=None,payload_sink=None):
    """carriers(sha,size) returns only externally authenticated typed recipes."""
    scoped=None
    if journal.get('terminal') or type(journal.get('sequence')) is not int:
        raise ValueError('current source qualification needs live continuous tracking')
    if journal.get('ready') is not True or journal.get('errors'):
        from vk_nightly_scoped_coverage import ScopedCoverage
        if not isinstance(coverage,ScopedCoverage):raise ValueError('current source qualification needs live continuous tracking')
        scoped=coverage.check(journal,[str(path)])
    if payload_sink is not None:
        observed=capture_version(path,payload_sink,maximum_bytes=maximum_bytes,guard=guard)
    elif Path(path).suffix=='.jsonl':
        try:observed=qualify_jsonl_point(path,maximum_bytes=maximum_bytes,guard=guard)
        except ValueError as error:
            if str(error)!='JSONL point lacks a complete final record boundary':raise
            # A stable raw file need not be syntactically complete JSONL. Only
            # append-tolerant prefix qualification requires a record boundary.
            observed=capture_version(path,HashOnly(),maximum_bytes=maximum_bytes,guard=guard)
    else:observed=capture_version(path,HashOnly(),maximum_bytes=maximum_bytes,guard=guard)
    row=dict(kind='file',bytes=observed['bytes'],sha256=observed['sha256'],
             **{k:observed['metadata'][k] for k in ('mode','uid','gid','mtime_ns','xattrs')})
    carrier=next(iter(carriers(row['sha256'],row['bytes'])),None)
    if carrier is not None:
        if (carrier.get('kind')!='file' or carrier.get('bytes')!=row['bytes']
                or carrier.get('sha256')!=row['sha256'] or not carrier.get('segments')):
            raise ValueError('retained current-version carrier differs')
        row['segments']=carrier['segments']
    return dict(source=observed['source'],source_identity=observed['source_identity'],row=row,
                source_observed_at=observed['completed_at'],
                journal={k:journal[k] for k in ('instance','sequence','scope_sha256','plan_sha256')},
                state='qualified-retained-body' if carrier is not None else 'qualified-pending-body',
                source_payload_bytes_hashed=observed['bytes'],backup_payload_bytes_copied=0,
                carrier_epoch_preserved=True,original_epoch_repaired=False,
                **({'JSONL_point_qualification':observed} if observed.get('independent_source_hashes') else {}),
                namespace_or_whole_baseline_accepted=False,
                **({'scoped_qualification_coverage':scoped} if scoped is not None else {}))
