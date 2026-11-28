"""Resumable control index of independently proved, retained B components.

No archive payload or live source is opened here. A trusted reader supplies the
exact independently sealed record stream after checking native carrier identity
and owner admission. Each complete component commits once; interrupted component
transactions roll back without losing earlier work. This is a version catalog,
not source qualification, journal closure or whole-backup acceptance.
"""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat

from vk_nightly_checkpoints import digest, typed_component_rows

FORMAT = 'vk-nightly-retained-version-index-v1'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def component_id(component):
    return hashlib.sha256(canonical(component).encode()).hexdigest()


class ComponentIndex:
    @classmethod
    @contextmanager
    def held(cls, path, *, create=False, maximum_bytes=1536*1024**2):
        path=Path(path)
        if (not path.is_absolute() or path.resolve()!=path or type(maximum_bytes) is not int
                or maximum_bytes<65536):
            raise ValueError('canonical finite control index required')
        fd=os.open(path,os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK|
                   (os.O_CREAT|os.O_EXCL if create else 0),0o600)
        db=None
        try:
            info=os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_nlink!=1
                    or info.st_size>maximum_bytes):
                raise ValueError('owned unique control inode within budget required')
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            db=sqlite3.connect(path,timeout=0,isolation_level=None)
            db.execute('pragma journal_mode=DELETE');db.execute('pragma synchronous=FULL')
            db.execute('pragma cache_size=-1024');db.execute('pragma mmap_size=0')
            page=db.execute('pragma page_size').fetchone()[0]
            if db.execute('pragma max_page_count='+str(maximum_bytes//page)).fetchone()[0]>maximum_bytes//page:
                raise ValueError('existing metadata exceeds budget')
            value=cls();value.path=path;value.fd=fd;value.db=db
            value.inode=(info.st_dev,info.st_ino)
            if create:
                with value.transaction():
                    db.execute('create table metadata(format text not null)')
                    db.execute('insert into metadata values(?)',(FORMAT,))
                    db.execute('create table components(id text primary key,definition text not null,members integer not null,raw_bytes integer not null) without rowid')
                    db.execute('create table versions(name text not null,layer text not null,row text not null,primary key(name,layer)) without rowid')
                    db.execute('create index content_hash on versions(json_extract(row,\'$.sha256\'),json_extract(row,\'$.bytes\'))')
                directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
                try:os.fsync(directory)
                finally:os.close(directory)
            if db.execute('select format from metadata').fetchall()!=[(FORMAT,)]:
                raise ValueError('unknown retained component index')
            value.check();yield value;value.check()
        finally:
            if db is not None:db.close()
            os.close(fd)

    def check(self):
        info=self.path.lstat();opened=os.fstat(self.fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink!=1
                or (info.st_dev,info.st_ino)!=self.inode
                or (opened.st_dev,opened.st_ino)!=self.inode or self.path.resolve()!=self.path):
            raise ValueError('retained control inode substituted')

    @contextmanager
    def transaction(self):
        self.check();self.db.execute('begin immediate')
        try:
            yield
            self.check();self.db.execute('commit')
        except BaseException:
            if self.db.in_transaction:self.db.execute('rollback')
            raise

    def contains(self,component):
        self.check();row=self.db.execute('select definition from components where id=?',
                                       (component_id(component),)).fetchone()
        if row is None:return False
        if row[0]!=canonical(component):raise ValueError('retained component binding differs')
        return True

    def adopt(self,component,records_raw,*,checkpoint=lambda:None):
        if self.contains(component):return {'already_committed':True,'metadata_bytes_read':0}
        identifier=component_id(component);layer='retained-'+identifier
        rows=typed_component_rows(component,records_raw,layer=layer)
        with self.transaction():
            for number,(name,row) in enumerate(rows):
                self.db.execute('insert into versions values(?,?,?)',(name,layer,canonical(row)))
                if number%1024==0:checkpoint()
            self.db.execute('insert into components values(?,?,?,?)',
                            (identifier,canonical(component),len(rows),component['raw_bytes']))
            checkpoint()
        return {'already_committed':False,'members':len(rows),'metadata_bytes_read':len(records_raw)}

    def carriers(self,sha256,size):
        digest(sha256);self.check()
        if type(size) is not int or size<0:raise ValueError('nonnegative content bytes required')
        for name,layer,raw in self.db.execute(
                "select name,layer,row from versions where json_extract(row,'$.sha256')=? "
                "and json_extract(row,'$.bytes')=? order by name,layer",(sha256,size)):
            yield name,layer,json.loads(raw)
        self.check()

    def summary(self):
        self.check()
        components,members,raw=self.db.execute('select count(*),coalesce(sum(members),0),coalesce(sum(raw_bytes),0) from components').fetchone()
        return dict(format=FORMAT,components=components,versioned_members=members,
                    verified_raw_version_bytes=raw,payload_bytes_copied=0,
                    current_source_qualified=False,full_backup_accepted=False)
