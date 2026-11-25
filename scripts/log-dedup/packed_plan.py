"""Read-only migration plans and scoped integration with existing live owners."""
import base64
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import uuid

import log_dedup as logs
import packed_objects
from packed_admission import pinned, NormalPreparedRecovery
from packed_publication import PackedBatch, PinnedReaders, stable
import reclaim
from scoped_fence import ClosedLogFence, WriterRoster
from online_owner import LiveReaders


def check_bindings(database, rows, owner):
    with closing(sqlite3.connect(Path(database).as_uri()+'?mode=ro',uri=True,timeout=2)) as db:
        db.execute('pragma query_only=on');db.execute('begin')
        for row in rows:
            wanted = next((r for r in row['bindings'] if r['owner'] == owner), None)
            actual = db.execute('''select e.session_id,e.status,e.completed_at,s.workspace_id
                from execution_processes e join sessions s on s.id=e.session_id where e.id=?''',
                (uuid.UUID(Path(row['path']).stem).bytes,)).fetchone()
            if wanted is None:
                if actual is not None:
                    raise logs.ArchiveError('A new database owner appeared')
            elif actual != (uuid.UUID(wanted['session']).bytes,wanted['status'],wanted['completed_at'],
                             uuid.UUID(wanted['workspace']).bytes):
                raise logs.ArchiveError('Selected SQL binding changed')


def split_group(reference):
    """Keep prepared packs intact while bounding each independent transaction."""
    rows = pinned(reference)['source_rows']
    if not rows or len({r['path'] for r in rows}) != len(rows):
        raise logs.ArchiveError('Unique nonempty prepared selection required')
    result, selected, size = [], [], 0
    for row in rows:
        n = row['raw_bytes']
        if type(n) is not int or not 0 <= n <= 2*1024**3:
            raise logs.ArchiveError('Single history exceeds scoped transaction bound')
        if selected and (len(selected) == 64 or size+n > 2*1024**3):
            result.append(selected);selected=[];size=0
        selected.append(row['path']);size+=n
    if selected:result.append(selected)
    return result


