import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch

from test_monitor import m, sample, FakeBridge

a, p = m.accounting, m.pressure


def ssd(headroom=600*p.MIB, at=1000, remaining=100*p.MIB, known=True):
    return {'policy': p.SSD, 'identity': 'fixture-fs', 'at': at, 'percent': 99,
            'available': p.SSD_FLOOR + remaining + headroom,
            'accounting': {'status': 'known', 'remaining_future_bytes': remaining,
                           'snapshot_id': str(uuid.uuid4()), 'observed_at': at,
                           'snapshot_sha256':a.digest({'at':at,'remaining':remaining}),
                           'valid_until': at+120} if known else {'status': 'unknown'}}


class Headroom(unittest.TestCase):
    def test_existing_floor_is_immediate_even_without_accounting(self):
        for free in (p.SSD_FLOOR, p.SSD_FLOOR-1):
            s = ssd(known=False); s['available'] = free
            _, d = p.advance({}, s)
            self.assertTrue(d['eligible']); self.assertIsNone(d['headroom_bytes'])
            self.assertEqual(d['reason'], 'physical_floor')

    def test_negative_headroom_above_floor_is_immediate(self):
        s = ssd(-1)
        self.assertGreater(s['available'], p.SSD_FLOOR)
        _, d = p.advance({}, s)
        self.assertTrue(d['eligible']); self.assertEqual(d['headroom_bytes'], -1)

    def test_zero_and_256MiB_need_two_one_minute_samples(self):
        for h in (0, 256*p.MIB):
            state, d = p.advance({}, ssd(h))
            self.assertFalse(d['eligible'])
            state, d = p.advance(state, ssd(h, at=1060))
            self.assertTrue(d['eligible'])

    def test_two_low_samples_are_consecutive_and_gap_bounded(self):
        state, _ = p.advance({}, ssd(256*p.MIB))
        state, _ = p.advance(state, ssd(257*p.MIB, at=1060))
        _, d = p.advance(state, ssd(256*p.MIB, at=1120))
        self.assertFalse(d['eligible'])
        state, _ = p.advance({}, ssd(256*p.MIB))
        _, d = p.advance(state, ssd(256*p.MIB, at=1121))
        self.assertFalse(d['eligible'])

    def test_fast_repeats_and_admission_revalidation_do_not_count(self):
        state, _ = p.advance({}, ssd(100*p.MIB))
        state, d = p.advance(state, ssd(100*p.MIB, at=1030))
        self.assertEqual(d['critical_count'], 1)
        state, d = p.advance(state, ssd(100*p.MIB, at=1060), periodic=False)
        self.assertFalse(d['eligible']); self.assertEqual(d['critical_count'], 1)
        _, d = p.advance(state, ssd(100*p.MIB, at=1060))
        self.assertTrue(d['eligible'])

    def test_recovery_at_512MiB_needs_three_consecutive_samples(self):
        state, _ = p.advance({}, ssd(-1))
        for index in range(1, 4):
            state, d = p.advance(state, ssd(512*p.MIB, at=1000+60*index))
            self.assertEqual(d['recovered'], index == 3)
        self.assertFalse(d['eligible'])
        _, d = p.advance(state, ssd(-1, at=1240))
        self.assertTrue(d['eligible'])

    def test_unknown_accounting_breaks_runs_and_never_recovers(self):
        state, _ = p.advance({}, ssd(-1))
        state, _ = p.advance(state, ssd(800*p.MIB, at=1060))
        state, d = p.advance(state, ssd(800*p.MIB, at=1120, known=False))
        self.assertEqual(d['severity'], 'unknown'); self.assertFalse(d['recovered'])
        self.assertIsNone(d['headroom_bytes']); self.assertEqual(d['recovery_count'], 0)
        state, d = p.advance(state, ssd(800*p.MIB, at=1180))
        self.assertFalse(d['recovered']); self.assertEqual(d['recovery_count'], 1)

    def test_stale_accounting_is_unknown_even_if_remaining_is_zero(self):
        s = ssd(remaining=0); s['accounting']['valid_until'] = s['at']
        _, d = p.advance({}, s)
        self.assertEqual(d['severity'], 'unknown'); self.assertFalse(d['recovered'])

    def test_missing_mount_observation_breaks_run_without_clearing_latch(self):
        state, _ = p.advance({}, ssd(-1))
        state, _ = p.advance(state, ssd(at=1060))
        state = p.break_run(state)
        self.assertTrue(state['latched']); self.assertEqual(state['recovery_count'], 0)

    def test_ssd_percentage_is_not_used_and_OS_percentage_is_unchanged(self):
        _, d = p.advance({}, ssd())
        self.assertFalse(d['eligible'])  # 99% used can coexist with sufficient headroom.
        for percent in (83, 84, 85, 91, 92, 96, 97, 100):
            s = sample(percent)
            _, d = p.advance({}, s)
            self.assertEqual(d['severity'], m.level(percent))
            self.assertEqual(d['eligible'], percent >= 92)
            self.assertEqual(d['recovered'], percent <= 83)

    def test_written_bytes_reduce_free_and_remaining_once(self):
        s1 = ssd(400*p.MIB, remaining=1000*p.MIB)
        s2 = ssd(400*p.MIB, at=1060, remaining=900*p.MIB)
        self.assertEqual(s1['available']-s2['available'], 100*p.MIB)
        _, d1 = p.advance({}, s1); _, d2 = p.advance({}, s2)
        self.assertEqual(d1['headroom_bytes'], d2['headroom_bytes'])

    def test_recovery_dip_breaks_consecutive_evidence(self):
        state, _ = p.advance({}, ssd(-1))
        for at in (1060,1120): state, _ = p.advance(state, ssd(at=at))
        state, d = p.advance(state, ssd(511*p.MIB, at=1180))
        self.assertFalse(d['recovered']); self.assertEqual(d['recovery_count'], 0)
        _, d = p.advance(state, ssd(at=1240))
        self.assertFalse(d['recovered'])

    def test_mutated_or_regressed_accounting_cannot_prove_recovery(self):
        original=ssd(-1);state,_=p.advance({},original)
        changed=copy.deepcopy(original);changed['at']=1060
        changed['available']+=p.GIB;changed['accounting']['snapshot_sha256']='f'*64
        _,d=p.advance(state,changed)
        self.assertEqual(d['severity'],'unknown');self.assertFalse(d['recovered'])
        regressed=ssd(at=999);regressed['at']=1060
        _,d=p.advance(state,regressed)
        self.assertEqual(d['severity'],'unknown');self.assertFalse(d['recovered'])


