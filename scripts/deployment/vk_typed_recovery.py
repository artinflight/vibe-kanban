"""Leased reader for an explicitly mixed-epoch, composed recovery set.

This format is deliberately separate from NightlyStore. It reuses an accepted
restored base and a consolidated overlay; it never asserts original archive
inclusion, a host-atomic snapshot, a writer fence or activation authority.
The trusted controller supplies authenticated, retained layer roots. Cooperative
leases protect those dependencies until the last consumer read. Same-account
callbacks and flock are not a security boundary against an uncooperative owner.
"""
import base64
from contextlib import ExitStack, contextmanager
import fcntl
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sqlite3
import stat
import zlib
import zipfile
from vk_nightly_control_format import key


FORMAT = 'vk-typed-current-recovery-v1'
BLOCK = 65536
MAX_ROW = 1024 * 1024


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def checksum(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def stream_checksum(stream):
    # Keep metadata authentication compatible with the installed Python runtimes;
    # hashlib.file_digest is only a convenience API added in Python 3.11.
    h = hashlib.sha256()
    for block in iter(lambda: stream.read(BLOCK), b''):
        h.update(block)
    return h.hexdigest()


def digest(value):
    if (not isinstance(value, str) or len(value) != 64
            or any(c not in '0123456789abcdef' for c in value)):
        raise ValueError('invalid SHA256')
    return value


def fingerprint(st):
    return st.st_dev, st.st_ino, st.st_size, st.st_mode, st.st_mtime_ns, st.st_ctime_ns


@contextmanager
def contained(root, selector):
    """Open every path component without following links, including root."""
    parts = key(selector).split('/')
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for component in parts[:-1]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        child = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(child, 'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError('recovery content is not a regular file')
            yield stream
    finally:
        os.close(fd)


class LocalDependencies:
    """Concrete provider, usable on the existing native B-backed Linux restore.

    Layer IDs and roots are supplied by the controller, never selected by a
    content consumer. The descriptor pins the provider identity and each layer's
    index/proof identity. Existing owner-created lease files must be retained;
    this reader creates, retires and repairs nothing.
    """
    def __init__(self, roots, identities, *, admission_check, lease_paths=None):
        self.roots = {name: Path(path) for name, path in roots.items()}
        self.identities = identities
        self.admission_check = admission_check
        self.lease_paths = lease_paths or {name: root / 'RECOVERY_READ.lease'
                                           for name, root in self.roots.items()}
        self.active = False
        self.leases = []
        self.root_ids = {}
        self.lease_ids = {}

    @contextmanager
    def held(self):
        if (self.active or set(self.roots) != set(self.identities)
                or set(self.lease_paths) != set(self.roots)):
            raise ValueError('invalid or already-held dependency set')
        try:
            self.admission_check()
            for name, root in sorted(self.roots.items()):
                before = root.lstat()
                if not stat.S_ISDIR(before.st_mode) or root.resolve() != root:
                    raise ValueError('dependency root must be an exact directory')
                self.root_ids[name] = before.st_dev, before.st_ino
                fd = os.open(self.lease_paths[name], os.O_RDONLY | os.O_NOFOLLOW)
                self.leases.append(fd)
                if not stat.S_ISREG(os.fstat(fd).st_mode):
                    raise ValueError('invalid dependency lease')
                fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
                self.lease_ids[name] = os.fstat(fd).st_dev, os.fstat(fd).st_ino
            self.active = True
            self.check()
            yield self
        finally:
            self.active = False
            for fd in self.leases:
                os.close(fd)
            self.leases.clear()

    def check(self):
        if not self.active:
            raise ValueError('recovery dependency lease has ended')
        self.admission_check()
        for name, root in self.roots.items():
            st = root.lstat()
            if (not stat.S_ISDIR(st.st_mode) or (st.st_dev, st.st_ino) != self.root_ids[name]
                    or root.resolve() != root):
                raise ValueError('recovery dependency root replaced')
            st = Path(self.lease_paths[name]).lstat()
            if not stat.S_ISREG(st.st_mode) or (st.st_dev, st.st_ino) != self.lease_ids[name]:
                raise ValueError('recovery dependency lease replaced')

    @contextmanager
    def open(self, layer, selector):
        self.check()
        if layer not in self.roots:
            raise ValueError('undeclared dependency layer')
        with contained(self.roots[layer], selector) as stream:
            before = fingerprint(os.fstat(stream.fileno()))
            yield stream
            if fingerprint(os.fstat(stream.fileno())) != before:
                raise ValueError('dependency changed during read')
        self.check()


class ComposedIndex:
    """Accepted base, consolidated map, and optionally one current journal patch.

    A nested base is another held ComposedIndex, never a live filesystem view.
    The public holder bounds this to three authenticated indexes. Keeping the
    final journal patch small avoids cloning the complete retained map again.
    """
    def __init__(self, base, overlay, check):
        self.base, self.overlay, self.check = base, overlay, check
        for connection in (base, overlay):
            if isinstance(connection, sqlite3.Connection):
                connection.execute('pragma query_only=on')

    def entry(self, name):
        self.check()
        return self._entry(name)

    def _entry(self, name):
        # Internal metadata lookup: the complete validation pass owns its held
        # descriptors and checks identities before/after each bounded batch.
        key(name)
        row = self.overlay.execute('select row from puts where name=?', (name,)).fetchone()
        if row is None:
            if self.overlay.execute('select 1 from removes where name=?', (name,)).fetchone():
                raise KeyError(name)
            if not isinstance(self.base, sqlite3.Connection):
                return self.base._entry(name)
            row = self.base.execute('select row from entries where name=?', (name,)).fetchone()
        if row is None:
            raise KeyError(name)
        if len(row[0]) > MAX_ROW:
            raise ValueError('excessive recovery row')
        return json.loads(row[0])

    def entries(self, *, after=None):
        self.check()
        if after is not None:key(after)
        base = (self.base.entries(after=after) if not isinstance(self.base, sqlite3.Connection)
                else self.base.execute('select name,row from entries where name>? order by name',(after or '',)))
        yield from self._merge(base, after=after)
        self.check()

    def changed_entries(self):
        """Selected replacements from either overlay, including shadow/removal."""
        self.check()
        previous = self.base.changed_entries() if not isinstance(self.base, sqlite3.Connection) else ()
        yield from self._merge(previous)
        self.check()

    def _merge(self, previous, *, after=None):
        base = iter(previous)
        overlay = iter(self.overlay.execute('select name,row from puts where name>? order by name',(after or '',)))
        removed = iter(self.overlay.execute('select name from removes where name>? order by name',(after or '',)))
        a, b, c = next(base, None), next(overlay, None), next(removed, None)
        while a is not None or b is not None:
            if b is not None and (a is None or b[0] <= a[0]):
                chosen = b
                if a is not None and a[0] == b[0]:
                    a = next(base, None)
                b = next(overlay, None)
            else:
                chosen = a
                a = next(base, None)
            while c is not None and c[0] < chosen[0]:
                c = next(removed, None)
            if c is not None and c[0] == chosen[0]:
                # A key cannot be simultaneously replaced and removed.
                if self.overlay.execute('select 1 from puts where name=?', (chosen[0],)).fetchone():
                    raise ValueError('ambiguous replacement/tombstone')
                continue
            if isinstance(chosen[1], str):
                if len(chosen[1]) > MAX_ROW:
                    raise ValueError('excessive recovery row')
                value = json.loads(chosen[1])
            else:
                value = chosen[1]  # Already bounded/decoded by the held lower index.
            yield chosen[0], value
        self.check()


@contextmanager
def held_index(provider, *references):
    """Authenticate exact index bytes and retain their descriptors until close.

    On Linux /proc/self/fd pins the opened inode across pathname replacement.
    All connections and underlying descriptors remain held for all reads.
    Two indexes are the ordinary base/map pair. An optional third is a bounded,
    consolidated current journal patch, not an unbounded history chain.
    """
    current_map=(bool(references) and references[0].get('format')=='vk-nightly-current-member-map-v1')
    if current_map and len(references) not in (1,2):
        raise ValueError('complete current map allows at most one bounded journal patch')
    if not current_map and len(references) not in (2, 3):
        raise ValueError('recovery requires base/map and at most one current journal patch')
    with ExitStack() as stack:
        streams = []
        connections = []
        for reference in references:
            stream = stack.enter_context(provider.open(reference['layer'], reference['selector']))
            st = os.fstat(stream.fileno())
            if (st.st_size != reference['bytes']
                    or stream_checksum(stream) != digest(reference['sha256'])):
                raise ValueError('authenticated index bytes differ')
            streams.append((stream, fingerprint(st)))
            connection = sqlite3.connect('file:/proc/self/fd/' + str(stream.fileno()) + '?mode=ro&immutable=1', uri=True)
            stack.callback(connection.close)
            connection.execute('pragma cache_size=-4096')
            connections.append(connection)

        def check():
            provider.check()
            if any(fingerprint(os.fstat(f.fileno())) != before for f, before in streams):
                raise ValueError('authenticated index changed during lease')

        if current_map:
            from vk_nightly_current_map import SealedMemberIndex
            index=SealedMemberIndex(connections[0],check,references[0])
            for overlay in connections[1:]:
                index=ComposedIndex(index,overlay,check)
        else:
            index = connections[0]
            for overlay in connections[1:]:
                index = ComposedIndex(index, overlay, check)
        index.references = tuple(references)
        check()
        yield index
        check()


def read_metadata(provider, reference, *, maximum=32 * 1024**2):
    """Read only a declared, hash-pinned and explicitly bounded metadata object."""
    size = reference['bytes']
    if type(size) is not int or not 0 <= size <= maximum:
        raise ValueError('metadata object exceeds bound')
    with provider.open(reference['layer'], reference['selector']) as stream:
        raw = stream.read(size + 1)
    if len(raw) != size or hashlib.sha256(raw).hexdigest() != digest(reference['sha256']):
        raise ValueError('metadata object identity differs')
    return raw


def validate_member(name, row, lookup):
    key(name)
    if row.get('kind') not in ('file', 'directory', 'symlink', 'hardlink'):
        raise ValueError('unsupported recovery kind')
    for field in ('uid', 'gid', 'mode', 'mtime_ns'):
        if type(row.get(field)) is not int or row[field] < 0:
            raise ValueError('invalid numeric metadata')
    if row['mode'] > 0o7777 or not isinstance(row.get('xattrs'), dict):
        raise ValueError('invalid recovery mode/xattrs')
    for field, value in row['xattrs'].items():
        if not isinstance(field, str) or '\0' in field:
            raise ValueError('invalid xattr name')
        base64.b64decode(value, validate=True)
    for parent in PurePosixPath(name).parents:
        if str(parent) == '.':
            break
        try:
            ancestor = lookup(str(parent))
        except KeyError:
            continue  # Sparse selected roots do not own unselected parents.
        if ancestor.get('kind') != 'directory':
            raise ValueError('recovery member traverses link or file')
    if row['kind'] in ('file', 'hardlink'):
        digest(row.get('sha256'))
        if type(row.get('bytes')) is not int or row['bytes'] < 0:
            raise ValueError('invalid content length')
    if row['kind'] == 'symlink':
        if not isinstance(row.get('target'), str) or not row['target'] or '\0' in row['target']:
            raise ValueError('invalid preserved link literal')
    if row['kind'] == 'hardlink':
        target = lookup(key(row['target']))
        if target.get('kind') != 'file' or any(target.get(f) != row[f] for f in
                ('bytes', 'sha256', 'mode', 'uid', 'gid', 'mtime_ns', 'xattrs')):
            raise ValueError('hardlink metadata/content differs')


class HeldRecoverySet:
    def __init__(self, descriptor, expected_sha256, provider, index):
        if checksum(descriptor) != digest(expected_sha256):
            raise ValueError('typed recovery descriptor digest differs')
        self.descriptor = json.loads(canonical(descriptor))
        self.provider, self.index = provider, index
        self.expected_sha256 = expected_sha256
        self.verified = False
        self.enrollment_resolution = None

    def check(self):
        self.provider.check()
        self.index.check()
        if checksum(self.descriptor) != self.expected_sha256:
            raise ValueError('held recovery descriptor changed')

    def validate(self, *, plan_sha256, scope_sha256, required_sources,
                 original_sources, required_pins, required_SQL,
                 journal_scope_sha256=None, immutable_sources=None, enrollment_resolution=None,
                 required_root_aliases=None):
        """Validate the complete namespace and exact caller-selected contract.

        Required sets come from the consumer's authenticated package, not from
        the descriptor's own assertions. A passing receipt alone is insufficient.
        Whole body reads of new components are a separate required proof.
        """
        self.verified = False
        self.check(); d = self.descriptor
        immutable_sources = immutable_sources or {}
        # Declared source-root links and their explicitly resolved targets are
        # both capture scope (matching the producer's original scan contract).
        # The consumer supplies this binding from its authenticated package;
        # descriptor-only additions cannot authorize arbitrary outside roots.
        aliases = required_root_aliases or {}
        if (not isinstance(aliases, dict) or d.get('root_aliases', {}) != aliases
                or not set(aliases) <= set(required_sources)):
            raise ValueError('explicit source-root alias contract differs')
        target_roots = set()
        for alias, binding in aliases.items():
            if (not isinstance(binding, dict) or set(binding) != {'literal', 'resolved'}
                    or not isinstance(binding['resolved'], str) or not binding['resolved'].startswith('/')
                    or binding['literal'] != binding['resolved']):
                raise ValueError('direct absolute source-root alias binding required')
            target = '/' + key(binding['resolved'][1:])
            if target == alias or target.startswith(alias.rstrip('/') + '/'):
                raise ValueError('source-root alias cycle')
            link = self.index.entry(key(alias[1:]))
            target_row = self.index.entry(key(target[1:]))
            if (link.get('kind') != 'symlink' or link.get('target') != binding['literal']
                    or target_row.get('kind') not in ('directory', 'file', 'hardlink')):
                raise ValueError('source-root alias link/target coverage differs')
            target_roots.add(target)
        effective_sources = set(required_sources) | target_roots
        journal_scope_sha256 = journal_scope_sha256 or scope_sha256
        if (d.get('format') != FORMAT or d.get('source_prefix') != '/'
                or d.get('writer_fence_verified') is not False
                or d.get('original_epoch_complete') is not False
                or d.get('plan_sha256') != plan_sha256 or d.get('scope_sha256') != scope_sha256
                or set(d.get('sources', [])) != set(required_sources)
                or not set(original_sources) <= set(required_sources)
                or set(d.get('original_source_dispositions', {})) != set(original_sources)
                or d.get('dependencies') != self.provider.identities
                or d.get('indexes') != list(self.index.references)
                or d.get('immutable_sources', {}) != immutable_sources
                or not set(immutable_sources) <= set(required_sources)):
            raise ValueError('typed recovery scope/epoch/dependencies differ')
        if immutable_sources:
            if set(d.get('journal_sources', [])) != set(required_sources) - set(immutable_sources):
                raise ValueError('mutable/immutable source coverage differs')
            for proof in immutable_sources.values():
                digest(proof['independent_proof_sha256']); digest(proof['member_map_sha256'])
                if type(proof.get('member_count')) is not int or proof['member_count'] <= 0:
                    raise ValueError('invalid immutable source closure')
        elif journal_scope_sha256 != scope_sha256:
            raise ValueError('different journal scope lacks explicit immutable closure')
        journal = d.get('journal', {})
        if (not journal.get('instance') or journal.get('scope_sha256') != journal_scope_sha256
                or type(journal.get('start')) is not int or journal['start'] < 0
                or type(journal.get('end')) is not int or journal['end'] < journal['start']
                or journal.get('event_closure_verified') is not True):
            raise ValueError('source/journal reconciliation incomplete')
        resolved_paths = []
        if journal.get('errors') != []:
            from vk_vanished_enrollment import VanishedEnrollmentCoverage
            if not isinstance(enrollment_resolution, VanishedEnrollmentCoverage):
                raise ValueError('raw journal errors require authenticated typed enrollment coverage')
            resolved_paths = enrollment_resolution.validate_anchor(journal,
                plan_sha256=plan_sha256, required_sources=required_sources)
        elif enrollment_resolution is not None:
            raise ValueError('unexpected enrollment certificate for error-free journal')
        h = hashlib.sha256(); count = 0; source_members = set(); target_members = set()
        frozen = {root: [hashlib.sha256(), 0] for root in immutable_sources}
        lookup = lru_cache(maxsize=8192)(self.index._entry)
        for name, row in self.index.entries():
            validate_member(name, row, lookup)
            if row['kind'] == 'file':
                if 'pending_content_request' in row or 'prefix_segments' in row:
                    raise ValueError('current content request has not been independently sealed')
                segments = row.get('segments', [{'layer': 'accepted-base', 'selector': name,
                                                'sha256': row['sha256'], 'bytes': row['bytes']}])
                if not isinstance(segments, list) or not segments:
                    raise ValueError('missing content recipe')
                total = 0
                for segment in segments:
                    key(segment['selector']); digest(segment['sha256'])
                    if (segment['layer'] not in self.provider.identities
                            or type(segment.get('bytes')) is not int or segment['bytes'] < 0
                            or segment.get('encoding', 'raw') not in ('raw', 'zlib', 'zip-member')):
                        raise ValueError('undeclared/invalid content dependency')
                    if segment.get('encoding') in ('zlib', 'zip-member'):
                        digest(segment.get('encoded_sha256'))
                        if type(segment.get('encoded_bytes')) is not int or segment['encoded_bytes'] <= 0:
                            raise ValueError('missing bounded encoded component identity')
                        if segment['encoding'] == 'zip-member':
                            key(segment['member'])
                    total += segment['bytes']
                if total != row['bytes']:
                    raise ValueError('content recipe coverage differs')
            absolute = '/' + name
            if any(absolute == path or absolute.startswith(path.rstrip('/') + '/') for path in resolved_paths):
                raise ValueError('vanished enrollment subtree remains in selected map')
            if not any(absolute == root or absolute.startswith(root.rstrip('/') + '/') for root in effective_sources):
                raise ValueError('member outside declared source scope')
            if absolute in required_sources:
                source_members.add(absolute)
            if absolute in target_roots:
                target_members.add(absolute)
            encoded = canonical({'name': name, 'entry': row}) + b'\n'
            h.update(encoded); count += 1
            for root, accumulator in frozen.items():
                alias_target = aliases.get(root, {}).get('resolved')
                if (absolute == root or absolute.startswith(root.rstrip('/') + '/')
                        or alias_target is not None and (absolute == alias_target
                            or absolute.startswith(alias_target.rstrip('/') + '/'))):
                    accumulator[0].update(encoded); accumulator[1] += 1
            if count % 2048 == 0:
                self.check()
        if (count != d.get('member_count') or h.hexdigest() != d.get('member_map_sha256')
                or source_members != set(required_sources) or target_members != target_roots):
            raise ValueError('complete member map/root coverage differs')
        for root, (frozen_digest, frozen_count) in frozen.items():
            proof = immutable_sources[root]
            if frozen_count != proof['member_count'] or frozen_digest.hexdigest() != proof['member_map_sha256']:
                raise ValueError('immutable source member closure differs')
        for path, pin in required_pins.items():
            row = self.index.entry(key(path.removeprefix('/')))
            if row.get('kind') not in ('file', 'hardlink') or any(row.get(f) != pin[f] for f in ('bytes', 'sha256')):
                raise ValueError('required runtime pin differs')
        sql = d.get('SQLite', {})
        if set(sql) != set(required_SQL):
            raise ValueError('consistent SQLite coverage differs')
        for path, component in sql.items():
            row = self.index.entry(key(path.removeprefix('/')))
            if (row.get('kind') != 'file' or not component.get('epoch')
                    or component.get('method') != 'SQLite-backup-API'
                    or component.get('integrity') != 'ok'
                    or any(row.get(f) != component.get(f) for f in ('bytes', 'sha256'))):
                raise ValueError('consistent SQLite component binding differs')
            digest(component.get('independent_proof_sha256'))
        if enrollment_resolution is not None:
            enrollment_resolution.validate_anchor(journal, plan_sha256=plan_sha256, required_sources=required_sources)
        self.enrollment_resolution = enrollment_resolution
        self.check(); self.verified = True
        return {'format': FORMAT, 'descriptor_sha256': self.expected_sha256,
                'member_count': count, 'member_map_sha256': h.hexdigest(),
                'writer_fence_verified': False, 'activation_authorized': False,
                'member_map_validated': True, 'independent_current_restore_accepted': False}

    def _segment(self, segment):
        size = segment['bytes']; digest(segment['sha256'])
        if type(size) is not int or size < 0:
            raise ValueError('invalid segment size')
        encoded = segment.get('encoding', 'raw')
        if encoded not in ('raw', 'zlib', 'zip-member'):
            raise ValueError('unsupported segment encoding')
        if encoded == 'zip-member':
            with self.provider.open(segment['layer'], key(segment['selector'])) as stream:
                if (os.fstat(stream.fileno()).st_size != segment['encoded_bytes']
                        or stream_checksum(stream) != segment['encoded_sha256']):
                    raise ValueError('pinned ZIP identity differs')
                stream.seek(0)
                with zipfile.ZipFile(stream) as archive:
                    member = key(segment['member'])
                    if archive.namelist().count(member) != 1 or archive.getinfo(member).file_size != size:
                        raise ValueError('ambiguous/incorrect ZIP component')
                    h = hashlib.sha256(); n = 0
                    with archive.open(member) as body:
                        while block := body.read(BLOCK):
                            n += len(block)
                            if n > size:
                                raise ValueError('ZIP component exceeds bound')
                            h.update(block); yield block
                    if n != size or h.hexdigest() != segment['sha256']:
                        raise ValueError('ZIP member readback differs')
            return
        decoder = zlib.decompressobj() if encoded == 'zlib' else None
        h = hashlib.sha256(); n = 0; source_h = hashlib.sha256(); source_n = 0
        with self.provider.open(segment['layer'], key(segment['selector'])) as stream:
            while block := stream.read(BLOCK):
                source_h.update(block); source_n += len(block)
                if source_n > segment.get('encoded_bytes', size):
                    raise ValueError('encoded component exceeds bound')
                pending = block
                while pending:
                    value = decoder.decompress(pending, BLOCK) if decoder else pending
                    pending = decoder.unconsumed_tail if decoder else b''
                    n += len(value)
                    if n > size or (decoder and decoder.unused_data):
                        raise ValueError('component overflow/trailing data')
                    h.update(value)
                    if value:
                        yield value
            if (n != size or h.hexdigest() != segment['sha256']
                    or (decoder and (not decoder.eof or decoder.unused_data or decoder.unconsumed_tail))
                    or source_n != segment.get('encoded_bytes', size)
                    or source_h.hexdigest() != segment.get('encoded_sha256', segment['sha256'])):
                raise ValueError('component readback differs')

    def blocks(self, name):
        self.check()
        if not self.verified:
            raise ValueError('complete typed member map has not been validated')
        name = key(name); row = self.index.entry(name)
        if row['kind'] == 'hardlink':
            row = self.index.entry(row['target'])
        if row['kind'] != 'file':
            raise ValueError('recovery member has no regular content')
        segments = row.get('segments')
        if segments is None:
            segments = [{'layer': 'accepted-base', 'selector': name,
                         'sha256': row['sha256'], 'bytes': row['bytes']}]
        if not isinstance(segments, list) or not segments:
            raise ValueError('missing recovery content recipe')
        h = hashlib.sha256(); size = 0
        for segment in segments:
            for block in self._segment(segment):
                size += len(block)
                if size > row['bytes']:
                    raise ValueError('composed member exceeds declared bound')
                h.update(block); yield block
        if size != row['bytes'] or h.hexdigest() != row['sha256']:
            raise ValueError('composed member readback differs')
        self.check()

    def catchup(self, journal_reader):
        self.check()
        if not self.verified:
            raise ValueError('typed set is not validated')
        anchor = self.descriptor['journal']
        if self.enrollment_resolution is not None:
            # Return the unmodified raw unready report plus the separately
            # authenticated resolution identity; never manufacture readytrue.
            resolution = self.enrollment_resolution
            resolution.validate_anchor(anchor, plan_sha256=self.descriptor['plan_sha256'],
                                       required_sources=self.descriptor['sources'])
            watched, drained = resolution.current(plan_sha256=self.descriptor['plan_sha256'],
                                                   required_sources=self.descriptor['sources'])
            self.check()
            return {'format': FORMAT, 'descriptor_sha256': self.expected_sha256,
                    'watched': watched, 'drained': drained,
                    'enrollment_resolution_sha256': resolution.expected_sha256,
                    'writer_fence_verified': False, 'activation_authorized': False,
                    'fresh_final_SQLite_API_required': True}
        watched = journal_reader(anchor['start'])
        if (watched.get('ready') is not True or watched.get('errors')
                or watched.get('instance') != anchor['instance']
                or watched.get('scope_sha256') != anchor['scope_sha256']
                or type(watched.get('sequence')) is not int or watched['sequence'] < anchor['end']):
            raise ValueError('journal continuity lost; preserve set and reconcile')
        self.check()
        return {'format': FORMAT, 'descriptor_sha256': self.expected_sha256,
                'watched': watched, 'writer_fence_verified': False,
                'activation_authorized': False, 'fresh_final_SQLite_API_required': True}


def read_rows(stream, *, expected_sha256, expected_count):
    """Bounded single-zlib JSONL reader for the already sealed reconciliation.

    Exhaust this iterator before accepting an overlay. A truncated stream, an
    unaccepted source observation, duplicate/out-of-order name or extra stream
    fails; this does not rerun source capture or infer missing rows from Git.
    """
    decoder = zlib.decompressobj(); pending_line = b''; h = hashlib.sha256()
    count = 0; previous = None
    while block := stream.read(BLOCK):
        pending = block
        while pending:
            raw = decoder.decompress(pending, BLOCK)
            pending = decoder.unconsumed_tail
            if decoder.unused_data:
                raise ValueError('trailing reconciliation data')
            h.update(raw); pending_line += raw
            while b'\n' in pending_line:
                line, pending_line = pending_line.split(b'\n', 1)
                if len(line) > MAX_ROW:
                    raise ValueError('excessive reconciliation row')
                row = json.loads(line)
                name = key(row['name'])
                if previous is not None and name <= previous:
                    raise ValueError('duplicate/out-of-order reconciliation member')
                if 'unaccepted_source_error' in row:
                    raise ValueError('source reconciliation contains an unaccepted member')
                previous = name; count += 1
                if count > expected_count:
                    raise ValueError('excessive reconciliation rows')
                yield row
            if len(pending_line) > MAX_ROW:
                raise ValueError('excessive reconciliation row')
    if (not decoder.eof or decoder.unused_data or decoder.unconsumed_tail or pending_line
            or count != expected_count or h.hexdigest() != digest(expected_sha256)):
        raise ValueError('sealed reconciliation length/digest differs')


def retained_prefix(stream, *, encoded_sha256, encoded_bytes, complete_sha256,
                    complete_count, partial_sha256, partial_bytes, last_name):
    """Read authenticated complete records from a failed, unterminated stream.

    This authenticates a bounded prefix only. Its excluded partial record never
    becomes a member, and callers still need explicit suffix/journal coverage.
    Exhaust the iterator before accepting derived output; preserve original bytes.
    """
    decoder = zlib.decompressobj(); pending_line = b''
    encoded = hashlib.sha256(); complete = hashlib.sha256()
    size = count = 0; previous = None
    while block := stream.read(BLOCK):
        size += len(block); encoded.update(block)
        if size > encoded_bytes:
            raise ValueError('retained prefix encoded bound differs')
        pending = block
        while pending:
            raw = decoder.decompress(pending, BLOCK)
            pending = decoder.unconsumed_tail
            if decoder.unused_data:
                raise ValueError('retained prefix contains trailing stream')
            pending_line += raw
            lines = pending_line.split(b'\n'); pending_line = lines.pop()
            for line in lines:
                if len(line) > MAX_ROW:
                    raise ValueError('excessive retained row')
                row = json.loads(line); name = key(row['name'])
                if previous is not None and name <= previous:
                    raise ValueError('retained prefix order differs')
                if 'unaccepted_source_error' in row:
                    raise ValueError('retained prefix has source failure')
                previous = name; count += 1; complete.update(line + b'\n')
                if count > complete_count:
                    raise ValueError('retained prefix record count differs')
                yield row
            if len(pending_line) > MAX_ROW:
                raise ValueError('excessive retained partial row')
    if (decoder.eof or decoder.unused_data or decoder.unconsumed_tail
            or size != encoded_bytes or encoded.hexdigest() != digest(encoded_sha256)
            or count != complete_count or complete.hexdigest() != digest(complete_sha256)
            or previous != last_name or len(pending_line) != partial_bytes
            or hashlib.sha256(pending_line).hexdigest() != digest(partial_sha256)):
        raise ValueError('retained prefix identity differs')


def build_overlay(base, output, observations, *, sql_components, source_body_index,
                  verified_carriers=None, checkpoint=lambda: None):
    """Derive a consolidated map and minimal whole-body/prefix-tail requests.

    Only authenticated accepted base bodies are reused. A prefix recipe requires
    the earlier complete source-body comparison; a name or Git resolution alone
    is insufficient. Requests are not accepted content until their actual encoded
    identity and independent composed readback have been sealed. No source reads,
    B writes, lease creation, retirement or activation occur here.
    """
    output.execute('create table puts(name text primary key,row text) without rowid')
    output.execute('create table removes(name text primary key) without rowid')
    output.execute('create table requests(sha text primary key,row text) without rowid')
    # Only one short target name per inode is needed. Keep derivation scratch in
    # RAM, not a second on-disk copy of every full member/metadata row.
    inodes = sqlite3.connect(':memory:')
    inodes.execute('create table inodes(dev integer,ino integer,name text,primary key(dev,ino)) without rowid')
    old_rows = iter(base.execute('select name,row from entries order by name'))
    prior = next(old_rows, None)
    count = 0; sidecars = 0; reused = 0; requested = 0
    for observation in observations:
        name = key(observation['name'])
        while prior is not None and prior[0] < name:
            output.execute('insert into removes values(?)', (prior[0],))
            prior = next(old_rows, None)
        before = None
        if prior is not None and prior[0] == name:
            before = json.loads(prior[1])
            prior = next(old_rows, None)
        if observation['kind'] == 'SQLite-sidecar-covered-by-supported-backup-API':
            if observation['required_component_source'] not in sql_components:
                raise ValueError('sidecar lacks its consistent image')
            sidecars += 1
            if before is not None:
                output.execute('insert into removes values(?)', (name,))
            continue
        row = {f: observation[f] for f in ('kind', 'mode', 'uid', 'gid', 'mtime_ns', 'xattrs')}
        if row['kind'] == 'symlink':
            row['target'] = observation['target']
        elif row['kind'] == 'file':
            row.update(bytes=observation['bytes'], sha256=observation['sha256'])
            if observation.get('body_source') == 'verified_current_consistent_SQLite_component':
                component = sql_components['/' + name]
                if any(component[f] != row[f] for f in ('bytes', 'sha256')):
                    raise ValueError('SQL image differs from source reconciliation')
                row['segments'] = [component['segment']]
                # Consistent SQL contents and metadata belong to their recorded
                # image epoch, not the later online raw main/WAL observation.
                row.update(component['metadata'])
            else:
                carrier = observation.get('authenticated_accepted_base_body_carrier')
                later = (verified_carriers or {}).get(row['sha256'])
                if carrier is not None:
                    found = base.execute('select row from entries where name=?', (key(carrier),)).fetchone()
                    old = json.loads(found[0]) if found else {}
                    if old.get('kind') != 'file' or any(old.get(f) != row[f] for f in ('bytes', 'sha256')):
                        raise ValueError('accepted body carrier differs')
                    if carrier != name:
                        row['segments'] = [{'layer': 'accepted-base', 'selector': carrier,
                                            'bytes': row['bytes'], 'sha256': row['sha256']}]
                    reused += 1
                elif later is not None:
                    if later['bytes'] != row['bytes'] or later['sha256'] != row['sha256']:
                        raise ValueError('verified later component carrier differs')
                    row['segments'] = [later]
                    reused += 1
                else:
                    start = 0; segments = []
                    if observation.get('old_body_is_exact_current_prefix'):
                        old = base.execute('select row from entries where name=?', (name,)).fetchone()
                        old = json.loads(old[0]) if old else {}
                        if old.get('kind') == 'hardlink':
                            target = key(old['target'])
                            old = json.loads(base.execute('select row from entries where name=?', (target,)).fetchone()[0])
                        else:
                            target = name
                        if (old.get('kind') != 'file' or old.get('sha256') != observation['accepted_base_sha256']
                                or old.get('bytes') != observation['accepted_base_bytes'] or old['bytes'] > row['bytes']):
                            raise ValueError('accepted prefix binding differs')
                        start = old['bytes']
                        segments.append(dict(layer='accepted-base', selector=target,
                                             bytes=start, sha256=old['sha256']))
                    request_id = checksum({'sha256': row['sha256'], 'bytes': row['bytes'], 'start': start})
                    observed_fp = observation.get('recorded_body_fingerprint')
                    if observed_fp is not None:
                        if (not isinstance(observed_fp, list) or len(observed_fp) != 6
                                or any(type(v) is not int for v in observed_fp)
                                or observed_fp[:4] != [row['bytes'], stat.S_IFREG | row['mode'], row['uid'], row['gid']]
                                or observed_fp[4] != row['mtime_ns']):
                            raise ValueError('sealed body fingerprint differs from member')
                        body = (*observed_fp, bytes.fromhex(digest(row['sha256'])))
                    else:
                        body = source_body_index.execute('select bytes,mode,uid,gid,mtime,ctime,sha from bodies where dev=? and ino=?',
                                                         (observation['source_device'], observation['source_inode'])).fetchone()
                    if body is None or body[0] != row['bytes'] or bytes(body[6]).hex() != row['sha256']:
                        raise ValueError('source-body identity changed within reconciliation')
                    request = {'id': request_id, 'source': '/' + name, 'start': start,
                               'bytes': row['bytes'] - start, 'member_sha256': row['sha256'],
                               'member_bytes': row['bytes'], 'recorded_body_fingerprint': list(body[:6]),
                               'source_device': observation['source_device'], 'source_inode': observation['source_inode']}
                    output.execute('insert or ignore into requests values(?,?)', (request_id, canonical(request).decode()))
                    # Deliberately unsealed: a source request is not a blob or a
                    # verified supplement. The producer replaces this field only
                    # after actual transfer and independent readback.
                    row['pending_content_request'] = request_id
                    row['prefix_segments'] = segments
                    requested += 1
                inode = observation['source_device'], observation['source_inode']
                earlier = inodes.execute('select name from inodes where dev=? and ino=?', inode).fetchone()
                if earlier:
                    found = output.execute('select row from puts where name=?', (earlier[0],)).fetchone()
                    if found is None:
                        found = base.execute('select row from entries where name=?', (earlier[0],)).fetchone()
                    target = json.loads(found[0])
                    if all(target.get(f) == row[f] for f in ('bytes', 'sha256', 'mode', 'uid', 'gid', 'mtime_ns', 'xattrs')):
                        row = {f: row[f] for f in ('mode', 'uid', 'gid', 'mtime_ns', 'xattrs', 'bytes', 'sha256')}
                        row.update(kind='hardlink', target=earlier[0])
                else:
                    inodes.execute('insert into inodes values(?,?,?)', (*inode, name))
        if row != before:
            output.execute('insert into puts values(?,?)', (name, canonical(row).decode()))
        count += 1
        if count % 2048 == 0:
            output.commit()
            checkpoint()
    # Main/WAL/SHM source files are explicitly replaced by a consistent API image;
    # their raw sidecar paths must not accidentally fall through from old base.
    while prior is not None:
        output.execute('insert into removes values(?)', (prior[0],))
        prior = next(old_rows, None)
    output.commit()
    inodes.close()
    used = {json.loads(raw).get('pending_content_request')
            for raw, in output.execute('select row from puts')}
    for request_id, in list(output.execute('select sha from requests')):
        if request_id not in used:
            output.execute('delete from requests where sha=?', (request_id,))
    output.commit()
    return {'member_count': count, 'SQL_sidecars_covered_not_raw_members': sidecars,
            'base_body_reused_paths': reused, 'pending_body_request_paths': requested,
            'full_current_set_accepted': False}


def verify_overlay_contents(handle, *, accepted_components):
    """Independently exhaust all new composed bodies, reusing exact prior proofs.

    Run at the independent consumer, not against live source files. The caller
    authenticates accepted_components from already completed independent readback
    receipts (e.g. all137 SQLite images). Those exact bodies need not be reread.
    This returns content evidence, not a writer fence or operational acceptance.
    """
    handle.check()
    if not handle.verified:
        raise ValueError('complete member map not validated')
    count = 0; total = 0; reused = 0
    for name, row in handle.index.changed_entries():
        if row.get('kind') != 'file':
            continue
        prior = accepted_components.get(name)
        if prior is not None:
            digest(prior['independent_proof_sha256'])
            if any(prior.get(f) != row.get(f) for f in ('bytes', 'sha256')):
                raise ValueError('independently verified component differs')
            reused += 1
            continue
        if not row.get('segments'):
            continue  # Same accepted base member; only its recorded metadata changed.
        if all(s['layer'] == 'accepted-base' for s in row['segments']):
            continue  # Same authenticated accepted body selected at a different path.
        for block in handle.blocks(name):
            total += len(block)
        count += 1
    handle.check()
    return {'descriptor_sha256': handle.expected_sha256, 'new_composed_bodies_readback': count,
            'new_composed_body_readback_bytes': total,
            'exact_independent_component_proofs_reused': reused,
            'unchanged_accepted_base_proof_reused': True,
            'original_epoch_complete': False, 'activation_authorized': False}


def bind_components(overlay, measured, independently_restored, *, layer):
    """Resolve pending requests only to exact transferred/restored components.

    The caller authenticates the measured and independent receipts first. Every
    referenced component must match decoded and encoded lengths/digests, and its
    independently restored file readback. This does not seal journal/runtime
    coverage or replace the controller's final database/fence requirements.
    """
    changed = 0
    for name, raw in list(overlay.execute('select name,row from puts order by name')):
        row = json.loads(raw)
        request = row.get('pending_content_request')
        if request is None:
            continue
        source = measured[request]
        component = independently_restored[source['sha256']]
        for field in ('bytes', 'sha256', 'encoded_bytes', 'encoded_sha256'):
            if component.get(field) != source[field]:
                raise ValueError('restored component differs from measured request')
        if (component.get('independent_file_readback_sha256') != source['sha256']
                or component.get('independently_allocated') is not True
                or source['selected_member_sha256'] != row['sha256']):
            raise ValueError('independent component/member binding missing')
        segment = {field: component[field] for field in ('bytes', 'sha256', 'encoded_bytes', 'encoded_sha256')}
        segment.update(encoding='zlib', layer=layer, selector=key(component['file']))
        row['segments'] = row.pop('prefix_segments') + [segment]
        if sum(s['bytes'] for s in row['segments']) != row['bytes']:
            raise ValueError('composed request length differs')
        del row['pending_content_request']
        overlay.execute('update puts set row=? where name=?', (canonical(row).decode(), name))
        changed += 1
    overlay.commit()
    return changed
