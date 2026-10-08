"""Bound PR229 archive/provider contracts; no capture, SSH reconfiguration or launch.

Verification drains every archive before its index is accepted. Materialization
streams selected members once per contributing archive. Payload is never cached.
Default reads use the unchanged authenticated Desktop Archive implementation.
Explicit test factories are marked fixture-only and cannot authorize deployment.
"""
import base64
import copy
from contextlib import contextmanager
from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath

from vk_archive_store import Archive, reference
from vk_candidate_generation import Blocked, digest, require, relative, validate_manifest, inventory

PR229 = "754129c5fff55da2f5598d8c7beb4d4325587ead"
MAX_INDEX_BYTES = 64 * 1024**2


def source_pins():
    root = Path(__file__).parent
    receipt = json.loads((root / 'receipts/direct-stream-20261008.json').read_text())
    require(len(receipt['source_sha256']) == 8, 'reviewed direct-B source inventory incomplete')
    for raw, expected in receipt['source_sha256'].items():
        require(raw.startswith('scripts/deployment/') and '..' not in PurePosixPath(raw).parts,
                'unsafe reviewed source selector')
        require(hashlib.sha256((root / Path(raw).name).read_bytes()).hexdigest() == expected,
                'reviewed direct-B source hash changed: ' + Path(raw).name)
    return dict(receipt['source_sha256'])


def metadata(member):
    require(member.uid >= 0 and member.gid >= 0, "invalid archived numeric ownership")
    row = {"mode": member.mode, "uid": member.uid, "gid": member.gid,
           "mtime_ns": int(Decimal(member.pax_headers.get("mtime", str(member.mtime))) * 10**9),
           "xattrs": {k[len("SCHILY.xattr."):]: base64.b64encode(v.encode("utf-8", "surrogateescape")).decode()
                      for k, v in member.pax_headers.items() if k.startswith("SCHILY.xattr.")}}
    for k in member.pax_headers:
        if k.startswith("SCHILY.acl."):
            required = "system.posix_acl_default" if k.endswith("default") else "system.posix_acl_access"
            require(required in row["xattrs"], "ACL text has no binary restoration proof")
    return row


