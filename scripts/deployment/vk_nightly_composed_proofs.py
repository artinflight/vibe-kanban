"""Independent content-proof closure for an immutable composed B member map.

Never a source scan or a second payload copy. Every selected segment must have
an actual accepted native object, accepted-base catalog entry or authenticated
retained component. Multi-segment files need their ordered full-file readback
proof. SQL needs its decoded B acceptance record and independent integrity proof.
The caller holds immutable-index/dependency and object-store leases plus real B
admission throughout. Ordinary complete-reader/restore acceptance is separate.
"""
import hashlib
import json
from pathlib import Path
import stat

from vk_nightly_current_map import decode_member
from vk_nightly_checkpoints import digest,under


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def carrier_identity(objects,definition):
    """Native B identity check; reuse the existing full readback, not a new hash."""
    path=Path(under(definition['native_path'],'B:/vk-backups'))
    if path.resolve()!=path:raise ValueError('retained carrier path changed')
    for part in (path,*path.parents):
        info=part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:
            raise ValueError('retained carrier crosses a reparse point')
    digest(definition['sha256']);expected=definition['file_identity']
    actual=objects.file_identity(path)
    if (not isinstance(expected,list) or len(expected) not in (4,5,6)
            or actual[:len(expected)]!=expected or definition['bytes']!=actual[2]):
        raise ValueError('retained carrier identity changed; preserve and reconcile')
    return actual


def retained_ordered_proof(database,value,member,*,member_name=None):
    """Reopen an exact old ordered-body proof; preserve its original epoch.

    Earlier metadata handovers could retain the qualified recipe without the
    later explicit history hint. Resolve only that same member's immutable
    history or its authenticated completed-body index, matching the complete
    ordered recipe/hash/length. Current qualified name/metadata stay separate.
    Never infer a proof from chunk hashes or current source availability.
    """
    from vk_nightly_control_format import key
    reference=value.get('retained_carrier_reuse',{}).get('completed_file_history')
    if (value.get('qualification',{}).get('state')!='qualified-retained-body'
            or value['qualification'].get('row')!=member):
        if reference:raise ValueError('retained ordered body current qualified point differs')
        return None
    if reference:
        key(reference['name']);digest(reference['version_sha256'])
        rows=database.execute('select version_sha256,accepted_row,proof from file_acceptance_history '
            'where name=? and version_sha256=?',(reference['name'],reference['version_sha256'])).fetchall()
        if not rows:raise ValueError('retained ordered body history missing or changed')
        history_name=reference['name']
    else:
        if member_name is None:return None
        key(member_name)
        if value['qualification'].get('source')!='/'+member_name:
            raise ValueError('retained body source/member binding differs')
        if not database.execute("select 1 from sqlite_master where type='table' and name='file_acceptance_history'").fetchone():
            return None
        history_name=member_name
        rows=database.execute('select version_sha256,accepted_row,proof from file_acceptance_history '
            'where name=? order by version_sha256 limit 129',(member_name,)).fetchall()
        if len(rows)>128:raise ValueError('retained ordered body history exceeds finite reconciliation bound')
    for version,raw,encoded_proof in rows:
        if raw is None:
            if reference:raise ValueError('retained ordered body history missing or changed')
            continue  # Legacy proof without its exact recipe cannot qualify.
        digest(version)
        if hashlib.sha256(raw).hexdigest()!=version:
            raise ValueError('retained ordered body history missing or changed')
        accepted=decode_member(raw);original=accepted['member'];proof=decode_member(encoded_proof)
        matches=(original.get('kind')=='file' and
                 all(original.get(k)==member.get(k) for k in ('bytes','sha256','segments')))
        if not matches and not reference:continue
        if (not matches or accepted.get('independent_file_proof')!=proof
                or proof.get('independent_ordered_B_readback_sha256')!=member['sha256']
                or proof.get('independent_ordered_B_readback_bytes')!=member['bytes']
                or proof.get('source_metadata')!={k:original[k] for k in ('mode','uid','gid','mtime_ns','xattrs')}):
            raise ValueError('retained ordered body proof or current qualified point differs')
        return dict(history_reference=dict(name=history_name,version_sha256=version),
            original_ordered_proof_sha256=hashlib.sha256(canonical(proof)).hexdigest(),
            original_body_metadata_preserved=True,current_qualified_metadata_not_relabelled=True,
            explicit_hint_present=reference is not None)
    if reference is None and database.execute(
            "select 1 from sqlite_master where type='table' and name='completed_file_carriers'").fetchone():
        # A metadata handover may omit the old explicit hint for a duplicate
        # name. This index is only a locator: reauthenticate the complete old
        # row/proof below, never accept a hash-only chunk or infer old inclusion.
        carrier=database.execute('select row,history_name,history_version from completed_file_carriers '
            'where sha256=? and bytes=?',(member['sha256'],member['bytes'])).fetchone()
        if carrier:
            old=decode_member(carrier[0])
            if any(old.get(k)!=member.get(k) for k in ('bytes','sha256','segments')):
                return None
            located=dict(value,retained_carrier_reuse=dict(completed_file_history=
                dict(name=carrier[1],version_sha256=carrier[2])))
            proof=retained_ordered_proof(database,located,member,member_name=member_name)
            return dict(proof,explicit_hint_present=False,authenticated_completed_body_locator=True)
    return None


