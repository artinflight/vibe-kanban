"""Count an actual cold capture stream without retaining its archive payload.

This is capacity evidence, never an accepted backup or permission to retire one.
SQLite images use the normal registered B snapshot path. The full tar stream is
hashed/compressed and its unique chunk/layout sizes are counted in SSD SQLite.
No archive/object payload is retained and no publication receipt is fabricated.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tarfile
import threading
import time
import traceback
import zlib

from vk_archive_stream import StreamingArchive
from vk_candidate_direct_b import metadata
from vk_nightly_generation import CHUNKED, CHUNK_BYTES, MAX_ENTRIES, MAX_INDEX, encoded, name
from vk_prep_common import storage, save


class MeasurementComplete(ValueError):
    pass


class StreamMeter:
    def __init__(self, root, *, allocation_unit=4096):
        self.root=storage(root);self.root.mkdir(mode=0o700,exist_ok=False)
        if type(allocation_unit) is not int or not 512<=allocation_unit<=65536 or allocation_unit&(allocation_unit-1):
            raise ValueError('observed finite power-of-two allocation unit required')
        self.unit=allocation_unit;self.started=time.monotonic();self.count=0
        self.db=sqlite3.connect(self.root/'capacity-index.sqlite')
        self.db.execute('PRAGMA journal_mode=DELETE');self.db.execute('PRAGMA cache_size=-32768')
        self.db.execute('CREATE TABLE objects(name TEXT PRIMARY KEY,logical INTEGER,encoded INTEGER,allocated INTEGER) WITHOUT ROWID')
        self.db.execute('CREATE TABLE entries(name TEXT PRIMARY KEY,row TEXT,key_bytes INTEGER,row_bytes INTEGER) WITHOUT ROWID')
        self.manifest=None

    def allocated(self,size):return ((size+self.unit-1)//self.unit)*self.unit

    def object(self,key,logical,encoded_bytes):
        old=self.db.execute('SELECT logical,encoded FROM objects WHERE name=?',(key,)).fetchone()
        if old is not None:
            if old!=(logical,encoded_bytes):raise ValueError('conflicting measured object identity')
            return
        self.db.execute('INSERT INTO objects VALUES(?,?,?,?)',(key,logical,encoded_bytes,self.allocated(encoded_bytes)))

    def row(self,key,value):
        name(key);raw=encoded(value)
        self.db.execute('INSERT INTO entries VALUES(?,?,?,?)',(key,raw.decode(),len(encoded(key)),len(raw)))
        self.count+=1
        if self.count>MAX_ENTRIES:raise ValueError('capacity stream exceeds supported entry count')
        if self.count%4096==0:
            self.db.commit();save(self.root/'progress.private.json',{'entries':self.count,'seconds':time.monotonic()-self.started})

    def consume(self,stream):
        with tarfile.open(fileobj=stream,mode='r|') as tar:
            for member in tar:
                tar.members.clear()
                if member.name=='payload/manifest.json':
                    if self.manifest is not None or not member.isfile() or member.size>32*1024**2:
                        raise ValueError('invalid transport manifest')
                    self.manifest=json.load(tar.extractfile(member));continue
                key=member.name.lstrip('/');row=metadata(member)
                if member.isdir():row['kind']='directory'
                elif member.issym():row.update(kind='symlink',target=member.linkname)
                elif member.islnk():row.update(kind='hardlink',target=member.linkname.lstrip('/'))
                elif member.isfile():
                    checksum=hashlib.sha256();size=0;chunks=[]
                    with tar.extractfile(member) as payload:
                        while block:=payload.read(CHUNK_BYTES):
                            checksum.update(block);size+=len(block);chunk=hashlib.sha256(block).hexdigest()
                            old=self.db.execute('SELECT logical FROM objects WHERE name=?',('chunk-'+chunk,)).fetchone()
                            if old is None:self.object('chunk-'+chunk,len(block),len(zlib.compress(block,1)))
                            elif old[0]!=len(block):raise ValueError('chunk identity changed')
                            chunks.append({'sha256':chunk,'bytes':len(block)})
                    if size!=member.size:raise ValueError('truncated measured file')
                    h=checksum.hexdigest();layout=encoded({'encoding':CHUNKED,'sha256':h,'bytes':size,'chunks':chunks})
                    self.object(h,size,len(layout));row.update(kind='file',bytes=size,sha256=h)
                else:raise ValueError('unapproved measured special member')
                self.row(key,row)
        # Drain the final tar padding so the source writer cannot remain stuck.
        while stream.read(1024**2):pass
        if self.manifest is None:raise ValueError('missing capture transport manifest')
        for raw,snapshot in self.manifest.get('sqlite_snapshots',{}).items():
            old='payload/'+snapshot['path'];key=raw.lstrip('/')
            row=self.db.execute('SELECT row FROM entries WHERE name=?',(old,)).fetchone()
            if row is None:raise ValueError('missing measured SQLite payload')
            value=json.loads(row[0])
            if value['sha256']!=snapshot['sha256']:raise ValueError('snapshot stream hash mismatch')
            self.db.execute('DELETE FROM entries WHERE name=?',(old,));self.count-=1;self.row(key,value)
        self.db.commit()

    def summary(self):
        # Complete canonical hardlink metadata exactly as the backup index does.
        # Keep only one row/chain in memory; the archive can order aliases first.
        for key,raw in self.db.execute('SELECT name,row FROM entries'):
            row=json.loads(raw)
            if row['kind']!='hardlink':continue
            target=row['target'];seen={key}
            while True:
                if target in seen:raise ValueError('measured hardlink cycle')
                seen.add(target)
                found=self.db.execute('SELECT row FROM entries WHERE name=?',(target,)).fetchone()
                if found is None:raise ValueError('missing measured hardlink target')
                original=json.loads(found[0])
                if original['kind']!='hardlink':break
                target=original['target']
            if original['kind']!='file':raise ValueError('measured hardlink target is not regular')
            row.update(target=target,sha256=original['sha256'],bytes=original['bytes'],xattrs=original['xattrs'])
            encoded_row=encoded(row)
            self.db.execute('UPDATE entries SET row=?,row_bytes=? WHERE name=?',(encoded_row.decode(),len(encoded_row),key))
        self.db.commit()
        row_bytes=self.db.execute('SELECT sum(key_bytes+1+row_bytes+1) FROM entries').fetchone()[0] or 0
        entries_bytes=2+row_bytes-(1 if self.count else 0)
        if entries_bytes>MAX_INDEX:raise ValueError('measured index exceeds metadata ceiling')
        objects,encoded_bytes,allocated=self.db.execute('SELECT count(*),coalesce(sum(encoded),0),coalesce(sum(allocated),0) FROM objects').fetchone()
        files=logical=restore=directories=hardlinks=maximum_file=0
        for raw, in self.db.execute('SELECT row FROM entries'):
            row=json.loads(raw)
            if row['kind']=='file':
                files+=1;logical+=row['bytes'];restore+=self.allocated(row['bytes'])
                maximum_file=max(maximum_file,row['bytes'])
            elif row['kind']=='directory':directories+=1
            elif row['kind']=='hardlink':hardlinks+=1
        return {'entries':self.count,'regular_files':files,'directories':directories,'hardlinks':hardlinks,
                'logical_regular_bytes':logical,'canonical_entry_table_bytes':entries_bytes,
                'unique_objects':objects,'encoded_object_bytes':encoded_bytes,
                'cluster_rounded_object_payload_upper_bound':allocated,
                'full_tree_regular_payload_allocation':restore,'allocation_unit':self.unit,
                'maximum_regular_file_bytes':maximum_file,
                'filesystem_metadata_and_growth_not_included':True,'backup_created':False}

    def measure(self,source):
        if not isinstance(source,StreamingArchive):raise ValueError('fixed streaming archive required')
        compressor=subprocess.Popen(['zstd','-T1','-3','-c'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        read_fd,write_fd=os.pipe();reader=os.fdopen(read_fd,'rb');writer=os.fdopen(write_fd,'wb')
        errors=[];compressed={'bytes':0,'sha256':None}
        class Tee:
            def write(self,data):compressor.stdin.write(data);writer.write(data);return len(data)
            def flush(self):compressor.stdin.flush();writer.flush()
        def produce():
            try:source.produce(Tee())
            except BaseException as error:errors.append(error)
            finally:
                for stream in (compressor.stdin,writer):
                    try:stream.close()
                    except OSError:pass
        def count():
            h=hashlib.sha256()
            try:
                while block:=compressor.stdout.read(1024**2):
                    compressed['bytes']+=len(block);h.update(block)
                    if compressed['bytes']>source.max_bytes:raise ValueError('measured archive exceeds hard limit')
                compressed['sha256']=h.hexdigest()
            except BaseException as error:errors.append(error);compressor.kill()
        producer=threading.Thread(target=produce,daemon=True);counter=threading.Thread(target=count,daemon=True)
        producer.start();counter.start()
        try:
            try:self.consume(reader)
            except BaseException:
                # A failed producer records its exception BEFORE closing the
                # pipe. EOF can otherwise hide it behind a missing manifest or
                # truncated TAR error. Do not replace a parser error with a
                # broken pipe caused later by our own reader cleanup.
                if errors:raise errors[0]
                raise
            producer.join(timeout=30);counter.join(timeout=30)
            if producer.is_alive() or counter.is_alive():raise ValueError('capacity producer did not finish')
            if errors:raise errors[0]
            if compressor.wait(timeout=30)!=0:raise ValueError('capacity compressor failed')
            value={**self.summary(),'compressed_archive_bytes':compressed['bytes'],
                   'compressed_archive_sha256':compressed['sha256'],'seconds':time.monotonic()-self.started,
                   'full_tar_stream_counted':True,'stream_retained':False}
            save(self.root/'stream-measurement.private.json',value);return value
        except BaseException as error:
            # Preserve private source/stage diagnostics even when the producer
            # never reaches the transport manifest. This is not a result seal.
            failure={'passed':False,'error_type':type(error).__name__,'error':str(error),
                     'traceback':traceback.format_exc(),'entries_observed':self.count,
                     'compressed_bytes_observed':compressed['bytes'],
                     'sqlite_diagnostic':getattr(error,'nightly_sqlite_diagnostic',None)}
            try:save(self.root/'stream-failure.private.json',failure)
            except Exception as secondary:
                error.add_note('Failure receipt could not be saved: '+type(secondary).__name__)
            raise
        finally:
            if compressor.poll() is None:compressor.kill()
            reader.close()
            # Broken pipes close the owned source producer after a parser error.
            for stream in (compressor.stdin,compressor.stdout,compressor.stderr):
                try:stream.close()
                except OSError:pass
            producer.join(timeout=30);counter.join(timeout=30);compressor.wait()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True);parser.add_argument('--config-sha256',required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--allocation-unit',type=int,required=True)
    parser.add_argument('--measure-full',action='store_true');args=parser.parse_args()
    if not args.measure_full:raise ValueError('explicit full-stream measurement required')
    from vk_nightly_job import checksum,validate
    from vk_nightly_capture_adapter import RegisteredWorkspace,run_capture
    from vk_candidate_direct_b import source_pins
    # Validate the packaged provenance receipt before opening a B job/watcher.
    source_pins()
    if checksum(args.config)!=args.config_sha256:raise ValueError('measurement configuration changed')
    config=json.loads(args.config.read_text());plan=json.loads(Path(config['plan_path']).read_text());validate(config,plan)
    if config.get('capacity_measurement_only') is not True or not config['wsl_root'].startswith('/mnt/b/vk-backups/vk-nightly-capacity-'):
        raise ValueError('fresh explicit measurement-only B namespace required')
    meter=StreamMeter(args.output,allocation_unit=args.allocation_unit)
    class Workspace(RegisteredWorkspace):
        def mirror(self,source):
            if not isinstance(source,StreamingArchive):return super().mirror(source)
            value=meter.measure(source)
            value.update(registered_input_bytes_excluding_archive=sum(x['bytes'] for x in self.sealed.values()),
                         registered_inputs=self.sealed,scope_sha256=config['scope_sha256'],
                         plan_identity=config['plan_identity'],no_publication_receipt_issued=True)
            save(meter.root/'capacity-result.private.json',value)
            raise MeasurementComplete('full stream measured; intentionally no backup publication')
    try:run_capture(config,plan,enroll_fresh=True,workspace_factory=Workspace)
    except MeasurementComplete:print(json.dumps({'passed':True,'capacity_measured':True,'backup_created':False,'report':str(meter.root/'capacity-result.private.json')}))
    else:raise ValueError('measurement unexpectedly reached publication')


if __name__=='__main__':main()
