"""Build a typed current descriptor from an authenticated immutable B map.

The trusted installed consumer supplies scope, original gap dispositions,
carrier identities, SQL requirements and runtime pins. Only retained metadata
is read. This never declares backup/restore acceptance or enables scheduling;
the independent ordinary reader must validate the descriptor and its bodies.
"""
import hashlib
import json
import math

from vk_nightly_current_map import (SealedMemberIndex, SQL_aliases, decode_member,
                                    pending_replay_for_epoch)
from vk_nightly_control_format import key
from vk_nightly_checkpoints import digest,source_path
from vk_typed_recovery import FORMAT,HeldRecoverySet,canonical,checksum,validate_member


def sample_runtime_files(paths,*,maximum_bytes,checkpoint):
    """Independently hash only the finite always-sampled source dependencies.

    These stable source points are not kernel-coverage or backup-body proofs.
    Actual guarded capture/readback and immutable component adoption are separate.
    """
    from vk_nightly_file_version import capture_version
    from vk_nightly_qualification import HashOnly
    if (not isinstance(paths,list) or not paths or len(paths)!=len(set(paths))
            or type(maximum_bytes) is not int or maximum_bytes<1):
        raise ValueError('explicit finite runtime source read budget required')
    for path in paths:source_path(path)
    files={};total=0
    for path in sorted(paths):
        checkpoint();point=capture_version(path,HashOnly(),maximum_bytes=max(1,maximum_bytes-total),guard=checkpoint)
        total+=point['bytes']
        if total>maximum_bytes:raise ValueError('finite runtime source read budget exceeded')
        files[path]=dict(kind='file',bytes=point['bytes'],sha256=point['sha256'],source_identity=point['source_identity'],
            Linux_metadata=point['metadata'],source_observed_at=point['completed_at'])
    return dict(format='vk-nightly-finite-runtime-source-points-v1',files=files,files_sampled=len(files),
        source_payload_bytes_hashed=total,global_source_paths_scanned=0,backup_payload_bytes_copied=0,
        kernel_journal_coverage_claimed=False,current_baseline_accepted=False)


def journal_evidence(database,*,checkpoint):
    record=database.execute('select binding,complete,suffix_complete from namespace_reconciliation where id=1').fetchone()
    if not record or record[1:]!=(1,1):raise ValueError('complete current namespace and durable suffix required')
    binding=json.loads(record[0]);instance=binding['instance'];start=binding['start_sequence']
    if type(start) is not int or start<0 or not instance:raise ValueError('actual source epoch/sequence required')
    if pending_replay_for_epoch(database,instance) is not None:raise ValueError('current journal replay remains unfinished')
    cursor=start;count=0;chain=hashlib.sha256()
    for sha,since,through,summary in database.execute(
            "select sha256,since,through,summary from namespace_replay_windows where complete=1 "
            "and json_extract(summary,'$.instance')=? order by since,through,sha256",(instance,)):
        checkpoint();digest(sha);summary=json.loads(summary)
        if (since!=cursor or type(through) is not int or through<since
                or summary.get('window_sha256')!=sha or summary.get('since')!=since or summary.get('through')!=through
                or summary.get('journal_suffix_complete_through')!=through
                or summary.get('original_epoch_repaired') is not False):
            raise ValueError('retained journal chain has a gap or inconsistent cursor')
        pieces=[];size=0
        for number,(part,data) in enumerate(database.execute(
                'select part,data from namespace_replay_inputs where sha256=? order by part',(sha,))):
            checkpoint()
            if not isinstance(data,bytes):raise ValueError('retained journal input is not bytes')
            size+=len(data)
            if part!=number or not 0<len(data)<=65536 or size>16*1024**2:
                raise ValueError('bounded complete retained journal input required')
            pieces.append(data)
        raw=b''.join(pieces)
        if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('retained journal input hash differs')
        value=json.loads(raw);report=value['report'];replay=value['replay'];barrier=report.get('barrier',{})
        if (any(report.get(k)!=binding.get(k) for k in ('instance','scope_sha256','plan_sha256'))
                or report.get('coverage_model')!='all-selected-inodes-v1' or report.get('ready') is not True
                or report.get('errors')!=[] or report.get('terminal') or report.get('since')!=since or report.get('sequence')!=through
                or barrier.get('kernel_drain_completed') is not True or barrier.get('durable_sequence')!=through
                or barrier.get('instance')!=instance or replay.get('since')!=since or replay.get('through')!=through
                or replay.get('required_root_bindings')!=binding['required_root_bindings']):
            raise ValueError('actual full-inode retained barrier differs')
        chain.update(canonical(dict(sha256=sha,since=since,through=through))+b'\n');count+=1;cursor=through
    if not count:raise ValueError('actual independently retained journal window required')
    return dict(instance=instance,scope_sha256=binding['scope_sha256'],start=start,end=cursor,errors=[],
                event_closure_verified=True,retained_window_count=count,retained_window_chain_sha256=chain.hexdigest(),
                original_epoch_repaired=False),binding


