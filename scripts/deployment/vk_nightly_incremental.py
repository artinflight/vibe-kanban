"""Normal bounded current-map catch-up using the already delivered B journal.

No namespace bootstrap, global source inventory or body copy occurs here. The
installed controller owns admission and the global producer lease, serially
delivers the source outbox first, and supplies the authenticated working map and
journal references. A lost source epoch requires the separate gap procedure.
This stage never accepts a baseline or enables a calendar.
"""
import json

from vk_change_journal import scope
from vk_nightly_b_controls import tracking_store,retry_native_busy
from vk_nightly_current_map import pending_replay_for_epoch
from vk_nightly_metadata_replay import durable_report,stage_input,load_input,replay_cursor
from vk_nightly_namespace import replay_metadata
from vk_prep_common import identity


def advance_suffix(client,*,index_name,checkpoint_sha256,journal_name,journal_checkpoint_sha256,
                   plan,maximum_paths,maximum_journal_bytes,guard,on_progress=lambda _:None):
    """Apply one authenticated suffix; resume its actual B input on interruption.

    The caller supplies real configured bounds and a ready, independently
    delivered source epoch. All temporary/rollback/index bytes stay on native B.
    Reopening the normal readonly provider verifies committed metadata before
    returning, but is not independent body/SQL/runtime/whole-restore acceptance.
    """
    if type(maximum_paths) is not int or not 1<=maximum_paths<=100000:
        raise ValueError('finite ordinary delta path budget required')
    guard();db=client.connect(index_name,checkpoint_sha256)
    try:
        row=db.execute('select binding,complete from namespace_reconciliation where id=1').fetchone()
        if not row or row[1]!=1:raise ValueError('complete current namespace required; use explicit gap recovery')
        binding=json.loads(row[0]);instance=binding['instance']
        if (binding['plan_sha256']!=identity(plan) or binding['scope_sha256']!=identity(scope(plan))
                or set(binding['required_root_bindings'])!=set(plan['sources'])):
            raise ValueError('normal delta source/plan differs; explicit reconciliation required')
        with tracking_store(client,journal_name,journal_checkpoint_sha256,
                            maximum_bytes=maximum_journal_bytes) as ledger:
            # A new delivery must not replace the exact input of an interrupted
            # native transaction, even if newer names are already on B.
            pending=pending_replay_for_epoch(db,instance)
            if pending is not None:
                inputs=load_input(db,pending,guard=guard);window=pending;resumed=True
            else:
                since=replay_cursor(db,instance,binding['start_sequence'])
                report=durable_report(ledger,instance,since,guard=guard,maximum_paths=maximum_paths)
                replay=replay_metadata(plan,report,instance=instance,since=since,
                                       maximum_paths=maximum_paths,checkpoint=guard)
                inputs=dict(report=report,replay=replay)
                window=retry_native_busy(lambda:stage_input(db,report,replay,guard=guard),guard=guard);resumed=False
            guard();on_progress(dict(phase='current-delta-input-durable',input_sha256=window,
                                    resumed_retained_input=resumed,source_body_bytes_read=0,SSD_index_bytes=0))
            result=retry_native_busy(lambda:client.call(op='replay-current-map',name=index_name,
                journal_index=journal_name,input_sha256=window,maximum_paths=maximum_paths),guard=guard)
        expected=db.execute('select complete,summary from namespace_replay_windows where sha256=?',(window,)).fetchone()
        if not expected or expected[0]!=1 or json.loads(expected[1])!={k:v for k,v in result.items() if k!='already_complete'}:
            raise ValueError('committed ordinary delta result differs')
    finally:db.close()
    # Release the writer first. Native SQLite/FULL plus a normal readonly reopen
    # preserve an acknowledged cursor without retaining an SSD journal copy.
    view=client.connect(index_name,checkpoint_sha256,readonly=True,working=True)
    try:
        if load_input(view,window,guard=guard)!=inputs:raise ValueError('normal B delta input readback differs')
        actual=view.execute('select complete,summary from namespace_replay_windows where sha256=?',(window,)).fetchone()
        if actual!=expected:raise ValueError('normal B delta result readback differs')
        if view.execute('select suffix_complete from namespace_reconciliation where id=1').fetchone()!=(1,):
            raise ValueError('actual current delta remains incomplete')
    finally:view.close()
    guard()
    return dict(result,input_sha256=window,resumed_retained_input=resumed,
                normal_B_metadata_reopen_verified=True,global_namespace_audits_started=0,
                source_body_bytes_read=0,SSD_index_bytes=0,baseline_accepted=False,schedule_enabled=False)
