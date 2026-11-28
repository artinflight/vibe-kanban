"""Ordinary read-only access to converter members inside sealed B checkpoints.

Checkpoint SQLite and packed tar stay on B. Read only bounded parts, retain the
normal dependency leases, and cache at most two immutable checkpoint handles.
No extraction, payload copy, writer lease acquisition or source fallback.
"""
from collections import OrderedDict
from contextlib import contextmanager,ExitStack
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import stat
import tarfile

MAGIC=b'VKLOGCAS1\n'
MAX_MANIFEST=16*1024**2
MAX_CHUNKS=100000
MAX_CHUNK=256*1024
ENCODING='control-tar-v1'
MAX_BODY=26*1024**2
MAX_CHECKPOINT=64*1024**2
PART=1024**2


def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def validate(s):
    from vk_nightly_control_format import key
    from vk_nightly_checkpoints import digest
    if (s.get('encoding')!=ENCODING or s.get('layer')!='nightly-controls-v1'
            or s['selector']!=digest(s['checkpoint_sha256'])+'.sqlite'
            or type(s['checkpoint_bytes']) is not int or not 0<s['checkpoint_bytes']<=MAX_CHECKPOINT):
        raise ValueError('exact bounded converter checkpoint required')
    digest(s['control_manifest_sha256']);digest(s['sha256']);key(s['member_source'])
    if type(s['bytes']) is not int or not 0<=s['bytes']<=MAX_BODY:
        raise ValueError('bounded converter member required')
    for k in ('carrier_source','manifest_source'):
        if not isinstance(s[k],str) or not s[k].startswith('/') or '..' in Path(s[k]).parts:
            raise ValueError('exact immutable control source key required')
    return s


