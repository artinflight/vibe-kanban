"""One-shot recovery of a fully installed batch before any staging retirement.

Reopens the existing B epochs and checks the original journal. Never calls Batch,
convert, prepare, dispatch, or a service mutation. An uncertain attempt is retained
for explicit reconciliation, not retried. All prior proofs remain unchanged.
"""
import argparse
import hashlib
import os
from pathlib import Path
import time

from checkpoint_control import atomic, canonical, locked, read, require
from controlled_conversion import checkpoint, load_legacy, reference, sha, verify_pins
from boundary_handoff import alive
from upgrade_controlled_worker import UNIT, unit

ERROR = 'Staging replica differs from durable primary object'
NAMES = ['PLAN.private.json', 'NONBENEFICIAL.private.json', 'OWNER.private.json',
         'OWNER_EFFECTIVE.private.json', 'CONFIGURATION.private.json', 'B_REQUEST.private.json',
         'CONVERSION.private.json', 'journal/state.json', 'ORIGINAL_B_PROOF.private.json',
         'GRAPH_PROOF.private.json', 'DYNAMIC_RECOVERY.private.json',
         'ALLOCATION_BEFORE.private.json', 'PHYSICAL_BEFORE.private.json',
         'STAGING_CREATED_IDENTITIES.private.json', 'PREPARATION_COMPLETE.private.json']


def terminal(p):
    require(p['unit'] == UNIT and p['authorization_ref'], 'exact authorized finite operation required')
    require(unit(UNIT) == p['terminal_unit'] and p['terminal_unit']['MainPID'] == '0'
            and p['terminal_unit']['ActiveState'] in ('inactive', 'failed'), 'converter is not terminal')
    require(not alive(p['old_process']), 'old converter is alive')
    for name, expected in p['serving_units'].items():
        require(unit(name) == expected, 'serving identity changed')


def inspect(root, failure_sha, override=None):
    root = Path(root)
    require(sha(root/'FAILURE.private.json') == failure_sha, 'failure receipt changed')
    failure = read(root/'FAILURE.private.json')
    committed = read(root/'COMMITTED.private.json', 8*1024**2)
    require(failure['operation'] == committed['operation'] and failure['type'] == 'ValueError'
            and failure['error'] == ERROR and failure['completed_batches'] == len(committed['batches']),
            'different failure or committed prefix')
    number = len(committed['batches']) + len(committed.get('skipped', []))
    folder = root/f'batch-{number:04d}'
    # Check the entire completed prefix through the qualified driver. Only the
    # expected final tail rejection is acceptable; no corrupted prefix is hidden.
    try:
        checkpoint(root, True, batch_override=override)
    except ValueError as error:
        require(str(error) == 'unreconciled uncommitted batch; no automatic continuation',
                'completed prefix qualification failed: '+str(error))
    else:
        raise ValueError('no installed tail requiring reconciliation')
    for candidate in root.glob('batch-*'):
        require(int(candidate.name[6:]) <= number, 'later preparation requires separate reconciliation')
    for name in ['RESULT.private.json', 'PHYSICAL_AFTER.private.json', 'ALLOCATION_AFTER.private.json',
                 'STAGING_RETIREMENT_PLAN.private.json', 'STAGING_RETIREMENT_RESULT.private.json',
                 'CARRIER_RETIREMENT_PLAN.private.json', 'CARRIER_RETIREMENT_RESULT.private.json']:
        require(not (folder/name).exists(), 'retirement or finalization already started; reconcile')
    plan = read(folder/'PLAN.private.json', 8*1024**2)
    owner = read(folder/'OWNER_EFFECTIVE.private.json')
    journal = read(folder/'journal/state.json', 8*1024**2)
    conversion = read(folder/'CONVERSION.private.json')
    selected = read(root/'FINITE_BATCHES.private.json', 8*1024**2)['batches'][number]['names']
    excluded = read(folder/'NONBENEFICIAL.private.json')
    names = {r['path'] for r in plan['files']}; omitted = {r['path'] for r in excluded}
    digest = hashlib.sha256(canonical(plan)).hexdigest()
    require(names == set(journal['files']) and len(names) == len(plan['files'])
            and names.isdisjoint(omitted) and names|omitted == set(selected)
            and all(r['reason'] == 'no_positive_allocated_benefit' for r in excluded), 'tail scope differs')
    require(journal['complete'] and journal['outcome'] == 'installed'
            and conversion['complete'] and conversion['outcome'] == 'installed'
            and conversion['files'] == len(names) and owner['plan_sha256'] == digest
            and journal['plan_sha256'] == digest and journal['archive'] == str(folder/'archive'),
            'tail conversion is not fully installed')
    require(read(folder/'ORIGINAL_B_PROOF.private.json')['independent_normal_B_full_EOF_hash_and_Linux_metadata_verified']
            and read(folder/'GRAPH_PROOF.private.json')['independent_backup_verified']
            and read(folder/'DYNAMIC_RECOVERY.private.json', 8*1024**2)['actual_independent_normal_restore']['independent_owner_controls_restore_verified'],
            'retained backup proofs incomplete')
    source = Path(plan['source_root'])
    for row in plan['files']:
        relative = Path(row['path']); require(not relative.is_absolute() and '..' not in relative.parts, 'unsafe source path')
        path = source/relative; entry = journal['files'][row['path']]; s = path.lstat()
        require(entry['state'] == 'installed' and not path.is_symlink()
                and [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns] == entry['installed_identity']
                and sha(path) == entry['manifest_sha256'] == sha(folder/'archive'/relative), 'installed manifest changed')
        for side in row.get('sidecars', []):
            path = (source/relative).with_suffix('.'+side['extension']); s = path.lstat()
            require(not path.is_symlink() and [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns] == side['identity']
                    and sha(path) == side['sha256'], 'installed sidecar changed')
    graphs = sorted((folder/'graph-recovery').glob('graph-checkpoint-*.json'), key=lambda p: int(p.stem.rsplit('-',1)[1]))
    require(graphs and [p.name for p in graphs] == [f'graph-checkpoint-{n}.json' for n in range(len(graphs))], 'graph receipt prefix differs')
    pins = [reference(root/n) for n in ['FAILURE.private.json','COMMITTED.private.json','FINITE_BATCHES.private.json']]
    pins += [reference(folder/n) for n in NAMES] + [reference(p) for p in graphs]
    return dict(operation=committed['operation'], batch=number, folder=str(folder), pins=pins,
                files=len(names), raw_bytes=sum(r['raw_bytes'] for r in plan['files']))