def compile_group(reference, source_root, databases, selected_paths=None):
    group = pinned(reference)
    root, prepared = Path(source_root), Path(group['destination'])
    rows = group['source_rows']
    if selected_paths is not None:
        if not selected_paths or len(set(selected_paths)) != len(selected_paths):
            raise logs.ArchiveError('Unique bounded subset required')
        rows = [r for r in rows if r['path'] in set(selected_paths)]
        if {r['path'] for r in rows} != set(selected_paths):
            raise logs.ArchiveError('Transaction includes a foreign prepared history')
    if not 1 <= len(rows) <= 64 or sum(r['raw_bytes'] for r in rows) > 2*1024**3:
        raise logs.ArchiveError('Prepared group exceeds scoped transaction bounds')
    for owner, database in databases.items():check_bindings(database, rows, owner)
    common = set(databases)
    for row in rows:common &= {r['owner'] for r in row['bindings']}
    owner = next((o for o in ('main','protected') if o in common), None)
    if owner is None:raise logs.ArchiveError('No common exact database binding')
    workspaces = {r['workspace'] for row in rows for r in row['bindings']}
    if len(workspaces) != 1:raise logs.ArchiveError('Group crosses workspace ownership')
    entries, sealed_rows, packs, sidecars = [], [], {}, []
    for row in rows:
        path = logs.safe_path(root,row['path'])
        if logs.version(path.stat()) != row['version'] or reclaim.file_hash(path) != row['sha256']:
            raise logs.ArchiveError('Original differs from accepted packing source')
        meta = reclaim.metadata_for(path)
        actual = logs.sidecars(path)
        expected = {s['path']:(s['version'],s['sha256'])for s in row['sidecars']}
        observed = {str(path.with_suffix('.'+ext)):(identity,logs.sha(raw))for ext,raw,identity in actual}
        if expected != observed:raise logs.ArchiveError('Sidecars changed after packing')
        if len([1 for ext,raw,_ in actual if ext=='capture.json'and json.loads(raw)['capture_state']=='closed'])!=1:
            raise logs.ArchiveError('Closed capture required')
        entries.append(dict(path=row['path'],identity=row['version'],raw_bytes=row['raw_bytes'],sha256=row['raw_sha256'],
                            sidecars=[dict(extension=ext,sha256=logs.sha(raw),identity=identity)for ext,raw,identity in actual]))
        manifest = packed_objects.load_manifest(prepared/path.name)
        if (manifest['raw_bytes'],manifest['sha256']) != (row['raw_bytes'],row['raw_sha256']):
            raise logs.ArchiveError('Prepared history differs from original')
        for pack in logs.physical_objects(prepared/path.name,manifest):
            if pack.name in packs:continue
            if reclaim.file_hash(pack) != pack.stem:raise logs.ArchiveError('Prepared pack changed')
            packs[pack.name]=dict(sha256=pack.stem,bytes=pack.stat().st_size)
        sealed_rows.append(dict(path=row['path'],original=stable(path.stat()),metadata=meta,
                                original_sha256=row['sha256'],packed_sha256=reclaim.file_hash(prepared/path.name)))
        for ext,raw,identity in actual:
            side=path.with_suffix('.'+ext)
            sidecars.append(dict(path=str(side.relative_to(root)),sha256=logs.sha(raw),version=identity,
                                 metadata=reclaim.metadata_for(side),body_base64=base64.b64encode(raw).decode()))
    plan=dict(source_root=str(root),files=entries)
    key=logs.sha(reclaim.canonical(plan))
    return dict(number=group['number'],plan=plan,plan_sha256=key,workspace_id=next(iter(workspaces)),
                database=databases[owner],databases=databases,source_rows=rows,sidecar_recovery=sidecars,
                prepared=str(prepared),files=sealed_rows,packs=packs)


def migrate_group(group, journal, readers, recovery, *, reserve_bytes, checkpoint=lambda phase,path:None):
    """Inert until actual new serving readers and the held B adapter qualify.

    No service actions or scheduling. The finite controller owns its single run
    lease/dispatch journal; this function owns only the existing scoped locks.
    """
    if not isinstance(readers,LiveReaders) or not isinstance(recovery,NormalPreparedRecovery):
        raise logs.ArchiveError('Actual live-reader and normal recovery adapters required')
    plan=group['plan']
    if (Path(plan['source_root']) != readers.source
            or recovery.mapping['groups'].get(group['plan_sha256']) != group):
        raise logs.ArchiveError('Migration differs from actual reader root or B-restored plan')
    for owner,database in group['databases'].items():
        name = 'protected5650' if owner == 'protected' else owner
        if not any(m['source'] == database for m in readers.config['readers'][name]['mounts']):
            raise logs.ArchiveError('Migration database is outside the actual serving mounts')
    if logs.sha(reclaim.canonical(plan))!=group['plan_sha256']:
        raise logs.ArchiveError('Migration plan binding differs')
    def owners():
        readers.check()
        for owner,database in group['databases'].items():check_bindings(database,group['source_rows'],owner)
    owners()
    pins=PinnedReaders([dict(pid=r['server_pid'],sha256=r['sha256'])for r in readers.config['readers'].values()],owners)
    main=readers.config['readers']['main']
    writer=WriterRoster([dict(pid=main['server_pid'],sha256=main['sha256'])],owners)
    fence=ClosedLogFence(root=plan['source_root'],database=group['database'],workspace_id=group['workspace_id'],plan=plan,roster=writer)
    batch=PackedBatch(plan,group['prepared'],journal,fence,pins,recovery,reserve_bytes=reserve_bytes)
    with fence.held():
        # Completed retirement is reconciled, never published again.
        if not (Path(journal)/'RETIRED.json').exists():batch.publish(checkpoint)
        result=batch.retire(checkpoint)
        owners();recovery.check()
        return result
