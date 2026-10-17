"""Backup-preservation index; deliberately grants NO deployment eligibility.

Reuse audited receipt-bound archives, path mapping and PAX decoding. Sparse
selected backup roots do not imply ownership of their unselected parents.
Ownership/modes/link targets are retained as data, never applied or followed by
this object store. Candidate/deployment validation remains in its original code.
"""
import base64
import copy
from contextlib import contextmanager
import hashlib
import json
from pathlib import PurePosixPath

from vk_candidate_direct_b import PR229, DirectBProvider, metadata, hardlink_metadata
from vk_nightly_generation import MAX_ENTRIES, MAX_INDEX, name, encoding_summary
from vk_archive_store import reference


def validate_backup_entries(entries):
    if not entries or len(entries)>MAX_ENTRIES:raise ValueError('empty/excessive backup inventory')
    validated_parents=set();cached_parent_bytes=0
    for key,row in entries.items():
        name(key)
        if row.get('kind') not in ('file','directory','symlink','hardlink'):raise ValueError('unsupported backup kind')
        for field in ('uid','gid','mode','mtime_ns'):
            if type(row.get(field)) is not int or row[field]<0:raise ValueError('invalid preserved numeric metadata')
        if row['mode']>0o7777:raise ValueError('invalid preserved mode')
        if not isinstance(row.get('xattrs'),dict):raise ValueError('missing preserved xattrs')
        for field,value in row['xattrs'].items():
            if not isinstance(field,str) or '\0' in field:raise ValueError('invalid preserved xattr name')
            base64.b64decode(value,validate=True)
        parent=key.rpartition('/')[0]
        while parent:
            if parent in validated_parents:break
            if parent in entries and entries[parent]['kind']!='directory':
                raise ValueError('backup member traverses an archived link or file')
            # Repeated dependency paths share long ancestors. Cache only a
            # finite 4MiB/65536-name set; a miss retains the full validation.
            if len(validated_parents)<65536 and cached_parent_bytes+len(parent)<=4*1024**2:
                validated_parents.add(parent);cached_parent_bytes+=len(parent)
            parent=parent.rpartition('/')[0]
        if row['kind'] in ('file','hardlink'):
            h=row.get('sha256');size=row.get('bytes')
            if not isinstance(h,str) or len(h)!=64 or any(c not in '0123456789abcdef' for c in h) or type(size) is not int or size<0:
                raise ValueError('invalid backup content binding')
        if row['kind']=='symlink' and (not isinstance(row.get('target'),str) or not row['target'] or '\0' in row['target']):
            raise ValueError('invalid preserved link literal')
        if row['kind']=='hardlink':
            name(row['target']);target=entries.get(row['target'],{})
            if target.get('kind')!='file' or any(row[k]!=target.get(k) for k in ('sha256','bytes','mode','uid','gid','mtime_ns','xattrs')):
                raise ValueError('backup hardlink identity mismatch')


