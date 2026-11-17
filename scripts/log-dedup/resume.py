"""Read-only continuation checks; receipts never grant a live writer lease.

Completed batches are dependencies of a NEW operation, never Batch.run inputs
again. Pin evidence by hash and repeat verification under the new real fence.
No import/function here acquires backup custody or changes production.
"""
from pathlib import Path

import log_dedup as logs
import reclaim


def completed_batch(plan, journal, original_proof, *, guard=lambda: None):
    """Verify installed bytes/inodes/metadata/sidecars and retained normal B proof.

    Caller pins plan, journal and proof. Historical proof is not a fresh B restore
    or complete object-store closure claim. Access times may advance on reads.
    """
    names = [row['path'] for row in plan['files']]
    if not names or len(set(names)) != len(names):
        raise logs.ArchiveError('Unique nonempty completed batch required')
    if (journal.get('version') != 1 or journal.get('complete') is not True
            or journal.get('operation') != 'install' or journal.get('outcome') != 'installed'
            or journal.get('plan_sha256') != logs.sha(reclaim.canonical(plan))
            or set(journal.get('files', {})) != set(names)):
        raise logs.ArchiveError('Exact complete installed journal required; reconcile partial attempt')
    proof_rows = original_proof.get('actual_restores', [])
    proof = {row['relative']: row for row in proof_rows}
    if (original_proof.get('independent_normal_B_full_EOF_hash_and_Linux_metadata_verified') is not True
            or len(proof) != len(proof_rows)):
        raise logs.ArchiveError('Retained independent normal B original proof required')
    required = set()
    root = Path(plan['source_root'])
    for row in plan['files']:
        guard()
        path = logs.safe_path(root, row['path'])
        record = journal['files'][row['path']]
        before = logs.regular(path)
        if (record.get('state') != 'installed' or before.st_nlink != 1
                or logs.version(before) != record.get('installed_identity')
                or logs.sha(path.read_bytes()) != record.get('manifest_sha256')):
            raise logs.ArchiveError('Completed manifest identity/content changed')
        stable = lambda metadata: {k: v for k, v in metadata.items() if k != 'atime_ns'}
        if stable(reclaim.metadata_for(path)) != stable(record['metadata']):
            raise logs.ArchiveError('Completed manifest metadata changed')
        manifest = logs.reconstruct(path)
        if manifest['sha256'] != row['sha256'] or manifest['raw_bytes'] != row['raw_bytes']:
            raise logs.ArchiveError('Completed history differs from original')
        expected_sides = {side['extension']: side for side in row.get('sidecars', [])}
        actual_sides = {ext: (data, identity) for ext, data, identity in logs.sidecars(path)}
        if set(actual_sides) != set(expected_sides):
            raise logs.ArchiveError('Completed sidecar set changed')
        expected = [(row['path'], row['sha256'], row['raw_bytes'], row['identity'][:2])]
        for ext, side in expected_sides.items():
            data, identity = actual_sides[ext]
            if identity != side['identity'] or logs.sha(data) != side['sha256']:
                raise logs.ArchiveError('Completed sidecar changed')
            expected.append((str(Path(row['path']).with_suffix('.' + ext)),
                             side['sha256'], len(data), side['identity'][:2]))
        for name, digest, size, source_inode in expected:
            required.add(name)
            restored = proof.get(name, {})
            inode = restored.get('separate_restored_inode', [])
            if (restored.get('sha256') != digest or restored.get('bytes') != size
                    or restored.get('Linux_metadata_verified') is not True
                    or len(inode) != 2 or inode == source_inode):
                raise logs.ArchiveError('Completed original/sidecar B proof incomplete')
        if logs.version(logs.regular(path)) != logs.version(before):
            raise logs.ArchiveError('Completed manifest changed during verification')
    if (set(proof) != required or original_proof.get('files') != len(required)
            or original_proof.get('bytes') != sum(row['bytes'] for row in proof_rows)):
        raise logs.ArchiveError('Normal B proof scope differs')
    guard()
    return dict(verified=True, source_root=str(root.resolve(strict=True)),
                plan_sha256=logs.sha(reclaim.canonical(plan)),
                paths=sorted(names), files=len(names),
                original_bytes=sum(row['raw_bytes'] for row in plan['files']),
                historical_B_proof_only=True, live_custody_granted=False)


