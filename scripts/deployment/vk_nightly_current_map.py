"""Resumable current member map over namespace and version qualifications.

Only control metadata is read/written. Required bodies, SQL images and replay
gaps stay explicit; a draft cannot be published as an accepted recovery set.
The controller authenticates inputs, retains their leases and enforces actual
capacity/health. The qualification reader may be live: each exact-name lookup
finishes before output work, so it does not hold a read transaction across the
qualifier's commits. Later completed qualifications are refreshed by keyset.
"""
from contextlib import contextmanager
import json
import hashlib
import os
from pathlib import Path
import sqlite3
import stat
import zlib

from vk_nightly_qualification import decode_observation, encode_observation
from vk_nightly_checkpoints import digest
from vk_nightly_control_format import key

FORMAT = 'vk-nightly-current-member-map-v1'
READY = ('directory', 'symlink', 'verified-file')
ROW_DICTIONARY = (b'source namespace identity member source_identity source_observed_at qualification '
    b'scoped_qualification_coverage directory kind uid gid mode mtime_ns xattrs bytes sha256 segments '
    b'layer selector encoding encoded_bytes encoded_sha256 raw_journal_ready whole_scope_accepted '
    b'required_reconciliation_roots backup_payload_bytes_copied carrier_epoch_preserved journal '
    b'instance plan_sha256 scope_sha256 sequence namespace_or_whole_baseline_accepted '
    b'original_epoch_repaired row source_payload_bytes_hashed state qualified-retained-body '
    b'qualified-pending-body /home/mcp/.local/share/vibe-kanban-green-codex-home/ '
    b'/mnt/vk-storage/worktrees/ /home/mcp/.cache/ accepted-base verified-file')


def encode_member(value):
    raw=json.dumps(value,sort_keys=True,separators=(',', ':'),allow_nan=False).encode()
    if len(raw)>1024**2:raise ValueError('bounded member control required')
    encoder=zlib.compressobj(9,zdict=ROW_DICTIONARY)
    return b'VKM1\0'+encoder.compress(raw)+encoder.flush()


def decode_member(raw):
    if not isinstance(raw,bytes) or not raw.startswith(b'VKM1\0'):
        return decode_observation(raw)
    decoder=zlib.decompressobj(zdict=ROW_DICTIONARY)
    value=decoder.decompress(raw[5:],1024**2+1)
    if len(value)>1024**2 or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ValueError('incomplete/excessive member control')
    return json.loads(value)


def SQL_aliases(connection):
    """Retain SQL names that are links as dependencies, never empty coverage."""
    if not connection.execute("select 1 from sqlite_master where name='SQL_sources'").fetchone():return {}
    return {name:decode_member(raw)['member']['target'] for name,raw in connection.execute(
        "select m.name,m.row from members m join SQL_sources s on s.path='/' || m.name where m.state='symlink'")}


def additive_scope_SQL_sources(previous,current,proof,SQL_sources):
    """Validate a B-authenticated overlap before a complete new metadata epoch.

    The caller authenticates the exact proof bytes through the normal B index.
    This never certifies the old directory/hardlink gap: every new-scope member
    still comes from the complete later namespace and its pending suffix.
    """
    if (not isinstance(proof,dict) or proof.get('format')!='vk-nightly-additive-full-inode-overlap-v1'
            or proof.get('baseline_accepted') is not False
            or proof.get('old_hardlink_and_alias_gap_repaired') is not False
            or proof.get('full_gap_metadata_reconciliation_required') is not True):
        raise ValueError('authenticated explicit additive overlap required')
    old=proof.get('old_required_root_bindings');new=proof.get('new_required_root_bindings')
    if (not isinstance(old,dict) or not isinstance(new,dict) or not old
            or old!=previous.get('required_root_bindings') or new!=current.get('required_root_bindings')
            or any(new.get(k)!=v for k,v in old.items())):
        raise ValueError('additive overlap must preserve every old root binding')
    added=proof.get('added_roots')
    if (not isinstance(added,list) or not added or len(added)!=len(set(added))
            or set(added)!=set(new)-set(old)):
        raise ValueError('exact nonempty added roots required')
    for name in added:
        # These are Linux source names even when this classifier runs next to
        # SQLite on Windows B. Native Path() is only for the control indexes.
        if not isinstance(name,str) or not name.startswith('/'):
            raise ValueError('canonical additive source root required')
        key(name[1:])
    reports=[proof.get('old_namespace'),proof.get('new_before'),proof.get('new_after')]
    for number,report in enumerate(reports):
        expected=previous if number==0 else current
        if (not isinstance(report,dict) or report.get('ready') is not True or report.get('errors')
                or report.get('terminal') or type(report.get('since')) is not int or report['since']!=0
                or not isinstance(report.get('instance'),str) or not report['instance']
                or type(report.get('sequence')) is not int or report['sequence']<0
                or any(report.get(k)!=expected.get(k) for k in ('plan_sha256','scope_sha256'))
                or report.get('barrier')!=dict(kernel_drain_completed=True,durable_sequence=report.get('sequence'),instance=report.get('instance'))):
            raise ValueError('actual complete overlap barriers required')
        if number and (report.get('coverage_model')!='all-selected-inodes-v1'
                       or report.get('instance')!=current.get('instance')):
            raise ValueError('new complete inode epoch required')
    if not reports[1]['sequence']<=reports[2]['sequence']<=current['start_sequence']:
        raise ValueError('new metadata epoch must follow the verified overlap')
    sources=[]
    for name in added:
        root=new[name]
        if name not in SQL_sources or root.get('literal') is None:continue
        target=root.get('resolved')
        if (root['literal']!=target or target not in added
                or new[target].get('identity',[None,None,None])[2]!=stat.S_IFREG):
            raise ValueError('added SQL alias requires its exact regular target root')
        sources.append(target)
    return sources


