"""Cold workspace references in ordinary Nightly current-map/SQL acceptance.

No archive body capture, live SQL writes, scheduler, or metadata exclusions are
created here. Physical archive removal reaches the existing change journal in
its normal way. This module verifies that the current map contains no old cold
payload and that a separately restored current SQL image retains the exact
accepted recovery catalog. The externally pinned selection binds that catalog.
"""
import hashlib
import json
from pathlib import PurePosixPath
import uuid


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',', ':'),ensure_ascii=False).encode()).hexdigest()


def records(db):
    result=[]
    rows=db.execute('''SELECT s.workspace_id,s.phase,s.request_version,s.operation_id,
        r.requested_state,r.request_version,w.archived,w.pinned,g.manifest_sha256,g.manifest,g.recovery_locator
        FROM workspace_archive_state s
        LEFT JOIN workspace_archive_requests r USING(workspace_id)
        LEFT JOIN workspaces w ON w.id=s.workspace_id
        LEFT JOIN workspace_archive_generations g ON g.workspace_id=s.workspace_id
          AND g.request_version=s.request_version AND g.operation_id=s.operation_id
        WHERE s.phase!='active' ORDER BY s.workspace_id''').fetchall()
    for wid,phase,version,operation,requested,current,archived,pinned,sha,raw,locator in rows:
        if (phase!='cold' or requested!='archived' or current!=version or archived!=1 or pinned!=0
                or raw is None or hashlib.sha256(raw.encode()).hexdigest()!=sha):
            raise ValueError('workspace archive/revival is incomplete or its recovery catalog differs')
        checks=(
            'SELECT 1 FROM workspace_archive_reads WHERE workspace_id=?',
            "SELECT 1 FROM workspace_archive_inputs WHERE workspace_id=? AND state NOT IN ('dispatched','cancelled')",
            "SELECT 1 FROM execution_processes e JOIN sessions s ON s.id=e.session_id WHERE s.workspace_id=? AND e.status='running'",
            "SELECT 1 FROM turn_github_sync_incoming WHERE workspace_id=? AND state NOT IN ('handled','dismissed')",
            'SELECT 1 FROM turn_github_sync_user_queue WHERE workspace_id=?',
            'SELECT 1 FROM watcher_job_leases WHERE workspace_id=? AND closed_at IS NULL',
            """SELECT 1 FROM scratch d JOIN sessions s ON s.id=d.id WHERE s.workspace_id=?
               AND d.scratch_type='DRAFT_FOLLOW_UP' AND (NOT json_valid(d.payload)
               OR coalesce(json_extract(d.payload,'$.type'),'')!='DRAFT_FOLLOW_UP'
               OR coalesce(json_type(d.payload,'$.data.message'),'null') NOT IN ('text','null')
               OR trim(coalesce(json_extract(d.payload,'$.data.message'),''))!='')""")
        if any(db.execute(query,(wid,)).fetchone() for query in checks):
            raise ValueError('cold workspace has pending input or a live owner')
        manifest=json.loads(raw)
        value=dict(workspace_id=str(uuid.UUID(bytes=wid)),request_version=version,
                   operation_id=operation,manifest_sha256=sha,manifest=manifest,recovery_locator=json.loads(locator))
        if any(manifest.get(key)!=value[key] for key in ('workspace_id','request_version','operation_id')):
            raise ValueError('cold manifest has another workspace/generation')
        result.append(value)
    return result


def contract(selection):
    selection.check()
    return dict(format='vk-nightly-cold-workspace-catalog-v1',database=str(selection.database),
        required_active_sources=selection.required,cold_generations=len(selection.references),
        cold_generations_sha256=digest(selection.references),excluded_roots=dict(sorted(selection.roots.items())))


def validate(value):
    if value.get('format')!='vk-nightly-cold-workspace-catalog-v1':
        raise ValueError('qualified cold-workspace contract required')
    paths=[value['database'],*value['required_active_sources'],*value['excluded_roots']]
    if any(not isinstance(p,str) or str(PurePosixPath(p))!=p or not p.startswith('/')
           or p=='/' or '..'in PurePosixPath(p).parts for p in paths):
        raise ValueError('exact canonical current workspace paths required')
    if value['database'] not in value['required_active_sources']:
        raise ValueError('current SQL/catalog is a mandatory active recovery source')
    for required in value['required_active_sources']:
        if any(PurePosixPath(required).is_relative_to(root) for root in value['excluded_roots']):
            raise ValueError('active SQL/shared dependency was excluded')


def check_map(db,value,*,guard):
    validate(value)
    for root in value['excluded_roots']:
        guard();name=root[1:]
        # Indexed exact/range checks; neither LIKE wildcards nor a full rescan.
        if db.execute('SELECT 1 FROM members WHERE name=? OR (name>=? AND name<?) LIMIT 1',
                      (name,name+'/',name+'0')).fetchone():
            raise ValueError('current Nightly map still contains physically archived payload')
    for path in value['required_active_sources']:
        guard()
        row=db.execute('SELECT state FROM members WHERE name=?',(path[1:],)).fetchone()
        if row is None or row[0] not in ('directory','symlink','verified-file'):
            raise ValueError('current SQL/catalog/shared dependency missing from Nightly map')


def check_restored_sql(db,value):
    validate(value)
    actual=records(db)
    roots={root:row['workspace_id'] for row in actual for root in row['manifest']['payloads']['roots']}
    if (len(actual)!=value['cold_generations'] or digest(actual)!=value['cold_generations_sha256']
            or roots!=value['excluded_roots']):
        raise ValueError('independently restored current SQL lost or changed cold recovery references')
    return dict(cold_generations=len(actual),cold_generations_sha256=digest(actual),
                body_bytes_recaptured=0,current_SQL_cold_catalog_verified=True)


def open_selection(reference,guard):
    """Load only the installed, SHA-pinned archive bridge, never backup content."""
    import importlib.util
    import os
    from pathlib import Path
    import stat
    import sys
    entry=reference['entry'];path=Path(entry['path']);before=path.lstat()
    if (path.name!='driver.py' or not path.is_absolute() or path.resolve(strict=True)!=path
            or not stat.S_ISREG(before.st_mode) or before.st_uid!=os.getuid()
            or before.st_nlink!=1 or before.st_mode & 0o022):
        raise ValueError('owned canonical archive bridge entry required')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=entry['sha256'] or path.lstat()!=before:
        # atime can change after read, so compare the stable fields below.
        after=path.lstat()
        fields=('st_dev','st_ino','st_size','st_mode','st_mtime_ns','st_ctime_ns','st_uid','st_gid','st_nlink')
        if (hashlib.sha256(raw).hexdigest()!=entry['sha256']
                or any(getattr(before,k)!=getattr(after,k)for k in fields)):
            raise ValueError('archive bridge source changed')
    spec=importlib.util.spec_from_file_location('driver',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    value,actual=module.configuration(reference['configuration']['path'])
    if actual!=reference['configuration']:
        raise ValueError('exact installed archive configuration required')
    folder=str(path.parent)
    if folder not in sys.path:sys.path.insert(0,folder)
    # Every archive module was verified by configuration() before import.
    for name in module.MODULES:
        loaded=sys.modules.get(name[:-3])
        if loaded is not None and Path(loaded.__file__).resolve()!=path.with_name(name):
            raise ValueError('foreign archive implementation already loaded')
    import nightly_binding
    return nightly_binding.open_selection(reference['configuration'],guard)
