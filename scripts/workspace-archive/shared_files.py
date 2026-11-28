"""Normal-B recovery points for shared attachment roots; no source retirement.

A verified point is reused while its exact source versions remain current. New
uploads create a new immutable point through the existing CAS. A revival may
restore missing files, but never replace newer shared data or remove an upload.
"""
from pathlib import Path
import json
import os
import uuid

from catalog import Conflict, canonical
from custody import Custody
from lifecycle import digest
from normal_b import immutable
from shared_dependency import private_directory
import payloads

NAMESPACE = uuid.UUID('c6c7610e-9176-4b0a-9db9-acbcc4e87e32')


def current(tree):
    """Metadata identity check, not a new body hash or a B recovery proof."""
    children = {}
    for row in tree['entries']:
        path = Path(tree['roots'][row['root']]) / row['relative']
        if row['relative'] != '.':
            children.setdefault(path.parent, set()).add(path.name)
    for row in tree['entries']:
        path = Path(tree['roots'][row['root']]) / row['relative']
        if not os.path.lexists(path) or payloads.signature(path.lstat()) != row['version']:
            return False
        if row['kind'] == 'directory' and set(os.listdir(path)) != children.get(path, set()):
            return False
    return True


class SharedFiles:
    def __init__(self, control_root, custody_root, provider, authority):
        self.control = private_directory(control_root)
        self.custody_root, self.provider, self.authority = custody_root, provider, authority

    def validate(self, record, roots):
        manifest = record['manifest']
        if (record.get('format') != 'vk-workspace-shared-files-point-v1'
                or digest(manifest) != record['manifest_sha256']
                or manifest.get('format') != 'vk-workspace-shared-files-v1'
                or manifest['payloads']['roots'] != list(roots)):
            raise Conflict('Exact shared attachment recovery binding required')
        payloads.validate(manifest['payloads'])
        if any(r['kind'] == 'symlink' for r in manifest['payloads']['entries']):
            raise Conflict('Shared attachment aliases require explicit dependency qualification')
        return manifest

    def ensure(self, roots):
        roots = sorted(map(str, roots))
        self.authority.check_shared_files(roots)
        key = str(uuid.uuid5(NAMESPACE, digest(roots)))
        with Custody(self.custody_root, key, exclusive=True) as custody:
            def check():
                custody.check()
                self.authority.check_shared_files(roots)
            for path in sorted(self.control.glob(key + '-*.accepted.json'), key=lambda p: p.stat().st_mtime_ns, reverse=True):
                record = json.loads(path.read_text())
                manifest = self.validate(record, roots)
                if current(manifest['payloads']):
                    if self.provider.describe(record['recovery_locator'], record['manifest_sha256']) != manifest:
                        raise Conflict('Shared attachment B metadata differs')
                    check()
                    if not current(manifest['payloads']):
                        raise Conflict('Shared attachment versions changed during reuse')
                    return record
            tree = payloads.snapshot(roots, check)
            if any(r['kind'] == 'symlink' for r in tree['entries']):
                raise Conflict('Shared attachment aliases remain protected')
            operation = str(uuid.uuid5(NAMESPACE, digest(payloads.comparable(tree, versions=True))))
            point = self.control / (key + '-' + operation)
            if not point.exists():
                point.mkdir(mode=0o700)
                payloads.directory_sync(point.parent)
            private_directory(point)
            intent = point / 'intent.json'
            if intent.exists():
                manifest = json.loads(intent.read_text())
                if payloads.comparable(manifest['payloads'], versions=True) != payloads.comparable(tree, versions=True):
                    raise Conflict('Uncertain shared-file operation differs')
            else:
                manifest = dict(format='vk-workspace-shared-files-v1', operation_id=operation, payloads=tree)
                immutable(intent, canonical(manifest).encode())
            locator_path = point / 'locator.json'
            if locator_path.exists():
                locator = json.loads(locator_path.read_text())
            else:
                locator = self.provider.capture(manifest)
                immutable(locator_path, canonical(locator).encode())
            record = dict(format='vk-workspace-shared-files-point-v1', manifest=manifest,
                          manifest_sha256=digest(manifest), recovery_locator=locator)
            self.validate(record, roots)
            stage = self.restored(record, point, check)
            check()
            if not current(manifest['payloads']):
                raise Conflict('Shared attachments changed during independent verification')
            immutable(self.control / (key + '-' + operation + '.accepted.json'), canonical(record).encode())
            payloads.remove_verified(manifest['payloads'], [stage / str(i) for i in range(len(roots))], guard=check)
            stage.rmdir()
            payloads.directory_sync(stage.parent)
            return record

    def restored(self, record, point, check):
        tree = record['manifest']['payloads']
        for attempt in range(len(list(point.glob('restore-*.intent.json'))) + 1):
            stage = point / ('restore-' + str(attempt))
            immutable(point / ('restore-' + str(attempt) + '.intent.json'),
                      canonical(dict(manifest_sha256=record['manifest_sha256'], stage=str(stage))).encode())
            if os.path.lexists(stage):
                try:
                    payloads.verify(tree, [stage / str(i) for i in range(len(tree['roots']))], guard=check)
                except (FileNotFoundError, ValueError):
                    # Preserve partial copies. Resource admission includes them.
                    continue
            else:
                self.authority.reserve_restore(record['manifest'], stage)
                with self.provider.recall(record['recovery_locator'], record['manifest_sha256']) as recovered:
                    if recovered.manifest != record['manifest']:
                        raise Conflict('Shared attachments independently recalled from B differ')
                    payloads.restore(tree, stage, recovered.open_body, guard=check)
            return stage
        raise Conflict('Unresolved shared attachment restore attempt')

    def recover_missing(self, record, roots):
        manifest = self.validate(record, roots)
        tree = manifest['payloads']
        key = str(uuid.uuid5(NAMESPACE, digest(sorted(roots))))
        with Custody(self.custody_root, key, exclusive=True) as custody:
            def check():
                custody.check()
                self.authority.check_shared_files(roots)
            check()
            point = self.control / (key + '-' + manifest['operation_id'])
            private_directory(point)
            stage = None
            for row in tree['entries']:
                check()
                path = Path(tree['roots'][row['root']]) / row['relative']
                payloads.parent_safe(path)
                if row['kind'] == 'directory':
                    if not os.path.lexists(path):
                        path.mkdir(mode=0o700)
                        payloads.apply_metadata(path, row)
                        payloads.directory_sync(path.parent)
                    elif path.is_symlink() or not path.is_dir() or path.stat().st_uid != os.getuid():
                        raise Conflict('Shared attachment directory changed')
                    continue  # preserve current directory metadata and new uploads
                single = dict(format='vk-workspace-payloads-v1', roots=[str(path)],
                              entries=[dict(row, root=0, relative='.')])
                if os.path.lexists(path):
                    payloads.verify(single, guard=check)
                    continue
                if stage is None:
                    stage = self.restored(record, point, check)
                self.authority.reserve_publication({'payloads': single}, 0, path)
                payloads._publish_file(stage / str(row['root']) / row['relative'], path, row, check)
                payloads.verify(single, guard=check)
            # Retain the verified stage for interrupted repairs; the normal
            # scoped staging retirement owns cleanup after dependency acceptance.
            check()
