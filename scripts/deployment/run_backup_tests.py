#!/usr/bin/env python3
"""Run the backup integration fixtures without production/remote operations."""
import os
from pathlib import Path
import sys
import unittest


def main():
    mount = Path('/mnt/vk-storage')
    temporary = Path(os.environ['TMPDIR']).resolve()
    if not mount.is_mount() or temporary == mount or not temporary.is_relative_to(mount) or not temporary.is_dir():
        raise ValueError('Existing task-local TMPDIR on mounted /mnt/vk-storage required')
    base = str(Path(__file__).parent)
    loader = unittest.TestLoader()
    suites = [loader.discover(base, pattern=pattern) for pattern in (
        'test_vk_nightly*.py', 'test_vk_history*.py', 'test_vk_backup_content_audit.py')]
    suites += [loader.loadTestsFromName(module) for module in (
        'test_vk_rolling_backup', 'test_vk_desktop_backups', 'test_vk_archive_stream',
        'test_vk_b_disk_capture', 'test_vk_b_disk_snapshot',
        'test_vk_candidate_direct_b', 'test_vk_candidate_scaffold')]
    return 0 if unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(suites)).wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
