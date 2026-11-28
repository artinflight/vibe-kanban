"""Verified immutable shared Git recovery points, never shared-tree retirement.

Workspace archives embed the accepted point and its normal-B locator. A later
workspace reuses that point when its complete private Git roots are covered;
active changes to unrelated branches do not force another graph capture. Points
and uncertain captures are preserved, and every restore is create-only.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import uuid

from catalog import Conflict, canonical
from custody import Custody
from lifecycle import digest
from normal_b import immutable
import payloads
import git_dependency

NAMESPACE = uuid.UUID('68a6a978-ce73-48a7-a0cc-a048618fdf07')


def private_directory(path):
    path = Path(path)
    payloads.parent_safe(path)
    st = path.lstat()
    if path.is_symlink() or not path.is_dir() or st.st_uid != os.getuid() or st.st_mode & 0o077:
        raise Conflict('Private owned dependency directory required')
    return path


def roots(common):
    result = git_dependency.git(common, '--git-dir=' + str(common), 'cat-file',
                                '--batch-all-objects', '--batch-check=%(objectname) %(objecttype)')
    values = []
    for row in result.decode('ascii').splitlines():
        oid, kind = row.split(' ')
        git_dependency.object_id(oid)
        if kind in ('commit', 'tag'):
            values.append(oid)
    return sorted(set(values))


class SharedGit:
    def __init__(self, control_root, custody_root, provider, authority):
        self.control = private_directory(control_root)
        self.custody_root, self.provider, self.authority = custody_root, provider, authority

    def _validate(self, record, common, required):
        if record.get('format') != 'vk-workspace-shared-git-point-v1':
            raise Conflict('Unknown shared dependency point')
        manifest = record['manifest']
        if (digest(manifest) != record['manifest_sha256']
                or manifest.get('format') != 'vk-workspace-shared-git-v1'
                or manifest['source_root'] != str(common)
                or manifest['payloads']['roots'] != [str(common)]
                or not set(required) <= set(manifest['object_roots'])):
            raise Conflict('Shared Git point does not cover required workspace history')
        payloads.validate(manifest['payloads'])
        return manifest

    def ensure(self, spec):
        """Reuse a verified graph or capture/restore it through the normal owner."""
        self.authority.check_shared(spec)
        if git_dependency.inspect(spec['worktree'], spec['repository'], spec['branch'].removeprefix('refs/heads/')) != spec:
            raise Conflict('Workspace Git dependency changed before preparation')
        common = Path(spec['common'])
        required = spec['object_roots']
        key = str(uuid.uuid5(NAMESPACE, str(common)))
        with Custody(self.custody_root, key, exclusive=True) as custody:
            def check():
                custody.check()
                self.authority.check_shared(spec)
            for path in sorted(self.control.glob(key + '-*.accepted.json')):
                record = json.loads(path.read_text())
                try:
                    self._validate(record, common, required)
                except Conflict:
                    continue
                # Stored acceptance is immutable local authority, not a backup
                # selecting code. Reopen B metadata before trusting its locator.
                if self.provider.describe(record['recovery_locator'], record['manifest_sha256']) != record['manifest']:
                    raise Conflict('Shared normal-B recovery point changed')
                check()
                if git_dependency.inspect(spec['worktree'], spec['repository'], spec['branch'].removeprefix('refs/heads/')) != spec:
                    raise Conflict('Workspace Git dependency changed during reuse')
                return record
            check()
            tree = payloads.snapshot([common], check)
            covered = roots(common)
            if not set(required) <= set(covered):
                raise Conflict('Live shared Git graph lacks private workspace roots')
            payloads.verify(tree, versions=True, guard=check)
            # Reading changes atime. It does not create a new capture identity.
            operation = str(uuid.uuid5(NAMESPACE, digest(dict(source=str(common),
                payloads=payloads.comparable(tree, versions=True), object_roots=covered))))
            point = self.control / (key + '-' + operation)
            if not point.exists():
                point.mkdir(mode=0o700)
                payloads.directory_sync(point.parent)
            private_directory(point)
            intent = point / 'intent.json'
            if intent.exists():
                manifest = json.loads(intent.read_text())
                if (manifest['operation_id'] != operation or manifest['source_root'] != str(common)
                        or payloads.comparable(manifest['payloads'], versions=True) != payloads.comparable(tree, versions=True)
                        or manifest['object_roots'] != covered):
                    raise Conflict('Uncertain shared dependency operation differs')
            else:
                manifest = dict(format='vk-workspace-shared-git-v1', operation_id=operation,
                    source_root=str(common), object_roots=covered, payloads=tree)
                immutable(intent, canonical(manifest).encode())
            locator_path = point / 'locator.json'
            if locator_path.exists():
                locator = json.loads(locator_path.read_text())
            else:
                locator = self.provider.capture(manifest)
                immutable(locator_path, canonical(locator).encode())
            attempt = 0
            while True:
                stage = point / ('restore-' + str(attempt))
                immutable(point / ('restore-' + str(attempt) + '.intent.json'),
                          canonical(dict(operation=operation, manifest_sha256=digest(manifest), stage=str(stage))).encode())
                if os.path.lexists(stage):
                    try:
                        payloads.verify(manifest['payloads'], [stage / '0'], guard=check)
                    except (FileNotFoundError, ValueError):
                        # Keep the exact interrupted copy. The reserve guard
                        # accounts for it before a new attempt is allocated.
                        immutable(point / ('restore-' + str(attempt) + '.partial.json'),
                                  canonical(dict(operation=operation, preserved_stage=str(stage))).encode())
                        attempt += 1
                        continue
                else:
                    self.authority.reserve_restore(manifest, stage)
                    with self.provider.recall(locator, digest(manifest)) as recovered:
                        if recovered.manifest != manifest:
                            raise Conflict('Independently restored shared manifest differs')
                        payloads.restore(manifest['payloads'], stage, recovered.open_body, guard=check)
                break
            git_dependency.verify_shared_snapshot(stage / '0', covered)
            if roots(stage / '0') != covered:
                raise Conflict('Independently restored Git object inventory differs')
            check()
            if git_dependency.inspect(spec['worktree'], spec['repository'], spec['branch'].removeprefix('refs/heads/')) != spec:
                raise Conflict('Workspace Git dependency changed during capture')
            record = dict(format='vk-workspace-shared-git-point-v1', manifest=manifest,
                manifest_sha256=digest(manifest), recovery_locator=locator)
            immutable(self.control / (key + '-' + operation + '.accepted.json'), canonical(record).encode())
            # Only this independently verified staging copy is removed. The
            # actual shared repository, previous points and partials stay intact.
            payloads.remove_verified(manifest['payloads'], [stage / '0'], guard=check)
            stage.rmdir()
            payloads.directory_sync(stage.parent)
            return record

    @contextmanager
    def recall(self, record, spec, destination):
        """Normal independent recovery for the shared graph; never live overwrite."""
        manifest = self._validate(record, Path(spec['common']), spec['object_roots'])
        self.authority.check_shared(spec)
        self.authority.reserve_restore(manifest, destination)
        with self.provider.recall(record['recovery_locator'], record['manifest_sha256']) as recovered:
            if recovered.manifest != manifest:
                raise Conflict('Shared dependency recovery binding differs')
            restored = payloads.restore(manifest['payloads'], destination, recovered.open_body,
                                        guard=lambda: self.authority.check_shared(spec))
        git_dependency.verify_shared_snapshot(restored[0], spec['object_roots'])
        yield restored[0]
