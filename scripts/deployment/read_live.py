"""Read back a recorded deployment without changing services, data or routing.

Outputs only allowlisted service identity, route contracts, public asset hashes
and database metadata. Never reads session history or account credential files.
A passing observation is not authority to restart or cut back the recorded PID.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import ssl
import subprocess
from urllib.parse import urlsplit
from urllib.request import urlopen


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def observe(manifest, ca):
    name = manifest['live_service']
    properties = ['MainPID', 'InvocationID', 'ActiveState', 'SubState',
                  'MemoryHigh', 'MemoryMax', 'MemorySwapMax', 'TasksMax']
    def service():
        command = ['systemctl', '--user', 'show', name]
        for prop in properties:
            command += ['-p', prop]
        return dict(line.split('=', 1) for line in subprocess.check_output(command, text=True).splitlines())
    before = service()
    pid = int(before['MainPID'])
    if pid <= 0:
        raise ValueError('Recorded service is not running')
    before['executable_sha256'] = digest(f'/proc/{pid}/exe')
    origin = manifest['public_origin'].rstrip('/')
    if urlsplit(origin).scheme != 'https':
        raise ValueError('Verified HTTPS public origin required')
    tls = ssl.create_default_context(cafile=ca)
    routes = []
    for base in (f"http://127.0.0.1:{int(manifest['backend_port'])}", origin):
        for path in ('/api/health', '/api/issue-workflows/capabilities', '/api/provider-admission/capabilities'):
            with urlopen(base + path, context=tls, timeout=15) as response:
                data = json.loads(response.read(65536))
                routes.append(dict(origin=base, path=path, status=response.status, data=data))
    with urlopen(origin + '/', context=tls, timeout=15) as response:
        html = response.read(1024 * 1024).decode()
    assets = sorted(set(re.findall(r'(?:src|href)="(/assets/[^"<>]+)"', html)))
    frontend = Path(manifest['public_frontend_pointer']).resolve(strict=True)
    asset_results = []
    for asset in manifest['public_assets']:
        if not re.fullmatch(r'/assets/[A-Za-z0-9_.-]+', asset):
            raise ValueError('Literal public asset name required')
        local_hash = digest(frontend / asset.lstrip('/'))
        with urlopen(origin + asset, context=tls, timeout=30) as response:
            remote_hash = hashlib.file_digest(response, 'sha256').hexdigest()
        asset_results.append(dict(path=asset, present=asset in assets, sha256=local_hash,
                                  public_bytes_match=remote_hash == local_hash))
    database = Path(manifest['live_database']).resolve(strict=True)
    info = database.stat()
    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as db:
        migrations = db.execute('SELECT COUNT(*) FROM _sqlx_migrations WHERE success=1').fetchone()[0]
    after = service()
    stable = all(after[key] == before[key] for key in ('MainPID', 'InvocationID', 'ActiveState'))
    passed = (stable and before['ActiveState'] == 'active'
              and before['executable_sha256'] == manifest['live_binary_sha256']
              and str(database) == manifest['resolved_database']
              and migrations == manifest['database_migrations']
              and str(frontend) == manifest['public_frontend_release']
              and all(row['status'] == 200 and row['data'].get('success') for row in routes)
              and all(row['present'] and row['public_bytes_match'] for row in asset_results))
    return dict(UTC=datetime.now(timezone.utc).isoformat(), passed=passed, service=before,
                stable_service_identity=stable, frontend=str(frontend), assets=asset_results,
                database=dict(resolved=str(database), device=info.st_dev, inode=info.st_ino,
                              migrations=migrations), routes=routes, mutation_performed=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--ca', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if not os.path.ismount('/mnt/vk-storage') or not output.is_relative_to('/mnt/vk-storage'):
        raise ValueError('Receipt must be on mounted secondary SSD')
    # Reserve before observing, so a consumed receipt never causes repeated work.
    with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        result = observe(json.loads(args.manifest.read_text()), args.ca)
        json.dump(result, stream, indent=2)
    print(json.dumps(dict(passed=result['passed'], UTC=result['UTC'], mutation_performed=False)))
    return 0 if result['passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
