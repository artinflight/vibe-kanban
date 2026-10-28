"""Normal B finalization: ready map -> accepted immutable image -> proof closure.

The caller owns the finite cycle/admission and supplies exact retained map,
catalogs and externally prepared recovery contract. Existing normal protocols
seal/read back metadata on B and authenticate all body recipes. No source
inventory, source body capture, baseline-pointer promotion or calendar occurs.
The independent composed consumer must still accept the returned packet.
"""
from contextlib import ExitStack
import json

from vk_nightly_current_map import FORMAT,READY,decode_member,runtime_components
from vk_typed_recovery import checksum


def bind_SQL_scope(client,current_map,contract,request,*,guard):
    """Freeze a journal-derived SQL scope against a separate normal map read.

    The installed template explicitly authorizes this discovery within its
    exact tracked roots. Neither a descriptor nor the SQL producer alone may
    choose a smaller scope. The final contract contains the full concrete
    list and independently reopened cohort, never the discovery placeholder.
    """
    if contract.get('SQL_scope_authority')!='authenticated-current-map-and-cohort-v1':
        return
    if contract.get('required_SQL') is not None:
        raise ValueError('late-bound SQL contract must not override a concrete required scope')
    guard();db=client.connect(current_map['index_name'],current_map['checkpoint_sha256'],readonly=True,working=True)
    try:
        row=db.execute('select binding,complete,suffix_complete from namespace_reconciliation where id=1').fetchone()
        if not row or row[1:]!=(1,1):raise ValueError('complete authenticated current SQL namespace required')
        namespace=json.loads(row[0]);binding=request['binding']
        if (checksum({k:v for k,v in request.items() if k!='cohort_id'})!=request['cohort_id']
                or binding.get('source_instance')!=namespace.get('instance')
                or binding.get('source_root_bindings')!=namespace.get('required_root_bindings')
                or set(namespace.get('required_root_bindings',{}))!=set(contract['sources'])
                or any(binding.get(k)!=contract[k] or namespace.get(k)!=contract[k]
                       for k in ('plan_sha256','scope_sha256'))):
            raise ValueError('independent SQL scope/namespace/installed root contract differs')
        rows=db.execute("select s.path,m.state from SQL_sources s left join members m on m.name=substr(s.path,2) and s.path='/'||m.name order by s.path").fetchall()
        if not rows or len(rows)>1024 or any(state is None for _,state in rows):
            raise ValueError('finite complete independently reopened SQL source membership required')
        required=[path for path,state in rows if state!='symlink']
        if (len(required)!=len(set(required)) or set(required)!=set(request['SQL_scope_sources'])
                or len(request['SQL_scope_sources'])!=len(required)):
            raise ValueError('SQL request omitted or added current map sources')
        contract['required_SQL']=required
    finally:db.close()
    guard()


def bind_runtime_scope(client,current_map,contract,result,*,guard):
    """Freeze finite runtime references from a separately reopened main map.

    The installed template supplies exact source hashes/lengths and the phase
    supplies its sealed component digest. Neither can widen the required set.
    Actual point/proof references are decoded from the adopted B records.
    """
    authority=contract.get('runtime_scope_authority')
    if authority not in (None,'authenticated-runtime-component-v1'):
        raise ValueError('unsupported runtime binding authority')
    if authority is None:
        if result.get('always_runtime_files')!=contract.get('always_runtime_files',{}):
            raise ValueError('actual adopted runtime component differs from external consumer contract')
        return
    if contract.get('always_runtime_files') is not None:
        raise ValueError('late-bound runtime contract must not override concrete references')
    expected=contract['required_runtime_points'];reference=result['component_reference']
    if not expected or len(expected)>16 or result.get('actual_independent_B_runtime_component_reopen_verified') is not True:
        raise ValueError('finite independently reopened runtime component required')
    guard();db=client.connect(current_map['index_name'],current_map['checkpoint_sha256'],readonly=True,working=True)
    try:
        def lookup(name):
            row=db.execute('select state,row from members where name=?',(name,)).fetchone()
            if not row or row[0]!='verified-file':raise ValueError('adopted runtime member missing')
            return decode_member(row[1])['member']
        actual=runtime_components(db,lookup)
        if set(actual)!=set(expected) or actual!=result['always_runtime_files']:
            raise ValueError('independent runtime membership/references differ')
        for path,point in actual.items():
            if (any(point[k]!=expected[path][k] for k in ('kind','bytes','sha256'))
                    or point['component_index_sha256']!=reference['sha256']):
                raise ValueError('runtime point differs from installed source pins/sealed component')
        contract['always_runtime_files']=actual
    finally:db.close()
    guard()


