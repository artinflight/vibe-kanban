"""MCP owns source snapshots, verifies remote output, and alone seals archives."""
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import tarfile
import uuid

import log_dedup as logs
from checkpoint_control import atomic, read, require
from remote_pack import digest, MAX_BYTES


class HashingReader:
    def __init__(self,stream):self.stream=stream;self.hash=hashlib.sha256()
    def read(self,size=-1):
        block=self.stream.read(size);self.hash.update(block);return block


def snapshot(source_root,names,workspace,folder,guard):
    """Read stable copied inputs only; no source mutation or source-log lease claim."""
    root=Path(source_root);folder=Path(folder);folder.mkdir(mode=0o700)
    files=[];expected=[];total=0;job_id=str(uuid.uuid4())
    require(1<=len(names)<=64 and len(set(names))==len(names),'bounded unique selection required')
    with tarfile.open(folder/'input.tar','w') as output:
        for index,name in enumerate(names):
            guard();source=logs.safe_path(root,name);before=logs.regular(source)
            companions=logs.sidecars(source)
            capture=[raw for ext,raw,_ in companions if ext=='capture.json']
            require(len(capture)==1 and json.loads(capture[0]).get('capture_state')=='closed','closed capture required')
            total+=before.st_size;require(total<=MAX_BYTES,'remote input bound exceeded')
            with source.open('rb') as body:
                require(logs.version(os.fstat(body.fileno()))==logs.version(before),'source changed on open')
                require(body.read(len(logs.MAGIC))!=logs.MAGIC,'already archived source cannot be prepared again')
                body.seek(0);reader=HashingReader(body)
                info=tarfile.TarInfo(str(index)+'.bin');info.size=before.st_size;info.mode=0o600
                output.addfile(info,reader)
                require(logs.version(os.fstat(body.fileno()))==logs.version(before),'source changed while copied')
            require(logs.version(logs.regular(source))==logs.version(before),'source changed after copy')
            require(logs.sidecars(source)==companions,'source sidecar changed while copied')
            expected.append({'index':index,'bytes':before.st_size,'sha256':reader.hash.hexdigest()})
            files.append({'path':name,'identity':logs.version(before),'allocated_bytes':before.st_blocks*512,
                'sha256':reader.hash.hexdigest(),'raw_bytes':before.st_size,
                'sidecars':[{'extension':ext,'sha256':logs.sha(raw),'identity':identity}for ext,raw,identity in companions]})
    with (folder/'input.tar').open('rb') as f:os.fsync(f.fileno())
    request={'job_id':job_id,'files':expected,'input_sha256':digest(folder/'input.tar'),
             'gzip_os_byte':gzip.compress(b'',mtime=0)[9]}
    atomic(folder/'request.json',request)
    evidence={'job_id':job_id,'workspace':workspace,'source_root':str(root),'files':files,
              'request_sha256':digest(folder/'request.json')}
    atomic(folder/'SNAPSHOT.private.json',evidence);return evidence


def validate_snapshot(evidence,guard):
    root=Path(evidence['source_root'])
    for entry in evidence['files']:
        guard();source=logs.safe_path(root,entry['path'])
        require(logs.version(logs.regular(source))==entry['identity'],'prepared source identity changed')
        actual=[{'extension':ext,'sha256':logs.sha(raw),'identity':identity}for ext,raw,identity in logs.sidecars(source)]
        require(actual==entry['sidecars'],'prepared source sidecars changed')


