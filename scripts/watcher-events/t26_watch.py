#!/usr/bin/env python3
"""T26 runner for the existing PR215 client; shares resource-guard's timer.

No cleanup, steering, server restart or credential acquisition.
Dispatch requires an explicitly enabled native or existing-connector transport.
"""
import argparse
import contextlib
import fcntl
import http.client
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid

import monitor
import pressure

COOLDOWN = 1800
MAX_STATE_BYTES = 8 * 1024 * 1024


def configured_owner(config):
    """Require the reviewed existing-owner binding from private local config.

    Deployment identities are not compiled into public source. Native admission
    still verifies its separate exact saved-owner/configuration binding.
    """
    workspace, session = config['workspace_id'], config['session_id']
    if any(not isinstance(value, str) or str(uuid.UUID(value)) != value
           or uuid.UUID(value).int == 0 for value in (workspace, session)):
        raise ValueError('existing_owner_binding_required')
    return workspace, session


def local_get(path):
    conn = http.client.HTTPConnection('127.0.0.1', 4720, timeout=5)
    try:
        conn.request('GET', path)
        response = conn.getresponse()
        raw = response.read(262145)
        if (response.status != 200 or len(raw) > 262144
                or response.getheader('Content-Type', '').split(';')[0] != 'application/json'):
            raise ValueError('owner_status_unavailable')
        data = json.loads(raw)
        if data.get('success') is not True:
            raise ValueError('owner_status_unavailable')
        return data['data']
    finally:
        conn.close()


def process_identity(proc):
    """Metadata only; never return command lines, environments or open files."""
    before = (proc / 'stat').read_text().rpartition(') ')[2].split()[19]
    value = {'pid': int(proc.name), 'start_ticks': before,
             'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
             'name': (proc / 'comm').read_text().strip(),
             'cgroup': (proc / 'cgroup').read_text().strip()}
    if (proc / 'stat').read_text().rpartition(') ')[2].split()[19] != before:
        raise ValueError('process_identity_changed')
    return value


def ssh_broker_metadata(proc):
    value = process_identity(proc)
    status = dict(line.split(':', 1) for line in (proc / 'status').read_text().splitlines() if ':' in line)
    value.update(uids=[int(n) for n in status['Uid'].split()], parent=int(status['PPid'].strip()))
    return value


def protected_ssh_broker(proc):
    # A root-owned sshd vouches only for its transport broker and direct SFTP
    # subsystem. Shells, Python, agents and all other descendants remain scanned.
    # No sudo, new privilege or generic same-UID/name exclusion is introduced.
    try:
        child = ssh_broker_metadata(proc)
        if child['uids'] != [os.getuid()] * 4 or child['name'] not in {'sshd', 'sftp-server'}:
            return False
        if not child['cgroup'].startswith('0::/user.slice/user-' + str(os.getuid()) + '.slice/session-') or not child['cgroup'].endswith('.scope'):
            return False
        parent = ssh_broker_metadata(Path('/proc') / str(child['parent']))
        if child['name'] == 'sftp-server':
            if parent['name'] != 'sshd' or parent['uids'] != child['uids'] or parent['cgroup'] != child['cgroup']:
                return False
            parent = ssh_broker_metadata(Path('/proc') / str(parent['parent']))
        if parent['name'] != 'sshd' or parent['uids'] != [0] * 4:
            return False
        return ssh_broker_metadata(proc) == child
    except (OSError, ValueError, IndexError, KeyError):
        return False


def reviewed_infrastructure(proc, config):
    # Legacy compatibility helper; the shared owner reader does not use these
    # PID exceptions. Exact reviewed infrastructure identities only, never an
    # unreadable process, a name, or a service cgroup. PID reuse/restart invalidates
    # the exception; any new unreadable process still holds delivery.
    if protected_ssh_broker(proc):
        return True
    rows = config.get('reviewed_infrastructure_processes', [])
    if not isinstance(rows, list) or len(rows) > 128:
        return False
    expected = next((r for r in rows if isinstance(r, dict) and r.get('pid') == int(proc.name)), None)
    if expected is None or not isinstance(expected.get('reason'), str) or not expected['reason']:
        return False
    try:
        return process_identity(proc) == {k: v for k, v in expected.items() if k != 'reason'}
    except (OSError, ValueError, IndexError):
        return False


def owner_status(config):
    import owner_activity
    return owner_activity.inspect(config, api_get=local_get)


def busy(owner):
    import owner_activity
    return owner_activity.busy(owner)


def active(owner):
    # Activity is informative; callers retain pending delivery while busy.
    return any(owner.get(k) for k in ('coding_or_script_turns', 'independent_jobs', 'process_ids'))


