"""Finite remote preparation of copied logs. Never opens live history or backups.

Only numeric input members are read; output is a bounded tar of content-addressed
objects and manifests. MCP independently verifies all output before adoption.
"""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import tarfile
import time
import uuid

import log_dedup as logs

MAX_BYTES = 512 * 1024**2
MIN_FREE = 35 * 1024**3


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for data in iter(lambda:f.read(1024**2),b''):h.update(data)
    return h.hexdigest()


def save(path,value):
    with Path(path).open('x',encoding='utf-8') as f:
        json.dump(value,f,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())


def member(archive,name,body):
    info=tarfile.TarInfo(name);info.size=len(body);info.mode=0o600
    archive.addfile(info,io.BytesIO(body))


def run(root,request_sha,*,minimum_free=MIN_FREE):
    root=Path(root).resolve();request_path=root/'request.json'
    if digest(request_path)!=request_sha:raise ValueError('Request checksum differs')
    request=json.loads(request_path.read_text(encoding='utf-8'))
    if str(uuid.UUID(request['job_id']))!=request['job_id']:raise ValueError('Invalid job ID')
    files=request['files'];total=sum(x['bytes']for x in files)
    if not 1<=len(files)<=64 or not 0<total<=MAX_BYTES:raise ValueError('Finite input bound exceeded')
    if [x['index']for x in files]!=list(range(len(files))):raise ValueError('Non-canonical file order')
    if digest(root/'input.tar')!=request['input_sha256']:raise ValueError('Input transfer checksum differs')
    if shutil.disk_usage(root).free<minimum_free+2*total:raise ValueError('Remote free-space admission refused')
    save(root/'STARTED.json',{'job_id':request['job_id'],'pid':os.getpid(),'at':time.time()})
    if os.name=='nt':
        import ctypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.GetCurrentProcess.restype=ctypes.c_void_p
        kernel.SetPriorityClass.argtypes=[ctypes.c_void_p,ctypes.c_uint]
        kernel.SetPriorityClass.restype=ctypes.c_int
        if not kernel.SetPriorityClass(kernel.GetCurrentProcess(),0x4000):
            save(root/'FAILURE.json',{'job_id':request['job_id'],'type':'BackgroundPriorityError',
                 'windows_error':ctypes.get_last_error(),'complete':False,'before_payload_processing':True})
            raise OSError('Cannot set own worker background priority')
    started=time.monotonic();last_check=started;objects=set();completed=[]
    try:
        with tarfile.open(root/'input.tar','r|') as incoming, tarfile.open(root/'output.partial.tar','w') as outgoing:
            for index,expected in enumerate(files):
                source=incoming.next()
                if source is None or not source.isfile() or source.name!=str(index)+'.bin' or source.size!=expected['bytes']:
                    raise ValueError('Input member differs from exact request')
                body=incoming.extractfile(source);h=hashlib.sha256();chunks=[];size=0
                for block in logs.chunks(body):
                    now=time.monotonic()
                    if now-started>3300:raise TimeoutError('Finite preparation deadline reached')
                    if now-last_check>=5:
                        if shutil.disk_usage(root).free<minimum_free:raise ValueError('Remote free-space floor reached')
                        last_check=now
                    h.update(block);size+=len(block);key=logs.sha(block)
                    chunks.append({'sha256':key,'bytes':len(block)})
                    if len(chunks)>logs.MAX_CHUNKS:raise ValueError('Manifest chunk bound exceeded')
                    if key not in objects:
                        compressed=bytearray(gzip.compress(block,compresslevel=6,mtime=0))
                        compressed[9]=request['gzip_os_byte']
                        member(outgoing,'objects/'+key+'.gz',bytes(compressed));objects.add(key)
                if size!=expected['bytes'] or h.hexdigest()!=expected['sha256']:
                    raise ValueError('Copied input body checksum differs')
                manifest={'version':1,'raw_bytes':size,'sha256':h.hexdigest(),'chunks':chunks}
                member(outgoing,'manifests/'+str(index)+'.jsonl',logs.encode(manifest))
                completed.append({'index':index,'bytes':size,'sha256':h.hexdigest()})
            if incoming.next() is not None:raise ValueError('Unexpected additional input member')
        with (root/'output.partial.tar').open('r+b') as f:os.fsync(f.fileno())
        os.replace(root/'output.partial.tar',root/'output.tar')
        result={'job_id':request['job_id'],'request_sha256':request_sha,'output_sha256':digest(root/'output.tar'),
            'files':completed,'objects':len(objects),'bytes':total,'seconds':time.monotonic()-started,
            'live_history_access':False,'complete':True}
        save(root/'RESULT.json',result);return result
    except BaseException as error:
        save(root/'FAILURE.json',{'job_id':request['job_id'],'type':type(error).__name__,
            'complete':False,'seconds':time.monotonic()-started})
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True);parser.add_argument('--request-sha256',required=True)
    args=parser.parse_args();print(json.dumps(run(args.root,args.request_sha256),sort_keys=True))
