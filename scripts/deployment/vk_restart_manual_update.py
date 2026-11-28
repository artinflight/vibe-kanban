"""Unarmed, source-bound manual Staging update over Nightly's normal phases.

No CLI, scheduler, service control or accepted-current pointer mutation. A future
cutover owner must supply Seamus's explicit instruction and continuously verify
its real writer fence. Import and profile authentication never capture data.
"""
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
import copy
import hashlib
import json
from pathlib import Path
import time


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def interruption_budget(plan):
    """Finite reviewed budgets; never extend an already admitted attempt.

    October29 needs about 41 minutes before the independently measured
    19.5-minute normal restore. The newly authorized 75/15 budget keeps a data
    contingency AND a separate service recovery allowance.
    """
    if plan.get('completion_policy') == 'until-verified-or-real-safety-failure-v1':
        if any(plan.get(key) is not None for key in (
                'maximum_update_seconds','switch_smoke_recovery_seconds','maximum_interruption_seconds')):
            raise ValueError('Completion-driven operation must not carry overall time limits')
        return None, None, None
    data_seconds = plan.get('maximum_update_seconds')
    recovery_seconds = plan.get('switch_smoke_recovery_seconds', 900)
    total_seconds = plan.get('maximum_interruption_seconds', 3600)
    if (type(data_seconds) is not int or type(recovery_seconds) is not int
            or type(total_seconds) is not int
            or (data_seconds, recovery_seconds) not in ((2700, 900), (3000, 600), (4500, 900))
            or data_seconds + recovery_seconds != total_seconds):
        raise ValueError('Exact finite backup/restore and separate service-recovery budget required')
    return data_seconds, recovery_seconds, total_seconds


def authenticate(plan, *, folder):
    if (plan.get('format') != 'vk-staging-manual-update-plan-v1'
            or plan.get('armed') is not False
            or plan.get('accepted_current_pointer_mutation') is not False):
        raise ValueError('Unarmed bounded manual Staging plan required')
    interruption_budget(plan)
    for reference in plan['evidence'].values():
        if digest(reference['path']) != reference['sha256']:
            raise ValueError('Pinned preparation evidence changed')
    if not plan['source_sha256'] or len(plan['source_sha256']) > 64:
        raise ValueError('Finite exact source closure required')
    for name, sha in plan['source_sha256'].items():
        if Path(name).name != name or not name.startswith('vk_') or not name.endswith('.py'):
            raise ValueError('Fixed installed module required')
        if digest(Path(folder) / name) != sha:
            raise ValueError('Prepared source changed: ' + name)
    current = plan['current_map']
    if (current['index_name'] != 'staging-current-map-v12-20261028'
            or current['checkpoint_sha256'] != '6471650c53e0d66a22de43bacc643940b27c8b7bf6c760f09d4b13cbf31e5371'
            or plan['source_observer']['instance'] != '44aadc4a21ed47359009272db6c11c95'):
        raise ValueError('Actual recovered source and retained draft required')
    if set(plan['workers']) != {'files', 'SQL', 'runtime'}:
        raise ValueError('All three fixed producers required')
    for name, worker in plan['workers'].items():
        if worker['source_sha256'] != plan['source_sha256']:
            raise ValueError('Producer source closure differs')
        for controls in (worker['B_controls'], worker['desktop']):
            if controls.get('whole_cycle_deadline_UTC') is not None:
                raise ValueError('Unarmed template cannot reopen an expired admission')
        if name != 'runtime' and (worker['B_index_name'] != current['index_name']
                or worker['B_checkpoint_sha256'] != current['checkpoint_sha256']):
            raise ValueError('Producer map binding differs')
    for phase in ('files', 'SQL'):
        if plan['phases'][phase]['source_observer'] != plan['source_observer']:
            raise ValueError('Phase source owner differs')
    if plan['phases']['files'].get('resume_qualified_input_sha256'):
        raise ValueError('Final update must select the actual newly delivered suffix')
    if plan['phases']['runtime']['main_map'] != current:
        raise ValueError('Runtime adoption target differs')
    if plan['finalize']['current_map'] != current:
        raise ValueError('Finalizer map differs')
    if plan['finalize']['contract']['required_SQL'] is not None:
        raise ValueError('Current SQL scope must come from actual independent map/cohort')
    route = plan['route']
    old, maintenance = json.loads(route['serving_bytes']), json.loads(route['maintenance_bytes'])
    expected = dict(old, mode='maintenance', epoch=maintenance['epoch'])
    if (old.get('mode') != 'blue' or old.get('port') != 5640
            or old.get('authoritativePort') != 5621 or maintenance != expected
            or maintenance['epoch'] <= old['epoch']):
        raise ValueError('Only declared maintenance change through existing history proxy allowed')
    expected_pin = dict(kind='file', bytes=len(route['maintenance_bytes'].encode()),
                        sha256=hashlib.sha256(route['maintenance_bytes'].encode()).hexdigest())
    for field in ('required_pins', 'required_runtime_points'):
        if plan['finalize']['contract'][field][route['path']] != expected_pin:
            raise ValueError('Actual maintenance bytes must be bound in both recovery requirements')
    return hashlib.sha256(canonical(plan)).hexdigest()


