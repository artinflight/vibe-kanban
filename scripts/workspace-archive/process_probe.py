"""Client for the separately installed metadata-only workspace inspector.

No generic sudo, policy edits, fallback exemptions or helper installation. The
external manager owns that explicit installed capability and its root policy.
"""
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import time

from catalog import Conflict
from host import pinned, process_identity

HELPER = '/usr/local/sbin/vk-workspace-archive-inspect-v1'


def inspect(config, custody, roots, identities=()):
    if config['launcher']['path'] != HELPER:
        raise Conflict('Only the scoped installed workspace inspector is supported')
    for key in ('launcher', 'code'):
        pinned(config[key])
        if Path(config[key]['path']).stat().st_uid != 0:
            raise Conflict('Installed process inspector must remain root owned')
    custody.check()
    request = dict(abi=1, nonce=secrets.token_hex(32), owner_pid=os.getpid(),
                   owner_start=process_identity(os.getpid())[0], workspace_id=custody.path.stem,
                   roots=sorted(map(str, roots)), identities=sorted([list(p) for p in identities]))
    raw = json.dumps(request, sort_keys=True, separators=(',', ':')).encode()
    if len(raw) > 32 * 1024**2:
        raise Conflict('Process-inspection metadata exceeds its bounded protocol')
    started = time.monotonic_ns()
    result = subprocess.run(['sudo', '-n', '--', HELPER], input=raw, capture_output=True, timeout=65)
    custody.check()
    if result.returncode or len(result.stdout) > 65536:
        raise Conflict('Scoped workspace process clearance is unavailable or held')
    receipt = json.loads(result.stdout)
    if (receipt.get('abi') != 1 or receipt.get('nonce') != request['nonce']
            or receipt.get('request_sha256') != hashlib.sha256(raw).hexdigest()
            or receipt.get('owner_pid') != request['owner_pid']
            or receipt.get('owner_start') != request['owner_start']
            or receipt.get('code_sha256') != config['code']['sha256']
            or receipt.get('policy_sha256') != config['policy_sha256']
            or receipt.get('euid') != 0 or receipt.get('consumer_clearance_passed') is not True
            or receipt.get('production_changed') is not False
            or not started <= receipt['issued_mono_ns'] <= time.monotonic_ns()):
        raise Conflict('Process clearance does not bind this exact live owner/request/policy')
    return receipt
