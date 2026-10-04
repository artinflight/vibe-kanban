"""Reconstruct the validated DeletionAwareJournal semantics without dropping events.

Require parent DELETE, DELETE_SELF, and IGNORED; reject root loss, overflow,
unknown errors, missing covering watches and unwatched recreated directories.
This does not certify writer fencing or authorize a handover.
"""
from pathlib import Path
import copy,json,os,subprocess
MASK=0x40000000 | 0x200 | 0x400 | 0x8000

def recopy_cover(path, allowed, roots, covered):
    assert path.is_absolute() and str(path)==os.path.normpath(str(path)), 'Invalid moved destination'
    assert not path.is_symlink() and not any(p.is_symlink() for p in path.parents), 'Moved destination traverses a symlink'
    matches=[root for root in allowed if root in path.parents]
    assert len(matches)==1, 'Moved or failed-watch path lacks unique bounded coverage'
    parent=matches[0]
    assert parent not in roots and roots.intersection(parent.parents)
    assert covered(parent), 'Recopy subtree has no covering parent watch'
    return parent

def observed_move(path, mask):
    moved_in=mask&0x40000880==0x40000880
    removed=(not path.exists() and not path.is_symlink()
             and mask&(MASK|0x800)==(MASK|0x800))
    assert moved_in or removed, 'Missing move-in or complete deletion evidence'

def source_removal(path, parent, events, roots, covered, move_sources):
    explicit=move_sources.get(str(path))
    candidates=[Path(p) for p,mask in events.items()
                if mask&0x40000040==0x40000040 and parent in Path(p).parents
                and Path(p).name==path.name and Path(p)!=path]
    assert explicit or len(candidates)==1, 'Move needs an explicit source or unique matching source evidence'
    source=Path(explicit) if explicit else candidates[0]
    assert source.is_absolute() and str(source)==os.path.normpath(str(source)) and source!=path, 'Invalid move source'
    assert source not in roots and roots.intersection(source.parents), 'Move source outside protected scope'
    assert events.get(str(source),0)&0x40000040==0x40000040, 'Missing observed source removal'
    assert not source.is_symlink() and not any(p.is_symlink() for p in source.parents), 'Move source traverses a symlink'
    assert any(covered(ancestor) for ancestor in source.parents), 'Move source has no covering watch'
    return str(source)

def reconcile(value, full, roots, covered, recreated_covered, recopy_covered=lambda p:False):
    assert value['instance']==full['instance'] and value['scope_sha256']==full['scope_sha256']
    if not value['errors']:return value
    accepted=[]
    for error in {json.dumps(e,sort_keys=True):e for e in value['errors']}.values():
        if set(error)!={'watch_removed'}:return value
        path=Path(error['watch_removed'])
        if not path.is_absolute() or str(path)!=os.path.normpath(str(path)):return value
        if path in roots or not roots.intersection(path.parents):return value
        mask=full['events'].get(str(path),0)
        if mask&MASK != MASK and not (mask&0x8400==0x8400 and recopy_covered(path)):return value
        if not any(covered(parent) for parent in path.parents):return value
        if path.exists() and not recreated_covered(path):return value
        if path.is_symlink():return value
        accepted.append(str(path))
    result=copy.deepcopy(value)
    result['errors']=[];result['ready']=True
    result['reconciled_directory_deletions']=accepted
    return result

def kernel_watches(service, expected_pid):
    assert service.endswith('.service') and expected_pid.isdigit() and int(expected_pid)>0
    pid=subprocess.check_output(['systemctl','--user','show',service,'-p','MainPID','--value'],text=True).strip()
    assert pid==expected_pid,'Watcher changed; readiness must be rebuilt'
    watches=set()
    for p in (Path('/proc')/pid/'fdinfo').iterdir():
        for line in p.read_text().splitlines():
            if line.startswith('inotify wd:'):
                d=dict(x.split(':',1) for x in line.split()[1:] if ':' in x)
                watches.add((int(d['sdev'],16),int(d['ino'],16)))
    assert watches
    return watches