def build(database,reference,contract,*,checkpoint):
    if contract.get('format')!='vk-nightly-current-recovery-contract-v1':raise ValueError('explicit installed consumer contract required')
    digest(contract['plan_sha256']);digest(contract['scope_sha256'])
    required=contract['sources'];original=contract['original_sources'];SQL=contract['required_SQL'];pins=contract['required_pins']
    for values in (required,original,SQL):
        if not isinstance(values,list) or len(values)!=len(set(values)):raise ValueError('unique explicit consumer source set required')
        for path in values:source_path(path)
    if not set(original)<=set(required) or set(contract['original_source_dispositions'])!=set(original):
        raise ValueError('original required roots/dispositions must remain explicit')
    original_epoch=contract['original_epoch']
    if (original_epoch.get('complete') is not False or original_epoch.get('original_gaps_repaired') is not False
            or type(original_epoch.get('unresolved_gap_count')) is not int or original_epoch['unresolved_gap_count']<0):
        raise ValueError('honest original-epoch gap disposition required')
    digest(original_epoch['gap_manifest_sha256']);digest(original_epoch['accepted_restore_proof_sha256'])
    journal,binding=journal_evidence(database,checkpoint=checkpoint)
    if (any(binding.get(k)!=contract[k] for k in ('plan_sha256','scope_sha256'))
            or set(binding['required_root_bindings'])!=set(required)):
        raise ValueError('consumer source roots/plan differ from actual journal namespace')
    if (reference.get('format')!='vk-nightly-current-member-map-v1'
            or type(reference.get('bytes')) is not int or reference['bytes']<=0):
        raise ValueError('authenticated immutable current-map reference required')
    digest(reference['sha256']);key(reference['selector'])
    SQL_points={};sidecars={};aliases=SQL_aliases(database)
    request=contract.get('current_SQL_request')
    qualification=None
    if request is not None:
        # The installed consumer obtains this exact request through an
        # independent normal B reopen of the SQL phase, never a live-source
        # list or a boolean saying that old points are current.
        wanted=digest(request['cohort_id'])
        if checksum({k:v for k,v in request.items() if k!='cohort_id'})!=wanted:
            raise ValueError('current SQL request digest differs')
        rb=request['binding'];selected=request['sources'];all_sources=request['SQL_scope_sources']
        always=request['always_SQL_API_sources']
        if (request.get('format')!='vk-nightly-current-SQL-cohort-request-v1'
                or rb.get('source_instance')!=binding['instance']
                or any(rb.get(k)!=binding[k] for k in ('plan_sha256','scope_sha256'))
                or rb.get('source_root_bindings')!=binding['required_root_bindings']
                or any(not isinstance(v,list) or len(v)!=len(set(v)) for v in (selected,all_sources,always))
                or set(all_sources)!=set(SQL) or not set(always)<=set(selected)<=set(all_sources)
                or not set(aliases.values())<=set(always)
                or request.get('unchanged_SQL_points_reused')!=len(set(all_sources)-set(selected))
                or set(contract.get('always_SQL_API_sources',[]))!=set(always)):
            raise ValueError('current SQL request scope/epoch/mandatory API binding differs')
        qualification=dict(format='vk-nightly-current-SQL-qualification-v1',cohort_id=wanted,
            selected_sources=sorted(selected),unchanged_sources=sorted(set(all_sources)-set(selected)),
            always_SQL_API_sources=sorted(always),source_instance=binding['instance'])
    for name,raw in database.execute("select m.name,m.row from members m join SQL_sources s on s.path='/'||m.name where m.state!='symlink' order by m.name"):
        checkpoint();value=decode_member(raw);point=value.get('SQL_point');source='/'+name
        if not point or source not in SQL:raise ValueError('current SQL point missing or outside exact consumer cohort: '+source)
        member=value.get('member',{});proof=point.get('independent',{});epoch=point.get('original_source_API_point_at')
        if (point.get('source')!=source or point.get('status')!='consistent_SQL_point_verified'
                or point.get('method')!='SQLite-backup-API' or point.get('source_API_point_qualifies_later_epoch_not_original') is not True
                or type(epoch) not in (int,float) or not math.isfinite(epoch) or epoch<=0
                or proof.get('integrity')!='ok' or any(point.get(k)!=member.get(k) or proof.get(k)!=member.get(k) for k in ('bytes','sha256'))):
            raise ValueError('complete independently accepted SQL API point required: '+source)
        if qualification and source in qualification['selected_sources'] and point.get('SQL_cohort_id')!=qualification['cohort_id']:
            raise ValueError('selected SQL point does not belong to the independently reopened current request: '+source)
        SQL_points[source]=dict(bytes=member['bytes'],sha256=member['sha256'],method='SQLite-backup-API',integrity='ok',
            epoch=dict(original_source_API_point_at=epoch,later_than_original_failed_archive=True),
            independent_proof_sha256=digest(point['B_acceptance_object']['sha256']))
        if point.get('SQL_cohort_id') is not None:
            SQL_points[source]['SQL_cohort_id']=digest(point['SQL_cohort_id'])
    if set(SQL_points)!=set(SQL):raise ValueError('exact independently accepted SQL cohort is incomplete')
    for name,raw in database.execute("select name,row from members where state='SQLite-sidecar' order by name"):
        source=decode_member(raw)['required_SQL_source']
        if source not in SQL_points:raise ValueError('sidecar has no actual consistent SQL target')
        sidecars[name]=dict(source=source,snapshot_sha256=SQL_points[source]['sha256'])
    explicit_always=contract.get('always_SQL_API_sources',[])
    if (not isinstance(explicit_always,list) or len(explicit_always)!=len(set(explicit_always))
            or not set(explicit_always)<=set(SQL_points)):
        raise ValueError('always-current SQL API dependencies must have captured target points')
    always_SQL=sorted(set(explicit_always)|set(aliases.values()))
    alias_proofs={}
    for name,target in aliases.items():
        if target not in SQL_points:raise ValueError('SQL alias lacks its independently accepted resolved target')
        alias_proofs[name]=dict(source=target,snapshot_sha256=SQL_points[target]['sha256'])
    reference=dict(reference,consistent_SQL_sidecars=sidecars,consistent_SQL_aliases=alias_proofs)
    index=SealedMemberIndex(database,checkpoint,reference)
    runtime=contract.get('always_runtime_files',{})
    if index.runtime_components!=runtime:raise ValueError('actual finite runtime component contract differs')
    h=hashlib.sha256();count=0;layers={reference['layer']};roots=set()
    from functools import lru_cache
    lookup=lru_cache(maxsize=8192)(index._entry)
    for name,row in index.entries():
        validate_member(name,row,lookup)
        if row['kind']=='file':
            if 'pending_content_request' in row or 'prefix_segments' in row:raise ValueError('unsealed current content request')
            segments=row.get('segments',[dict(layer='accepted-base',selector=name,bytes=row['bytes'],sha256=row['sha256'])])
            if not isinstance(segments,list) or not segments or sum(s['bytes'] for s in segments)!=row['bytes']:
                raise ValueError('complete current body recipe required')
            for segment in segments:layers.add(segment['layer'])
        absolute='/'+name
        if absolute in required:roots.add(absolute)
        h.update(canonical(dict(name=name,entry=row))+b'\n');count+=1
        if count%1024==0:checkpoint()
    if roots!=set(required):raise ValueError('complete current required root coverage missing')
    if not layers<=set(contract['dependencies']):raise ValueError('authenticated carrier dependency missing')
    for path,pin in pins.items():
        source_path(path);row=index.entry(path[1:])
        if row.get('kind') not in ('file','hardlink') or any(row.get(k)!=pin[k] for k in ('bytes','sha256')):
            raise ValueError('current runtime pin missing or changed')
    checkpoint()
    descriptor=dict(format=FORMAT,source_prefix='/',plan_sha256=contract['plan_sha256'],scope_sha256=contract['scope_sha256'],
        sources=required,original_source_dispositions=contract['original_source_dispositions'],original_epoch=original_epoch,
        original_epoch_complete=False,writer_fence_verified=False,dependencies=contract['dependencies'],indexes=[reference],
        bounded_delta_start_sequence=journal['end'],
        member_count=count,member_map_sha256=h.hexdigest(),SQLite=SQL_points,journal=journal,
        root_aliases=contract.get('root_aliases',{}),always_runtime_files=runtime,always_SQL_API_sources=always_SQL,
        installed_consumer_contract_sha256=checksum(contract),
        independent_current_restore_accepted=False,scheduling_authorized=False)
    if qualification is not None:descriptor['current_SQL_qualification']=qualification
    # Reuse the ordinary complete-member validator for scope, recipes, root
    # aliases, SQL and pins. This metadata-only interface cannot open bodies or
    # assert dependency leases/readability; the independent consumer still must.
    class MetadataContract:
        identities=contract['dependencies']
        def check(self):checkpoint()
    handle=HeldRecoverySet(descriptor,checksum(descriptor),MetadataContract(),index)
    handle.validate(plan_sha256=contract['plan_sha256'],scope_sha256=contract['scope_sha256'],
        required_sources=required,original_sources=original,required_pins=pins,required_SQL=SQL,
        required_root_aliases=contract.get('root_aliases',{}),required_runtime_files=runtime,
        required_SQL_qualification=qualification)
    return descriptor