class SealedMemberIndex:
    """Typed-reader view of one authenticated complete current-map image.

    No second million-row JSON/SQLite copy is required. The holder authenticates
    exact sealed bytes and holds provider leases. Unresolved states fail closed;
    only explicitly bound consistent-SQL sidecars may be omitted from restore.
    """
    def __init__(self,connection,check,reference):
        self.db=connection;self.check=check;self.references=(reference,)
        connection.execute('pragma query_only=on')
        if connection.execute('select format,complete from metadata').fetchall()!=[(FORMAT,1)]:
            raise ValueError('complete authenticated current member map required')
        if connection.execute("select 1 from sqlite_master where name='namespace_reconciliation'").fetchone():
            if connection.execute('select complete,suffix_complete from namespace_reconciliation').fetchall()!=[(1,1)]:
                raise ValueError('later namespace requires its completed durable journal suffix')
        self.sidecars=reference.get('consistent_SQL_sidecars',{})
        actual={name:decode_member(raw)['required_SQL_source'] for name,raw in connection.execute(
            "select name,row from members where state='SQLite-sidecar'")}
        if set(actual)!=set(self.sidecars):raise ValueError('exact consistent-SQL sidecar disposition required')
        for name,source in actual.items():
            proof=self.sidecars[name]
            if proof.get('source')!=source:raise ValueError('SQL sidecar/main source differs')
            main=self.entry(source[1:])
            if main['sha256']!=proof.get('snapshot_sha256'):raise ValueError('SQL sidecar image binding differs')
        aliases=SQL_aliases(connection);proofs=reference.get('consistent_SQL_aliases',{})
        if set(aliases)!=set(proofs):raise ValueError('explicit consistent-SQL alias dependency required')
        for name,target in aliases.items():
            if not isinstance(target,str) or not target.startswith('/') or proofs[name].get('source')!=target:
                raise ValueError('SQL alias target differs from actual member')
            try:
                main=self._entry(key(target[1:]))
                point=decode_member(connection.execute('select row from members where name=?',(target[1:],)).fetchone()[0]).get('SQL_point')
            except KeyError as error:raise ValueError('SQL alias needs its actual captured target') from error
            if (not point or point.get('source')!=target or main['sha256']!=proofs[name].get('snapshot_sha256')
                    or main['sha256']!=point.get('sha256') or point.get('independent',{}).get('integrity')!='ok'):
                raise ValueError('SQL alias lacks an independently accepted target point')

    def _entry(self,name):
        key(name)
        row=self.db.execute('select state,row from members where name=?',(name,)).fetchone()
        if row is None or row[0]=='SQLite-sidecar' and name in self.sidecars:raise KeyError(name)
        if row[0] not in READY:raise ValueError('unresolved current recovery member: '+name+' ('+row[0]+')')
        return decode_member(row[1])['member']

    def entry(self,name):self.check();return self._entry(name)

    def entries(self,*,after=None):
        self.check()
        if after is not None:key(after)
        for name,state,raw in self.db.execute('select name,state,row from members where name>? order by name',(after or '',)):
            if state=='SQLite-sidecar' and name in self.sidecars:continue
            if state not in READY:raise ValueError('unresolved current recovery member: '+name+' ('+state+')')
            yield name,decode_member(raw)['member']
        self.check()

    def changed_entries(self):yield from self.entries()


