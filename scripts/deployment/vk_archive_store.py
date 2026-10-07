"""Receipt-bound Desktop archive reads; never materialize an archive on MCP."""
from contextlib import contextmanager
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile

from vk_prep_common import digest, storage


SSH = ["ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
       "-o", "StrictHostKeyChecking=yes", "-o", "ServerAliveInterval=15",
       "-o", "ServerAliveCountMax=3", "-o", "ControlMaster=no",
       "-o", "ControlPath=none", "desktop", "python", "-"]

LOCATORS = {}


def install_locators(results):
    """Bind retained, package-verified descriptors for legacy manifest parents."""
    additions = {}
    for result in results:
        ref = reference(result)
        if not ref.get('desktop_directory'):
            raise ValueError('Portable recovery needs an exact Desktop locator')
        Archive(ref, desktop_only=True)
        key = (ref['folder'], ref['archive'], ref['sha256'])
        if key in additions and additions[key] != ref or key in LOCATORS and LOCATORS[key] != ref:
            raise ValueError('Conflicting retained Desktop locator')
        additions[key] = ref
    LOCATORS.update(additions)


def reference(result):
    receipt = result["receipt"]
    if receipt.get("desktop_verified") is not True:
        raise ValueError("Backup receipt is unverified")
    ref = {"folder": result["folder"], "archive": result["archive"],
           "sha256": receipt["sha256"]}
    if receipt.get("desktop_directory"):
        ref.update(desktop_directory=receipt["desktop_directory"], bytes=receipt["bytes"])
    return ref


def remote_code(path, checksum, size, stream):
    # The path travels as Python data on stdin, never shell syntax. SSH retains
    # the existing verified host identity. This code opens the backup read-only.
    return "PATH,EXPECTED,SIZE,STREAM=" + repr((path, checksum, size, stream)) + "\n" + '''
import os,sys,json,hashlib
def signature(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
with open(PATH,'rb') as f:
 before=signature(os.fstat(f.fileno()))
 if before[2]!=SIZE:raise ValueError('Desktop archive size mismatch')
 h=hashlib.sha256()
 for b in iter(lambda:f.read(1048576),b''):
  h.update(b)
  if STREAM:sys.stdout.buffer.write(b)
 if h.hexdigest()!=EXPECTED:raise ValueError('Desktop archive checksum mismatch')
 if before!=signature(os.fstat(f.fileno())) or before!=signature(os.stat(PATH)):
  raise ValueError('Desktop archive changed during read')
 if STREAM:sys.stdout.buffer.flush()
 else:print(json.dumps({'sha256':h.hexdigest(),'bytes':SIZE,'remote':PATH}))
'''


