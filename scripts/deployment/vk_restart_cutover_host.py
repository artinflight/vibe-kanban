"""Current Nightly final-update adapter over the retained real host transaction.

Import is inert. The independent controller supplies an authenticated manifest,
waits for every coding turn to finish, and calls execute once. No database
restore, model launch, replay acknowledgement or recovery retirement is provided.
"""
from contextlib import contextmanager, ExitStack
from datetime import datetime, timezone, timedelta
from pathlib import Path
import ast
import copy
import hashlib
import importlib.util
import json
import os
import sqlite3
import ssl
import subprocess
import sys
import time


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_references(references):
    for name, ref in references.items():
        if digest(ref['path']) != ref['sha256']:
            raise ValueError('Cutover source or evidence changed: ' + name)


def final_deadlines(start, window_end, *, data_seconds=3000, recovery_seconds=600):
    from vk_restart_manual_update import interruption_budget
    _, _, total_seconds = interruption_budget(dict(maximum_update_seconds=data_seconds,
        switch_smoke_recovery_seconds=recovery_seconds,
        maximum_interruption_seconds=data_seconds+recovery_seconds))
    if (data_seconds, recovery_seconds) not in ((3000, 600), (4500, 900)):
        raise ValueError('Exact reviewed host interruption budget required')
    total_end = min(start + timedelta(seconds=total_seconds), window_end)
    data_end = min(start + timedelta(seconds=data_seconds), total_end-timedelta(seconds=recovery_seconds))
    if (data_end-start).total_seconds() < data_seconds:
        raise ValueError('Insufficient owner-window time for backup and service recovery')
    return data_end, total_end


def validate_final_backup(result, plan_sha):
    restore = result.get('independent_restore', {})
    if (result.get('format') != 'vk-staging-final-update-result-v1'
            or result.get('plan_sha256') != plan_sha
            or result.get('release_backup_accepted') is not True
            or result.get('accepted_current_pointer_modified') is not False
            or result.get('cutover_performed') is not False
            or not all(restore.get(k) is True for k in (
                'independent_composed_restore_verified',
                'normal_leased_consumer_entrypoint_verified',
                'actual_existing_B_backed_consumer_route_verified'))):
        raise ValueError('Actual current composed normal restore acceptance required')
    return result


def metadata_lock_owner(path):
    info=Path(path).stat()
    wanted=(os.major(info.st_dev),os.minor(info.st_dev),info.st_ino)
    for line in Path('/proc/locks').read_text().splitlines():
        fields=line.split()
        if len(fields)<8 or fields[1]!='FLOCK':continue
        device=fields[5].split(':')
        if len(device)==3 and (int(device[0],16),int(device[1],16),int(device[2]))==wanted:
            return int(fields[4])
    return None


@contextmanager
def wait_metadata_lane(path,original,expected,*,guard,report=lambda _:None,
                       maximum_seconds=60,inspect=None,sleep=time.sleep):
    """Wait only before entering the original lane; never retry an operation."""
    if inspect is None:
        from vk_restart_writer_fence import unit_state
        inspect=unit_state
    start=time.monotonic()
    with ExitStack() as stack:
        while True:
            guard()
            try:
                stack.enter_context(original(path));break
            except BlockingIOError:
                owner=metadata_lock_owner(path)
                if owner is not None:
                    actual=inspect(expected['unit'])
                    if (owner!=expected['pid'] or actual.get('MainPID')!=str(expected['pid'])
                            or actual.get('InvocationID')!=expected['invocation']):
                        raise ValueError('Unknown metadata-lane owner; no producer retry')
                if time.monotonic()-start>=maximum_seconds:
                    raise TimeoutError('Finite known metadata-lane admission wait expired')
                report(dict(phase='waiting-known-metadata-follower-before-entry',owner_PID=owner,
                    source_body_bytes_read=0,backup_payload_bytes_copied=0))
                sleep(.25)
        yield


