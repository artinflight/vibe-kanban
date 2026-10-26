"""Resumable metadata-only namespace reconciliation after a proven journal gap.

Ordinary Nightly cycles never invoke this walk. Completed directories are
checkpointed on native B and not enumerated again. An interrupted directory
may be listed again; already committed metadata is updated, never body-copied.
Concurrent disappearance/change remains an explicit replay error. Complete
enumeration is not body, journal-suffix or whole-baseline acceptance.
"""
import json
import os
from pathlib import Path
import stat

from vk_nightly_namespace import observe
from vk_nightly_tracking import source_bindings
from vk_nightly_qualification import encode_observation
from vk_rolling_backup import Exclusions
from vk_prep_common import identity
from vk_change_journal import scope


def initialize(db,plan,anchor):
    if not anchor['ready'] or anchor['errors'] or anchor.get('terminal'):raise ValueError('ready source observer required')
    roots=source_bindings(plan)
    if any(v is None for v in roots.values()):raise ValueError('required source root absent; explicit disposition needed')
    binding=dict(plan_sha256=identity(plan),scope_sha256=identity(scope(plan)),instance=anchor['instance'],
                 start_sequence=anchor['sequence'],required_root_bindings=roots,original_epoch_repaired=False)
    if (anchor['plan_sha256'],anchor['scope_sha256'])!=(binding['plan_sha256'],binding['scope_sha256']):
        raise ValueError('journal/source namespace plan differs')
    db.execute('create table if not exists gap_meta(id integer primary key,binding text not null,complete integer not null)')
    old=db.execute('select binding from gap_meta where id=1').fetchone()
    if old:
        recorded=json.loads(old[0])
        if any(recorded[k]!=binding[k] for k in ('plan_sha256','scope_sha256','instance','required_root_bindings')):
            raise ValueError('observer/scope/root changed; preserve old reconciliation and begin explicit successor')
        return recorded
    exclusions=Exclusions(plan)
    targets=sorted({v['resolved'] for v in roots.values()})
    minimal=[]
    for target in targets:
        if not any(Path(target).is_relative_to(p) for p in minimal):minimal.append(target)
    db.execute('begin immediate')
    try:
        db.execute('create table gap_pending(path text primary key,done integer not null) without rowid')
        db.execute('create index gap_pending_done on gap_pending(done,path)')
        db.execute('create table namespace(name text primary key,row blob not null) without rowid')
        db.execute('create table namespace_errors(name text primary key,error blob not null) without rowid')
        db.execute('create table gap_stats(id integer primary key,unique_paths integer not null)')
        db.execute('insert into gap_stats values(1,0)')
        db.execute('insert into gap_meta values(1,?,0)',(json.dumps(binding,sort_keys=True,separators=(',',':')),))
        db.executemany('insert into gap_pending values(?,0)',((p,) for p in minimal if not exclusions(p)))
        for raw,value in roots.items():
            if value['literal'] is not None and not exclusions(raw):
                db.execute('insert or replace into namespace values(?,?)',(raw[1:],encode_observation(observe(raw))))
        db.execute('update gap_stats set unique_paths=(select count(*) from namespace) where id=1')
        db.execute('commit')
    except BaseException:
        if db.in_transaction:db.execute('rollback')
        raise
    return binding


def directory_records(path,exclusions):
    """Yield anchored metadata/error rows; never open a source body."""
    path=Path(path)
    try:
        value=observe(path);yield ('row',str(path)[1:],encode_observation(value),False)
        if value['kind']!='directory':return
        fd=opened_directory(path)
        try:
            before=os.fstat(fd)
            if [before.st_dev,before.st_ino]!=value['identity'][:2]:raise ValueError('directory changed before anchored enumeration')
            with os.scandir(fd) as listing:
                for entry in listing:
                    child=path/entry.name
                    if exclusions(child):continue
                    try:
                        row=observe(Path('/proc/self/fd')/str(fd)/entry.name)
                        yield ('row',str(child)[1:],encode_observation(row),row['kind']=='directory')
                    except (OSError,ValueError) as error:
                        yield ('error',str(child)[1:],encode_observation(dict(type=type(error).__name__,reason=str(error),errno=getattr(error,'errno',None),requires_explicit_replay=True)),False)
            current=path.lstat()
            if (current.st_dev,current.st_ino)!=(before.st_dev,before.st_ino):raise ValueError('directory path changed during enumeration')
        finally:os.close(fd)
    except (OSError,ValueError) as error:
        yield ('error',str(path)[1:],encode_observation(dict(type=type(error).__name__,reason=str(error),errno=getattr(error,'errno',None),requires_explicit_replay=True)),False)


