"""Same-process composition of the real reader-owner and reclamation interfaces.

This module does not acquire custody, open a backup, control services or launch
an agent. The finite host operation must load this assembly BEFORE constructing
its real WriterFence, and retain that fence and the SAME normal B reader until
conversion or exact raw recovery finishes. Failure never releases maintenance.
"""
import hashlib
import json
from pathlib import Path
import types



def load_module(name, row):
    """Validate owned source identity/hash and execute those exact bytes."""
    import os
    import stat
    path = Path(row['path'])
    if not path.is_absolute() or path.resolve(strict=True) != path:
        raise ValueError('Literal absolute sealed source required')
    before = path.lstat()
    if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid()
            or before.st_nlink != 1 or before.st_mode & 0o022):
        raise ValueError('Unique owned non-writable sealed source required')
    raw = path.read_bytes()
    after = path.lstat()
    version = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    if version(before) != version(after) or hashlib.sha256(raw).hexdigest() != row['sha256']:
        raise ValueError('Sealed source changed or hash mismatch')
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def prepare(manifest):
    """Load exactly the deployment owner's class universe, before any fence."""
    adapter = load_module('sealed_reader_owner_adapter', manifest['adapter'])
    if adapter.PROTOCOL != 1 or not callable(adapter.admit_held):
        raise ValueError('Qualified held-custody owner adapter required')
    spec = json.loads(adapter.owned_bytes(manifest['spec']['path'], manifest['spec']['sha256']))
    for name, row in spec['modules'].items():
        adapter.load_pinned(name, row)
    actions = load_module('sealed_reader_owner_actions', manifest['owner_actions'])
    return adapter, actions


def convert_held(*, assembly, manifest, operation, plan, archive, journal,
                 fence, recovery, record):
    """Activate and convert under the caller's real held host/B custody.

    Caller invokes its host release/acceptance after this returns. If conversion
    fails, restore raw bytes under the SAME admitted readers/fence before asking
    the owner for old-software recovery. A recovery failure leaves all controls
    held and propagates; it never silently falls back to an unaware reader.
    """
    import sys
    adapter, actions = assembly
    reclaim = sys.modules['reclaim']
    inputs = manifest['activation_inputs']
    phase = 'activation'
    batch = None
    raw_recovered = False
    try:
        actions.activate(inputs['path'], inputs['sha256'], operation, fence, recovery)
        record('actual_reader_activation_complete', {'operation': operation})
        sealed = actions.seal_controller_inputs(
            inputs['path'], inputs['sha256'], operation, fence, recovery, plan)
        config = json.loads(adapter.owned_bytes(sealed['config_path'], sealed['config_sha256']))
        phase = 'conversion'
        with adapter.admit_held(config, plan, fence, recovery) as custody:
            if custody['writer_fence'] is not fence or custody['recovery'] is not recovery:
                raise ValueError('The SAME actual fence and B context must remain held')
            batch = reclaim.Batch(plan, archive, journal, fence, recovery,
                                  custody['reader_guard'], reserve_bytes=custody['reserve_bytes'])
            try:
                result = batch.run(after_replace=lambda path: record('manifest_readback_complete', {'path': path}))
            except BaseException:
                # Initial admission/journal failure before initialization has
                # no valid restoration authority. Preserve evidence unchanged.
                if batch.state is not None:
                    recovered = batch.run(rollback=True)
                    raw_recovered = True
                    record('exact_raw_recovery_complete', recovered)
                raise
        record('actual_frozen_conversion_complete', result)
        return result
    except BaseException:
        # Only independently verified raw bytes permit old reader recovery.
        # The owner checks every original again and rejects a partial rollback.
        record('reader_recovery_required', {'phase': phase, 'maintenance_retained': True})
        if batch is not None and batch.state is not None and not raw_recovered:
            raise  # Keep aware readers and maintenance after failed raw recovery.
        actions.recover_before_conversion(
            inputs['path'], inputs['sha256'], operation, fence, plan)
        record('old_readers_recovered_frozen', {'maintenance_retained': True})
        raise