class Archive:
    def __init__(self, ref, archive_directory=None, *, desktop_only=False):
        ref = dict(ref)
        name = ref["archive"]
        if (not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*\.tar\.zst", name)
                or not re.fullmatch(r"[0-9a-f]{64}", ref["sha256"])):
            raise ValueError("Invalid backup archive reference")
        self.path = storage(Path(ref["folder"]) / name)
        self.name, self.stem = name, Path(name).stem
        self.sha256 = ref["sha256"]
        self.remote = None
        if archive_directory:
            if desktop_only:
                raise ValueError("Desktop-only mode conflicts with local archive override")
            self.path = storage(Path(archive_directory) / name)
        else:
            if not ref.get('desktop_directory'):
                ref = LOCATORS.get((ref['folder'], ref['archive'], ref['sha256']), ref)
            if not ref.get("desktop_directory"):
                # Legacy archive manifests lack the remote locator. Preserve the
                # original descriptors and require their exact archive identity.
                descriptor = Path(ref["folder"]) / (name + ".result.json")
                if not descriptor.is_file():
                    descriptor = Path(ref["folder"]) / "result.json"
                if descriptor.is_file():
                    result = json.loads(descriptor.read_text())
                    candidate = reference(result)
                    if any(candidate[k] != ref[k] for k in ("folder", "archive", "sha256")):
                        raise ValueError("Backup locator descriptor identity mismatch")
                    ref = candidate
            if ref.get("desktop_directory"):
                directory = ref["desktop_directory"]
                if (not re.fullmatch(r"B:/vk-backups/[A-Za-z0-9_./-]+", directory)
                        or ".." in PurePosixPath(directory).parts
                        or type(ref.get("bytes")) is not int or ref["bytes"] <= 0):
                    raise ValueError("Invalid Desktop backup locator")
                self.remote = directory.rstrip("/") + "/" + name
                self.size = ref["bytes"]
        if desktop_only and not self.remote:
            raise ValueError("No verified Desktop locator for backup")
        self.key = self.remote or str(self.path)

    def verify(self):
        if not self.remote:
            if digest(self.path) != self.sha256:
                raise ValueError("Backup chain checksum mismatch; parent unverified")
            return {"sha256": self.sha256, "bytes": self.path.stat().st_size,
                    "local": str(self.path)}
        result = subprocess.run(SSH, input=remote_code(self.remote, self.sha256, self.size, False),
                                text=True, capture_output=True, timeout=1800)
        if result.returncode:
            raise ValueError("Desktop backup unavailable or checksum verification failed: " + self.remote)
        receipt = json.loads(result.stdout)
        if receipt != {"sha256": self.sha256, "bytes": self.size, "remote": self.remote}:
            raise ValueError("Unexpected Desktop verification receipt")
        return receipt

    @contextmanager
    def contents(self):
        """Yield tar members, then require the complete compressed stream hash.

        Consumers may write only private scratch output until the context exits
        successfully. Partial reads are drained, so a header alone cannot pass.
        """
        reader = None
        decompressor = None
        try:
            if self.remote:
                reader = subprocess.Popen(SSH, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                          stderr=subprocess.DEVNULL)
                reader.stdin.write(remote_code(self.remote, self.sha256, self.size, True).encode())
                reader.stdin.close()
                decompressor = subprocess.Popen(["zstd", "-dc"], stdin=reader.stdout,
                                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                reader.stdout.close()
            else:
                self.verify()
                decompressor = subprocess.Popen(["zstd", "-dc", str(self.path)],
                                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            with tarfile.open(fileobj=decompressor.stdout, mode="r|") as tar:
                yield tar
            while decompressor.stdout.read(1024 * 1024):
                pass
            if decompressor.wait(timeout=60):
                raise ValueError("Backup decompression failed")
            if reader is not None and reader.wait(timeout=60):
                raise ValueError("Desktop archive read/hash failed; scratch restore is unverified")
        finally:
            for process in (decompressor, reader):
                if process is not None:
                    if process.poll() is None:
                        process.kill()
                    process.wait()
                    for handle in (process.stdin, process.stdout, process.stderr):
                        if handle is not None and not handle.closed:
                            handle.close()

    def manifest(self):
        found = None
        with self.contents() as tar:
            for member in tar:
                if member.name == "payload/manifest.json":
                    if found is not None or not member.isfile() or member.size > 32 * 1024 * 1024:
                        raise ValueError("Invalid or duplicate backup manifest")
                    found = json.load(tar.extractfile(member))
        if found is None:
            raise ValueError("Missing backup manifest")
        return found


def chain(result, archive_directory=None, *, desktop_only=False):
    current = reference(result)
    archives, seen = [], set()
    while current:
        archive = Archive(current, archive_directory, desktop_only=desktop_only)
        if archive.key in seen:
            raise ValueError("Backup parent cycle")
        seen.add(archive.key)
        manifest = archive.manifest()
        if (manifest.get("scope_sha256") != result["scope_sha256"]
                or manifest.get("plan_sha256") != result["plan_sha256"]):
            raise ValueError("Backup chain scope or plan mismatch")
        archives.append(archive)
        current = manifest["parent"]
    return archives
