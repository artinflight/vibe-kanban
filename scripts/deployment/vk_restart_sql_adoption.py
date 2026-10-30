"""Guarded old-epoch SQL reuse from an independently restored catch-up.

No CLI, schedule, service controls or source writes. The final-update owner calls
this only inside its real writer fence; standalone previews never adopt. Every
adoption uses the existing native acceptance-object decoder and preserves the
old API epoch. An error retains the draft and requires another genuine suffix.
"""
import hashlib
import json
from pathlib import Path

from vk_restart_sql_sidecar_reuse import canonical, qualify_sidecar_source


def load_checkpoint(reference):
    path = Path(reference['path'])
    if not path.is_absolute() or path.resolve() != path:
        raise ValueError('Canonical exact catch-up acceptance receipt required')
    with path.open('rb') as stream:raw = stream.read(8*1024**2+1)
    if len(raw) > 8*1024**2 or hashlib.sha256(raw).hexdigest() != reference['sha256']:
        raise ValueError('Catch-up acceptance receipt changed or exceeded bound')
    value = json.loads(raw);candidate = value.get('candidate', {});packet = value.get('consumer_packet', {});restore = value.get('normal_restore', {})
    if (value.get('recovery_checkpoint_verified') is not True or value.get('accepted_current_pointer_modified') is not False
            or value.get('live_later_changes_not_claimed_backed_up') is not True
            or value.get('all_old_recovery_retained') is not True
            or not all(restore.get(k) is True for k in ('normal_leased_consumer_entrypoint_verified',
                'independent_composed_restore_verified', 'actual_existing_B_backed_consumer_route_verified'))
            or restore.get('consumer_packet_sha256') != hashlib.sha256(canonical(packet)).hexdigest()):
        raise ValueError('Actual normal leased independent catch-up restore required')
    for name in ('descriptor', 'consumer_contract', 'content_proof'):
        sha = hashlib.sha256(canonical(candidate.get(name))).hexdigest()
        if (candidate.get(name+'_sha256') != sha or packet.get(name) != candidate.get(name)
                or packet.get(name+'_sha256') != sha or restore.get(name+'_sha256') != sha):
            raise ValueError('Catch-up descriptor/contract/content proof bindings differ')
    reference_map = candidate['descriptor']['indexes'][0]
    if (reference_map['sha256'] != candidate['sealed_map']['sha256']
            or reference_map['bytes'] != candidate['sealed_map']['bytes']):
        raise ValueError('Exact independently restored immutable map required')
    request = candidate['consumer_contract']['current_SQL_request']
    if request['binding']['source_instance'] != candidate['descriptor']['journal']['instance']:
        raise ValueError('Catch-up SQL and source epochs differ')
    return value


def open_accepted_SQL_map(client, reference):
    """Open the immutable accepted map using a native-valid, read-only handle."""
    return client.connect('sql-reuse-accepted-catchup', reference['sha256'], readonly=True)


