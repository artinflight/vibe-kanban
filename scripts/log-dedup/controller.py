#!/usr/bin/env python3
"""Run one reviewed batch through a source-pinned deployment-owner adapter.

The adapter is trusted executable deployment code, not an admission JSON flag.
Its admit(config, plan, rollback=...) context must own real ingress/consumer
custody, yield the retained WriterFence already held, provide independent B
readback, and recover/retain maintenance on failure before releasing consumers.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

import log_dedup as logs
from reclaim import Batch


def load_adapter(path, expected):
    path = Path(path)
    if not path.is_absolute() or path.resolve(strict=True) != path:
        raise logs.ArchiveError('Literal absolute owner adapter path required')
    before = logs.regular(path)
    if before.st_uid != os.getuid() or before.st_mode & 0o022 or before.st_nlink != 1:
        raise logs.ArchiveError('Unique owned non-writable owner adapter required')
    raw = path.read_bytes()
    if not logs.valid_hash(expected) or hashlib.sha256(raw).hexdigest() != expected:
        raise logs.ArchiveError('Owner adapter source hash mismatch')
    if logs.version(logs.regular(path)) != logs.version(before):
        raise logs.ArchiveError('Owner adapter changed during load')
    # Execute the verified bytes rather than reopening a path after verification.
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader('log_dedup_owner_adapter', loader=None))
    module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    if module.PROTOCOL != 1 or not callable(module.admit):
        raise logs.ArchiveError('Qualified owner adapter protocol required')
    return module


def run(args):
    plan = json.loads(args.plan.read_bytes())
    config = json.loads(args.config.read_bytes())
    adapter = load_adapter(args.adapter, args.adapter_sha256)
    with adapter.admit(config, plan, rollback=args.rollback) as custody:
        batch = Batch(plan, args.archive, args.journal, custody['writer_fence'],
                      custody['recovery'], custody['reader_guard'],
                      reserve_bytes=custody['reserve_bytes'])
        return batch.run(rollback=args.rollback)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('plan', 'archive', 'journal', 'config', 'adapter'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--adapter-sha256', required=True)
    parser.add_argument('--rollback', action='store_true')
    args = parser.parse_args()
    print(json.dumps(run(args), indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        message = str(error) if isinstance(error, logs.ArchiveError) else type(error).__name__
        print('Guarded log conversion failed: ' + message, file=sys.stderr)
        sys.exit(1)
