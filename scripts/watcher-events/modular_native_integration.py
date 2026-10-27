#!/usr/bin/env python3
"""Current module against the real, ephemeral cfg(test) native router.

Only executor/process I/O and capacity/owner observations are synthetic. Native
admission, queues, approval bridge, SQLite and receipts are real. No live target,
credential, model, notification server, disk manipulation or service is used.
"""
import copy
import http.client
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch
from urllib.parse import urlsplit
import uuid

import monitor
import native_adapter as native
import native_http
import pressure
import t26_watch
import watch_events


def run(d):
    assert d['fixture_protocol'] == 'modular-native-fixture-v1'
    url = urlsplit(d['base_url'])
    assert (url.scheme == 'http' and url.hostname == '127.0.0.1'
            and url.port not in (None, 80, 443, 4720) and url.path == '/api'
            and not (url.username or url.password or url.query or url.fragment))
    assert d['control_url'] == f'http://{url.netloc}/__fixture'
    root = Path(d['state_root']).resolve()
    assert os.environ.get('VK_STORAGE_TEST_CHILD') == 'native_modular_watchers_decimal_disks_and_hot_second_connection'
    assert root.is_dir() and Path(d['owner_file']).resolve() == Path(os.environ['VK_STORAGE_ALERT_OWNER_FILE']).resolve()
    assert Path(d['owner_file']).resolve().parent == Path(os.environ['CODEX_HOME']).resolve().parent
    counts = {'POST': 0, 'GET': 0}
    checks = []
    idle = {'inventory_unknown': False, 'coding_or_script_turns': [],
            'independent_jobs': [], 'queued': [], 'process_ids': []}

    def connection(host, port, timeout):
        assert (host, port) == ('127.0.0.1', 4720)
        return http.client.HTTPConnection('127.0.0.1', url.port, timeout=timeout)

    def control(operation=None, second=False):
        conn = http.client.HTTPConnection('127.0.0.1', url.port, timeout=10)
        try:
            conn.request('GET' if operation is None else 'POST',
                         '/__fixture' + ('/secondary' if second else ''),
                         None if operation is None else json.dumps({'operation': operation}),
                         {'Content-Type': 'application/json'})
            reply = conn.getresponse()
            assert reply.status == 200
            result = json.loads(reply.read(65536))
            assert result['server_pid'] == d['server_identity']['pid']
            assert result['server_start_ticks'] == d['server_identity']['start_ticks']
            return result
        finally:
            conn.close()

    def binding(owner):
        return {**{k: owner[k] for k in ('workspace_id', 'session_id')},
                'executor_config_sha256': native.digest(owner['executor_config'])}

    def sample(key, free, at):
        return {'policy': pressure.OS_DECIMAL if key == 'os' else pressure.SSD_DECIMAL,
                'identity': 'synthetic-' + key, 'at': at, 'available': free, 'percent': 99,
                'total_bytes': 100_000_000_000, 'used_bytes': 100_000_000_000-free,
                'mount': {'target': '/' if key == 'os' else '/synthetic/ssd',
                          'source': '/dev/synthetic-' + key, 'uuid': 'synthetic-' + key,
                          'fstype': 'ext4', 'maj:min': '0:1'}}

    with patch.object(native_http, 'HTTPConnection', connection):
        # Both exact strict decimal boundaries exercise the real Disk cycle,
        # injected notification receipts, native HTTP codec and execution ledger.
        for label, thresholds in [('os', {'os': 10_000_000_000}),
                                  ('ssd', {'ssd': 25_000_000_000}),
                                  ('both', {'os': 10_000_000_000, 'ssd': 25_000_000_000})]:
            store = monitor.Store(root / (label + '.sqlite'))
            now = time.time()
            b = binding(d['owners'][0])
            config = {**b, 'activation_approved': True, 'ntfy_wake': True,
                      'state_file': str(root / (label + '.sqlite')),
                      'admission_protocol': native.PROTOCOL,
                      'volumes': {key: {'phone': key == 'ssd'} for key in thresholds},
                      'native_transport': {'enabled': True, 'route': 'existing_local_gateway_v1',
                          'executor_config_sha256': b['executor_config_sha256'],
                          'max_validation_age_seconds': 60}}
            samples = {key: sample(key, threshold, now) for key, threshold in thresholds.items()}
            notifications = []

            def bridge_factory(config):
                bridge = monitor.Bridge(config)
                bridge.observe = lambda alias: samples[alias]
                transport = bridge.transport
                def counted(method, path, body):
                    counts[method] += 1
                    return transport(method, path, body)
                bridge.transport = counted
                return bridge

            def tick(meta, at):
                return t26_watch.cycle(store, config, samples, {}, idle, meta, at,
                    bridge_factory=bridge_factory,
                    publisher_factory=lambda _: lambda *args: notifications.append(args),
                    root_receipt_reader=lambda _: {'kind': 'low', 'sent_at': now})

            baseline = control()['launches']
            meta, result = tick({}, now)
            assert control()['launches'] == baseline
            assert store.db.execute('SELECT count(*) FROM incidents').fetchone()[0] == 0
            samples = {key: sample(key, threshold-1, now) for key, threshold in thresholds.items()}
            meta, result = tick(meta, now)
            assert result['status'] == 'accepted', result
            assert control()['launches'] == baseline+1
            prompt = control()['latest_prompt']
            for key, threshold in thresholds.items():
                for expected in (str(threshold-1)+' bytes', str(threshold)+' bytes', '/dev/synthetic-'+key):
                    assert expected in prompt, (expected, prompt)
            incident = store.db.execute('SELECT id FROM incidents ORDER BY id').fetchall()
            assert len(incident) == len(thresholds)
            assert store.db.execute('SELECT count(*) FROM batches').fetchone()[0] == 1
            posts = counts['POST']
            meta, _ = tick(meta, now)
            assert counts['POST'] == posts
            assert store.db.execute('SELECT id FROM incidents ORDER BY id').fetchall() == incident
            control('complete')
            # Only recovery observation timestamps are injected. No backend clocks
            # or real capacity readings are changed, and recovery sends no POST.
            for i in range(3):
                at = now + (i+1)*60
                samples = {key: sample(key, threshold+2_000_000_000, at) for key, threshold in thresholds.items()}
                meta, _ = tick(meta, at)
            assert store.db.execute('SELECT count(*) FROM incidents WHERE recovered IS NULL').fetchone()[0] == 0
            assert counts['POST'] == posts
            store.close()
            checks.append(label+'_strict_decimal_native_receipt_exact_report_dedup_recovery')

        # Add an unrelated source/rule/target and native allowlist entry while
        # the SAME Rust listener, deployment, queue and DB remain alive.
        owner_file = Path(d['owner_file'])
        temporary = owner_file.with_suffix('.next')
        temporary.write_text(json.dumps({'version': 1, 'owners': d['owners']}))
        os.chmod(temporary, 0o600)
        temporary.replace(owner_file)
        template = json.loads((Path(__file__).parent/'watchers.example.json').read_text())
        cfg = {**template, 'activation_approved': True,
               'sources': {'printer-status': template['sources']['printer-status']},
               'targets': {'printer-owner': {**template['targets']['printer-owner'],
                   **binding(d['owners'][1]), 'enabled': True}},
               'rules': {'printer-error': template['rules']['printer-error']}}
        cfg['sources']['printer-status']['max_age_seconds'] = 300
        cfg['targets']['printer-owner'].update(max_validation_age_seconds=300, cooldown_seconds=60)
        registry_file = root/'modular-registry.json'
        registry_file.write_text(json.dumps(cfg)); os.chmod(registry_file, 0o600)
        registry = watch_events.Registry(json.loads(registry_file.read_text()))
        store_path = root/'printer.sqlite'
        store = watch_events.EventStore(store_path)
        event = {'version': 1, 'source': 'printer-status', 'event_id': str(uuid.uuid4()),
                 'resource': 'mk4', 'sequence': 1, 'observed_at': time.time()-181,
                 'values': {'state': 'error'}, 'report': 'Synthetic printer fault; report only.'}
        def ingest(value):
            routed = registry.event(value['source'], value, value['observed_at'])
            store.observations({key: s for _, key, s in routed}, {}, value['observed_at'])
        ingest(event)
        transport = native_http.LocalNativeHTTP(binding(d['owners'][1]))
        lost = True
        def lose_reply(method, path, body):
            nonlocal lost
            counts[method] += 1
            result = transport(method, path, body)
            if method == 'POST' and lost:
                lost = False
                raise TimeoutError('safe test loss AFTER actual native commit')
            return result
        assert watch_events.drain(store, registry, 'printer-owner', time.time(), lambda _: idle, lose_reply) == 'unknown'
        row = store.db.execute('SELECT * FROM batches').fetchone()
        bid = row['id']; posts = counts['POST']
        assert control(second=True)['launches'] == 4
        store.close(); store = watch_events.EventStore(store_path)
        # Reconcile after process reopen even with an unknown current inventory.
        watch_events.drain(store, registry, 'printer-owner', time.time()+61,
                           lambda _: {'inventory_unknown': True}, lose_reply)
        row = store.db.execute('SELECT * FROM batches').fetchone()
        assert row['id'] == bid and row['status'] == 'accepted' and row['execution']
        assert counts['POST'] == posts and counts['GET'] >= 1
        ingest(event)
        control('complete', second=True)
        watch_events.drain(store, registry, 'printer-owner', time.time()+62, lambda _: idle, lose_reply)
        assert counts['POST'] == posts
        assert store.db.execute('SELECT count(*) FROM incidents').fetchone()[0] == 1
        assert 'Synthetic printer fault' in control(second=True)['latest_prompt']
        # Recover under the original rule before editing its condition. Samples
        # are safely injected in the recent past; the native backend sees only
        # real fresh validation, never a future timestamp or altered host clock.
        for i in range(3):
            recovery = {**event, 'event_id': str(uuid.uuid4()), 'sequence': i+2,
                        'observed_at': event['observed_at']+60*(i+1),
                        'values': {'state': 'operational'}}
            ingest(recovery)
        assert store.db.execute('SELECT recovered FROM incidents').fetchone()[0] is not None
        assert counts['POST'] == posts
        cfg['rules']['printer-error']['trigger']['value'] = 'faulted'
        changed = registry_file.with_suffix('.next')
        changed.write_text(json.dumps(cfg)); os.chmod(changed, 0o600); changed.replace(registry_file)
        registry = watch_events.Registry(json.loads(registry_file.read_text()))
        changed_event = {**event, 'event_id': str(uuid.uuid4()), 'sequence': 5,
                         'observed_at': time.time(), 'values': {'state': 'faulted'},
                         'report': 'Synthetic changed condition; still report only.'}
        ingest(changed_event)
        # Inject scheduler time to exercise expired cooldown without waiting or
        # changing wall clocks. The event/native validation timestamp stays real.
        scheduler_now = max(time.time()+61, store.meta('next_attempt', 0)+1,
                            store.meta('last_accepted', 0)+61)
        outcome = watch_events.drain(store, registry, 'printer-owner', scheduler_now,
                                     lambda _: idle, lose_reply)
        assert outcome == 'accepted', outcome
        assert counts['POST'] == posts+1 and control(second=True)['launches'] == 5
        assert store.db.execute('SELECT count(*) FROM incidents').fetchone()[0] == 2
        control('complete', second=True)
        store.close()
        checks.extend(['settled_condition_edit_and_rearm_same_backend',
                       'second_unrelated_source_and_target_hot_reload_same_backend',
                       'real_native_commit_lost_ack_client_reopen_GET_only',
                       'replayed_event_one_incident_one_execution'])
    return {'fixture_protocol': d['fixture_protocol'], 'status': 'passed', 'evidence': checks,
            'backend_listener_count': 1, 'owner_targets': 2, 'server_identity': d['server_identity'],
            'http_counts': counts, 'executor_io': 'synthetic; native launch/approval/receipt path real'}


if __name__ == '__main__':
    print(json.dumps(run(json.loads(Path(sys.argv[1]).read_text())), sort_keys=True))
