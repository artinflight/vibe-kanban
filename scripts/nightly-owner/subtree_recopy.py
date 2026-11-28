"""Bounded fallback: independently hash moved subtrees and fence changes.

The ordinary journal remains authoritative elsewhere. This is not permission to
ignore a move: the caller must validate covering watches, scope and move events.
No old checkpoint is rewritten. Verified parent metadata permits incremental
copying; the whole subtree is still independently hashed at both final fences.
"""
import copy
import hashlib
import os
from pathlib import Path
import stat
import json


def snapshot(root):
    root=Path(root)
    assert root.is_dir() and not root.is_symlink()
    paths=[root]
    for directory,dirs,names in os.walk(root,followlinks=False):
        paths.extend(Path(directory)/name for name in dirs+names)
    result={}
    for path in paths:
        st=path.lstat()
        content=None
        if stat.S_ISREG(st.st_mode):
            with path.open('rb') as stream:
                content=hashlib.file_digest(stream,'sha256').hexdigest()
            after=path.lstat()
            assert (st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns), 'Moved subtree changed during hash inventory'
        result[str(path)]=(st.st_dev,st.st_ino,st.st_mode,st.st_size,st.st_mtime_ns,
                           st.st_ctime_ns,os.readlink(path) if path.is_symlink() else None,content)
    return result


class RecopyJournal:
    def __init__(self,reader,parent=None):
        self.reader=reader
        self.before=None
        self.roots=None
        self.prior={}
        if parent and 'recopy_baseline' in parent:
            receipt=parent.get('metadata_receipt',{})
            name=receipt.get('name','')
            assert name == parent['archive']+'.result.json'
            metadata=Path(parent['folder'])/name
            assert receipt.get('desktop_verified') is True
            with metadata.open('rb') as stream:
                assert hashlib.file_digest(stream,'sha256').hexdigest()==receipt['sha256']
            verified=json.loads(metadata.read_text())
            for key in ('recopy_baseline','journal_instance','journal_sequence','scope_sha256','plan_sha256','archive'):
                assert verified[key]==parent[key], 'Unverified recopy parent: '+key
            assert verified['receipt']['sha256']==parent['receipt']['sha256']
            self.prior=verified['recopy_baseline']

    def __call__(self,since=0):
        value=copy.deepcopy(self.reader(since))
        roots=value.get('required_subtree_recopy',[])
        current={p:list(signature) for root in roots for p,signature in snapshot(root).items()}
        if self.before is None:
            self.before=current
            self.roots=roots
            prior_roots=self.prior.get('roots',[])
            prior_files=self.prior.get('files',{})
            changed={root for root in roots if root not in prior_roots}
            changed.update(p for p in set(current)|set(prior_files)
                           if any(p==root or p.startswith(root+os.sep) for root in roots)
                           and current.get(p)!=prior_files.get(p))
        else:
            assert roots==self.roots,'Additional moved subtree requires a new capture'
            changed={p for p in set(current)|set(self.before) if current.get(p)!=self.before.get(p)}
        value['changed']=sorted(set(value['changed'])|changed)
        for path in changed:
            value.setdefault('events',{})[path]=value.get('events',{}).get(path,0)|0x2
        value['recopy_baseline']={'roots':roots,'files':self.before}
        return value
