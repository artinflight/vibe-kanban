"""Crash-safe journal control checkpoints; never a source crawler or watcher.

The sole observer supplies complete authenticated reports. This store commits
raw reports and its cursor in one FULL-synchronous transaction. A restarted
collector resumes that cursor; duplicate exact batches do not duplicate work.
An observer epoch change, overflow, persistent enrollment error or open historic
coverage gap requires explicit current-set reconciliation, never an empty delta.
Only control metadata is stored. Production placement/leases/admission and B
readback remain with the controller. This module starts no service or schedule.
"""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat

from vk_nightly_checkpoints import authenticated, parse

FORMAT = 'vk-nightly-durable-journal-v1'
MAX_REPORT = 16 * 1024**2


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def sequence(value):
    if type(value) is not int or value < 0:
        raise ValueError('nonnegative actual journal sequence required')
    return value


def validate_report(raw, *, instance, scope_sha256, since):
    if not isinstance(raw, bytes):
        raise ValueError('complete bounded journal report bytes required')
    if len(raw) > MAX_REPORT:
        raise ValueError('complete bounded journal report exceeded: '+str(len(raw))+
                         ' bytes > '+str(MAX_REPORT)+'; no truncated commit')
    value = parse(raw)
    if (value.get('instance') != instance or value.get('scope_sha256') != scope_sha256
            or sequence(value.get('sequence')) < sequence(since)
            or type(value.get('ready')) is not bool
            or not isinstance(value.get('errors'), list)
            or not isinstance(value.get('changed'), list)
            or not isinstance(value.get('events'), dict)):
        raise ValueError('journal epoch/scope/sequence or collections differ')
    changed = value['changed']
    if (len(changed) != len(set(changed)) or set(changed) != set(value['events'])
            or any(not isinstance(p, str) or not p.startswith('/') or str(Path(p)) != p
                   or '..' in Path(p).parts or '\x00' in p for p in changed)
            or any(type(mask) is not int or not 0 < mask < 2**32 for mask in value['events'].values())):
        raise ValueError('complete canonical changed-path/event set required')
    if value['sequence'] == since and changed:
        raise ValueError('changed events cannot follow an unchanged sequence')
    return value


