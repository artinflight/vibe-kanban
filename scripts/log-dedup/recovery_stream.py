"""Bounded file interface over Nightly's already-held normal recovery reader.

The owner supplies the validated HeldRecoverySet and retains its provider/index
leases and native B admission throughout. No capture, transport, lease acquisition
or state changes happen here. A location string is never admission authority.
"""
from contextlib import contextmanager
import hashlib
from pathlib import PurePosixPath
import re

import log_dedup as logs


MAX_READ = 1024 * 1024
BASE = rf'[0-9a-f]{{2}}/{logs.UUID}/processes/'
MEMBER = re.compile(BASE + rf'(?:{logs.UUID}\.(?:jsonl|capture\.json|recovered-final\.json)|\.log-objects/[0-9a-f]{{64}}\.gz)')


class Body:
    def __init__(self, blocks, size, digest, guard):
        self.blocks = iter(blocks)
        self.remaining = size
        self.expected = digest
        self.guard = guard
        self.pending = memoryview(b'')
        self.digest = hashlib.sha256()
        self.eof = False

    def read(self, size):
        if type(size) is not int or not 1 <= size <= MAX_READ:
            raise logs.ArchiveError('Finite recovery read of at most 1 MiB required')
        self.guard()
        output = bytearray()
        while len(output) < size:
            if self.pending:
                count = min(size - len(output), len(self.pending))
                output.extend(self.pending[:count])
                self.pending = self.pending[count:]
                continue
            if self.eof:
                break
            try:
                block = next(self.blocks)
            except StopIteration:
                if self.remaining or self.digest.hexdigest() != self.expected:
                    raise logs.ArchiveError('Normal recovery body hash/length mismatch')
                self.eof = True
                break
            if not isinstance(block, bytes) or not 1 <= len(block) <= MAX_READ:
                raise logs.ArchiveError('Normal recovery block exceeds bounded byte protocol')
            self.remaining -= len(block)
            if self.remaining < 0:
                raise logs.ArchiveError('Normal recovery body exceeds expected length')
            self.digest.update(block)
            self.pending = memoryview(block)
        self.guard()
        return bytes(output)

    def finish(self):
        if not self.eof or self.pending:
            raise logs.ArchiveError('Normal recovery body was not consumed to verified EOF')
        self.guard()

    def close(self):
        close = getattr(self.blocks, 'close', None)
        if close:
            close()


class NormalRecovery:
    """Bridge handle.index.entry(name), handle.blocks(name), handle.check().

    source_namespace is the original absolute sessions-root name in the accepted
    normal B map, not a local fallback. The owner pins its concrete handle/guard.
    """
    def __init__(self, handle, *, source_namespace, location, guard):
        path = PurePosixPath(source_namespace)
        if (not source_namespace.startswith('/') or source_namespace.startswith('//')
                or str(path) != source_namespace or '..' in path.parts
                or source_namespace == '/'):
            raise logs.ArchiveError('Exact absolute source namespace required')
        if not location.startswith('desktop:B:/vk-backups/') or not callable(guard):
            raise logs.ArchiveError('Admitted canonical B context required')
        self.handle, self.guard = handle, guard
        self.prefix = source_namespace[1:] + '/'
        self.location = location

    def check(self):
        self.guard()
        self.handle.check()

    @contextmanager
    def open_member(self, relative, expected_sha256):
        match = MEMBER.fullmatch(relative)
        parts = relative.split('/')
        if not match or parts[0] != parts[1][:2] or not logs.valid_hash(expected_sha256):
            raise logs.ArchiveError('Exact session-local recovery reference required')
        self.check()
        name = self.prefix + relative
        row = self.handle.index.entry(name)
        if (row.get('kind') not in ('file', 'hardlink') or row.get('sha256') != expected_sha256
                or type(row.get('bytes')) is not int or row['bytes'] < 0):
            raise logs.ArchiveError('Normal B member differs from exact selected version')
        stream = Body(self.handle.blocks(name), row['bytes'], expected_sha256, self.check)
        try:
            yield stream
            stream.finish()
        finally:
            stream.close()
        self.check()

    def open_original(self, relative, expected_sha256):
        if '/.log-objects/' in relative:
            raise logs.ArchiveError('Original recovery requires a log or sidecar')
        return self.open_member(relative, expected_sha256)
