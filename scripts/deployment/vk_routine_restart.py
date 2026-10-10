"""Bounded orchestration around Staging's existing current-data handover driver.

No production driver, shell executor, restoration or retirement is supplied here.
Review is an operational gate, not a security boundary between same-UID agents.
"""
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import sqlite3
import time


def plan_digest(plan):
    return hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class Blocked(ValueError):
    pass


def require(value, reason):
    if not value:
        raise Blocked(reason)


def execution_inventory(database):
    """Read real lifecycle rows; never manufacture completion to satisfy release."""
    with sqlite3.connect(Path(database).absolute().as_uri() + '?mode=ro', uri=True) as connection:
        return [row[0] for row in connection.execute(
            "SELECT lower(hex(id)) FROM execution_processes WHERE status='running' AND dropped=0 ORDER BY id")]


def wait_for_real_drain(read_inventory, preparation_execution_hex, deadline_monotonic,
                        *, clock=time.monotonic, sleep=time.sleep):
    """Called by the already authorized unprivileged queue/service, not an agent.

    Overall deadline comes from FIX READY. A new user execution blocks rather
    than being interrupted; the existing ownership API remains the atomic gate.
    """
    require(isinstance(preparation_execution_hex, str) and len(preparation_execution_hex) == 32
            and all(ch in '0123456789abcdef' for ch in preparation_execution_hex),
            'exact existing preparation execution identity required')
    while True:
        require(clock() < deadline_monotonic, 'real preparation execution did not drain before total pipeline deadline')
        active = read_inventory()
        if not active:
            return {'real_execution_drained': True, 'status_rows_changed': False}
        require(active == [preparation_execution_hex], 'new active production work arrived; leave current owner usable')
        sleep(min(0.5, max(0, deadline_monotonic - clock())))