def adopt_unchanged_SQL(client, settings, worker, source, *, guard, report=lambda _:None):
    """Called after the physical fence, before the original SQL selector.

    The caller retains native controls, metadata lane, exact source RPC and
    writer-fence guards. This advances a real suffix, then requalifies only the
    selected old cohort. The original selector captures every refused source.
    """
    from vk_nightly_b_controls import tracking_store
    from vk_nightly_current_map import decode_member
    from vk_nightly_incremental import advance_suffix
    from vk_nightly_inode_journal import require_full_coverage
    from vk_nightly_outbox_export import retained_prefix_report
    from vk_nightly_metadata_replay import stage_input, load_input
    accepted = load_checkpoint(settings['accepted_checkpoint'])
    candidate = accepted['candidate'];request = candidate['consumer_contract']['current_SQL_request']
    if (request['cohort_id'] != settings['expected_SQL_cohort_id']
            or request['binding']['source_instance'] != source.reference['instance']
            or request['binding']['map_index'] != worker['B_index_name']
            or request['binding']['map_checkpoint_sha256'] != worker['B_checkpoint_sha256']):
        raise ValueError('Exact catch-up cohort, current draft and source required')
    guard();source.check();source.deliver()
    target = source.config['B_delivery_target']
    delta = advance_suffix(client,index_name=worker['B_index_name'],checkpoint_sha256=worker['B_checkpoint_sha256'],
        journal_name=target['index_name'],journal_checkpoint_sha256=target['checkpoint_sha256'],plan=source.plan,
        maximum_paths=settings['maximum_delta_paths'],maximum_journal_bytes=worker['B_controls']['maximum_index_bytes'],guard=guard,on_progress=report)
    ref = candidate['descriptor']['indexes'][0]
    baseline = open_accepted_SQL_map(client, ref)
    try:
        rows = baseline.execute("select s.path,m.row from SQL_sources s cross join members m on m.name=substr(s.path,2) and s.path='/'||m.name where m.state!='symlink' order by s.path").fetchall()
        sidecar_rows = baseline.execute("select name,row from members where state='SQLite-sidecar' order by name").fetchall()
        if len(rows) > 1024 or len(sidecar_rows) > 4096:
            raise ValueError('Bounded actual immutable SQL scope required')
        sidecar_map = {'/'+name:decode_member(raw) for name,raw in sidecar_rows}
        with tracking_store(client,target['index_name'],target['checkpoint_sha256'],maximum_bytes=worker['B_controls']['maximum_index_bytes']) as ledger:
            journal = retained_prefix_report(ledger,source.config['endpoint'],source.reference['instance'],request['metadata_delta']['through'],guard=guard)
            require_full_coverage(journal)
            if journal['sequence'] < delta['through']:
                raise ValueError('Complete SQL reuse history must include actual current suffix')
            selected = [];refused = []
            for path, raw in rows:
                guard();baseline.request('check');point=decode_member(raw).get('SQL_point', {})
                sides={suffix:sidecar_map.get(path+suffix) for suffix in ('-wal','-journal')}
                proof=qualify_sidecar_source(path,point,sides,request,journal,guard=guard)
                if proof['eligible_unchanged_SQL_reuse']:selected.append((path,point,sides,proof))
                else:refused.append(dict(source=path,reason=proof['reason']))
            db=client.connect(worker['B_index_name'],worker['B_checkpoint_sha256'])
            try:
                binding=dict(format='vk-staging-old-SQL-epoch-reuse-v1',accepted_checkpoint_sha256=settings['accepted_checkpoint']['sha256'],
                    immutable_map_sha256=ref['sha256'],SQL_cohort_id=request['cohort_id'],proofs=[p for _,_,_,p in selected])
                staged=stage_input(db,journal,dict(SQL_epoch_reuse=binding),guard=guard)
                if load_input(db,staged,guard=guard)!={'report':journal,'replay':{'SQL_epoch_reuse':binding}}:
                    raise ValueError('Independent staged B SQL reuse input differs')
                db.execute('create table if not exists staging_SQL_epoch_reuse(source text,point_sha256 text,staged_input_sha256 text,proof text,primary key(source,point_sha256,staged_input_sha256)) without rowid')
                adopted=[];already=[]
                for path,point,sides,proof in selected:
                    guard();source.check();baseline.request('check')
                    if not qualify_sidecar_source(path,point,sides,request,journal,guard=guard)['eligible_unchanged_SQL_reuse']:
                        raise ValueError('SQL source changed before adoption; preserve draft and replay next genuine suffix')
                    current=db.execute('select state,row from members where name=?',(path[1:],)).fetchone()
                    if not current:continue
                    if current[0]=='verified-file':already.append(path);continue
                    if current[0]!='SQLite-needs-image':
                        raise ValueError('SQL reuse cannot replace unrelated current state')
                    client.call(op='accept-SQL-point',name=worker['B_index_name'],record=point)
                    if not qualify_sidecar_source(path,point,sides,request,journal,guard=guard)['eligible_unchanged_SQL_reuse']:
                        raise ValueError('SQL source changed after adoption; no final acceptance')
                    db.execute('insert or ignore into staging_SQL_epoch_reuse values(?,?,?,?)',
                        (path,point['B_acceptance_object']['sha256'],staged,canonical(proof).decode()))
                    adopted.append((path,point))
                post=retained_prefix_report(ledger,source.config['endpoint'],source.reference['instance'],request['metadata_delta']['through'],guard=guard)
                require_full_coverage(post)
                post_proofs=[]
                for path,point in adopted:
                    sides={suffix:sidecar_map.get(path+suffix) for suffix in ('-wal','-journal')}
                    proof=qualify_sidecar_source(path,point,sides,request,post,guard=guard)
                    if not proof['eligible_unchanged_SQL_reuse']:
                        raise ValueError('Fresh post-adoption barrier found a SQL change; no final acceptance')
                    post_proofs.append(proof)
                post_binding=dict(SQL_epoch_reuse_postcheck=dict(original_staged_input_sha256=staged,proofs=post_proofs))
                post_staged=stage_input(db,post,post_binding,guard=guard)
                if load_input(db,post_staged,guard=guard)!={'report':post,'replay':post_binding}:
                    raise ValueError('Independent staged B post-adoption barrier differs')
                db.request('check')
            finally:db.close()
    finally:baseline.close()
    # A separate normal B connection must retain the exact original API point.
    view=client.connect(worker['B_index_name'],worker['B_checkpoint_sha256'],readonly=True,working=True)
    try:
        for path,point in adopted:
            row=view.execute('select state,row from members where name=?',(path[1:],)).fetchone()
            if row[0]!='verified-file' or decode_member(row[1]).get('SQL_point')!=point:
                raise ValueError('Independent original-epoch B SQL adoption differs')
        view.request('check')
    finally:view.close()
    guard();source.check()
    return dict(format='vk-staging-unchanged-SQL-reuse-result-v1',adopted_SQL_points=len(adopted),already_accepted_points=len(already),
        accepted_API_bytes_reused=sum(point['bytes'] for _,point in adopted),refused=refused,metadata_delta=delta,
        staged_input_sha256=staged,postcheck_staged_input_sha256=post_staged,postcheck_through=post['sequence'],independent_B_SQL_epoch_reopen_verified=True,new_API_epoch_claimed=False,
        final_backup_acceptance_claimed=False,source_body_bytes_copied=0)
