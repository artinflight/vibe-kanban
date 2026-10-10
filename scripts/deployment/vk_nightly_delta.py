"""Content-verified transport delta against ONE verified self-contained current.

No timestamp-only reuse, archive parent or growing chain. The caller obtains the
baseline from the held B resident, and final publication still verifies every
object on B. Same-account callbacks are not a privilege boundary.
"""
import base64
import hashlib
import os
from pathlib import Path
import stat

from vk_nightly_archive_index import NightlyArchiveProvider, validate_backup_entries
from vk_candidate_generation import digest
from vk_nightly_generation import MAX_INDEX, encoded


def fingerprint(info):
    return info.st_dev,info.st_ino,info.st_size,info.st_mode,info.st_uid,info.st_gid,info.st_mtime_ns,info.st_ctime_ns


def strict_scan(roots, exclusions):
    """An unreadable subtree is failure, never an implicit retention exclusion."""
    paths=set();visited=set()
    def error(exc):raise exc
    def visit(raw):
        root=Path(raw);paths.add(str(root))
        if root.is_symlink():
            target=str(root.resolve(strict=True))
            if target not in visited:visit(target)
        elif root.is_dir():
            if str(root) in visited:return
            visited.add(str(root))
            for directory,dirs,files in os.walk(root,followlinks=False,onerror=error):
                dirs[:]=[item for item in dirs if not exclusions(Path(directory)/item)]
                paths.update(str(Path(directory)/item) for item in dirs+files if not exclusions(Path(directory)/item))
    for root in roots:visit(root)
    return paths


class DeltaSelection:
    def __init__(self, baseline, prefix, scope):
        if baseline is not None and (baseline.get('scope_sha256')!=scope or baseline.get('parent') is not None):
            raise ValueError('delta requires bound self-contained current')
        self.baseline=baseline;self.prefix=Path(prefix);self.reused={};self.present=None
    def inventory(self, paths):
        self.present={Path(raw).relative_to(self.prefix).as_posix() for raw in paths}
        self.present.discard('.')
    def include(self, raw):
        if self.baseline is None:return True
        p=Path(raw);key=p.relative_to(self.prefix).as_posix();row=self.baseline['entries'].get(key,{})
        before=p.lstat()
        # Include every link/metadata header and every hardlink group's payload.
        # GNU tar canonicalization may change after an alias is removed.
        if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or row.get('kind')!='file':return True
        meta={'mode':stat.S_IMODE(before.st_mode),'uid':before.st_uid,'gid':before.st_gid,
              'mtime_ns':before.st_mtime_ns,'xattrs':{k:base64.b64encode(os.getxattr(p,k)).decode() for k in os.listxattr(p)}}
        if row.get('bytes')!=before.st_size or any(row.get(k)!=v for k,v in meta.items()):return True
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(fd,'rb') as stream:
            if fingerprint(os.fstat(stream.fileno()))!=fingerprint(before):raise ValueError('delta source substituted')
            checksum=hashlib.file_digest(stream,'sha256').hexdigest()
            after=os.fstat(stream.fileno())
        if fingerprint(before)!=fingerprint(after) or fingerprint(p.lstat())!=fingerprint(before):
            # Do not reuse a moving source. Ordinary capture retains its existing
            # online-warning/journal rules rather than silently accepting reuse.
            return True
        if checksum!=row['sha256']:return True
        self.reused[raw]=fingerprint(after)
        return False
    def finish(self, watched):
        if self.present is None:raise ValueError('delta lacks complete source inventory')
        if any(raw in watched['changed'] or fingerprint(Path(raw).lstat())!=value for raw,value in self.reused.items()):
            raise ValueError('reused source changed during capture; current preserved')
    def merge(self, proof):
        if self.baseline is None:return proof
        prior=self.baseline['entries'];entries={k:r for k,r in prior.items() if k in self.present}
        reused_keys={Path(raw).relative_to(self.prefix).as_posix() for raw in self.reused}
        if set(entries)-set(proof['entries']) != reused_keys:
            raise ValueError('delta omission is not exactly the content-verified reuse set')
        entries.update(proof['entries']);validate_backup_entries(entries)
        # Validate the complete index budget, not only the small delta archive.
        encoded(entries)
        return {**proof,'entries':entries,'manifest_sha256':digest(entries),
                'transport':'content-verified nightly delta','baseline_generation':self.baseline['generation'],
                'baseline_manifest_sha256':hashlib.sha256(encoded(self.baseline)).hexdigest(),
                'reused_files':len(reused_keys),'reused_content_bytes':sum(entries[k]['bytes'] for k in reused_keys)}


class DeltaProvider(NightlyArchiveProvider):
    def __init__(self,*args,selection,**kwargs):
        super().__init__(*args,**kwargs);self.selection=selection
    def verify(self,capture_id):
        proof=self.selection.merge(super().verify(capture_id))
        self.indexes[capture_id]['proof']=proof
        return proof
