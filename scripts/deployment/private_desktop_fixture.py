"""SSD-only test transport for the exact read/hash program; no network calls."""
import os
from pathlib import Path
import shutil
import sys
from unittest.mock import patch

from vk_prep_common import digest


class PrivateDesktop:
    def __init__(self, root):
        self.cwd = Path.cwd()
        os.chdir(root)
        self.transport = patch('vk_archive_store.SSH', [sys.executable, '-'])
        self.transport.start()
        self.directory = 'B:/vk-backups/private-fixture'

    def mirror(self, source):
        remote = Path(self.directory) / source.name
        remote.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, remote)
        return {'desktop_verified': True, 'name': source.name, 'sha256': digest(remote),
                'bytes': remote.stat().st_size, 'desktop_directory': self.directory}

    def close(self):
        self.transport.stop()
        os.chdir(self.cwd)