def finalize(client,*,current_map,map_layer,contract,cycle_binding,base_catalog,recipe_catalogs,
             SQL_phase=None,runtime_phase=None,guard,report=lambda _:None):
    guard();contract=json.loads(json.dumps(contract))
    if contract.get('runtime_scope_authority') and runtime_phase is None:
        raise ValueError('independently reopened runtime phase required')
    if runtime_phase is not None:bind_runtime_scope(client,current_map,contract,runtime_phase,guard=guard)
    if len(recipe_catalogs)>8:raise ValueError('finite explicit proof catalogs required')
    if (contract.get('required_SQL') or contract.get('SQL_scope_authority')) and SQL_phase is None:
        raise ValueError('independently reopened current SQL request required')
    if SQL_phase is not None:
        view=client.connect(SQL_phase['index_name'],SQL_phase['checkpoint_sha256'],readonly=True,working=True)
        try:
            # Working read must name the actual SQL phase, not an empty or
            # another cohort's seed. Its native binding is checked by open().
            row=view.execute('select row from SQL_cycle_request where id=1').fetchone()
            if not row:raise ValueError('current SQL cohort request is missing')
            actual=json.loads(row[0])
            bind_SQL_scope(client,current_map,contract,actual,guard=guard)
            if (checksum({k:v for k,v in actual.items() if k!='cohort_id'})!=actual['cohort_id']
                    or set(actual['SQL_scope_sources'])!=set(contract['required_SQL'])
                    or actual['binding'].get('map_index')!=current_map['index_name']
                    or actual['binding'].get('map_checkpoint_sha256')!=current_map['checkpoint_sha256']
                    or any(actual['binding'].get(k)!=contract[k] for k in ('plan_sha256','scope_sha256'))
                    or ('always_SQL_API_sources' in contract and
                        set(contract['always_SQL_API_sources'])!=set(actual['always_SQL_API_sources']))
                    or contract.get('current_SQL_request') not in (None,actual)):
                raise ValueError('independent SQL request/required scope differs')
            contract['current_SQL_request']=actual
            contract['always_SQL_API_sources']=actual['always_SQL_API_sources']
        finally:view.close()
    contract_sha=checksum(contract)
    db=client.connect(current_map['index_name'],current_map['checkpoint_sha256'])
    try:
        if db.execute('select format,complete from metadata').fetchall()!=[(FORMAT,1)]:
            raise ValueError('complete retained map required before sealing')
        if db.execute('select complete,suffix_complete from namespace_reconciliation where id=1').fetchone()!=(1,1):
            raise ValueError('complete retained journal suffix required before sealing')
        states=dict(db.execute('select state,count(*) from members group by state'))
        unresolved={k:n for k,n in states.items() if k not in (*READY,'SQLite-sidecar')}
        if unresolved:raise ValueError('unresolved required map points; no new checkpoint: '+json.dumps(unresolved,sort_keys=True))
        sealed=client.seal_checkpoint(db.key,dict(cycle=cycle_binding,consumer_contract_sha256=contract_sha),
            on_progress=lambda n:report(dict(phase='immutable-current-map-independent-readback',bytes_read=n)))
    finally:db.close()
    reference=dict(format=FORMAT,layer=map_layer,selector=sealed['sha256']+'.sqlite',
        sha256=sealed['sha256'],bytes=sealed['bytes'])
    with ExitStack() as stack:
        def opened(name,sha):
            db=client.connect(name,sha,readonly=True);stack.callback(db.close);return db
        current=opened('final-current-map',sealed['sha256'])
        descriptor=current.request('build-current-descriptor',reference=reference,consumer_contract=contract)
        if contract.get('dependency_selection_authority')=='sealed-map-recipes-v1':
            selected=descriptor['dependencies']
            if any(name not in contract['dependencies'] or value!=contract['dependencies'][name]
                   for name,value in selected.items()):
                raise ValueError('descriptor selected an unauthenticated provider')
            contract['dependencies']=selected
        if descriptor['installed_consumer_contract_sha256']!=checksum(contract):
            raise ValueError('sealed descriptor/effective consumer contract differs')
        base=opened('final-base-catalog',base_catalog['checkpoint_sha256'])
        catalogs=[opened('final-recipe-'+str(n),r['checkpoint_sha256']) for n,r in enumerate(recipe_catalogs)]
        proof=current.request('audit-current-content',reference=reference,base_index=base.key,
                              recipe_indexes=[d.key for d in catalogs])
        guard()
    def catalog_ref(ref):
        return dict(sha256=ref['checkpoint_sha256'],selector=ref['checkpoint_sha256']+'.sqlite',bytes=ref['bytes'])
    expected=dict(base=catalog_ref(base_catalog),recipes=[catalog_ref(r) for r in recipe_catalogs])
    if (proof['base_catalog_reference']!=expected['base'] or proof['recipe_catalog_references']!=expected['recipes']):
        raise ValueError('actual immutable proof catalogs differ from installed contract')
    return dict(format='vk-nightly-finalized-current-candidate-v1',sealed_map=sealed,
        descriptor=descriptor,descriptor_sha256=checksum(descriptor),consumer_contract=contract,
        consumer_contract_sha256=checksum(contract),sealed_template_contract_sha256=contract_sha,
        content_proof=proof,content_proof_sha256=checksum(proof),
        expected_catalogs=expected,cycle_binding=cycle_binding,
        whole_baseline_accepted=False,independent_consumer_still_required=True,schedule_enabled=False,
        source_payload_bytes_read=0,OS_SSD_payload_or_index_bytes=0)


