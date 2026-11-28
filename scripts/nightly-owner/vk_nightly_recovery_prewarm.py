"""Sealed RAM replay of actual NORMAL B bodies under the SAME held context.

Call prewarm before physical reader/writer freeze. This module opens no B
transport, lease, live original or packed object. The caller keeps its real B
context alive through replay and header switches; all normal checks still run.
"""
from contextlib import contextmanager
import fcntl
import hashlib
import os
import stat

BLOCK=1024*1024
SEALS=fcntl.F_SEAL_WRITE|fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_SEAL


def version(fd):
    s=os.fstat(fd)
    return s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns


class ReplayBody:
    def __init__(self,fd,size,sha,check):
        self.fd,self.size,self.expected,self.check=fd,size,sha,check
        self.offset=0;self.digest=hashlib.sha256();self.eof=False
    def read(self,size):
        if type(size)is not int or not 1<=size<=BLOCK:raise ValueError('bounded replay read required')
        self.check();data=os.pread(self.fd,min(size,self.size-self.offset),self.offset)
        if not data:
            if self.offset!=self.size or self.digest.hexdigest()!=self.expected:
                raise ValueError('replay full EOF hash/length differs')
            self.eof=True
        else:self.digest.update(data);self.offset+=len(data)
        self.check();return data
    def finish(self):
        if not self.eof:raise ValueError('replay was not consumed to verified EOF')
        self.check()


class PrewarmedRecovery:
    def __init__(self,recovery,*,maximum_bytes,admit):
        if type(maximum_bytes)is not int or maximum_bytes<1 or not callable(admit):
            raise ValueError('explicit actual RAM admission and byte envelope required')
        if not recovery.location.startswith('desktop:B:/vk-backups/'):
            raise ValueError('actual canonical normal B context required')
        self.original=recovery;self.location=recovery.location;self.prefix=recovery.prefix
        # Transfer the REAL held Reader identity for existing admit_held checks.
        # It is neither constructed nor marked whole-set verified here.
        self.handle=getattr(recovery,'handle',None)
        self.maximum_bytes=maximum_bytes;self.admit=admit;self.entries={};self.complete=False;self.closed=False
    def check(self):
        if self.closed:raise ValueError('prewarm context closed')
        self.original.check()
        for fd,identity,sha,size in self.entries.values():
            if (version(fd)!=identity or fcntl.fcntl(fd,fcntl.F_GET_SEALS)&SEALS!=SEALS):
                raise ValueError('sealed B-derived RAM inode changed')
    def populate(self,files):
        if self.entries or self.complete:raise ValueError('one finite prewarm per held context')
        if (not isinstance(files,list)or not files or len(files)>32
                or len({v['relative']for v in files})!=len(files)):
            raise ValueError('exact bounded unique selected originals required')
        total=sum(v['bytes']for v in files)
        if any(type(v['bytes'])is not int or v['bytes']<0 for v in files)or total>self.maximum_bytes:
            raise ValueError('actual prewarm exceeds admitted RAM peak')
        self.admit(total);self.check()
        try:
            for item in files:
                self.check();fd=os.memfd_create('nightly-normal-B-replay',os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING)
                # Keep every failed partial FD until the context closes. No
                # source/capture/store path is ever used as a cache fallback.
                self.entries[item['relative']]=(fd,version(fd),item['sha256'],item['bytes'])
                count=0;digest=hashlib.sha256()
                with self.original.open_original(item['relative'],item['sha256'])as body:
                    while block:=body.read(BLOCK):
                        self.original.check();count+=len(block)
                        if count>item['bytes']:raise ValueError('actual B prewarm exceeds exact length')
                        digest.update(block);view=memoryview(block)
                        while view:
                            n=os.write(fd,view)
                            if n<=0:raise OSError('RAM prewarm short write')
                            view=view[n:]
                if count!=item['bytes']or digest.hexdigest()!=item['sha256']:
                    raise ValueError('actual B prewarm EOF differs')
                os.fsync(fd);fcntl.fcntl(fd,fcntl.F_ADD_SEALS,SEALS)
                if not stat.S_ISREG(os.fstat(fd).st_mode):raise ValueError('RAM replay inode invalid')
                self.entries[item['relative']]=(fd,version(fd),item['sha256'],item['bytes'])
            self.complete=True;self.check()
        except BaseException:
            self.complete=False
            raise
    @contextmanager
    def open_original(self,relative,sha256):
        if not self.complete:raise ValueError('actual B prewarm incomplete')
        self.check();fd,identity,expected,size=self.entries[relative]
        if sha256!=expected:raise ValueError('exact prewarmed version differs')
        stream=ReplayBody(fd,size,expected,self.check)
        yield stream
        stream.finish();self.check()
    def close(self):
        if self.closed:return
        for fd,*_ in self.entries.values():os.close(fd)
        self.closed=True
    def __enter__(self):return self
    def __exit__(self,*_):self.close()