def report(samples, history, owner, now):
    lines = ['T26 capacity alert. Decimal GB (1 GB = 1,000,000,000 bytes).',
             'Warning/cleanup-dispatch thresholds only; admission and safety floors are unchanged.']
    for key, sample in sorted(samples.items()):
        available, mount = sample['available'], sample['mount']
        threshold = pressure.DECIMAL_POLICIES[sample['policy']]
        lines.append(f"{key}: {available / 1e9:.3f} GB available ({available} bytes); "
                     f"trigger strictly below {threshold} bytes; "
                     f"total={sample['total_bytes']} bytes; used={sample['used_bytes']} bytes; "
                     f"mount={mount['target']} device={mount['source']} "
                     f"UUID={mount['uuid']} type={mount['fstype']} maj:min={mount['maj:min']}.")
        for label, seconds in (('1min', 60), ('1h', 3600), ('24h', 86400)):
            candidates = [r for r in history if r['at'] <= now - seconds and key in r['volumes']
                          and r['volumes'][key]['identity'] == sample['identity']]
            old = max(candidates, key=lambda r: r['at'], default=None)
            if old is None or now - seconds - old['at'] > 150:
                lines.append(f'{key} {label} growth: baseline unavailable.')
            else:
                delta = old['volumes'][key]['available'] - available
                lines.append(f"{key} {label} net available-space consumption={delta} bytes "
                             f"over {now - old['at']:.0f}s (negative means reclaimed space).")
    lines.append('Owner activity: ' + json.dumps(owner, sort_keys=True))
    lines.append('Request the existing Disk Space owner to revalidate and perform its already-authorized '
                 'cleanup. Preserve sources, histories, recovery data, browser profiles, credentials, '
                 'Staging caches/artifacts and active jobs. No new cleanup worker or broader deletion '
                 'authority; irreplaceable-data actions retain per-action approval. No billing/extras.')
    return '\n'.join(lines)


def atomic_json(path, value):
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    if len(raw) > 65536:
        raise ValueError('bounded_report_limit')
    temp = path.with_suffix('.tmp')
    with temp.open('wb') as stream:
        os.chmod(temp, 0o600)
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)


def root_notification_receipt(config):
    # Existing resource-guard writes these only after a successful ntfy publish.
    root = Path(config['root_notification_state_dir'])
    def small(name):
        with (root / name).open() as stream:
            value = stream.read(65)
        if len(value) > 64:
            raise ValueError('invalid_root_notification_receipt')
        return value.strip()
    level = small('root-headroom-alert-state')
    sent = small('root-headroom-last-alert-at')
    if level not in ('low', 'normal') or not sent.isdecimal():
        raise ValueError('invalid_root_notification_receipt')
    return {'kind': 'low' if level == 'low' else 'recovery', 'sent_at': int(sent)}


def ntfy_wake_samples(store, config, samples, now, receipt_reader=root_notification_receipt):
    if config.get('ntfy_wake') is not True:
        return samples
    result = {}
    for row in store.pending(samples):
        key = row['volume']
        sample = samples[key]
        if sample['policy'] == pressure.OS_DECIMAL:
            try:
                receipt = receipt_reader(config)
                valid = (receipt['kind'] == 'low' and row['opened'] - 30 <= receipt['sent_at'] <= now
                         and now - receipt['sent_at'] <= 420)
            except Exception:
                valid = False
        else:
            phone = store.db.execute('SELECT * FROM phones WHERE volume=?', (key,)).fetchone()
            valid = bool(phone and phone['status'] == 'sent' and phone['level'] == 'warning'
                         and row['opened'] - 30 <= phone['sent'] <= now)
        if valid:
            result[key] = sample
    return result


