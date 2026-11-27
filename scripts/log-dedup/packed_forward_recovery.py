"""Recover a prepared forward group through the existing normal-B context.

Only new manifest/pack bodies are captured. Identical existing B bodies retain
unchanged selectors; a newly restored mapping records their new names/metadata.
No publication, schedule, source mutation, transport or backup epoch replacement.
"""
import copy
from pathlib import Path

import log_dedup as logs
from packed_admission import CheckpointCatalog, NormalPreparedRecovery
import packed_recovery as checkpoints
import reclaim


def recover(prepared, folder, prior_index, operation, recovery, capture, *, guard):
    if not prepared['beneficial']:
        raise ValueError('Nonbeneficial raw history must be preserved')
    folder = Path(folder)
    if folder.exists() or folder.resolve()!=folder:
        raise FileExistsError('Existing recovery requires reconciliation; no replay')
    group = prepared['group'];guard()
    base = CheckpointCatalog(prior_index)
    # Prior aliases are references for old prepared names, not prerequisites
    # that keep their disposable staging copies alive forever. Canonical points
    # remain available by their immutable checkpoint sources and content hashes.
    lookup = {}
    for name,row in base.rows.items():
        member=row['point']['member'];lookup.setdefault((member['sha256'],member['bytes']),name)
    source=Path(group['prepared'])
    names={str(source/Path(r['path']).name)for r in group['files']}
    names.update(str(source/'.log-packs'/name)for name in group['packs'])
    rows=[];aliases=[];metadata=[]
    for name in sorted(names):
        path=Path(name);st=logs.regular(path)
        row=dict(path=name,bytes=st.st_size,sha256=reclaim.file_hash(path),version=logs.version(st))
        metadata.append(dict(row,metadata=reclaim.metadata_for(path)))
        old=lookup.get((row['sha256'],row['bytes']))
        if old is None:rows.append(row)
        else:aliases.append(dict(checkpoint_source=old,expected=row))
    folder.mkdir(mode=0o700);reclaim.sync_directory(folder.parent)
    index=copy.deepcopy(prior_index)
    index['packed_files']=list(index['packed_files']);index['checkpoints']=list(index['checkpoints'])
    new=[];proof_paths=[]
    for number,batch in enumerate(checkpoints.batches(rows,maximum=24*1024**2)):
        guard();name=f'PACKED_FORWARD_{number:04d}';verified=capture(batch,name)
        checkpoints.verify_scope(verified['checkpoint'],batch)
        actual=verified['actual_independent_normal_restore']
        if (not actual['independent_owner_controls_restore_verified']
                or not actual['normal_leased_consumer_entrypoint_verified']):
            raise ValueError('Actual independent new-body restore required')
        path=folder/(name+'_ACCEPTED.json');checkpoints.write_new(path,verified)
        ref=dict(name=name,path=str(path),sha256=reclaim.file_hash(path),index_reference=verified['checkpoint']['index_reference'])
        index['checkpoints'].append(ref);index['packed_files'].extend(batch);new.append(ref);proof_paths.append(path)
    mapping=dict(format='vk-packed-publication-mapping-v1',operation=operation,
                 source_root=group['plan']['source_root'],groups={group['plan_sha256']:group},
                 prepared_aliases=aliases,prepared_metadata=metadata,no_live_mutations=True)
    mapping_path=folder/'MAPPING.json';index_path=folder/'INDEX.json'
    checkpoints.write_new(mapping_path,mapping);checkpoints.write_new(index_path,index)
    controls=[dict(path=str(p),bytes=p.stat().st_size,sha256=reclaim.file_hash(p))for p in [mapping_path,index_path,*proof_paths]]
    if any(r['bytes']>24*1024**2 for r in controls):raise ValueError('Bounded forward recovery mapping required')
    # Both remain independently addressable immutable normal-B points.
    verified=capture(controls,'FORWARD_MAPPING')
    checkpoints.verify_scope(verified['checkpoint'],controls)
    restored=NormalPreparedRecovery.read_mapping(recovery,verified['checkpoint'],str(mapping_path),reclaim.file_hash(mapping_path))
    restored_index=NormalPreparedRecovery.read_mapping(recovery,verified['checkpoint'],str(index_path),reclaim.file_hash(index_path))
    if restored!=mapping or restored_index!=index:raise ValueError('Actual normal-B mapping/index differs')
    catalog=CheckpointCatalog(restored_index);catalog.add_aliases(restored['prepared_aliases'])
    adapter=NormalPreparedRecovery(catalog,recovery,restored,guard)
    sealed={k:group[k]for k in ['plan_sha256','prepared','files','packs']}
    proof=adapter(sealed);guard()
    result=dict(actual_current_normal_B_bytes_verified=True,new_body_files=len(rows),
                new_body_bytes=sum(r['bytes']for r in rows),reused_body_files=len(aliases),
                reused_body_bytes=sum(a['expected']['bytes']for a in aliases),
                prepared_metadata_recovered_from_B=True,new_body_checkpoints=new,
                mapping_checkpoint=verified['checkpoint'],mapping_sha256=reclaim.file_hash(mapping_path),
                index_sha256=reclaim.file_hash(index_path),admission=proof,source_mutations=False)
    checkpoints.write_new(folder/'RECOVERED.json',result)
    return adapter,result
