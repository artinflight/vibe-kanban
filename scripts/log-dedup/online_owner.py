"""Source-pinned host adapter for online closed-log batches; no service actions.

Config binds the current production readers, exact staged plan and Nightly's
selected-version configuration. The sole writable service must implement protocol
1; the other serving reader must have an actual read-only session mount. Runtime
bindings are collected fresh after activation, never copied from an old operation.
"""
from contextlib import contextmanager
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
import uuid

import graph
import log_dedup as logs
import nightly_graph
from reclaim import atomic_bytes, canonical
from scoped_fence import ClosedLogFence, WriterRoster, process_identity

PROTOCOL = 1
UNITS = {'main': 'vibe-kanban-native-review-20261015.service',
         'protected5650': 'vk-chat-history-readonly-20261010.service'}


class ResourceAdmissionError(logs.ArchiveError):
    def __init__(self, observation):
        self.observation = observation
        super().__init__('Existing online resource admission failed: ' + json.dumps(observation, sort_keys=True))


def resource_observation():
    if not os.path.ismount('/mnt/vk-storage'):
        raise logs.ArchiveError('Mounted SSD required')
    fs = os.statvfs('/mnt/vk-storage')
    mem = int(next(r.split()[1] for r in Path('/proc/meminfo').read_text().splitlines()
                   if r.startswith('MemAvailable:'))) * 1024
    full = next(r for r in Path('/proc/pressure/memory').read_text().splitlines() if r.startswith('full '))
    pressure = float(dict(p.split('=') for p in full.split()[1:])['avg10'])
    return dict(ssd_available_bytes=fs.f_bavail * fs.f_frsize,
                memory_available_bytes=mem, memory_full_avg10=pressure)


def pinned(ref):
    p = Path(ref['path'])
    before = logs.regular(p)
    if (not p.is_absolute() or p.resolve(strict=True) != p or before.st_uid != os.getuid()
            or before.st_nlink != 1 or before.st_mode & 0o022):
        raise logs.ArchiveError('Exact private source-pinned owner input required')
    raw = p.read_bytes()
    if logs.sha(raw) != ref['sha256'] or logs.version(logs.regular(p)) != logs.version(before):
        raise logs.ArchiveError('Pinned online owner input changed')
    return raw


def unit(name):
    raw = subprocess.check_output(['systemctl', '--user', 'show', name, '-p', 'MainPID',
                                   '-p', 'InvocationID', '-p', 'ActiveState', '-p', 'FreezerState', '-p', 'ControlGroup'],
                                  text=True, timeout=10)
    return dict(line.split('=', 1) for line in raw.splitlines())


def readonly_mount(pid, inside):
    """Check kernel mount options, including any nested writable overrides."""
    decode = lambda value: re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), value)
    mounts = [(Path(decode(row.split()[4])), set(row.split()[5].split(',')))
              for row in Path('/proc', str(pid), 'mountinfo').read_text().splitlines()]
    path = Path(inside)
    ancestors = [(p, opts) for p, opts in mounts if p == path or p in path.parents]
    if not ancestors or 'ro' not in max(ancestors, key=lambda r: len(r[0].parts))[1]:
        raise logs.ArchiveError('Protected history reader has a writable log mount')
    if any(path in p.parents and 'ro' not in opts for p, opts in mounts):
        raise logs.ArchiveError('Protected reader has a nested writable log mount')


