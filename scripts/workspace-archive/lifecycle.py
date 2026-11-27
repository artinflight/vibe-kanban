"""Recoverable physical archive/restore transactions under workspace custody.

The provider is the source-pinned normal Nightly B adapter, not an agent-created
backup transport. Authority revalidates application/native/process/dependency
ownership. Neither a UI archive flag nor successful fixture tests may substitute
for that production integration. This library deliberately has no standalone
production CLI and performs no execution dispatch or service restart.
"""
import hashlib
import os
from pathlib import Path
import uuid

from catalog import canonical, Conflict
import payloads


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class Lifecycle:
    def __init__(self, catalog, custody, provider, authority, staging_root, event=lambda *_: None):
        if not custody.exclusive:
            raise ValueError('Exclusive workspace custody required')
        self.catalog, self.custody = catalog, custody
        self.workspace = custody.path.stem
        self.provider, self.authority = provider, authority
        self.staging = Path(staging_root)
        payloads.parent_safe(self.staging)
        st = self.staging.lstat()
        if (not self.staging.is_dir() or self.staging.is_symlink()
                or st.st_uid != os.getuid() or st.st_mode & 0o077):
            raise ValueError('Private owned mounted staging root required')
        self.event = event  # Failure injection in tests; production uses progress records.

    def check(self, manifest=None):
        self.custody.check()
        self.authority.check(self.workspace, manifest)

    def _load(self):
        record = self.catalog.io(self.workspace)
        if record is None:
            raise Conflict('Missing durable physical intent')
        journal = record['journal']
        manifest = journal['manifest']
        state = self.catalog.state(self.workspace)
        operation = state['operation_id']
        if (manifest['format'] != 'vk-workspace-archive-v1'
                or manifest['workspace_id'] != self.workspace
                or manifest['operation_id'] != operation
                or manifest['request_version'] != state['request_version']):
            raise Conflict('Physical journal identity differs')
        payloads.validate(manifest['payloads'])
        roots = manifest['payloads']['roots']
        if manifest['ownership']['roots'] != roots:
            raise Conflict('Payload roots differ from ownership plan')
        self.authority.validate_plan(self.workspace, manifest['ownership'])
        expected = [str(Path(p).with_name('.vk-cold-' + operation + '-' + str(i)))
                    for i, p in enumerate(roots)]
        if (journal['retired_roots'] != expected
                or journal['verification_stage'] != str(self.staging / operation)):
            raise Conflict('Physical retirement paths differ from durable ownership')
        abandoned = journal.get('abandoned_verification', [])
        if abandoned != [str(self.staging / (operation + '-partial-' + str(i))) for i in range(len(abandoned))]:
            raise Conflict('Verification recovery paths differ')
        attempts = [str(self.staging / (operation + '-revive-' + str(i)))
                    for i in range(len(journal['restore_attempts']))]
        if attempts != journal['restore_attempts']:
            raise Conflict('Restore attempt paths differ')
        if journal['publication'] is not None:
            if len(journal['publication']) != len(roots):
                raise Conflict('Incomplete publication roots')
            for i, path in enumerate(journal['publication']):
                allowed = [roots[i], expected[i]] + [str(Path(a) / str(i)) for a in attempts]
                if path not in allowed:
                    raise Conflict('Unowned restore publication path')
        if state['phase'] != 'preparing':
            point = self.catalog.recovery(self.workspace)
            if point['manifest'] != manifest or point['recovery_locator'] != journal['recovery']:
                raise Conflict('Journal differs from immutable accepted B generation')
        return record

    def _save(self, record, journal):
        self.catalog.save_io(self.workspace, record['operation_id'], journal, record['revision'])
        return self.catalog.io(self.workspace)

    def _archive_check(self, record, phases):
        self.check(record['journal']['manifest'])
        m = record['journal']['manifest']
        self.catalog.check_archive(self.workspace, m['request_version'], m['operation_id'], phases)

    def prepare(self, version, operation, ownership):
        """Capture, reopen B, restore every byte/metadata, then qualify retirement."""
        operation = str(uuid.UUID(operation))
        self.check()
        # Authority produces the complete exact closure, including shared
        # references. A mutable path list from an untrusted caller is not enough.
        self.authority.validate_plan(self.workspace, ownership)
        tree = payloads.snapshot(ownership['roots'], lambda: self.check())
        manifest = dict(format='vk-workspace-archive-v1', workspace_id=self.workspace,
                        request_version=version, operation_id=operation,
                        ownership=ownership, payloads=tree)
        self.catalog.begin_archive(self.workspace, version, operation)
        stage = self.staging / operation
        journal = dict(manifest=manifest, verification_stage=str(stage),
                       retired_roots=[str(Path(p).with_name('.vk-cold-' + operation + '-' + str(i)))
                                      for i, p in enumerate(tree['roots'])],
                       recovery=None, restore_attempts=[], publication=None,
                       abandoned_verification=[], verification_relocation=None)
        self.catalog.save_io(self.workspace, operation, journal)
        self.event('copy_intent', manifest)
        return self.resume_preparation()

    def resume_preparation(self):
        record = self._load()
        journal = record['journal']
        manifest, tree = journal['manifest'], journal['manifest']['payloads']
        self._archive_check(record, ('preparing',))
        payloads.verify(tree, versions=True, guard=lambda: self.check(manifest))
        # Stable operation identity lets the normal provider reconcile a timed
        # out capture. It must not recapture or overwrite an uncertain generation.
        if journal['recovery'] is None:
            journal['recovery'] = self.provider.capture(manifest)
            record = self._save(record, journal)
        self.event('captured', manifest)
        stage = Path(journal['verification_stage'])
        pending = journal.get('verification_relocation')
        if pending is not None:
            if pending != journal['abandoned_verification'][-1]:
                raise Conflict('Unowned partial verification relocation')
            if os.path.lexists(stage) == os.path.lexists(pending):
                raise Conflict('Ambiguous interrupted verification relocation')
            if os.path.lexists(stage):
                payloads.rename_new(stage, pending)
            journal['verification_relocation'] = None
            record = self._save(record, journal)
        if stage.exists():
            # Full staging can survive a lost receipt. Preserve incomplete
            # staging as its own journaled attempt before retrying the same B
            # generation; never delete or overwrite the interrupted evidence.
            try:
                payloads.verify(tree, [stage / str(i) for i in range(len(tree['roots']))],
                                guard=lambda: self.check(manifest))
            except (FileNotFoundError, ValueError):
                target = str(self.staging / (manifest['operation_id'] + '-partial-' + str(len(journal['abandoned_verification']))))
                journal['abandoned_verification'].append(target)
                journal['verification_relocation'] = target
                record = self._save(record, journal)
                payloads.rename_new(stage, target)
                journal['verification_relocation'] = None
                record = self._save(record, journal)
        if not stage.exists():
            self.authority.reserve_restore(manifest, stage)
            with self.provider.recall(journal['recovery'], digest(manifest)) as recovered:
                if recovered.manifest != manifest:
                    raise ValueError('Independently recalled B manifest differs')
                payloads.restore(tree, stage, recovered.open_body,
                                 guard=lambda: self.check(manifest))
        payloads.verify(tree, versions=True, guard=lambda: self.check(manifest))
        self._archive_check(record, ('preparing',))
        self.event('restored_from_B', manifest)
        self.catalog.record_verified(self.workspace, manifest['request_version'], manifest['operation_id'],
                                     manifest, journal['recovery'])
        return manifest

    def retire(self):
        record = self._load()
        journal, manifest = record['journal'], record['journal']['manifest']
        tree = manifest['payloads']
        state = self.catalog.state(self.workspace)
        if state['phase'] == 'verified':
            self._archive_check(record, ('verified',))
            payloads.verify(tree, versions=True, guard=lambda: self.check(manifest))
            self.catalog.begin_retirement(self.workspace, manifest['request_version'], manifest['operation_id'])
        self._archive_check(record, ('retiring',))
        current = [Path(q) if os.path.lexists(q) else Path(p)
                   for p, q in zip(tree['roots'], journal['retired_roots'])]
        payloads.verify(tree, current, guard=lambda: self.check(manifest))
        resolved = []
        for i, (source, retired) in enumerate(zip(tree['roots'], journal['retired_roots'])):
            self._archive_check(record, ('retiring',))
            source, retired = Path(source), Path(retired)
            if os.path.lexists(source) == os.path.lexists(retired):
                raise Conflict('Ambiguous retirement paths; preserve both and reconcile')
            if os.path.lexists(source):
                payloads.rename_new(source, retired)
                self.event('root_retired', i)
            resolved.append(retired)
        payloads.verify(tree, resolved, guard=lambda: self.check(manifest))
        self._archive_check(record, ('retiring',))
        self.catalog.finish_retirement(self.workspace, manifest['request_version'], manifest['operation_id'])
        self.event('cold', manifest)
        self.purge()

    def purge(self):
        record = self._load()
        journal, manifest = record['journal'], record['journal']['manifest']
        self._archive_check(record, ('cold',))
        if any(os.path.lexists(p) for p in manifest['payloads']['roots']):
            raise Conflict('Active path reappeared; cold retirement stopped')
        guard = lambda: self._archive_check(record, ('cold',))
        payloads.remove_verified(manifest['payloads'], journal['retired_roots'], guard=guard)
        stage = Path(journal['verification_stage'])
        if stage.exists():
            payloads.remove_verified(manifest['payloads'],
                [stage / str(i) for i in range(len(manifest['payloads']['roots']))], guard=guard)
            stage.rmdir()
            payloads.directory_sync(stage.parent)
        self.event('local_retirement_complete', manifest)

    def restore(self):
        """Restore same paths before normal admission; never replace newer data."""
        record = self._load()
        journal, manifest = record['journal'], record['journal']['manifest']
        tree = manifest['payloads']
        self.check(manifest)
        state = self.catalog.state(self.workspace)
        if state['phase'] == 'preparing':
            # A message arrived before retirement. Original data is sufficient;
            # an offline B must not prevent cancelling an intact preparation.
            payloads.verify(tree, versions=True, guard=lambda: self.check(manifest))
            self.catalog.cancel_preparation(self.workspace, manifest['operation_id'])
            return
        if state['phase'] != 'restoring':
            self.catalog.begin_restore(self.workspace)
        self.event('restore_intent', manifest)
        if journal['publication'] is None:
            # Interrupted retirement may have left complete originals in their
            # source/quarantine locations. Reuse only if the whole tree verifies.
            current = [Path(p) if os.path.lexists(p) else Path(q)
                       for p, q in zip(tree['roots'], journal['retired_roots'])]
            if all(os.path.lexists(p) for p in current):
                try:
                    payloads.verify(tree, current, guard=lambda: self.check(manifest))
                except (FileNotFoundError, ValueError):
                    current = None
            else:
                current = None
            if current is None:
                # Preserve every partial attempt. Admission must account for
                # retained bytes before allocating another bounded stage.
                stage = self.staging / (manifest['operation_id'] + '-revive-' + str(len(journal['restore_attempts'])))
                self.authority.reserve_restore(manifest, stage)
                journal['restore_attempts'].append(str(stage))
                record = self._save(record, journal)
                with self.provider.recall(journal['recovery'], digest(manifest)) as recovered:
                    if recovered.manifest != manifest:
                        raise ValueError('B recovery manifest differs')
                    current = payloads.restore(tree, stage, recovered.open_body,
                                               guard=lambda: self.check(manifest))
            journal['publication'] = [str(p) for p in current]
            record = self._save(record, journal)
        for i, (staged, destination) in enumerate(zip(journal['publication'], tree['roots'])):
            self.check(manifest)
            if staged == destination:
                continue
            if os.path.lexists(staged) and os.path.lexists(destination):
                raise Conflict('Revival destination already exists; preserve newer data')
            if os.path.lexists(staged):
                payloads.rename_new(staged, destination)
                self.event('root_revived', i)
            elif not os.path.lexists(destination):
                raise Conflict('Both revival source and destination are absent')
        payloads.verify(tree, guard=lambda: self.check(manifest))
        self.catalog.finish_restore(self.workspace, manifest['operation_id'])
        self.event('revival_complete', manifest)
