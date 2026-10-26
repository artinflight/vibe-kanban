"""Authoritative control SQLite runs on native Desktop B, never over SSHFS.

Only the pinned worker supplies SQL and index names. Recovery descriptors do
not supply commands. Framed bounded requests carry bytes losslessly. Native
SQLite FULL transactions and per-index kernel leases survive a lost client;
uncommitted work rolls back, acknowledged commits reopen without replay.
Immutable import checkpoints preserve the exact original index and Linux
metadata separately from its writable descendant. No original is retired here.
"""
import base64
from contextlib import contextmanager,nullcontext
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import struct
import tempfile

LIMIT=4*1024**2
BLOCK=65536


def packed(value):
    def default(v):
        if isinstance(v,bytes):return {'__nightly_bytes__':base64.b64encode(v).decode()}
        raise TypeError(type(v).__name__)
    raw=json.dumps(value,default=default,separators=(',',':'),allow_nan=False).encode()
    if len(raw)>LIMIT:raise ValueError('bounded B control frame exceeded')
    return raw


def unpacked(raw):
    def hook(v):
        if set(v)=={'__nightly_bytes__'}:return base64.b64decode(v['__nightly_bytes__'],validate=True)
        return v
    return json.loads(raw,object_hook=hook)


def exact(stream,n):
    value=bytearray()
    while len(value)<n:
        part=stream.read(n-len(value))
        if not part:raise EOFError('B control connection ended; retain committed state')
        value.extend(part)
    return bytes(value)


def send(stream,value):
    raw=packed(value);stream.write(struct.pack('!I',len(raw))+raw);stream.flush()


def recv(stream):
    size=struct.unpack('!I',exact(stream,4))[0]
    if not 0<size<=LIMIT:raise ValueError('bounded B control frame required')
    return unpacked(exact(stream,size))


def name(value):
    if not isinstance(value,str) or not re.fullmatch('[a-z0-9][a-z0-9-]{0,95}',value):
        raise ValueError('fixed B control index name required')
    return value


def sha(value):
    if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{64}',value):raise ValueError('exact index SHA required')
    return value


def atomic_new(path,value):
    with Path(path).open('x') as f:
        json.dump(value,f,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())


