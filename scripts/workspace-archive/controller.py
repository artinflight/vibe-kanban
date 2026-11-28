"""One finite archive/revival invocation owned by the serving writer.

The deployment factory supplies qualified live identities, resource admission,
process visibility and normal B. This engine owns no daemon, retry loop, execution
dispatch or restart. It reconciles the existing physical operation before doing
anything and never creates a replacement for an uncertain operation.
"""
import uuid

from catalog import Conflict, identity
from lifecycle import Lifecycle


class Controller:
    def __init__(self, catalog, custody, provider, authority, staging, event=lambda *_: None):
        self.catalog, self.custody, self.authority = catalog, custody, authority
        self.workspace = custody.path.stem
        self.lifecycle = Lifecycle(catalog, custody, provider, authority, staging, event)

    def run(self, action):
        if action not in ('archive', 'ensure'):
            raise ValueError('Only finite archive or same-workspace restoration is supported')
        self.custody.check()
        self.authority.begin(self.workspace, action)
        state = self.catalog.state(self.workspace)
        phase = state['phase'] if state else 'active'
        if action == 'ensure':
            if phase != 'active':
                self.lifecycle.restore()
            wanted = 'active'
        else:
            request = self.catalog.db.execute('''SELECT request_version,requested_state FROM
                workspace_archive_requests WHERE workspace_id=?''', (identity(self.workspace),)).fetchone()
            if request is None or request['requested_state'] != 'archived':
                raise Conflict('The current archive request was withdrawn')
            self.catalog._archive_current(self.workspace, request['request_version'])
            if phase == 'restoring':
                raise Conflict('Existing restoration must complete before a new archive')
            if phase == 'active':
                ownership = self.authority.plan(self.workspace)
                self.lifecycle.prepare(request['request_version'], str(uuid.uuid4()), ownership)
                phase = 'verified'
            elif state['request_version'] != request['request_version']:
                raise Conflict('Previous physical generation must be restored before rearchival')
            elif phase == 'preparing':
                self.lifecycle.resume_preparation()
                phase = 'verified'
            if phase in ('verified', 'retiring'):
                self.lifecycle.retire()
            elif phase == 'cold':
                self.lifecycle.purge()
            else:
                raise Conflict('Physical state is unresolved')
            wanted = 'cold'
        state = self.catalog.state(self.workspace)
        phase = state['phase'] if state else 'active'
        if phase != wanted:
            raise Conflict('Finite lifecycle did not reach its requested physical state')
        self.custody.check()
        self.authority.finish(self.workspace, action)
        return dict(format='vk-workspace-archive-driver-result-v1', complete=True,
                    workspace_id=self.workspace, phase=phase,
                    operation_id=state['operation_id'] if state else None)