def remaining(observation, completed):
    """Refuse unaccounted CAS and exclude the verified committed union explicitly."""
    if observation.get('complete') is not True or observation.get('read_only') is not True:
        raise logs.ArchiveError('Complete current metadata observation required')
    if any(batch.get('source_root') != str(Path(observation['root']).resolve(strict=True))
           for batch in completed):
        raise logs.ArchiveError('Completed batch belongs to another source root')
    paths = [name for batch in completed for name in batch['paths']]
    if len(set(paths)) != len(paths) or not all(b.get('verified') is True for b in completed):
        raise logs.ArchiveError('Disjoint verified completed batches required')
    expected = set(paths)
    actual = {name for name, row in observation['files'].items() if row['archived']}
    if actual != expected:
        raise logs.ArchiveError('Unexpected or missing installed batch; reconcile before resuming')
    eligible = observation['eligible_closed_inactive_files']
    if len(set(eligible)) != len(eligible) or expected.intersection(eligible):
        raise logs.ArchiveError('Completed batch offered for conversion again')
    return dict(completed_paths=sorted(expected), remaining_paths=sorted(eligible),
                exclusions=dict(observation['exclusions']),
                writer_fence_established=False, production_run_ready=False)


def qualify_history_inputs(original, candidate, raw_cas, live):
    """Qualify a context-correct baseline without normalizing any page fields.

    Each replacement digest must independently equal RAW, CAS and live pages.
    Protected baselines and all noncanary requirements stay unchanged. The caller
    seals evidence; merely learning a live digest does not qualify it.
    """
    key = 'canary_qualified_page_sha256'
    if {k: v for k, v in original.items() if k != key} != {
            k: v for k, v in candidate.items() if k != key}:
        raise logs.ArchiveError('Noncanary history acceptance changed')
    old, new = original[key], candidate[key]
    if set(old) != {'main', 'protected5650'} or set(new) != set(old):
        raise logs.ArchiveError('Exact qualified history roles required')
    if new['protected5650'] != old['protected5650']:
        raise logs.ArchiveError('Protected baseline must remain unchanged')
    if set(live) != set(old) or set(raw_cas) != set(old['main']):
        raise logs.ArchiveError('Complete role-specific canary evidence required')
    for role, rows in new.items():
        if set(rows) != set(old[role]) or set(live[role]) != set(rows):
            raise logs.ArchiveError('Canary scope changed')
        for execution, digest in rows.items():
            result = live[role][execution]
            if (not logs.valid_hash(digest) or result.get('exact') is not True
                    or result.get('actual') != digest or result.get('expected') != digest):
                raise logs.ArchiveError('Exact live context parity required')
            if role == 'main':
                pair = raw_cas[execution]
                if pair.get('exact') is not True or pair.get('raw') != digest or pair.get('converted') != digest:
                    raise logs.ArchiveError('Independent raw/CAS context parity required')
    return dict(verified=True, exact_page_comparison=True, normalization_applied=False)


def recover_compatible(*, qualification, verify_lossless_service, release, record):
    """Separate strict qualification from independent safe aware-service recovery.

    Validator MUST check compatible identities, decoded committed/current bytes,
    sidecars, review/settings/queues and real custody. Release uses the normal host
    capacity/route/ingress ABI. Neither health nor a page-hash failure grants it.
    """
    try:
        qualification()
    except Exception as error:
        record('strict_acceptance_failed', dict(type=type(error).__name__,
                                               reclamation_accepted=False))
    proof = verify_lossless_service()  # Never swallowed; leave maintenance held.
    if proof.get('lossless_compatible_service_verified') is not True:
        raise logs.ArchiveError('Independent compatible recovery proof required')
    result = release()
    record('compatible_service_recovered', dict(reclamation_accepted=False))
    return result