class Store:
    def __init__(self,root,objects,*,guard,maximum_index_bytes=4*1024**3):
        self.root=Path(root);self.objects=objects;self.guard=guard;self.maximum=maximum_index_bytes
        if self.root.resolve()!=self.root or not self.root.is_dir():raise ValueError('existing canonical B control directory required')
        self.handles={};self.cursors={};self.next_cursor=0;self.readonly_identities={};self.pending_rows={};self.exhausted={}
        self.cache_bytes=128*1024**2;self.guard_reason=None

    def configure(self,db):
        # This is a per-connection ceiling, not a preallocation or global
        # reserve. The measured842MB map thrashed at the former2MB setting.
        if os.name=='nt':
            import ctypes
            class Memory(ctypes.Structure):
                _fields_=[('length',ctypes.c_uint32),('load',ctypes.c_uint32),
                    *[(n,ctypes.c_uint64) for n in ('totalPhys','availPhys','totalPage','availPage','totalVirtual','availVirtual','extended')]]
            m=Memory();m.length=ctypes.sizeof(m)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
                raise OSError('native Desktop memory admission unreadable')
            planned=(len(self.handles)+1)*self.cache_bytes+256*1024**2
            if m.availPhys<planned:raise ValueError('native control-cache and frame headroom unavailable')
        db.execute('pragma temp_store=MEMORY');db.execute('pragma cache_size=-'+str(self.cache_bytes//1024));db.execute('pragma mmap_size=0')
        def progress():
            try:self.guard(0);return 0
            except BaseException as error:self.guard_reason=type(error).__name__+': '+str(error);return 1
        db.set_progress_handler(progress,10000)

    def checkpoint(self,digest):return self.root/(sha(digest)+'.sqlite')

    def checked(self,path):
        self.objects.regular(path)
        if path.resolve()!=path:raise ValueError('B index alias/reparse substitution')

    def directory(self,path):
        path.mkdir(exist_ok=True)
        if path.resolve()!=path or not path.is_dir() or getattr(path.lstat(),'st_file_attributes',0)&0x400:
            raise ValueError('control lease directory crosses alias/reparse')

    def hash(self,path):
        self.checked(path);before=self.objects.file_identity(path);h=hashlib.sha256()
        with path.open('rb') as f:
            for block in iter(lambda:f.read(BLOCK),b''):self.guard(0);h.update(block)
        if self.objects.file_identity(path)!=before:raise ValueError('B index changed during independent hash')
        return h.hexdigest()

    def import_index(self,q):
        digest=sha(q['sha256']);size=q['bytes'];path=self.checkpoint(digest)
        if type(size) is not int or not 0<size<=self.maximum:raise ValueError('finite imported index size required')
        proof=path.with_suffix('.import.json')
        if proof.exists():
            self.checked(proof);r=json.loads(proof.read_text())
            if (r['bytes']!=size or r['Linux_metadata']!=q['Linux_metadata']
                    or r['identity']!=self.objects.file_identity(path)):
                raise ValueError('accepted B index checkpoint changed')
            return dict(status='already_verified',receipt=r)
        self.guard(size+1024**2)
        if not path.exists():
            temp=path.with_name(path.name+'.'+os.urandom(8).hex()+'.partial')
            h=hashlib.sha256();total=0
            with temp.open('xb') as f:
                for segment in q['segments']:
                    obj,_,accepted=self.objects.object_paths(self.root.parent/'objects-v1',segment['sha256'])
                    self.checked(accepted);receipt=json.loads(accepted.read_text())
                    if (receipt['raw_sha256']!=segment['sha256'] or receipt['raw_bytes']!=segment['bytes']
                            or receipt['identity']!=self.objects.file_identity(obj)
                            or receipt.get('independent_RAM_reopened_hash_verified') is not True):
                        raise ValueError('accepted control chunk differs')
                    for block in self.objects.decoded(obj,expected_size=segment['bytes'],expected_sha=segment['sha256'],
                            encoded_sha=segment['encoded_sha256'],guard=lambda:self.guard(size-total)):
                        total+=len(block)
                        if total>size:raise ValueError('index import exceeds original bytes')
                        h.update(block);f.write(block)
                f.flush();os.fsync(f.fileno())
            if total!=size or h.hexdigest()!=digest:raise ValueError('imported index source hash differs; partial retained')
            if path.exists():raise ValueError('index checkpoint collision')
            os.rename(temp,path)
        if path.stat().st_size!=size or self.hash(path)!=digest:raise ValueError('native full checkpoint hash differs')
        db=sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True)
        try:
            self.configure(db)
            if db.execute('pragma integrity_check').fetchall()!=[('ok',)]:raise ValueError('native imported index integrity failed')
        finally:db.close()
        return dict(status='needs_independent_readback',bytes=size,sha256=digest)

    def acknowledge(self,q):
        path=self.checkpoint(q['sha256']);proof=path.with_suffix('.import.json')
        if q.get('independent_stream_sha256')!=q['sha256'] or self.hash(path)!=q['sha256']:
            raise ValueError('independent control checkpoint readback missing')
        db=sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True)
        try:
            self.configure(db)
            if db.execute('pragma integrity_check').fetchall()!=[('ok',)]:raise ValueError('checkpoint integrity differs at acceptance')
        finally:db.close()
        receipt=dict(sha256=q['sha256'],bytes=path.stat().st_size,identity=self.objects.file_identity(path),
                     Linux_metadata=q['Linux_metadata'],native_integrity='ok',independent_readback=True)
        if proof.exists():
            self.checked(proof)
            if json.loads(proof.read_text())!=receipt:raise ValueError('checkpoint acceptance collision')
            return receipt
        atomic_new(proof,receipt);return receipt

    def authorizer(self,action,a,b,db,trigger):
        if action in (sqlite3.SQLITE_ATTACH,sqlite3.SQLITE_DETACH,sqlite3.SQLITE_CREATE_VTABLE,sqlite3.SQLITE_DROP_VTABLE):
            return sqlite3.SQLITE_DENY
        if action==sqlite3.SQLITE_FUNCTION and (b or '').lower()=='load_extension':return sqlite3.SQLITE_DENY
        if action==sqlite3.SQLITE_PRAGMA:
            allow={'query_only','integrity_check','quick_check','page_count','page_size','max_page_count','cache_size','mmap_size','temp_store','journal_mode','synchronous','user_version','table_info'}
            if a.lower() not in allow:return sqlite3.SQLITE_DENY
            if b is not None and (a.lower()=='journal_mode' and b.upper()!='DELETE'
                    or a.lower()=='synchronous' and b.upper() not in ('FULL','2')
                    or a.lower()=='temp_store' and b.upper() not in ('MEMORY','2')
                    or a.lower()=='mmap_size' and b!='0'
                    or a.lower()=='max_page_count' and (not b.isdigit() or int(b)>self.maximum//4096)):
                return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    def open(self,q):
        key=name(q['name'])
        if key in self.handles:raise ValueError('index already open in this session')
        checkpoint=self.checkpoint(q['checkpoint_sha256']);proof=checkpoint.with_suffix('.import.json')
        self.checked(proof);accepted=json.loads(proof.read_text())
        if not accepted.get('independent_readback') or accepted['identity']!=self.objects.file_identity(checkpoint):
            raise ValueError('verified original B checkpoint required')
        readonly=q.get('readonly') is True;working_read=readonly and q.get('working') is True
        # Only writers take the owner lease. A normal native read-only SQLite
        # transaction may inspect committed health/cursors while its writer
        # remains active; SQLite's native locks provide that consistency.
        lease=nullcontext() if working_read else self.objects.store_lease(self.root/(key+'-lease'))
        if not working_read:self.directory(self.root/(key+'-lease'))
        lease.__enter__()
        try:
            path=checkpoint if readonly and not working_read else self.root/(key+'.sqlite')
            binding=self.root/(key+'.binding.json')
            if working_read:
                self.checked(binding);bound=json.loads(binding.read_text())
                if bound!={'checkpoint_sha256':q['checkpoint_sha256'],'inode':self.objects.file_identity(path)[:2]}:
                    raise ValueError('read-only working-index binding changed')
            if not readonly:
                if not binding.exists():
                    if path.exists():
                        # Recover a completed clone after acknowledgement loss;
                        # partial clones keep their separate names.
                        if self.hash(path)!=q['checkpoint_sha256']:raise ValueError('unbound working index differs')
                    else:
                        self.guard(checkpoint.stat().st_size+1024**2)
                        temp=path.with_name(path.name+'.'+os.urandom(8).hex()+'.partial')
                        with checkpoint.open('rb') as source,temp.open('xb') as out:
                            for block in iter(lambda:source.read(BLOCK),b''):self.guard(0);out.write(block)
                            out.flush();os.fsync(out.fileno())
                        if self.hash(temp)!=q['checkpoint_sha256']:raise ValueError('working clone differs')
                        if path.exists():raise ValueError('working index collision')
                        os.rename(temp,path)
                    atomic_new(binding,dict(checkpoint_sha256=q['checkpoint_sha256'],inode=self.objects.file_identity(path)[:2]))
                self.checked(binding);bound=json.loads(binding.read_text())
                if bound!={'checkpoint_sha256':q['checkpoint_sha256'],'inode':self.objects.file_identity(path)[:2]}:
                    raise ValueError('working index binding changed')
            self.checked(path)
            suffix='?mode=ro' if working_read else '?mode=ro&immutable=1' if readonly else '?mode=rw'
            db=sqlite3.connect(path.as_uri()+suffix,uri=True,timeout=0,isolation_level=None)
            self.configure(db)
            if not readonly:
                db.execute('pragma journal_mode=DELETE');db.execute('pragma synchronous=FULL')
                page=db.execute('pragma page_size').fetchone()[0]
                db.execute('pragma max_page_count='+str(self.maximum//page))
            db.set_authorizer(self.authorizer)
            self.handles[key]=(db,path,self.objects.file_identity(path)[:2],lease)
            if readonly and not working_read:self.readonly_identities[key]=self.objects.file_identity(path)
            return dict(open=True,in_transaction=False,bytes=path.stat().st_size)
        except BaseException:lease.__exit__(None,None,None);raise

    def call(self,q):
        self.guard(1024**2);op=q['op']
        self.guard_reason=None
        if op=='describe':
            key=name(q['name']);p=self.root/(key+'.binding.json');self.checked(p)
            return json.loads(p.read_text())
        if op=='seed':
            # New control state only: no live/source database is copied. The
            # caller independently reads this tiny B-native seed before use.
            temp=self.root/('empty-'+os.urandom(8).hex()+'.partial')
            db=sqlite3.connect(temp)
            try:
                db.execute('pragma temp_store=MEMORY');db.execute('pragma synchronous=FULL')
                db.execute('create table nightly_control_seed(version integer not null)')
                db.execute('insert into nightly_control_seed values(1)');db.commit()
            finally:db.close()
            digest=self.hash(temp);path=self.checkpoint(digest)
            if path.exists():
                if self.hash(path)!=digest:raise ValueError('control seed collision')
                # Keep this tiny duplicate too; no original retirement here.
            else:os.rename(temp,path)
            return dict(sha256=digest,bytes=path.stat().st_size,Linux_metadata={'origin':'new-native-B-control-not-a-source-copy'})
        if op in ('import','acknowledge'):
            directory=self.root/(sha(q['sha256'])+'-import-lease');self.directory(directory)
            with self.objects.store_lease(directory):
                return self.import_index(q) if op=='import' else self.acknowledge(q)
        if op=='open':return self.open(q)
        key=name(q['name']);db,path,inode,lease=self.handles[key]
        self.checked(path)
        if self.objects.file_identity(path)[:2]!=inode:raise ValueError('open B control index substituted')
        if key in self.readonly_identities and self.objects.file_identity(path)!=self.readonly_identities[key]:
            raise ValueError('immutable B checkpoint changed while reading')
        if op=='check':return dict(in_transaction=db.in_transaction,bytes=path.stat().st_size)
        if op=='namespace-next':
            limit=q['limit']
            if type(limit) is not int or not 1<=limit<=512:raise ValueError('bounded namespace queue request required')
            return dict(paths=[p for p, in db.execute('select path from gap_pending where done=0 order by path limit ?',(limit,))])
        if op=='namespace-statistics':
            return dict(unique_paths=db.execute('select count(*) from namespace').fetchone()[0],
                pending_directories=db.execute('select count(*) from gap_pending where done=0').fetchone()[0],
                replay_errors=db.execute('select count(*) from namespace_errors').fetchone()[0],
                index_bytes=path.stat().st_size)
        if op=='namespace-batch':
            if len(q['rows'])+len(q['errors'])>1024 or len(q['completed'])>512:
                raise ValueError('bounded namespace transaction required')
            maximum=q['maximum_paths']
            if type(maximum) is not int or maximum<1:raise ValueError('finite namespace bound required')
            self.guard(path.stat().st_size+LIMIT);db.execute('begin immediate')
            try:
                added=db.executemany('insert or ignore into namespace values(?,?)',q['rows']).rowcount
                total=db.execute('select unique_paths from gap_stats where id=1').fetchone()[0]+max(0,added)
                if total>maximum:raise ValueError('measured namespace exceeds admitted path bound')
                db.executemany('update namespace set row=? where name=?',((raw,member) for member,raw in q['rows']))
                db.executemany('insert or ignore into gap_pending values(?,0)',((p,) for p in q['children']))
                db.executemany('insert into namespace_errors values(?,?) on conflict(name) do update set error=excluded.error',q['errors'])
                db.executemany('update gap_pending set done=1 where path=?',((p,) for p in q['completed']))
                db.execute('update gap_stats set unique_paths=? where id=1',(total,));db.execute('commit')
            except BaseException:
                if db.in_transaction:db.execute('rollback')
                raise
            return dict(unique_paths=total,index_bytes=path.stat().st_size)
        if op=='close':
            for cid,(owner,cursor) in list(self.cursors.items()):
                if owner==key:
                    cursor.close();del self.cursors[cid];self.pending_rows.pop(cid,None);self.exhausted.pop(cid,None)
            db.close();lease.__exit__(None,None,None);del self.handles[key];self.readonly_identities.pop(key,None)
            return dict(closed=True)
        if op=='refresh-current-map':
            # The exact same qualified-row classifier runs next to both native
            # SQLite indexes; no per-path network round trips or source reread.
            import vk_nightly_current_map as current
            from vk_nightly_qualification import decode_observation
            qualifier,qp,qi,ql=self.handles[name(q['qualifier'])]
            if self.objects.file_identity(qp)[:2]!=qi:raise ValueError('qualifier index substituted')
            value=current.CurrentMap();value.db=db;value.path=path;value.inode=tuple(inode)
            def qualified(member):
                row=qualifier.execute('select row from versions where name=?',(member,)).fetchone()
                return decode_observation(row[0]) if row else None
            return value.refresh_unresolved(qualified,checkpoint=lambda:self.guard(path.stat().st_size+LIMIT),
                maximum_paths=q['maximum_paths'],after=q.get('after',''))
        if op=='reconcile-current-map':
            import vk_nightly_current_map as current
            from vk_nightly_qualification import decode_observation
            qualifier,qp,qi,ql=self.handles[name(q['qualifier'])]
            namespace,np,ni,nl=self.handles[name(q['namespace'])]
            for p,i in ((qp,qi),(np,ni)):
                if self.objects.file_identity(p)[:2]!=i:raise ValueError('reconciliation dependency substituted')
            value=current.CurrentMap();value.db=db;value.path=path;value.inode=tuple(inode)
            def qualified(member):
                row=qualifier.execute('select row from versions where name=?',(member,)).fetchone()
                return decode_observation(row[0]) if row else None
            return value.reconcile_namespace(namespace,qualified,checkpoint=lambda:self.guard(path.stat().st_size+LIMIT),
                maximum_paths=q['maximum_paths'])
        if op=='member-demand':
            from vk_nightly_current_map import decode_member
            totals={};largest=[]
            for member,state,raw in db.execute("select name,state,row from members where state not in ('directory','symlink','verified-file')"):
                value=decode_member(raw);row=value.get('member') or value.get('namespace') or {}
                count,size=totals.get(state,(0,0));size+=row.get('bytes',0);totals[state]=(count+1,size)
                if state=='file-needs-capture':
                    largest.append((row['bytes'],member));largest=sorted(largest,reverse=True)[:10]
            return dict(unresolved_counts_and_logical_bytes=totals,largest_qualified_pending_files=largest,
                        source_body_bytes_read=0,backup_payload_bytes_copied=0)
        if op=='accept-file-point':
            import vk_nightly_current_map as current
            value=current.CurrentMap();value.db=db;value.path=path;value.inode=tuple(inode)
            return value.accept_file(q['member_name'],q['original_sha256'],q['accepted'],q['proof'],
                checkpoint=lambda:self.guard(path.stat().st_size+LIMIT))
        if op=='defer-file-point':
            import vk_nightly_current_map as current
            value=current.CurrentMap();value.db=db;value.path=path;value.inode=tuple(inode)
            value.defer_file(q['member_name'],q['original_sha256'],q['reason'],
                checkpoint=lambda:self.guard(path.stat().st_size+LIMIT))
            return dict(deferred=True)
        if op in ('execute','executemany'):
            # A rollback journal can touch any existing page. This is actual
            # operation headroom, not a withdrawn fixed B reserve.
            self.guard(path.stat().st_size+LIMIT)
            statement=q['sql']
            if not isinstance(statement,str) or len(statement)>65536:raise ValueError('bounded trusted SQL required')
            cursor=getattr(db,op)(statement,q.get('parameters',[]))
            affected=cursor.rowcount
            cid=None
            if cursor.description:
                if len(self.cursors)>=256:raise ValueError('control cursor budget exceeded')
                self.next_cursor+=1;cid=self.next_cursor;self.cursors[cid]=(key,cursor)
            else:cursor.close()
            return dict(cursor=cid,rowcount=affected,in_transaction=db.in_transaction)
        if op=='fetch':
            owner,cursor=self.cursors[q['cursor']]
            if owner!=key:raise ValueError('cursor owner differs')
            count=q['count']
            if type(count) is not int or not 1<=count<=128:raise ValueError('bounded fetch required')
            available=self.pending_rows.pop(q['cursor'],[])
            if not available:
                available=cursor.fetchmany(count);self.exhausted[q['cursor']]=len(available)<count
            rows=[];size=0
            for row in available:
                needed=len(packed(row))+1
                if rows and size+needed>LIMIT-65536:break
                rows.append(row);size+=needed
            if len(rows)<len(available):self.pending_rows[q['cursor']]=available[len(rows):]
            done=self.exhausted[q['cursor']] and len(rows)==len(available)
            if done:cursor.close();del self.cursors[q['cursor']];self.exhausted.pop(q['cursor'],None)
            return dict(rows=rows,done=done,in_transaction=db.in_transaction)
        raise ValueError('unknown B control operation')

    def close(self):
        for key in list(self.handles):self.call(dict(op='close',name=key))


def serve(root,source,output,*,objects,guard,maximum_index_bytes=4*1024**3):
    store=Store(root,objects,guard=guard,maximum_index_bytes=maximum_index_bytes)
    try:
        while True:
            q=recv(source)
            if q['op']=='bye':send(output,dict(closed=True));return
            if q['op']=='readback':
                path=store.checkpoint(q['sha256']);store.checked(path)
                identity=objects.file_identity(path);send(output,dict(bytes=path.stat().st_size))
                with path.open('rb') as stream:
                    for block in iter(lambda:stream.read(BLOCK),b''):guard(0);output.write(block)
                output.flush()
                if objects.file_identity(path)!=identity:raise ValueError('checkpoint changed during readback')
                send(output,dict(sha256=store.hash(path)));continue
            try:result=store.call(q)
            except (OSError,ValueError,sqlite3.Error,KeyError) as error:
                send(output,dict(error_type=type(error).__name__,error=str(error),guard_reason=store.guard_reason));continue
            send(output,dict(result=result))
    except EOFError:pass
    finally:
        # Closing is a consistency operation even when a resource guard failed:
        # native SQLite must roll back only this connection's uncommitted work.
        for db,path,inode,lease in list(store.handles.values()):
            try:db.close()
            finally:lease.__exit__(None,None,None)


class Client:
    def __init__(self,source,output,*,guard=lambda:None):self.source=source;self.output=output;self.guard=guard
    def call(self,**query):
        self.guard();send(self.output,query);value=recv(self.source)
        if 'error' in value:raise ValueError('native B '+value['error_type']+': '+value['error']+
                                           ('; '+value['guard_reason'] if value.get('guard_reason') else ''))
        return value['result']
    def readback(self,digest,*,sink=None,on_progress=lambda _:None):
        self.guard();send(self.output,dict(op='readback',sha256=digest));header=recv(self.source)
        h=hashlib.sha256();left=header['bytes'];reported=0
        while left:
            self.guard();block=exact(self.source,min(left,BLOCK));h.update(block);left-=len(block)
            if sink is not None:
                view=memoryview(block)
                while view:
                    n=sink.write(view)
                    if type(n) is not int or not 0<n<=len(view):raise OSError('control recall sink short write')
                    view=view[n:]
            read=header['bytes']-left
            if read-reported>=16*1024**2 or not left:on_progress(read);reported=read
        final=recv(self.source)
        if final!={'sha256':digest} or h.hexdigest()!=digest:raise ValueError('independent B index readback differs')
        return header['bytes']
    def connect(self,key,digest,*,readonly=False,working=False):
        self.call(op='open',name=key,checkpoint_sha256=digest,readonly=readonly,working=working)
        return Connection(self,key)


class Connection:
    def __init__(self,client,key):self.client=client;self.key=key;self.in_transaction=False
    def request(self,op,**query):
        value=self.client.call(op=op,name=self.key,**query)
        self.in_transaction=value.get('in_transaction',self.in_transaction);return value
    def execute(self,sql,parameters=()):
        result=self.request('execute',sql=sql,parameters=parameters)
        return Cursor(self,result['cursor'],result['rowcount'])
    def executemany(self,sql,parameters):
        result=self.request('executemany',sql=sql,parameters=list(parameters))
        return Cursor(self,result['cursor'],result['rowcount'])
    def close(self):self.request('close')
    def commit(self):
        if self.in_transaction:self.execute('commit')
    def rollback(self):
        if self.in_transaction:self.execute('rollback')


class Cursor:
    def __init__(self,db,cid,rowcount=-1):self.db=db;self.id=cid;self.rowcount=rowcount;self.buffer=[];self.done=cid is None
    def fetchone(self):
        if not self.buffer and not self.done:
            value=self.db.request('fetch',cursor=self.id,count=128);self.done=value['done'];self.buffer=value['rows']
        return tuple(self.buffer.pop(0)) if self.buffer else None
    def fetchall(self):return list(self)
    def __iter__(self):
        while True:
            row=self.fetchone()
            if row is None:return
            yield row


@contextmanager
def current_map(client,key,digest,*,binding):
    from vk_nightly_current_map import CurrentMap,FORMAT
    class RemoteMap(CurrentMap):
        def check(self):self.db.request('check')
        def source_phase_check(self):
            # Each fetch and final atomic acceptance revalidates the native
            # inode and held writer lease. Source streaming needs the host
            # guard, without an extra network round trip for every tiny file.
            client.guard()
        def accept_file(self,name,original_sha256,accepted,proof,*,checkpoint):
            checkpoint()
            return self.db.request('accept-file-point',member_name=name,original_sha256=original_sha256,
                                   accepted=accepted,proof=proof)
        def defer_file(self,name,original_sha256,reason,*,checkpoint):
            checkpoint()
            return self.db.request('defer-file-point',member_name=name,original_sha256=original_sha256,reason=reason)
    value=RemoteMap();value.db=client.connect(key,digest)
    class RemotePath:
        def stat(self):return type('Size',(),{'st_size':value.db.request('check')['bytes']})()
    value.path=RemotePath()
    try:
        expected=json.dumps(binding,sort_keys=True,separators=(',',':'),allow_nan=False)
        if value.db.execute('select format,binding from metadata').fetchall()!=[(FORMAT,expected)]:
            raise ValueError('remote current-map input binding differs')
        yield value
    finally:value.db.close()


@contextmanager
def tracking_store(client,key,digest,*,maximum_bytes=256*1024**2):
    from vk_nightly_tracking import TrackingStore
    class RemoteTracking(TrackingStore):
        def check(self):self.db.request('check')
        def byte_size(self):return self.db.request('check')['bytes']
    value=RemoteTracking();value.db=client.connect(key,digest)
    try:
        page=value.db.execute('pragma page_size').fetchone()[0]
        value.db.execute('pragma max_page_count='+str(maximum_bytes//page))
        value.initialize(value.db)
        yield value
    finally:value.db.close()


def seed(client):
    value=client.call(op='seed');client.readback(value['sha256'])
    client.call(op='acknowledge',sha256=value['sha256'],independent_stream_sha256=value['sha256'],Linux_metadata=value['Linux_metadata'])
    return value['sha256']
