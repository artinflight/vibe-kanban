"""Claim an exact prepared script once, then replace this process with it.

No scheduler, retry, recovery or child agent. An uncertain STARTED blocks replay.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def claim(config, config_sha256, script, script_sha256, predecessor,
          predecessor_sha256, *, invocation, pid, now):
    config, script, predecessor = map(Path, (config, script, predecessor))
    uuid.UUID(invocation)
    if config.parent.resolve() != script.parent.resolve() or pid <= 0:
        raise ValueError('exact prepared script directory and process required')
    for path, expected in ((config, config_sha256), (script, script_sha256),
                           (predecessor, predecessor_sha256)):
        if digest(path) != expected:
            raise ValueError('prepared script or predecessor changed')
    if json.loads(config.read_bytes())['entrypoint_sha256'] != script_sha256:
        raise ValueError('config does not bind this script')
    if json.loads(predecessor.read_bytes()).get('complete') is not True:
        raise ValueError('accepted predecessor required')
    folder = config.parent
    if any((folder / name).exists() for name in ('STARTED.private.json', 'RESULT.private.json', 'STOP.private.json')):
        raise ValueError('existing dispatch must be reconciled; no replay')
    receipt = dict(at=now, config_sha256=config_sha256, entrypoint_sha256=script_sha256,
                   predecessor_sha256=predecessor_sha256, invocation=invocation, pid=pid)
    # Exclusive creation protects concurrent launch attempts before any payload IO.
    with (folder / 'STARTED.private.json').open('x') as stream:
        json.dump(receipt, stream, sort_keys=True)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    fd = os.open(folder, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('config', 'config-sha256', 'script', 'script-sha256', 'predecessor', 'predecessor-sha256'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    claim(**vars(args), invocation=os.environ['INVOCATION_ID'], pid=os.getpid(), now=time.time())
    os.execv(sys.executable, [sys.executable, '-B', args.script, '--sha256', args.config_sha256])


if __name__ == '__main__':
    main()
