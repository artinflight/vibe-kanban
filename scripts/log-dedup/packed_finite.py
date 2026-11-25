"""Sealed finite production entrypoint. No service, timer or backup-owner changes.

Publication requires the accepted, actually running paired readers. Existing run
folders are reconciliation holds, including failures before the first batch.
"""
from contextlib import ExitStack
from pathlib import Path
import json
import os
import time

import incremental
from lease_preflight import wait_available
import online_owner
from packed_admission import CheckpointCatalog, NormalPreparedRecovery, pinned
import packed_controller
from packed_live import Adapter
import packed_recovery as checkpoints
import reclaim


def reference(path):
    return dict(path=str(path), sha256=reclaim.file_hash(Path(path)))


def configuration(reference):
    c = pinned(reference)
    if (c['format'] != 'vk-packed-finite-production-v1'
            or c['expected_transactions'] != 311 or c['expected_files'] != 3639
            or c['maximum_seconds'] != 21600
            or c['maximum_control_bytes'] != 512*1024**2
            or c['reserve_bytes'] != 3*1024**3):
        raise ValueError('Exact selected finite conversion and resource bounds required')
    for row in c['source_inputs']:
        if reclaim.file_hash(Path(row['path'])) != row['sha256']:
            raise ValueError('Sealed publication source changed')
    mapping = pinned(c['mapping_source'])
    keys, names = packed_controller.selection(mapping)
    if len(keys) != c['expected_transactions'] or len(names) != c['expected_files']:
        raise ValueError('Finite selection differs')
    return c


def accepted_readers(c):
    """No copied-fixture or merely prepared candidate may admit publication."""
    package = pinned(c['cutover_config'])
    accepted = pinned(c['pair_acceptance'])
    folder = Path(c['cutover_config']['path']).parent
    result = json.loads((folder/'RESULT.private.json').read_bytes())
    if (not accepted['complete'] or not accepted['actual_pair_engine_qualified']
            or not accepted['package_B_recovery_verified']
            or accepted['cutover_config_sha256'] != c['cutover_config']['sha256']
            or not result['complete'] or not result['cutover_only']
            or result['bulk_conversion_started']
            or result['operation'] != c['operation']
            or not result['release']['public_route_restored']):
        raise ValueError('Accepted actual paired activation required')
    post = json.loads((folder/'POST_ACTIVATION.private.json').read_bytes())
    rc = pinned(post['readers'])
    for role, key in [('main', 'main'), ('protected5650', 'protected')]:
        row = rc['readers'][role]
        observed = result[key]
        if (row['sha256'] != package['artifacts'][key]['sha256']
                or str(row['main_pid']) != observed['MainPID']
                or row['invocation'] != observed['InvocationID']):
            raise ValueError('Activated reader identity differs')
    if (post['backward_mapping'] != c['mapping_source']
            or post['existing_owner_lock'] != c['production_lock']):
        raise ValueError('Existing converter custody or selection differs')
    readers = online_owner.LiveReaders(rc, c['source_root'])
    return readers, post['readers']