def classify(name, observation, qualification, *, SQL_sources):
    key(name)
    source = '/' + name
    kind = observation.get('kind')
    metadata = {k: observation[k] for k in ('mode', 'uid', 'gid', 'mtime_ns', 'xattrs')}
    if kind in ('directory', 'symlink'):
        row = dict(metadata, kind=kind)
        if kind == 'symlink': row['target'] = observation['target']
        return kind, dict(member=row, namespace_identity=observation['identity'])
    if kind != 'file':
        return 'special-needs-disposition', dict(namespace=observation)
    if source in SQL_sources:
        return 'SQLite-needs-image', dict(source=source, namespace=observation)
    database = next((source[:-len(suffix)] for suffix in ('-wal', '-shm', '-journal')
                     if source.endswith(suffix) and source[:-len(suffix)] in SQL_sources), None)
    if database is not None:
        return 'SQLite-sidecar', dict(source=source, required_SQL_source=database, namespace=observation)
    if qualification is None:
        return 'file-needs-qualification', dict(source=source, namespace=observation)
    if qualification.get('source') != source:
        raise ValueError('qualification source/name differs')
    state = qualification.get('state')
    if state == 'current-version-deferred' and 'SQLite requires' in qualification.get('reason', ''):
        return 'SQLite-needs-image', dict(source=source, namespace=observation,
                                         detected_by='qualified-source SQLite header refusal')
    if state not in ('qualified-retained-body', 'qualified-pending-body'):
        return 'current-namespace-replay-required', dict(source=source, qualification=qualification,
                                                       namespace=observation)
    row = qualification['row']
    if (row.get('kind') != 'file' or type(row.get('bytes')) is not int or row['bytes'] < 0
            or len(qualification.get('source_identity', [])) != 9):
        raise ValueError('complete qualified source version required')
    digest(row.get('sha256'))
    identity = qualification['source_identity']
    if (identity[2:5] != [stat.S_IFREG | row['mode'], row['bytes'], row['mtime_ns']]
            or identity[6:8] != [row['uid'], row['gid']]):
        raise ValueError('qualified member/identity metadata differ')
    if state == 'qualified-retained-body':
        segments = row.get('segments')
        if not isinstance(segments, list) or not segments or sum(s['bytes'] for s in segments) != row['bytes']:
            raise ValueError('complete independently accepted carrier recipe required')
        for segment in segments:
            digest(segment['sha256']); key(segment['selector'])
        return 'verified-file', dict(member=row, qualification=qualification)
    if row.get('segments'):
        raise ValueError('pending body cannot claim sealed segments')
    return 'file-needs-capture', dict(member=row, qualification=qualification)