def admit(plan, instruction, *, folder, now=None):
    """A data declaration cannot supply the missing physical writer fence."""
    sha = authenticate(plan, folder=folder)
    if (instruction.get('operator') != 'Seamus' or instruction.get('pause_confirmed') is not True
            or instruction.get('plan_sha256') != sha or not instruction.get('instruction_reference')):
        raise PermissionError('Separate Seamus pause/final-update instruction required')
    if plan.get('completion_policy') == 'until-verified-or-real-safety-failure-v1':
        if (instruction.get('completion_policy') != plan['completion_policy']
                or instruction.get('deadline_UTC') is not None):
            raise ValueError('Explicit deadline-free completion instruction required')
        return sha, None
    now = now or datetime.now(timezone.utc)
    end = datetime.fromisoformat(instruction['deadline_UTC'])
    left = (end - now).total_seconds()
    if end.tzinfo is None or not 0 < left <= plan['maximum_update_seconds']:
        raise ValueError('Fresh finite manual admission required; no old Nightly window reuse')
    return sha, end


def prepare_runtime(client, plan, *, guard):
    """Create only the two explicitly sampled runtime points on native B.

    This runs AFTER authorized maintenance, not during preparation. The original
    serving route remains in the sealed parent/operation and is restored by the
    service owner after health/ownership acceptance, never blindly from backup.
    """
    from vk_nightly_b_controls import seed
    from vk_nightly_current_map import FORMAT, encode_member
    from vk_nightly_file_version import capture_version
    from vk_nightly_qualification import HashOnly
    worker = plan['workers']['runtime']
    settings = plan['phases']['runtime']
    reference = dict(index_name=worker['B_index_name'], checkpoint_sha256=seed(client))
    if reference['checkpoint_sha256'] != worker['B_checkpoint_sha256']:
        raise ValueError('Native empty metadata seed changed')
    points = []
    for source in settings['runtime_paths']:
        guard()
        observed = capture_version(source, HashOnly(), maximum_bytes=worker['maximum_source_bytes'], guard=guard)
        row = dict(kind='file', bytes=observed['bytes'], sha256=observed['sha256'],
                   **{k: observed['metadata'][k] for k in ('mode', 'uid', 'gid', 'mtime_ns', 'xattrs')})
        point = dict(source=source, source_identity=observed['source_identity'], row=row,
                     state='qualified-pending-body', source_observed_at=observed['completed_at'],
                     kernel_journal_coverage_claimed=False, original_epoch_repaired=False)
        expected = plan['finalize']['contract']['required_runtime_points'][source]
        if any(point['row'][k] != expected[k] for k in ('kind', 'bytes', 'sha256')):
            raise ValueError('Actual runtime bytes differ from declared maintenance profile')
        points.append((source[1:], 'file-needs-capture', encode_member(dict(member=point['row'], qualification=point))))
    db = client.connect(reference['index_name'], reference['checkpoint_sha256'])
    try:
        # No overwrite or inferred predecessor success. A retry must preserve
        # this operation's partial component and use its normal resume binding.
        if db.execute("select 1 from sqlite_master where name='metadata'").fetchone():
            raise ValueError('Runtime namespace exists; reconcile owned partial before retry')
        db.execute('begin immediate')
        try:
            db.execute('create table metadata(format text,binding text,last_name text,complete integer)')
            db.execute('insert into metadata values(?,?,?,1)', (FORMAT, canonical(worker['map_binding']).decode(), ''))
            db.execute('create table members(name text primary key,state text not null,row blob not null) without rowid')
            db.execute('create index member_states on members(state,name)')
            db.execute('create table SQL_sources(path text primary key) without rowid')
            db.executemany('insert into members values(?,?,?)', points)
            guard(); db.execute('commit')
        except BaseException:
            if db.in_transaction:
                db.execute('rollback')
            raise
    finally:
        db.close()
    return reference


