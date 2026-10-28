"""Bounded delta selection over an accepted baseline and durable journal.

The authenticated controller supplies the accepted baseline anchor and current
report. No global walk, stat or content hash is performed for unchanged paths.
New/moved-in directories require only their affected subtrees to be enumerated.
Journal faults/epoch loss demand explicit reconciliation, never an empty delta.
"""
import re
from pathlib import PurePosixPath
from vk_nightly_inode_journal import require_full_coverage


class ReconciliationRequired(ValueError):pass


def under(path,root):return path==root or path.startswith(root.rstrip('/')+'/')


def select(anchor,report,*,required_sql,maximum_paths,enumerate_subtree):
    try:require_full_coverage(report)
    except ValueError as error:raise ReconciliationRequired(str(error)) from error
    if (anchor.get('baseline_accepted') is not True or report.get('ready') is not True
            or report.get('errors') or report.get('terminal')
            or anchor.get('instance')!=report.get('instance')
            or anchor.get('scope_sha256')!=report.get('scope_sha256')
            or anchor.get('plan_sha256')!=report.get('plan_sha256')
            or type(anchor.get('sequence')) is not int or anchor['sequence']<0
            or report.get('since')!=anchor.get('sequence')
            or type(report.get('sequence')) is not int or report['sequence']<anchor['sequence']):
        raise ReconciliationRequired('accepted baseline and uninterrupted exact journal coverage required')
    if type(maximum_paths) is not int or maximum_paths<1:raise ValueError('finite delta budget required')
    sources=anchor.get('sources')
    def canonical(path):
        return (isinstance(path,str) and path.startswith('/') and str(PurePosixPath(path))==path
                and '..' not in PurePosixPath(path).parts and '\x00' not in path)
    if (not isinstance(sources,list) or not sources or len(sources)!=len(set(sources))
            or any(not canonical(path) for path in sources)):
        raise ValueError('bound required source roots missing')
    aliases=anchor.get('root_aliases',{})
    if not isinstance(aliases,dict) or not set(aliases)<=set(sources):
        raise ReconciliationRequired('accepted source-root alias contract differs')
    effective=set(sources)
    for alias,binding in aliases.items():
        if (not isinstance(binding,dict) or set(binding)!={'literal','resolved'}
                or not canonical(binding.get('resolved')) or binding['literal']!=binding['resolved']
                or under(binding['resolved'],alias)):
            raise ReconciliationRequired('canonical accepted root alias target required')
        effective.add(binding['resolved'])
    changed=report.get('changed');events=report.get('events')
    if (not isinstance(changed,list) or len(changed)!=len(set(changed))
            or not isinstance(events,dict) or set(changed)!=set(events)):
        raise ReconciliationRequired('complete changed-path/event set required')
    always=anchor.get('always_SQL_API_sources',[])
    if (not isinstance(always,list) or any(not isinstance(path,str) for path in always)
            or len(always)!=len(set(always)) or not set(always)<=set(required_sql)
            or any(not isinstance(path,str) or not path.startswith('/') or str(PurePosixPath(path))!=path
                   or '..' in PurePosixPath(path).parts or '\x00' in path
                   or not any(under(path,root) for root in effective) for path in always)):
        raise ReconciliationRequired('always-snapshotted SQL dependencies must be explicitly bound in source scope')
    runtime=anchor.get('always_runtime_files',{})
    if not isinstance(runtime,dict):raise ReconciliationRequired('explicit accepted runtime dependency map required')
    for path,row in runtime.items():
        if (not isinstance(path,str) or not path.startswith('/') or str(PurePosixPath(path))!=path
                or '..' in PurePosixPath(path).parts or '\x00' in path or not isinstance(row,dict)
                or row.get('kind')!='file' or type(row.get('bytes')) is not int or row['bytes']<0
                or not isinstance(row.get('sha256'),str) or not re.fullmatch('[0-9a-f]{64}',row['sha256'])):
            raise ReconciliationRequired('canonical accepted runtime file point required')
    if len(runtime)>maximum_paths:raise ReconciliationRequired('bounded runtime dependency budget exceeded')
    # Runtime code/control files outside the main source plan remain an
    # explicit component. The controller always observes their complete stable
    # points; this selector never claims the kernel watched these paths.
    # A critical SQL alias target may live outside a directory root. Its WAL
    # need not modify the main inode, so its API snapshot is always required.
    # Ordinary unchanged workspaces still incur zero inventory/content reads.
    selected=set();subtrees=set();SQL=set(always);deleted=set()
    def add(path):
        if (not isinstance(path,str) or not path.startswith('/') or str(PurePosixPath(path))!=path
                or '..' in PurePosixPath(path).parts or '\x00' in path):
            raise ValueError('canonical changed source required')
        if not any(under(path,root) for root in effective):raise ValueError('changed path outside bound source roots')
        selected.add(path)
        if len(selected|set(runtime))>maximum_paths:raise ReconciliationRequired('bounded final delta exceeded; finish Nightly catch-up first')
    for path in changed:
        mask=events[path]
        if type(mask) is not int or mask<=0:raise ReconciliationRequired('actual event mask required')
        db=next((raw for raw in required_sql if path in (raw,raw+'-wal',raw+'-shm',raw+'-journal')),None)
        if db is not None:SQL.add(db);continue
        add(path)
        if mask&0x40000000 and mask&(0x100|0x80):subtrees.add(path)
        if mask&(0x200|0x40):deleted.add(path)
    # Minimal disjoint expansion roots avoid rescanning unchanged workspaces or
    # walking a moved subtree more than once. Never truncate a bounded result.
    roots=[]
    for path in sorted(subtrees):
        if not any(under(path,root) for root in roots):roots.append(path)
    for root in roots:
        for path in enumerate_subtree(root):
            if not under(path,root):raise ValueError('subtree enumerator escaped changed root')
            add(path)
    return dict(instance=report['instance'],since=anchor['sequence'],through=report['sequence'],
                paths=sorted(selected),subtrees_enumerated=roots,removed_or_moved_from=sorted(deleted),
                SQLite_API_sources=sorted(SQL),runtime_files_to_observe_always=sorted(runtime),
                kernel_coverage_for_runtime_files_claimed=False,
                unchanged_paths_scanned=0,unchanged_payload_bytes_read=0,
                writer_fence_verified=False,final_restart_SQLite_API_required=True)
