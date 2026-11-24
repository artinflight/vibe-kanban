"""Pinned adapter to the already qualified scoped writer/normal-B converter."""
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import sqlite3
import sys
import time
import uuid

from incremental import source, save


def version(st):
    return [st.st_dev, st.st_ino, st.st_mode, st.st_size, st.st_mtime_ns,
            st.st_ctime_ns, st.st_uid, st.st_gid, st.st_nlink]


def fingerprint(path):
    side = path.with_suffix('.capture.json')
    before = version(path.lstat())
    if side.is_symlink() or side.stat().st_size > 4096:
        raise ValueError('bounded regular capture metadata required')
    raw = side.read_bytes()
    after = version(path.lstat())
    if before != after:
        raise ValueError('log changed during observation')
    return dict(inode=before, capture_sha256=hashlib.sha256(raw).hexdigest()), json.loads(raw)


class Adapter:
    def __init__(self, config):
        self.config = config
        # Verify every dependency before executing the retained qualified worker.
        for reference in config['qualified_sources']:
            source(reference)
        reference = config['qualified_worker']
        module = importlib.util.module_from_spec(importlib.util.spec_from_loader('qualified_incremental_worker', loader=None))
        module.__file__ = reference['path']
        exec(compile(source(reference), module.__file__, 'exec'), module.__dict__)
        self.w = module
        fast_dir = Path(config['fast_source_dir'])
        sys.path.insert(0, str(fast_dir))
        import fast_online
        import fast_retirement
        if (Path(fast_online.__file__) != fast_dir/'fast_online.py'
                or Path(fast_retirement.__file__) != fast_dir/'fast_retirement.py'
                or fast_online.ClosedLogFence is not module.online_owner.ClosedLogFence):
            raise ValueError('qualified acceleration module binding differs')
        units = fast_online.FreshUnits(list(module.online_owner.UNITS.values()))
        for unit in module.online_owner.UNITS.values():
            if units(unit) != module.online_owner.unit(unit):
                raise ValueError('fresh unit identity differs')
        module.online_owner.unit = units
        module.online_owner.readonly_mount = fast_online.readonly_mount
        module.online_owner.ClosedLogFence = fast_online.FreshClosedLogFence
        module.support.retire_new_staging_objects = fast_retirement.retire_new_staging_objects
        module.readers.resource_wait = 600
        module.readers.check()

    def inventory(self):
        w = self.w
        root = Path(w.C['source_root'])
        db = sqlite3.connect(Path(w.C['database']).as_uri()+'?mode=ro', uri=True)
        try:
            db.execute('pragma query_only=on')
            db.execute('begin')
            processes = {str(uuid.UUID(bytes=r[0])): (str(uuid.UUID(bytes=r[1])), r[2], r[3])
                         for r in db.execute('select id,session_id,status,completed_at from execution_processes')}
            sessions = {str(uuid.UUID(bytes=r[0])): str(uuid.UUID(bytes=r[1]))
                        for r in db.execute('select id,workspace_id from sessions')}
        finally:
            db.close()
        active = {r[0] for r in processes.values() if r[1] == 'running'}
        rows = []
        for path in root.glob('*/*/processes/*.jsonl'):
            if path.is_symlink():
                raise ValueError('unexpected symlink log')
            with path.open('rb') as body:
                header = body.read(16)
            if header.startswith(b'VKLOGCAS'):
                continue
            st = path.stat()
            process = processes.get(path.stem)
            session = path.parent.parent.name
            reason = 'unbound'
            binding = None
            if process and process[0] == session and session in sessions:
                if session in active:
                    reason = 'active_session'
                elif process[1] not in ('completed', 'failed', 'killed') or process[2] is None:
                    reason = 'nonterminal'
                elif time.time_ns() - st.st_mtime_ns < self.config['minimum_closed_age_seconds'] * 10**9:
                    reason = 'recent_capture'
                else:
                    try:
                        binding, capture = fingerprint(path)
                        reason = 'eligible_closed' if capture.get('capture_state') == 'closed' else 'pending_capture'
                    except (OSError, ValueError, AttributeError):
                        reason = 'invalid_capture'
            rows.append(dict(path=str(path.relative_to(root)), workspace=sessions.get(session),
                             bytes=st.st_size, allocated=st.st_blocks*512,
                             fingerprint=binding, reason=reason))
        w.readers.check()
        return dict(at=time.time(), files=rows, source_root=str(root), provider_requests_created=0)

    def begin(self, folder, operation):
        self.w.D = folder
        self.w.C = dict(self.w.C, operation=operation)

    def convert(self, folder, batch):
        w = self.w
        for row in batch['rows']:
            actual, capture = fingerprint(Path(w.C['source_root'])/row['path'])
            if actual != row['fingerprint'] or capture.get('capture_state') != 'closed':
                raise ValueError('selected version changed; preserve and reconcile')
        w.prepare(folder, [r['path'] for r in batch['rows']], batch['workspace'])
        nonbeneficial = json.loads((folder/'NONBENEFICIAL.private.json').read_text())
        skipped = [r['path'] for r in nonbeneficial]
        if (folder/'SKIPPED.private.json').exists():
            return dict(converted_files=0, nonbeneficial=skipped,
                        independent_recovery_verified=True, no_source_mutation=True,
                        reason='all originals preserved because conversion is nonbeneficial')
        w.convert(folder)
        result = json.loads((folder/'RESULT.private.json').read_text())
        if not result['complete'] or not result['normal_B_original_and_graph_verified']:
            raise ValueError('qualified conversion did not complete')
        self.retire_carriers(folder)
        return dict(converted_files=result['files'], nonbeneficial=skipped,
                    independent_recovery_verified=True,
                    result=w.ref(folder/'RESULT.private.json'),
                    allocated_release_bytes=result['allocated_release_including_objects_and_directories'])

    def retire_carriers(self, folder):
        w = self.w
        proof = json.loads((folder/'DYNAMIC_RECOVERY.private.json').read_text())
        if not proof['actual_independent_normal_restore']['independent_owner_controls_restore_verified']:
            raise ValueError('independent B control restoration required')
        points = []
        for receipt in (folder/'graph-recovery').glob('graph-checkpoint-*.json'):
            record = json.loads(receipt.read_bytes())
            path = Path(record['carrier_source'])
            if not path.is_relative_to(folder/'graph-recovery') or path.name != 'closure.tar':
                raise ValueError('foreign carrier path')
            points.append(next(r for r in record['checkpoint']['manifest']['files'] if r['source'] == str(path)))
        save(folder/'CARRIER_RETIREMENT_PLAN.private.json', dict(points=points, only_new_duplicate_staging=True))
        old = signal.getsignal(signal.SIGIO)
        def consumer(*_):
            raise ValueError('carrier consumer appeared; preserve remaining replicas')
        signal.signal(signal.SIGIO, consumer)
        released = 0
        try:
            for row in points:
                w.readers.check()
                path = Path(row['source'])
                fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                try:
                    st = os.fstat(fd)
                    if (version(st) != row['source_identity'] or version(path.lstat()) != version(st)
                            or st.st_uid != os.getuid() or st.st_nlink != 1
                            or w.sha(path) != row['member']['sha256']):
                        raise ValueError('owned carrier identity or bytes changed')
                    fcntl.fcntl(fd, fcntl.F_SETOWN, os.getpid())
                    fcntl.fcntl(fd, fcntl.F_SETLEASE, fcntl.F_WRLCK)
                    if version(path.lstat()) != row['source_identity']:
                        raise ValueError('carrier changed after lease')
                    path.unlink()
                    w.reclaim.sync_directory(path.parent)
                    released += st.st_blocks*512
                finally:
                    try:
                        fcntl.fcntl(fd, fcntl.F_SETLEASE, fcntl.F_UNLCK)
                    finally:
                        os.close(fd)
        finally:
            signal.signal(signal.SIGIO, old)
        save(folder/'CARRIER_RETIREMENT_RESULT.private.json', dict(complete=True, allocated_duplicate_carrier_bytes_removed=released, primary_objects_and_all_B_epochs_preserved=True))

    def finish(self, folder, state):
        w = self.w
        paths = [folder/'INVENTORY.private.json', folder/'SELECTION.private.json']
        paths += sorted(folder.glob('BATCH-*.private.json'))
        # All batch graph/original/control receipts already have verified B
        # copies. Seal small run indexes in bounded groups, reusing one owner.
        with w.bridge.pinned_modules(w.legacy_manifest) as legacy:
            with w.owned.open_recovery(w.C['seed_config']['path'], json.loads(w.read(w.C['seed_plan'])),
                    legacy=legacy, legacy_sha256=w.C['nightly']['legacy_factory_sha256']) as recovery:
                for offset in range(0, len(paths), 48):
                    selected = paths[offset:offset+48]
                    proof = w.control_checkpoint(recovery, [str(p) for p in selected],
                                                 state['operation'], w.sha(folder/'SELECTION.private.json'))
                    save(folder/('RUN_INDEX_%04d.private.json' % offset), proof)