def _run(plan, instruction, *, folder, verify_fence, report=lambda _: None):
    """Called only by the separately instructed service owner; never auto-run.

    verify_fence must inspect actual service freeze, queue/ingress and ownership,
    not validate an asserted JSON Boolean. It raises on unknown ownership. This
    function controls no live service and never promotes Nightly's global pointer.
    """
    sha, end = admit(plan, instruction, folder=folder)
    from vk_nightly_current_cycle import recorded_file_tail, close_deferred_files
    from vk_nightly_file_cycle import Source, run as files
    from vk_nightly_sql_cycle import run as SQL
    from vk_nightly_runtime_cycle import capture_component
    from vk_nightly_finalize_current import finalize, consumer_packet
    from vk_nightly_desktop_controls import DesktopControls
    from vk_nightly_desktop_objects import DesktopObjects
    from vk_nightly_typed_worker import host_guard
    from vk_nightly_remote_consumer import run as consume
    from vk_restart_tracking_client import TrackingClient, installed, deliver_when_ready
    import vk_nightly_tracking as tracking
    workers = copy.deepcopy(plan['workers'])
    phases = copy.deepcopy(plan['phases'])
    for worker in workers.values():
        if end is None:
            worker.pop('whole_cycle_deadline_UTC',None)
            worker['completion_policy']=plan['completion_policy']
        else:
            worker.update(timeout_seconds=plan['maximum_update_seconds'], whole_cycle_deadline_UTC=end.isoformat())
        for field in ('B_controls', 'desktop'):
            if end:worker[field]['whole_cycle_deadline_UTC'] = end.isoformat()
            else:worker[field].pop('whole_cycle_deadline_UTC',None)
    start = time.monotonic()
    last_fence = [0.0]
    def guard():
        host_guard(workers['SQL'], start)
        if time.monotonic()-last_fence[0] >= 5:
            verify_fence(); last_fence[0] = time.monotonic()
    def boundary():
        guard(); verify_fence()
    boundary()
    if Path(plan['route']['path']).read_bytes() != plan['route']['maintenance_bytes'].encode():
        raise ValueError('Actual authorized maintenance route missing')
    owner = Source(plan['source_observer'], workers['files']['B_controls'], guard=guard)
    health = owner.check()
    client = TrackingClient(tracking, endpoint=owner.config['endpoint'], instance=health['instance'],
        owner_pid=health['owner_pid'], owner_start_ticks=health['owner_start_ticks'], owner_uid=1000,
        timeout_seconds=90, guard=guard)
    results = {}
    with installed(tracking, client):
        deliver_when_ready(owner, client, on_wait=report)
        results['files'] = files(phases['files'], workers['files'], report=report)
        results['files'] = close_deferred_files(results['files'], workers['files'], owner, report=report)
        boundary()
        results['SQL'] = SQL(phases['SQL'], workers['SQL'], report=report)
        if results['SQL'].get('more_pending') or results['SQL'].get('deferred_SQL'):
            raise ValueError('Current SQL capture incomplete; incumbent must remain recoverable')
        boundary()
        with DesktopControls(workers['runtime']['B_controls'], guard=guard) as remote:
            prepare_runtime(remote.client, plan, guard=guard)
        results['runtime'] = capture_component(phases['runtime'], workers['runtime'], owner, guard=guard, report=report)
        tail = recorded_file_tail(workers['files'], owner, report=report)
        if tail.get('more_pending'):
            raise ValueError('Recorded final file points remain unresolved')
        sql_reference = phases['SQL']['SQL_phase_index']
        with DesktopControls(workers['files']['B_controls'], guard=guard) as remote:
            db = remote.client.connect(**dict(key=plan['current_map']['index_name'], digest=plan['current_map']['checkpoint_sha256']), readonly=True, working=True)
            try:
                missing = db.execute("select 1 from members where state='SQLite-needs-image' limit 1").fetchone()
                count = db.execute("select count(*) from SQL_sources s cross join members m on m.name=substr(s.path,2) and s.path='/'||m.name where m.state!='symlink'").fetchone()[0]
            finally:
                db.close()
        if missing or count != results['SQL']['complete_SQL_scope_sources']:
            sql_reference = dict(sql_reference, index_name=sql_reference['index_name'] + '-recorded')
            closure = dict(phases['SQL'], SQL_phase_index=sql_reference,
                cohort_tag=phases['SQL']['cohort_tag']+'-recorded', recorded_SQL_scope_from=phases['SQL']['SQL_phase_index'])
            results['SQL_closure'] = SQL(closure, workers['SQL'], report=report)
            if results['SQL_closure'].get('more_pending') or results['SQL_closure'].get('deferred_SQL'):
                raise ValueError('Recorded SQL closure incomplete')
        boundary()
        with DesktopControls(workers['files']['B_controls'], guard=guard) as remote:
            settings = dict(plan['finalize'], SQL_phase=sql_reference, runtime_phase=results['runtime'], guard=guard, report=report)
            # Explicit manual admission is separate from the expired Nightly
            # calendar. finalize does not touch the calendar/accepted pointer.
            settings['cycle_binding'] = dict(format='vk-staging-manual-update-admission-v1',
                plan_sha256=sha, deadline_UTC=end.isoformat() if end else None, source_instance=owner.reference['instance'])
            candidate = finalize(remote.client, **settings)
        packet = consumer_packet(candidate, **dict(plan['consumer'],
            remaining_seconds=(end-datetime.now(timezone.utc)).total_seconds() if end else None,
            whole_cycle_deadline_UTC=end.isoformat() if end else None))
        if end is None:packet['completion_policy']=plan['completion_policy']
        with DesktopObjects(workers['files']['desktop'], guard=guard):
            with DesktopControls(workers['files']['B_controls'], guard=guard) as remote:
                with ExitStack() as stack:
                    refs = [packet['descriptor']['indexes'][0], packet['expected_catalogs']['base'], *packet['expected_catalogs']['recipes']]
                    if packet['expected_catalogs'].get('base_names'):
                        refs.append(packet['expected_catalogs']['base_names'])
                    images = []
                    for n, ref in enumerate(refs):
                        db = remote.client.connect('staging-proof-'+str(n), ref['sha256'], readonly=True)
                        stack.callback(db.close); images.append(db)
                    last = [0.0]
                    def check():
                        guard()
                        if time.monotonic()-last[0] >= 5:
                            for image in images:
                                image.request('check')
                            last[0] = time.monotonic()
                    restored = consume(workers['files']['B_controls'], packet, guard=check, report=report)
                    check()
        boundary()
    return dict(format='vk-staging-final-update-result-v1', plan_sha256=sha,
        candidate=candidate, consumer_packet=packet, independent_restore=restored,
        components=results, final_recorded_files=tail, elapsed_seconds=time.monotonic()-start,
        release_backup_accepted=True, accepted_current_pointer_modified=False,
        cutover_performed=False, service_owner_must_verify_fence_and_semantics_again=True)