class AccountingInput(unittest.TestCase):
    def setUp(self):
        self.expected = {'max_age_seconds':120, 'authorities': {k: str(i)*64 for i,k in enumerate(('nightly','staging','mp','bb'), 1)}}
        remaining = {'nightly':4*p.GIB, 'staging':48*p.MIB, 'mp':400*p.MIB, 'bb':96*p.MIB}
        self.doc = {'schema': a.SCHEMA, 'snapshot_id':str(uuid.uuid4()), 'filesystem_uuid':'fixture-fs',
                    'authority_set_sha256':a.digest(self.expected['authorities']), 'observed_at':1000,
                    'valid_until':1120, 'complete':True, 'allocations':[
                        {'allocation_id':k, 'remaining_future_bytes':v, 'usage_observed_at':1000,
                         'authority_sha256':self.expected['authorities'][k], 'usage_receipt_sha256':'a'*64}
                        for k,v in remaining.items()]}

    def validate(self):
        return a.validate(self.doc, self.expected, 'fixture-fs', 1000)

    def test_only_future_remaining_is_summed(self):
        d = self.validate()
        # Synthetic usage: 5GiB whole-task minus 1GiB already resident = 4GiB future.
        self.assertEqual(d['remaining_future_bytes'], 4*p.GIB+(48+400+96)*p.MIB)
        # Staging's 32MiB window is within its 48MiB synthetic remainder, never added again.
        self.assertNotEqual(d['remaining_future_bytes'], 4*p.GIB+(48+32+400+96)*p.MIB)

    def test_nightly_only_telemetry_cannot_omit_BB_or_other_owners(self):
        self.doc['allocations'] = self.doc['allocations'][:1]
        with self.assertRaises(ValueError): self.validate()

    def test_missing_BB_or_duplicate_owner_is_not_zero(self):
        self.doc['allocations'][-1] = copy.deepcopy(self.doc['allocations'][0])
        with self.assertRaises(ValueError): self.validate()

    def test_stale_wrong_mount_wrong_authority_incomplete_and_future_rejected(self):
        for change in ({'valid_until':999}, {'valid_until':2000}, {'filesystem_uuid':'other'},
                       {'authority_set_sha256':'0'*64}, {'complete':False}, {'observed_at':1001}):
            with self.subTest(change=change):
                d = {**self.doc, **change}
                with self.assertRaises(ValueError): a.validate(d,self.expected,'fixture-fs',1000)

    def test_negative_boolean_and_stale_usage_rejected(self):
        for change in ({'remaining_future_bytes':-1}, {'remaining_future_bytes':True},
                       {'usage_observed_at':800}, {'usage_receipt_sha256':'not-evidence'}):
            d = copy.deepcopy(self.doc); d['allocations'][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                a.validate(d,self.expected,'fixture-fs',1000)

    def test_zero_requires_explicit_complete_fresh_owner_confirmation(self):
        for row in self.doc['allocations']: row['remaining_future_bytes']=0
        self.assertEqual(self.validate()['remaining_future_bytes'], 0)
        self.doc['complete'] = False
        with self.assertRaises(ValueError): self.validate()

    def test_file_missing_insecure_or_symlink_is_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'current.json'; c = {**self.expected, 'snapshot_path':str(path)}
            self.assertEqual(a.load(c,'fixture-fs',1000)['status'], 'unknown')
            path.write_text(json.dumps(self.doc)); path.chmod(0o644)
            self.assertEqual(a.load(c,'fixture-fs',1000)['status'], 'unknown')
            path.chmod(0o600)
            self.assertEqual(a.load(c,'fixture-fs',1000)['status'], 'known')
            link=Path(temp)/'link'; link.symlink_to(path); c['snapshot_path']=str(link)
            self.assertEqual(a.load(c,'fixture-fs',1000)['status'], 'unknown')


class DurableSSD(unittest.TestCase):
    def test_floor_incident_can_send_with_unknown_accounting_in_isolated_route(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'state.db';s=m.Store(path);at=time.time()
            try:
                v=ssd(at=at,known=False);v['available']=p.SSD_FLOOR
                values={'ssd':v};s.observations(values,{},at)
                b=FakeBridge();b.samples=values
                self.assertEqual(s.dispatch(values,b,path),'accepted')
                proof=__import__('json').loads(s.db.execute('SELECT evidence FROM attempts').fetchone()[0])['observations']['ssd']['pressure']
                self.assertEqual(proof['reason'],'physical_floor')
                self.assertIsNone(proof['headroom_bytes'])
            finally:s.close()

    def test_counter_survives_restart_and_revalidation_is_not_another_sample(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'state.db'; s=m.Store(path); at=time.time()
            first={'ssd':ssd(200*p.MIB,at=at)}; s.observations(first,{},at)
            self.assertEqual(s.db.execute('SELECT count(*) FROM incidents').fetchone()[0],0)
            s.close(); s=m.Store(path)
            try:
                second={'ssd':ssd(200*p.MIB,at=at+60)}; s.observations(second,{},at+60)
                self.assertEqual(s.db.execute('SELECT count(*) FROM incidents').fetchone()[0],1)
                b=FakeBridge(); b.samples=second
                with patch.object(m.time,'time',return_value=at+60):
                    self.assertEqual(s.dispatch(second,b,path),'accepted')
                state=json.loads(s.db.execute('SELECT state FROM volume_state').fetchone()[0])
                self.assertEqual(state['critical_count'],2)
            finally:s.close()

    def test_unknown_never_recovers_or_dispatches_but_floor_still_does(self):
        with tempfile.TemporaryDirectory() as temp:
            s=m.Store(Path(temp)/'state.db'); at=time.time()
            try:
                values={'ssd':ssd(-1,at=at)}; s.observations(values,{},at)
                unknown={'ssd':ssd(at=at+60,known=False)}; s.observations(unknown,{},at+60)
                self.assertFalse(s.pending(unknown))
                self.assertIsNone(s.db.execute('SELECT recovered FROM incidents').fetchone()[0])
                floor=ssd(at=at+120,known=False);floor['available']=p.SSD_FLOOR
                values={'ssd':floor};s.observations(values,{},at+120)
                self.assertEqual(len(s.pending(values)),1)
            finally:s.close()

    def test_phone_recovery_uses_three_headroom_samples_not_percent(self):
        with tempfile.TemporaryDirectory() as temp:
            s=m.Store(Path(temp)/'state.db');at=time.time();calls=[]
            try:
                for index,h in enumerate((-1,600*p.MIB,600*p.MIB,600*p.MIB)):
                    v=ssd(h,at=at+60*index);s.observations({'ssd':v},{},at+60*index)
                    s.phone('ssd',v,lambda *args:calls.append(args),at+60*index)
                    if index < 3:self.assertEqual(len(calls),1)
                self.assertEqual([c[1] for c in calls],['critical','normal'])
            finally:s.close()


if __name__=='__main__': unittest.main()
