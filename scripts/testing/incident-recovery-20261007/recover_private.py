"""Authenticate B-only streams and recover affected files into private scratch.

This has no production placement path and never starts an executable.
"""
from contextlib import contextmanager
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
BACKUP = Path('/mnt/vk-storage/vk-runtime-backup-20261007')
sys.path.insert(0, '/mnt/vk-storage/vk-desktop-provider-20261007/recovery-package-49cf82d60/tools')
from vk_archive_store import Archive, configure_transport, reference
from vk_prep_common import save, digest
from vk_rolling_backup import restore_chain
from vk_staged_recovery import HashReader


def selected(name):
    return (name.startswith(('mnt/vk-storage/worktrees/', 'home/mcp/code/worktrees/'))
            or '/.git/worktrees/' in name)


def main():
    assert os.path.ismount('/mnt/vk-storage')
    configure_transport('10.0.0.109', '100.70.23.123')
    full = json.loads((BACKUP / 'full-result.json').read_text())
    head = json.loads((BACKUP / 'delta-result.json').read_text())
    records = {}
    for result in (full, head):
        archive = Archive(reference(result))
        records[archive.key] = {'sha256': archive.sha256, 'verification': archive.verify(),
            'manifest': json.loads((Path(result['folder']) / 'payload/manifest.json').read_text())}
    save(ROOT / 'fresh-B-verification.json', records)
    original = Archive.contents
    expected, streamed = {}, []

    @contextmanager
    def filtered(archive):
        receipt = records[archive.key]
        assert receipt['sha256'] == archive.sha256
        manifest = copy.deepcopy(receipt['manifest'])
        manifest['sqlite_snapshots'] = {p: row for p, row in manifest['sqlite_snapshots'].items()
                                        if selected(p.lstrip('/'))}
        manifest['absent_paths'] = [p for p in manifest['absent_paths'] if selected(p.lstrip('/'))]
        payloads = {'payload/' + row['path'] for row in manifest['sqlite_snapshots'].values()}
        hashes, modes, links = {}, {}, {}
        found = False
        body = json.dumps(manifest).encode()
        with original(archive) as tar:
            class Selection:
                def __iter__(self):
                    nonlocal found
                    for member in tar:
                        if member.name == 'payload/manifest.json':
                            assert json.load(tar.extractfile(member)) == receipt['manifest']
                            found = True
                            proxy = copy.copy(member)
                            proxy.size = len(body)
                            yield proxy
                        elif member.name in payloads:
                            yield member
                        elif selected(member.name):
                            if member.isfile():
                                hashes[member.name] = hashlib.sha256()
                                modes[member.name] = member.mode
                            elif member.issym() or member.islnk():
                                links[member.name] = {'link': member.linkname, 'hardlink': member.islnk()}
                            yield member

                def extractfile(self, member):
                    if member.name == 'payload/manifest.json':
                        return io.BytesIO(body)
                    stream = tar.extractfile(member)
                    return HashReader(stream, hashes[member.name]) if member.name in hashes else stream
            yield Selection()
        assert found
        for name, checksum in hashes.items():
            expected[name] = {'sha256': checksum.hexdigest(), 'mode': modes[name]}
        for name in links:
            expected.pop(name, None)
        absent = {p.lstrip('/').rstrip('/') for p in manifest['absent_paths']}
        for name in list(expected):
            if any('/'.join(name.split('/')[:i]) in absent for i in range(1, len(name.split('/')) + 1)):
                del expected[name]
        for name, row in manifest['sqlite_snapshots'].items():
            expected[name.lstrip('/')] = {'sha256': row['sha256'], 'sqlite': True}
        streamed.append({'archive': archive.key, 'sha256': archive.sha256, 'fully_verified': True})

    destination = BACKUP / 'backups/incident-private-recovery-2316'
    with patch.object(Archive, 'manifest', lambda a: copy.deepcopy(records[a.key]['manifest'])), \
            patch.object(Archive, 'contents', filtered):
        result = restore_chain(head, destination, desktop_only=True, retire_verified_snapshots=True)
    for name, row in expected.items():
        path = destination / 'files' / name
        assert digest(path) == row['sha256'], name
        if 'mode' in row:
            assert path.stat().st_mode & 0o7777 == row['mode'], name
    save(ROOT / 'private-recovery-result.json', {'passed': True, 'restore': result,
        'files': expected, 'complete_streams': streamed, 'production_placement': False,
        'post_backup_edits_recovered': False})
    print(json.dumps({'private_recovery_passed': True, 'verified_files': len(expected),
                      'destination': str(destination), 'production_placement': False}))


if __name__ == '__main__':
    main()
