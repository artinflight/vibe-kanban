"""Per-execution custody for a qualified lock-aware live writer, without a pause.

Protocol 1 is implemented by utils::log_mutation. The source-pinned owner adapter
must enumerate EVERY writer and independently qualify readers, backup/resource
owners and cleanup policy. A protocol flag alone is not a deployment qualification.
No service actions, SQL writes, capacity changes or input/queue edits occur here.
"""
from contextlib import closing, contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import uuid

import log_dedup as logs


def process_identity(pid):
    path = Path('/proc') / str(pid)
    fields = (path / 'stat').read_text().rsplit(')', 1)[1].split()
    exe = (path / 'exe').stat()
    return (fields[19], logs.version(exe))


class WriterRoster:
    """Bind live process births, binary hashes and actual --build-info capability.

    owner_guard is trusted deployment code checking the complete current serving
    roster and cleanup/reader configuration, not a JSON assertion of readiness.
    """
    def __init__(self, writers, owner_guard):
        if not writers or len(writers) > 8 or not callable(owner_guard):
            raise logs.ArchiveError('Complete bounded live writer roster required')
        self.writers, self.owner_guard, self.identities = writers, owner_guard, {}

    def qualify(self):
        self.owner_guard()
        self.identities = {}
        for row in self.writers:
            pid, expected = row['pid'], row['sha256']
            if type(pid) is not int or pid < 1 or pid in self.identities or not logs.valid_hash(expected):
                raise logs.ArchiveError('Exact unique writer PID and qualified binary hash required')
            before = process_identity(pid)
            executable = Path('/proc') / str(pid) / 'exe'
            with executable.open('rb') as body:
                actual = hashlib.file_digest(body, 'sha256').hexdigest()
            if actual != expected:
                raise logs.ArchiveError('Live writer differs from qualified binary')
            reply = subprocess.run([str(executable), '--build-info'], check=True,
                                   capture_output=True, timeout=15)
            if len(reply.stdout) > 65536 or json.loads(reply.stdout).get('executionLogMutationLockProtocol') != 1:
                raise logs.ArchiveError('Live writer lacks execution-log mutation lock protocol 1')
            if process_identity(pid) != before:
                raise logs.ArchiveError('Writer changed during protocol qualification')
            self.identities[pid] = before
        self.check()

    def check(self):
        self.owner_guard()
        if len(self.identities) != len(self.writers):
            raise logs.ArchiveError('Live writer protocol was not qualified')
        for pid, identity in self.identities.items():
            if process_identity(pid) != identity:
                raise logs.ArchiveError('Qualified writer process or binary changed')


class ClosedLogFence:
    """Try-lock only reviewed closed executions belonging to exactly one workspace.

    Existing and future writers of those same IDs are excluded by permanent lock
    inodes. Writers of other IDs, even in the same session, remain independent.
    Failed acquisition releases only locks acquired here and never waits on work.
    """
    def __init__(self, *, root, database, workspace_id, plan, roster):
        self.root, self.database = Path(root), Path(database)
        if (not self.root.is_absolute() or self.root.resolve(strict=True) != self.root
                or not self.database.is_absolute() or self.database.resolve(strict=True) != self.database
                or not isinstance(roster, WriterRoster)):
            raise logs.ArchiveError('Canonical roots and actual live-writer roster required')
        self.workspace = uuid.UUID(workspace_id)
        if str(self.workspace) != workspace_id or plan['source_root'] != str(self.root):
            raise logs.ArchiveError('Exact workspace and log-root binding required')
        self.entries = {row['path']: row for row in plan['files']}
        if (not 1 <= len(self.entries) <= 64 or len(self.entries) != len(plan['files'])
                or sum(row['raw_bytes'] for row in plan['files']) > 2 * 1024**3):
            raise logs.ArchiveError('Bounded unique per-workspace selection required')
        self.roster, self.locks = roster, {}
        self.db_identity = self._identity(self.database)
        self.root_identity = self._identity(self.root)
        self.binding = {'database': str(self.database), 'log_source_root': str(self.root),
                        'workspace_id': workspace_id, 'mutation_lock_protocol': 1}

    @staticmethod
    def _identity(path):
        st = path.lstat()
        if stat.S_ISLNK(st.st_mode):
            raise logs.ArchiveError('Custody path is an alias')
        return (st.st_dev, st.st_ino)

    def validate_entry(self, entry):
        if self.entries.get(entry['path']) != entry:
            raise logs.ArchiveError('Execution outside held workspace selection')
        match = logs.LOG_PATH.fullmatch(entry['path'])
        if not match or match[1] != match[2][:2]:
            raise logs.ArchiveError('Invalid execution path')
        with closing(sqlite3.connect(self.database.as_uri() + '?mode=ro', uri=True, timeout=2)) as conn:
            conn.execute('PRAGMA query_only=ON')
            row = conn.execute('''SELECT e.session_id, e.status, e.completed_at, s.workspace_id
                FROM execution_processes e JOIN sessions s ON s.id=e.session_id WHERE e.id=?''',
                (uuid.UUID(match[3]).bytes,)).fetchone()
        if (row is None or row[0] != uuid.UUID(match[2]).bytes or row[3] != self.workspace.bytes
                or row[1] not in ('completed', 'failed', 'killed') or row[2] is None):
            raise logs.ArchiveError('Exact terminal execution/workspace binding required')
        source = logs.safe_path(self.root, entry['path'])
        sidecars = logs.sidecars(source)
        actual = [(ext, logs.sha(raw)) for ext, raw, _ in sidecars]
        expected = [(r['extension'], r['sha256']) for r in entry['sidecars']]
        captures = [raw for ext, raw, _ in sidecars if ext == 'capture.json']
        if actual != expected or len(captures) != 1 or json.loads(captures[0]).get('capture_state') != 'closed':
            raise logs.ArchiveError('Exact closed capture and unchanged sidecars required')

    def check(self):
        self.roster.check()
        if self._identity(self.database) != self.db_identity or self._identity(self.root) != self.root_identity:
            raise logs.ArchiveError('Scoped database or log root changed')
        if set(self.locks) != set(self.entries):
            raise logs.ArchiveError('Actual retained execution mutation locks required')
        for relative, (fd, identity) in self.locks.items():
            path = logs.safe_path(self.root, relative).with_suffix('.mutation.lock')
            opened, named = os.fstat(fd), logs.regular(path)
            if ((opened.st_dev, opened.st_ino) != identity or self._identity(path) != identity
                    or named.st_uid != os.getuid() or named.st_nlink != 1 or named.st_mode & 0o022):
                raise logs.ArchiveError('Execution mutation lock inode changed')
            self.validate_entry(self.entries[relative])

    @contextmanager
    def held(self):
        if self.locks:
            raise logs.ArchiveError('Scoped custody already held')
        self.roster.qualify()  # Refuse old production BEFORE creating any lock file.
        try:
            for relative in sorted(self.entries):
                self.validate_entry(self.entries[relative])
                path = logs.safe_path(self.root, relative).with_suffix('.mutation.lock')
                fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, 0o600)
                try:
                    st = os.fstat(fd)
                    if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid()
                            or st.st_nlink != 1 or st.st_mode & 0o022):
                        raise logs.ArchiveError('Unique owned execution lock required')
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self.locks[relative] = (fd, (st.st_dev, st.st_ino))
                except BaseException:
                    os.close(fd)
                    raise
            self.check()
            yield self
            self.check()
        finally:
            for fd, _ in self.locks.values():
                os.close(fd)
            self.locks.clear()
            # Permanent lock names are deliberately retained, including on failure.