class Parts(io.RawIOBase):
    def __init__(self,db,point,guard):
        self.db=db;self.point=point;self.guard=guard;self.position=0;self.cache=None;self.part=-1
        self.size=point['member']['bytes']
        if type(self.size) is not int or not 0<=self.size<=MAX_BODY:raise ValueError('bounded packed control required')
        if db.execute('select count(*) from owner_control_parts where source=?',(point['source'],)).fetchone()!=( (self.size+PART-1)//PART,):
            raise ValueError('packed control parts incomplete')
    def tell(self):return self.position
    def seek(self,offset,whence=0):
        position=offset if whence==0 else self.position+offset if whence==1 else self.size+offset if whence==2 else -1
        if not 0<=position<=self.size:raise ValueError('packed stream seek outside body')
        self.position=position;return position
    def readable(self):return True
    def seekable(self):return True
    def read(self,size=-1):
        if size<0:size=self.size-self.position
        size=min(size,self.size-self.position,PART);out=bytearray()
        while len(out)<size:
            self.guard();part,offset=divmod(self.position,PART)
            if part!=self.part:
                row=self.db.execute('select data from owner_control_parts where source=? and part=?',(self.point['source'],part)).fetchone()
                expected=min(PART,self.size-part*PART)
                if row is None or not isinstance(row[0],bytes) or len(row[0])!=expected:raise ValueError('packed control part differs')
                self.cache=row[0];self.part=part
            n=min(size-len(out),len(self.cache)-offset);out.extend(self.cache[offset:offset+n]);self.position+=n
        return bytes(out)


class Pool:
    def __init__(self,provider):self.provider=provider;self.cache=OrderedDict();self.verified=OrderedDict()
    def close(self):
        for entry in self.cache.values():entry['stack'].close()
        self.cache.clear();self.verified.clear()
    def check(self):
        self.provider.check()
        for e in self.cache.values():
            st=os.fstat(e['stream'].fileno())
            if (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)!=e['identity']:
                raise ValueError('held converter checkpoint changed')
    def checkpoint(self,s):
        validate(s);self.check();key=(s['checkpoint_sha256'],s['control_manifest_sha256'],s['carrier_source'],s['manifest_source'])
        if key in self.cache:
            e=self.cache.pop(key);self.cache[key]=e;return e
        while len(self.cache)>=2:self.cache.popitem(last=False)[1]['stack'].close()
        stack=ExitStack()
        try:
            stream=stack.enter_context(self.provider.open('nightly-controls-v1',s['selector']))
            st=os.fstat(stream.fileno());h=hashlib.sha256()
            if not stat.S_ISREG(st.st_mode) or st.st_size!=s['checkpoint_bytes']:raise ValueError('checkpoint length/type differs')
            identity=(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)
            # Same held owner/provider custody, exact immutable file identity.
            # Cache only128 small identities, not file bodies or member tables.
            prior=self.verified.get(s['checkpoint_sha256'])==identity
            if not prior:
                for block in iter(lambda:stream.read(PART),b''):self.provider.check();h.update(block)
                if h.hexdigest()!=s['checkpoint_sha256']:raise ValueError('checkpoint full hash differs')
            # Existing provider pins inode; SQLite opens the same held file on Linux.
            filename='/proc/self/fd/'+str(stream.fileno()) if os.name!='nt' else str(Path(stream.name).resolve())
            db=sqlite3.connect(Path(filename).as_uri()+'?mode=ro&immutable=1',uri=True)
            stack.callback(db.close);db.execute('pragma cache_size=-2048');db.execute('pragma mmap_size=0');db.execute('pragma temp_store=MEMORY')
            rows=db.execute('select sha256,row from owner_control_manifest').fetchall()
            if len(rows)!=1 or rows[0][0]!=s['control_manifest_sha256'] or hashlib.sha256(rows[0][1].encode()).hexdigest()!=rows[0][0]:
                raise ValueError('immutable owner-control manifest differs')
            manifest=json.loads(rows[0][1]);points={p['source']:p for p in manifest['files']}
            if set(points)!={s['carrier_source'],s['manifest_source']}:raise ValueError('packed checkpoint source scope differs')
            bodies={}
            for name,p in points.items():
                if db.execute('select point from owner_control_files where source=?',(name,)).fetchone()!=(canonical(p).decode(),):
                    raise ValueError('packed point differs from owner manifest')
                body=Parts(db,p,self.provider.check);h=hashlib.sha256();raw=bytearray()
                if not prior or name==s['manifest_source']:
                    for block in iter(lambda:body.read(PART),b''):
                        h.update(block)
                        if name==s['manifest_source']:raw.extend(block)
                    if h.hexdigest()!=p['member']['sha256']:raise ValueError('packed control full-body hash differs')
                body.seek(0);bodies[name]=body
                if name==s['manifest_source']:members=json.loads(raw)['files']
            tar=tarfile.open(fileobj=bodies[s['carrier_source']],mode='r:');stack.callback(tar.close)
            infos=tar.getmembers()
            if len(infos)!=len(members) or len({t.name for t in infos})!=len(infos):raise ValueError('packed tar member scope differs')
            index={}
            for i,(r,t) in enumerate(zip(members,infos)):
                if r['member']!=str(i) or t.name!=str(i) or not t.isfile() or t.size!=r['bytes'] or r['path'] in index:
                    raise ValueError('packed tar member identity differs')
                index[r['path']]=(r,t)
            identity=(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)
            e=dict(stack=stack,stream=stream,identity=identity,tar=tar,members=index,reference=dict(s));self.cache[key]=e;self.check()
            self.verified[s['checkpoint_sha256']]=identity;self.verified.move_to_end(s['checkpoint_sha256'])
            while len(self.verified)>128:self.verified.popitem(last=False)
            return e
        except BaseException:stack.close();raise
    @contextmanager
    def member(self,s):
        e=self.checkpoint(s);row,info=e['members'][s['member_source']]
        if any(row[k]!=s[k] for k in ('bytes','sha256')):raise ValueError('packed selected member differs')
        with e['tar'].extractfile(info) as body:
            yield body
        self.check()


class Dependencies:
    """Wrap existing normal dependencies; retain their identities and custody."""
    def __init__(self,base):
        self.base=base;self.identities=base.identities;self.pool=Pool(base);self.admission_check=self.check
    def check(self):self.pool.check()
    def open(self,*a):return self.base.open(*a)
    def packed_member(self,s):return self.pool.member(s)
    def close(self):self.pool.close()


class NativeDependencies:
    def __init__(self,controls,objects,guard):
        self.roots={'nightly-controls-v1':Path(controls),'nightly-objects-v1':Path(objects)};self.guard=guard;self.identities={k:{} for k in self.roots}
    def check(self):self.guard()
    @contextmanager
    def open(self,layer,selector):
        from vk_nightly_control_format import key
        self.check();key(selector)
        if '/' in selector or layer not in self.roots:raise ValueError('fixed native checkpoint/object selector required')
        path=self.roots[layer]/selector
        if path.resolve()!=path or not path.is_file():raise ValueError('native immutable dependency alias/type differs')
        with path.open('rb') as stream:yield stream
        self.check()


def import_checkpoint(database,provider,reference,source_root,*,guard):
    """Native B metadata catalog only; stable readback before atomic adoption."""
    validate(reference)
    if not source_root.startswith('/') or '..' in Path(source_root).parts:raise ValueError('exact source prefix required')
    database.execute('create table if not exists converted_checkpoints(id text primary key,binding text)')
    database.execute('create table if not exists converted_carriers(sha256 text,bytes integer,row text,primary key(sha256,bytes)) without rowid')
    binding=dict(reference=reference,source_root=source_root);raw=canonical(binding).decode();identifier=hashlib.sha256(raw.encode()).hexdigest()
    prior=database.execute('select binding from converted_checkpoints where id=?',(identifier,)).fetchone()
    if prior:
        if prior!=(raw,):raise ValueError('converted import binding changed')
        guard();return dict(reused=True,checkpoint=identifier,new_backup_payload_bytes=0)
    pool=Pool(provider)
    try:
        entry=pool.checkpoint(reference);database.execute('begin immediate');count=0
        for relative,(row,info) in entry['members'].items():
            guard();from vk_nightly_control_format import key
            key(relative);segment=dict(reference,member_source=relative,bytes=row['bytes'],sha256=row['sha256'])
            h=hashlib.sha256();total=0
            with pool.member(segment) as stream:
                for block in iter(lambda:stream.read(PART),b''):guard();h.update(block);total+=len(block)
            if h.hexdigest()!=row['sha256'] or total!=row['bytes']:raise ValueError('converted member full readback differs')
            member=dict(row['metadata'],kind='file',bytes=row['bytes'],sha256=row['sha256'],segments=[segment])
            database.execute('insert or ignore into converted_carriers values(?,?,?)',(row['sha256'],row['bytes'],canonical(member).decode()));count+=1
        pool.check();database.execute('insert into converted_checkpoints values(?,?)',(identifier,raw));database.execute('commit')
        return dict(reused=False,checkpoint=identifier,members=count,new_backup_payload_bytes=0)
    except BaseException:
        if database.in_transaction:database.execute('rollback')
        raise
    finally:pool.close()
