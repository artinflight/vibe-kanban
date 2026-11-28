"""Production host qualification for one writer-owned archive invocation.

No service actions or fallback identities. Discover the current systemd process
births, verify the actual binaries/configuration/mounts, and retain those identities
through the finite transaction. Privileged process inspection is separately
source/policy pinned; an inaccessible process never implies consumer clearance.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time

from catalog import Conflict
import payloads


def pinned(ref):
    path = Path(ref['path'])
    payloads.parent_safe(path)
    st = path.lstat()
    if (path.resolve(strict=True) != path or not stat.S_ISREG(st.st_mode)
            or st.st_uid not in (0, os.getuid()) or st.st_nlink != 1 or st.st_mode & 0o022):
        raise Conflict('Canonical owned source/configuration required')
    with path.open('rb') as stream:
        value = stream.read()
    if hashlib.sha256(value).hexdigest() != ref['sha256'] or payloads.signature(path.lstat()) != payloads.signature(st):
        raise Conflict('Qualified source/configuration changed')
    return value


def process_identity(pid):
    base = Path('/proc') / str(pid)
    fields = (base / 'stat').read_text().rsplit(')', 1)[1].split()
    binary = (base / 'exe').stat()
    return (fields[19], payloads.signature(binary))


def unit(name):
    if not re.fullmatch(r'[a-zA-Z0-9_.@:-]+\.service', name):
        raise Conflict('Exact configured service unit required')
    result = subprocess.run(['systemctl', '--user', 'show', name, '-p', 'MainPID', '-p', 'InvocationID',
        '-p', 'ActiveState', '-p', 'FreezerState', '-p', 'ControlGroup'], check=True,
        capture_output=True, text=True, timeout=10)
    return dict(row.split('=', 1) for row in result.stdout.splitlines())


def readonly_mount(pid, path):
    decode = lambda value: re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), value)
    mounts = [(Path(decode(row.split()[4])), set(row.split()[5].split(',')))
              for row in Path('/proc', str(pid), 'mountinfo').read_text().splitlines()]
    target = Path(path)
    ancestors = [(p, modes) for p, modes in mounts if p == target or p in target.parents]
    if (not ancestors or 'ro' not in max(ancestors, key=lambda r: len(r[0].parts))[1]
            or any(target in p.parents and 'ro' not in modes for p, modes in mounts)):
        raise Conflict('Protected reader binding is not actually read-only')


def member_pids(group):
    base = Path('/sys/fs/cgroup') / group.lstrip('/')
    if not group.startswith('/') or '..' in Path(group).parts or base.resolve(strict=True) != base:
        raise Conflict('Canonical serving control group required')
    result = set()
    for path in (base / 'cgroup.procs', *base.glob('**/cgroup.procs')):
        result.update(int(p) for p in path.read_text().splitlines())
    return result


class Host:
    def __init__(self, config, custody, configuration_ref, *, writer_child=True):
        self.config, self.custody = config, custody
        self.writer_child = writer_child
        self.configuration_ref = configuration_ref
        self.runtime_versions = {}
        self.readers, self.sources = {}, {}
        self.checked_at = float('-inf')
        self.staging = Path(config['staging_root'])
        self.mount = Path(config['storage_mount'])
        if (self.mount != Path('/mnt/vk-storage') or not os.path.ismount(self.mount)
                or not self.staging.is_relative_to(self.mount)
                or self.staging.resolve(strict=True) != self.staging):
            raise Conflict('Private staging on mounted secondary SSD required')
        self.mount_identity = (self.mount.stat().st_dev, self.mount.stat().st_ino)
        if self.staging.stat().st_dev != self.mount_identity[0]:
            raise Conflict('Staging storage is not the qualified SSD')
        # These are the retained admission floors, not a new quota or scheduler.
        resources = config['resources']
        for key in ('ssd_reserve_bytes', 'active_reserve_bytes', 'memory_floor_bytes'):
            if type(resources[key]) is not int or resources[key] < 0:
                raise Conflict('Explicit qualified resource floors required')
        if resources['memory_full_avg10_max'] < 0:
            raise Conflict('Qualified memory pressure limit required')

    def qualify(self):
        if self.readers:
            self.check()
            self.check_boundary()
            return
        if set(self.config['readers']) != {'writer', 'protected'}:
            raise Conflict('Complete current writer/protected reader pair required')
        for role, row in self.config['readers'].items():
            artifact = Path(row['artifact']['path'])
            artifact_info = artifact.lstat()
            if (artifact.resolve(strict=True) != artifact or not stat.S_ISREG(artifact_info.st_mode)
                    or artifact_info.st_uid not in (0, os.getuid()) or artifact_info.st_mode & 0o022):
                raise Conflict('Qualified serving artifact is not a canonical owned file')
            with artifact.open('rb') as body:
                if hashlib.file_digest(body, 'sha256').hexdigest() != row['artifact']['sha256']:
                    raise Conflict('Qualified serving artifact hash differs')
            if payloads.signature(artifact.lstat()) != payloads.signature(artifact_info):
                raise Conflict('Serving artifact changed during verification')
            state = unit(row['unit'])
            if state['ActiveState'] != 'active' or state['FreezerState'] != 'running' or not state['InvocationID']:
                raise Conflict('Configured serving reader is not running')
            expected = artifact.stat()
            matches = []
            for pid in member_pids(state['ControlGroup']):
                try:
                    st = Path('/proc', str(pid), 'exe').stat()
                    if (st.st_dev, st.st_ino) == (expected.st_dev, expected.st_ino):
                        matches.append(pid)
                except FileNotFoundError:
                    continue
            if len(matches) != 1:
                raise Conflict('Actual serving executable is not uniquely bound to its unit')
            pid = matches[0]
            birth = process_identity(pid)
            if birth[1] != payloads.signature(artifact_info):
                raise Conflict('Actual serving binary differs from the verified artifact inode')
            result = subprocess.run(['/proc/' + str(pid) + '/exe', '--build-info'], check=True,
                                    capture_output=True, timeout=15)
            if len(result.stdout) > 65536:
                raise Conflict('Serving capability response exceeded its protocol')
            info = json.loads(result.stdout)
            required = dict(workspaceArchiveCustodyProtocol=1, executionLogMutationLockProtocol=1,
                            automaticWorkspaceDeletion=False, automaticAttachmentCleanup=False)
            if any(info.get(k) != v for k, v in required.items()) or info.get('sourceCommit') != row['source_commit']:
                raise Conflict('Actual binary lacks the qualified archive/custody/cleanup contract')
            if role == 'writer' and (pid != int(state['MainPID']) or (self.writer_child and os.getppid() != pid)):
                raise Conflict('Physical helper was not spawned by the current serving writer')
            self.readers[role] = dict(pid=pid, birth=birth, unit=state)
        for ref in self.config['source_pins']:
            pinned(ref)
            self.sources[ref['path']] = payloads.signature(Path(ref['path']).lstat())
        self.check_boundary()

    def check(self):
        self.custody.check()
        if set(self.readers) != {'writer', 'protected'}:
            raise Conflict('Serving pair has not been qualified')
        for observed in self.readers.values():
            if process_identity(observed['pid']) != observed['birth']:
                raise Conflict('Serving process or binary changed during archival')
        if self.writer_child and os.getppid() != self.readers['writer']['pid']:
            raise Conflict('Serving writer no longer owns this helper')
        for path, version in self.sources.items():
            if payloads.signature(Path(path).lstat()) != version:
                raise Conflict('Archive release input changed during invocation')
        # Byte loops check births and custody every block. Slow service/resource
        # metadata is refreshed on the established five-second guard cadence.
        if time.monotonic() - self.checked_at >= 5:
            self.check_boundary()

    def check_boundary(self):
        self.custody.check()
        if (not os.path.ismount(self.mount)
                or (self.mount.stat().st_dev, self.mount.stat().st_ino) != self.mount_identity):
            raise Conflict('Secondary SSD identity changed')
        for role, observed in self.readers.items():
            row, pid = self.config['readers'][role], observed['pid']
            if unit(row['unit']) != observed['unit'] or process_identity(pid) != observed['birth']:
                raise Conflict('Current service invocation changed')
            env = dict(v.split(b'=', 1) for v in Path('/proc', str(pid), 'environ').read_bytes().split(b'\0') if b'=' in v)
            required = row['required_environment']
            protected = {'DISABLE_ATTACHMENT_CLEANUP': '1', 'DISABLE_STATUS_WORKTREE_CLEANUP': '1',
                         'DISABLE_WORKTREE_CLEANUP': '1'}
            if role == 'writer':
                protected['VK_CODEX_MAX_ACTIVE_EXECUTIONS'] = '8'
            if any(required.get(k) != v for k, v in protected.items()):
                raise Conflict('Existing cleanup/capacity settings were omitted from qualification')
            if any(env.get(k.encode()) != v.encode() for k, v in required.items()):
                raise Conflict('Selected serving settings differ')
            if not row['bindings']:
                raise Conflict('Actual serving data/configuration bindings required')
            for binding in row['bindings']:
                source = Path(binding['source'])
                actual = Path('/proc', str(pid), 'root') / binding['inside'].lstrip('/')
                a, b = actual.stat(), source.stat()
                if (a.st_dev, a.st_ino) != (b.st_dev, b.st_ino):
                    raise Conflict('Actual serving data/configuration mount differs')
                if binding['readonly']:
                    readonly_mount(pid, binding['inside'])
            required_sources = {self.config['database'], self.config['sessions_root'],
                                self.config['native_state'], str(self.custody.root)}
            if not required_sources <= {b['source'] for b in row['bindings']}:
                raise Conflict('Required current catalog/native/history/custody bindings omitted')
            if role == 'protected' and any(not b['readonly'] for b in row['bindings']
                                           if b['source'] in required_sources - {str(self.custody.root)}):
                raise Conflict('Protected current catalog and history must be mounted read-only')
            runtime_ref = row['runtime_configuration']
            # Runtime JSON contains the driver-config hash, so hashing it back
            # into that same config would create an impossible hash cycle.
            # Instead verify its exact semantic binding to the already pinned
            # driver/config and retain its immutable inode/version for this call.
            observed_ref = dict(runtime_ref, sha256=hashlib.sha256(Path(runtime_ref['path']).read_bytes()).hexdigest())
            runtime = json.loads(pinned(observed_ref))
            version = payloads.signature(Path(runtime_ref['path']).lstat())
            if self.runtime_versions.setdefault(role, version) != version:
                raise Conflict('Serving runtime file changed during invocation')
            driver_ref = next((ref for ref in self.config['source_pins'] if ref['path'] == runtime['driver']), None)
            if (driver_ref is None or runtime['driver_sha256'] != driver_ref['sha256']
                    or runtime['driver_configuration'] != self.configuration_ref['path']
                    or runtime['driver_configuration_sha256'] != self.configuration_ref['sha256']):
                raise Conflict('Serving runtime is not bound to this exact physical driver')
            if (runtime['role'] != ('writer' if role == 'writer' else 'reader')
                    or runtime['custody_root'] != str(self.custody.root)
                    or runtime['database'] != next(b['inside'] for b in row['bindings'] if b['source'] == self.config['database'])
                    or required.get('VK_WORKSPACE_ARCHIVE_CONFIG') != runtime_ref['inside']):
                raise Conflict('Serving archive runtime has different ownership or role')
            inside = Path('/proc', str(pid), 'root') / runtime_ref['inside'].lstrip('/')
            if hashlib.sha256(inside.read_bytes()).hexdigest() != observed_ref['sha256']:
                raise Conflict('Actually served archive runtime configuration differs')
        self.resources()
        self.checked_at = time.monotonic()

    def resources(self):
        limits = self.config['resources']
        available = os.statvfs(self.mount)
        memory = int(next(r.split()[1] for r in Path('/proc/meminfo').read_text().splitlines()
                          if r.startswith('MemAvailable:'))) * 1024
        pressure = next(r for r in Path('/proc/pressure/memory').read_text().splitlines() if r.startswith('full '))
        full = float(dict(p.split('=') for p in pressure.split()[1:])['avg10'])
        if (available.f_bavail * available.f_frsize < limits['ssd_reserve_bytes']
                or memory < limits['memory_floor_bytes'] or full > limits['memory_full_avg10_max']):
            raise Conflict('Existing archive resource admission is held')

    def check_processes(self, roots, identities=()):
        self.check()
        from process_probe import inspect
        inspect(self.config['process_inspector'], self.custody, roots, identities)
        self.check()

    def reserve_restore(self, tree, stage):
        self.check()
        allowed = [Path(p) for p in self.config['temporary_roots']]
        if not any(p in stage.parents for p in allowed):
            raise Conflict('Restore staging lies outside qualified temporary ownership')
        if stage.parent.stat().st_dev != self.mount_identity[0]:
            raise Conflict('Backup staging must remain on the secondary SSD')
        self.space(tree['entries'], stage.parent, self.config['resources']['ssd_reserve_bytes'])

    def reserve_publication(self, tree, index, destination):
        self.check()
        if str(destination) != tree['roots'][index]:
            raise Conflict('Publication destination differs from verified ownership')
        payloads.parent_safe(destination)
        self.space([r for r in tree['entries'] if r['root'] == index], destination.parent,
                   self.config['resources']['active_reserve_bytes'])

    @staticmethod
    def space(entries, parent, reserve):
        fs = os.statvfs(parent)
        block = fs.f_frsize
        needed = sum(((r['bytes'] + block - 1) // block) * block if r['kind'] == 'file' else block for r in entries)
        if fs.f_bavail * block < needed + reserve or fs.f_favail < len(entries):
            raise Conflict('Destination cannot accommodate the complete verified restoration')
