"""Actual kernel-drain + durable-commit barrier; no marker files or sleeps.

The installed observer must implement this protocol. An old endpoint cannot
be called fresh because it returned a cached snapshot. No SSD write, source
write, guessed wait interval or arbitrary memory-pressure threshold is used.
"""
from vk_nightly_tracking import request


def flush(endpoint,instance,since,*,guard,maximum_paths=100000):
    guard();value=request(endpoint,instance,since,maximum_paths=maximum_paths,barrier=True)
    proof=value.get('barrier')
    if (not value['ready'] or value['errors'] or value.get('terminal')
            or proof!=dict(kernel_drain_completed=True,durable_sequence=value['sequence'],instance=instance)):
        raise ValueError('actual supported ready kernel/durable barrier required; no freshness inferred')
    guard();return value