class DirectBProvider:
    def __init__(self, namespace_scope_sha256, required_databases, *, archive_factory=Archive,
                 fixture_only=False):
        require(archive_factory is Archive or fixture_only, "custom archive factory requires explicit fixture mode")
        self.scope = namespace_scope_sha256
        self.required = tuple(required_databases)
        self.factory, self.fixture_only = archive_factory, fixture_only
        self.source_hashes = source_pins()
        self.records, self.indexes = {}, {}

    def register(self, capture_id, result, source_plan, source_scope, source_prefix,
                 *, origin_root_binding, source_commit=PR229):
        require(capture_id not in self.records, "capture registration is immutable")
        require(source_commit == PR229, "direct-B source head mismatch")
        require(result.get("passed") is True and result.get("direct_stream") is True
                and result.get("local_archive_bytes") == 0 and result.get("local_snapshot_bytes") == 0,
                "capture was not accepted by direct-B provider")
        require(result.get("metadata_receipt", {}).get("desktop_verified") is True,
                "backup metadata publication is unverified")
        published = copy.deepcopy(result)
        metadata_receipt = published.pop('metadata_receipt')
        published['frozen_boundary_verified'] = False
        published['handover_acceptance_pending'] = bool(result.get('frozen_boundary_requested'))
        body = (json.dumps(published, sort_keys=True, indent=2) + '\n').encode()
        require(metadata_receipt.get('sha256') == hashlib.sha256(body).hexdigest(),
                'published recovery descriptor digest differs from capture result')
        require(result["plan_sha256"] == source_plan and result["scope_sha256"] == source_scope,
                "raw backup plan/scope binding mismatch")
        prefix = Path(source_prefix)
        require(prefix.is_absolute() and str(prefix) == str(prefix.resolve()), "source namespace prefix is aliased")
        self.records[capture_id] = {"result": copy.deepcopy(result), "plan": source_plan, "scope": source_scope,
                                   "prefix": str(prefix), "origin": origin_root_binding}

    def mapped(self, raw, record):
        path = PurePosixPath('/' + raw.lstrip('/'))
        require('..' not in path.parts, "archive path traversal")
        prefix = PurePosixPath(record['prefix'])
        require(path == prefix or path.is_relative_to(prefix), "archive member outside pinned namespace prefix")
        value = path.relative_to(prefix).as_posix()
        return '' if value == '.' else str(relative(value))

    def archives(self, record):
        current, seen, archives = reference(record['result']), set(), []
        while current:
            require(len(archives) < 128 and current['sha256'] not in seen, "backup parent chain cycle/bound exceeded")
            seen.add(current['sha256'])
            archive = self.factory(current, desktop_only=True)
            manifest = archive.manifest()  # Complete stream hash checked by Archive.
            require(manifest['plan_sha256'] == record['plan'] and manifest['scope_sha256'] == record['scope'],
                    "archive parent scope mismatch")
            archives.append((archive, manifest))
            current = manifest['parent']
        require(bool(archives), "empty backup chain")
        return list(reversed(archives))

    def verify(self, capture_id):
        record = self.records[capture_id]
        entries, locations, headers = {}, {}, {}
        archives = self.archives(record)
        for index, (archive, manifest) in enumerate(archives):
            snapshots = {'payload/' + r['path']: (self.mapped(raw, record), r['sha256'])
                         for raw, r in manifest['sqlite_snapshots'].items()}
            seen, found_snapshots = set(), set()
            with archive.contents() as tar:
                for member in tar:
                    if member.name == 'payload/manifest.json':
                        continue  # Archives.manifest already authenticated it exactly.
                    if member.name in snapshots:
                        name, expected_hash = snapshots[member.name]
                        found_snapshots.add(member.name)
                    else:
                        require(not member.name.startswith('payload/'), "unrecognized backup payload")
                        name, expected_hash = self.mapped(member.name, record), None
                    require(name not in seen, "duplicate candidate archive member")
                    seen.add(name)
                    if not name:
                        require(member.isdir(), "namespace root is not a directory")
                        continue  # Fixture namespace context; header stays authenticated on B.
                    row = metadata(member)
                    if member.isdir():
                        row['kind'] = 'directory'
                    elif member.isfile():
                        with tar.extractfile(member) as stream:
                            sha = hashlib.file_digest(stream, 'sha256').hexdigest()
                        require(expected_hash is None or sha == expected_hash, "SQLite snapshot differs from archive manifest")
                        row.update(kind='file', sha256=sha, bytes=member.size)
                        locations[name] = (index, member.name)
                    elif member.issym():
                        target = member.linkname
                        if target.startswith('/') and record['prefix'] != '/':
                            target = '/' + self.mapped(target, record)
                        row.update(kind='symlink', target=target)
                    elif member.islnk():
                        row.update(kind='hardlink', target=self.mapped(member.linkname, record))
                    else:
                        raise Blocked('unsupported archived special file')
                    entries[name] = row
                    headers[name] = dict(member.pax_headers)
            require(found_snapshots == snapshots.keys(), "archive omitted SQLite snapshots")
            for raw in manifest['absent_paths']:
                absent = self.mapped(raw, record)
                require(bool(absent), "archive removed the namespace root")
                for name in list(entries):
                    if name == absent or name.startswith(absent + '/'):
                        entries.pop(name)
                        locations.pop(name, None)
                        headers.pop(name, None)
            require(len(json.dumps(entries).encode()) <= MAX_INDEX_BYTES, "candidate index exceeds metadata budget")
        # Canonicalize authenticated hardlink groups for exact candidate inventory.
        groups = {}
        for name, row in entries.items():
            if row['kind'] not in ('file', 'hardlink'):
                continue
            target, visited = name, set()
            while entries.get(target, {}).get('kind') == 'hardlink':
                require(target not in visited, "archived hardlink cycle")
                visited.add(target)
                target = entries[target]['target']
            require(entries.get(target, {}).get('kind') == 'file', "archived hardlink target unavailable")
            groups.setdefault(target, []).append(name)
        for target, names in groups.items():
            primary = min(names)
            source_row, location = dict(entries[target]), locations[target]
            for name in names:
                entries[name] = {**source_row, 'kind': 'file' if name == primary else 'hardlink'}
                if name != primary:
                    entries[name]['target'] = primary
            locations[primary] = location
        validate_manifest(entries)
        require(set(self.required) <= entries.keys(), "required operational database absent")
        result = record['result']
        proof = {'provider': 'desktop-B', 'scope_sha256': self.scope, 'capture_id': capture_id,
                 'full_current_state': True, 'entries': entries, 'manifest_sha256': digest(entries),
                 'origin_root_binding': record['origin'], 'writer_fence': result.get('writer_fence'),
                 'frozen_boundary_verified': result.get('frozen_boundary_verified'),
                 'fixture_only': self.fixture_only, 'source_commit': PR229,
                 'metadata_limits': 'PAX retained; built-in comparison covers current UID/GID, mode, mtime, POSIX ACL/user xattrs and links. Atime is not restored; original inode/ctime/birthtime are unsupported. Foreign ownership/other xattrs block; full operational metadata acceptance remains required'}
        self.indexes[capture_id] = {'proof': proof, 'archives': archives, 'locations': locations, 'headers': headers}
        return copy.deepcopy(proof)

    @contextmanager
    def file_members(self, capture_id, selected):
        indexed = self.indexes[capture_id]
        require(set(selected) <= indexed['proof']['entries'].keys(), "requested member outside verified index")

        def members():
            seen = set()
            by_archive = {}
            for name in selected:
                index, member_name = indexed['locations'][name]
                by_archive.setdefault(index, {})[member_name] = name
            for index, wanted in sorted(by_archive.items()):
                archive, _ = indexed['archives'][index]
                with archive.contents() as tar:
                    for member in tar:
                        if member.name in wanted:
                            name = wanted[member.name]
                            require(name not in seen and member.isfile(), "replay member duplicate/type changed")
                            with tar.extractfile(member) as stream:
                                yield name, stream
                            seen.add(name)
            require(seen == set(selected), "verified chain omitted requested replay member")
        iterator = members()
        try:
            yield iterator
            # Force EOF/full archive hash even if a caller stops early.
            for _ in iterator:
                pass
        finally:
            iterator.close()


