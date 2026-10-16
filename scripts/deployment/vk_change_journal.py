#!/usr/bin/env python3
"""Read-only backup journal. Lost coverage invalidates every incremental child."""

import argparse
import ctypes
import json
import os
from pathlib import Path
import select
import socket
import struct
import threading
import time
import uuid

from vk_prep_common import identity, storage

MASK = 0x2 | 0x4 | 0x8 | 0x40 | 0x80 | 0x100 | 0x200 | 0x400 | 0x800
OVERFLOW, UNMOUNT, IGNORED, ISDIR = 0x4000, 0x2000, 0x8000, 0x40000000


def scope(plan):
    return {"sources": sorted(set(plan["sources"])),
            "excluded_rebuildable_directories": sorted(set(plan.get("excluded_rebuildable_directories", [])))}


class Journal:
    def __init__(self, plan):
        self.plan = scope(plan)
        self.instance = uuid.uuid4().hex
        self.lib = ctypes.CDLL(None, use_errno=True)
        self.lib.inotify_init1.argtypes = [ctypes.c_int]
        self.lib.inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
        self.fd = self.lib.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
        if self.fd < 0:
            raise OSError(ctypes.get_errno(), "inotify_init1")
        self.roots = {str(Path(path).resolve()) for path in self.plan["sources"]}
        self.excluded = {str(Path(path).resolve()) for path in self.plan["excluded_rebuildable_directories"]}
        self.watches, self.changed, self.events, self.errors = {}, {}, {}, []
        self.deleted_watches = set()
        self.seq, self.ready = 0, False
        self.lock = threading.RLock()

    def excluded_path(self, path):
        return str(Path(path).resolve()) in self.excluded

    def tree(self, root):
        for directory, dirs, _ in os.walk(root, followlinks=False):
            dirs[:] = [name for name in dirs if not self.excluded_path(Path(directory) / name)]
            with self.lock:
                wd = self.lib.inotify_add_watch(self.fd, os.fsencode(directory), MASK | 0x01000000)
                if wd < 0:
                    self.errors.append({"watch_failed": directory, "errno": ctypes.get_errno()})
                else:
                    self.watches[wd] = directory

    def event(self, wd, mask, name):
        with self.lock:
            if mask & (OVERFLOW | UNMOUNT):
                self.errors.append({"coverage_lost": mask, "at": time.time()})
                return
            directory = self.watches.get(wd)
            if directory is None:
                self.errors.append({"unknown_watch": wd, "mask": mask})
                return
            if mask & 0x400:
                parent_covered = str(Path(directory).parent) in self.watches.values()
                if directory not in self.roots and parent_covered:
                    self.deleted_watches.add(wd)
                else:
                    self.errors.append({"protected_root_deleted": directory})
            if mask & IGNORED and wd in self.deleted_watches:
                self.deleted_watches.remove(wd)
                self.watches.pop(wd, None)
                # DELETE_SELF recorded the tombstone; the parent covers recreation.
                return
            path = str(Path(directory) / name) if name else directory
            if self.excluded_path(path):
                return
            self.seq += 1
            self.changed[path] = self.seq
            bits = self.events.setdefault(path, {})
            for bit in range(32):
                flag = 1 << bit
                if mask & flag:
                    bits[flag] = self.seq
            if mask & 0x800:
                self.errors.append({"directory_moved": path})
            if mask & IGNORED:
                self.watches.pop(wd, None)
                self.errors.append({"watch_removed": path})
            if mask & ISDIR and mask & (0x100 | 0x80) and Path(path).is_dir():
                self.tree(path)

    def read(self):
        with self.lock:
            while True:
                try:
                    data = os.read(self.fd, 1024 * 1024)
                except BlockingIOError:
                    return
                offset = 0
                while offset < len(data):
                    wd, mask, cookie, size = struct.unpack_from("iIII", data, offset)
                    name = os.fsdecode(data[offset + 16:offset + 16 + size].split(b"\0")[0])
                    self.event(wd, mask, name)
                    offset += 16 + size

    def report(self, since=0):
        with self.lock:
            self.read()
            return {"ready": self.ready and not self.errors, "sequence": self.seq,
                    "instance": self.instance, "scope_sha256": identity(self.plan),
                    "watches": len(self.watches), "errors": list(self.errors),
                    "changed": [path for path, sequence in self.changed.items() if sequence > since],
                    "events": {path: sum(flag for flag, sequence in bits.items() if sequence > since)
                               for path, bits in self.events.items() if self.changed[path] > since}}

    def close(self):
        os.close(self.fd)


def request(endpoint, since=0):
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(120)
        client.connect(str(endpoint))
        client.sendall(json.dumps({"since": since}).encode())
        chunks = []
        while chunk := client.recv(1024 * 1024):
            chunks.append(chunk)
    return json.loads(b"".join(chunks))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--socket", required=True, type=Path)
    args = parser.parse_args()
    endpoint = storage(args.socket)
    endpoint.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if endpoint.exists():
        raise ValueError("Existing journal socket must not be replaced")
    journal = Journal(json.loads(args.plan.read_text()))
    server = socket.socket(socket.AF_UNIX)
    server.bind(str(endpoint))
    os.chmod(endpoint, 0o600)
    server.listen()

    def watch():
        while True:
            select.select([journal.fd], [], [], 1)
            journal.read()

    threading.Thread(target=watch, daemon=True).start()
    for root in sorted(journal.roots):
        if not Path(root).is_dir():
            journal.errors.append({"root_unavailable": root})
        else:
            journal.tree(root)
    journal.ready = True
    print(json.dumps({"watch_ready": journal.report()["ready"], "instance": journal.instance}), flush=True)
    while True:
        connection, _ = server.accept()
        with connection:
            value = json.loads(connection.recv(1024))
            connection.sendall(json.dumps(journal.report(int(value.get("since", 0)))).encode())


if __name__ == "__main__":
    main()