def audit(database,reference,*,base_catalog,recipe_catalogs,objects,objects_root,
          guard,native_carrier=None,named_components=None,base_names_catalog=None,base_names_catalog_sha256=None,progress=lambda _:None):
    """Stream one sealed map's proof closure using bounded metadata caches.

    Catalog connections are independently accepted immutable images selected by
    the installed consumer. They are not paths supplied by a recovery manifest.
    Hash chains cover file points and ordered segment references, including
    duplicate references; no unbounded in-memory content/name inventory is built.
    """
    from functools import lru_cache
    digest(reference['sha256']);objects_root=Path(objects_root)
    native_carrier=native_carrier or (lambda value:carrier_identity(objects,value))
    files=raw_bytes=segments_count=object_refs=retained_refs=base_refs=SQL_points=ordered=control_bytes=0
    file_chain=hashlib.sha256();segment_chain=hashlib.sha256()
    provenance=base_catalog.execute('select source_catalog_sha256,restore_proof_sha256 from provenance').fetchall()
    if len(provenance)!=1:raise ValueError('exact accepted-base catalog/restore provenance required')
    for value in provenance[0]:digest(value)
    if base_names_catalog is not None and digest(base_names_catalog_sha256)!=provenance[0][0]:
        raise ValueError('original accepted-base name catalog provenance differs')
    schemas=[]
    for catalog in recipe_catalogs:
        columns={r[1] for r in catalog.execute('pragma table_info(components)')}
        if {'id','definition'}<=columns:schemas.append('definitions')
        elif columns=={'layer','archive_path','archive_identity','records_sha','members','raw_bytes'}:
            schemas.append('v8i')
        else:raise ValueError('unsupported authenticated retained component catalog schema')

    @lru_cache(maxsize=256)
    def retained(layer):
        if not layer.startswith('retained-'):raise ValueError('undeclared retained carrier layer')
        identifier=digest(layer[len('retained-'):]);found=[]
        for catalog,schema in zip(recipe_catalogs,schemas):
            if schema!='definitions':continue
            row=catalog.execute('select definition from components where id=?',(identifier,)).fetchone()
            if row:found.append(json.loads(row[0]))
        if not found or any(canonical(v)!=canonical(found[0]) for v in found):
            raise ValueError('selected retained carrier is absent or ambiguous in authenticated catalogs')
        definition=found[0]
        if hashlib.sha256(canonical(definition)).hexdigest()!=identifier:
            raise ValueError('retained component definition digest differs')
        if definition.get('encoding')!='zip-member':raise ValueError('accepted retained ZIP component required')
        for item in ('archive','records'):guard();native_carrier(definition[item])
        return definition

    @lru_cache(maxsize=256)
    def v8i(layer,encoded_sha):
        digest(encoded_sha)
        if layer!='v8i-file-'+encoded_sha[:24]:raise ValueError('v8i component/full archive hash binding differs')
        found=[]
        for catalog,schema in zip(recipe_catalogs,schemas):
            if schema!='v8i':continue
            row=catalog.execute('select archive_path,archive_identity,records_sha,members,raw_bytes '
                                'from components where layer=?',(layer,)).fetchone()
            if row:found.append(row)
        if not found or any(row!=found[0] for row in found):
            raise ValueError('selected v8i component is absent or ambiguous in authenticated catalogs')
        path,identity,records_sha,members,raw_bytes=found[0];identity=json.loads(identity)
        digest(records_sha)
        if (not isinstance(identity,list) or len(identity)!=4 or type(members) is not int or members<1
                or type(raw_bytes) is not int or raw_bytes<0):
            raise ValueError('complete independently verified v8i component binding required')
        archive=dict(native_path=path,name=Path(path).name,bytes=identity[2],file_identity=identity,sha256=encoded_sha)
        guard();native_carrier(archive)
        return dict(encoding='zip-member',archive=archive,records_sha=records_sha)

    @lru_cache(maxsize=32)
    def named(layer):
        # Explicit installed contract, never a definition supplied by a member.
        import zipfile
        definition=(named_components or {}).get(layer)
        if (not isinstance(definition,dict)
                or definition.get('format')!='vk-nightly-named-ZIP-component-v1'
                or definition.get('encoding')!='zip-member'):
            raise ValueError('undeclared retained carrier layer')
        digest(definition['independent_restore_proof_sha256'])
        archive=definition['archive'];members=definition['members']
        if not isinstance(members,dict) or not members:raise ValueError('complete named ZIP member proof required')
        guard();native_carrier(archive)
        path=Path(archive['native_path']);sha=hashlib.sha256();length=0
        with path.open('rb') as stream:
            for block in iter(lambda:stream.read(1024**2),b''):
                guard();sha.update(block);length+=len(block)
            if length!=archive['bytes'] or sha.hexdigest()!=archive['sha256']:
                raise ValueError('named ZIP archive full hash differs')
            stream.seek(0)
            with zipfile.ZipFile(stream) as zipped:
                names=zipped.namelist()
                if len(names)!=len(set(names)) or set(names)!=set(members):
                    raise ValueError('named ZIP exact member set differs')
                for name,expected in members.items():
                    guard();digest(expected['sha256']);h=hashlib.sha256();size=0
                    if zipped.getinfo(name).file_size!=expected['bytes']:
                        raise ValueError('named ZIP member length differs')
                    with zipped.open(name) as body:
                        for block in iter(lambda:body.read(1024**2),b''):
                            guard();h.update(block);size+=len(block)
                    if size!=expected['bytes'] or h.hexdigest()!=expected['sha256']:
                        raise ValueError('named ZIP member full hash differs')
        guard();native_carrier(archive)
        return definition

    @lru_cache(maxsize=1024)
    def accepted(segment_raw):
        segment=json.loads(segment_raw);objects.object_segment(segment,32*1024**2);guard()
        receipt=objects.accepted_object_receipt(objects_root,segment['sha256'],segment['bytes'])
        if any(receipt.get(k)!=segment[k] for k in ('encoded_bytes','encoded_sha256')):
            raise ValueError('accepted object encoding differs from selected recipe')
        return receipt

    def segment_proof(segment):
        nonlocal object_refs,retained_refs,base_refs
        guard();layer=segment['layer'];digest(segment['sha256'])
        if type(segment['bytes']) is not int or segment['bytes']<0:raise ValueError('exact segment length required')
        if layer=='nightly-objects-v1':
            receipt=accepted(canonical(segment));object_refs+=1
            return dict(kind='accepted-native-object',receipt_sha256=hashlib.sha256(canonical(receipt)).hexdigest())
        if layer=='accepted-base':
            original_name=False
            if segment.get('encoding','raw')!='raw':raise ValueError('accepted base raw segment required')
            args=(segment['sha256'],segment['bytes'],segment['selector'])
            if not base_catalog.execute('select 1 from bodies where sha256=? and bytes=? and name=?',args).fetchone():
                # The content index deliberately deduplicates equal bytes. A
                # different original name needs the authenticated FULL source
                # catalog, not merely another matching hash/current file.
                if (base_names_catalog is None or not base_catalog.execute(
                        'select 1 from bodies where sha256=? and bytes=?',args[:2]).fetchone()
                        or not base_names_catalog.execute(
                            'select 1 from current where name=? and old_sha256=? and old_bytes=?',
                            (segment['selector'],segment['sha256'],segment['bytes'])).fetchone()):
                    raise ValueError('selected base segment is absent from accepted restore catalog: '+segment['selector'])
                original_name=True
            base_refs+=1
            return dict(kind='accepted-restored-base',restore_proof_sha256=provenance[0][1],
                original_name_catalog_sha256=base_names_catalog_sha256 if original_name else None)
        if layer.startswith('retained-SQL-'):
            raise ValueError('legacy SQL segment requires its decoded API acceptance dependency')
        component=(named(layer) if layer in (named_components or {}) else
                   v8i(layer,segment['encoded_sha256']) if layer.startswith('v8i-file-') else retained(layer))
        archive=component['archive']
        if (segment.get('encoding')!='zip-member' or segment.get('selector')!=archive['name']
                or segment.get('encoded_bytes')!=archive['bytes'] or segment.get('encoded_sha256')!=archive['sha256']):
            raise ValueError('selected retained segment/archive binding differs')
        # The immutable catalog authenticates the exact per-member record,
        # not just the archive's existence or the source's current Git object.
        if layer in (named_components or {}):
            original=component['members'].get(segment.get('member'),{})
            if any(original.get(k)!=segment[k] for k in ('bytes','sha256')):
                raise ValueError('named ZIP member differs from independently restored contract')
            retained_refs+=1
            return dict(kind='named-independent-ZIP-component',archive_sha256=archive['sha256'],
                        independent_restore_proof_sha256=component['independent_restore_proof_sha256'])
        matched=False
        for catalog in recipe_catalogs:
            for raw, in catalog.execute('select row from versions where layer=? and json_extract(row,\'$.sha256\')=? '
                    'and json_extract(row,\'$.bytes\')=?',(layer,segment['sha256'],segment['bytes'])):
                row=json.loads(raw)
                if row.get('segments')==[segment]:
                    if layer.startswith('v8i-file-'):
                        row_provenance=row.get('component_provenance',{})
                        if (row_provenance.get('archive_sha256')!=archive['sha256']
                                or row_provenance.get('record_sha256')!=component['records_sha']):
                            raise ValueError('v8i member provenance differs from immutable component binding')
                    matched=True;break
            if matched:break
        if not matched:raise ValueError('selected ZIP member has no exact independently verified catalog record')
        retained_refs+=1
        return (dict(kind='retained-v8i-independent-component',archive_sha256=archive['sha256'],
                     records_sha256=component['records_sha']) if layer.startswith('v8i-file-') else
                dict(kind='retained-independent-component',component_sha256=layer[len('retained-'):]))

    def SQL_record(point,member):
        nonlocal control_bytes
        seal=point.get('B_acceptance_object')
        if (point.get('status')!='consistent_SQL_point_verified' or point.get('method')!='SQLite-backup-API'
                or point.get('independent',{}).get('integrity')!='ok'
                or any(point.get(k)!=member[k] or point['independent'].get(k)!=member[k] for k in ('bytes','sha256'))
                or point.get('member')!=member or not isinstance(seal,dict)
                or type(seal.get('bytes')) is not int or not 0<seal['bytes']<=1024**2):
            raise ValueError('complete independently restored SQL API point required')
        accepted(canonical(seal));parts=[];length=0
        for block in objects.decoded(objects_root/seal['selector'],expected_size=seal['bytes'],
                expected_sha=seal['sha256'],encoded_sha=seal['encoded_sha256'],guard=guard):
            length+=len(block)
            if length>1024**2:raise ValueError('SQL acceptance control exceeds bound')
            parts.append(block)
        actual=json.loads(b''.join(parts));control_bytes+=length
        expected={k:v for k,v in point.items() if k not in ('B_acceptance_object','new_B_total_encoded_bytes_including_control')}
        if actual!=expected:raise ValueError('decoded B SQL acceptance record differs from selected point')
        return seal['sha256']

    progress(dict(phase='native-current-content-proof',verified_files=0,verified_raw_bytes=0))
    for name,state,raw in database.execute('select name,state,row from members order by name'):
        guard()
        if state not in ('verified-file','directory','symlink','SQLite-sidecar'):
            raise ValueError('unresolved selected recovery point: '+name+' ('+state+')')
        value=decode_member(raw)
        if state in ('directory','symlink'):
            if value.get('member',{}).get('kind')!=state:raise ValueError('non-file member state/kind differs')
            continue
        if state=='SQLite-sidecar':continue  # Exact API disposition is checked by the complete reader.
        member=value['member']
        if member['kind']!='file':raise ValueError('verified file state has a different member kind')
        recipe=member.get('segments')
        if (not isinstance(recipe,list) or not recipe or sum(p['bytes'] for p in recipe)!=member['bytes']):
            raise ValueError('complete selected file recipe required')
        proof=value.get('independent_file_proof');SQL=value.get('SQL_point');evidence={}
        if SQL is not None:
            if SQL.get('source')!='/'+name:raise ValueError('selected SQL source differs')
            evidence['SQL_acceptance_sha256']=SQL_record(SQL,member);SQL_points+=1
        if proof is not None:
            if (proof.get('independent_ordered_B_readback_sha256')!=member['sha256']
                    or proof.get('independent_ordered_B_readback_bytes')!=member['bytes']
                    or proof.get('source_metadata')!={k:member[k] for k in ('mode','uid','gid','mtime_ns','xattrs')}):
                raise ValueError('ordered file readback/hash/Linux metadata proof differs')
            evidence['ordered_file_proof_sha256']=hashlib.sha256(canonical(proof)).hexdigest();ordered+=1
        if len(recipe)>1 and not (proof or SQL):
            retained_proof=retained_ordered_proof(database,value,member,member_name=name)
            if retained_proof is None:raise ValueError('multi-segment file lacks full ordered readback proof: '+name)
            evidence['retained_ordered_file_proof']=retained_proof;ordered+=1
        if len(recipe)==1 and any(recipe[0][k]!=member[k] for k in ('bytes','sha256')):
            raise ValueError('single-segment full-file hash/length differs')
        for number,segment in enumerate(recipe):
            if segment['layer'].startswith('retained-SQL-'):
                dependency=SQL.get('dependency') if SQL else None
                image=dependency.get('legacy_image') if dependency else None
                if (not image or dependency.get('layer')!=segment['layer'] or segment.get('encoding','raw')!='raw'
                        or segment['selector']!=image['name'] or any(segment[k]!=image[k] for k in ('bytes','sha256'))
                        or segment['layer']!='retained-SQL-'+hashlib.sha256(image['native_path'].encode()).hexdigest()[:24]):
                    raise ValueError('selected legacy SQL dependency differs from actual API acceptance')
                guard();native_carrier(image);part=dict(kind='accepted-legacy-SQL',SQL_acceptance_sha256=evidence['SQL_acceptance_sha256'])
                retained_refs+=1
            else:part=segment_proof(segment)
            segment_chain.update(canonical(dict(name=name,part=number,segment=segment,proof=part))+b'\n');segments_count+=1
        file_chain.update(canonical(dict(name=name,member=member,proof=evidence))+b'\n')
        files+=1;raw_bytes+=member['bytes']
        if files%4096==0:progress(dict(phase='native-current-content-proof',verified_files=files,verified_raw_bytes=raw_bytes))
    guard()
    return dict(format='vk-nightly-independent-composed-content-proof-v1',map_reference=reference,
        file_points=files,file_raw_bytes=raw_bytes,selected_segments=segments_count,
        accepted_native_object_references=object_refs,accepted_base_references=base_refs,
        retained_component_references=retained_refs,SQL_acceptance_records_independently_decoded=SQL_points,
        ordered_file_readback_proofs_reused=ordered,SQL_control_bytes_read=control_bytes,
        file_proof_chain_sha256=file_chain.hexdigest(),segment_proof_chain_sha256=segment_chain.hexdigest(),
        source_body_bytes_read=0,new_backup_payload_bytes=0,fresh_full_body_decode_claimed=False,
        current_baseline_accepted=False,normal_complete_reader_still_required=True)