def cycle(store, config, samples, errors, owner, meta, now, bridge_factory=monitor.Bridge,
          publisher_factory=monitor.publisher, root_receipt_reader=root_notification_receipt):
    store.observations(samples, errors, now)
    # One producer decision feeds the existing ntfy publisher and native wake path.
    # Recovery reaches ntfy only: pending() requires a current low-space decision.
    notifications = {}
    for key, sample in samples.items():
        if not config.get('volumes', {}).get(key, {}).get('phone'):
            continue
        try:
            reminder = config['volumes'][key].get('phone_reminder_seconds', 21600)
            if type(reminder) is not int or not 300 <= reminder <= 86400:
                raise ValueError('invalid_phone_reminder')
            notifications[key] = store.phone(key, sample, publisher_factory(config), now, reminder) or 'no_change'
        except Exception:
            notifications[key] = 'configuration_unavailable'
            with store.db:
                store.audit('phone_config_unavailable', {'volume': key})
    # Upgrade old host-inventory-only waits once, only when no delivery was ever
    # attempted. Never shorten a real receipt/attempt's durable retry delay.
    if meta.get('owner_wait_policy') != 1:
        if not store.db.execute('SELECT 1 FROM attempts LIMIT 1').fetchone() and not store.db.execute('SELECT 1 FROM batches LIMIT 1').fetchone():
            meta.update(next_attempt=0, failures=0)
        meta['owner_wait_policy'] = 1
    # Bound waits across wall-clock regressions; never create a new incident to retry.
    meta['next_attempt'] = min(meta.get('next_attempt', 0), now + 3600)
    if 'last_accepted' in meta:
        meta['last_accepted'] = min(meta['last_accepted'], now)
    history = [r for r in meta.get('history', []) if 0 <= now - r['at'] <= 86550][-1440:]
    text = report(samples, history, owner, now)
    if not history or now - history[-1]['at'] >= 60:
        history.append({'at': now, 'volumes': {k: {p: v[p] for p in ('available', 'identity')}
                                              for k, v in samples.items()}})
    meta.update(history=history, last_read_at=now)
    pending = store.pending(samples)
    wake_samples = ntfy_wake_samples(store, config, samples, now, root_receipt_reader)
    ready_to_wake = store.pending(wake_samples)
    unsettled = store.db.execute("SELECT 1 FROM batches WHERE status IN ('dispatching','unknown','accepted')").fetchone()
    status = 'observation_unknown' if errors else 'healthy_or_episode_already_reported'
    if pending or unsettled:
        if busy(owner):
            status = 'pending_owner_busy_or_inventory_unknown'
        elif now < meta.get('next_attempt', 0):
            status = 'backoff'
        elif not ready_to_wake and not unsettled:
            status = 'pending_ntfy_receipt'
        elif not monitor.transport_enabled(config):
            status = ('pending_connector_activation' if config.get('dispatch_transport') == 'connector-follow-up-v1'
                      else 'pending_native_release_and_binding')
        elif not unsettled and now - meta.get('last_accepted', -COOLDOWN) < COOLDOWN:
            status = 'episode_cooldown'
        else:
            bridge = bridge_factory(config)
            bridge.capacity_report = text
            status = store.dispatch(wake_samples, bridge, Path(config['state_file']))
        if status == 'accepted':
            meta.update(last_accepted=now, failures=0, next_attempt=now + COOLDOWN)
        elif status not in ('backoff', 'pending_owner_busy_or_inventory_unknown'):
            failures = min(meta.get('failures', 0) + 1, 7)
            meta.update(failures=failures, next_attempt=now + min(3600, 60 * 2 ** (failures - 1)))
    else:
        meta.update(failures=0, next_attempt=0)
    return meta, {'at': now, 'status': status, 'pending_incidents': len(store.pending(samples)),
                  'native_transport_enabled': config.get('native_transport', {}).get('enabled') is True,
                  'dispatch_transport': config.get('dispatch_transport', 'storage-admission-v2'),
                  'wake_dispatch_enabled': monitor.transport_enabled(config),
                  'owner': owner, 'errors': errors, 'ntfy': notifications, 'report': text}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args()
    config = monitor.read_config(args.config)
    if 'event_registry' in config:
        import watch_events
        registry = watch_events.Registry(watch_events.read_json(config['event_registry']['path']))
        config = watch_events.disk_config(config, registry)
    configured_owner(config)
    if config.get('ntfy_wake') is True and config['volumes'].get('os', {}).get('phone'):
        raise ValueError('reuse_existing_root_ntfy_producer')
    monitor.observe(config['state_volume'])
    state = Path(config['state_file'])
    if (not state.parent.resolve().is_relative_to(Path(config['state_volume']['path']))
            or monitor.mount(str(state.parent))['uuid'] != config['state_volume']['uuid']):
        raise ValueError('state_mount_mismatch')
    os.umask(0o077)
    with state.with_suffix('.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        with contextlib.closing(monitor.Store(state)) as store:
            # Hard cap; never prune delivery/uncertainty tombstones to gain space.
            page_size = store.db.execute('PRAGMA page_size').fetchone()[0]
            store.db.execute('PRAGMA max_page_count=' + str(MAX_STATE_BYTES // page_size))
            store.db.execute('PRAGMA journal_size_limit=1048576')
            store.db.execute('CREATE TABLE IF NOT EXISTS runtime (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT)')
            saved = store.db.execute('SELECT body FROM runtime WHERE id=1').fetchone()
            meta = json.loads(saved[0]) if saved else {}
            if config.get('dispatch_transport') == 'connector-follow-up-v1':
                try:
                    import connector_adapter
                    connector_adapter.process_probe(config)
                except Exception:
                    # A probe error never disables ordinary observation/alerts.
                    pass
            samples, errors = {}, {}
            for key, volume in config['volumes'].items():
                try:
                    samples[key] = monitor.sample_volume(volume)
                except Exception:
                    errors[key] = 'mount_or_capacity_unavailable'
            try:
                owner = owner_status(config)
            except Exception:
                owner = {'inventory_unknown': True}
            meta, output = cycle(store, config, samples, errors, owner, meta, time.time())
            with store.db:
                store.db.execute('INSERT OR REPLACE INTO runtime VALUES (1,?)', (json.dumps(meta),))
            atomic_json(state.parent / 'latest.json', output)
            if not args.quiet:
                print(json.dumps({k: output[k] for k in ('status', 'pending_incidents', 'native_transport_enabled')}))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # No exception bodies or secrets; no blind resend after failed commits.
        if '--quiet' not in __import__('sys').argv:
            print('{"status":"failed_closed"}')
        raise SystemExit(1)