def consumer_packet(candidate,*,provider_placement,readback_sources,scratch_parent,
                    maximum_scratch_bytes,maximum_readback_bytes,remaining_seconds,
                    whole_cycle_deadline_UTC,Linux_resource_admission,readback_scope_authority=None):
    if candidate.get('format')!='vk-nightly-finalized-current-candidate-v1':raise ValueError('actual finalized current candidate required')
    fields=('descriptor','descriptor_sha256','consumer_contract','consumer_contract_sha256',
            'content_proof','content_proof_sha256','expected_catalogs')
    if candidate['consumer_contract'].get('dependency_selection_authority')=='sealed-map-recipes-v1':
        selected=set(candidate['consumer_contract']['dependencies'])
        provider_placement=json.loads(json.dumps(provider_placement))
        for field in ('roots','root_bindings','lease_paths'):
            if not selected<=set(provider_placement[field]):
                raise ValueError('selected provider lacks independently admitted placement/lease')
            provider_placement[field]={k:v for k,v in provider_placement[field].items() if k in selected}
    if readback_scope_authority is not None:
        if readback_scope_authority!='effective-contract-mandatory-v1':
            raise ValueError('unsupported composed readback selection authority')
        if not isinstance(readback_sources,list):raise ValueError('explicit supplemental readback list required')
        contract=candidate['consumer_contract']
        readback_sources=sorted(set(readback_sources)|set(contract['required_pins'])
            |set(contract.get('always_runtime_files',{}))|set(candidate['descriptor']['always_SQL_API_sources']))
        if len(readback_sources)>256:raise ValueError('finite mandatory composed readback scope exceeded')
    return dict({k:candidate[k] for k in fields},format='vk-nightly-composed-consumer-packet-v1',
        provider_placement=provider_placement,readback_sources=readback_sources,scratch_parent=scratch_parent,
        maximum_scratch_bytes=maximum_scratch_bytes,maximum_readback_bytes=maximum_readback_bytes,
        remaining_seconds=remaining_seconds,whole_cycle_deadline_UTC=whole_cycle_deadline_UTC,
        Linux_resource_admission=Linux_resource_admission)
