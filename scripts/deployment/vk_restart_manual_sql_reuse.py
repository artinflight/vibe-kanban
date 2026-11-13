"""Unarmed SQL-reuse entry over the existing physical final-update fence.

No CLI or service controls. The original admission and WriterFence remain the
only execution boundary. The original serial selector captures every source
that fails old-epoch qualification; recorded SQL closure never selects a new
suffix. The pinned Nightly source modules are left unchanged.
"""
from contextlib import contextmanager
from pathlib import Path
import time

import vk_restart_manual_update as original_update
from vk_restart_sql_adoption import adopt_unchanged_SQL, load_checkpoint


HELPERS = {'vk_restart_manual_sql_reuse.py', 'vk_restart_sql_adoption.py',
           'vk_restart_sql_sidecar_reuse.py', 'vk_restart_sql_reuse.py'}


def authenticate(plan, *, folder):
    sha = original_update.authenticate(plan, folder=folder)
    settings = plan['SQL_epoch_reuse']
    if set(settings['helper_sha256']) != HELPERS or settings.get('new_API_epoch_claimed') is not False:
        raise ValueError('Exact source-bound old-epoch reuse helpers required')
    for name, expected in settings['helper_sha256'].items():
        if original_update.digest(Path(__file__).resolve().parent/name) != expected:
            raise ValueError('SQL reuse helper changed')
    value = load_checkpoint(settings['accepted_checkpoint'])
    request = value['candidate']['consumer_contract']['current_SQL_request']
    if (request['cohort_id'] != settings['expected_SQL_cohort_id']
            or request['binding']['source_instance'] != plan['source_observer']['instance']
            or request['binding']['map_index'] != plan['current_map']['index_name']
            or request['binding']['map_checkpoint_sha256'] != plan['current_map']['checkpoint_sha256']
            or settings['maximum_delta_paths'] != plan['phases']['SQL']['maximum_delta_paths']):
        raise ValueError('Exact accepted catch-up, source and current map binding required')
    return sha


@contextmanager
def installed(plan):
    """One trusted serial controller; no competing or persistent replacement."""
    import vk_nightly_sql_cycle as sql
    import vk_nightly_file_cycle as files
    from vk_nightly_desktop_controls import DesktopControls
    old = sql.run
    def with_reuse(config, worker, *, report):
        if config.get('recorded_SQL_scope_from'):
            return old(config, worker, report=report)
        start = time.monotonic()
        # original_update.fenced_phase_guards wraps this actual module guard
        # while the original WriterFence is held around the entire invocation.
        guard = lambda:sql.host_guard(worker, start)
        guard()
        source = files.Source(config['source_observer'], worker['B_controls'], guard=guard)
        with DesktopControls(worker['B_controls'], guard=guard) as remote:
            reused = adopt_unchanged_SQL(remote.client, plan['SQL_epoch_reuse'], worker, source, guard=guard, report=report)
        value = old(config, worker, report=report)
        return dict(value, unchanged_API_epoch_reuse=reused)
    sql.run = with_reuse
    try:
        yield
    finally:
        changed = sql.run is not with_reuse
        sql.run = old
        if changed:
            raise ValueError('Concurrent SQL entry replacement; final acceptance forbidden')


def run_after_pause(plan, instruction, *, folder, quiet_inventory, released_ownership, report=lambda _:None):
    # Refuse missing authority BEFORE any adapter, source RPC or native B call.
    original_update.admit(plan, instruction, folder=folder)
    authenticate(plan, folder=folder)
    if plan.get('preparation_blockers'):
        raise PermissionError('Unresolved preparation blockers; seal a newly qualified plan before final update')
    with installed(plan):
        return original_update.run_after_pause(plan, instruction, folder=folder,
            quiet_inventory=quiet_inventory, released_ownership=released_ownership, report=report)
