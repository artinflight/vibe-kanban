"""Explicit volume policies. SSD tuning and cadence tolerance are proposals, not active policy."""

GIB = 1024**3
MIB = 1024**2
SSD_FLOOR = 2 * GIB  # Existing owner-confirmed floor.
SSD_PROPOSAL = {
    'critical_buffer_bytes': 256 * MIB, 'critical_samples': 2,
    'recovery_buffer_bytes': 512 * MIB, 'recovery_samples': 3,
    'sample_interval_seconds': 60, 'max_sample_gap_seconds': 90,
}
OS = 'os_percent'
SSD = 'ssd_headroom_proposal_v1'


def percent_level(percent):
    return next((name for boundary, name in ((97, 'emergency'), (92, 'critical'),
                                            (85, 'warning')) if percent >= boundary), 'normal')


def advance(previous, sample, periodic=True):
    """A revalidation read can change eligibility but never supplies an extra debounce sample."""
    policy = sample['policy']
    if policy == OS:
        p = sample['percent']
        return {}, {'severity': percent_level(p), 'eligible': p >= 92,
                    'recovered': p <= 83, 'reason': 'os_percentage'}
    if policy != SSD:
        raise ValueError('unknown_volume_policy')
    state = dict(previous)
    if state.get('identity', sample['identity']) != sample['identity']:
        raise ValueError('volume_identity_changed')
    state['identity'] = sample['identity']
    state.setdefault('critical_count', 0)
    state.setdefault('recovery_count', 0)
    state.setdefault('latched', False)
    at = sample['at']
    free = sample['available']
    if type(free) is not int or free < 0:
        raise ValueError('invalid_available_bytes')
    accounting = sample.get('accounting', {})
    known = (accounting.get('status') == 'known'
             and type(accounting.get('remaining_future_bytes')) is int
             and accounting['remaining_future_bytes'] >= 0
             and accounting.get('observed_at', at + 1) <= at
             and at < accounting.get('valid_until', 0))
    if known:
        # A producer snapshot ID is immutable; do not use a replay/regression as recovery evidence.
        if (accounting['observed_at'] < state.get('accounting_observed_at', 0)
                or (accounting.get('snapshot_id') == state.get('accounting_snapshot_id')
                    and accounting.get('snapshot_sha256') != state.get('accounting_snapshot_sha256'))):
            known = False
        else:
            state.update(accounting_observed_at=accounting['observed_at'],
                         accounting_snapshot_id=accounting.get('snapshot_id'),
                         accounting_snapshot_sha256=accounting.get('snapshot_sha256'))
    headroom = free - SSD_FLOOR - accounting['remaining_future_bytes'] if known else None
    last = state.get('last_sample_at')
    delta = at - last if last is not None else None
    count = periodic and (last is None or delta >= SSD_PROPOSAL['sample_interval_seconds'])
    if delta is not None and (delta < 0 or delta > SSD_PROPOSAL['max_sample_gap_seconds']):
        state.update(critical_count=0, recovery_count=0)
        if delta < 0:
            count = False
    if not known:
        state.update(critical_count=0, recovery_count=0)
        # No unknown observation contributes to either consecutive run.
        state.pop('last_sample_at', None)
    immediate = free <= SSD_FLOOR or (known and headroom < 0)
    reason = 'physical_floor' if free <= SSD_FLOOR else 'accounting_unknown'
    recovered = False
    if immediate:
        state.update(latched=True, critical_count=0, recovery_count=0)
        if periodic:
            state['last_sample_at'] = at
        reason = 'physical_floor' if free <= SSD_FLOOR else 'negative_headroom'
    elif known:
        reason = 'headroom_hysteresis'
        if count:
            state['last_sample_at'] = at
            if headroom <= SSD_PROPOSAL['critical_buffer_bytes']:
                state['critical_count'] += 1
                state['recovery_count'] = 0
                if state['critical_count'] >= SSD_PROPOSAL['critical_samples']:
                    state['latched'] = True
            elif headroom >= SSD_PROPOSAL['recovery_buffer_bytes']:
                state['critical_count'] = 0
                state['recovery_count'] += 1
                if state['recovery_count'] >= SSD_PROPOSAL['recovery_samples']:
                    recovered = True
                    state['latched'] = False
            else:
                state.update(critical_count=0, recovery_count=0)
        elif headroom > SSD_PROPOSAL['critical_buffer_bytes']:
            state['critical_count'] = 0
        # Contrary revalidation evidence breaks recovery even between timer samples.
        if headroom < SSD_PROPOSAL['recovery_buffer_bytes']:
            state['recovery_count'] = 0
    severity = 'critical' if immediate or (known and state['latched']) else 'normal' if known else 'unknown'
    return state, {'severity': severity, 'eligible': severity == 'critical', 'recovered': recovered,
                   'reason': reason, 'available_bytes': free, 'floor_bytes': SSD_FLOOR,
                   'headroom_bytes': headroom, 'accounting_status': 'known' if known else 'unknown',
                   'critical_count': state['critical_count'], 'recovery_count': state['recovery_count']}


def break_run(previous):
    state = dict(previous)
    state.update(critical_count=0, recovery_count=0)
    state.pop('last_sample_at', None)
    return state
