"""Shared preparation helpers. No service lifecycle or production-state writes."""

import contextlib
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + str(os.getpid()) + ".new")
    with temporary.open("x", encoding="utf-8") as stream:
        os.chmod(temporary, 0o600)
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def storage(path):
    mount = Path("/mnt/vk-storage")
    subprocess.run(["mountpoint", "-q", str(mount)], check=True)
    path = Path(path).resolve()
    if not path.is_relative_to(mount) or path == mount:
        raise ValueError("Preparation payloads must be below mounted /mnt/vk-storage")
    return path


@contextlib.contextmanager
def measured(timings, name):
    start = time.monotonic()
    try:
        yield
    finally:
        timings[name] = time.monotonic() - start


def file_identity(path):
    path = Path(path)
    try:
        info = path.stat()
    except FileNotFoundError:
        return None
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]
