"""Read-only bridge from an independent nightly to restart catch-up.

A trusted controller owns the journal reader, B authentication and physical
readback callback. Same-account callbacks are not a security boundary. This
module grants no activation, writer fence, retirement or production restore.
The object-store format is explicit; it is never disguised as a tar receipt.
"""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path, PurePosixPath
import stat
import threading

from vk_change_journal import scope
from vk_nightly_archive_index import validate_backup_entries
from vk_nightly_generation import PRODUCER, encoding_summary, object_blocks, name, regular
from vk_prep_common import identity
from vk_rolling_backup import check_journal


FORMAT = 'vk-nightly-restart-baseline-v1'


def capture_binding(result, plan, prefix, proof):
    """Preserve the START sequence: events during capture still need catch-up."""
    if (type(result.get('schema')) is not int or result['schema'] != 1 or result.get('passed') is not True
            or result.get('parent') is not None or result.get('online_preparation') is not True
            or result.get('plan_sha256') != identity(plan)
            or result.get('scope_sha256') != identity(scope(plan))):
        raise ValueError('restart baseline requires the verified complete online capture plan')
    sequence = result.get('journal_sequence')
    if type(sequence) is not int or sequence < 0 or not result.get('journal_instance'):
        raise ValueError('capture journal anchor missing')
    if proof.get('full_current_state') is not True:
        raise ValueError('restart baseline lacks the complete verified index')
    validate_backup_entries(proof['entries'])
    snapshots = result.get('sqlite_snapshots', {})
    required = set(plan.get('sqlite_snapshots', [])) | set(plan.get('critical_sqlite', []))
    if set(snapshots) != set(result['databases']) or not required <= set(snapshots):
        raise ValueError('consistent SQLite coverage incomplete')
    databases = {}
    for raw, row in snapshots.items():
        key = PurePosixPath(raw).relative_to(prefix).as_posix()
        entry = proof['entries'].get(key, {})
        if entry.get('kind') != 'file' or entry.get('sha256') != row['sha256']:
            raise ValueError('consistent SQLite image differs from current object')
        databases[raw] = {'key': key, 'sha256': entry['sha256'], 'bytes': entry['bytes']}
    return {'schema': 1, 'plan_sha256': identity(plan), 'scope_sha256': identity(scope(plan)),
            'source_prefix': str(prefix), 'journal_instance': result['journal_instance'],
            'journal_sequence': sequence, 'databases': databases,
            'capture_result_sha256': identity(result), 'snapshot_reuse_allowed': False,
            **({'retained_snapshot_recovery': result['retained_SQLite_recovery'],
                'operational_adoption_eligible': False} if result.get('retained_SQLite_recovery') else {})}


class HeldBaseline:
    def __init__(self, store, manifest, binding, checksum):
        self.store, self.manifest, self.binding, self.checksum = store, manifest, binding, checksum
        self.active = True

    def check(self):
        if not self.active:
            raise ValueError('nightly baseline lease has ended')
        self.store.check()
        with regular(self.store.root / 'current.json') as stream:
            current = json.loads(stream.read(4097))
        if current != {'generation': self.manifest['generation'], 'manifest_sha256': self.checksum}:
            raise ValueError('held current baseline changed')

    def catchup(self, journal):
        self.check()
        watched = journal(self.binding['journal_sequence'])
        if (watched.get('ready') is not True or watched.get('errors')
                or watched.get('scope_sha256') != self.binding['scope_sha256']
                or watched.get('instance') != self.binding['journal_instance']
                or type(watched.get('sequence')) is not int
                or watched['sequence'] < self.binding['journal_sequence']):
            raise ValueError('journal continuity lost; complete reconciliation required; preserve baseline')
        self.check()
        return {'format': FORMAT, 'generation': self.manifest['generation'],
                'manifest_sha256': self.checksum, **self.binding,
                'watched': watched, 'writer_fence_verified': False,
                'activation_authorized': False, 'retirement_authorized': False,
                'whole_plan_restore_acceptance_required': True}

    def blocks(self, key):
        self.check();name(key)
        row = self.manifest['entries'][key]
        if row['kind'] == 'hardlink':
            row = self.manifest['entries'][row['target']]
        if row['kind'] != 'file':
            raise ValueError('baseline member has no regular content')
        path = self.store.root / self.manifest['generation'] / 'objects' / row['sha256']
        for block in object_blocks(path, row['sha256'], row['bytes'], self.manifest.get('object_encoding')):
            yield block
        self.check()


