"""Fixed serial integration of the direct-B current-set backup phases.

The installed caller owns the lifetime cycle lease and externally authenticated
configs, consumer contract/placement and existing normal-reader adapter. No
manifest-selected command, bootstrap namespace scan, timer or backend restart.
The B ledger and absolute whole-night deadline survive interrupted controllers.
"""
from datetime import datetime,timezone
import time

from vk_nightly_cycle_state import run_cycle
from vk_nightly_file_cycle import Source
from vk_nightly_file_cycle import run as file_cycle
from vk_nightly_sql_cycle import run as SQL_cycle
from vk_nightly_runtime_cycle import capture_component
from vk_nightly_finalize_current import finalize,consumer_packet
from vk_nightly_desktop_controls import DesktopControls
from vk_nightly_typed_worker import host_guard,run_B
from vk_typed_recovery import checksum



def recorded_file_tail(worker,owner,*,report):
    """One bounded recorded delta; deliver newer events without selecting them."""
    owner.check();last_delivery=time.monotonic()
    def boundary():
        nonlocal last_delivery
        owner.check()
        if time.monotonic()-last_delivery>=120:
            owner.deliver();last_delivery=time.monotonic()
    selected=dict(worker,qualification=dict(worker['qualification'],attach_base_prefixes=False))
    with DesktopControls(worker['B_controls'],guard=owner.guard) as remote:
        return run_B(selected,at_component_boundary=boundary,
            source_report=lambda:owner.report(remote.client),status_sink=report)


def close_deferred_files(original,worker,owner,*,report):
    """Close only unresolved recorded names, without a new namespace suffix.

    The predecessor receipt remains byte-for-byte readable on B. A crash before
    the whole-cycle phase commit reuses accepted bodies from the same map; a
    crash after that commit skips this callback through the reopened ledger.
    Original deferred epoch truth is retained inside the composed receipt.
    """
    if original.get('more_pending') is False:return original
    if (original.get('actual_independent_B_file_cycle_receipt_reopen_verified') is not True
            or original.get('requires_source_requalification') is not True):
        raise ValueError('only independently reopened deferred file points can enter bounded closure')
    tail=recorded_file_tail(worker,owner,report=report)
    if tail.get('more_pending') is not False:
        raise ValueError('recorded file points still changing or incomplete; preserve all versions')
    # A different normal native connection observes committed member states;
    # a caller's Boolean is insufficient to close a source replacement race.
    with DesktopControls(worker['B_controls'],guard=owner.guard) as remote:
        db=remote.client.connect(worker['B_index_name'],worker['B_checkpoint_sha256'],readonly=True,working=True)
        try:
            if db.execute("select 1 from members where state in ('file-needs-qualification',"
                          "'current-namespace-replay-required','file-needs-capture') limit 1").fetchone():
                raise ValueError('independent B map still has unresolved file points')
            db.request('check')
        finally:db.close()
    owner.check()
    return dict(phase='finite-current-file-cycle-complete',more_pending=False,
        original_component_receipt=original,original_component_receipt_sha256=checksum(original),
        recorded_file_delta=tail,normal_B_file_closure_reopen_verified=True,
        actual_independent_B_file_cycle_receipt_reopen_verified=True,
        final_B_delivery=original['final_B_delivery'],baseline_accepted=False,schedule_enabled=False)


def run(config,workers,store,*,consumer,guard,report=lambda _:None,now=lambda:datetime.now(timezone.utc),
        completed_components=None):
    """Callbacks are fixed source functions; consumer is the trusted normal route.

    Each new nightly must install a unique SQL phase/cohort tag bound to that
    cycle. Replaying this SAME binding resumes its frozen request, not new SQL
    API snapshots. Final delta consumes only names already recorded by that
    request's suffix: it does not chase an always-changing global namespace.
    """
    binding=config['cycle_binding'];deadline=binding['deadline_UTC']
    actual={name:dict(worker,whole_cycle_deadline_UTC=deadline,
        B_controls=dict(worker['B_controls'],whole_cycle_deadline_UTC=deadline),
        desktop=dict(worker.get('desktop',worker['B_controls']),whole_cycle_deadline_UTC=deadline))
        for name,worker in workers.items()}
    source_ref=config['files']['source_observer'];main=actual['files']
    for name in ('SQL','runtime'):
        if config[name]['source_observer']!=source_ref or actual[name]['B_controls']!=main['B_controls']:
            raise ValueError('same actual source owner and native B controls required')
    if (config['SQL']['cohort_tag']!=binding['SQL_cohort_tag']
            or config['SQL']['SQL_phase_index']!=binding['SQL_phase_index']
            or config['finalize']['current_map']!={k:main['B_'+k] for k in ('index_name','checkpoint_sha256')}):
        raise ValueError('frozen cycle SQL request and retained map bindings differ')
    if config['files'].get('metadata_predecessor') or config['SQL'].get('file_predecessor'):
        raise ValueError('synchronous whole-cycle configuration cannot launch or await other phase units')
    completed_components=completed_components or {}
    if completed_components and set(completed_components)!=set(('files','SQL','runtime')):
        raise ValueError('only one complete independently reopened existing serial chain can be adopted')
    if completed_components and binding.get('cycle_kind')!='adopt-existing-commissioning':
        raise ValueError('existing components cannot masquerade as a timed ordinary incremental cycle')
    def files(_,end,check):
        check()
        value=completed_components['files'] if completed_components else file_cycle(config['files'],actual['files'],report=report)
        if value.get('more_pending') is False:return value
        started=time.monotonic()
        owner=Source(source_ref,main['B_controls'],guard=lambda:(check(),host_guard(main,started)))
        return close_deferred_files(value,main,owner,report=report)
    def SQL(_,end,check):
        check()
        return completed_components['SQL'] if completed_components else SQL_cycle(config['SQL'],actual['SQL'],report=report)
    def runtime(results,end,check):
        started=time.monotonic();check()
        if completed_components:return completed_components['runtime']
        owner=Source(source_ref,main['B_controls'],guard=lambda:(check(),host_guard(actual['runtime'],started)))
        return capture_component(config['runtime'],actual['runtime'],owner,guard=owner.guard,report=report)
    def candidate(results,end,check):
        # SQL selection advanced one durable journal suffix after the earlier
        # file phase. Finish exactly those newly dirty files without advancing
        # again and invalidating already captured SQL or chasing live history.
        started=time.monotonic()
        owner=Source(source_ref,main['B_controls'],guard=lambda:(check(),host_guard(main,started)))
        tail=recorded_file_tail(main,owner,report=report)
        if tail['more_pending']:raise ValueError('bounded recorded final delta remains incomplete; retain all points')
        with DesktopControls(main['B_controls'],guard=owner.guard) as remote:
            settings=dict(config['finalize'],guard=owner.guard,report=report)
            settings['runtime_phase']=results['runtime']
            value=finalize(remote.client,**settings)
        left=(datetime.fromisoformat(end)-now()).total_seconds()
        packet=consumer_packet(value,**dict(config['consumer'],remaining_seconds=left,whole_cycle_deadline_UTC=end))
        return dict(candidate=value,packet=packet,final_delta=tail)
    def restore(results,end,check):
        # The independently pinned normal consumer must enforce actual B
        # admission while it holds provider/metadata leases through readback.
        return consumer(results['candidate']['packet'],guard=check,report=report)
    return run_cycle(store,binding,files=files,SQL=SQL,runtime=runtime,finalize=candidate,
                     restore=restore,guard=guard,now=now,report=report)