class CurrentMap:
    @classmethod
    @contextmanager
    def held(cls, path, *, binding, create=False, maximum_bytes=768*1024**2):
        import fcntl
        path = Path(path)
        if (path.resolve() != path or not path.is_absolute() or type(maximum_bytes) is not int
                or maximum_bytes < 65536):
            raise ValueError('canonical finite current-map control required')
        encoded = json.dumps(binding, sort_keys=True, separators=(',', ':'), allow_nan=False)
        if len(encoded) > 65536 or not isinstance(binding, dict):
            raise ValueError('bounded externally authenticated input binding required')
        if not create:
            probe=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            try:
                if not stat.S_ISREG(os.fstat(probe).st_mode):raise ValueError('regular current-map control required')
                if os.read(probe,32).startswith(b'VK_NIGHTLY_B_CONTROL_POINTER_V1\n'):
                    raise ValueError('current map relocated: use the authenticated native-B control provider, not local SQLite')
            finally:os.close(probe)
        fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK |
                     (os.O_CREAT | os.O_EXCL if create else 0), 0o600)
        db = None
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1
                    or info.st_size > maximum_bytes):
                raise ValueError('owned single current-map inode required')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            db = sqlite3.connect(path, timeout=0, isolation_level=None)
            db.execute('pragma synchronous=FULL'); db.execute('pragma journal_mode=DELETE')
            db.execute('pragma cache_size=-2048'); db.execute('pragma mmap_size=0')
            page = db.execute('pragma page_size').fetchone()[0]
            if db.execute('pragma max_page_count='+str(maximum_bytes//page)).fetchone()[0] > maximum_bytes//page:
                raise ValueError('existing current-map exceeds control budget')
            if create:
                db.execute('begin immediate')
                db.execute('create table metadata(format text,binding text,last_name text,complete integer)')
                db.execute('insert into metadata values(?,?,?,0)', (FORMAT, encoded, ''))
                db.execute('create table members(name text primary key,state text not null,row blob not null) without rowid')
                db.execute('create index member_states on members(state,name)')
                db.execute('create table SQL_sources(path text primary key) without rowid')
                db.execute('commit')
            if db.execute('select format,binding from metadata').fetchall() != [(FORMAT, encoded)]:
                raise ValueError('current-map input binding differs')
            value = cls(); value.path=path; value.fd=fd; value.db=db
            value.inode=(info.st_dev, info.st_ino)
            value.check(); yield value; value.check()
        finally:
            if db is not None: db.close()
            os.close(fd)

    def check(self):
        info = self.path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or (info.st_dev, info.st_ino) != self.inode or self.path.resolve() != self.path):
            raise ValueError('current-map inode replaced')

    def compile(self, namespace, qualified, *, SQL_sources, checkpoint, maximum_paths,
                special_versions=None, progress=lambda _: None):
        """Resume after committed names; never stat/hash/open a source body.

        Namespace is immutable and held by the caller. qualified(name) performs
        a short live lookup, returning a decoded complete observation or None.
        special_versions supplies separately verified later points (e.g. the
        small Printshop/append recovery), not invented current-source hashes.
        """
        self.check()
        if type(maximum_paths) is not int or maximum_paths < 1:
            raise ValueError('bounded metadata composition required')
        if self.db.execute('select complete from metadata').fetchone()[0]:
            return dict(already_complete=True, processed=0, **self.summary())
        SQL_sources = set(SQL_sources)
        self.db.executemany('insert or ignore into SQL_sources values(?)', ((p,) for p in SQL_sources))
        SQL_sources.update(p for p, in self.db.execute('select path from SQL_sources'))
        last = self.db.execute('select last_name from metadata').fetchone()[0]
        processed = 0
        while True:
            checkpoint(); self.check()
            limit=min(128,max(1,maximum_paths-processed))
            batch = namespace.execute('select name,row from namespace where name>? order by name limit ?', (last,limit)).fetchall()
            if not batch: break
            if processed + len(batch) > maximum_paths:
                return dict(already_complete=False, processed=processed, more_members=True, **self.summary())
            prepared=[]; newSQL=[]
            for name, raw in batch:
                observation=decode_observation(raw)
                version=(special_versions or {}).get(name)
                if version is None and observation.get('kind')=='file': version=qualified(name)
                state, value=classify(name, observation, version, SQL_sources=SQL_sources)
                if state=='SQLite-needs-image': SQL_sources.add('/'+name); newSQL.append('/'+name)
                prepared.append((name,state,encode_member(value)))
            self.db.execute('begin immediate')
            try:
                self.db.executemany('insert into members values(?,?,?)', prepared)
                self.db.executemany('insert or ignore into SQL_sources values(?)', ((p,) for p in newSQL))
                self.db.execute('update metadata set last_name=?', (batch[-1][0],))
                self.check(); checkpoint(); self.db.execute('commit')
            except BaseException:
                if self.db.in_transaction:self.db.execute('rollback')
                raise
            last=batch[-1][0]; processed+=len(batch)
            if processed%4096==0:progress(dict(processed=processed,last_name=last,control_bytes=self.path.stat().st_size))
        self.db.execute('update metadata set complete=1')
        return dict(already_complete=False, processed=processed, more_members=False, **self.summary())

    def reconcile_namespace(self, namespace, qualified, *, checkpoint, maximum_paths,
                            allow_unaccepted_epoch_successor=False,source_scope_extension=None):
        """Adopt one complete later metadata epoch without replaying body hashes.

        Reuse requires the full nine-field identity AND Linux xattrs from the
        earlier successful hash to match the later anchored observation. A new
        inode, same-length rewrite, metadata change or missing proof remains
        unresolved. Absent old names are retained separately pending the live
        journal suffix; neither this pass nor its new epoch repairs old gaps.
        """
        if type(maximum_paths) is not int or maximum_paths<1:raise ValueError('finite namespace reconciliation required')
        record=namespace.execute('select binding,complete from gap_meta where id=1').fetchone()
        if not record or record[1]!=1:raise ValueError('complete later namespace epoch required')
        if namespace.execute('select count(*) from namespace_errors').fetchone()[0]:
            raise ValueError('namespace errors require explicit targeted replay before absence adoption')
        binding=json.loads(record[0]);encoded=json.dumps(binding,sort_keys=True,separators=(',',':'))
        self.check();db=self.db
        db.execute('create table if not exists namespace_reconciliation(id integer primary key,binding text,last_name text,complete integer,suffix_complete integer)')
        db.execute('insert or ignore into namespace_reconciliation values(1,?,?,0,0)',(encoded,''))
        stored,last,complete=db.execute('select binding,last_name,complete from namespace_reconciliation where id=1').fetchone()
        if stored!=encoded:
            if not allow_unaccepted_epoch_successor:
                raise ValueError('later namespace/observer binding changed; preserve existing reconciliation')
            previous=json.loads(stored)
            suffix=db.execute('select suffix_complete from namespace_reconciliation where id=1').fetchone()[0]
            if not complete or suffix:
                raise ValueError('only completed unaccepted namespace may have an explicit successor')
            same_scope=all(previous.get(k)==binding.get(k) for k in
                           ('plan_sha256','scope_sha256','required_root_bindings'))
            additional_SQL=[];extension_raw=None
            if not same_scope:
                additional_SQL=additive_scope_SQL_sources(previous,binding,source_scope_extension,
                    {p for p, in db.execute('select path from SQL_sources')})
                extension_raw=json.dumps(source_scope_extension,sort_keys=True,separators=(',',':'))
            elif source_scope_extension is not None:raise ValueError('unexpected scope extension for same scope')
            # Preserve the whole old gap/absence evidence before resetting the
            # derived draft cursor. Immutable checkpoints and body versions are
            # untouched. A later current epoch never repairs the original gap.
            old_digest=hashlib.sha256(stored.encode()).hexdigest()
            db.execute('create table if not exists namespace_reconciliation_history '
                '(sha256 text primary key,binding text,last_name text,complete integer,suffix_complete integer) without rowid')
            db.execute('create table if not exists namespace_absent_history '
                '(epoch_sha256 text,name text,old_state text,row blob,disposition text,primary key(epoch_sha256,name)) without rowid')
            if extension_raw is not None:
                db.execute('create table if not exists namespace_scope_extensions(sha256 text primary key,row text not null) without rowid')
            db.execute('begin immediate')
            try:
                if extension_raw is not None:
                    db.execute('insert into namespace_scope_extensions values(?,?)',
                               (hashlib.sha256(extension_raw.encode()).hexdigest(),extension_raw))
                    db.executemany('insert or ignore into SQL_sources values(?)',((p,) for p in additional_SQL))
                db.execute('insert into namespace_reconciliation_history values(?,?,?,?,?)',
                           (old_digest,stored,last,complete,suffix))
                db.execute('insert into namespace_absent_history select ?,name,old_state,row,disposition from namespace_absent',(old_digest,))
                db.execute('delete from namespace_absent')
                db.execute('update namespace_absence_cursor set last_name=? where id=1',('',))
                db.execute('update namespace_reconciliation set binding=?,last_name=?,complete=0,suffix_complete=0 where id=1',(encoded,''))
                checkpoint();self.check();db.execute('commit')
            except BaseException:
                if db.in_transaction:db.execute('rollback')
                raise
            last='';complete=0
        if complete:return dict(already_complete=True,processed=0,journal_suffix_required=True,**self.summary())
        db.execute('update metadata set complete=0');sources={p for p, in db.execute('select path from SQL_sources')}
        processed=reused=0
        def matches(version,observation):
            return (version is not None and version.get('state') in ('qualified-retained-body','qualified-pending-body')
                and version.get('source_identity')==observation['identity']
                and all(version['row'].get(k)==observation[k] for k in ('mode','uid','gid','mtime_ns','bytes','xattrs')))
        while processed<maximum_paths:
            checkpoint();self.check()
            batch=namespace.execute('select name,row from namespace where name>? order by name limit ?',
                                    (last,min(128,maximum_paths-processed))).fetchall()
            if not batch:break
            # Alternate per-file reads across two HDD indexes caused repeated
            # seeks. Batch the same exact-name lookups before processing them;
            # no identity/hash/metadata checks or durable boundaries change.
            names=[name for name,_ in batch]
            qualifications=qualified.many(names) if hasattr(qualified,'many') else None
            old_rows={name:raw for name,raw in db.execute('select name,row from members where name in ('+
                         ','.join('?' for _ in names)+')',names)}
            rows=[];newSQL=[]
            for name,raw in batch:
                observation=decode_observation(raw);version=None
                if observation['kind']=='file':
                    candidate=qualifications.get(name) if qualifications is not None else qualified(name)
                    if matches(candidate,observation):version=candidate
                    if version is None:
                        old=old_rows.get(name)
                        previous=decode_member(old).get('qualification') if old else None
                        if matches(previous,observation):version=previous
                    if version is not None:
                        version=dict(version,journal={k:binding[k] for k in ('instance','plan_sha256','scope_sha256')},
                            metadata_handover=dict(original_journal=version.get('journal'),
                                exact_source_identity_and_xattrs_reobserved=True,source_body_bytes_reread=0,
                                original_journal_gap_repaired=False))
                        version['journal']['sequence']=binding['start_sequence'];reused+=1
                state,value=classify(name,observation,version,SQL_sources=sources)
                if state=='SQLite-needs-image':sources.add('/'+name);newSQL.append('/'+name)
                rows.append((name,state,encode_member(value)))
            db.execute('begin immediate')
            try:
                db.executemany('insert into members values(?,?,?) on conflict(name) do update set state=excluded.state,row=excluded.row',rows)
                db.executemany('insert or ignore into SQL_sources values(?)',((p,) for p in newSQL))
                db.execute('update namespace_reconciliation set last_name=? where id=1',(batch[-1][0],))
                checkpoint();self.check();db.execute('commit')
            except BaseException:
                if db.in_transaction:db.execute('rollback')
                raise
            last=batch[-1][0];processed+=len(batch)
        more=namespace.execute('select 1 from namespace where name>? limit 1',(last,)).fetchone() is not None
        if not more:
            # ATTACH is deliberately disabled in native B. Keyset merge the two
            # ordered local cursors instead of trusting current Git resolution
            # or inferring that an old name was included in a later archive.
            db.execute('create table if not exists namespace_absent(name text primary key,old_state text,row blob,disposition text) without rowid')
            db.execute('create table if not exists namespace_absence_cursor(id integer primary key,last_name text)')
            db.execute('insert or ignore into namespace_absence_cursor values(1,?)',('',))
            tail=db.execute('select last_name from namespace_absence_cursor where id=1').fetchone()[0]
            namespace_names=iter(namespace.execute('select name from namespace where name>? order by name',(tail,)))
            present=next(namespace_names,(None,))[0];since_checkpoint=0
            while True:
                checkpoint();batch=db.execute('select name,state,row from members where name>? order by name limit 128',(tail,)).fetchall()
                if not batch:break
                missing=[]
                for name,state,raw in batch:
                    while present is not None and present<name:present=next(namespace_names,(None,))[0]
                    if present!=name:missing.append((name,state,raw,'later-gap-absence-needs-journal-suffix'))
                tail=batch[-1][0];since_checkpoint+=len(batch)
                if missing or since_checkpoint>=8192:
                    self._retain_absent(missing,checkpoint,tail);since_checkpoint=0
            self._retain_absent([],checkpoint,tail)
            db.execute('begin immediate')
            try:
                db.execute('update namespace_reconciliation set complete=1 where id=1')
                db.execute('update metadata set complete=1');checkpoint();db.execute('commit')
            except BaseException:
                if db.in_transaction:db.execute('rollback')
                raise
        return dict(processed=processed,reused_qualified_versions=reused,last_name=last,more_names=more,
                    journal_suffix_required=True,original_epoch_repaired=False,**self.summary())

    def _retain_absent(self,rows,checkpoint,last_name):
        self.db.execute('begin immediate')
        try:
            self.db.executemany('insert or ignore into namespace_absent values(?,?,?,?)',rows)
            self.db.executemany('delete from members where name=?',((r[0],) for r in rows))
            self.db.execute('update namespace_absence_cursor set last_name=? where id=1',(last_name,))
            checkpoint();self.db.execute('commit')
        except BaseException:
            if self.db.in_transaction:self.db.execute('rollback')
            raise

    def reencode(self, *, checkpoint, maximum_paths, progress=lambda _:None):
        """Lossless in-place control compaction; retain compile cursor and values.

        This touches only this owner's unaccepted draft. No source/body read,
        VACUUM copy, accepted carrier mutation or replay of qualification work.
        Per-batch digest chain and cursor survive interruption transactionally.
        """
        import hashlib
        if type(maximum_paths) is not int or maximum_paths<1:raise ValueError('finite control rewrite required')
        self.db.execute('create table if not exists row_encoding(id integer primary key,last_name text,chain text,complete integer)')
        self.db.execute('insert or ignore into row_encoding values(1,?,?,0)', ('','0'*64))
        last,chain,complete=self.db.execute('select last_name,chain,complete from row_encoding where id=1').fetchone()
        count=0
        if complete:return dict(already_complete=True,processed=0,logical_digest_chain=chain)
        while count<maximum_paths:
            checkpoint();self.check()
            batch=self.db.execute('select name,row from members where name>? order by name limit ?',
                                  (last,min(128,maximum_paths-count))).fetchall()
            if not batch:
                self.db.execute('update row_encoding set complete=1 where id=1')
                return dict(already_complete=False,processed=count,complete=True,logical_digest_chain=chain)
            prepared=[];newchain=chain
            for name,raw in batch:
                value=decode_member(raw);packed=encode_member(value)
                if decode_member(packed)!=value:raise ValueError('lossless member rewrite failed')
                logical=json.dumps(value,sort_keys=True,separators=(',', ':'),allow_nan=False).encode()
                newchain=hashlib.sha256(bytes.fromhex(newchain)+name.encode()+b'\0'+hashlib.sha256(logical).digest()).hexdigest()
                prepared.append((packed,name))
            self.db.execute('begin immediate')
            try:
                self.db.executemany('update members set row=? where name=?',prepared)
                self.db.execute('update row_encoding set last_name=?,chain=? where id=1',(batch[-1][0],newchain))
                checkpoint();self.check();self.db.execute('commit')
            except BaseException:
                if self.db.in_transaction:self.db.execute('rollback')
                raise
            last=batch[-1][0];chain=newchain;count+=len(batch)
            if count%4096==0:progress(dict(reencoded_paths=count,last_reencoded_name=last))
        return dict(already_complete=False,processed=count,complete=False,logical_digest_chain=chain)

    def summary(self):
        self.check()
        return dict(format=FORMAT, member_states=dict(self.db.execute('select state,count(*) from members group by state')),
                    namespace_composed=bool(self.db.execute('select complete from metadata').fetchone()[0]),
                    source_paths_scanned=0, source_payload_bytes_read=0, backup_payload_bytes_copied=0,
                    current_baseline_accepted=False)

    def pending_files(self,maximum):
        """Bounded keyset batches; accepted rows can safely leave the index."""
        after='';count=0
        while count<maximum:
            self.check()
            rows=self.db.execute("select name,row from members where state='file-needs-capture' and name>? order by name limit ?",
                                 (after,min(128,maximum-count))).fetchall()
            if not rows:return
            for name,raw in rows:
                yield name,raw
                after=name;count+=1

    def source_phase_check(self):self.check()

    def accept_file(self,name,original_sha256,accepted,proof,*,checkpoint):
        """One guarded atomic acceptance, also used next to native B SQLite.

        The source transfer and independent ordered readback precede this call.
        Bind their exact original pending row, full digest, length and metadata;
        a lost acknowledgement can replay only the identical accepted result.
        """
        key(name);digest(original_sha256);self.check();db=self.db
        found=db.execute('select state,row from members where name=?',(name,)).fetchone()
        if found is None:raise ValueError('pending file disappeared from member map')
        encoded=encode_member(accepted)
        if found[0]=='verified-file' and found[1]==encoded:return dict(already_accepted=True)
        if found[0]!='file-needs-capture' or hashlib.sha256(found[1]).hexdigest()!=original_sha256:
            raise ValueError('pending file ownership/version changed')
        original=decode_member(found[1]);member=accepted['member'];point=original['qualification']
        expected=dict(original,member=member,qualification=dict(point,row=member,state='qualified-retained-body'),
                      independent_file_proof=proof)
        if (accepted!=expected or member!=dict(original['member'],segments=member.get('segments'))
                or proof.get('independent_ordered_B_readback_sha256')!=member['sha256']
                or proof.get('independent_ordered_B_readback_bytes')!=member['bytes']
                or proof.get('source_metadata')!={k:member[k] for k in ('mode','uid','gid','mtime_ns','xattrs')}):
            raise ValueError('file acceptance/readback differs from qualified point')
        classify(name,dict(member,identity=point['source_identity']),accepted['qualification'],SQL_sources=set())
        checkpoint();db.execute('begin immediate')
        try:
            db.execute('create table if not exists file_acceptance_history(name text,version_sha256 text,proof blob,accepted_row blob,primary key(name,version_sha256)) without rowid')
            old=db.execute('select proof from file_acceptance where name=?',(name,)).fetchone()
            if old and db.execute('select 1 from file_acceptance_history where name=? and proof=? limit 1',(name,old[0])).fetchone() is None:
                db.execute('insert or ignore into file_acceptance_history values(?,?,?,NULL)',(name,hashlib.sha256(b'legacy-proof\0'+old[0]).hexdigest(),old[0]))
            encoded_proof=encode_member(proof)
            db.execute('insert or ignore into file_acceptance_history values(?,?,?,?)',(name,hashlib.sha256(encoded).hexdigest(),encoded_proof,encoded))
            db.execute('insert into file_acceptance values(?,?) on conflict(name) do update set proof=excluded.proof',(name,encoded_proof))
            updated=db.execute("update members set state='verified-file',row=? where name=? and state='file-needs-capture'",(encoded,name))
            if updated.rowcount!=1:raise ValueError('pending file ownership changed')
            self.check();checkpoint();db.execute('commit')
        except BaseException:
            if db.in_transaction:db.execute('rollback')
            raise
        return dict(already_accepted=False)

    def defer_file(self,name,original_sha256,reason,*,checkpoint):
        """Preserve an unavailable point while other independently valid files finish."""
        key(name);digest(original_sha256);self.check();db=self.db
        found=db.execute('select state,row from members where name=?',(name,)).fetchone()
        if not found or found[0]!='file-needs-capture' or hashlib.sha256(found[1]).hexdigest()!=original_sha256:
            raise ValueError('deferred source ownership/version changed')
        value=decode_member(found[1]);point=value['qualification'];row=value['member']
        value.update(transfer_deferred=dict(reason=reason,qualified_point_sha256=original_sha256,requires_fresh_source_observation=True),
            namespace=dict(kind='file',identity=point['source_identity'],**{k:row[k] for k in ('mode','uid','gid','mtime_ns','bytes','xattrs')}))
        checkpoint();db.execute('begin immediate')
        try:
            db.execute('create table if not exists file_transfer_deferred(name text,point_sha256 text,row blob,reason text,primary key(name,point_sha256)) without rowid')
            db.execute('insert or ignore into file_transfer_deferred values(?,?,?,?)',(name,original_sha256,found[1],reason))
            db.execute("update members set state='current-namespace-replay-required',row=? where name=?",(encode_member(value),name))
            self.check();checkpoint();db.execute('commit')
        except BaseException:
            if db.in_transaction:db.execute('rollback')
            raise

    def accept_SQL_point(self,record,*,checkpoint):
        """The caller authenticates the exact B-sealed independent API proof.

        An API-image size may differ from the live main/WAL files. Retain its
        actual source epoch separately; never adopt a raw WAL/main shortcut.
        """
        source=record['source'];name=key(source.removeprefix('/'));row=record['member'];proof=record['independent']
        if (source!='/'+name or record.get('status')!='consistent_SQL_point_verified'
                or record.get('method')!='SQLite-backup-API'
                or record.get('source_API_point_qualifies_later_epoch_not_original') is not True
                or row.get('kind')!='file' or row.get('bytes')!=record['bytes'] or row.get('sha256')!=record['sha256']
                or proof.get('integrity')!='ok' or proof.get('bytes')!=record['bytes'] or proof.get('sha256')!=record['sha256']
                or not (proof.get('independent_Linux_metadata_verified') is True
                        or proof.get('reused_accepted_independent_SQL_image') is True and proof.get('current_Linux_metadata_verified') is True)
                or not row.get('segments') or sum(x['bytes'] for x in row['segments'])!=row['bytes']
                or any(row.get(k)!=record['source_metadata_before'][k] for k in ('mode','uid','gid','mtime_ns','xattrs'))):
            raise ValueError('complete independently verified consistent SQL point required')
        digest(row['sha256']);point_sha=digest(record['B_acceptance_object']['sha256'])
        self.check()
        if not self.db.execute('select complete from metadata').fetchone()[0]:
            raise ValueError('finish namespace adoption before SQL binding')
        old=self.db.execute('select state,row from members where name=?',(name,)).fetchone()
        if old is None or self.db.execute('select 1 from SQL_sources where path=?',(source,)).fetchone() is None:
            raise ValueError('SQL point must belong to the selected source map')
        encoded=encode_member(dict(member=row,SQL_point=record))
        if old==('verified-file',encoded):return dict(already_accepted=True)
        if old[0]!='SQLite-needs-image' and not decode_member(old[1]).get('SQL_point'):
            raise ValueError('SQL point cannot replace an unrelated file version')
        self.db.execute('create table if not exists SQL_acceptance_history '
                        '(source text,point_sha256 text,record blob,primary key(source,point_sha256)) without rowid')
        self.db.execute('begin immediate')
        try:
            self.db.execute('insert or ignore into SQL_acceptance_history values(?,?,?)',(source,point_sha,encode_member(record)))
            self.db.execute("update members set state='verified-file',row=? where name=?",(encoded,name))
            checkpoint();self.check();self.db.execute('commit')
        except BaseException:
            if self.db.in_transaction:self.db.execute('rollback')
            raise
        return dict(already_accepted=False)

    def refresh_unresolved(self,qualified,*,checkpoint,maximum_paths,SQL_sources=(),after='',progress=lambda _:None):
        """Refresh only unresolved exact names from newer retained observations.

        An explicit keyset permits bounded continuation even when a name still
        has no body qualification. Ready members are never rehashed/replayed.
        The controller verifies the observation's epoch/coverage. Namespace
        moves/absence still require their separate journal closure.
        """
        if type(maximum_paths) is not int or maximum_paths<1:raise ValueError('finite unresolved refresh required')
        self.check()
        if not self.db.execute('select complete from metadata').fetchone()[0]:
            raise ValueError('namespace composition must finish before refresh')
        sources=set(SQL_sources)|{p for p, in self.db.execute('select path from SQL_sources')}
        states=('file-needs-qualification','current-namespace-replay-required','SQLite-sidecar')
        placeholders=','.join('?' for _ in states);last=after;processed=0;resolved=0
        while processed<maximum_paths:
            checkpoint();self.check()
            batch=self.db.execute('select name,state,row from members where state in ('+placeholders+
                ') and name>? order by name limit ?',(*states,last,min(128,maximum_paths-processed))).fetchall()
            if not batch:break
            prepared=[];newSQL=[]
            for name,old_state,raw in batch:
                value=decode_member(raw);observation=value.get('namespace')
                if observation is None:raise ValueError('unresolved namespace observation missing')
                version=qualified(name)
                if version is None or version.get('state') not in ('qualified-retained-body','qualified-pending-body','current-version-deferred'):
                    continue
                state,new=classify(name,observation,version,SQL_sources=sources)
                if state=='SQLite-needs-image':sources.add('/'+name);newSQL.append('/'+name)
                if state!=old_state or new!=value:
                    prepared.append((state,encode_member(new),name));resolved+=int(state in READY or state=='file-needs-capture')
            self.db.execute('begin immediate')
            try:
                self.db.executemany('update members set state=?,row=? where name=?',prepared)
                self.db.executemany('insert or ignore into SQL_sources values(?)',((p,) for p in newSQL))
                checkpoint();self.check();self.db.execute('commit')
            except BaseException:
                if self.db.in_transaction:self.db.execute('rollback')
                raise
            last=batch[-1][0];processed+=len(batch)
            if processed%4096==0:progress(dict(refreshed_names=processed,resolved_versions=resolved,last_refresh_name=last))
        more=self.db.execute('select 1 from members where state in ('+placeholders+') and name>? limit 1',(*states,last)).fetchone() is not None
        return dict(processed=processed,resolved_versions=resolved,last_name=last,more_names=more,**self.summary())