class LiveReaders:
    def __init__(self, config, source_root):
        self.config, self.source = config, Path(source_root)
        self.resource_wait = config.get('resource_wait_seconds', 0)
        if type(self.resource_wait) is not int or not 0 <= self.resource_wait <= 600:
            raise logs.ArchiveError('Resource wait must fit the existing 600-second no-progress supervision')
        self.identities = {}
        if set(config['readers']) != set(UNITS):
            raise logs.ArchiveError('Exact current two-reader roster required')
        for name, row in config['readers'].items():
            required = {key: '1' for key in ('DISABLE_ATTACHMENT_CLEANUP',
                        'DISABLE_STATUS_WORKTREE_CLEANUP', 'DISABLE_WORKTREE_CLEANUP')}
            if name == 'main':
                required['VK_CODEX_MAX_ACTIVE_EXECUTIONS'] = '8'
            if any(row['required_environment'].get(k) != v for k, v in required.items()):
                raise logs.ArchiveError('Existing cleanup protection and selected capacity must remain bound')
            if not row['mounts']:
                raise logs.ArchiveError('Qualified native/database mounts required')
            if row['unit'] != UNITS[name]:
                raise logs.ArchiveError('Foreign serving unit')
            pid = row['server_pid']
            before = process_identity(pid)
            with Path('/proc', str(pid), 'exe').open('rb') as f:
                digest = hashlib.file_digest(f, 'sha256').hexdigest()
            if digest != row['sha256'] or process_identity(pid) != before:
                raise logs.ArchiveError('Actual reader differs from qualified artifact')
            self.identities[name] = before
        self.check()

    def check(self):
        started = time.monotonic()
        while True:
            observation = resource_observation()
            self.check_identities()
            if (observation['ssd_available_bytes'] >= 3 * 1024**3
                    and observation['memory_available_bytes'] >= 4 * 1024**3
                    and observation['memory_full_avg10'] <= .10):
                return
            error = ResourceAdmissionError(observation)
            wait = getattr(self, 'resource_wait', 0)
            if time.monotonic() - started >= wait:
                raise error
            # No read, publication or progress credit while resources are held.
            # Recheck identities and the unchanged floors before proceeding.
            print(json.dumps(dict(event='dedup_resource_wait', **observation)), flush=True)
            time.sleep(min(5, max(0, wait - (time.monotonic() - started))))

    def check_identities(self):
        for name, row in self.config['readers'].items():
            state = unit(row['unit'])
            pid = row['server_pid']
            if (state['ActiveState'] != 'active' or state['FreezerState'] != 'running'
                    or state['MainPID'] != str(row['main_pid']) or state['InvocationID'] != row['invocation']
                    or process_identity(pid) != self.identities[name]):
                raise logs.ArchiveError('Current serving reader changed or is paused')
            memberships = [r.split(':', 2)[2] for r in Path('/proc', str(pid), 'cgroup').read_text().splitlines()]
            if (not state['ControlGroup'] or not any(p == state['ControlGroup'] or p.startswith(state['ControlGroup'] + '/')
                    for p in memberships) or name == 'main' and pid != row['main_pid']):
                raise logs.ArchiveError('Qualified server is outside its actual serving unit')
            inside = Path('/proc', str(pid), 'root') / row['sessions_inside'].lstrip('/')
            a, b = inside.stat(), self.source.stat()
            if (a.st_dev, a.st_ino) != (b.st_dev, b.st_ino):
                raise logs.ArchiveError('Actual serving session root differs')
            if name == 'protected5650':
                readonly_mount(pid, row['sessions_inside'])
            for binding in row['mounts']:
                actual = Path('/proc', str(pid), 'root') / binding['inside'].lstrip('/')
                a, b = actual.stat(), Path(binding['source']).stat()
                if [a.st_dev, a.st_ino] != binding['identity'] or [b.st_dev, b.st_ino] != binding['identity']:
                    raise logs.ArchiveError('Required native/database reader mount changed')
            for ref in row.get('binding_files', []):
                pinned(ref)
            # Read only explicitly bound settings; never log process environment.
            env = dict(p.split(b'=', 1) for p in Path('/proc', str(pid), 'environ').read_bytes().split(b'\0') if b'=' in p)
            for key, value in row['required_environment'].items():
                if env.get(key.encode()) != value.encode():
                    raise logs.ArchiveError('Selected reader setting changed')


def nightly_modules(config):
    manifest = json.loads(pinned(config['manifest']))
    folder = Path(config['folder'])
    for name, sha in manifest['source_sha256'].items():
        pinned(dict(path=str(folder / name), sha256=sha))
    sys.path.insert(0, str(folder))
    modules = []
    for name in ('vk_nightly_owned_context', 'vk_nightly_owner_controls'):
        module = importlib.import_module(name)
        if Path(module.__file__) != folder / (name + '.py'):
            raise logs.ArchiveError('Foreign Nightly owner module')
        modules.append(module)
    raw = pinned(config['bridge'])
    bridge = importlib.util.module_from_spec(importlib.util.spec_from_loader('online_nightly_bridge', loader=None))
    bridge.__file__ = config['bridge']['path']
    exec(compile(raw, bridge.__file__, 'exec'), bridge.__dict__)
    return (*modules, bridge)