@contextmanager
def fenced_phase_guards(verify_fence):
    """One trusted serial controller; restore module bindings on every exit."""
    import vk_nightly_typed_worker as worker
    import vk_nightly_file_cycle as files
    import vk_nightly_sql_cycle as sql
    import vk_nightly_runtime_cycle as runtime
    import vk_nightly_current_cycle as cycle
    modules = (worker, files, sql, runtime, cycle)
    originals = [(module, module.host_guard) for module in modules]
    last = [0.0]
    def checked():
        if time.monotonic()-last[0] >= 5:
            verify_fence(); last[0] = time.monotonic()
    bindings = []
    try:
        verify_fence()
        for module, original in originals:
            def guarded(config, started, original=original):
                original(config, started); checked()
            module.host_guard = guarded
            bindings.append((module, original, guarded))
        yield checked
    finally:
        changed = any(module.host_guard is not guarded for module, _, guarded in bindings)
        for module, original, _ in bindings:
            module.host_guard = original
        if changed:
            raise ValueError('Concurrent host guard replacement; acceptance forbidden')


def run(plan, instruction, *, folder, verify_fence, report=lambda _: None):
    # Refuse before imports/adapters/native traffic if there is no instruction.
    admit(plan, instruction, folder=folder)
    with fenced_phase_guards(verify_fence):
        return _run(plan, instruction, folder=folder, verify_fence=verify_fence, report=report)


def run_after_pause(plan, instruction, *, folder, quiet_inventory, released_ownership, report=lambda _: None):
    """Only public service-owner composition: actual fence, never a Boolean.

    The receipt must be the authenticated release RPC response. No release,
    freeze, stop or route action happens here; the separately instructed owner
    performs those controls and records its natural safe-checkpoint boundary.
    """
    admit(plan, instruction, folder=folder)
    from vk_restart_writer_fence import WriterFence
    from vk_restart_tracking_client import metadata_lane
    fence = WriterFence(plan['writer_fence'], quiet_inventory, released_ownership)
    with metadata_lane(plan['metadata_lane']):
        with fence.held() as verify:
            return run(plan, instruction, folder=folder, verify_fence=verify, report=report)