def journal(root,since=0,recopy_roots=None,move_sources=None,*,plan_path=None):
    import sys
    sys.path.insert(0,str(root/'deployment-tools'))
    from vk_change_journal import request,scope
    from vk_prep_common import identity
    plan=json.loads((plan_path or root/'backup-plan.json').read_text())
    coverage_path=root/'move-coverage.json'
    coverage=json.loads(coverage_path.read_text()) if coverage_path.exists() else plan.get('move_coverage',{})
    recopy_roots=coverage.get('recopy_roots',[]) if recopy_roots is None else recopy_roots
    move_sources=coverage.get('move_sources',{}) if move_sources is None else move_sources
    full=request(root/'journal.sock',0)
    value=full if since==0 else request(root/'journal.sock',since)
    assert value['scope_sha256']==identity(scope(plan))
    watcher=coverage['journal_identity']
    watches=kernel_watches(watcher['service'],str(watcher['pid']))
    def covered(path):
        try:
            if path.is_symlink() or not path.is_dir():return False
            stat=path.stat()
            return ((os.major(stat.st_dev)<<20)|os.minor(stat.st_dev),stat.st_ino) in watches
        except FileNotFoundError:return False
    def recreated(path):
        count=0
        for directory,dirs,_ in os.walk(path,followlinks=False):
            count+=1
            if count>2048 or not covered(Path(directory)):return False
            if any((Path(directory)/d).is_symlink() for d in dirs):return False
        return count>0
    roots={Path(p).resolve() for p in plan['sources']}
    unique=list({json.dumps(e,sort_keys=True):e for e in full['errors']}.values())
    moved=[error for error in unique if set(error)=={'directory_moved'}]
    repair=set()
    if moved and recopy_roots:
        allowed={Path(p) for p in recopy_roots}
        for error in moved:
            path=Path(error['directory_moved'])
            parent=recopy_cover(path,allowed,roots,covered)
            # RecopyJournal hashes the whole explicit subtree before and after
            # capture. Interior watch gaps cannot certify a frozen boundary.
            observed_move(path,full['events'].get(str(path),0))
            source_removal(path,parent,full['events'],roots,covered,move_sources or {})
            repair.add(str(parent))
        full=copy.deepcopy(full);value=copy.deepcopy(value)
        full['errors']=[e for e in full['errors'] if e not in moved]
        value['errors']=[e for e in value['errors'] if e not in moved]
    failed=[error for error in unique if set(error)=={'watch_failed','errno'}]
    if failed and recopy_roots:
        for error in failed:
            path=Path(error['watch_failed'])
            assert error['errno']==2 and not path.is_symlink()
            parent=recopy_cover(path,{Path(p) for p in recopy_roots},roots,covered)
            assert any(full['events'].get(str(ancestor),0)&0x40000240
                       and full['events'].get(str(ancestor),0)&0x240
                       for ancestor in (path,*path.parents) if parent in ancestor.parents), 'No observed removal for missing watch'
            repair.add(str(parent))
        full=copy.deepcopy(full);value=copy.deepcopy(value)
        full['errors']=[e for e in full['errors'] if e not in failed]
        value['errors']=[e for e in value['errors'] if e not in failed]
    # A recreated directory inside a recopy root is independently inventoried
    # and hashed at both capture fences, even if an interior watch was lost.
    bounded=lambda p:any(Path(r) in p.parents for r in repair)
    result=reconcile(value,full,roots,covered,lambda p: bounded(p) or recreated(p),bounded)
    if repair:
        result['required_subtree_recopy']=sorted(repair)
        if not result['errors']:
            result['ready']=True
    (root/'journal-raw-latest.json').write_text(json.dumps(full))
    (root/'journal-reconciliation.json').write_text(json.dumps({'instance':result['instance'],
        'raw_errors':full['errors'],'accepted':result.get('reconciled_directory_deletions',[]),
        'remaining_errors':result['errors'],'kernel_watches_checked':len(watches),
        'directory_move_errors':moved,'failed_watch_errors':failed,'required_subtree_recopy':sorted(repair),
        'explicit_move_sources':move_sources or {},'writer_fence_verified':False},indent=2))
    return result