class JournalStore:
    """Caller holds this context for each append/query; no hidden retry/copy."""
    @classmethod
    @contextmanager
    def held(cls, path, *, binding, start, create=False, maximum_bytes=64*1024**2):
        path = Path(path)
        if not path.is_absolute() or type(maximum_bytes) is not int or maximum_bytes <= 0:
            raise ValueError('absolute control path and finite metadata budget required')
        if (set(binding) != {'instance', 'scope_sha256', 'plan_sha256', 'observer'}
                or not isinstance(binding['instance'], str) or not binding['instance']
                or any(not isinstance(binding[k], str) or len(binding[k]) != 64
                       or any(c not in '0123456789abcdef' for c in binding[k])
                       for k in ('scope_sha256', 'plan_sha256'))
                or not isinstance(binding['observer'], dict)):
            raise ValueError('exact observer and source binding required')
        sequence(start)
        flags = os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
        fd = os.open(path, flags | (os.O_CREAT | os.O_EXCL if create else 0), 0o600)
        connection = None
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or path.resolve() != path:
                raise ValueError('regular canonical unique journal control inode required')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # SQLite's journal sidecar belongs to the canonical path; retain
            # the lease and recheck that path before every transaction.
            connection = sqlite3.connect(path, timeout=0, isolation_level=None)
            connection.execute('pragma synchronous=FULL')
            connection.execute('pragma journal_mode=DELETE')
            connection.execute('pragma mmap_size=0')
            connection.execute('pragma cache_size=-1024')
            page_size = connection.execute('pragma page_size').fetchone()[0]
            if maximum_bytes < 4*page_size or st.st_size > maximum_bytes:
                raise ValueError('journal metadata exceeds admitted control budget')
            if connection.execute('pragma max_page_count='+str(maximum_bytes//page_size)).fetchone()[0] > maximum_bytes//page_size:
                raise ValueError('existing journal exceeds admitted page budget')
            self = cls()
            self.path, self.fd, self.connection = path, fd, connection
            self.inode, self.binding, self.start = (st.st_dev, st.st_ino), binding, start
            if create:
                connection.execute('begin immediate')
                connection.execute('create table metadata(format text not null,binding blob not null,start integer not null,cursor integer not null)')
                connection.execute('create table batches(id integer primary key,since integer not null,end integer not null,sha text not null,previous text,raw blob not null)')
                connection.execute('insert into metadata values(?,?,?,?)', (FORMAT, canonical(binding), start, start))
                connection.execute('commit')
                directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
                try: os.fsync(directory)
                finally: os.close(directory)
            self.check()
            yield self
        finally:
            if connection is not None: connection.close()
            os.close(fd)

    def check(self):
        st = self.path.lstat()
        if (not stat.S_ISREG(st.st_mode) or (st.st_dev, st.st_ino) != self.inode
                or st.st_nlink != 1 or self.path.resolve() != self.path):
            raise ValueError('journal control path substituted')
        rows = self.connection.execute('select format,binding,start,cursor from metadata').fetchall()
        if len(rows) != 1 or rows[0][:3] != (FORMAT, canonical(self.binding), self.start):
            raise ValueError('persisted journal binding differs')
        return sequence(rows[0][3])

    def append(self, *, since, raw, expected_sha256):
        # Hash is supplied by the authenticated complete-wire collector, never
        # inferred from a truncated page or accepted merely from a header.
        value = authenticated(raw, expected_sha256)
        validate_report(raw, instance=self.binding['instance'],
                        scope_sha256=self.binding['scope_sha256'], since=since)
        cursor = self.check()
        last = self.connection.execute('select since,end,sha from batches order by id desc limit 1').fetchone()
        if last == (since, value['sequence'], expected_sha256) and cursor == value['sequence']:
            return {'cursor': cursor, 'already_committed': True}
        if since != cursor:
            raise ValueError('collector cursor differs; preserve and resume actual committed cursor')
        try:
            self.connection.execute('begin immediate')
            self.check()
            self.connection.execute('insert into batches(since,end,sha,previous,raw) values(?,?,?,?,?)',
                                    (since, value['sequence'], expected_sha256, last[2] if last else None, raw))
            self.connection.execute('update metadata set cursor=?', (value['sequence'],))
            self.connection.execute('commit')
        except BaseException:
            if self.connection.in_transaction: self.connection.execute('rollback')
            raise
        self.check()
        return {'cursor': value['sequence'], 'already_committed': False}

    def report(self, since):
        """Union complete batch intervals; an interior cursor overselects safely.

        This authenticates all control batches and never stats/hashes/scans source
        bodies. Persistent faults poison selection even after an apparently clean
        later report. An accepted baseline is independently required by consumer.
        """
        cursor = self.check(); sequence(since)
        if not self.start <= since <= cursor:
            raise ValueError('requested sequence is outside durable coverage')
        previous = None; expected = self.start; changes = {}; errors = []; seen_errors = set(); ready = True
        for begin, end, sha, parent, raw in self.connection.execute(
                'select since,end,sha,previous,raw from batches order by id'):
            if parent != previous or begin != expected or digest(raw) != sha:
                raise ValueError('durable journal batch chain differs')
            value = validate_report(raw, instance=self.binding['instance'],
                                    scope_sha256=self.binding['scope_sha256'], since=begin)
            if value['sequence'] != end:
                raise ValueError('batch terminal sequence differs')
            ready = ready and value['ready'] and not value['errors'] and not value.get('pending_directory_moves')
            if value.get('coverage_gap') and value['coverage_gap'].get('continuity_proven') is not True:
                ready = False
            for error in value['errors']:
                encoded = canonical(error)
                if encoded not in seen_errors:
                    errors.append(error); seen_errors.add(encoded)
            if end > since:
                for name, mask in value['events'].items(): changes[name] = changes.get(name, 0) | mask
            previous, expected = sha, end
        if expected != cursor:
            raise ValueError('durable cursor has no complete batch')
        self.check()
        return {'format': FORMAT, 'instance': self.binding['instance'],
                'scope_sha256': self.binding['scope_sha256'], 'sequence': cursor,
                'durable_since': self.start, 'ready': bool(ready and previous is not None),
                'errors': errors, 'changed': sorted(changes), 'events': changes,
                'history_before_start_proven': False, 'baseline_accepted': False,
                'writer_fence_verified': False}
