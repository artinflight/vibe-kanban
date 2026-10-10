"""Backup-preservation index; deliberately grants NO deployment eligibility.

Reuse audited receipt-bound archives, path mapping and PAX decoding. Sparse
selected backup roots do not imply ownership of their unselected parents.
Ownership/modes/link targets are retained as data, never applied or followed by
this object store. Candidate/deployment validation remains in its original code.
"""
import base64
import copy
import hashlib
import json
from pathlib import PurePosixPath

from vk_candidate_direct_b import PR229, DirectBProvider, metadata, hardlink_metadata
from vk_nightly_generation import MAX_ENTRIES, MAX_INDEX, name
from vk_candidate_generation import digest


def validate_backup_entries(entries):
    if not entries or len(entries)>MAX_ENTRIES:raise ValueError('empty/excessive backup inventory')
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
        for parent in PurePosixPath(key).parents:
            if parent.as_posix() in entries and entries[parent.as_posix()]['kind']!='directory':
                raise ValueError('backup member traverses an archived link or file')
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
    def verify(self,capture_id):
        record=self.records[capture_id];archives=self.archives(record)
        if len(archives)!=1:raise ValueError('nightly input cannot depend on an archive chain')
        archive,manifest=archives[0];entries={};locations={}
        snapshots={'payload/'+row['path']:(self.mapped(raw,record),row['sha256']) for raw,row in manifest['sqlite_snapshots'].items()}
        found=set()
        with archive.contents() as tar:
            for member in tar:
                if member.name=='payload/manifest.json':continue
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
                    row.update(kind='file',sha256=checksum,bytes=member.size);locations[key]=(0,member.name)
                elif member.issym():row.update(kind='symlink',target=member.linkname)
                elif member.islnk():row.update(kind='hardlink',target=self.mapped(member.linkname,record))
                else:raise ValueError('unsupported special backup member')
                entries[key]=row
        if found!=set(snapshots):raise ValueError('missing backup SQLite image')
        for key,row in entries.items():
            if row['kind']!='hardlink':continue
            target=row['target'];seen={key}
            while entries.get(target,{}).get('kind')=='hardlink':
                if target in seen:raise ValueError('backup hardlink cycle')
                seen.add(target);target=entries[target]['target']
            if entries.get(target,{}).get('kind')!='file':raise ValueError('missing backup hardlink content')
            hardlink_metadata(entries,target,[key]);original=entries[target]
            row.update(target=target,sha256=original['sha256'],bytes=original['bytes'],xattrs=copy.deepcopy(original['xattrs']))
            locations[key]=locations[target]
        validate_backup_entries(entries)
        if not set(self.required)<=set(entries):raise ValueError('missing required backup database')
        size=sum(len(piece.encode()) for piece in json.JSONEncoder().iterencode(entries))
        if size>self.metadata_budget_bytes:raise ValueError('backup index exceeds bounded metadata capacity')
        proof={'provider':'desktop-B','scope_sha256':self.scope,'capture_id':capture_id,'full_current_state':True,
            'entries':entries,'manifest_sha256':digest(entries),'fixture_only':self.fixture_only,
            'source_commit':PR229,'index_policy':'backup-preservation-v1','metadata_encoded_bytes':size,
            'operational_dependency_closure_verified':False,'deployment_eligible':False,
            'metadata_policy':'preservation only; unselected parent metadata unspecified; numeric owner/mode/xattrs and literal symlinks recorded, never applied/followed'}
        self.indexes[capture_id]={'proof':proof,'archives':archives,'locations':locations,'headers':{}}
        return copy.deepcopy(proof)