def adopt_frozen_readers(*, base, adapter, spec, prior, operation, fence, recovery):
    """Construct fresh custody from live compatible readers, without restarting.

    ``base`` and ``adapter`` are the sealed owner ABI in its real class universe.
    Historical JSON alone cannot pass their held-fence/B/cgroup/namespace checks.
    The caller persists this result in a NEW operation and calls host adoption.
    """
    import copy
    import os
    import stat
    import uuid
    base.actual_fence(fence)
    base.actual_recovery(recovery)
    if prior.get('completed') is not True or prior.get('raw_recovery'):
        raise logs.ArchiveError('Completed compatible reader activation required')
    if recovery.prefix != fence.binding['log_source_root'].lstrip('/') + '/':
        raise logs.ArchiveError('Recovery/source namespace differs')
    expected_units = {base.MAIN, base.READER, base.PROXY}
    if set(prior['new_units']) != expected_units:
        raise logs.ArchiveError('Exact three serving owners required')
    actual_units = {}
    for unit, expected in prior['new_units'].items():
        current = base.state(unit)
        if (current.get('ActiveState') != 'active' or current.get('FreezerState') != 'frozen'
                or any(current[k] != expected[k] for k in ('MainPID', 'InvocationID'))):
            raise logs.ArchiveError('Compatible serving owner changed or is not frozen')
        actual_units[unit] = current
    owned = []
    for row in prior['owned']:
        path = Path(row['path'])
        if str(path).startswith('/run/'):
            if path.exists() or path.is_symlink():
                raise logs.ArchiveError('Prior temporary startup hold still exists')
            continue
        st = path.lstat()
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_nlink != 1
                or [st.st_dev, st.st_ino] != row['identity']
                or logs.sha(path.read_bytes()) != row['sha256']):
            raise logs.ArchiveError('Persistent compatible boot configuration changed')
        owned.append(copy.deepcopy(row))
    custody = dict(readers=prior['actual_reader_custody'],
                   log_source_root=fence.binding['log_source_root'])
    adapter.check_readers(spec, custody)
    base.actual_fence(fence)
    base.actual_recovery(recovery)
    return dict(operation=uuid.UUID(operation).hex, completed=True,
                phase='existing_compatible_readers_adopted_under_new_real_fence',
                adopted_existing_compatible_readers=True, reader_restart_performed=False,
                source_replacement=False, owned=owned, new_units=actual_units,
                actual_reader_custody=copy.deepcopy(prior['actual_reader_custody']),
                writer_binding=copy.deepcopy(fence.binding),
                queue_before=copy.deepcopy(fence.before),
                capacity_released=copy.deepcopy(fence.released))


def readback_members(plan):
    """Stable physical members; called while the real host fence remains held.

    Version tuples include inode, size, mtime and ctime. Access time is excluded.
    This is metadata, never a substitute for the first full decoded EOF read.
    """
    root = Path(plan['source_root'])
    rows = {}
    for row in plan['files']:
        path = logs.safe_path(root, row['path'])
        with path.open('rb') as f:
            archived = f.read(len(logs.MAGIC)) == logs.MAGIC
        members = [path]
        if archived:
            manifest = logs.load_manifest(path)
            if manifest['sha256'] != row['sha256'] or manifest['raw_bytes'] != row['raw_bytes']:
                raise logs.ArchiveError('Readback manifest differs from original')
            store = path.parent / '.log-objects'
            if store.is_symlink() or not store.is_dir():
                raise logs.ArchiveError('Invalid readback object store')
            members += [store / (chunk['sha256'] + '.gz') for chunk in manifest['chunks']]
        sides = logs.sidecars(path)
        if {ext: logs.sha(data) for ext, data, _ in sides} != {
                side['extension']: side['sha256'] for side in row.get('sidecars', [])}:
            raise logs.ArchiveError('Readback sidecar set/content differs')
        members += [path.with_suffix('.' + ext) for ext, _, _ in sides]
        for member in members:
            relative = str(member.relative_to(root))
            version = logs.version(logs.regular(member))
            if relative in rows and rows[relative] != version:
                raise logs.ArchiveError('Readback member changed')
            rows[relative] = version
    return rows


def seal_readback(plan, *, verify_decoded, guard):
    """Bind a genuine full decoded reader proof to stable physical versions.

    Keep the same real fence through before/read/after. Caller persists the seal
    with its immutable plan/journal in normal B. No new backup is made here.
    """
    guard()
    before = readback_members(plan)
    verify_decoded()  # Actual production library full EOF/hash/length, not metadata.
    guard()
    if readback_members(plan) != before:
        raise logs.ArchiveError('Physical members changed during decoded readback')
    return dict(plan_sha256=logs.sha(reclaim.canonical(plan)),
                full_decoded_readback_verified=True, physical_members=before)


def verify_readback_seal(plan, seal, *, guard):
    """Bounded recovery reuses verified EOF only while ALL versions still match.

    No repeat of a whole historical API check or full decoded multi-GB union.
    Missing/unsealed current batches still require their own full reader proof.
    This does not grant custody: the caller must retain/revalidate the real fence.
    """
    guard()
    if (seal.get('full_decoded_readback_verified') is not True
            or seal.get('plan_sha256') != logs.sha(reclaim.canonical(plan))
            or readback_members(plan) != seal.get('physical_members')):
        raise logs.ArchiveError('Lossless readback seal changed; retain maintenance')
    guard()
    return dict(lossless_versions_verified=True, files=len(plan['files']))