@contextmanager
def admit_online(config, plan, rollback=False, record=lambda phase,value:None):
    if (config['format'] != 'vk-scoped-online-owner-v1'
            or config['plan_sha256'] != logs.sha(canonical(plan))
            or not 3 * 1024**3 <= config['reserve_bytes'] <= 16 * 1024**3):
        raise logs.ArchiveError('Exact finite online owner configuration required')
    operation = uuid.UUID(config['operation']).hex
    readers = LiveReaders(config, plan['source_root'])
    main = config['readers']['main']
    roster = WriterRoster([dict(pid=main['server_pid'], sha256=main['sha256'])], readers.check)
    roster.qualify()  # No B operation or mutation-lock creation for an old writer.
    info = json.loads(subprocess.check_output(['/proc/' + str(main['server_pid']) + '/exe', '--build-info'], timeout=15))
    if info.get('automaticWorkspaceDeletion') is not False or info.get('automaticAttachmentCleanup') is not False:
        raise logs.ArchiveError('Incompatible automatic cleanup enabled')
    archive = Path(config['archive'])
    inventory = graph.inventory(archive, plan)
    receipts = Path(config['backup_receipts'])
    if (not receipts.is_absolute() or receipts.resolve() != receipts
            or not receipts.is_relative_to('/mnt/vk-storage') or receipts.is_relative_to(archive)
            or receipts.is_relative_to(plan['source_root'])):
        raise logs.ArchiveError('Separate canonical SSD recovery receipt folder required')
    receipts.mkdir(mode=0o700, parents=True, exist_ok=True)
    st = receipts.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
        raise logs.ArchiveError('Owned private recovery receipts required')
    # Single owner per operation, including preparation before execution locks.
    import fcntl
    fd = os.open(receipts / 'owner.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        lock_stat = os.fstat(fd)
        if (not stat.S_ISREG(lock_stat.st_mode) or lock_stat.st_uid != os.getuid()
                or lock_stat.st_nlink != 1 or lock_stat.st_mode & 0o077):
            raise logs.ArchiveError('Unique private operation owner lock required')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_identity = (lock_stat.st_dev, lock_stat.st_ino)
        owned, hook, bridge = nightly_modules(config['nightly'])
        normal = json.loads(pinned(config['nightly']['selected_config']))
        legacy_manifest = json.loads(pinned(config['nightly']['legacy_manifest']))
        def save(number, value):
            path = receipts / ('graph-checkpoint-' + str(number) + '.json')
            raw = canonical(value) + b'\n'
            if path.exists():
                if path.read_bytes() != raw:
                    raise logs.ArchiveError('Existing recovery epoch differs; preserve and reconcile it')
            else:
                atomic_bytes(path, raw)
        with bridge.pinned_modules(legacy_manifest) as legacy:
            with owned.open_recovery(config['nightly']['selected_config']['path'], plan, legacy=legacy,
                                     legacy_sha256=config['nightly']['legacy_factory_sha256']) as recovery:
                def guard():
                    current_lock = (receipts / 'owner.lock').lstat()
                    if (current_lock.st_dev, current_lock.st_ino) != lock_identity:
                        raise logs.ArchiveError('Online operation owner lock changed')
                    readers.check()
                    recovery.check()
                guard()
                packed = config.get('archive_transport') == 'packed-control-graph-v1'
                if config.get('archive_transport') not in (None, 'packed-control-graph-v1'):
                    raise logs.ArchiveError('Unknown archive transport')
                if packed:
                    import packed_graph
                graph_module = packed_graph if packed else nightly_graph
                graph_kwargs = dict(scratch=receipts, record=record) if packed else {}
                retained = sorted(receipts.glob('graph-checkpoint-*.json'),
                                  key=lambda p: int(p.stem.rsplit('-', 1)[1]))
                if retained:
                    accepted = []
                    for number, path in enumerate(retained):
                        if path.name != 'graph-checkpoint-' + str(number) + '.json':
                            raise logs.ArchiveError('Incomplete retained graph receipt sequence')
                        st = logs.regular(path)
                        if st.st_uid != os.getuid() or st.st_nlink != 1 or st.st_mode & 0o077:
                            raise logs.ArchiveError('Private retained graph receipt required')
                        accepted.append(json.loads(path.read_bytes()))
                    if packed and config.get('archive_resume_attempt'):
                        graph_context = graph_module.checkpoint_graph(recovery, inventory, hook=hook, normal=normal,
                            operation=operation, plan_sha256=config['plan_sha256'],
                            seed=config['nightly']['control_seed'], save=save, retained=accepted,
                            attempt=config['archive_resume_attempt'], **graph_kwargs)
                    else:
                        graph_context = graph_module.reopen_graph(recovery, inventory, accepted,
                                                                   hook=hook, normal=normal, **graph_kwargs)
                else:
                    graph_context = graph_module.checkpoint_graph(recovery, inventory, hook=hook, normal=normal,
                        operation=operation, plan_sha256=config['plan_sha256'],
                        seed=config['nightly']['control_seed'], save=save, **graph_kwargs)
                with graph_context as archive_recovery:
                    fence = ClosedLogFence(root=plan['source_root'], database=config['database'],
                                           workspace_id=config['workspace_id'], plan=plan, roster=roster)
                    with fence.held():
                        guard()
                        yield dict(writer_fence=fence, recovery=recovery, archive_recovery=archive_recovery,
                                   reader_guard=guard, reserve_bytes=config['reserve_bytes'])
                        guard()
    finally:
        os.close(fd)
