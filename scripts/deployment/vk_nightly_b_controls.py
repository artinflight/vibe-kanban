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
import subprocess
import time
import traceback

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


class ImmutableImageChecks:
    """Batch redundant identity opens of leased, immutable SQLite images.

    Genuine drive/STOP/capacity/deadline admission still runs on EVERY call.
    Image identities are bracketed at entry/forced completion, at most256
    metadata steps apart and at most0.1s while callbacks are active. No accepted
    result is returned before the final forced identity validation.
    """
    def __init__(self,images,objects,guard,*,label,clock=time.monotonic):
        self.images=tuple(images);self.objects=objects;self.guard=guard
        self.label=label;self.clock=clock;self.last=None;self.steps=0
    def __call__(self,*,force=False):
        self.guard();self.steps+=1;now=self.clock()
        if force or self.last is None or self.steps>=256 or now-self.last>=0.1:
            for path,identity in self.images:
                if self.objects.file_identity(path)!=identity:
                    raise ValueError('immutable '+self.label+' changed')
            self.last=now;self.steps=0


class Store:
    def __init__(self,root,objects,*,guard,maximum_index_bytes=4*1024**3,progress=None):
        self.root=Path(root);self.objects=objects;self.guard=guard;self.maximum=maximum_index_bytes
        self.progress=progress or (lambda _:None)
        if self.root.resolve()!=self.root or not self.root.is_dir():raise ValueError('existing canonical B control directory required')
        self.handles={};self.writable=set();self.cursors={};self.next_cursor=0;self.readonly_identities={};self.pending_rows={};self.exhausted={}
        self.cache_bytes=128*1024**2;self.guard_reason=None;self.temporary_configured=False

    def configure(self,db):
        if not self.temporary_configured:
            # SQLite spill/statement journals and Python-owned temporary work
            # belong on the same admitted B control volume. This affects only
            # this dedicated worker process, never OS/global settings or sources.
            self.guard(1024**2);temporary=self.root/'sqlite-tmp-v1';self.directory(temporary)
            previous=db.execute('pragma temp_store_directory').fetchone()
            self.previous_temporary_directory=previous[0] if previous else ''
            db.execute("pragma temp_store_directory='"+str(temporary).replace("'","''")+"'")
            actual=db.execute('pragma temp_store_directory').fetchone()
            if actual is None or Path(actual[0]).resolve()!=temporary:
                raise ValueError('native SQLite cannot verify B temporary placement')
            self.temporary_directory=temporary;self.temporary_configured=True
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

    def seal_working(self,key,db,path,q):
        """Make a resumable B-native control image, never a source-body copy.

        A successful image is still unaccepted until the ordinary independent
        stream/hash and acknowledge path passes. The request binds its logical
        epoch separately from immutable bytes. Lost replies reuse the exact
        image; later writes to the working descendant cannot alter it.
        """
        if key not in self.writable or db.in_transaction:
            raise ValueError('owned committed writable index required for sealing')
        request=dict(format='vk-nightly-B-working-checkpoint-v1',index=key,binding=q['binding'])
        canonical=json.dumps(request,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        if len(canonical)>65536 or hashlib.sha256(canonical).hexdigest()!=sha(q['request_sha256']):
            raise ValueError('exact bounded working-checkpoint request binding required')
        manifest=self.root/('snapshot-'+q['request_sha256']+'.json')
        if manifest.exists():
            self.checked(manifest)
            if manifest.stat().st_size>131072:raise ValueError('bounded working-checkpoint receipt required')
            result=json.loads(manifest.read_text());image=self.checkpoint(result['sha256'])
            if result['request']!=request or self.objects.file_identity(image)!=result['image_identity'] or self.hash(image)!=result['sha256']:
                raise ValueError('retained working-checkpoint receipt or image differs')
            return dict(result,reused_completed_snapshot=True)
        size=path.stat().st_size;page_size=db.execute('pragma page_size').fetchone()[0]
        if size>self.maximum:raise ValueError('working-checkpoint exceeds admitted image budget')
        self.guard(size+2*LIMIT);before=self.objects.file_identity(path)
        temporary=self.root/('snapshot-'+q['request_sha256']+'-'+os.urandom(8).hex()+'.partial')
        # Reserve the pathname exclusively; never replace retained partials.
        with temporary.open('xb'):pass
        target=sqlite3.connect(temporary,isolation_level=None)
        try:
            self.configure(target);target.execute('pragma synchronous=FULL')
            target.execute('pragma page_size='+str(page_size))
            target.execute('pragma max_page_count='+str(self.maximum//page_size))
            def progress(status,remaining,total):
                if status not in (sqlite3.SQLITE_OK,sqlite3.SQLITE_DONE):
                    raise sqlite3.OperationalError('snapshot backup could not progress: '+str(status))
                self.guard(remaining*page_size+2*LIMIT)
            db.backup(target,pages=256,progress=progress,sleep=0)
            if target.execute('pragma integrity_check').fetchall()!=[('ok',)]:
                raise ValueError('native working-checkpoint integrity failed; partial retained')
        finally:target.close()
        with temporary.open('r+b') as stream:os.fsync(stream.fileno())
        if self.objects.file_identity(path)!=before:
            raise ValueError('working index changed while sealing; partial retained')
        if temporary.stat().st_size>self.maximum:raise ValueError('sealed image exceeds admitted byte budget')
        digest=self.hash(temporary);image=self.checkpoint(digest)
        if image.exists():
            if self.hash(image)!=digest:raise ValueError('working-checkpoint content collision')
            # The separately retained partial is never mistaken for an accepted image.
        else:os.rename(temporary,image)
        result=dict(format='vk-nightly-B-working-checkpoint-result-v1',request=request,
            request_sha256=q['request_sha256'],sha256=digest,bytes=image.stat().st_size,
            image_identity=self.objects.file_identity(image),source_identity=before,
            Linux_metadata=dict(origin='native-B-control-image-not-source-Linux-metadata'),
            native_integrity='ok',status='needs_independent_readback',reused_completed_snapshot=False)
        self.guard(0);atomic_new(manifest,result);return result

    def accepted_snapshot(self,q):
        """Recall only an already independently accepted immutable image.

        Verify its complete native hash now, and reopen its original import
        receipt under the existing import lease. Never snapshot the working
        descendant or fabricate a new independent-readback observation.
        """
        request=dict(format='vk-nightly-B-working-checkpoint-v1',index=name(q['index']),binding=q['binding'])
        raw=json.dumps(request,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        if len(raw)>65536 or hashlib.sha256(raw).hexdigest()!=sha(q['request_sha256']):
            raise ValueError('exact accepted-snapshot request required')
        manifest=self.root/('snapshot-'+q['request_sha256']+'.json');self.checked(manifest)
        if manifest.stat().st_size>131072:raise ValueError('bounded immutable snapshot receipt required')
        result=json.loads(manifest.read_text());image=self.checkpoint(result['sha256'])
        directory=self.root/(result['sha256']+'-import-lease');self.checked(directory/'OBJECT_STORE.lease')
        with self.objects.store_lease(directory):
            proof=image.with_suffix('.import.json');self.checked(proof)
            if proof.stat().st_size>131072:raise ValueError('bounded immutable acceptance required')
            accepted=json.loads(proof.read_text());actual=self.objects.file_identity(image)
            if (result['request']!=request or result['request_sha256']!=q['request_sha256']
                    or actual!=result['image_identity'] or accepted.get('identity')!=actual
                    or accepted.get('sha256')!=result['sha256'] or accepted.get('bytes')!=actual[2]
                    or result['bytes']!=actual[2] or accepted.get('Linux_metadata')!=result['Linux_metadata']
                    or accepted.get('native_integrity')!='ok' or accepted.get('independent_readback') is not True
                    or self.hash(image)!=result['sha256'] or self.objects.file_identity(image)!=actual):
                raise ValueError('accepted immutable snapshot/proof changed; preserve originals')
            self.guard(0)
            return dict(result,acceptance=accepted,reused_completed_snapshot=True,
                independent_stream_readback_verified=True,previous_independent_stream_readback_reused=True,
                new_independent_stream_bytes_read=0,new_snapshot_bytes=0,whole_baseline_accepted=False)

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
        lease.__enter__();db=None
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
            if not readonly and path.stat().st_size>self.maximum:
                raise ValueError('existing native B index exceeds this phase byte budget; preserve and use its measured working size')
            suffix='?mode=ro' if working_read else '?mode=ro&immutable=1' if readonly else '?mode=rw'
            db=sqlite3.connect(path.as_uri()+suffix,uri=True,timeout=0,isolation_level=None)
            self.configure(db)
            if not readonly:
                db.execute('pragma journal_mode=DELETE');db.execute('pragma synchronous=FULL')
                page=db.execute('pragma page_size').fetchone()[0]
                actual=db.execute('pragma max_page_count='+str(self.maximum//page)).fetchone()[0]
                if actual!=self.maximum//page:raise ValueError('native SQLite page ceiling differs from admitted index budget')
            db.set_authorizer(self.authorizer)
            self.handles[key]=(db,path,self.objects.file_identity(path)[:2],lease)
            if not readonly:self.writable.add(key)
            if readonly and not working_read:self.readonly_identities[key]=self.objects.file_identity(path)
            return dict(open=True,in_transaction=False,bytes=path.stat().st_size)
        except BaseException:
            if db is not None:db.close()
            lease.__exit__(None,None,None);raise

    def call(self,q):
        self.guard(1024**2);op=q['op']
        self.guard_reason=None
        if op=='describe':
            key=name(q['name']);p=self.root/(key+'.binding.json');self.checked(p)
            return json.loads(p.read_text())
        if op=='inspect-working':
            # Do not hold a SQLite read cursor across a remote fetch while a
            # FULL/DELETE writer is committing. These are filesystem progress
            # counters, never a substitute for accepted SQL/content evidence.
            key=name(q['name']);binding=self.root/(key+'.binding.json');self.checked(binding)
            if binding.stat().st_size>4096:raise ValueError('bounded native index binding required')
            bound=json.loads(binding.read_text());path=self.root/(key+'.sqlite');self.checked(path)
            identity=self.objects.file_identity(path)
            if bound!={'checkpoint_sha256':sha(q['checkpoint_sha256']),'inode':identity[:2]}:
                raise ValueError('inspected working-index binding changed')
            allocated=getattr(path.stat(),'st_blocks',None)
            if os.name=='nt':
                import ctypes
                api=ctypes.WinDLL('kernel32',use_last_error=True).GetCompressedFileSizeW
                api.argtypes=[ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_uint32)];api.restype=ctypes.c_uint32
                high=ctypes.c_uint32();ctypes.set_last_error(0);low=api(str(path),ctypes.byref(high))
                if low==0xffffffff and ctypes.get_last_error():raise ctypes.WinError(ctypes.get_last_error())
                allocated=(high.value<<32)|low
            elif allocated is not None:allocated*=512
            return dict(working_bytes=identity[2],allocated_bytes=allocated,identity=identity,
                        metadata_only=True,content_or_SQL_acceptance=False)
        if op=='accepted-snapshot':return self.accepted_snapshot(q)
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
        if op=='seal-working':return self.seal_working(key,db,path,q)
        if op=='adopt-runtime-component':
            if key not in self.writable:raise ValueError('owned main map writer required')
            source=name(q['component_index']);component,cp,ci,_=self.handles[source]
            reference=q['component_reference']
            if (source not in self.readonly_identities or reference.get('sha256')!=cp.stem
                    or reference.get('bytes')!=cp.stat().st_size or reference.get('selector')!=cp.name):
                raise ValueError('actual independently accepted immutable runtime component required')
            if self.objects.file_identity(cp)!=self.readonly_identities[source]:raise ValueError('runtime component image changed')
            import vk_nightly_current_map as current
            value=current.CurrentMap();value.db=db;value.path=path;value.inode=tuple(inode)
            return value.adopt_runtime_component(component,reference,q['expected_files'],checkpoint=lambda:self.guard(LIMIT))
        if op=='build-current-descriptor':
            if key not in self.readonly_identities:
                raise ValueError('independently accepted immutable checkpoint required for descriptor')
            reference=q['reference'];contract=q['consumer_contract']
            if (reference.get('sha256')!=path.stem or reference.get('bytes')!=path.stat().st_size
                    or reference.get('selector')!=path.name
                    or not isinstance(contract.get('dependencies'),dict)
                    or contract['dependencies'].get(reference.get('layer'),{}).get('native_root','').replace('\\','/').rstrip('/').casefold()
                        !=str(self.root).replace('\\','/').rstrip('/').casefold()):
                raise ValueError('exact admitted immutable B control reference required')
            from vk_nightly_recovery_descriptor import build
            checked=ImmutableImageChecks([(path,self.readonly_identities[key])],self.objects,
                lambda:self.guard(0),label='descriptor image')
            checked(force=True)
            result=build(db,reference,contract,checkpoint=checked)
            checked(force=True);return result
        if op=='audit-current-content':
            if key not in self.readonly_identities:
                raise ValueError('independently accepted immutable current map required for content audit')
            reference=q['reference']
            if (reference.get('sha256')!=path.stem or reference.get('bytes')!=path.stat().st_size
                    or reference.get('selector')!=path.name or reference.get('format')!='vk-nightly-current-member-map-v1'):
                raise ValueError('exact immutable content-audit map reference required')
            catalogs=q['recipe_indexes'];base=name(q['base_index'])
            if (not isinstance(catalogs,list) or len(catalogs)>8 or len(catalogs)!=len(set(catalogs))
                    or not {base,*catalogs}<=self.readonly_identities.keys()):
                raise ValueError('explicit independently accepted immutable proof catalogs required')
            base_names=q.get('base_names_index')
            if base_names is not None:
                base_names=name(base_names)
                if base_names not in self.readonly_identities:raise ValueError('independently accepted original-name catalog required')
            keys={key,base,*catalogs,*([base_names] if base_names else [])}
            checked=ImmutableImageChecks([(self.handles[selected][1],self.readonly_identities[selected])
                for selected in keys],self.objects,lambda:self.guard(0),label='content-audit dependency')
            checked(force=True)
            from vk_nightly_composed_proofs import audit
            object_root=self.root.parent/'objects-v1'
            self.objects.regular(object_root/'OBJECT_STORE.lease')
            # A read-only audit cannot run alongside an admitted body writer,
            # create missing store state or change any accepted receipt.
            with self.objects.store_lease(object_root):
                result=audit(db,reference,base_catalog=self.handles[base][0],
                    recipe_catalogs=[self.handles[n][0] for n in catalogs],objects=self.objects,
                    objects_root=object_root,guard=checked,named_components=q.get('named_components',{}),
                    base_names_catalog=self.handles[base_names][0] if base_names else None,
                    base_names_catalog_sha256=self.handles[base_names][1].stem if base_names else None,progress=self.progress)
                def catalog_reference(selected):
                    value=self.handles[selected][1]
                    return dict(sha256=value.stem,selector=value.name,bytes=value.stat().st_size)
                result['base_catalog_reference']=catalog_reference(base)
                result['recipe_catalog_references']=[catalog_reference(selected) for selected in catalogs]
                if base_names:result['base_names_catalog_reference']=catalog_reference(base_names)
                checked(force=True);return result
        if op=='check':return dict(in_transaction=db.in_transaction,bytes=path.stat().st_size)
        if op=='storage-status':
            temporary=str(self.temporary_directory)
            return dict(index_bytes=path.stat().st_size,maximum_index_bytes=self.maximum,
                page_count=db.execute('pragma page_count').fetchone()[0],page_size=db.execute('pragma page_size').fetchone()[0],
                max_page_count=db.execute('pragma max_page_count').fetchone()[0],
                temp_store=db.execute('pragma temp_store').fetchone()[0],temporary_directory=temporary,
                sqlite_temp_directory=str(self.root/'sqlite-tmp-v1'),
                temporary_volume_free_bytes=shutil.disk_usage(temporary).free,
                B_control_free_bytes=shutil.disk_usage(self.root).free,sqlite_version=sqlite3.sqlite_version,
                in_transaction=db.in_transaction,metadata_only=True)

        if op=='namespace-next':
            limit=q['limit']
            if type(limit) is not int or not 1<=limit<=512:raise ValueError('bounded namespace queue request required')
            return dict(paths=[p for p, in db.execute('select path from gap_pending where done=0 order by path limit ?',(limit,))])
        if op=='namespace-statistics':
            return dict(unique_paths=db.execute('select count(*) from namespace').fetchone()[0],
                pending_directories=db.execute('select count(*) from gap_pending where done=0').fetchone()[0],
                replay_errors=db.execute('select count(*) from namespace_errors').fetchone()[0],
                index_bytes=path.stat().st_size)
        if op=='namespace-inode-demand':
            from vk_nightly_qualification import decode_observation
            maximum=q['maximum_paths']
            if type(maximum) is not int or not 1<=maximum<=1000000:raise ValueError('bounded retained namespace required')
            identities={};files=directories=links=hardlinks=seen=0
            for member,raw in db.execute('select name,row from namespace order by name'):
                seen+=1
                if seen>maximum:raise ValueError('retained metadata exceeds inode-count admission')
                if seen%1024==0:self.guard(1024**2)
                row=decode_observation(raw);kind=row['kind']
                if kind not in ('file','directory','symlink'):continue
                identity=row['identity'];key=(identity[0],identity[1],kind)
                linked=kind=='file' and identity[8]>1
                identities[key]=identities.get(key,False) or linked
                files+=kind=='file';directories+=kind=='directory';links+=kind=='symlink';hardlinks+=linked
            regular=sum(k[2]=='file' for k in identities);dirs=sum(k[2]=='directory' for k in identities)
            symlinks=sum(k[2]=='symlink' for k in identities)
            return dict(retained_paths=seen,regular_paths=files,directory_paths=directories,
                symlink_paths=links,unique_symlink_inodes=symlinks,
                unique_regular_inodes=regular,unique_directory_inodes=dirs,
                hardlinked_paths=hardlinks,unique_hardlinked_inodes=sum(identities.values()),
                all_inode_watch_demand=regular+dirs+symlinks,source_body_bytes_read=0,source_paths_scanned=0,
                scope='retained namespace epoch, not fresh filesystem admission')
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
            db.close();lease.__exit__(None,None,None);del self.handles[key];self.readonly_identities.pop(key,None);self.writable.discard(key)
            return dict(closed=True)
        if op=='accept-SQL-point':
            # Accept only the exact independently sealed body record, not a
            # caller's asserted integrity flag or current source resolution.
            import vk_nightly_current_map as current
            record=q['record'];seal=record['B_acceptance_object']
            if type(seal['bytes']) is not int or not 0<seal['bytes']<=1024**2:
                raise ValueError('bounded SQL acceptance control object required')
            obj,_,accepted=self.objects.object_paths(self.root.parent/'objects-v1',seal['sha256'])
            self.checked(accepted)
            if accepted.stat().st_size>65536:raise ValueError('bounded accepted-object receipt required')
            receipt=json.loads(accepted.read_text());self.checked(obj)
            if (receipt.get('raw_sha256')!=seal['sha256'] or receipt.get('raw_bytes')!=seal['bytes']
                    or receipt.get('independent_RAM_reopened_hash_verified') is not True
                    or receipt.get('identity')!=self.objects.file_identity(obj)
                    or receipt.get('encoded_sha256')!=seal['encoded_sha256']):
                raise ValueError('accepted B SQL control object changed')
            raw=b''.join(self.objects.decoded(obj,expected_size=seal['bytes'],expected_sha=seal['sha256'],
                encoded_sha=seal['encoded_sha256'],guard=lambda:self.guard(1024**2)))
            expected={k:v for k,v in record.items() if k not in ('B_acceptance_object','new_B_total_encoded_bytes_including_control')}
            if json.loads(raw)!=expected:raise ValueError('SQL acceptance differs from its actual B object')
            value=current.CurrentMap();value.db=db;value.path=path;value.inode=tuple(inode)
            return value.accept_SQL_point(record,checkpoint=lambda:self.guard(LIMIT))
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
            def many(members):
                return {member:decode_observation(raw) for member,raw in qualifier.execute(
                    'select name,row from versions where name in ('+','.join('?' for _ in members)+')',members)}
            qualified.many=many
            extension=None
            if q.get('source_scope_extension_proof_sha256') is not None:
                expected=sha(q['source_scope_extension_proof_sha256'])
                proof_db,proof_path,proof_inode,_=self.handles[name(q['source_scope_extension_index'])]
                if self.objects.file_identity(proof_path)[:2]!=proof_inode:raise ValueError('scope proof index substituted')
                record=proof_db.execute('select row from source_outbox_handovers_inodes_v9 where sha256=?',(expected,)).fetchone()
                if record is None or hashlib.sha256(record[0].encode()).hexdigest()!=expected:
                    raise ValueError('actual B scope-extension proof missing or changed')
                extension=json.loads(record[0])
            terminal=None
            if q.get('terminal_epoch_gap_sha256') is not None:
                expected=sha(q['terminal_epoch_gap_sha256'])
                proof_db,proof_path,proof_inode,_=self.handles[name(q['terminal_epoch_gap_index'])]
                if self.objects.file_identity(proof_path)[:2]!=proof_inode:raise ValueError('terminal gap index substituted')
                record=proof_db.execute('select row from source_terminal_gaps where sha256=?',(expected,)).fetchone()
                if record is None or hashlib.sha256(record[0].encode()).hexdigest()!=expected:
                    raise ValueError('actual B terminal gap proof missing or changed')
                terminal=json.loads(record[0])
            return value.reconcile_namespace(namespace,qualified,checkpoint=lambda:self.guard(path.stat().st_size+LIMIT),
                maximum_paths=q['maximum_paths'],allow_unaccepted_epoch_successor=q.get('allow_unaccepted_epoch_successor') is True,
                source_scope_extension=extension,terminal_epoch_gap=terminal)
        if op=='replay-current-map':
            import vk_nightly_current_map as current
            expected=sha(q['input_sha256']);parts=[];total=0
            for number,(part,data) in enumerate(db.execute('select part,data from namespace_replay_inputs where sha256=? order by part',(expected,))):
                if part!=number or not isinstance(data,bytes) or not 0<len(data)<=65536:
                    raise ValueError('replay input part missing or malformed')
                parts.append(data);total+=len(data)
                if total>16*1024**2:raise ValueError('finite replay input exceeded')
            raw=b''.join(parts)
            if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('exact retained replay input required')
            value=json.loads(raw);report=value['report']
            mapped=current.CurrentMap();mapped.db=db;mapped.path=path;mapped.inode=tuple(inode)
            if db.execute("select 1 from sqlite_master where name='namespace_replay_windows'").fetchone():
                accepted=db.execute('select complete from namespace_replay_windows where sha256=?',(expected,)).fetchone()
                if accepted:
                    # An existing window was admitted against the actual B
                    # ledger before its first commit. Resume its exact saved
                    # input/cursor or return its completed point; later source
                    # changes/faults remain the next unaccepted suffix.
                    return mapped.apply_metadata_replay(report,value['replay'],checkpoint=lambda:self.guard(LIMIT),maximum_paths=q['maximum_paths'])
            journal,jp,ji,_=self.handles[name(q['journal_index'])]
            if self.objects.file_identity(jp)[:2]!=ji:raise ValueError('source journal index substituted')
            epoch=journal.execute('select binding,cursor,ready,terminal from epochs where instance=?',(report['instance'],)).fetchone()
            if not epoch or not epoch[2] or epoch[3] or epoch[1]!=report['sequence']:
                raise ValueError('actual durable B journal cursor/health differs')
            bound=json.loads(epoch[0])
            if any(bound.get(k)!=report.get(k) for k in ('instance','plan_sha256','scope_sha256','coverage_model')):
                raise ValueError('actual durable B journal binding differs')
            if journal.execute('select 1 from faults where instance=? limit 1',(report['instance'],)).fetchone():
                raise ValueError('actual B journal has an unreconciled fault')
            events=dict(journal.execute('select path,mask from changes where instance=? and sequence>? order by path',(report['instance'],report['since'])))
            if events!=report['events']:raise ValueError('replay names differ from actual retained B journal')
            delivery=journal.execute('select cursor,sha256 from outbox_delivery where instance=?',(report['instance'],)).fetchone()
            if not delivery or delivery[0]!=report['sequence']:raise ValueError('verified source barrier delivery unavailable')
            chunks=[data for part,data in journal.execute('select part,data from outbox_report_parts where instance=? order by part',(report['instance'],))]
            saved=b''.join(chunks)
            if len(saved)>16*1024**2 or hashlib.sha256(saved).hexdigest()!=delivery[1]:raise ValueError('source barrier delivery changed')
            if json.loads(saved).get('barrier')!=report.get('barrier'):raise ValueError('replay barrier differs from actual B delivery')
            mapped=current.CurrentMap();mapped.db=db;mapped.path=path;mapped.inode=tuple(inode)
            return mapped.apply_metadata_replay(report,value['replay'],checkpoint=lambda:self.guard(path.stat().st_size+LIMIT),maximum_paths=q['maximum_paths'])
        if op=='reuse-completed-file-carriers':
            import vk_nightly_current_map as current
            value=current.CurrentMap();value.db=db;value.path=path;value.inode=tuple(inode)
            return value.reuse_pending_carriers(lambda *_:(),checkpoint=lambda:self.guard(LIMIT),
                maximum_paths=q['maximum_paths'],after=q.get('after',''))
        if op=='index-completed-file-carriers':
            import vk_nightly_current_map as current
            value=current.CurrentMap();value.db=db;value.path=path;value.inode=tuple(inode)
            return value.index_completed_file_carriers(checkpoint=lambda:self.guard(LIMIT),
                maximum_paths=q['maximum_paths'],after=q.get('after',('', '')))
        if op in ('adopt-qualifications','reuse-current-file-carriers'):
            import vk_nightly_current_map as current
            base,bp,bi,_=self.handles[name(q['base_index'])]
            recipes=[]
            if not isinstance(q['recipe_indexes'],list) or len(q['recipe_indexes'])>8:raise ValueError('finite retained recipe indexes required')
            for key in q['recipe_indexes']:
                recipe,rp,ri,_=self.handles[name(key)]
                if self.objects.file_identity(rp)[:2]!=ri:raise ValueError('recipe catalog substituted')
                recipes.append(recipe)
            if self.objects.file_identity(bp)[:2]!=bi:raise ValueError('base catalog substituted')
            provenance=base.execute('select source_catalog_sha256,restore_proof_sha256 from provenance').fetchall()
            if len(provenance)!=1:raise ValueError('exact accepted base provenance required')
            for digest in provenance[0]:sha(digest)
            def carriers(digest,size):
                found=base.execute('select name from bodies where sha256=? and bytes=?',(digest,size)).fetchone()
                if found:
                    yield dict(kind='file',sha256=digest,bytes=size,segments=[dict(layer='accepted-base',selector=found[0],sha256=digest,bytes=size)])
                    return
                for catalog in recipes:
                    found=catalog.execute("select row from versions where json_extract(row,'$.sha256')=? and json_extract(row,'$.bytes')=? order by name,layer limit 1",(digest,size)).fetchone()
                    if found:yield json.loads(found[0]);return
            value=current.CurrentMap();value.db=db;value.path=path;value.inode=tuple(inode)
            if op=='reuse-current-file-carriers':
                return value.reuse_pending_carriers(carriers,checkpoint=lambda:self.guard(path.stat().st_size+LIMIT),
                    maximum_paths=q['maximum_paths'],after=q.get('after',''))
            return value.adopt_qualifications(q['records'],carriers,checkpoint=lambda:self.guard(path.stat().st_size+LIMIT))
        if op=='attach-base-prefixes':
            import vk_nightly_current_map as current
            base,bp,bi,_=self.handles[name(q['base_index'])]
            if self.objects.file_identity(bp)[:2]!=bi:raise ValueError('accepted base catalog substituted')
            value=current.CurrentMap();value.db=db;value.path=path;value.inode=tuple(inode)
            return value.attach_base_prefixes(base,checkpoint=lambda:self.guard(path.stat().st_size+LIMIT),
                maximum_paths=q['maximum_paths'],after=q.get('after',''))
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
        if op=='accept-file-points':
            import vk_nightly_current_map as current
            value=current.CurrentMap();value.db=db;value.path=path;value.inode=tuple(inode)
            return dict(results=value.accept_files(q['records'],checkpoint=lambda:self.guard(path.stat().st_size+LIMIT)))
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

    def restore_temporary_scope(self):
        # Dedicated receivers exit after closing their handles. Embedded users
        # must also restore SQLite's process-local setting; never repoint
        # Python's global tempfile cache into a disposable control fixture.
        if not self.temporary_configured:return
        probe=sqlite3.connect(':memory:')
        try:
            actual=probe.execute('pragma temp_store_directory').fetchone()
            if actual and Path(actual[0]).resolve()==self.temporary_directory:
                probe.execute("pragma temp_store_directory='"+self.previous_temporary_directory.replace("'","''")+"'")
        finally:probe.close()
        self.temporary_configured=False

    def close(self):
        for key in list(self.handles):self.call(dict(op='close',name=key))
        self.restore_temporary_scope()


def serve(root,source,output,*,objects,guard,maximum_index_bytes=4*1024**3):
    store=Store(root,objects,guard=guard,maximum_index_bytes=maximum_index_bytes,
                progress=lambda value:send(output,dict(progress=value)))
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
            except (OSError,ValueError,sqlite3.Error,KeyError,subprocess.SubprocessError) as error:
                context=dict(operation=str(q.get('op',''))[:128],index=str(q.get('name',''))[:128],
                    sqlite_errorcode=getattr(error,'sqlite_errorcode',None),sqlite_errorname=getattr(error,'sqlite_errorname',None),
                    frames=[dict(function=f.name,line=f.lineno) for f in traceback.extract_tb(error.__traceback__)[-8:]])
                send(output,dict(error_type=type(error).__name__,error=str(error),guard_reason=store.guard_reason,native_context=context));continue
            send(output,dict(result=result))
    except EOFError:pass
    finally:
        # Closing is a consistency operation even when a resource guard failed:
        # native SQLite must roll back only this connection's uncommitted work.
        for db,path,inode,lease in list(store.handles.values()):
            try:db.close()
            finally:lease.__exit__(None,None,None)
        store.restore_temporary_scope()


class NativeControlError(ValueError):
    def __init__(self,value):
        self.native_error_type=value['error_type'];self.guard_reason=value.get('guard_reason');self.native_context=value.get('native_context')
        super().__init__('native B '+value['error_type']+': '+value['error']+
                         ('; '+self.guard_reason if self.guard_reason else '')+
                         ('; context='+json.dumps(self.native_context,sort_keys=True)[:2048] if self.native_context else ''))


class NativeControlDeferred(NativeControlError):
    """Only actual competing ownership/SQLite BUSY, never denied controls."""


def retry_native_busy(operation,*,guard,timeout_seconds=10,clock=time.monotonic,sleep=time.sleep):
    """Retry the same rolled-back SQLite operation, never its body transfer.

    Only the protocol's typed SQLITE_BUSY/LOCKED signal qualifies. Access,
    STOP/health/ownership and integrity failures propagate without retry. Each
    attempt checks the caller's real guards; the finite wait cannot extend the
    owning phase deadline or authorize another producer.
    """
    if not isinstance(timeout_seconds,(int,float)) or not 0<timeout_seconds<=60:
        raise ValueError('finite native SQLite contention wait required')
    start=clock()
    while True:
        guard()
        try:return operation()
        except NativeControlDeferred as error:
            if error.native_error_type!='OperationalError' or clock()-start>=timeout_seconds:raise
            guard();sleep(.05)


class Client:
    def __init__(self,source,output,*,guard=lambda:None):
        self.source=source;self.output=output;self.guard=guard;self.operation_metrics={}
    def metrics(self):
        return dict(format='vk-nightly-control-roundtrips-v1',
            requests=sum(v['requests'] for v in self.operation_metrics.values()),
            wait_seconds=sum(v['wait_seconds'] for v in self.operation_metrics.values()),
            operations={k:dict(v) for k,v in self.operation_metrics.items()},
            SQL_text_or_parameters_recorded=False)
    def call(self,*,on_progress=None,**query):
        self.guard();started=time.monotonic()
        operation=query.get('op','unknown')
        if operation not in self.operation_metrics and len(self.operation_metrics)>=64:operation='other'
        metric=self.operation_metrics.setdefault(operation,dict(requests=0,wait_seconds=0.0,maximum_wait_seconds=0.0))
        try:
            send(self.output,query)
            while True:
                value=recv(self.source)
                if set(value)!={'progress'}:break
                if not isinstance(value['progress'],dict):raise ValueError('bounded native progress record required')
                self.guard()
                if on_progress is not None:on_progress(value['progress'])
        finally:
            elapsed=time.monotonic()-started;metric['requests']+=1;metric['wait_seconds']+=elapsed
            metric['maximum_wait_seconds']=max(metric['maximum_wait_seconds'],elapsed)
        if 'error' in value:
            temporary=not value.get('guard_reason') and (value['error_type']=='BlockingIOError'
                or value['error_type']=='OperationalError' and value['error'] in ('database is locked','database table is locked'))
            raise (NativeControlDeferred if temporary else NativeControlError)(value)
        return value['result']
    def recover_completed_files(self,key,*,on_progress=lambda _:None):
        """Finite keyset metadata passes before any pending body upload."""
        after=('', '')
        while True:
            indexed=self.call(op='index-completed-file-carriers',name=key,maximum_paths=8192,after=after)
            on_progress(dict(indexed,phase='indexing-retained-completed-body-proofs'))
            if not indexed['more_names']:break
            after=indexed['last_key']
        after='';reused=raw_bytes=0
        while True:
            batch=self.call(op='reuse-completed-file-carriers',name=key,maximum_paths=8192,after=after)
            reused+=batch['completed_file_points_reused'];raw_bytes+=batch['retained_file_bytes_reused']
            on_progress(dict(batch,phase='reusing-completed-body-points-before-transfer',
                completed_file_points_reused_this_phase=reused,retained_raw_bytes_reused_this_phase=raw_bytes))
            if not batch['more_names']:break
            after=batch['last_name']
        return dict(completed_file_points_reused=reused,retained_raw_bytes_reused=raw_bytes,
                    source_payload_bytes_read=0,backup_payload_bytes_copied=0)

    def seal_checkpoint(self,key,binding,*,on_progress=lambda _:None):
        """Seal a committed native index and independently accept exact bytes.

        This accepts only an immutable metadata image. It makes no current-set,
        source coverage, body restore, journal or scheduling acceptance claim.
        """
        request=dict(format='vk-nightly-B-working-checkpoint-v1',index=name(key),binding=binding)
        digest=hashlib.sha256(json.dumps(request,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        result=self.call(op='seal-working',name=key,binding=binding,request_sha256=digest)
        if result['request']!=request or result['request_sha256']!=digest or result['native_integrity']!='ok':
            raise ValueError('native working-checkpoint binding differs')
        if self.readback(result['sha256'],on_progress=on_progress)!=result['bytes']:
            raise ValueError('independent working-checkpoint length differs')
        accepted=self.call(op='acknowledge',sha256=result['sha256'],
            independent_stream_sha256=result['sha256'],Linux_metadata=result['Linux_metadata'])
        if (accepted['sha256']!=result['sha256'] or accepted['bytes']!=result['bytes']
                or accepted.get('native_integrity')!='ok' or accepted.get('independent_readback') is not True):
            raise ValueError('ordinary immutable checkpoint acceptance differs')
        return dict(result,acceptance=accepted,independent_stream_readback_verified=True,
                    whole_baseline_accepted=False)

    def accepted_snapshot(self,key,binding):
        request=dict(format='vk-nightly-B-working-checkpoint-v1',index=name(key),binding=binding)
        digest=hashlib.sha256(json.dumps(request,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        result=self.call(op='accepted-snapshot',index=key,binding=binding,request_sha256=digest)
        if (result['request']!=request or result['request_sha256']!=digest
                or result.get('previous_independent_stream_readback_reused') is not True
                or result['acceptance'].get('independent_readback') is not True
                or result['acceptance'].get('identity')!=result['image_identity']
                or result['acceptance'].get('sha256')!=result['sha256']):
            raise ValueError('existing independently accepted snapshot binding differs')
        return result

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
    def request(self,op,*,on_progress=None,**query):
        value=self.client.call(op=op,name=self.key,on_progress=on_progress,**query)
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
        def accept_files(self,records,*,checkpoint):
            checkpoint()
            return self.db.request('accept-file-points',records=records)['results']
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
