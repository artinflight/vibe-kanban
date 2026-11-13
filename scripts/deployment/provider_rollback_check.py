#!/usr/bin/env python3
"""Read-only planning guard, NEVER restart/rollback authorization or a backend.
Catalog provenance must be independently bound to the supplied binary by its
reviewed build receipt. Even matching metadata requires actual latest-data rehearsal.
"""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess

VERSION = 20261021140000
TABLES = ('provider_handoff_reservations', 'provider_failover_activations')


def catalog(repo, ref=None):
    if ref:
        # Resolve a commit object first. No remote, mutable branch checkout or hook.
        ref = subprocess.check_output(['git', 'rev-parse', '--verify', ref + '^{commit}'], cwd=repo, text=True).strip()
        names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', ref, '--', 'crates/db/migrations'], cwd=repo, text=True).splitlines()
        read = lambda name: subprocess.check_output(['git', 'show', ref + ':' + name], cwd=repo)
    else:
        names = [str(p.relative_to(repo)) for p in sorted((repo/'crates/db/migrations').glob('*.sql'))]
        read = lambda name: (repo/name).read_bytes()
    if len(names) > 1000:
        raise ValueError('migration catalog bound exceeded')
    result = {}
    for name in names:
        match = re.fullmatch(r'(\d+)_.+\.sql', Path(name).name)
        if not match or name.endswith('.down.sql'):
            continue
        raw = read(name)
        if len(raw) > 1024*1024:
            raise ValueError('migration size bound exceeded')
        version = int(match[1])
        if version in result:
            raise ValueError('duplicate migration version')
        # SQLx Migration::new hashes the unmodified SQL string using SHA384.
        result[version] = hashlib.sha384(raw).hexdigest()
    return result


def metadata(connection):
    connection.row_factory = sqlite3.Row
    applied = connection.execute('SELECT version,success,hex(checksum) checksum FROM _sqlx_migrations ORDER BY version LIMIT 1001').fetchall()
    if len(applied) > 1000:
        raise ValueError('applied migration bound exceeded')
    objects = connection.execute("SELECT name,type,sql FROM sqlite_master WHERE name LIKE 'provider_handoff%' OR name LIKE 'provider_failover%' OR name LIKE 'provider_activation%' ORDER BY name").fetchall()
    installed = {r['name'] for r in objects if r['type'] == 'table'}
    owners = {}
    for table in TABLES:
        owners[table] = (dict(connection.execute('SELECT state,count(*) FROM '+table+' GROUP BY state').fetchall())
                         if table in installed else None)
    # No prompts, execution IDs, account data or native history are read.
    return {'applied': [dict(r) for r in applied], 'tables': sorted(installed),
            'owners': owners,
            'schemaDigest': hashlib.sha256(json.dumps([tuple(r) for r in objects],sort_keys=True).encode()).hexdigest()}


def assess(snapshot, candidate, fallback):
    blockers = []
    def block(code, **details): blockers.append(dict(code=code, **details))
    if any(not r['success'] for r in snapshot['applied']):
        block('dirty_migration')
    missing = sorted(set(candidate) - set(fallback))
    if missing:
        block('fallback_catalog_missing_planned_versions', versions=missing)
    for row in snapshot['applied']:
        v = row['version']
        if v not in fallback:
            block('fallback_catalog_missing_applied_version', version=v)
        elif fallback[v].lower() != row['checksum'].lower():
            block('fallback_migration_checksum_mismatch', version=v)
        if candidate.get(v, '').lower() != row['checksum'].lower():
            block('candidate_migration_checksum_mismatch', version=v)
    mismatch = sorted(v for v in set(candidate) & set(fallback) if candidate[v] != fallback[v])
    if mismatch:
        block('fallback_planned_checksum_mismatch', versions=mismatch)
    if snapshot['tables'] and set(snapshot['tables']) != set(TABLES):
        block('provider_schema_incomplete')
    if any(states and any(n for state,n in states.items() if state != 'released') for states in snapshot['owners'].values()):
        block('latest_data_owner_recovery_unverified', action='retain_reservations_and_rehearse_matched_fallback')
    return {'contractVersion':'vk.provider-rollback-check.v1','scope':'metadata-only',
            'status':'blocked' if blockers else 'rehearsal_required', 'blockers':blockers,
            'runtimeCompatibilityVerified':False,'providerStarted':False,
            'destructiveDownMigrationAllowed':False,'reservationReleaseAllowed':False,
            'latestDataRehearsalRequired':True,'providerSchemaPresent':bool(snapshot['tables'])}


def inspect(database, source_root, fallback_binary, expected_sha, fallback_ref):
    if not re.fullmatch(r'[a-f0-9]{40}|[a-f0-9]{64}', fallback_ref) or not re.fullmatch(r'[a-f0-9]{64}', expected_sha):
        raise ValueError('immutable fallback source/binary pins required')
    digest = hashlib.sha256()
    with fallback_binary.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''): digest.update(chunk)
    if digest.hexdigest() != expected_sha:
        raise ValueError('fallback binary hash mismatch')
    candidate, fallback = catalog(source_root), catalog(source_root, fallback_ref)
    with closing(sqlite3.connect(database.resolve().as_uri()+'?mode=ro', uri=True, timeout=.5)) as connection:
        connection.execute('PRAGMA query_only=ON')
        connection.execute('BEGIN')
        snapshot = metadata(connection)
    result = assess(snapshot,candidate,fallback)
    result.update(fallbackSha256=expected_sha, fallbackSourceRef=fallback_ref,
                  provenance='operator-supplied build binding; not runtime rehearsal',
                  appliedMigrationCount=len(snapshot['applied']), providerSchemaDigest=snapshot['schemaDigest'])
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--database',type=Path,required=True)
    p.add_argument('--source-root',type=Path,required=True)
    p.add_argument('--fallback-binary',type=Path,required=True)
    p.add_argument('--fallback-sha256',required=True)
    p.add_argument('--fallback-source-ref',required=True)
    a=p.parse_args()
    try:
        result=inspect(a.database,a.source_root.resolve(),a.fallback_binary,a.fallback_sha256,a.fallback_source_ref)
    except (OSError,ValueError,sqlite3.Error,subprocess.SubprocessError):
        result={'status':'blocked','code':'rollback_metadata_or_identity_unavailable','runtimeCompatibilityVerified':False}
    print(json.dumps(result,sort_keys=True))
    return 2 if result['status']=='blocked' else 3  # 3 is NOT acceptance.

if __name__=='__main__':raise SystemExit(main())
