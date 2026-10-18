#!/usr/bin/env python3
"""Exact T90 client against T64's real cfg(test) native HTTP/SQLite fixture.

The hosted Rust test owns both listener and migrated backend, with synthetic
executor I/O. This driver starts no server, model, service or production binding.
Only the explicit storage-native-fixture-v1 descriptor enables test setup calls.
"""
import concurrent.futures
import http.client
import json
from pathlib import Path
import sys
import threading
import time
from urllib.parse import urlsplit

import monitor
import native_adapter as native


def run(descriptor):
    if descriptor['fixture_protocol'] != 'storage-native-fixture-v1':
        raise ValueError('explicit_native_fixture_required')
    url, control = urlsplit(descriptor['base_url']), urlsplit(descriptor['control_url'])
    if (url.scheme != 'http' or url.hostname != '127.0.0.1' or not url.port
            or url.port in {80, 443, 4720} or url.path != '/api'
            or url.username or url.password or url.query or url.fragment
            or control.scheme != url.scheme or control.netloc != url.netloc
            or control.path != '/__fixture' or control.query or control.fragment):
        raise ValueError('isolated_ephemeral_loopback_fixture_required')
    journal = Path(descriptor['state_file'])
    if not journal.is_absolute() or not journal.parent.is_dir():
        raise ValueError('isolated_state_directory_required')
    counts = {'POST':0, 'GET':0}
    lock = threading.Lock()
    drop = False
    fanout = False
    competing_replies = []
    checks = []

    def exchange(method, path, body):
        connection = http.client.HTTPConnection('127.0.0.1', url.port, timeout=30)
        try:
            connection.request(method, path, None if body is None else native.canonical(body).encode(),
                               {'Content-Type':'application/json'})
            reply = connection.getresponse()
            raw = reply.read(65537)
            if reply.status != 200 or len(raw)>65536:
                raise ValueError('native_protocol_error')
            return json.loads(raw)
        finally:
            connection.close()

    def transport(method, path, body):
        nonlocal drop, fanout
        if method not in counts or not path.startswith('/api/storage-alerts/batches'):
            raise ValueError('readonly_reconciliation_or_submit_only')
        def send_one(_=None):
            with lock:
                counts[method] += 1
            return exchange(method,path,body)
        if method=='POST' and fanout:
            fanout=False
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                competing_replies.extend(pool.map(send_one,range(4)))
            reply=competing_replies[0]
        else:
            reply=send_one()
        if method=='POST' and drop:
            drop=False
            raise TimeoutError('controlled_loss_after_real_commit')
        return reply

    def setup(operation=None):
        return exchange('GET' if operation is None else 'POST', '/__fixture',
                    None if operation is None else {'operation':operation})

    def observe(key):
        return {'percent':98,'available':1024,'at':time.time(),
                'identity':'synthetic-native-integration-fs','policy':monitor.pressure.OS}

    adapter=native.NativeAdapter(descriptor['binding'],transport,observe,
                                 descriptor['max_validation_age_seconds'])

    def poll(store):
        samples={'os':observe('os')}
        store.observations(samples,{},time.time())
        return store.dispatch(samples,adapter,'synthetic-private-receipt-é')

    def batch(store):
        return store.db.execute('SELECT * FROM batches ORDER BY created DESC LIMIT 1').fetchone()

    def open_pressure(store):
        assert store.db.execute('SELECT count(*) FROM incidents WHERE recovered IS NULL').fetchone()[0]==1

    def finish(store):
        setup('complete')
        assert poll(store)=='no_action'
        assert batch(store)['status']=='completed'
        open_pressure(store)
        store.close()

    if descriptor['phase']=='initial':
        assert not journal.exists(), 'Use a fresh native fixture directory'
        baseline=setup()['launches']
        queued_receipt=setup('queue_user')['queued']
        store=monitor.Store(journal.with_suffix('.queue.sqlite'))
        assert poll(store)=='deferred'
        original=store.document(batch(store))
        native_state=setup()
        assert native_state['launches']==baseline
        assert native_state['queued']==queued_receipt
        assert native_state['queued']['status']=='queued'
        assert native_state['queued']['message']['data']['message']=='synthetic queued user'
        checks.extend(['native_queue_deferral_zero_launch','ordinary_user_queue_preserved'])
        # Strictly-newer validation is required before another possible POST.
        previous=native.parse_utc(original['validation']['observed_at']).timestamp()
        adapter.observe=lambda key:{**observe(key),'at':previous}
        before=dict(counts)
        assert poll(store)=='deferred_fresh_validation_required'
        assert counts==before
        checks.append('same_observation_not_retried')
        adapter.observe=observe
        setup('clear_queue')
        assert poll(store)=='accepted'
        current=store.document(batch(store))
        assert current['batch_id']==original['batch_id'] and current['intent_sha256']==original['intent_sha256']
        assert current['attempt_id']!=original['attempt_id']
        assert native.parse_utc(current['validation']['observed_at'])>native.parse_utc(original['validation']['observed_at'])
        assert setup()['launches']==baseline+1
        checks.append('native_queue_deferral_strict_fresh_same_intent_retry')
        finish(store)
        checks.append('execution_success_does_not_recover_pressure')

        setup('busy')
        baseline=setup()['launches']
        store=monitor.Store(journal.with_suffix('.busy.sqlite'))
        assert poll(store)=='deferred' and setup()['launches']==baseline
        checks.append('native_owner_busy_no_launch')
        original=store.document(batch(store))
        setup('interrupt')
        assert poll(store)=='accepted'
        current=store.document(batch(store))
        assert current['intent_sha256']==original['intent_sha256']
        assert 'synthetic interrupted user' in setup()['latest_prompt']
        assert setup()['launches']==baseline+1
        checks.append('native_busy_deferral_and_ordinary_interrupted_turn_recovery')
        finish(store)

        store=monitor.Store(journal.with_suffix('.lost.sqlite'))
        drop=True
        before=dict(counts)
        assert poll(store)=='unknown'
        saved=store.document(batch(store));store.close()
        store=monitor.Store(journal.with_suffix('.lost.sqlite'))
        assert poll(store)=='held_prior_delivery'
        row=batch(store)
        assert row['status']=='accepted' and row['id']==saved['batch_id']
        assert counts=={'POST':before['POST']+1,'GET':before['GET']+1}
        checks.append('real_commit_lost_response_restart_GET_only')
        finish(store)

        store_path=journal.with_suffix('.concurrent.sqlite')
        store=monitor.Store(store_path)
        baseline=setup()['launches']
        fanout=True
        assert poll(store)=='accepted'
        row=batch(store);document=store.document(row)
        replies=[native.decode(body,document,document['known_attempt_ids']) for body in competing_replies]
        assert len(replies)==4
        assert all(r['kind']=='accepted' and r['execution_id']==row['execution'] for r in replies)
        replay=adapter.send(document)
        assert replay['kind']=='accepted' and replay['execution_id']==row['execution']
        checks.append('competing_first_deliveries_and_accepted_replay_same_execution')
        assert setup()['launches']==baseline+1
        open_pressure(store)
        checks.append('concurrent_duplicate_native_POST_one_execution')
        # Retain the exact accepted intent/attempts across a real native DB reopen.
        journal.write_text(native.canonical({'state_path':str(store_path),'document':document,
            'execution_id':row['execution'],'launches':setup()['launches']}))
        store.close()
    elif descriptor['phase']=='reopened':
        saved=json.loads(journal.read_text())
        store=monitor.Store(saved['state_path'])
        assert poll(store)=='held_prior_delivery'
        row=batch(store)
        assert row['status']=='accepted' and row['execution']==saved['execution_id']
        assert store.document(row)==saved['document']
        checks.append('reopened_exact_immutable_intent_execution_binding')
        # Fixture launch counter resets on rebuild; it must remain zero here.
        assert setup()['launches']==0
        assert counts=={'POST':0,'GET':1}
        open_pressure(store)
        store.close()
        checks.append('real_native_WAL_reopen_exact_accepted_binding_GET_only')
    else:
        raise ValueError('unknown_fixture_phase')
    return {'fixture_protocol':'storage-native-fixture-v1','phase':descriptor['phase'],
            'status':'passed','checks':len(checks),'evidence':checks,'calls':counts}


if __name__=='__main__':
    print(native.canonical(run(json.loads(Path(sys.argv[1]).read_text()))))
