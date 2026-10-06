#!/usr/bin/python3 -B
"""Deny confirmation/hold transport only; all real actions use the reviewed broker."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

root = Path(os.environ['VK_SYNTHETIC_ROOT'])
assert root.name.startswith('vk-continuation-http-')
tool = Path(sys.argv[0]).name
assert tool in ('systemctl', 'systemd-run')
args = sys.argv[1:]

def event(kind, **fields):
    with (root/'fault-manager-events.jsonl').open('a') as log:
        log.write(json.dumps({'atMs': int(time.time()*1000), 'kind': kind, 'tool': tool, 'args': args, **fields})+'\n')

# /usr/bin/{tool} is the read-only bind of fixture_manager_client.py, never
# the host manager. Preserve its private broker and independent lease guard.
event('forward')
if tool == 'systemctl' and 'show' in args and (root/'deny-exit-confirmation').exists():
    actual = subprocess.run(['/usr/bin/systemctl', *args], capture_output=True)
    event('verification-denied', actualExitCode=actual.returncode, actualOutput=actual.stdout.decode(errors='replace'))
    # Fail closed: cannot manufacture a successful exit or affect real authority.
    sys.exit(1)
result = subprocess.run(['/usr/bin/'+tool, *args])
event('broker-return', exitCode=result.returncode)
if tool == 'systemd-run' and '--pipe' in args:
    # Keep the controller-side transport open after the independently guarded
    # worker exits, so EOF cannot short-circuit the deliberate RPC stall.
    time.sleep(3)
    event('transport-released')
sys.exit(result.returncode)
