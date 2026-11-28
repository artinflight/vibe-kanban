#!/usr/bin/env python3
"""T26 runner for the existing PR215 client; shares resource-guard's timer.

No cleanup, ordinary follow-up, steering, server restart or credential access.
Production dispatch stays gated until native admission is actually released.
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


def owner_status(config):
    """Read coding/script turns, independent Codex jobs, queues and OS processes.

    Never turn an unreadable inventory into idle. Only IDs/counts cross into state.
    Native atomic admission is still required after this advisory preflight.
    """
    result = {'coding_or_script_turns': [], 'independent_jobs': [], 'queued': [],
              'process_ids': [], 'inventory_unknown': False}
    workspace, session = configured_owner(config)
    path = Path(config['vibe_db']).resolve(strict=True)
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=0.2) as db:
        db.execute('PRAGMA query_only=ON')
        deadline = time.monotonic() + 2
        db.set_progress_handler(lambda: int(time.monotonic() > deadline), 10000)
        rows = db.execute('SELECT id FROM sessions WHERE workspace_id=? LIMIT 17',
                          (uuid.UUID(workspace).bytes,)).fetchall()
        if not rows or len(rows) > 16 or uuid.UUID(session).bytes not in [r[0] for r in rows]:
            raise ValueError('owner_binding_unavailable')
        result['coding_or_script_turns'] = [str(uuid.UUID(bytes=r[0])) for r in db.execute(
            "SELECT e.id FROM execution_processes e JOIN sessions s ON s.id=e.session_id "
            "WHERE s.workspace_id=? AND e.status='running' AND e.run_reason != 'devserver' LIMIT 128", (uuid.UUID(workspace).bytes,))]
    for row in rows:
        sid = str(uuid.UUID(bytes=row[0]))
        jobs = local_get('/api/execution-processes/subagents/session?session_id=' + sid)
        if not isinstance(jobs, list) or len(jobs) > 128:
            raise ValueError('job_inventory_unavailable')
        for job in jobs:
            if job.get('status') == 'running':
                result['independent_jobs'].append(str(job['id']))
            elif job.get('status') not in ('completed', 'failed'):
                result['inventory_unknown'] = True
        queue = local_get('/api/sessions/' + sid + '/queue')
        if not isinstance(queue, dict) or queue.get('status') not in ('empty', 'queued'):
            raise ValueError('queue_inventory_unavailable')
        if queue['status'] != 'empty':
            result['queued'].append(sid)
    roots = [str(Path(p).resolve(strict=True)) for p in config['owner_roots']]
    for proc in Path('/proc').iterdir():
        if not proc.name.isdecimal() or int(proc.name) == os.getpid():
            continue
        try:
            if proc.stat().st_uid != os.getuid():
                continue
            cwd = os.readlink(proc / 'cwd')
            # Inspect only for exact owned path references; never retain arguments.
            with (proc / 'cmdline').open('rb') as stream:
                args = stream.read(65536)
            if any(cwd == r or cwd.startswith(r + '/') or r.encode() in args for r in roots):
                result['process_ids'].append(int(proc.name))
        except (FileNotFoundError, ProcessLookupError):
            pass
        except PermissionError:
            result['inventory_unknown'] = True
    return result


def busy(owner):
    return owner.get('inventory_unknown', True) or any(owner.get(k) for k in
        ('coding_or_script_turns', 'independent_jobs', 'queued', 'process_ids'))


def active(owner):
    # Positive activity suppresses this episode; unknown alone never proves active.
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
    covered = bool(pending and active(owner))
    if covered:
        store.cover_active_owner(pending)
        pending = store.pending(samples)
    wake_samples = ntfy_wake_samples(store, config, samples, now, root_receipt_reader)
    ready_to_wake = store.pending(wake_samples)
    unsettled = store.db.execute("SELECT 1 FROM batches WHERE status IN ('dispatching','unknown','accepted')").fetchone()
    status = ('suppressed_active_owner' if covered else
              'observation_unknown' if errors else 'healthy_or_episode_already_reported')
    if pending or unsettled:
        if now < meta.get('next_attempt', 0):
            status = 'backoff'
        elif not ready_to_wake and not unsettled:
            status = 'pending_ntfy_receipt'
        elif busy(owner):
            status = 'pending_owner_busy_or_inventory_unknown'
        elif config.get('native_transport', {}).get('enabled') is not True:
            status = 'pending_native_release_and_binding'
        elif not unsettled and now - meta.get('last_accepted', -COOLDOWN) < COOLDOWN:
            status = 'episode_cooldown'
        else:
            bridge = bridge_factory(config)
            bridge.capacity_report = text
            status = store.dispatch(wake_samples, bridge, Path(config['state_file']))
        if status == 'accepted':
            meta.update(last_accepted=now, failures=0, next_attempt=now + COOLDOWN)
        elif status != 'backoff':
            failures = min(meta.get('failures', 0) + 1, 7)
            meta.update(failures=failures, next_attempt=now + min(3600, 60 * 2 ** (failures - 1)))
    else:
        meta.update(failures=0, next_attempt=0)
    return meta, {'at': now, 'status': status, 'pending_incidents': len(pending),
                  'native_transport_enabled': config.get('native_transport', {}).get('enabled') is True,
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
