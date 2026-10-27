"""Finite qualification of unresolved map names; all growing state stays on B.

The caller owns map/catalog/source leases, current normal journal barriers,
resource admission and native adoption. Completed map states are never scanned
or hashed again. A resumed controller supplies its committed exact-name cursor;
a failed batch may retry only its still-unadopted points.
"""
import hashlib
from pathlib import Path

from vk_nightly_current_map import decode_member
from vk_nightly_inode_journal import require_full_coverage
from vk_nightly_qualification import qualify_file


def qualify_selected(current,*,journal,adopt,guard,maximum_paths,maximum_source_bytes,
                     after='',checkpoint_cursor=lambda _:None,on_progress=lambda _:None):
    if (type(maximum_paths) is not int or maximum_paths<1
            or type(maximum_source_bytes) is not int or maximum_source_bytes<1):
        raise ValueError('finite qualification path/read admission required')
    current.check();db=current.db
    if not db.execute('select complete from metadata').fetchone()[0]:raise ValueError('finish namespace before selected qualification')
    last=after;processed=hashed=read_ceiling=retained=pending=deferred=SQL=0
    def result(more):
        return dict(processed=processed,last_name=last,more_names=more,completed_source_hash_bytes=hashed,
            admitted_source_read_upper_bound=read_ceiling,retained_body_matches=retained,qualified_pending_bodies=pending,
            deferred_points=deferred,SQL_API_sources_discovered=SQL,source_namespace_paths_enumerated=0,
            backup_payload_bytes_copied=0,current_baseline_accepted=False)
    while processed<maximum_paths:
        guard();current.check()
        batch=db.execute("select name,row from members where state in ('file-needs-qualification','current-namespace-replay-required') and name>? order by name limit ?",
                         (last,min(64,maximum_paths-processed))).fetchall()
        if not batch:break
        report=journal();require_full_coverage(report);records=[];budget_stop=False
        for name,raw in batch:
            guard();path=Path('/'+name)
            try:size=path.lstat().st_size
            except FileNotFoundError:size=0
            # This ceiling counts an unsuccessful full hash attempt too. The
            # separately reported successful-hash bytes are not called total IO.
            if read_ceiling+size>maximum_source_bytes:budget_stop=True;break
            read_ceiling+=size
            try:
                point=qualify_file(path,maximum_bytes=max(1,size),journal=report,carriers=lambda *_:[],guard=guard)
            except (ValueError,FileNotFoundError) as error:
                point=dict(source=str(path),state='current-version-deferred',reason=str(error),
                    journal={k:report[k] for k in ('instance','sequence','scope_sha256','plan_sha256')},original_epoch_repaired=False)
            else:hashed+=point['source_payload_bytes_hashed']
            records.append(dict(name=name,original_sha256=hashlib.sha256(raw).hexdigest(),version=point))
        if records:
            accepted=adopt(records);processed+=len(records);last=records[-1]['name']
            retained+=accepted['retained_body_matches'];pending+=accepted['qualified_pending_bodies']
            deferred+=accepted['deferred_points'];SQL+=accepted['SQL_API_sources_discovered']
            value=result(True);checkpoint_cursor(value);on_progress(value)
        if budget_stop:return result(True)
    more=db.execute("select 1 from members where state in ('file-needs-qualification','current-namespace-replay-required') and name>? limit 1",(last,)).fetchone() is not None
    return result(more)
