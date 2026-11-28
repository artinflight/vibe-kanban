"""Fresh per-object checks without subprocess/connection startup overhead.

No cached ownership, SQL, mount or resource observations. Existing execution locks,
source/capture checks and all publication/backup requirements remain in force.
"""
from contextlib import contextmanager, closing
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import threading
import uuid

import log_dedup as logs
from scoped_fence import ClosedLogFence


class FreshUnits:
    lock = threading.RLock()
    FIELDS = {'MainPID': 'Service', 'InvocationID': 'Unit', 'ActiveState': 'Unit',
              'FreezerState': 'Unit', 'ControlGroup': 'Service'}

    def __init__(self, names, bus=None):
        import dbus
        if bus is None:
            socket=Path('/run/user')/str(os.getuid())/'bus'
            info=socket.stat()
            if not stat.S_ISSOCK(info.st_mode) or info.st_uid!=os.getuid():
                raise logs.ArchiveError('Existing owned user bus required')
            bus=dbus.bus.BusConnection('unix:path='+str(socket))
        self.bus = bus
        manager = dbus.Interface(self.bus.get_object('org.freedesktop.systemd1',
            '/org/freedesktop/systemd1', introspect=False), 'org.freedesktop.systemd1.Manager')
        self.objects = {name: dbus.Interface(self.bus.get_object('org.freedesktop.systemd1',
            manager.GetUnit(name, timeout=10), introspect=False), 'org.freedesktop.DBus.Properties')
            for name in names}

    def __call__(self, name):
        # Object handles are reused; all five property values are read anew.
        obj = self.objects[name]
        with self.lock:
            values = {key: obj.Get('org.freedesktop.systemd1.' + interface, key, timeout=10)
                      for key, interface in self.FIELDS.items()}
        return {key: bytes(value).hex() if key == 'InvocationID' else str(value)
                for key, value in values.items()}

    def close(self):
        self.bus.close()


def readonly_mount(pid, inside):
    """Same complete fresh mount inventory, with component-safe string ancestry."""
    decode = lambda value: re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), value)
    target = str(Path(inside))
    ancestors = []
    for row in Path('/proc', str(pid), 'mountinfo').read_text().splitlines():
        fields = row.split()
        point = str(Path(decode(fields[4])))
        options = set(fields[5].split(','))
        if point == target or target.startswith(point.rstrip('/') + '/'):
            ancestors.append((point, options))
        if point != target and point.startswith(target.rstrip('/') + '/') and 'ro' not in options:
            raise logs.ArchiveError('Protected reader has a nested writable log mount')
    if not ancestors or 'ro' not in max(ancestors, key=lambda row: len(row[0]))[1]:
        raise logs.ArchiveError('Protected history reader has a writable log mount')


class FreshClosedLogFence(ClosedLogFence):
    """Reuse one read-only connection; every check runs a fresh autocommit SELECT."""
    connection = None

    @contextmanager
    def query_connection(self):
        if self._identity(self.database) != self.db_identity:
            raise logs.ArchiveError('Scoped database changed')
        if self.connection is not None:
            if self.connection.in_transaction:
                raise logs.ArchiveError('Unexpected retained SQL transaction')
            yield self.connection
        else:
            with closing(sqlite3.connect(self.database.as_uri() + '?mode=ro', uri=True,
                                         timeout=2, isolation_level=None)) as conn:
                conn.execute('PRAGMA query_only=ON')
                yield conn

    def validate_entry(self, entry):
        if self.entries.get(entry['path']) != entry:
            raise logs.ArchiveError('Execution outside held workspace selection')
        match = logs.LOG_PATH.fullmatch(entry['path'])
        if not match or match[1] != match[2][:2]:
            raise logs.ArchiveError('Invalid execution path')
        with self.query_connection() as conn:
            cursor = conn.execute('''SELECT e.session_id, e.status, e.completed_at, s.workspace_id
                FROM execution_processes e JOIN sessions s ON s.id=e.session_id WHERE e.id=?''',
                (uuid.UUID(match[3]).bytes,))
            try:
                row = cursor.fetchone()
            finally:
                cursor.close()  # End the SELECT snapshot before the next observation.
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

    @contextmanager
    def held(self):
        if self.connection is not None:
            raise logs.ArchiveError('Scoped custody already held')
        if self._identity(self.database) != self.db_identity:
            raise logs.ArchiveError('Scoped database changed')
        conn = sqlite3.connect(self.database.as_uri() + '?mode=ro', uri=True,
                               timeout=2, isolation_level=None)
        conn.execute('PRAGMA query_only=ON')
        self.connection = conn
        try:
            with super().held():
                yield self
        finally:
            self.connection = None
            conn.close()


class DirectorySyncGroup:
    """Flush at bounded groups and before any retirement result is published.

    Per-object identity/lease checks are unchanged. A power loss before the next
    flush can leave duplicate staging entries present; primary/backup bytes are
    never involved. No complete retirement receipt precedes its directory flush.
    """
    def __init__(self, sync, limit=64):
        if not 1 <= limit <= 64:
            raise ValueError('Bounded directory sync group required')
        self.sync, self.limit, self.pending, self.count = sync, limit, set(), 0

    def removed(self, parent):
        self.pending.add(parent)
        self.count += 1
        if self.count >= self.limit:
            self.flush()

    def flush(self):
        for parent in sorted(self.pending):
            self.sync(parent)
        self.pending.clear()
        self.count = 0