def finish_batch(base, value, output):
    """Only the already installed tail; original before-accounting stays intact."""
    worker = base.w; folder = Path(value['folder']); output = Path(output)
    plan = read(folder/'PLAN.private.json', 8*1024**2)
    cfg = read(folder/'OWNER_EFFECTIVE.private.json'); request = read(folder/'B_REQUEST.private.json')
    conversion = read(folder/'CONVERSION.private.json'); dynamic = read(folder/'DYNAMIC_RECOVERY.private.json', 8*1024**2)
    before = read(folder/'ALLOCATION_BEFORE.private.json')
    roots = sorted({str((Path(plan['source_root'])/r['path']).parent) for r in plan['files']})
    started = time.monotonic()
    with worker.online_owner.admit_online(cfg, plan, record=worker.progress) as custody:
        guard = custody['reader_guard']; recovery = custody['recovery']
        proof = worker.graph.verify_provider(worker.graph.inventory(folder/'archive', plan),
                    custody['archive_recovery'], guard, guard_every=64)
        atomic(output/'GRAPH_REOPEN.private.json', proof)
        total = sum(r['bytes'] for r in request['files'])
        worker.admit_ram(total+max(r['bytes'] for r in request['files']))
        with worker.ReplayGroups(recovery, request['files']) as cache:
            cache.populate()
            for row in request['files']:
                actual = recovery.handle.index.entry(row['normal_namespace_name'])
                require(all(actual[k] == row['Linux_metadata'][k] for k in ('mode','uid','gid','mtime_ns','xattrs')), 'original Linux metadata differs')
            original = worker.support.verify_restored_RAM(cache, request, plan, guard)
            atomic(output/'ORIGINALS_REOPEN.private.json', original)
        # The production reader runs to EOF again without publishing anything.
        worker.support.rust_readback(plan, plan['source_root'], worker.C['reader_probe']['path'],
                                     worker.C['reader_probe']['sha256'], guard, worker.progress)
        reopened = worker.hook.verify_checkpoint(recovery, worker.normal['B_controls'], recovery.provider_placement,
            worker.normal['dependencies'], dynamic['checkpoint'], resource_admission=worker.normal['host_admission'])
        require(reopened['actual_independent_normal_restore']['independent_owner_controls_restore_verified'], 'control reopen failed')
        atomic(output/'CONTROLS_REOPEN.private.json', reopened)
        # Every original proof and journal remains byte-for-byte unchanged.
        verify_pins(value['pins'])
        retired = worker.retire_local_staging(custody, plan, folder, conversion, original, reopened)
        atomic(folder/'PHYSICAL_AFTER.private.json', worker.physical_accounting.measure(roots, guard=worker.readers.check))
        after = worker.allocation_counts(plan, folder/'archive'); atomic(folder/'ALLOCATION_AFTER.private.json', after)
        release = sum(before[k]-after[k] for k in ['selected_log_allocated_bytes','referenced_object_allocated_bytes','directory_allocated_bytes'])
        result = dict(complete=True, files=value['files'], raw_bytes=value['raw_bytes'], seconds=time.monotonic()-started,
            allocated_release_including_objects_and_directories=release, normal_B_original_and_graph_verified=True,
            ordinary_history_acceptance='Prior canary; full production EOF verified again during installed-tail recovery',
            staging_retirement=retired, production_service_actions=False, installed_recovery=str(output))
        atomic(folder/'RESULT.private.json', result)
    return result


