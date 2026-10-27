"""Adopt proven points into a later explicit SQL source cohort, without copying.

The caller authenticates both native-B control providers and verifies each
acceptance object. Source cohort expansion is explicit; old records/epochs stay
in their original ledger. No live database access or baseline acceptance here.
"""
import copy


def statistics(state):
    """Separate provenance totals from this cohort's incremental work.

    Accepted records retain their original byte counts when inherited. Summing
    those as new transfer demand would falsely charge completed components.
    These are component-ledger totals, not a per-attempt socket byte counter.
    """
    inherited={name for row in state.get('inherited_SQL_points',[]) for name in row['source_names']}
    completed=state['completed'];new=[r for name,r in completed.items() if name not in inherited]
    return dict(accepted_SQL_points_inherited_without_recopy=len(inherited & set(completed)),
                new_images_in_current_cohort=len(new),
                new_B_SQL_payload_encoded_bytes=sum(r.get('new_B_encoded_payload_bytes',0) for r in new),
                source_API_image_bytes=sum(r.get('source_API_image_bytes',0) for r in new),
                accepted_SQL_payload_encoded_bytes_including_inherited_points=sum(r.get('new_B_encoded_payload_bytes',0) for r in completed.values()),
                accepted_API_image_bytes_including_inherited_points=sum(r.get('source_API_image_bytes',0) for r in completed.values()))


def inherit(target,previous,*,reference,verify):
    if (target['binding']['B_root']!=previous['binding']['B_root']
            or target['binding']['catalog_sha256']!=previous['binding']['catalog_sha256']):
        raise ValueError('same authenticated B root and original SQL catalog required')
    allowed=set(target['binding']['sources']);old=set(previous['binding']['sources'])
    if not reference.get('index_name') or len(reference.get('checkpoint_sha256',''))!=64:
        raise ValueError('exact previous B control reference required')
    candidates={source:record for source,record in previous['completed'].items()
                if source in allowed and source not in target['completed'] and source not in target['partial']}
    if not set(candidates)<=old:raise ValueError('previous source cohort does not bind its points')
    for source,record in candidates.items():
        if record.get('source')!=source or not record.get('B_acceptance_object'):
            raise ValueError('exact accepted SQL source point required')
        verify(record)
    # Do not partially alter the new state if any older acceptance is unreadable
    # or invalid. The new backend saves this returned state transactionally.
    result=copy.deepcopy(target)
    result['completed'].update(copy.deepcopy(candidates))
    result.setdefault('inherited_SQL_points',[]).append(dict(reference,source_names=sorted(candidates),
        accepted_points=len(candidates),source_API_bytes_recaptured=0,backup_payload_bytes_recopied=0))
    return result
