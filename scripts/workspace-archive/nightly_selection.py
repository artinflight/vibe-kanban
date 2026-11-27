"""Current SQL plus cold-reference selection for the existing Nightly owner.

The owner keeps its existing schedule, journal, providers and capture pipeline.
This context only qualifies omissions from that pipeline. It holds shared
workspace custody (not global admission or the B lock), snapshots SQL using the
SQLite API, and makes every omission conditional on the same current generation.
The SQL image and returned descriptor must be captured by the normal owner before
its current-set acceptance. No live SQL writes or backup transport live here.
"""
from contextlib import ExitStack, closing
import hashlib
import os
from pathlib import Path
import sqlite3
import uuid

from catalog import Catalog, Conflict
from custody import Custody
from lifecycle import digest
import payloads


class SnapshotCatalog(Catalog):
    def __init__(self, database):
        self.db = sqlite3.connect(Path(database).resolve(strict=True).as_uri() + '?mode=ro',
                                 uri=True, isolation_level=None, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA query_only=ON')
        self.db.execute('BEGIN')


def records(catalog):
    # Strip SQLite's BLOB owner and replace it with a canonical, portable UUID.
    return [dict(workspace_id=str(uuid.UUID(bytes=r['workspace_id'])),
                 request_version=r['request_version'], operation_id=r['operation_id'],
                 manifest_sha256=r['manifest_sha256'], manifest=r['manifest'],
                 recovery_locator=r['recovery_locator']) for r in sorted(catalog.cold_generations(), key=lambda r: r['workspace_id'])]


def within(path, root):
    return path == root or root in path.parents


def absolute(value):
    path = Path(value)
    if not path.is_absolute() or str(path) != str(value) or '..' in path.parts or path == Path('/'):
        raise ValueError('Exact absolute source path required')
    return path


class Selection:
    """One scoped current-set selection; never reusable after its context closes.

    `authority` is the qualified driver's current ownership/dependency authority.
    `provider` is its source-pinned NormalB adapter. Fixture providers are useful
    for tests but do not establish production B acceptance.
    """
    def __init__(self, database, custody_root, provider, authority, *, required_sources):
        self.database = Path(database).resolve(strict=True)
        self.custody_root, self.provider, self.authority = custody_root, provider, authority
        self.required = sorted({str(absolute(p)) for p in required_sources} | {str(self.database)})
        self.stack = None
        self.references = None
        self.roots = {}
        self.sql = None
        self.sql_version = None
        self.locks = []

    def __enter__(self):
        if self.stack is not None or self.references is not None:
            raise Conflict('Selection cannot be entered twice')
        self.stack = ExitStack()
        try:
            with closing(SnapshotCatalog(self.database)) as initial:
                proposed = records(initial)
            for row in sorted(proposed, key=lambda r: r['workspace_id']):
                lock = self.stack.enter_context(Custody(self.custody_root, row['workspace_id'], exclusive=False))
                self.locks.append(lock)
            # Reopen after custody acquisition. A concurrent mover/new message
            # cannot silently substitute a different generation from the plan.
            with closing(SnapshotCatalog(self.database)) as current:
                actual = records(current)
                if actual != proposed:
                    raise Conflict('Cold generations changed during Nightly selection')
                journals = {r['workspace_id']: current.io(r['workspace_id']) for r in actual}
            # Network metadata verification must not pin a live SQL read
            # transaction/WAL across the archived population.
            for row in actual:
                self._qualify(journals[row['workspace_id']], row)
            self.references = proposed
            self.check()
            return self
        except BaseException:
            self.close()
            raise

    def _qualify(self, journal, row):
        manifest = row['manifest']
        if (manifest.get('format') != 'vk-workspace-archive-v1'
                or any(manifest.get(k) != row[k] for k in ('workspace_id', 'request_version', 'operation_id'))
                or digest(manifest) != row['manifest_sha256']):
            raise Conflict('Cold generation binding differs')
        payloads.validate(manifest['payloads'])
        self.authority.validate_plan(row['workspace_id'], manifest['ownership'])
        if manifest['ownership']['roots'] != manifest['payloads']['roots']:
            raise Conflict('Cold payload/dependency ownership differs')
        if (journal is None or journal['journal']['manifest'] != manifest
                or journal['journal']['recovery'] != row['recovery_locator']):
            raise Conflict('Cold physical journal differs from accepted generation')
        expected = [str(Path(p).with_name('.vk-cold-' + row['operation_id'] + '-' + str(i)))
                    for i, p in enumerate(manifest['payloads']['roots'])]
        if journal['journal']['retired_roots'] != expected:
            raise Conflict('Cold retirement ownership differs')
        for raw in manifest['payloads']['roots']:
            path = absolute(raw)
            payloads.parent_safe(path)
            if os.path.lexists(path):
                raise Conflict('Cold source exists locally; qualify its current contents')
            if any(within(path, absolute(p)) or within(absolute(p), path) for p in self.roots):
                raise Conflict('Cold workspaces have overlapping payload ownership')
            if any(within(absolute(p), path) for p in self.required):
                raise Conflict('Required SQL/catalog/shared recovery source cannot be excluded')
            self.roots[raw] = row['workspace_id']
        # Fully restored archive acceptance remains in its immutable generation.
        # Nightly reopens the small normal-B bundle and its immutable selectors;
        # it does not recapture or hash the archived body backlog every night.
        recovered = self.provider.describe(row['recovery_locator'], row['manifest_sha256'])
        if recovered != manifest:
            raise Conflict('Normal B archive metadata differs from current SQL')

    def check(self):
        if self.stack is None or self.references is None:
            raise Conflict('Nightly archive selection is not held')
        for lock in self.locks:
            lock.check()
        with closing(SnapshotCatalog(self.database)) as current:
            if records(current) != self.references:
                raise Conflict('Archive exclusion invalidated; retain prior backup and reselect current work')
        for row in self.references:
            self.authority.check(row['workspace_id'], row['manifest'])
        for path in self.roots:
            payloads.parent_safe(Path(path))
            if os.path.lexists(path):
                raise Conflict('Cold source reappeared; active capture must be reselected')

    def snapshot_sql(self, destination, *, maximum_bytes, reserve_bytes):
        """Capture catalog and app SQL in the SAME SQLite snapshot as exclusions.

        Space admission includes the complete image and the caller's existing
        reserve. The existing Nightly owner then stores this exact image through
        its normal SQL/control route. An unsuccessful/uncertain image is retained.
        """
        self.check()
        if self.sql is not None:
            raise Conflict('This selection already has its SQL image')
        destination = absolute(destination)
        payloads.parent_safe(destination)
        if any(within(destination, absolute(p)) for p in self.roots):
            raise ValueError('SQL recovery image cannot live inside a cold payload root')
        if (type(maximum_bytes) is not int or maximum_bytes <= 0
                or type(reserve_bytes) is not int or reserve_bytes < 0):
            raise ValueError('Measured SQL allocation and existing reserve required')
        fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        os.close(fd)
        with closing(SnapshotCatalog(self.database)) as current:
            if records(current) != self.references:
                raise Conflict('Current SQL generation differs before snapshot')
            pages = current.db.execute('PRAGMA page_count').fetchone()[0]
            page_size = current.db.execute('PRAGMA page_size').fetchone()[0]
            fs = os.statvfs(destination.parent)
            if pages * page_size > maximum_bytes or fs.f_bavail * fs.f_frsize < pages * page_size + reserve_bytes:
                raise OSError('Insufficient admitted SQL staging capacity')
            with closing(sqlite3.connect(destination)) as target:
                def progress(status, remaining, total):
                    self.check()
                    if total * page_size > maximum_bytes:
                        raise OSError('SQL image exceeded admitted bytes')
                current.db.backup(target, pages=256, progress=progress)
                if target.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                    raise ValueError('SQL recovery image failed integrity check')
        with closing(SnapshotCatalog(destination)) as copied:
            if records(copied) != self.references:
                raise Conflict('SQL recovery image and cold references differ')
        self.check()
        before = payloads.signature(destination.lstat())
        with destination.open('rb') as stream:
            os.fsync(stream.fileno())
            sha = hashlib.file_digest(stream, 'sha256').hexdigest()
        if payloads.signature(destination.lstat()) != before:
            raise Conflict('SQL image changed while being sealed')
        self.sql_version = before
        payloads.directory_sync(destination.parent)
        self.sql = dict(source=str(self.database), image=str(destination),
                        bytes=destination.stat().st_size, sha256=sha)
        return dict(self.sql)

    def include(self, source):
        """Filter one observed path; parent directories and shared data survive."""
        self.check()
        return self._include(source)

    def partition(self, sources):
        """Check one bounded observed batch, avoiding a SQL query per member."""
        self.check()
        included, referenced = [], []
        for source in sources:
            (included if self._include(source) else referenced).append(source)
        self.check()
        return included, referenced

    def _include(self, source):
        path = absolute(source)
        # Do not resolve a missing cold member through an unrelated later alias.
        # A spelling alias supplied by the existing observer is only eligible
        # when its resolved path is equally and unambiguously inside this root.
        resolved = path.resolve()
        for raw in self.roots:
            root = Path(raw)
            if within(path, root) or within(resolved, root):
                if os.path.lexists(path):
                    raise Conflict('Observed cold payload reappeared')
                return False
        return True

    def descriptor(self):
        self.check()
        if self.sql is None:
            raise Conflict('Current app SQL and cold catalog snapshot are required')
        if payloads.signature(Path(self.sql['image']).lstat()) != self.sql_version:
            raise Conflict('Selected SQL image changed or disappeared')
        return dict(format='vk-nightly-workspace-selection-v1', current_SQL=dict(self.sql),
                    required_active_sources=self.required, cold_generations=self.references,
                    excluded_roots=dict(sorted(self.roots.items())))

    def close(self):
        if self.stack is not None:
            self.stack.close()
            self.stack = None

    def __exit__(self, *args):
        self.close()


def verify_recovery(descriptor, expected_sha256, restored_sql, provider, *, required_sources, included_sources):
    """Normal consumer closure for the SQL image and referenced cold generations.

    Inputs `required_sources` and `included_sources` come from the qualified
    Nightly contract and the independently restored active-set manifest. The
    backup cannot decide its own minimum scope. Source paths in the descriptor
    are metadata only; this reader opens only the caller's restored SQL image.
    """
    if (descriptor.get('format') != 'vk-nightly-workspace-selection-v1'
            or digest(descriptor) != expected_sha256):
        raise ValueError('Exact Nightly workspace-selection descriptor required')
    required = {str(absolute(p)) for p in required_sources}
    if (not required or set(descriptor['required_active_sources']) != required
            or not required <= {str(absolute(p)) for p in included_sources}):
        raise ValueError('Current SQL/catalog/shared dependencies are missing from active recovery')
    point = descriptor['current_SQL']
    if point['source'] not in required:
        raise ValueError('Current application SQL is absent from the external recovery contract')
    restored_sql = absolute(restored_sql)
    payloads.parent_safe(restored_sql)
    st = restored_sql.lstat()
    if restored_sql.is_symlink() or not restored_sql.is_file() or st.st_size != point['bytes']:
        raise ValueError('Independently restored current SQL image required')
    before = payloads.signature(st)
    with restored_sql.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != point['sha256']:
            raise ValueError('Restored SQL bytes differ from archive selection')
    with closing(SnapshotCatalog(restored_sql)) as copied:
        actual = records(copied)
        if actual != descriptor['cold_generations']:
            raise Conflict('Restored SQL/catalog and cold dependency references differ')
    roots = {}
    for row in actual:
        manifest = row['manifest']
        if (manifest.get('format') != 'vk-workspace-archive-v1'
                or digest(manifest) != row['manifest_sha256']
                or any(manifest.get(k) != row[k] for k in ('workspace_id', 'request_version', 'operation_id'))):
            raise Conflict('Restored cold manifest identity differs')
        payloads.validate(manifest['payloads'])
        if manifest['ownership']['roots'] != manifest['payloads']['roots']:
            raise Conflict('Restored workspace dependency ownership differs')
        for raw in manifest['payloads']['roots']:
            path = absolute(raw)
            if any(within(path, absolute(p)) or within(absolute(p), path) for p in roots):
                raise Conflict('Restored cold ownership overlaps')
            if any(within(absolute(p), path) for p in required):
                raise Conflict('Required recovery source was excluded')
            roots[raw] = row['workspace_id']
        if provider.describe(row['recovery_locator'], row['manifest_sha256']) != manifest:
            raise Conflict('Normal B cold references differ from restored catalog')
    if roots != descriptor['excluded_roots']:
        raise Conflict('Nightly omissions differ from complete restored cold ownership')
    if payloads.signature(restored_sql.lstat()) != before:
        raise Conflict('Restored SQL changed during independent verification')
    return dict(format='vk-nightly-workspace-recovery-verified-v1',
                selection_sha256=expected_sha256, SQL_sha256=point['sha256'],
                cold_generations=len(actual), cold_roots=len(roots), body_bytes_recaptured=0)
