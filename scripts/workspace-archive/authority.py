"""Bind the finite lifecycle to qualified host and shared recovery ownership.

The source-pinned deployment factory supplies Host, not a caller-named plugin.
Host owns actual paired-reader identity/parent verification, process visibility
and filesystem/resource admission. It must qualify before any planning or B IO.
This composition does not itself certify that a deployment is ready or activated.
"""
from pathlib import Path

from catalog import Conflict
import git_dependency
from ownership import Ownership


class WorkspaceAuthority:
    def __init__(self, workspace, config, host):
        self.workspace, self.config, self.host = workspace, config, host
        self.action, self.git, self.files = None, None, None
        self.ownership = Ownership(config['database'], config['sessions_root'], config['native_state'],
            config['native_roots'], config['worktrees_root'], process_check=host.check_processes)

    def bind_dependencies(self, git, files):
        if self.git is not None or self.files is not None:
            raise Conflict('Shared recovery owner is already bound')
        self.git, self.files = git, files

    def begin(self, workspace, action):
        if workspace != self.workspace or action not in ('archive', 'ensure') or self.action is not None:
            raise Conflict('One exact finite workspace action is required')
        self.host.qualify()
        self.action = action
        self.check(workspace, None)

    def check(self, workspace, manifest=None):
        if workspace != self.workspace or self.action is None:
            raise Conflict('Workspace action has not been admitted by its serving owner')
        self.host.check()
        self.ownership.check_bindings()
        if manifest is not None and manifest['workspace_id'] != workspace:
            raise Conflict('Manifest belongs to another workspace')

    def plan(self, workspace):
        self.check(workspace)
        if self.action != 'archive' or self.git is None or self.files is None:
            raise Conflict('Complete qualified archive dependency owners required')
        plan = self.ownership.plan(workspace)
        plan['shared_git'] = [self.git.ensure(spec) for spec in plan['git']]
        plan['shared_files'] = self.files.ensure(self.config['attachment_roots'])
        self.validate_plan(workspace, plan)
        return plan

    def validate_plan(self, workspace, plan):
        self.check(workspace)
        self.ownership.validate(workspace, plan, archive=self.action == 'archive')
        for spec, record in zip(plan['git'], plan['shared_git'], strict=True):
            self.git._validate(record, Path(spec['common']), spec['object_roots'])
        self.files.validate(plan['shared_files'], sorted(self.config['attachment_roots']))
        if any(Path(root) == Path(shared) or Path(shared) in Path(root).parents
               for root in plan['roots'] for shared in self.config['attachment_roots']):
            raise Conflict('Shared attachment storage cannot be locally retired')

    def check_shared(self, spec):
        self.check(self.workspace)
        if self.git is None:
            raise Conflict('Shared Git recovery owner not bound')

    def check_shared_files(self, roots):
        self.check(self.workspace)
        if sorted(roots) != sorted(self.config['attachment_roots']):
            raise Conflict('Shared attachment roots differ from the qualified release')

    def reserve_restore(self, manifest, stage):
        self.check(self.workspace)
        self.host.reserve_restore(manifest['payloads'], Path(stage))

    def reserve_publication(self, manifest, index, destination):
        self.check(self.workspace)
        self.host.reserve_publication(manifest['payloads'], index, Path(destination))

    def validate_payloads(self, manifest):
        self.check(self.workspace, manifest)
        plan = manifest['ownership']
        identities = {tuple(row['version'][:2]) for row in manifest['payloads']['entries']}
        self.host.check_processes(plan['roots'], identities=identities)
        roots = [Path(p) for p in plan['roots'] + self.config['attachment_roots']]
        roots += [Path(spec['common']) for spec in plan['git']]
        for row in manifest['payloads']['entries']:
            if row['kind'] == 'symlink':
                link = Path(manifest['payloads']['roots'][row['root']]) / row['relative']
                target = (link.parent / row['target']).resolve()
                if not any(target == root or root in target.parents for root in roots):
                    raise Conflict('Workspace alias has an unqualified external dependency')

    def complete_restore(self, workspace, manifest):
        self.check(workspace, manifest)
        plan = manifest['ownership']
        self.validate_plan(workspace, plan)
        self.files.recover_missing(plan['shared_files'], sorted(self.config['attachment_roots']))
        # A changed shared branch or missing Git object stays a visible recovery
        # hold. Do not reset another owner's branch or call a fetch implicitly.
        for spec in plan['git']:
            git_dependency.verify_live(spec)
        self.ownership.complete_restore(workspace, plan)

    def finish(self, workspace, action):
        if action != self.action:
            raise Conflict('Finite action changed')
        self.check(workspace)
        self.host.check_boundary()