def import_archive(folder,destination,guard):
    """Treat remote output as untrusted; check all bytes and exact member names."""
    folder=Path(folder);destination=Path(destination);evidence=read(folder/'SNAPSHOT.private.json',8*1024**2)
    result=json.loads((folder/'RESULT.json').read_bytes());request=json.loads((folder/'request.json').read_bytes())
    require(result['complete'] and result['job_id']==evidence['job_id']==request['job_id']
            and result['request_sha256']==evidence['request_sha256']==digest(folder/'request.json')
            and result['files']==request['files'],'remote result does not match copied sources')
    validate_snapshot(evidence,guard)
    require(digest(folder/'output.tar')==result['output_sha256'],'remote output transfer checksum differs')
    require((folder/'output.tar').stat().st_size<=MAX_BYTES*2,'remote output bound exceeded')
    destination=logs.create_destination(destination,Path(evidence['source_root']))
    cache=destination/'.remote-objects';cache.mkdir(mode=0o700)
    seen=set();manifests={};objects={};total=0
    with tarfile.open(folder/'output.tar','r|') as archive:
        for member in archive:
            require(member.isfile() and member.name not in seen,'duplicate or nonregular remote member')
            seen.add(member.name);total+=member.size
            require(total<=MAX_BYTES*2,'remote members exceed total bound')
            obj=re.fullmatch(r'objects/([0-9a-f]{64})\.gz',member.name)
            manifest=re.fullmatch(r'manifests/([0-9]+)\.jsonl',member.name)
            require(obj is not None or manifest is not None,'unexpected remote member')
            limit=logs.MAX_CHUNK+1024 if obj else logs.MAX_MANIFEST+len(logs.MAGIC)
            require(0<member.size<=limit,'remote member bound exceeded')
            data=archive.extractfile(member).read(limit+1);require(len(data)==member.size,'truncated remote member')
            if obj:
                with gzip.GzipFile(fileobj=io.BytesIO(data)) as zipped:raw=zipped.read(logs.MAX_CHUNK+1)
                require(0<len(raw)<=logs.MAX_CHUNK and logs.sha(raw)==obj[1],'invalid remote object')
                logs.write_new(cache/(obj[1]+'.gz'),data);objects[obj[1]]=(len(raw),len(data))
            else:
                index=int(manifest[1]);require(0<=index<len(evidence['files']) and index not in manifests,'unexpected manifest index')
                path=destination/evidence['files'][index]['path'];path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                logs.write_new(path,data);manifests[index]=logs.load_manifest(path)
    require(len(objects)==result['objects'] and len(manifests)==len(evidence['files']),'incomplete remote archive')
    stores={};records=[];used=set()
    for index,entry in enumerate(evidence['files']):
        guard();target=destination/entry['path'];manifest=manifests[index];store=target.parent/'.log-objects'
        store.mkdir(exist_ok=True,mode=0o700);values=stores.setdefault(str(target.parent),{})
        require(manifest['sha256']==entry['sha256'] and manifest['raw_bytes']==entry['raw_bytes'],'remote manifest changed source bytes')
        for chunk in manifest['chunks']:
            key=chunk['sha256'];require(key in objects and objects[key][0]==chunk['bytes'],'missing remote chunk')
            used.add(key)
            if key in values:continue
            primary=Path(evidence['source_root'])/entry['path'];primary=primary.parent/'.log-objects'/(key+'.gz')
            selected=cache/(key+'.gz')
            if primary.exists() or primary.is_symlink():
                import reclaim
                reclaim.object_bytes(primary,chunk)  # Existing primary bytes remain authoritative.
                selected=primary
            before=logs.version(logs.regular(selected));body=selected.read_bytes()
            require(logs.version(logs.regular(selected))==before,'object changed during import')
            logs.write_new(store/(key+'.gz'),body);values[key]=[chunk['bytes'],len(body)]
        require(logs.reconstruct(target)['sha256']==entry['sha256'],'imported full history differs')
        source=logs.safe_path(Path(evidence['source_root']),entry['path']);companions=logs.sidecars(source)
        for extension,data,_ in companions:logs.write_new(target.with_suffix('.'+extension),data)
        record=logs.file_record(entry['path'],manifest,logs.regular(source),companions)
        require(all(record[key]==entry[key]for key in entry),'imported source metadata changed')
        records.append(record)
    require(used==set(objects),'remote archive contains unreferenced objects')
    validate_snapshot(evidence,guard)
    # Only exact new cache replicas created in this call are retired; durable copies
    # now exist inside the unsealed archive. No live source or old staging is touched.
    for key in objects:(cache/(key+'.gz')).unlink()
    cache.rmdir()
    plan=logs.measured_plan(Path(evidence['source_root']),records,stores)
    logs.sync_directories(destination)
    logs.write_new(destination/'receipt.json',json.dumps(plan,indent=2).encode()+b'\n')
    logs.sync_directories(destination)
    atomic(folder/'IMPORTED.private.json',{'job_id':evidence['job_id'],'archive':str(destination),
           'plan_sha256':logs.sha(json.dumps(plan,sort_keys=True,separators=(',',':')).encode()),'all_bodies_verified':True})
    return plan