def run(plan, driver, *, fix_ready_monotonic, clock=time.monotonic, budget_seconds=600, git_boundary=None):
    """Prepare while incumbent serves; hand over only under the existing gates.

    Driver methods are trusted source adapters, never manifest command strings.
    held() must hold the existing preparation lease. boundary() must authenticate
    live ownership and prevent admission races using the existing ownership API.
    handover() and recover_latest() retain the existing CandidateController/
    ownership/fallback contracts; this wrapper cannot supply those guarantees.
    """
    started = fix_ready_monotonic
    stages = {}
    phase = 'policy'
    touched = False
    expected = plan_digest(plan)

    def remaining():
        value = budget_seconds - (clock() - started)
        require(value > 0, 'routine preparation budget exhausted; incumbent must stay usable')
        return value

    def measured(name, callback):
        nonlocal phase
        phase = name
        before = clock()
        try:
            return callback()
        finally:
            stages[name] = clock() - before

    try:
        require(type(started) in (int, float) and 0 <= started <= clock(),
                'same-host FIX READY monotonic timestamp required; queue/build time cannot be excluded')
        require(type(budget_seconds) in (int, float) and 0 < budget_seconds <= 600,
                'routine restart goal must not exceed ten minutes')
        require(plan.get('route') == 'authoritative-current-data', 'restoration is a separate disaster-recovery operation')
        require(plan.get('retire_paths') == [], 'routine restart cannot require retirement or protected consumer inspection')
        require(plan.get('cleanup_enabled') is False, 'cleanup must remain disabled until separate human QA')
        require(plan.get('fallback_compatible') is True, 'latest-data compatible fallback required')
        require(plan.get('action_authorized') is True, 'specific handover authorization missing')
        require(type(plan.get('git_activation', False)) is bool, 'explicit Git activation mode required')
        if plan.get('git_activation') is True:
            from vk_restart_git_boundary import HeldGitCheck
            require(isinstance(git_boundary, HeldGitCheck), 'held Git check-all adapter missing')
        authorization = driver.authorization(plan)
        require(authorization.get('authenticated_owner_approval') is True
                and authorization.get('authorized_plan_sha256') == expected,
                'existing authenticated action approval must bind the exact plan; a manifest boolean is insufficient')
        package = measured('release_build', lambda: driver.build(plan, remaining()))
        validation = measured('validation_and_migration', lambda: driver.validate(plan, package, remaining()))
        require(package.get('plan_sha256') == expected and package.get('verified') is True,
                'package/migration preparation is not bound to this plan')
        require(validation.get('plan_sha256') == expected and validation.get('passed') is True,
                'release validation/migration did not pass for this plan')
        if plan.get('deployment_kind') == 'frontend-only':
            require(validation.get('backend_unchanged') is True and validation.get('backend_api_compatible') is True,
                    'frontend-only route requires actual backend identity and API compatibility')
        backup = measured('backup', lambda: driver.backup(plan, package, remaining()))
        require(backup.get('desktop_verified') is True and backup.get('integrity') == 'ok'
                and backup.get('full_baseline_retained') is True
                and backup.get('plan_sha256') == expected,
                'B primary-DB preimage and retained full baseline required; DB-only is not whole-state backup')
        review = measured('independent_review', lambda: driver.review(plan, package, backup, remaining()))
        require(review.get('approved_plan_sha256') == expected and review.get('passed') is True,
                'independent review is absent or refers to a different plan')
        remaining()
        prepared_seconds = clock() - started
        switch_started = clock()
        phase = 'held_boundary'
        with driver.held(plan):
            status = driver.boundary(plan, package, backup)
            require(plan_digest(plan) == expected, 'plan changed during preparation')
            require(status.get('authenticated_owner') is True and status.get('lease_held') is True
                    and status.get('active_executions') == [] and status.get('identity_pins_match') is True,
                    'live ownership, identities, lease or real execution drain failed')
            remaining()
            # All package hashes/network preparation/review are complete. The
            # existing handover owns its final fenced B snapshot and API gates.
            gate = git_boundary.held(remaining) if plan.get('git_activation') is True else nullcontext(None)
            phase = 'git_check_all' if plan.get('git_activation') is True else phase
            with gate as git_witness:
                action_budget = remaining()
                touched = True
                receipt = measured('handover', lambda: driver.handover(
                    plan, package, backup, action_budget, **({'git_boundary': git_witness} if git_witness is not None else {})))
                require(receipt.get('plan_sha256') == expected and receipt.get('live_acceptance') is True
                        and receipt.get('latest_data_preserved') is True
                        and receipt.get('fallback_retained') is True and receipt.get('cleanup_enabled') is False
                        and receipt.get('blocked_work_resumed') is True,
                        'handover acceptance incomplete; retain latest data and fallback')
                if git_witness is not None:
                    require(receipt.get('git_boundary') == git_witness,
                            'handover omitted or changed pinned Git witness')
        return {'passed': True, 'plan_sha256': expected, 'stages_seconds': stages,
                'total_seconds': clock() - started, 'routine_goal_seconds': budget_seconds,
                'preparation_seconds': prepared_seconds, 'switch_seconds': clock() - switch_started,
                'goal_met': clock() - started <= budget_seconds,
                'measurement_boundary': 'FIX READY through release build, validation, handover and blocked work resumed',
                'receipt': receipt}
    except Exception as error:
        recovery = None
        if touched:
            try:
                with driver.held(plan):
                    recovery = driver.recover_latest(plan)
            except Exception as recovery_error:
                recovery = {'held': True, 'error_type': type(recovery_error).__name__}
        return {'passed': False, 'failed_stage': phase, 'reason': str(error),
                'error_type': type(error).__name__, 'stages_seconds': stages,
                'total_seconds': clock() - started, 'production_action_attempted': touched,
                'recovery': recovery, 'next_action': 'Staging: inspect failed stage; preserve latest data, fallback and evidence',
                'operator_command_requested': False}