def reconcile(path):
    p = read(path, 8*1024**2); verify_pins(p['sources']); terminal(p)
    root = Path(p['operation_root']); output = Path(p['controls'])/'installed-recovery'
    require(root.resolve() == root and Path(p['controls']).parent == root and os.path.ismount('/mnt/vk-storage'), 'exact mounted operation required')
    with locked(root.parents[1]/'production-owner.lock', nonblocking=True):
        terminal(p); value = inspect(root, p['failure_sha256'], p['batch_override'])
        require(value == p['installed_tail'], 'tail evidence changed')
        # Atomic mkdir is the durable no-replay marker for this recovery.
        output.mkdir(mode=0o700)
        atomic(output/'ATTEMPT.private.json', dict(at=time.time(),value=value,authorization_ref=p['authorization_ref']))
        base = load_legacy(root)
        import fast_online
        import fast_retirement
        owner = base.w.online_owner
        require(fast_online.ClosedLogFence is owner.ClosedLogFence, 'qualified fence module differs')
        units = fast_online.FreshUnits(list(owner.UNITS.values()))
        for name in owner.UNITS.values(): require(units(name) == owner.unit(name), 'fresh unit differs')
        owner.unit = units; owner.readonly_mount = fast_online.readonly_mount
        owner.ClosedLogFence = fast_online.FreshClosedLogFence
        base.w.support.retire_new_staging_objects = fast_retirement.retire_new_staging_objects
        result = finish_batch(base, value, output)
        terminal(p); verify_pins(value['pins'])
        base.retire_carriers(Path(value['folder']))
        state = read(root/'COMMITTED.private.json', 8*1024**2)
        base.committed = state['batches']; base.skipped = state.get('skipped', [])
        base.committed.append(dict(batch=value['batch'],files=result['files'],raw_bytes=result['raw_bytes'],
            allocated_release=result['allocated_release_including_objects_and_directories'],result=str(Path(value['folder'])/'RESULT.private.json')))
        base.w.save(root/'COMMITTED.private.json', base.metadata())
        cp = checkpoint(root, True, batch_override=p['batch_override'])
        proof = dict(at=time.time(),verified=True,operation=p['operation'],batch=value['batch'],
            before=value,checkpoint=cp,no_conversion_or_dispatch_replayed=True,all_prior_epochs_preserved=True)
        atomic(output/'RESULT.private.json', proof)
        base.w.progress('installed_tail_reconciled_and_committed', dict(batch=value['batch'],files=result['files']))
        return reference(output/'RESULT.private.json')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--preparation',required=True)
    parser.add_argument('--recover',action='store_true');args=parser.parse_args()
    if args.recover: print(reconcile(args.preparation))
    else:
        p=read(args.preparation,8*1024**2);terminal(p)
        print(inspect(p['operation_root'],p['failure_sha256'],p['batch_override']))
