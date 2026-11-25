"""Select closed raw histories and prepare bounded forward packed transactions.

Reads both SQL owners. Active/pending/unbound/changed captures are preserved.
No scheduler or publication action occurs here. Recovery must precede migration.
"""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import time
import uuid

import log_dedup as logs
import packed_forward
from packed_plan import check_bindings, compile_group
from packed_recovery import write_new
import reclaim


def inventory(root, databases, *, minimum_age_seconds, guard, now_ns=time.time_ns):
    root = Path(root)
    if set(databases) != {'main','protected'} or not 0 <= minimum_age_seconds <= 86400:
        raise ValueError('Both serving SQL owners and bounded closed age required')
    snapshots = {}; active = set(); observed = []; eligible = []
    guard()
    for owner,database in databases.items():
        with closing(sqlite3.connect(Path(database).as_uri()+'?mode=ro',uri=True,timeout=2)) as db:
            db.execute('pragma query_only=on');db.execute('begin')
            rows = db.execute('''select e.id,e.session_id,e.status,e.completed_at,s.workspace_id
                from execution_processes e join sessions s on s.id=e.session_id''').fetchall()
            snapshots[owner] = {str(uuid.UUID(bytes=r[0])):dict(owner=owner,
                session=str(uuid.UUID(bytes=r[1])),status=r[2],completed_at=r[3],
                workspace=str(uuid.UUID(bytes=r[4]))) for r in rows}
            active.update(str(uuid.UUID(bytes=r[1])) for r in rows if r[2]=='running')
    for number,path in enumerate(sorted(root.glob('*/*/processes/*.jsonl'))):
        if number % 64 == 0:guard()
        before = logs.regular(path)
        with path.open('rb') as stream:header=stream.read(len(logs.MAGIC))
        if logs.is_archive_header(header):continue
        relative=str(path.relative_to(root));session=path.parent.parent.name
        bindings=[rows[path.stem] for rows in snapshots.values() if path.stem in rows]
        reason='eligible_closed';sides=[]
        if not bindings or any(b['session']!=session for b in bindings):reason='unbound'
        elif len({b['workspace'] for b in bindings})!=1:reason='ambiguous_workspace'
        elif session in active:reason='active_session'
        elif any(b['status']not in ('completed','failed','killed')or b['completed_at']is None for b in bindings):reason='nonterminal'
        elif now_ns()-before.st_mtime_ns < minimum_age_seconds*10**9:reason='recent_capture'
        else:
            try:
                sides=logs.sidecars(path)
                captures=[json.loads(raw) for ext,raw,_ in sides if ext=='capture.json']
                if len(captures)!=1 or captures[0].get('capture_state')!='closed':reason='pending_capture'
            except (OSError,ValueError,AttributeError):reason='invalid_capture'
        if logs.version(logs.regular(path))!=logs.version(before):reason='changed_capture'
        row=dict(path=relative,version=logs.version(before),bytes=before.st_size,
                 allocated_bytes=before.st_blocks*512,bindings=bindings,reason=reason,
                 sidecars=[dict(path=str(path.with_suffix('.'+ext)),version=identity,sha256=logs.sha(raw))for ext,raw,identity in sides])
        observed.append(row)
        if reason=='eligible_closed':eligible.append(row)
    guard()
    return dict(source_root=str(root),files=observed,eligible=eligible)


def partition(rows, *, maximum_files=32, maximum_bytes=512*1024**2):
    if not 1 <= maximum_files <= 64 or not 1 <= maximum_bytes <= 2*1024**3:
        raise ValueError('Bounded forward transaction limits required')
    groups=[];seen=set()
    for row in sorted(rows,key=lambda r:r['path']):
        if row['path']in seen or row['reason']!='eligible_closed' or not 0<=row['bytes']<=maximum_bytes:
            raise ValueError('Unique eligible bounded forward selection required')
        seen.add(row['path']);parent=str(Path(row['path']).parent)
        if not groups or groups[-1]['parent']!=parent or len(groups[-1]['rows'])==maximum_files or groups[-1]['bytes']+row['bytes']>maximum_bytes:
            groups.append(dict(parent=parent,rows=[],bytes=0))
        groups[-1]['rows'].append(row);groups[-1]['bytes']+=row['bytes']
    return groups


def prepare(selected, root, databases, folder, *, guard):
    root,folder=Path(root),Path(folder)
    if folder.exists()or folder.resolve()!=folder or folder.is_relative_to(root):
        raise ValueError('New isolated forward preparation required')
    batches=partition(selected)
    if len(batches)!=1:raise ValueError('Exactly one bounded session transaction required')
    guard()
    for owner,database in databases.items():check_bindings(database,selected,owner)
    source_rows=[];entries=[]
    for row in selected:
        path=logs.safe_path(root,row['path'])
        if logs.version(logs.regular(path))!=row['version']:raise ValueError('Selected raw version changed')
        with path.open('rb')as stream:
            if logs.is_archive_header(stream.read(len(logs.MAGIC))):raise ValueError('Selected raw became an archive')
        sides=logs.sidecars(path)
        if row['sidecars']!=[dict(path=str(path.with_suffix('.'+ext)),version=identity,sha256=logs.sha(raw))for ext,raw,identity in sides]:
            raise ValueError('Selected capture metadata changed')
        digest=reclaim.file_hash(path)
        if logs.version(logs.regular(path))!=row['version']:raise ValueError('Selected raw changed while hashing')
        source_rows.append(dict(row,sha256=digest,raw_sha256=digest,raw_bytes=row['bytes']))
        entries.append(dict(path=row['path'],identity=row['version'],raw_bytes=row['bytes'],sha256=digest,
                            sidecars=[dict(extension=ext,sha256=logs.sha(raw),identity=identity)for ext,raw,identity in sides]))
    folder.mkdir(mode=0o700);reclaim.sync_directory(folder.parent)
    plan=dict(source_root=str(root),files=entries);parent=logs.safe_path(root,entries[0]['path']).parent
    reuse=[]
    for path in sorted(parent.glob('*.jsonl')):
        with path.open('rb')as stream:header=stream.read(len(logs.MAGIC))
        if header==logs.PACKED_MAGIC:reuse.append(path)
    # Bound index memory and scan work; actual selected references are fully
    # decoded and hashed in the new prepared histories before any publication.
    reuse=reuse[-256:]
    prepared=folder/'packed';proof=packed_forward.prepare(plan,prepared,reuse=reuse)
    guard();reference=folder/'SOURCE_GROUP.json'
    write_new(reference,dict(number=0,destination=str(prepared),source_rows=source_rows))
    group=compile_group(dict(path=str(reference),sha256=reclaim.file_hash(reference)),str(root),databases)
    new_allocated=sum(p.stat().st_blocks*512 for p in prepared.glob('*.jsonl'))
    live_store=parent/'.log-packs'
    for p in (prepared/'.log-packs').glob('*.pack'):
        if not(live_store/p.name).exists():new_allocated+=p.stat().st_blocks*512
    if not live_store.exists():new_allocated+=(prepared/'.log-packs').stat().st_blocks*512
    original_allocated=sum(r['allocated_bytes']for r in selected)
    outcome=dict(group=group,preparation=proof,beneficial=new_allocated<original_allocated,
                 original_allocated_bytes=original_allocated,new_live_file_allocation_bytes=new_allocated,
                 staging_and_parent_directory_growth_excluded=True,source_mutations=False)
    write_new(folder/'PREPARED.json',outcome);return outcome