def advance_B(client,key,plan,binding,*,guard,maximum_directories,maximum_paths,on_progress=lambda _:None):
    """Coarse native transactions avoid one network round trip per file/dir."""
    if type(maximum_directories) is not int or maximum_directories<1 or type(maximum_paths) is not int or maximum_paths<1:
        raise ValueError('finite metadata reconciliation admission required')
    exclusions=Exclusions(plan);directories=0;rows=[];children=[];errors=[];done=[];latest={}
    def flush():
        nonlocal rows,children,errors,done,latest
        if not (rows or errors or done):return
        guard();exclusions.validate()
        latest=client.call(op='namespace-batch',name=key,rows=rows,children=children,errors=errors,
                           completed=done,maximum_paths=maximum_paths)
        rows=[];children=[];errors=[];done=[]
    while directories<maximum_directories:
        guard();exclusions.validate()
        paths=client.call(op='namespace-next',name=key,limit=min(512,maximum_directories-directories))['paths']
        if not paths:break
        for path in paths:
            guard()
            for kind,member,row,is_directory in directory_records(path,exclusions):
                (rows if kind=='row' else errors).append((member,row))
                if is_directory:children.append('/'+member)
                if len(rows)+len(errors)>=128:flush()
            done.append(path);directories+=1
        flush();on_progress(dict(latest,directories_this_phase=directories,last_directory=paths[-1]))
    flush()
    result=client.call(op='namespace-statistics',name=key)
    if not result['pending_directories']:
        if source_bindings(plan)!=binding['required_root_bindings']:raise ValueError('required roots/aliases changed; preserve and reconcile')
        client.call(op='execute',name=key,sql='update gap_meta set complete=1 where id=1',parameters=[])
    return dict(result,enumeration_complete=not result['pending_directories'],directories_this_phase=directories,
                source_body_bytes_read=0,backup_payload_bytes_copied=0,work_SSD_index_bytes=0,
                journal_suffix_required=True,current_baseline_accepted=False,original_epoch_repaired=False)


def opened_directory(path):
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
    try:
        for part in Path(path).parts[1:]:
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=child
        return fd
    except BaseException:os.close(fd);raise


def advance(db,plan,binding,*,guard,maximum_directories,maximum_paths,on_progress=lambda _:None):
    if type(maximum_directories) is not int or maximum_directories<1 or type(maximum_paths) is not int or maximum_paths<1:
        raise ValueError('finite metadata reconciliation admission required')
    exclusions=Exclusions(plan);directories=0;observations=0
    total=db.execute('select count(*) from namespace').fetchone()[0]
    def checkpoint():
        guard();exclusions.validate()
        if total>maximum_paths:raise ValueError('measured namespace exceeds admitted path bound; preserve cursor')
    def batch(rows,children,errors):
        nonlocal total,observations
        checkpoint();db.execute('begin immediate')
        try:
            added=db.executemany('insert or ignore into namespace values(?,?)',rows).rowcount
            if total+max(0,added)>maximum_paths:raise ValueError('measured namespace exceeds admitted path bound')
            db.executemany('update namespace set row=? where name=?',((raw,name) for name,raw in rows))
            db.executemany('insert or ignore into gap_pending values(?,0)',((p,) for p in children))
            db.executemany('insert into namespace_errors values(?,?) on conflict(name) do update set error=excluded.error',errors)
            checkpoint();db.execute('commit')
        except BaseException:
            if db.in_transaction:db.execute('rollback')
            raise
        total+=max(0,added);observations+=len(rows)
    while directories<maximum_directories:
        checkpoint();next_=db.execute('select path from gap_pending where done=0 order by path limit 1').fetchone()
        if next_ is None:break
        path=Path(next_[0]);rows=[];children=[];errors=[]
        def error(name,e):errors.append((str(name).lstrip('/'),encode_observation(dict(type=type(e).__name__,reason=str(e),errno=getattr(e,'errno',None),requires_explicit_replay=True))))
        try:
            value=observe(path);rows.append((str(path)[1:],encode_observation(value)))
            if value['kind']=='directory':
                fd=opened_directory(path)
                try:
                    before=os.fstat(fd)
                    if [before.st_dev,before.st_ino]!=value['identity'][:2]:raise ValueError('directory changed before anchored enumeration')
                    with os.scandir(fd) as listing:
                        for entry in listing:
                            child=path/entry.name
                            if exclusions(child):continue
                            try:
                                # The proc FD anchors all parent components;
                                # a concurrent parent symlink cannot redirect
                                # these metadata reads outside the opened dir.
                                record=observe(Path('/proc/self/fd')/str(fd)/entry.name)
                                rows.append((str(child)[1:],encode_observation(record)))
                                if record['kind']=='directory':children.append(str(child))
                            except (OSError,ValueError) as e:error(child,e)
                            if len(rows)+len(errors)>=128:
                                batch(rows,children,errors);rows=[];children=[];errors=[]
                    current=path.lstat()
                    if (current.st_dev,current.st_ino)!=(before.st_dev,before.st_ino):raise ValueError('directory path changed during enumeration')
                finally:os.close(fd)
        except (OSError,ValueError) as e:error(path,e)
        if rows or errors:batch(rows,children,errors)
        db.execute('update gap_pending set done=1 where path=?',(str(path),));directories+=1
        if directories%256==0:on_progress(dict(directories_this_phase=directories,unique_paths=total,metadata_observations_this_phase=observations,last_directory=str(path)))
    checkpoint()
    complete=db.execute('select 1 from gap_pending where done=0 limit 1').fetchone() is None
    if complete:
        if source_bindings(plan)!=binding['required_root_bindings']:raise ValueError('required roots/aliases changed; preserve and reconcile')
        db.execute('update gap_meta set complete=1 where id=1')
    return dict(phase='gap-namespace-enumerated' if complete else 'gap-namespace-partial',enumeration_complete=complete,
        unique_paths=total,directories_this_phase=directories,metadata_observations_this_phase=observations,
        replay_errors=db.execute('select count(*) from namespace_errors').fetchone()[0],
        source_body_bytes_read=0,backup_payload_bytes_copied=0,work_SSD_index_bytes=0,
        original_epoch_repaired=False,journal_suffix_required=True,current_baseline_accepted=False)
