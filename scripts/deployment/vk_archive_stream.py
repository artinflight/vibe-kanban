"""Bounded tar/zstd -> existing Desktop SSH transport. No local archive file.

An archive is not an accepted backup until capture publishes its verified result.
Failed/uncertain transfers retain a uniquely named remote partial, never overwrite
another backup, and are never resumed by concatenating a newly generated stream.
"""
import base64
import hashlib
import json
import re
import select
import struct
import subprocess
import threading
from pathlib import PurePosixPath


CHUNK = 1024 * 1024
MAX_ARCHIVE_BYTES = 128 * 1024**3

# Also exercised as a subprocess by offline tests; Windows and Linux stdlib only.
RECEIVER = r'''
import hashlib,json,os,re,struct,sys,uuid
from pathlib import Path,PurePosixPath
inp=sys.stdin.buffer
def exact(n):
    chunks=[]
    while n:
        b=inp.read(n)
        if not b:raise ValueError('Interrupted archive stream')
        chunks.append(b);n-=len(b)
    return b''.join(chunks)
def packet():
    n=struct.unpack('!I',exact(4))[0]
    if n>16384:raise ValueError('Oversized control packet')
    return json.loads(exact(n))
def emit(value):
    print(json.dumps(value),flush=True)
def signature(st):return (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)
header=packet()
directory=header['directory'];name=header['name'];limit=header['limit']
if (not re.fullmatch(r'B:/vk-backups/[A-Za-z0-9_./-]+',directory)
    or '..' in PurePosixPath(directory).parts
    or not re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]*\.tar\.zst',name)
    or type(limit) is not int or limit<=0):raise ValueError('Invalid archive destination')
parent=Path(directory);parent.mkdir(parents=True,exist_ok=True)
if not parent.resolve().is_relative_to(Path('B:/vk-backups').resolve()):
    raise ValueError('Desktop destination escapes backup root')
final=parent/name
if final.exists():raise ValueError('Existing archive is immutable')
partial=parent/(name+'.partial-'+uuid.uuid4().hex)
with partial.open('xb') as out:
    emit({'ready':True})
    h=hashlib.sha256();size=0
    while True:
        n=struct.unpack('!I',exact(4))[0]
        if n==0:break
        if n>1048576 or size+n>limit:raise ValueError('Archive transfer bound exceeded')
        b=exact(n);out.write(b);h.update(b);size+=n
    expected=packet()
    if expected!={'bytes':size,'sha256':h.hexdigest()} or size==0:
        raise ValueError('Archive stream checksum mismatch')
    out.flush();os.fsync(out.fileno())
    written=signature(os.fstat(out.fileno()))
with partial.open('rb') as check:
    before=signature(os.fstat(check.fileno()));verify=hashlib.sha256()
    for b in iter(lambda:check.read(1048576),b''):verify.update(b)
    if (before!=written or signature(os.fstat(check.fileno()))!=before
        or signature(partial.stat())!=before or verify.hexdigest()!=expected['sha256']):
        raise ValueError('Desktop archive readback mismatch')
# Atomic no-replace publication. A collision never replaces a previous backup.
os.link(partial,final)
if signature(final.stat())!=written:raise ValueError('Desktop publication changed')
partial.unlink()  # Only this receiver's verified temporary name, not an old file.
emit({'desktop_verified':True,'name':name,'desktop_directory':directory,
      'bytes':size,'sha256':verify.hexdigest(),'direct_stream':True})
'''


def packet(stream, value):
    data = json.dumps(value, separators=(",", ":")).encode()
    if len(data) > 16384:
        raise ValueError("Oversized control packet")
    stream.write(struct.pack("!I", len(data)))
    stream.write(data)
    stream.flush()


def response(process, timeout=1800):
    if not select.select([process.stdout], [], [], timeout)[0]:
        raise ValueError("Desktop stream acknowledgement timed out")
    line = process.stdout.readline(16385)
    if not line.endswith(b"\n") or len(line) > 16384:
        raise ValueError("Desktop did not acknowledge the archive stream")
    return json.loads(line)


class StreamingArchive:
    """Explicit streaming callback argument; deliberately not path-like."""

    def __init__(self, folder, name, produce, max_bytes=MAX_ARCHIVE_BYTES):
        self.parent, self.name, self.produce = folder, name, produce
        self.max_bytes = max_bytes
        self.sha256 = None
        self.bytes = None

    def deliver(self, directory, command):
        if (not re.fullmatch(r"B:/vk-backups/[A-Za-z0-9_./-]+", directory)
                or ".." in PurePosixPath(directory).parts):
            raise ValueError("Use the established Desktop B:/vk-backups destination")
        remote = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL)
        compressor = None
        producer = None
        errors = []
        try:
            packet(remote.stdin, {"directory": directory, "name": self.name, "limit": self.max_bytes})
            if response(remote, timeout=60) != {"ready": True}:
                raise ValueError("Desktop stream destination is not ready")
            compressor = subprocess.Popen(["zstd", "-T2", "-3", "-c"], stdin=subprocess.PIPE,
                                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

            def produce():
                try:
                    self.produce(compressor.stdin)
                    compressor.stdin.close()
                except BaseException as error:
                    errors.append(error)
                    if compressor.poll() is None:
                        compressor.kill()
                    try:
                        compressor.stdin.close()
                    except OSError:
                        pass

            producer = threading.Thread(target=produce, name="backup-tar-producer", daemon=True)
            producer.start()
            checksum, size = hashlib.sha256(), 0
            while block := compressor.stdout.read(CHUNK):
                size += len(block)
                if size > self.max_bytes:
                    raise ValueError("Compressed archive exceeds the configured Desktop bound")
                checksum.update(block)
                remote.stdin.write(struct.pack("!I", len(block)))
                remote.stdin.write(block)
            producer.join(timeout=30)
            if producer.is_alive():
                raise ValueError("Archive producer did not finish")
            if errors:
                raise errors[0]
            if compressor.wait(timeout=30) != 0:
                raise ValueError("Archive compressor failed")
            self.sha256, self.bytes = checksum.hexdigest(), size
            remote.stdin.write(struct.pack("!I", 0))
            packet(remote.stdin, {"bytes": size, "sha256": self.sha256})
            remote.stdin.close()
            receipt = response(remote)
            if remote.wait(timeout=1800) != 0:
                raise ValueError("Desktop archive verification failed")
            expected = {"desktop_verified": True, "name": self.name, "desktop_directory": directory,
                        "bytes": size, "sha256": self.sha256, "direct_stream": True}
            if receipt != expected:
                raise ValueError("Desktop archive receipt does not match the produced stream")
            return receipt
        finally:
            # Only subprocesses created by this call; never services or other agents.
            for process in (compressor, remote):
                if process is not None and process.poll() is None:
                    process.kill()
            for process in (compressor, remote):
                if process is not None:
                    process.wait()
            if producer is not None:
                producer.join(timeout=30)
            for process in (compressor, remote):
                if process is not None:
                    for stream in (process.stdin, process.stdout):
                        if stream is not None and not stream.closed:
                            try:
                                stream.close()
                            except OSError:
                                pass


def receiver_command(options):
    code = base64.b64encode(RECEIVER.encode()).decode()
    # Program bytes are encoded; destination data travels in a bounded stdin packet.
    return ["ssh", "-T", *options, "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=3", "desktop",
            'python -c "import base64;exec(base64.b64decode(\'' + code + '\'))"']
