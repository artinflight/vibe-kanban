"""Read-only Nightly integration with the same qualified serving pair/config.

The existing Nightly owner retains its own leases and tracking. Selection opens
normal B metadata before its capture lane, then keeps only scoped shared custody
while the normal cycle runs. Any new restore intent invalidates that selection.
"""
from contextlib import contextmanager
import os
from pathlib import Path
import stat

from catalog import Conflict
from driver import configuration
from host import Host
from nightly_selection import Selection
from ownership import Ownership
import payloads
import provider_factory
from lifecycle import digest


class RootGuard:
    def __init__(self, root):
        self.root=Path(root)
        self.identity=payloads.signature(self.root.lstat())[:2]
        self.locks=[]
        self.check()

    def check(self):
        st=self.root.lstat()
        if (self.root.resolve(strict=True)!=self.root or not stat.S_ISDIR(st.st_mode)
                or st.st_uid!=os.getuid() or st.st_mode & 0o077
                or payloads.signature(st)[:2]!=self.identity):
            raise Conflict('Actual shared custody root changed')
        for lock in self.locks: lock.check()


class ReadOnlyAuthority:
    def __init__(self, config, host, provider, guard, required):
        self.host,self.provider,self.guard,self.required=host,provider,guard,required
        self.ownership=Ownership(config['database'],config['sessions_root'],config['native_state'],
            config['native_roots'],config['worktrees_root'],process_check=lambda *_:None)
        self.verified=set()

    def check(self, workspace, manifest=None):
        self.guard();self.host.check();self.ownership.check_bindings()

    def validate_plan(self, workspace, plan):
        self.check(workspace)
        # This is read-only backup selection. It neither removes files nor
        # grants a mover process clearance. Shared custody prevents mutation.
        self.ownership.validate(workspace,plan,archive=False)
        shared=plan['shared_git']+[plan['shared_files']]
        for record in shared:
            manifest=record['manifest'];sha=record['manifest_sha256']
            if digest(manifest)!=sha:
                raise Conflict('Cold shared dependency manifest changed')
            for root in manifest['payloads']['roots']:
                if not any(Path(root).is_relative_to(p) for p in self.required):
                    raise Conflict('Nightly omitted a current shared recovery dependency')
            if sha not in self.verified:
                if self.provider.describe(record['recovery_locator'],sha)!=manifest:
                    raise Conflict('Shared cold recovery point is unavailable on B')
                self.verified.add(sha)


@contextmanager
def open_selection(reference, guard):
    config, actual=configuration(reference['path'])
    if actual!=reference:
        raise Conflict('Nightly does not name the qualified archive driver configuration')
    required=config['required_nightly_sources']
    if not {config['database'],config['native_state'],*config['attachment_roots']} <= set(required):
        raise Conflict('Nightly must retain current SQL/native/shared recovery sources')
    root=RootGuard(config['custody_root'])
    host=Host(config,root,actual,writer_child=False)
    host.qualify()
    def check(): guard();host.check()
    provider=provider_factory.create(config['nightly'],check)
    authority=ReadOnlyAuthority(config,host,provider,guard,required)
    with Selection(config['database'],config['custody_root'],provider,authority,required_sources=required) as selected:
        root.locks=selected.locks
        yield selected
        selected.check()
