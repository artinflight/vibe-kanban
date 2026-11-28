"""Witness unaffected source coverage while an explicit moved subtree is open.

Raw journal faults are never removed or marked ready. This certificate permits
only individual file qualification outside EVERY observed move/fault closure.
It cannot accept a complete baseline, a directory closure or a restart fence.
The controller must reconcile the named subtrees before whole-scope adoption.
"""
import json
import os
from pathlib import Path
import re
import stat

from vk_change_journal import scope
from vk_nightly_tracking import source_bindings
from vk_prep_common import identity
from vk_vanished_enrollment import start_ticks

FORMAT='vk-nightly-unaffected-source-coverage-v1'


def under(path,root):return path==root or path.startswith(root.rstrip('/')+'/')


def canonical_path(path):
    if (not isinstance(path,str) or not path.startswith('/') or str(Path(path))!=path
            or '..' in Path(path).parts or '\0' in path):raise ValueError('canonical coverage path required')
    return path


def observer_identity(observer):
    if start_ticks(observer['PID'])!=observer['start_ticks']:raise ValueError('observer process changed')
    p=Path('/proc')/str(observer['PID'])/'fd'/str(observer['fd'])
    if os.readlink(p)!='anon_inode:inotify':raise ValueError('observer lost inotify descriptor')
    info=p.stat();return [info.st_dev,info.st_ino]


def kernel_roots(observer,bindings):
    """One actual kernel witness over the small required-root set, no walk."""
    descriptor=observer_identity(observer);wanted={}
    for root,row in bindings.items():
        if row is None:raise ValueError('required root absent outside reconciliation scope')
        device,inode,_=row['target_identity'];wanted[((os.major(device)<<20)|os.minor(device),inode)]=root
    found={}
    p=Path('/proc')/str(observer['PID'])/'fdinfo'/str(observer['fd'])
    for line in p.read_text().splitlines():
        if not line.startswith('inotify wd:'):continue
        fields=dict(re.findall(r'(?:^|\s)(wd|ino|sdev|mask):([0-9a-f]+)(?=\s|$)',line))
        if set(fields)!={'wd','ino','sdev','mask'}:raise ValueError('unreadable kernel subscription')
        row={k:int(v,16) for k,v in fields.items()};key=(row['sdev'],row['ino'])
        if key in wanted:
            if row['mask']&0xfce!=0xfce:raise ValueError('required subscription mask incomplete')
            found[key]=row
    if set(found)!=set(wanted):raise ValueError('required root not kernel-watched')
    if observer_identity(observer)!=descriptor:raise ValueError('observer descriptor changed')
    return dict(descriptor=descriptor,watches=[found[k] for k in sorted(found)])


def move_paths(report):
    errors=report.get('errors')
    if (report.get('ready') is not False or not isinstance(errors,list) or not errors
            or any(set(e)!={'directory_moved'} for e in errors)):
        raise ValueError('only exact local directory-move faults can be scoped')
    paths=[canonical_path(e['directory_moved']) for e in errors]
    for path,mask in report.get('events',{}).items():
        if mask&0x40000000 and mask&0xc0:paths.append(canonical_path(path))
    return sorted(set(paths))


def seal(plan,report,*,observer,reconciliation_roots,kernel_reader=kernel_roots):
    roots=sorted(set(canonical_path(p) for p in reconciliation_roots))
    required=source_bindings(plan)
    resolved=[row['resolved'] for row in required.values() if row is not None]
    if (not roots or report.get('plan_sha256')!=identity(plan)
            or report.get('scope_sha256')!=identity(scope(plan))):raise ValueError('bound plan/scope required')
    for root in roots:
        if root in resolved or not any(under(root,parent) for parent in resolved):
            raise ValueError('cannot exclude a required root or an outside path')
    paths=move_paths(report)
    if any(not any(under(path,root) for root in roots) for path in paths):
        raise ValueError('move/fault closure is incomplete')
    # Alias and resolved forms both remain excluded. Never let a logical source
    # spelling sneak into a subtree whose physical coverage is unaccepted.
    outside={raw:row for raw,row in required.items()
             if row is None or not any(under(row['resolved'],r) for r in roots)}
    witness=kernel_reader(observer,outside)
    return dict(format=FORMAT,observer=observer,instance=report['instance'],
                plan_sha256=identity(plan),scope_sha256=identity(scope(plan)),
                raw_errors=report['errors'],through=report['sequence'],
                reconciliation_roots=roots,required_root_bindings=outside,kernel=witness,
                raw_journal_ready=False,whole_scope_accepted=False,historical_gap_recovered=False)


class ScopedCoverage:
    def __init__(self,certificate,expected_sha256,*,plan,kernel_identity=observer_identity,root_reader=source_bindings):
        self.certificate=json.loads(json.dumps(certificate));self.expected_sha256=expected_sha256
        self.plan=plan;self.kernel_identity=kernel_identity;self.root_reader=root_reader
        if (identity(certificate)!=expected_sha256 or certificate.get('format')!=FORMAT
                or certificate['plan_sha256']!=identity(plan)
                or certificate['scope_sha256']!=identity(scope(plan))):raise ValueError('coverage certificate differs')

    def check(self,report,paths):
        c=self.certificate
        if (identity(c)!=self.expected_sha256 or report.get('instance')!=c['instance']
                or report.get('scope_sha256')!=c['scope_sha256'] or report.get('plan_sha256')!=c['plan_sha256']
                or report.get('errors')!=c['raw_errors'] or report.get('terminal')
                or type(report.get('sequence')) is not int or report['sequence']<c['through']):
            raise ValueError('scoped raw coverage changed; retain proof and reconcile')
        for path in move_paths(report):
            if not any(under(path,r) for r in c['reconciliation_roots']):raise ValueError('new move outside witnessed closure')
        if self.kernel_identity(c['observer'])!=c['kernel']['descriptor']:raise ValueError('observer changed')
        now=self.root_reader(self.plan)
        if any(now[raw]!=expected for raw,expected in c['required_root_bindings'].items()):
            raise ValueError('required source binding changed')
        for raw in paths:
            path=canonical_path(str(raw));resolved=str(Path(path).resolve())
            if any(under(path,r) or under(resolved,r) or under(r,path) or under(r,resolved)
                   for r in c['reconciliation_roots']):raise ValueError('source requires explicit subtree reconciliation')
            if not any(row and under(resolved,row['resolved']) for row in c['required_root_bindings'].values()):
                raise ValueError('source outside witnessed roots')
        return dict(certificate_sha256=self.expected_sha256,qualified_paths=list(map(str,paths)),
                    raw_journal_ready=False,whole_scope_accepted=False,
                    required_reconciliation_roots=c['reconciliation_roots'])