def run(config_reference, folder, *, progress):
    c = configuration(config_reference)
    folder = Path(folder)
    if folder.resolve() != folder or folder.exists():
        raise FileExistsError('Existing finite dispatch requires reconciliation; no replay')
    readers, reader_reference = accepted_readers(c)
    # Reject an old writer or unpinned reader before any backup work.
    from packed_publication import PinnedReaders
    from scoped_fence import WriterRoster
    rows = readers.config['readers']
    PinnedReaders([dict(pid=r['server_pid'], sha256=r['sha256'])
                   for r in rows.values()], readers.check).check()
    WriterRoster([dict(pid=rows['main']['server_pid'], sha256=rows['main']['sha256'])],
                 readers.check).qualify()
    folder.mkdir(mode=0o700)
    checkpoints.write_new(folder/'DISPATCH.json', dict(config=config_reference,
        readers=reader_reference, operation=c['operation'], replay_allowed=False))
    began = time.monotonic()
    recovery = None
    used = 0
    completed = 0

    def check():
        readers.check()
        if time.monotonic()-began > c['maximum_seconds']:
            raise TimeoutError('Finite publication deadline exceeded')
        if recovery is not None:
            recovery.check()

    def emit(value):
        nonlocal completed
        check()
        completed = max(completed, value['completed'])
        progress(dict(value, completed=completed))

    try:
        normal = pinned(c['normal_config'])
        seed = pinned(c['seed_config'])
        owned, hook, bridge = online_owner.nightly_modules(c['nightly'])
        import vk_nightly_selected_factory  # noqa: F401; original factory registration
        wait_available(seed['controller_lease'], guard=check, maximum_seconds=300)
        with ExitStack() as stack:
            legacy = stack.enter_context(bridge.pinned_modules(pinned(c['nightly']['legacy_manifest'])))
            recovery = stack.enter_context(owned.open_recovery(c['seed_config']['path'],
                pinned(c['seed_plan']), legacy=legacy,
                legacy_sha256=c['nightly']['legacy_factory_sha256']))
            check()
            capture = pinned(c['mapping_capture'])
            verified = pinned(c['mapping_verified'])
            if (verified['checkpoint'] != capture
                    or not verified['actual_independent_normal_restore']['independent_owner_controls_restore_verified']):
                raise ValueError('Original mapping recovery receipt differs')
            mapping = NormalPreparedRecovery.read_mapping(recovery, capture,
                c['mapping_source']['path'], c['mapping_source']['sha256'])
            if mapping != pinned(c['mapping_source']):
                raise ValueError('Actual B mapping differs from exact selection')
            catalog = CheckpointCatalog(pinned(c['prior_index']))
            admitted = NormalPreparedRecovery(catalog, recovery, mapping, check)
            receipts = folder/'recovery'
            receipts.mkdir(mode=0o700)

            def capture_files(rows, name):
                nonlocal used
                used += sum(r['bytes'] for r in rows)
                if used > c['maximum_control_bytes']:
                    raise ValueError('Finite recovery-control budget exceeded')
                incremental.save(folder/'BUDGET.json', dict(charged_bytes=used,
                    limit=c['maximum_control_bytes']))
                return checkpoints.checkpoint_once(receipts, name, rows, guard=check,
                    capture=lambda paths,n:hook.checkpoint(recovery,
                        operation=c['operation'], plan_sha256=c['mapping_source']['sha256'],
                        paths=paths, maximum_bytes=n,
                        seed_checkpoint_sha256=c['nightly']['control_seed']),
                    restore=lambda point:hook.verify_checkpoint(recovery,
                        normal['B_controls'], recovery.provider_placement,
                        normal['dependencies'], point, resource_admission=normal['host_admission']),
                    progress=lambda name,n,size:emit(dict(phase='controls_restored_'+name,
                        completed=0, total=c['expected_transactions'])))

            controls = {r['path']:r for r in c['source_inputs']}
            for r in [config_reference, reader_reference]:
                controls[r['path']] = r
            control_rows = [dict(r, bytes=Path(r['path']).stat().st_size)
                            for r in controls.values()]
            for n,batch in enumerate(checkpoints.batches(control_rows)):
                capture_files(batch, 'PUBLICATION_CODE_%03d'%n)
            adapter = Adapter(readers, admitted, capture_files,
                reserve_bytes=c['reserve_bytes'], reader_artifacts=c['reader_artifacts'])
            result = packed_controller.execute(c['mapping_source'], folder/'transactions',
                c['production_lock'], adapter, maximum_seconds=c['maximum_seconds'],
                checkpoint=emit)
            check()
            checkpoints.write_new(folder/'RESULT.json', dict(result,
                full_dedup_complete=False, daily_not_activated=True,
                actual_paired_readers=True, current_B_mapping_verified=True))
            return result
    except BaseException as error:
        checkpoints.write_new(folder/'FAILURE.json', dict(error_type=type(error).__name__,
            reason=str(error)[:500], replay_allowed=False, preserve_all_journals=True))
        raise
