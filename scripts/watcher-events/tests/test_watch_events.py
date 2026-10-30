"""Safe module tests: injected observations, owner inventories and receipt transport.

No model, printer action, real low-disk manipulation, live API or credential I/O.
"""
import copy
import json
import io
import contextlib
import multiprocessing
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid

import native_adapter as native
import watch_events as events

WORKSPACE = '00000000-0000-4000-8000-000000000001'
SESSION = '00000000-0000-4000-8000-000000000002'


def config():
    return {'version': 1, 'activation_approved': True,
        'state_volume': {}, 'state_root': '/unused',
        'sources': {'disk': {'enabled': True, 'max_age_seconds': 300, 'driver': 'events-v1'}},
        'targets': {'disk-space': {'enabled': True,
            'workspace_id': str(uuid.uuid4()), 'session_id': str(uuid.uuid4()),
            'executor_config_sha256': 'a'*64, 'max_validation_age_seconds': 300,
            'cooldown_seconds': 60, 'vibe_db': '/unused/db', 'owner_roots': ['/unused/owner']}},
        'rules': {'disk-low': {'source': 'disk', 'target': 'disk-space', 'resource': '*',
            'trigger': {'field': 'available', 'op': 'lt', 'value': 10_000_000_000},
            'recover': {'field': 'available', 'op': 'ge', 'value': 12_000_000_000},
            'recovery_samples': 3, 'min_sample_seconds': 60, 'max_gap_seconds': 150,
            'instruction': 'Report capacity; preserve all existing cleanup approval requirements.'}}}


def event(n=1, available=9_999_999_999, at=None, source='disk', resource='os'):
    return {'version': 1, 'source': source, 'event_id': str(uuid.uuid4()), 'sequence': n,
            'resource': resource, 'observed_at': time.time() if at is None else at,
            'values': {'available': available}, 'report': 'injected fixture observation'}


def idle(_):
    return {'inventory_unknown': False, 'coding_or_script_turns': [], 'independent_jobs': [],
            'queued': [], 'process_ids': []}


class ReceiptFixture:
    """Codec fixture only. An accepted receipt here is NOT a live execution proof."""
    def __init__(self, result='accepted', lose=False):
        self.posts = []; self.gets = []; self.receipts = {}; self.result = result; self.lose = lose

    def __call__(self, method, path, body):
        if method == 'GET':
            self.gets.append(path)
            return self.receipts[path.split('/')[-1].split('?')[0]]
        self.posts.append(copy.deepcopy(body))
        kind = self.result
        intent = body['intent']
        receipt = {'protocol': native.PROTOCOL, 'outcome': kind, 'no_admission': kind != 'accepted',
            'automatic_launch_queued': False, 'replay': False, 'reason': 'fixture_' + kind,
            'execution_status': 'completed' if kind == 'accepted' else None,
            'receipt': {'batch_id': body['batch_id'], 'intent_sha256': body['intent_sha256'],
                'workspace_id': intent['workspace_id'], 'session_id': intent['session_id'],
                'attempt_id': body['attempt_id'], 'state': kind, 'reason': 'fixture_' + kind,
                'execution_id': str(uuid.uuid4()) if kind == 'accepted' else None}}
        self.receipts[body['batch_id']] = receipt
        if self.lose:
            raise TimeoutError('injected lost acknowledgement')
        return receipt


class WatchEventsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = events.EventStore(Path(self.tmp.name) / 'events.sqlite')
        self.cfg = config(); self.registry = events.Registry(self.cfg)
        self.fixture = ReceiptFixture()

    def tearDown(self):
        self.store.close(); self.tmp.cleanup()

    def ingest(self, value, registry=None):
        registry = registry or self.registry
        routed = registry.event(value['source'], value, value['observed_at'])
        samples = {k: s for _, k, s in routed}
        self.store.observations(samples, {}, value['observed_at'])
        return samples

    def run_drain(self, now=None, owner=idle, registry=None):
        return events.drain(self.store, registry or self.registry, 'disk-space',
                            time.time() if now is None else now, owner, self.fixture)

    def test_existing_dispatcher_codec_and_one_incident_for_replays(self):
        value = event(); self.ingest(value)
        self.assertEqual(self.run_drain(), 'accepted')
        for _ in range(3):
            self.ingest(value); self.run_drain()
        self.assertEqual(len(self.fixture.posts), 1)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM incidents').fetchone()[0], 1)
        body = self.fixture.posts[0]
        self.assertEqual(body['intent_sha256'], native.digest(body['intent']))
        self.assertIn('9999999999', body['intent']['prompt'])
        self.assertNotIn('OP::Disk Space', body['intent']['prompt'])

    def test_strict_boundary_and_hysteresis_rearm(self):
        start = time.time() - 240
        self.ingest(event(1, 10_000_000_000, start))
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM incidents').fetchone()[0], 0)
        self.ingest(event(2, 9_000_000_000, start + 1))
        recovered = [event(3+i, 12_000_000_000, start+60*(i+1)) for i in range(3)]
        self.ingest(recovered[0]); self.ingest(recovered[0])
        self.ingest(recovered[1])
        self.assertIsNone(self.store.db.execute('SELECT recovered FROM incidents').fetchone()[0])
        self.ingest(recovered[2])
        self.assertIsNotNone(self.store.db.execute('SELECT recovered FROM incidents').fetchone()[0])
        self.assertEqual(self.run_drain(), 'no_action')
        self.assertEqual(self.fixture.posts, [])
        self.ingest(event(6, 1, start+240))
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM incidents').fetchone()[0], 2)

    def test_active_coding_and_independent_jobs_stay_pending_then_wake_once(self):
        for activity in ('coding_or_script_turns', 'independent_jobs', 'process_ids'):
            with self.subTest(activity=activity):
                self.store.close()
                self.store = events.EventStore(Path(self.tmp.name)/(activity+'.sqlite'))
                self.ingest(event(resource=activity.replace('_', '-')))
                status = idle(None); status[activity] = ['fixture-active']
                count = len(self.fixture.posts)
                self.assertEqual(self.run_drain(owner=lambda _: status), 'held_owner_or_backoff')
                self.assertEqual(len(self.fixture.posts), count)
                self.assertEqual(self.run_drain(), 'accepted')
                self.run_drain()
                self.assertEqual(len(self.fixture.posts), count+1)

    def test_busy_owner_preserves_all_episodes_beyond_one_batch(self):
        for i in range(10):
            self.ingest(event(resource='resource-'+str(i)))
        status = {**idle(None), 'independent_jobs': ['fixture-active']}
        self.assertEqual(self.run_drain(owner=lambda _: status), 'held_owner_or_backoff')
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM incidents WHERE delivery='pending'").fetchone()[0], 10)
        self.assertEqual(self.fixture.posts, [])
        self.assertEqual(self.run_drain(now=time.time()+61), 'accepted')
        self.assertEqual(len(self.fixture.posts), 1)

    def test_native_busy_race_stays_pending_and_retries_same_batch_after_idle(self):
        self.ingest(event())
        self.fixture.result = 'deferred'
        def busy_native(method, path, body):
            reply = self.fixture(method, path, body)
            reply['reason'] = reply['receipt']['reason'] = 'owner_busy'
            return reply
        self.assertEqual(events.drain(self.store, self.registry, 'disk-space', time.time(), idle, busy_native), 'deferred')
        self.assertEqual(self.store.db.execute('SELECT delivery FROM incidents').fetchone()[0], 'deferred')
        original = self.fixture.posts[0]
        self.fixture.result = 'accepted'
        self.ingest(event(2))
        self.assertEqual(events.drain(self.store, self.registry, 'disk-space', time.time()+61, idle, self.fixture), 'accepted')
        self.assertEqual(len(self.fixture.posts), 2)
        self.assertEqual(self.fixture.posts[1]['batch_id'], original['batch_id'])
        self.assertEqual(self.fixture.posts[1]['intent_sha256'], original['intent_sha256'])
        self.assertNotEqual(self.fixture.posts[1]['attempt_id'], original['attempt_id'])
        self.run_drain(now=time.time()+1900)
        self.assertEqual(len(self.fixture.posts), 2)

    def test_queue_and_unknown_do_not_claim_activity_or_drop_delivery(self):
        self.ingest(event())
        for status in ({**idle(None), 'queued': ['fixture-queue']}, {'inventory_unknown': True}):
            self.assertEqual(self.run_drain(owner=lambda _: status), 'held_owner_or_backoff')
        row = self.store.db.execute('SELECT delivery FROM incidents').fetchone()
        self.assertEqual(row[0], 'pending')
        self.assertEqual(self.run_drain(), 'accepted')

    def test_unsettled_native_reservation_keeps_delivery_pending(self):
        self.ingest(event()); self.fixture.result = 'deferred'
        def unsettled(method, path, body):
            reply = self.fixture(method, path, body)
            reply['reason'] = reply['receipt']['reason'] = 'owner_admission_unsettled'
            return reply
        self.assertEqual(events.drain(self.store, self.registry, 'disk-space', time.time(), idle, unsettled), 'deferred')
        self.assertEqual(self.store.db.execute('SELECT delivery FROM incidents').fetchone()[0], 'deferred')
        self.assertEqual(len(self.store.pending(self.store.fresh(time.time()))), 1)

    def test_lost_reply_reopen_reconciles_without_another_post(self):
        self.fixture.lose = True; self.ingest(event())
        self.assertEqual(self.run_drain(), 'unknown')
        self.store.close(); self.store = events.EventStore(Path(self.tmp.name)/'events.sqlite')
        self.run_drain(now=time.time()+61)
        self.assertEqual(len(self.fixture.posts), 1)
        self.assertTrue(self.fixture.gets)
        self.assertEqual(self.store.db.execute('SELECT status FROM batches').fetchone()[0], 'completed')

    def test_unknown_not_found_never_resends(self):
        self.fixture.lose = True; self.ingest(event()); self.run_drain()
        self.fixture.receipts.clear()
        self.run_drain(now=time.time()+61)
        self.assertEqual(len(self.fixture.posts), 1)
        self.assertEqual(self.store.db.execute('SELECT status FROM batches').fetchone()[0], 'unknown')

    def test_deferred_retry_same_batch_new_attempt_only_after_fresh_event(self):
        self.fixture.result = 'deferred'; value = event(); self.ingest(value)
        self.assertEqual(self.run_drain(), 'deferred')
        self.assertEqual(self.run_drain(now=time.time()+61), 'deferred_fresh_validation_required')
        self.assertEqual(len(self.fixture.posts), 1)
        self.ingest(event(2, at=value['observed_at'] + .1))
        # Safe injected clock; no wall clock or real disk alteration.
        with patch('watch_events.time.time', return_value=value['observed_at'] + .2):
            with self.store.db:
                self.store.put('next_attempt', 0)
            self.run_drain(now=value['observed_at'] + .2)
        self.assertEqual(len(self.fixture.posts), 2)
        self.assertEqual(self.fixture.posts[0]['batch_id'], self.fixture.posts[1]['batch_id'])
        self.assertNotEqual(self.fixture.posts[0]['attempt_id'], self.fixture.posts[1]['attempt_id'])

    def test_registry_reload_adds_unrelated_source_and_second_target(self):
        self.ingest(event()); self.assertEqual(self.run_drain(), 'accepted')
        changed = copy.deepcopy(self.cfg)
        changed['sources']['printer'] = {'enabled': True, 'max_age_seconds': 120, 'driver': 'events-v1'}
        changed['targets']['printer-owner'] = copy.deepcopy(changed['targets']['disk-space'])
        changed['targets']['printer-owner']['workspace_id'] = str(uuid.uuid4())
        changed['targets']['printer-owner']['session_id'] = str(uuid.uuid4())
        changed['rules']['printer-state'] = {**copy.deepcopy(changed['rules']['disk-low']),
            'source': 'printer', 'target': 'printer-owner', 'resource': 'mk4',
            'trigger': {'field': 'state', 'op': 'eq', 'value': 'error'},
            'recover': {'field': 'state', 'op': 'eq', 'value': 'operational'},
            'instruction': 'Report the printer status only; no printer actions.'}
        registry_path = Path(self.tmp.name)/'registry.json'
        registry_path.write_text(json.dumps(self.cfg)); registry_path.chmod(0o600)
        events.Registry(events.read_json(registry_path))
        replacement = registry_path.with_suffix('.new')
        replacement.write_text(json.dumps(changed)); replacement.chmod(0o600)
        replacement.replace(registry_path)
        reloaded = events.Registry(events.read_json(registry_path))
        value = event(source='printer', resource='mk4'); value['values'] = {'state': 'error'}
        _, key, sample = reloaded.event('printer', value, time.time())[0]
        other = events.EventStore(Path(self.tmp.name)/'printer.sqlite')
        try:
            other.observations({key: sample}, {}, time.time())
            self.assertEqual(events.drain(other, reloaded, 'printer-owner', time.time(), idle, self.fixture), 'accepted')
            self.assertEqual(len(self.fixture.posts), 2)
            self.assertEqual(self.fixture.posts[1]['intent']['session_id'],
                             changed['targets']['printer-owner']['session_id'])
        finally:
            other.close()
        # This proves file reload and separate bindings, NOT a native deployment.

    def test_pending_target_cannot_be_rebound(self):
        self.ingest(event()); self.fixture.lose = True; self.run_drain()
        changed = copy.deepcopy(self.cfg); changed['targets']['disk-space']['session_id'] = str(uuid.uuid4())
        with self.assertRaisesRegex(ValueError, 'rebinding'):
            self.run_drain(registry=events.Registry(changed))
        self.assertEqual(len(self.fixture.posts), 1)

    def test_open_rule_change_or_removal_cannot_send_old_evidence(self):
        self.ingest(event())
        changed = copy.deepcopy(self.cfg); changed['rules']['disk-low']['trigger']['value'] = 1
        revised = events.Registry(changed)
        with self.assertRaisesRegex(ValueError, 'rule_change'):
            self.ingest(event(2), revised)
        self.assertEqual(self.run_drain(registry=revised), 'no_action')
        self.assertEqual(self.fixture.posts, [])

    def test_disabled_gate_does_not_read_owner_or_transport(self):
        self.ingest(event()); self.registry.config['activation_approved'] = False
        with patch('watch_events.t26_watch.owner_status', side_effect=AssertionError):
            self.assertEqual(self.run_drain(owner=lambda _: self.fail('owner read')), 'held_native_activation')
        self.assertEqual(self.fixture.posts, [])

    def test_sequence_conflicts_order_staleness_and_source_spoof(self):
        value = event(2); self.ingest(value)
        changed = copy.deepcopy(value); changed['values']['available'] = 1
        with self.assertRaisesRegex(ValueError, 'sequence_identity_conflict'):
            self.ingest(changed)
        with self.assertRaisesRegex(ValueError, 'out_of_order'):
            self.ingest(event(1))
        with self.assertRaisesRegex(ValueError, 'stale_event'):
            self.registry.event('disk', event(at=time.time()-301), time.time())
        with self.assertRaisesRegex(ValueError, 'invalid_or_stale_event'):
            self.registry.event('disk', event(source='printer'), time.time())

    def test_condition_and_payload_constraints(self):
        with self.assertRaisesRegex(ValueError, 'duplicate_json_key'):
            events.parse_json(b'{"source":"disk","source":"printer"}')
        with self.assertRaisesRegex(ValueError, 'input_limit'):
            events.parse_json(b' '*65537)
        changed = copy.deepcopy(self.cfg)
        changed['rules']['disk-low']['recover'] = copy.deepcopy(changed['rules']['disk-low']['trigger'])
        with self.assertRaisesRegex(ValueError, 'overlapping'):
            events.Registry(changed).event('disk', event(), time.time())
        with self.assertRaisesRegex(ValueError, 'measurement_unavailable'):
            value = event(); value['values']['available'] = 'unknown'
            self.registry.event('disk', value, time.time())

    def test_stale_cached_event_is_not_freshened_by_drain(self):
        self.ingest(event(at=time.time()-301))
        self.assertEqual(self.run_drain(), 'no_action')
        self.assertEqual(self.fixture.posts, [])

    def test_fast_samples_do_not_advance_or_postpone_recovery_anchor(self):
        start = time.time()-240
        self.ingest(event(1, 1, start))
        self.ingest(event(2, 12_000_000_000, start+60))
        self.ingest(event(3, 12_000_000_000, start+75))
        self.ingest(event(4, 12_000_000_000, start+120))
        self.assertIsNone(self.store.db.execute('SELECT recovered FROM incidents').fetchone()[0])
        self.ingest(event(5, 12_000_000_000, start+180))
        self.assertIsNotNone(self.store.db.execute('SELECT recovered FROM incidents').fetchone()[0])

    def test_recovery_gap_and_missing_measurement_break_streak(self):
        start = time.time()-500
        self.ingest(event(1, 1, start))
        self.ingest(event(2, 12_000_000_000, start+60))
        self.ingest(event(3, 12_000_000_000, start+300))
        self.ingest(event(4, 12_000_000_000, start+360))
        self.assertIsNone(self.store.db.execute('SELECT recovered FROM incidents').fetchone()[0])
        self.store.observations({}, {'disk:disk-low:os': 'unavailable'}, start+361)
        self.ingest(event(5, 12_000_000_000, start+420))
        self.assertIsNone(self.store.db.execute('SELECT recovered FROM incidents').fetchone()[0])

    def test_cooldown_survives_lost_scheduler_metadata(self):
        self.ingest(event()); self.assertEqual(self.run_drain(), 'accepted')
        with self.store.db:
            self.store.db.execute("DELETE FROM event_meta WHERE key IN ('last_accepted','next_attempt')")
        self.ingest(event(resource='different-resource'))
        self.assertEqual(self.run_drain(), 'held_cooldown')
        self.assertEqual(len(self.fixture.posts), 1)

    def test_batch_payload_fits_native_limits_before_intent_commit(self):
        for i in range(8):
            value = event(resource='resource-'+str(i))
            value['report'] = 'x'*4096
            value['values'].update({'detail'+str(n): 'y'*1024 for n in range(6)})
            self.ingest(value)
        self.assertEqual(self.run_drain(), 'accepted')
        body = self.fixture.posts[0]
        self.assertLess(len(body['intent']['prompt'].encode()), 32768)
        self.assertLess(len(native.canonical(body).encode()), 65536)
        self.assertLess(len(body['intent']['incidents']), 8)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM incidents').fetchone()[0], 8)

    def test_batch_size_is_native_bounded_and_resources_are_durable(self):
        for i in range(10):
            self.ingest(event(resource='volume-'+str(i)))
        self.assertEqual(self.run_drain(), 'accepted')
        self.assertEqual(len(self.fixture.posts[0]['intent']['incidents']), 8)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM incidents').fetchone()[0], 10)

    def test_simultaneous_duplicate_ingress_is_locked_and_durable(self):
        # The CLI lock is real; all network and mount reads are disabled/injected.
        changed = copy.deepcopy(self.cfg)
        changed['activation_approved'] = False
        changed['state_volume'] = {'path': self.tmp.name}
        changed['state_root'] = self.tmp.name
        registry_path = Path(self.tmp.name)/'registry.json'
        registry_path.write_text(json.dumps(changed)); registry_path.chmod(0o600)
        payload = json.dumps(event()).encode()
        context = multiprocessing.get_context('fork')
        barrier = context.Barrier(2); results = context.Queue()
        def receive():
            with patch('watch_events.monitor.observe', return_value={}), \
                 patch('watch_events.sys.stdin', io.TextIOWrapper(io.BytesIO(payload))), \
                 contextlib.redirect_stdout(io.StringIO()):
                barrier.wait(timeout=5)
                try:
                    result = events.main(['--registry', str(registry_path), '--source', 'disk'])
                except BlockingIOError:
                    result = 'locked_producer_must_retry'
                results.put(result)
        children = [context.Process(target=receive) for _ in range(2)]
        for child in children:
            child.start()
        for child in children:
            child.join(timeout=8)
            self.assertEqual(child.exitcode, 0)
        outcomes = [results.get(timeout=1) for _ in children]
        self.assertIn(0, outcomes)
        self.assertTrue(set(outcomes) <= {0, 'locked_producer_must_retry'})
        received = events.EventStore(Path(self.tmp.name)/'disk-space.sqlite')
        try:
            self.assertEqual(received.db.execute('SELECT count(*) FROM incidents').fetchone()[0], 1)
            self.assertEqual(received.db.execute('SELECT count(*) FROM attempts').fetchone()[0], 0)
        finally:
            received.close()

    def test_removed_target_files_still_count_toward_lifetime_quota(self):
        changed = copy.deepcopy(self.cfg); changed['activation_approved'] = False
        changed['state_volume'] = {'path': self.tmp.name}; changed['state_root'] = self.tmp.name
        registry_path = Path(self.tmp.name)/'registry.json'
        registry_path.write_text(json.dumps(changed)); registry_path.chmod(0o600)
        # Includes this test's existing DB: retain all prior state, don't rotate it away.
        for i in range(15):
            (Path(self.tmp.name)/('retired-'+str(i)+'.sqlite')).touch()
        with patch('watch_events.monitor.observe', return_value={}), \
             patch('watch_events.sys.stdin', io.TextIOWrapper(io.BytesIO(json.dumps(event()).encode()))):
            with self.assertRaisesRegex(ValueError, 'lifetime_target_state_limit'):
                events.main(['--registry', str(registry_path), '--source', 'disk'])
        self.assertFalse((Path(self.tmp.name)/'disk-space.sqlite').exists())

    def test_rule_cannot_move_to_another_target_while_old_delivery_is_unresolved(self):
        original = event(); self.ingest(original)
        self.fixture.lose = True; self.run_drain()
        changed = copy.deepcopy(self.cfg)
        changed['targets']['other-owner'] = copy.deepcopy(changed['targets']['disk-space'])
        changed['targets']['other-owner']['session_id'] = str(uuid.uuid4())
        changed['rules']['disk-low']['target'] = 'other-owner'
        revised = events.Registry(changed)
        later = event(2, at=original['observed_at'] + 1)
        with self.assertRaisesRegex(ValueError, 'open_rule_routing_change_forbidden'):
            events.check_routing_state(Path(self.tmp.name), revised.event('disk', later, later['observed_at']))
        self.assertEqual(len(self.fixture.posts), 1)
        self.assertEqual(self.store.db.execute('SELECT status FROM batches').fetchone()[0], 'unknown')
        self.assertFalse((Path(self.tmp.name)/'other-owner.sqlite').exists())
        # Removing/changing a rule never prevents periodic GET reconciliation.
        events.check_routing_state(Path(self.tmp.name), [])

    def test_closed_rule_move_requires_new_observation_and_can_reuse_configuration(self):
        start = time.time()-240
        self.ingest(event(1, 1, start))
        for n in range(2, 5):
            last = event(n, 12_000_000_000, start+60*(n-1)); self.ingest(last)
        changed = copy.deepcopy(self.cfg)
        changed['targets']['other-owner'] = copy.deepcopy(changed['targets']['disk-space'])
        changed['rules']['disk-low']['target'] = 'other-owner'
        revised = events.Registry(changed)
        with self.assertRaisesRegex(ValueError, 'retarget_requires_new_observation'):
            events.check_routing_state(Path(self.tmp.name), revised.event('disk', last, last['observed_at']))
        fresh = event(5, 1, start+240)
        events.check_routing_state(Path(self.tmp.name), revised.event('disk', fresh, fresh['observed_at']))

    def test_rule_move_is_held_after_capacity_recovers_until_uncertain_receipt_resolves(self):
        start = time.time()-240
        self.ingest(event(1, 1, start))
        with patch('watch_events.time.time', return_value=start+1):
            self.fixture.lose = True; self.run_drain(now=start+1)
        for n in range(2, 5):
            self.ingest(event(n, 12_000_000_000, start+60*(n-1)))
        self.assertIsNotNone(self.store.db.execute('SELECT recovered FROM incidents').fetchone()[0])
        changed = copy.deepcopy(self.cfg)
        changed['targets']['other-owner'] = copy.deepcopy(changed['targets']['disk-space'])
        changed['rules']['disk-low']['target'] = 'other-owner'
        fresh = event(5, 1, start+240)
        with self.assertRaisesRegex(ValueError, 'open_rule_routing_change_forbidden'):
            events.check_routing_state(Path(self.tmp.name), events.Registry(changed).event('disk', fresh, fresh['observed_at']))

    def test_state_database_symlink_is_never_followed(self):
        link = Path(self.tmp.name)/'other-owner.sqlite'
        link.symlink_to(Path(self.tmp.name)/'events.sqlite')
        value = event()
        with self.assertRaisesRegex(ValueError, 'state_symlink_forbidden'):
            events.check_routing_state(Path(self.tmp.name), self.registry.event('disk', value, value['observed_at']))

    def test_clock_regression_cooldown_is_bounded_once(self):
        with self.store.db:
            self.store.put('last_accepted', 10000)
            self.store.put('next_attempt', 10000)
        self.assertEqual(self.run_drain(now=1000), 'held_owner_or_backoff')
        self.assertEqual(self.store.meta('last_accepted'), 1000)
        self.assertEqual(self.store.meta('next_attempt'), 4600)
        self.assertEqual(self.run_drain(now=1001), 'held_owner_or_backoff')
        self.assertEqual(self.store.meta('next_attempt'), 4600)

    def test_disk_adapter_preserves_existing_owner_ledger_policy_and_false_gates(self):
        import pressure
        import t26_watch
        changed = copy.deepcopy(self.cfg)
        changed['sources']['disk']['driver'] = 'disk-existing-v1'
        target = changed['targets']['disk-space']
        target.update(workspace_id=WORKSPACE, session_id=SESSION, cooldown_seconds=1800)
        changed['rules']['disk-low']['resource'] = 'os'
        changed['rules']['ssd-low'] = copy.deepcopy(changed['rules']['disk-low'])
        changed['rules']['ssd-low'].update(resource='ssd',
            trigger={'field': 'available', 'op': 'lt', 'value': 25_000_000_000},
            recover={'field': 'available', 'op': 'ge', 'value': 27_000_000_000})
        registry = events.Registry(changed)
        original = {'activation_approved': False, 'native_transport': {'enabled': False},
            'state_file': '/existing/incidents.sqlite', 'workspace_id': WORKSPACE,
            'session_id': SESSION,
            'event_registry': {'path': '/registry', 'target': 'disk-space'},
            'volumes': {'os': {'policy': pressure.OS_DECIMAL}, 'ssd': {'policy': pressure.SSD_DECIMAL}}}
        effective = events.disk_config(original, registry)
        self.assertFalse(effective['activation_approved'])
        self.assertFalse(effective['native_transport']['enabled'])
        self.assertEqual(effective['state_file'], original['state_file'])
        with self.assertRaisesRegex(ValueError, 'reserved'):
            registry.event('disk', event(), time.time())
        changed['rules']['disk-low']['trigger']['value'] = 11_000_000_000
        with self.assertRaisesRegex(ValueError, 'threshold'):
            events.disk_config(original, events.Registry(changed))

    def test_public_source_requires_explicit_private_existing_owner_binding(self):
        import t26_watch
        self.assertEqual(t26_watch.configured_owner({'workspace_id': WORKSPACE, 'session_id': SESSION}),
                         (WORKSPACE, SESSION))
        for config in ({}, {'workspace_id': WORKSPACE},
                       {'workspace_id': str(uuid.UUID(int=0)), 'session_id': SESSION},
                       {'workspace_id': 'invalid', 'session_id': SESSION}):
            with self.subTest(config=config), self.assertRaises((KeyError, ValueError)):
                t26_watch.configured_owner(config)

    def test_disk_registry_cannot_replace_the_separate_private_owner_binding(self):
        import pressure
        changed = copy.deepcopy(self.cfg)
        # A caller-controlled registry target must match the separate Disk config.
        changed['targets']['disk-space'].update(workspace_id=str(uuid.uuid4()), session_id=SESSION)
        registry = events.Registry(changed)
        original = {'workspace_id': WORKSPACE, 'session_id': SESSION,
            'event_registry': {'path': '/registry', 'target': 'disk-space'}}
        with self.assertRaisesRegex(ValueError, 'existing_disk_owner_required'):
            events.disk_config(original, registry)

    def test_bounded_state_cap_and_unknown_tombstones_preserved(self):
        self.ingest(event()); self.fixture.lose = True; self.run_drain()
        self.assertEqual(self.store.db.execute('PRAGMA max_page_count').fetchone()[0], 2048)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM batches').fetchone()[0], 1)
        self.store.close(); self.store = events.EventStore(Path(self.tmp.name)/'events.sqlite')
        self.assertEqual(self.store.db.execute('SELECT status FROM batches').fetchone()[0], 'unknown')


if __name__ == '__main__':
    unittest.main()
