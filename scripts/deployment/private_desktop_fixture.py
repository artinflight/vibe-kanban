"""SSD-only test transport for the exact read/hash program; no network calls."""
import os
from pathlib import Path
import shutil
import sys
from unittest.mock import patch

from vk_prep_common import digest


def private_restore_room(root):
    """Unit-test capacity substitute, limited to <=8 MiB in its owned fixture.

Production restore_room and its 2 GiB floor stay unchanged. This host currently
cannot run that production path; never confuse tiny simulated-capacity tests
with an actual full-state restore or deployment clearance.
"""
    root = root.resolve()
    def check(destination, additional=0):
        destination = Path(destination).resolve()
        if not destination.is_relative_to(root) or destination == root:
            raise ValueError('Fixture capacity substitute escaped its private root')
        total = sum(p.stat().st_size for p in destination.rglob('*') if p.is_file() and not p.is_symlink())
        if total + additional > 8 * 1024**2 or shutil.disk_usage(root).free < 32 * 1024**2:
            raise ValueError('Private unit fixture exceeds its measured capacity allowance')
    return patch('vk_rolling_backup.restore_room', side_effect=check)


class PrivateDesktop:
    def __init__(self, root):
        self.cwd = Path.cwd()
        os.chdir(root)
        self.transport = patch('vk_archive_store.SSH', [sys.executable, '-'])
        self.transport.start()
        self.capacity = private_restore_room(root)
        self.capacity.start()
        self.directory = 'B:/vk-backups/private-fixture'

    def mirror(self, source):
        from vk_archive_stream import StreamingArchive, RECEIVER
        if isinstance(source, StreamingArchive):
            return source.deliver(self.directory, [sys.executable, '-c', RECEIVER])
        remote = Path(self.directory) / source.name
        remote.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, remote)
        return {'desktop_verified': True, 'name': source.name, 'sha256': digest(remote),
                'bytes': remote.stat().st_size, 'desktop_directory': self.directory}

    def close(self):
        self.capacity.stop()
        self.transport.stop()
        os.chdir(self.cwd)
