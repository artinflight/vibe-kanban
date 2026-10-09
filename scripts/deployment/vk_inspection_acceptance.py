"""Unprivileged read-only installed acceptance; no deletion/cutover/adoption.

Only synthetic managed artifacts/private acceptance lease/socket are created.
They are retained as evidence. Historical bytes are hashed as UID1000 BEFORE
root inspection. Root is invoked only through the two unchanged fixed commands.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import uuid

import vk_retirement_preflight as boundary
import vk_historical_archive_preflight as historical
from vk_candidate_owner import PreparationLease, PreparationStatus

ANCHOR = Path('/mnt/vk-storage/vk-process-inspection-managed-v1')
PLAN_HEAD = '29af1c33e029bc1fe9ef9467fd51a03eb586105d'
PLAN_SHA = 'a17d7f29b4b47c25811e8bf3d992f09ecd5084812d666dc761fbf4afff8a5357'


class Fence:
    def __init__(self): self.sealed = False
    def seal(self): self.sealed = True; return True
    def verify(self): return self.sealed


def identity(path):
    info = path.stat(follow_symlinks=False)
    return {key: getattr(info, 'st_' + key) for key in historical.IDENTITY}


def run(profile, installation):
    boundary.require(profile in ('managed', 'historical'))
    boundary.require(os.geteuid() == os.getuid() == 1000 and os.getgid() == 1000)
    boundary.require(os.path.ismount('/mnt/vk-storage'))
    boundary.require(installation['approved_plan_head'] == PLAN_HEAD and installation['plan_sha256'] == PLAN_SHA
                     and installation['adoption_enabled'] is False)
    fd = os.open(ANCHOR, os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        anchor = os.fstat(fd)
        boundary.require(anchor.st_uid == 0 and stat.S_IMODE(anchor.st_mode) == 0o755
                         and [anchor.st_dev, anchor.st_ino] == installation['anchor_identity'])
        release = uuid.uuid4().hex
        for kind in ('control', 'objects'):
            parent = os.open(kind, os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            try:
                info = os.fstat(parent)
                boundary.require(info.st_uid == 1000 and stat.S_IMODE(info.st_mode) == 0o700)
                os.mkdir(release, 0o700, dir_fd=parent)
            finally:
                os.close(parent)
    finally:
        os.close(fd)
    control = ANCHOR / 'control' / release
    lease_path = control / 'owner.lease'
    with lease_path.open('xb') as stream: pass
    lease_path.chmod(0o600)
    hashes = installation['installed_files']
    source = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()  # prep only
    root_binding = boundary.digest(installation['anchor_identity'])
    if profile == 'historical':
        manifest = historical.manifest_for(identity(lease_path), source_sha256=source,
                        root_binding=root_binding, release_id=release)
        installed = {'code_sha256': hashes['/usr/local/libexec/vk-historical-archive-inspection-v1.py'],
                     'policy_sha256': hashes['/etc/vibe-kanban/historical-archive-inspection-v1.json'],
                     'library_sha256': hashes['/usr/local/libexec/vk-process-inspection-v1.py']}
        check = historical.at_archive_boundary
    else:
        artifact = ANCHOR / 'objects' / release / 'acceptance-artifact'
        with artifact.open('xb') as stream: stream.write(b'synthetic inspection acceptance only\n')
        artifact.chmod(0o600)
        manifest = {'scope_id': 'managed-artifacts-v1', 'release_id': release, 'source_sha256': source,
                    'root_binding': root_binding, 'backup_manifest_sha256': '0' * 64,
                    'lease': identity(lease_path), 'targets': [{'name': artifact.name, 'identity': identity(artifact),
                    'sha256': hashlib.sha256(artifact.read_bytes()).hexdigest(), 'guard_held': False}]}
        installed = {'code_sha256': hashes['/usr/local/libexec/vk-process-inspection-v1.py'],
                     'policy_sha256': hashes['/etc/vibe-kanban/process-inspection-v1.json']}
        check = boundary.at_held_boundary
    status = boundary.BoundaryStatus(lambda: {'source': source, 'root_binding': root_binding,
                        'manifest_sha256': manifest['backup_manifest_sha256']})
    info = lease_path.stat()
    with PreparationLease(lease_path, (info.st_dev, info.st_ino)) as lease:
        parent = os.open(control, os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW)
        server = PreparationStatus(Path(f'/proc/self/fd/{parent}/owner.sock'), lease, status)
        try:
            # Synthetic gate values mean inspection-only, NEVER retirement approval.
            result = check(lease=lease, server=server, status=status, manifest=manifest,
                           scope_path=str(ANCHOR), installation=installed, prepare=lambda: None,
                           verify_gates=lambda: {key: True for key in boundary.GATES},
                           orchestration_fence=Fence(), consume=None, adoption_enabled=True)
        finally:
            server.close()  # ephemeral own endpoint only; retained artifacts/lease
            os.close(parent)
    result.update(acceptance_only=True, action_authorized=False, operational_adoption_changed=False)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', choices=('managed', 'historical'), required=True)
    parser.add_argument('--installation-json', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run(args.profile, json.loads(args.installation_json.read_bytes()))
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as error:
        print(json.dumps({'acceptance_only': True, 'passed': False, 'error_type': type(error).__name__,
                          'action_authorized': False, 'operational_adoption_changed': False}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
