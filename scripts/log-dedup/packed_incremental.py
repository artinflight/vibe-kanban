"""Packed adapter for the existing finite daily runner and monitoring contract.

No timer, worker, service action or separate converter lock. The existing runner
holds production custody and latches uncertain runs. One normal-B context serves
the selected run; all backup epochs and failed intents remain untouched.
"""
from contextlib import ExitStack
from pathlib import Path
import time

import incremental
import log_dedup as logs
import online_owner
from packed_admission import pinned
import packed_forward_plan as forward
from packed_forward_recovery import recover
from packed_live import Adapter as LiveAdapter
import packed_recovery as checkpoints
from lease_preflight import wait_available
import reclaim


def batches(rows, *, maximum_files, maximum_bytes):
    groups = forward.partition(rows, maximum_files=maximum_files, maximum_bytes=maximum_bytes)
    for group in groups:
        workspaces = {b['workspace'] for r in group['rows'] for b in r['bindings']}
        if len(workspaces) != 1:
            raise ValueError('An exact-session batch must have one SQL workspace')
        group['workspace'] = next(iter(workspaces))
    return groups


def reference(path):
    return dict(path=str(path), sha256=reclaim.file_hash(Path(path)))


class Adapter:
    batches = staticmethod(batches)

    def __init__(self, config):
        self.config = config
        self.c = config['packed']
        self.stack = ExitStack()
        self.recovery = None
        self.used = 0
        self.started = None
        self.root = Path(self.c['source_root'])
        # Capture these runtime PID/mount/config bindings after approved
        # serving-owner activation, never from candidate artifact paths alone.
        self.readers = online_owner.LiveReaders(pinned(self.c['readers']), self.root)
        self.databases = self.c['databases']
        for row in self.c['reader_artifacts'].values():
            pinned(row)
        if not pinned(self.c['forward_acceptance'])['actual_normal_B_forward_recovery_verified']:
            raise ValueError('Accepted actual normal-B forward qualification required')
        self.catalog_pointer = Path(config['state_root'])/'PACKED_CATALOG.private.json'
        self.index = pinned(self.c['prior_index'])
        if self.catalog_pointer.exists():
            self.index = pinned(incremental.read(self.catalog_pointer)['index'])
        self.last_index = None

    def check(self):
        self.readers.check()
        if self.started is not None and time.monotonic()-self.started > self.config['maximum_run_seconds']:
            raise TimeoutError('Finite packed daily deadline reached')
        if self.recovery is not None:
            self.recovery.check()

    def inventory(self):
        snapshot = forward.inventory(self.root, self.databases,
                    minimum_age_seconds=self.config['minimum_closed_age_seconds'], guard=self.check)
        for row in snapshot['files']:
            row['fingerprint'] = dict(version=row['version'], sidecars=row['sidecars'], bindings=row['bindings'])
        return snapshot

    def begin(self, folder, operation):
        self.folder, self.operation = Path(folder), operation
        self.started = time.monotonic()
        self.normal = pinned(self.c['normal_config'])
        seed = pinned(self.c['seed_config'])
        plan = pinned(self.c['seed_plan'])
        legacy_manifest = pinned(self.c['nightly']['legacy_manifest'])
        owned, self.hook, bridge = online_owner.nightly_modules(self.c['nightly'])
        # Register the existing selected-version normal recovery factory.
        import vk_nightly_selected_factory  # noqa: F401
        wait_available(seed['controller_lease'], guard=self.check, maximum_seconds=300)
        legacy = self.stack.enter_context(bridge.pinned_modules(legacy_manifest))
        self.recovery = self.stack.enter_context(owned.open_recovery(
            self.c['seed_config']['path'], plan, legacy=legacy,
            legacy_sha256=self.c['nightly']['legacy_factory_sha256']))
        self.check()

    def capture(self, folder, rows, name):
        self.check()
        size = sum(r['bytes'] for r in rows)
        if self.used+size > self.c['maximum_control_bytes']:
            raise ValueError('Finite packed recovery input budget exceeded')
        self.used += size
        incremental.save(self.folder/'PACKED_BUDGET.private.json', dict(
            charged_bytes=self.used, limit=self.c['maximum_control_bytes']))
        return checkpoints.checkpoint_once(folder, name, rows, guard=self.check,
            capture=lambda paths,n:self.hook.checkpoint(self.recovery,
                operation=self.operation, plan_sha256=incremental.digest(self.folder/'SELECTION.private.json'),
                paths=paths, maximum_bytes=n, seed_checkpoint_sha256=self.c['nightly']['control_seed']),
            restore=lambda cp:self.hook.verify_checkpoint(self.recovery,
                self.normal['B_controls'], self.recovery.provider_placement,
                self.normal['dependencies'], cp, resource_admission=self.normal['host_admission']),
            progress=lambda name,n,size:incremental.save(self.folder/'PACKED_PROGRESS.private.json',
                dict(at=time.time(), checkpoint=name, verified_files=n, verified_bytes=size)))

    @staticmethod
    def rows(paths):
        return [dict(path=str(p), bytes=logs.regular(p).st_size,
                     sha256=reclaim.file_hash(p)) for p in paths]

    def convert(self, folder, batch):
        self.check()
        folder = Path(folder)
        if folder.exists():
            raise FileExistsError('Existing batch requires reconciliation; no replay')
        folder.mkdir(mode=0o700)
        prepared = forward.prepare(batch['rows'], self.root, self.databases,
                                   folder/'preparation', guard=self.check)
        if not prepared['beneficial']:
            return dict(converted_files=0, nonbeneficial=[r['path'] for r in batch['rows']],
                        independent_recovery_verified=True, no_source_mutation=True)
        capture = lambda rows,name:self.capture(folder, rows, name)
        recovery, proof = recover(prepared, folder/'recovery', self.index,
                                  self.operation, self.recovery, capture, guard=self.check)
        group = prepared['group']
        live = LiveAdapter(self.readers, recovery, capture,
                           reserve_bytes=self.c['reserve_bytes'], reader_artifacts=self.c['reader_artifacts'])
        # Scoped allocation includes selected files, new pack names and these
        # directories. Staging and whole-filesystem effects remain separate.
        parent = (self.root/group['files'][0]['path']).parent
        paths = {parent, parent/'.log-packs'}
        paths.update(self.root/r['path'] for r in group['files'])
        paths.update(parent/'.log-packs'/name for name in group['packs'])
        def allocated():
            return sum(p.stat().st_blocks*512 for p in paths if p.exists())
        before = allocated()
        journal = folder/'publication'
        retired = live.convert(group, journal, lambda phase,path:incremental.save(
            self.folder/'PACKED_PROGRESS.private.json', dict(at=time.time(), phase=phase)))
        verified = live.verify(group, journal)
        if not retired['originals_released'] or not verified['full_EOF_verified']:
            raise ValueError('Complete packed publication and EOF required')
        after = allocated()
        controls = sorted(folder.rglob('*.json'))
        sealed = live.seal(controls)
        self.index = incremental.read(folder/'recovery/INDEX.json')
        self.last_index = reference(folder/'recovery/INDEX.json')
        result = dict(complete=True, files=len(group['files']),
            raw_bytes=sum(r['raw_bytes'] for r in group['plan']['files']),
            normal_B_original_and_graph_verified=True, full_EOF_verified=True,
            allocated_release_including_objects_and_directories=before-after,
            allocation_scope='selected raw files, referenced pack names and session directories',
            staging_excluded=True, recovery=proof, journals=sealed,
            source_selection=reference(folder/'preparation/SOURCE_GROUP.json'))
        checkpoints.write_new(folder/'RESULT.private.json', result)
        result_proof = capture(self.rows([folder/'RESULT.private.json']), 'BATCH_RESULT')
        return dict(converted_files=result['files'], nonbeneficial=[],
                    independent_recovery_verified=True, result=reference(folder/'RESULT.private.json'),
                    result_checkpoint=result_proof['checkpoint']['index_reference'])

    def finish(self, folder, state):
        paths = [folder/'INVENTORY.private.json', folder/'SELECTION.private.json']
        paths += sorted(folder.glob('BATCH-*.private.json'))
        for number, batch in enumerate(checkpoints.batches(self.rows(paths))):
            proof = self.capture(folder, batch, f'FINAL_CONTROL_{number:04d}')
            # Separate intent names preserve automatic.verify_run's exact glob.
            checkpoints.write_new(folder/f'RUN_INDEX_{number:04d}.private.json', proof)
        if self.last_index is not None:
            incremental.save(self.catalog_pointer, dict(index=self.last_index,
                operation=self.operation, preserved_previous_epochs=True))

    def close(self):
        self.stack.close()