class BoundSupervisor:
    """Read-only proof/lease supervisor; every operational activation is blocked.

    An owning controller supplies source-bound acceptance receipts from its real
    tests. This class never freezes a service, contacts an API or changes a route.
    Offline fixtures subclass only the activation intents, never safety checks.
    """
    def __init__(self, layout, source, scope, policy, fallback_artifact, *, fixture_only=False):
        self.layout, self.source, self.scope = layout.validate(), source, scope
        self.policy, self.fallback_artifact = policy, fallback_artifact
        require(not policy.get('fixture_only') or fixture_only, 'fixture capacity policy is not operational evidence')
        self.fixture_only = fixture_only
        self.capture = None
        self.fd = None
        self.stopped_proofs, self.acceptance_proofs = {}, {}
        self.acceptance_reader = None

    def held_fence(self, fd, capture_id):
        info = os.fstat(fd)
        require(info.st_uid == os.getuid(), 'writer lease not owned')
        self.fd, self.capture = fd, capture_id
        return {'verified': True, 'capture_id': capture_id, 'scope': self.scope,
                'lease': f'{info.st_dev}:{info.st_ino}'}

    def verify_fence(self, verified):
        require(not verified.get('fixture_only') or self.fixture_only, 'fixture archive proof is not operational fencing')
        require(self.fd is not None and verified['capture_id'] == self.capture
                and verified.get('frozen_boundary_verified') is True,
                'fresh held writer fence missing')
        expected = self.held_fence(self.fd, self.capture)
        require(verified.get('writer_fence') == expected, 'capture/lease fence binding differs')
        # A second independent open must observe the held kernel lease.
        path = Path('/proc/self/fd') / str(self.fd)
        probe = os.open(path, os.O_RDONLY)
        try:
            try:
                fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return expected
            raise Blocked('writer lease is no longer held')
        finally:
            os.close(probe)

    def verify_stopped(self, binding):
        proof = self.stopped_proofs.get(binding)
        require(proof is not None and (not proof.get('fixture_only') or self.fixture_only),
                'fixture stop proof is not operational evidence')
        require(proof is not None and proof.get('source') == self.source and proof.get('scope') == self.scope
                and proof.get('root_binding') == binding and proof.get('all_declared_writers_stopped') is True,
                'source/root-bound all-writer stop proof missing')

    def verify_capacity(self, verified, layout, stage, payload_bytes):
        require(layout == self.layout and self.policy.get('source') == self.source
                and self.policy.get('scope') == self.scope and self.policy.get('measured') is True,
                'measured target capacity proof missing')
        return {'policy_sha256': digest(self.policy), 'scope': self.scope, 'source': self.source,
                'capture_id': verified['capture_id'], 'stage': stage, 'payload_bytes': payload_bytes,
                'reserve_bytes': self.policy['reserve_bytes']}

    def acceptance(self, binding, source, scope, stage):
        require(binding == self.layout.binding() and source == self.source and scope == self.scope,
                'acceptance requested for different source/root')
        # Normalization can replace a DB inode immediately before acceptance.
        # The approved owner reads fresh independent evidence at that point;
        # never accept the pre-normalization receipt or blanket-clear anything.
        proof = (self.acceptance_reader(stage, self.capture) if self.acceptance_reader is not None
                 else self.acceptance_proofs.get(stage))
        require(proof is not None and (not proof.get('fixture_only') or self.fixture_only),
                'fixture acceptance is not operational evidence')
        require(proof is not None and proof.get('capture_id') == self.capture
                and proof.get('root_binding') == binding and proof.get('stage') == stage
                and proof.get('manifest_sha256') == digest(inventory(self.layout.tree)),
                'fresh application acceptance proof missing/stale')
        return copy.deepcopy(proof)

    def activate_candidate(self, proof, receipt):
        raise Blocked('Offline supervisor has no operational activation authority')

    def activate_compatible_fallback(self, proof, receipt):
        raise Blocked('Offline supervisor has no operational fallback authority')