class NightlyArchiveProvider(DirectBProvider):
    def __init__(self, *args, metadata_budget_bytes=MAX_INDEX, **kwargs):
        if type(metadata_budget_bytes) is not int or not 0 < metadata_budget_bytes <= MAX_INDEX:
            raise ValueError('nightly metadata budget must be bounded to 512MiB')
        # The historical candidate provider retains its original 256MiB ceiling.
        # Only this backup-preservation adapter adopts the measured nightly cap.
        super().__init__(*args, metadata_budget_bytes=min(metadata_budget_bytes, 256*1024**2), **kwargs)
        self.metadata_budget_bytes = metadata_budget_bytes

    def verify(self,capture_id):
        record=self.records[capture_id];result=record['result']
        if result.get('parent') is not None:raise ValueError('nightly input cannot depend on an archive chain')
        archive=self.factory(reference(result),desktop_only=True);manifest=None;entries={}
        snapshots={'payload/'+row['path']:(self.mapped(raw,record),row['sha256']) for raw,row in result['sqlite_snapshots'].items()}
        found=set()
        with archive.contents() as tar:
            for member in tar:
                # Only regular members are extracted; hardlinks use recorded
                # canonical metadata below, never TarFile's member cache.
                tar.members.clear()
                if member.name=='payload/manifest.json':
                    if manifest is not None or not member.isfile() or member.size>32*1024**2:
                        raise ValueError('duplicate/invalid embedded backup manifest')
                    manifest=json.load(tar.extractfile(member))
                    if (not isinstance(manifest,dict) or manifest.get('parent') is not None
                            or manifest.get('plan_sha256')!=record['plan'] or manifest.get('scope_sha256')!=record['scope']
                            or any(key not in result or result[key]!=value for key,value in manifest.items())):
                        raise ValueError('embedded backup manifest differs from bound capture')
                    continue
                if member.name in snapshots:
                    key,expected=snapshots[member.name];found.add(member.name)
                else:
                    if member.name.startswith('payload/'):raise ValueError('unknown backup payload')
                    key,expected=self.mapped(member.name,record),None
                if not key:
                    if not member.isdir():raise ValueError('invalid backup namespace root')
                    continue
                name(key)
                if key in entries:raise ValueError('duplicate backup member')
                row=metadata(member)
                if member.isdir():row['kind']='directory'
                elif member.isfile():
                    with tar.extractfile(member) as stream:checksum=hashlib.file_digest(stream,'sha256').hexdigest()
                    if expected is not None and checksum!=expected:raise ValueError('backup SQLite hash mismatch')
                    row.update(kind='file',sha256=checksum,bytes=member.size)
                elif member.issym():row.update(kind='symlink',target=member.linkname)
                elif member.islnk():row.update(kind='hardlink',target=self.mapped(member.linkname,record))
                else:raise ValueError('unsupported special backup member')
                entries[key]=row
                if len(entries)>MAX_ENTRIES:raise ValueError('excessive backup inventory')
        if manifest is None or found!=set(snapshots):raise ValueError('missing backup manifest/SQLite image')
        archives=[(archive,manifest)]
        for key,row in entries.items():
            if row['kind']!='hardlink':continue
            target=row['target'];seen={key}
            while entries.get(target,{}).get('kind')=='hardlink':
                if target in seen:raise ValueError('backup hardlink cycle')
                seen.add(target);target=entries[target]['target']
            if entries.get(target,{}).get('kind')!='file':raise ValueError('missing backup hardlink content')
            hardlink_metadata(entries,target,[key]);original=entries[target]
            row.update(target=target,sha256=original['sha256'],bytes=original['bytes'],xattrs=copy.deepcopy(original['xattrs']))
        validate_backup_entries(entries)
        if not set(self.required)<=set(entries):raise ValueError('missing required backup database')
        checksum,size=encoding_summary(entries)
        if size>self.metadata_budget_bytes:raise ValueError('backup index exceeds bounded metadata capacity')
        proof={'provider':'desktop-B','scope_sha256':self.scope,'capture_id':capture_id,'full_current_state':True,
            'entries':entries,'manifest_sha256':checksum,'fixture_only':self.fixture_only,
            'source_commit':PR229,'index_policy':'backup-preservation-v1','metadata_encoded_bytes':size,
            'operational_dependency_closure_verified':False,'deployment_eligible':False,
            'metadata_policy':'preservation only; unselected parent metadata unspecified; numeric owner/mode/xattrs and literal symlinks recorded, never applied/followed'}
        self.indexes[capture_id]={'proof':proof,'archives':archives,'snapshots':snapshots}
        # Fixed same-account callers share the verified table. They must not
        # mutate its rows; duplicating it adds an entire host-sized index.
        return proof

    @contextmanager
    def file_members(self,capture_id,selected):
        indexed=self.indexes[capture_id];record=self.records[capture_id]
        if not set(selected)<=indexed['proof']['entries'].keys():raise ValueError('requested member outside verified index')
        def members():
            seen=set()
            for archive,_ in indexed['archives']:
                with archive.contents() as tar:
                    for member in tar:
                        tar.members.clear()
                        if member.name=='payload/manifest.json':continue
                        key=indexed['snapshots'][member.name][0] if member.name in indexed['snapshots'] else self.mapped(member.name,record)
                        if key in selected and member.isfile():
                            if key in seen:raise ValueError('duplicate replay member')
                            with tar.extractfile(member) as stream:yield key,stream
                            seen.add(key)
            if seen!=set(selected):raise ValueError('verified archive omitted requested replay member')
        iterator=members()
        try:
            yield iterator
            for _ in iterator:pass
        finally:iterator.close()