@contextmanager
def held_baseline(store, plan, *, generation, manifest_sha256, physical_readback):
    """Hold the existing store lease through consumer readback/catch-up planning.

    The controller must retain this context until its last baseline read. It
    must supply fresh DB snapshots and its real managed writer fence at switch.
    No boolean in this descriptor establishes that fence or repairs a journal.
    """
    fd = os.open(store.root / 'lease', os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
    handle = None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('baseline lease is not regular')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        store.check();manifest = store.current()
        if (manifest is None or manifest.get('producer') != PRODUCER or manifest.get('parent') is not None
                or manifest.get('generation') != generation
                or encoding_summary(manifest)[0] != manifest_sha256):
            raise ValueError('pinned independent current baseline differs')
        binding = manifest.get('capture_context', {}).get('restart_capture')
        if (not isinstance(binding, dict) or binding.get('schema') != 1
                or binding.get('plan_sha256') != identity(plan)
                or binding.get('scope_sha256') != identity(scope(plan))
                or binding.get('retained_snapshot_recovery')
                or binding.get('snapshot_reuse_allowed') is not False
                or type(binding.get('journal_sequence')) is not int or binding['journal_sequence'] < 0
                or not binding.get('journal_instance')):
            raise ValueError('nightly lacks the exact restart capture contract; rebind through verified capture')
        validate_backup_entries(manifest['entries'])
        required = set(plan.get('sqlite_snapshots', [])) | set(plan.get('critical_sqlite', []))
        if not required <= set(binding['databases']):
            raise ValueError('nightly database coverage differs')
        for raw, row in binding['databases'].items():
            if PurePosixPath(raw).relative_to(binding['source_prefix']).as_posix() != row['key']:
                raise ValueError('nightly database mapping differs')
            item = manifest['entries'].get(row['key'], {})
            if any(item.get(k) != row[k] for k in ('sha256', 'bytes')) or item.get('kind') != 'file':
                raise ValueError('nightly database object differs')
        store.verify(manifest)
        expected = {'physical_b_verified': True, 'generation': generation,
                    'scope_sha256': store.scope, 'manifest_sha256': manifest_sha256}
        if physical_readback(store.root / generation, manifest) != expected:
            raise ValueError('exact independent physical readback missing')
        handle = HeldBaseline(store, manifest, binding, manifest_sha256)
        handle.check()
        yield handle
    finally:
        if handle is not None:handle.active = False
        os.close(fd)


@contextmanager
def capture_journal(plan, reader=None):
    """Only trusted source callers supply an existing owner-managed reader.

    Its lifecycle is left with that owner. The CLI's private watcher remains a
    backup-only default; it cannot promise cross-run incremental continuity.
    """
    owned = None
    stop = threading.Event()
    pump = None
    try:
        if reader is None:
            from vk_change_journal import Journal
            owned = Journal(plan)
            # Drain throughout watch enrollment, inventory and SQLite copying.
            # Waiting until capture checkpoints lets a busy source overflow the
            # kernel queue during a long, otherwise valid online backup.
            def drain():
                while not stop.wait(.05):
                    try:owned.read()
                    except Exception as error:
                        with owned.lock:
                            owned.errors.append({'private_reader_failed': type(error).__name__})
                        return
            pump = threading.Thread(target=drain, name='nightly-private-journal', daemon=True)
            pump.start()
            for raw in plan['sources']:owned.tree(raw)
            owned.ready = True
            reader = owned.report
        check_journal(reader(0), plan)
        yield reader
    except BaseException as error:
        if owned is not None:
            try:
                # Do not materialize another host-scale changed/events report
                # while handling a capture failure or memory exception.
                with owned.lock:
                    owned.read()
                    error.nightly_journal_diagnostic = {
                        'ready': owned.ready and not owned.errors,
                        'instance': owned.instance,
                        'sequence': owned.seq,
                        'scope_sha256': identity(owned.plan),
                        'expected_scope_sha256': identity(scope(plan)),
                        'watches': len(owned.watches),
                        'changed_count': len(owned.changed),
                        'error_count': len(owned.errors),
                        'errors': [str(item)[:1024] for item in owned.errors[:32]],
                        'errors_truncated': len(owned.errors) > 32,
                    }
                error.add_note('Private journal at capture failure: '
                               + json.dumps(error.nightly_journal_diagnostic, sort_keys=True))
            except Exception as secondary:
                error.add_note('Private journal diagnostic unavailable: ' + type(secondary).__name__)
        raise
    finally:
        if owned is not None:
            stop.set()
            if pump is not None:pump.join(timeout=30)
            owned.close()
            if pump is not None and pump.is_alive():
                raise ValueError('private backup journal did not quiesce; preserve capture')