def build_ops(config, base, transaction):
    """Compose the retained tested host methods; never call a legacy actor main."""
    from restart_queue_boundary import inventory, require_dispatch_quiet
    from vk_restart_manual_sql_reuse import authenticate, run_after_pause
    from vk_restart_writer_fence import unit_state, members
    plan = json.loads(Path(config['plan']['path']).read_text())
    source = Path(plan['source_folder'])
    sys.path.insert(0, str(source))
    plan_sha = authenticate(plan, folder=source)
    if plan_sha != config['plan_canonical_sha256']:
        raise ValueError('Exact currently authorized final-update plan required')
    holds=config.get('ingress_start_holds',[])
    if holds:
        if (set(row['unit'] for row in holds)!=set(config['owned_writers'])
                or plan['writer_fence'].get('stopped_unit_start_holds')!=holds):
            raise ValueError('Exact owned-writer start-hold closure required')
        runtime=Path('/run/user')/str(os.getuid())/'systemd/user'
        for row in holds:
            path=Path(row['path'])
            if path.parent!=runtime/(row['unit']+'.d') or not path.name.startswith('90-vk-staging-'):
                raise ValueError('Literal operation-owned runtime drop-in required')
    base.BOUNDARY = Path(config['queue_hooks']).parent
    base.CA = config['CA']
    base.ORIGINAL = Path(config['smoke_source'])
    base.DB = Path(plan['writer_fence']['database'])
    base.ROUTE = Path(plan['route']['path'])
    base.POINTER = Path(config['frontend_pointer'])
    base.META = Path(config['recovery_targets'])
    base.DROPIN = Path(config['dropin'])

    class Controls(base.HostControls):
        def __init__(self):
            super().__init__(final_module_path=config['driver'],
                final_module_sha=digest(config['driver']),
                completed_backup_path=plan['SQL_epoch_reuse']['accepted_checkpoint']['path'],
                completed_backup_sha=plan['SQL_epoch_reuse']['accepted_checkpoint']['sha256'],
                output=Path(config['evidence_output']))
            self.pair = config['pair']
            self.released_response = None
            self.owned_stops = []
            self.owned_start_holds = []
            self.owned_poller_freeze = False
            self.maintenance_started = None
            self.instruction = None
            self.companion_installed = False

        def record(self,phase,value):
            super().record(phase,value)
            state=dict(phase=phase,owned_stops=self.owned_stops,
                owned_poller_freeze=self.owned_poller_freeze,owned_start_holds=self.owned_start_holds,
                released_response=self.released_response,variant=self.variant,
                installed_dropin_sha=self.installed_dropin_sha,
                maintenance_started=self.maintenance_started,
                plan_sha256=plan_sha,controller_pid=os.getpid())
            # Actual proof/restore progress only; no source paths or private state.
            if isinstance(value,dict):
                state['progress_detail']={k:v for k,v in value.items() if k in (
                    'phase','verified_files','verified_raw_bytes','bytes_read',
                    'completed','selected','verified_bytes','elapsed_seconds')
                    and type(v) in (str,int,float,bool)}
            if self.instruction is not None:
                state['data_deadline_UTC']=self.data_end.isoformat() if self.data_end else None
                state['total_deadline_UTC']=self.total_end.isoformat() if self.total_end else None
                state['completion_policy']=plan.get('completion_policy','fixed-deadline')
            base.atomic_bytes(Path(config['runtime_state']),json.dumps(state,sort_keys=True).encode())

        def quiet_boundary(self):
            value=super().quiet_boundary()
            self.quiet_before=value
            return value

        def prepare(self):
            verify_references(config['references'])
            authenticate(plan, folder=source)
            for variant in ('candidate', 'fallback'):
                if digest(self.pair[variant]['path']) != self.pair[variant]['sha256']:
                    raise ValueError('Paired executable changed')
            if digest(base.UNIT_ROOT/base.UNIT) != config['unit_sha256']:
                raise ValueError('Incumbent unit changed')
            if digest(base.DROPIN) != config['dropin_sha256']:
                raise ValueError('Actual enrolled drop-in changed')
            if str(base.POINTER.resolve()) != self.pair['frontend_cutback']:
                raise ValueError('Current full frontend changed')
            for target, previous in config['companion_previous'].items():
                p = Path(target)
                if (digest(p) if p.exists() else None) != previous['sha256']:
                    raise ValueError('Current additive companion baseline changed')
            for row in config.get('ingress_start_holds',[]):
                if Path(row['path']).exists() or Path(row['path']).is_symlink():
                    raise ValueError('Preexisting runtime ingress start hold; reconcile owner')
            self.reader_check()
            return dict(source_verified=True, plan_sha256=plan_sha,
                        service_actions=False, final_backup_update=False)

        def reader_check(self):
            expected = config['protected_reader']
            state = unit_state(expected['unit'])
            if state['MainPID'] != str(expected['wrapper_pid']) or state['InvocationID'] != expected['invocation']:
                raise ValueError('Independent history-reader owner changed')
            if state['ActiveState']!='active' or state['FreezerState']!='running' or expected['server_pid'] not in members(state['ControlGroup']):
                raise ValueError('Protected reader is not actually running in its owned unit')
            status=Path('/proc/'+str(expected['wrapper_pid'])+'/status').read_text()
            if 'NoNewPrivs:\t1' not in status or 'CapEff:\t0000000000000000' not in status or '(enforce)' not in Path('/proc/'+str(expected['wrapper_pid'])+'/attr/current').read_text():
                raise ValueError('Protected reader enforcement changed')
            if digest('/proc/'+str(expected['server_pid'])+'/exe') != expected['server_sha256']:
                raise ValueError('Protected actual reader executable changed')

        def preflight(self):
            self.prepare()
            self.resources()
            available=int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')))*1024
            # Two bounded working API images plus object/control memory, above
            # the existing host floor; configured cgroup cap is not a reservation.
            if available < config['additional_SQL_RAM_peak_bytes']+4294967296:
                raise ValueError('Current SQL phase peak plus original host floor unavailable')
            ram=os.statvfs('/dev/shm')
            if ram.f_bavail*ram.f_frsize < config['SQL_RAM_filesystem_needed_bytes']:
                raise ValueError('Current two-image RAM filesystem admission unavailable')
            self.output.mkdir(mode=0o700, exist_ok=False)
            self.installed_dropin_sha = config['dropin_sha256']
            self.h = base.load(Path(config['release_primitives']), 'current_release_primitives')
            self.boundary = base.load(Path(config['queue_boundary']), 'current_queue_boundary')
            self.queue_namespace = dict(DB=base.DB, PORT=5621, ROUTE=base.ROUTE,
                OLD=base.UNIT, h=self.h, vibe_cgroup_quiet=self.cgroup_quiet)
            base.load(Path(config['queue_hooks']), 'current_queue_hooks').install(self.queue_namespace)
            nodes = [n for n in ast.parse(base.ORIGINAL.read_text()).body
                if isinstance(n, ast.FunctionDef) and n.name in ('routed_get', 'live_acceptance')]
            if len(nodes) != 2:
                raise ValueError('Reviewed public smoke functions missing')
            self.smoke = dict(json=json, ssl=ssl, CA=base.CA, re=__import__('re'),
                time=time, urllib=__import__('urllib'), META=base.META,
                digest=digest, hashlib=hashlib)
            exec(compile(ast.Module(body=nodes, type_ignores=[]),str(base.ORIGINAL),'exec'),self.smoke)
            self.quiet_boundary()
            # Fresh native guards and current demand before any service action.
            from vk_nightly_desktop_controls import DesktopControls
            from vk_nightly_typed_worker import host_guard
            from vk_restart_tracking_client import metadata_lane
            worker = copy.deepcopy(plan['workers']['files'])
            if plan.get('completion_policy')=='until-verified-or-real-safety-failure-v1':
                worker.pop('whole_cycle_deadline_UTC',None)
                for field in ('desktop','B_controls'):worker[field].pop('whole_cycle_deadline_UTC',None)
            else:
                end = (datetime.now(timezone.utc)+timedelta(seconds=120)).isoformat()
                for field in ('desktop','B_controls'):
                    worker[field]['whole_cycle_deadline_UTC'] = end
                worker.update(timeout_seconds=120,whole_cycle_deadline_UTC=end)
            begin=time.monotonic()
            with wait_metadata_lane(plan['metadata_lane'],metadata_lane,config['metadata_follower'],guard=self.resources):
                with DesktopControls(worker['B_controls'],guard=lambda:host_guard(worker,begin)) as remote:
                    db=remote.client.connect(plan['current_map']['index_name'],
                        plan['current_map']['checkpoint_sha256'],readonly=True,working=True)
                    try:
                        demand=remote.client.call(op='member-demand',name=plan['current_map']['index_name'])
                        db.request('check')
                    finally:db.close()
                    # Exercise the actual SQL-reuse read interface before any
                    # writer stop; a malformed handle cannot consume downtime.
                    from vk_restart_sql_adoption import load_checkpoint,open_accepted_SQL_map
                    accepted=load_checkpoint(plan['SQL_epoch_reuse']['accepted_checkpoint'])
                    baseline=open_accepted_SQL_map(remote.client,accepted['candidate']['descriptor']['indexes'][0])
                    try:
                        sql_count=baseline.execute('select count(*) from SQL_sources').fetchone()[0]
                        side_count=baseline.execute("select count(*) from members where state='SQLite-sidecar'").fetchone()[0]
                        baseline.request('check')
                    finally:baseline.close()
                    demand['SQL_reuse_native_readonly_interface']=dict(SQL_sources=sql_count,sidecars=side_count,verified_before_pause=True)
            self.record('native-prepause-admission',demand)
            self.quiet_boundary()  # A new turn during B admission forbids any pause.
            from vk_restart_ingress_hold import install
            self.owned_start_holds=config.get('ingress_start_holds',[])
            install(self.owned_start_holds,record=self.record)
            # Stop only the explicitly inventoried owned ingress writers, after quiet.
            for name,expected in config['owned_writers'].items():
                state=unit_state(name)
                if state['MainPID']!=str(expected['pid']) or state['InvocationID']!=expected['invocation']:
                    raise ValueError('Owned connector writer changed')
                self.owned_stops.append(name)
                self.record('owned-writer-stop-requested',dict(unit=name,identity=state))
                self.h.ctl('stop',name)
                stopped=unit_state(name)
                if stopped['MainPID']!='0' or stopped['ActiveState']!='inactive' or stopped['ControlGroup']:
                    raise ValueError('Owned ingress did not drain')
            self.quiet_boundary()
            self.record('actual-preflight-ready',dict(plan_sha256=plan_sha,
                new_backup_required=True,T18_fix_included=False,owned_stops=self.owned_stops))

        def cgroup_quiet(self):
            state=unit_state(base.UNIT)
            return state['MainPID']==str(config['incumbent']['pid']) and members(state['ControlGroup'])=={config['incumbent']['pid']}

        def live_binding(self):
            state=unit_state(base.UNIT)
            expected=config['incumbent']
            if state['MainPID']!=str(expected['pid']) or state['InvocationID']!=expected['invocation']:
                raise ValueError('Actual incumbent ownership changed')
            pid=state['MainPID']
            if digest('/proc/'+pid+'/exe')!=expected['sha256']:
                raise ValueError('Incumbent executable changed')
            ticks=Path('/proc/'+pid+'/stat').read_text().rsplit(')',1)[1].split()[19]
            if ticks!=expected['start_ticks']:
                raise ValueError('Incumbent process lifetime changed')
            self.reader_check()
            info=base.DB.stat()
            return dict(PID=int(pid),start_ticks=ticks,database=[info.st_dev,info.st_ino])

        def check_forward(self):
            self.reader_check()  # No ADB route exists or is created by this operation.

        def restore_existing_idle_forward(self):
            self.reader_check()

        def route_maintenance(self):
            if self.maintenance_started is None:
                now=datetime.now(timezone.utc)
                if config.get('not_before_UTC') and now < datetime.fromisoformat(config['not_before_UTC']):
                    raise ValueError('Owner window has not begun')
                if plan.get('completion_policy')=='until-verified-or-real-safety-failure-v1':
                    data_end=total_end=None
                else:
                    data_end,total_end=final_deadlines(now,datetime.fromisoformat(config['window_end_UTC']),
                        data_seconds=plan['maximum_update_seconds'],
                        recovery_seconds=plan['switch_smoke_recovery_seconds'])
                self.maintenance_started=time.monotonic()
                self.data_end=data_end;self.total_end=total_end
                self.instruction=dict(operator='Seamus',pause_confirmed=True,
                    instruction_reference=config['operator_instruction_reference'],
                    plan_sha256=plan_sha,deadline_UTC=data_end.isoformat() if data_end else None)
                if data_end is None:self.instruction['completion_policy']=plan['completion_policy']
            base.atomic_bytes(base.ROUTE,plan['route']['maintenance_bytes'].encode())

        def route_serving(self):
            base.atomic_bytes(base.ROUTE,plan['route']['serving_bytes'].encode())

        def restore_route(self,route):
            if route!=json.loads(plan['route']['serving_bytes']):
                raise ValueError('Only the exact preserved incumbent route may be restored')
            base.atomic_bytes(base.ROUTE,plan['route']['serving_bytes'].encode())

        def release_ownership(self):
            current=self.h.ownership(5621)
            if not current['owned'] or any(g.get('grant') is not None for g in current['state']['goals'].values()):
                raise ValueError('Actual owner/grants not quiet')
            released=self.h.ownership(5621,'release',current['state'])
            if released.get('owned') is not False:
                raise ValueError('Authenticated ownership release did not complete')
            self.released_response=released
            return released['state']

        def freeze_incumbent(self):
            name='fitrdy-manager.service';expected=plan['writer_fence']['frozen_units'][name]
            state=unit_state(name)
            if state['MainPID']!=str(expected['pid']) or state['InvocationID']!=expected['invocation'] or members(state['ControlGroup'])!={expected['pid']}:
                raise ValueError('Git-fetching poller not naturally drained')
            self.owned_poller_freeze=True
            self.record('owned-poller-freeze-requested',dict(unit=name,identity=state))
            self.h.ctl('freeze',name)
            self.h.ctl('freeze',base.UNIT)

        def verify_frozen_boundary(self,before):
            from vk_restart_writer_fence import WriterFence
            # Outside the actual retained lease, inspect controls and exact DB/queues.
            fence=WriterFence(plan['writer_fence'],before,self.released_response)
            fence.controls()
            return self.boundary.frozen(base.DB,before,incumbent_frozen=True,consumers_quiet=True)

        def semantic_snapshot(self):
            result=super().semantic_snapshot()
            review=base.load(Path(config['review_projection']),'current_review_projection')
            value=review.capture(base.DB,'Existing authorized full-SQL preservation projection; no separate export')
            review.verify_api_identity(value,review.api_state('http://127.0.0.1:5621'))
            if not value['review_journal_enabled']:
                raise ValueError('Review journal unavailable')
            self.semantic_before=result
            self.review_before=hashlib.sha256(json.dumps(value['tables'],sort_keys=True).encode()).hexdigest()
            return result

        def verify_semantics(self,before):
            super().verify_semantics(before)
            review=base.load(Path(config['review_projection']),'current_review_check')
            value=review.capture(base.DB,'Current preservation check only; no separate export')
            if hashlib.sha256(json.dumps(value['tables'],sort_keys=True).encode()).hexdigest()!=self.review_before:
                raise ValueError('Current review flags or identity mappings changed')

        def recovery_payloads(self,packet,restore):
            from vk_restart_recovery_control import records
            canonical=lambda v:json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
            payloads={'consumer-packet.json':canonical(packet),
                'accepted-normal-restore.json':canonical(restore),
                'provider-config.json':canonical(dict(B_controls=plan['workers']['files']['B_controls'],
                    desktop=plan['workers']['files']['desktop'],consumer=plan['consumer']))}
            for name,sha in plan['source_sha256'].items():
                path=source/name
                if digest(path)!=sha:raise ValueError('Recovery source changed')
                payloads['nightly-'+name]=path.read_bytes()
            for name,ref in config['recovery_source_refs'].items():
                if digest(ref['path'])!=ref['sha256']:raise ValueError('Recovery adapter source changed')
                payloads['host-'+name]=Path(ref['path']).read_bytes()
            payloads['RECOVERY.txt']=(
                'Native Desktop B recovery control. Original retained sets, gaps and later writes remain explicit.\n'
                'Extract only literal verified record names; verify every SHA256. No credentials or review projection are embedded.\n'
                'Use the preserved normal leased consumer, immutable packet descriptor/content proof and actual provider placement.\n'
                'A future restore requires fresh native identity/health/STOP/capacity/admission and fresh bounded deadlines; never reuse expired authority.\n'
                'Restore into a detached approved target. Never overwrite current live data from an older backup.\n'
                'Re-enroll a replacement host rather than bypass source, database-inode, dataset or startup guards.\n'
                'Retain candidate/fallback artifacts and original recovery. T18 helper publication is separate.\n').encode()
            rows=records(payloads)
            payloads['source-manifest.json']=canonical(dict(format='vk-release-recovery-source-manifest-v1',
                records=[dict(name=n,sha256=sha,bytes=len(raw)) for n,sha,raw in rows],
                no_prompts_or_credentials_or_review_projection=True))
            records(payloads)
            return payloads

        def seal_final_recovery_control(self,value,boundary):
            from vk_restart_recovery_control import write_control,independently_reopen
            from vk_restart_writer_fence import WriterFence
            from vk_restart_tracking_client import metadata_lane
            from vk_nightly_desktop_controls import DesktopControls
            from vk_nightly_typed_worker import host_guard
            from vk_nightly_b_controls import seed
            payloads=self.recovery_payloads(value['consumer_packet'],value['independent_restore'])
            worker=copy.deepcopy(plan['workers']['files'])
            for field in ('desktop','B_controls'):
                if self.instruction['deadline_UTC']:worker[field]['whole_cycle_deadline_UTC']=self.instruction['deadline_UTC']
                else:worker[field].pop('whole_cycle_deadline_UTC',None)
            if self.instruction['deadline_UTC'] is None:
                worker.pop('whole_cycle_deadline_UTC',None)
                worker['completion_policy']=plan['completion_policy']
            else:
                worker.update(timeout_seconds=plan['maximum_update_seconds'],whole_cycle_deadline_UTC=self.instruction['deadline_UTC'])
            started=time.monotonic()
            fence=WriterFence(plan['writer_fence'],boundary,self.released_response)
            with fence.held() as check:
                def guard():host_guard(worker,started);check()
                with wait_metadata_lane(plan['metadata_lane'],metadata_lane,config['metadata_follower'],guard=guard):
                    binding=dict(format='vk-final-release-recovery-control-v1',plan_sha256=plan_sha,
                        packet_sha256=hashlib.sha256(payloads['consumer-packet.json']).hexdigest(),
                        source_manifest_sha256=hashlib.sha256(payloads['source-manifest.json']).hexdigest())
                    with DesktopControls(worker['B_controls'],guard=guard) as remote:
                        ref=write_control(remote.client,config['final_recovery_control_key'],seed(remote.client),
                            payloads,binding,guard=guard,report=lambda v:self.record('final-recovery-control-progress',v))
                    with DesktopControls(worker['B_controls'],guard=guard) as remote:
                        accepted=independently_reopen(remote.client,ref,payloads,guard=guard)
                    check()
            self.record('durable-final-B-recovery-control',accepted)
            return accepted

        def final_current_backup(self,boundary,released,semantic):
            self.verify_frozen_boundary(boundary)
            import vk_restart_tracking_client as tracking
            original_lane=tracking.metadata_lane
            def admitted_lane(path):
                return wait_metadata_lane(path,original_lane,config['metadata_follower'],
                    guard=lambda:self.verify_frozen_boundary(boundary),
                    report=lambda v:self.record('final-metadata-admission-wait',v))
            tracking.metadata_lane=admitted_lane
            try:
                value=run_after_pause(plan,self.instruction,folder=source,
                    quiet_inventory=boundary,released_ownership=self.released_response,
                    report=lambda value:self.record('final-data-progress',value))
            finally:
                changed=tracking.metadata_lane is not admitted_lane
                tracking.metadata_lane=original_lane
                if changed:raise ValueError('Concurrent metadata admission replacement; no acceptance')
            validate_final_backup(value,plan_sha)
            value['durable_B_recovery_control']=self.seal_final_recovery_control(value,boundary)
            self.record('final-current-backup-accepted',value)
            return value

        def verify_final_current_backup(self,packet,boundary,released,semantic):
            validate_final_backup(packet,plan_sha)
            if packet.get('durable_B_recovery_control',{}).get('independent_native_reopen_verified') is not True:
                raise ValueError('Final recovery control not independently available on Desktop B')
            self.verify_frozen_boundary(boundary)
            self.verify_semantics(semantic)

        def stop_incumbent(self):
            if self.total_end is not None and (self.total_end-datetime.now(timezone.utc)).total_seconds()<plan['switch_smoke_recovery_seconds']:
                raise ValueError('Insufficient remaining switch/recovery time; preserve incumbent')
            self.thaw_if_frozen()
            self.h.ctl('stop',base.UNIT)

        def install_variant(self,variant):
            if variant not in ('candidate','fallback'):
                raise ValueError('Unknown exact variant')
            self.verify_incumbent_terminal()
            if digest(base.DROPIN)!=self.installed_dropin_sha:
                raise ValueError('Drop-in changed outside this transaction')
            staged=Path(config['staged_dropins'][variant])
            base.atomic_bytes(base.DROPIN,staged.read_bytes())
            self.installed_dropin_sha=digest(staged)
            subprocess.run(['systemctl','--user','daemon-reload'],check=True,timeout=20)
            self.variant=variant

        def recovery_acceptance(self,variant):
            super().recovery_acceptance(variant)
            self.reader_check()
            if variant=='candidate':
                value=self.h.read_api(5621,'issue-workflows/capabilities')
                if value.get('success') is not True or value['data'].get('version')!=1:
                    raise ValueError('Issue workflow APIv1 missing')
            from vk_restart_history_acceptance import bind_database, verify_history
            recent = config.get('recent_histories', [])
            bound = bind_database(base.DB, [row['execution'] for row in recent])
            for expected, actual in zip(recent, bound):
                # Older manifests hashed the annotated SQL summary. Authenticate
                # that exact summary, then compare only the original reply to
                # the durable history. Preserve checkpoint and review metadata.
                expected_summary = expected.get('summary_sha256', expected['selected_final_sha256'])
                if actual['summary_sha256'] != expected_summary:
                    raise ValueError('Selected summary changed since the admitted boundary')
                verify_history(lambda path: self.h.read_api(5621, path), actual)
            self.record('direct-release-acceptance',dict(variant=variant,
                protected_recovery_verified=True,issue_workflow_v1=variant=='candidate',T18_fix_included=False))

        def verify_public_review(self):
            # Public traffic may legitimately touch workspace timestamps or
            # append received inputs after ownership and routing are restored.
            # Exact pre-publication semantic verification remains mandatory;
            # afterwards compare current API identity/review state to the current
            # database, rather than treating new activity as data loss.
            review=base.load(Path(config['review_projection']),'public_review_projection')
            current=review.capture(base.DB,'Read-only post-publication identity verification')
            if not current['review_journal_enabled']:
                raise ValueError('Review journal unavailable after publication')
            review.verify_api_identity(current,review.api_state('http://127.0.0.1:5621'))
            return dict(review_journal_enabled=True,current_review_identity_verified=True)

        def https_acceptance(self,variant,before):
            super().https_acceptance(variant,before)
            ref=config['browser_smoke']
            if digest(ref['path'])!=ref['sha256']:
                raise ValueError('Pinned browser smoke changed')
            output=Path(config['browser_output_'+variant])
            subprocess.run(['/usr/bin/node',ref['path'],str(output)],check=True,timeout=90)
            value=json.loads(output.read_text())
            if value.get('passed') is not True or [r['width'] for r in value['results']]!=[1440,390]:
                raise ValueError('Actual desktop/mobile application acceptance missing')
            self.verify_public_review()
            self.record('actual-browser-acceptance',dict(variant=variant,receipt_path=str(output),
                receipt_sha256=digest(output),desktop_and_mobile_rendered=True,UI_writes_blocked=True))

        def install_companion(self):
            targets=sorted(config['companion_previous'],key=lambda p:p.endswith('/adapter.py'))
            staged=[]
            for target in targets:
                previous=config['companion_previous'][target];path=Path(target)
                if (digest(path) if path.exists() else None)!=previous['sha256']:
                    raise ValueError('Companion changed since admission')
                source_path=Path(config['companion_forward'][target])
                expected=config['companion_forward_sha256'][target]
                if digest(source_path)!=expected:
                    raise ValueError('Prepared companion changed')
                staged.append((path,source_path,previous))
            # New support modules first, facade last. Preserve every old source.
            for path,source_path,previous in staged:
                base.atomic_bytes(path,source_path.read_bytes())
                os.chmod(path,previous['mode'] or 0o600)
            self.companion_installed=True

        def resume_owned_consumers(self,success):
            # Validate stopped ownership before removing our start refusal.
            # A subsequent systemctl start is idempotent if boot recovery wins
            # the desired start race after this explicit release.
            for name in self.owned_stops:
                state=unit_state(name);expected=config['owned_writers'][name]
                if state['MainPID']==str(expected['pid']) and state['InvocationID']==expected['invocation'] and state['ActiveState']=='active':continue
                if state['MainPID']!='0' or state['ActiveState']!='inactive':
                    raise ValueError('Do not replace an externally changed ingress owner')
            if self.owned_poller_freeze:
                state=unit_state('fitrdy-manager.service')
                expected=plan['writer_fence']['frozen_units']['fitrdy-manager.service']
                if state['MainPID']!=str(expected['pid']) or state['InvocationID']!=expected['invocation']:
                    raise ValueError('Do not thaw a different poller owner')
                self.h.ctl('thaw','fitrdy-manager.service');self.owned_poller_freeze=False
            if success:self.install_companion()
            from vk_restart_ingress_hold import release
            release(self.owned_start_holds);self.owned_start_holds=[]
            for name in self.owned_stops:
                self.h.ctl('start',name)
                state=unit_state(name)
                if state['ActiveState']!='active' or state['MainPID']=='0':
                    raise ValueError('Desired ingress writer failed to start')
            self.owned_stops.clear()
            self.record('owned-consumers-resumed',dict(success=success,
                additive_companion_installed=self.companion_installed,T18_reader_untouched=True,
                runtime_start_holds_removed=True))

    return Controls()
