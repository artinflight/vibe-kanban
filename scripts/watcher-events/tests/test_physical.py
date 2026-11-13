"""Physical-free policy fixtures: proposed tuning, no producer or live dispatch."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_monitor import m, FakeBridge, sample

p=m.pressure
LOW=p.SSD_FLOOR+256*p.MIB
HIGH=p.SSD_FLOOR+512*p.MIB


def physical(free=LOW,at=1000):
    return {'policy':p.SSD_PHYSICAL,'identity':'fixture-ssd','at':at,'percent':99,'available':free}


class PhysicalPolicy(unittest.TestCase):
    def test_floor_is_immediate_but_buffers_are_separate_proposal(self):
        self.assertEqual(p.SSD_FLOOR,2147483648)
        self.assertEqual((LOW,HIGH),(2415919104,2684354560))
        for free in (0,p.SSD_FLOOR-1,p.SSD_FLOOR):
            _,d=p.advance({},physical(free))
            self.assertTrue(d['eligible']);self.assertEqual(d['reason'],'physical_floor')
        for free in (p.SSD_FLOOR+1,LOW):
            state,d=p.advance({},physical(free))
            self.assertFalse(d['eligible'])
            _,d=p.advance(state,physical(free,1060));self.assertTrue(d['eligible'])
        state,_=p.advance({},physical(LOW+1))
        _,d=p.advance(state,physical(LOW+1,1060));self.assertFalse(d['eligible'])

    def test_recovery_boundary_is_three_samples_and_rearms(self):
        for free in (HIGH-1,HIGH,HIGH+1):
            state,_=p.advance({},physical(p.SSD_FLOOR))
            for at in (1060,1120,1180):state,d=p.advance(state,physical(free,at))
            self.assertEqual(d['recovered'],free>=HIGH)
            self.assertEqual(d['eligible'],free<HIGH)
        state,d=p.advance(state,physical(LOW,1240));self.assertFalse(d['eligible'])
        _,d=p.advance(state,physical(LOW,1300));self.assertTrue(d['eligible'])

    def test_accounting_is_neither_read_nor_used_as_zero(self):
        base=physical(HIGH);state,_=p.advance({},physical(p.SSD_FLOOR))
        for accounting in (None,{'status':'unknown'}, {'status':'known','remaining_future_bytes':10**20}):
            a=dict(state);b=dict(state)
            for at in (1060,1120,1180):
                a,d=p.advance(a,{**base,'at':at})
                b,e=p.advance(b,{**base,'at':at,'accounting':accounting})
                self.assertEqual((a,d),(b,e))
            self.assertTrue(d['recovered']);self.assertNotIn('accounting_status',d)
            self.assertNotIn('headroom_bytes',d)
        volume={'policy':p.SSD_PHYSICAL}
        with patch.object(m,'observe',return_value=base),patch.object(m.accounting,'load') as load:
            self.assertEqual(m.sample_volume(volume),base);load.assert_not_called()

    def test_reserve_aware_path_requires_explicit_enable_and_actual_valid_input(self):
        with patch.object(m,'observe',return_value=physical()),patch.object(m.accounting,'load') as load:
            with self.assertRaisesRegex(ValueError,'reserve_aware_monitoring_disabled'):
                m.sample_volume({'policy':p.SSD})
            load.assert_not_called()
            load.return_value={'status':'unknown'}
            with self.assertRaisesRegex(ValueError,'complete_fresh_input_required'):
                m.sample_volume({'policy':p.SSD,'reserve_aware_enabled':True})
            load.return_value={'status':'known','remaining_future_bytes':0}
            self.assertEqual(m.sample_volume({'policy':p.SSD,'reserve_aware_enabled':True})['accounting'],load.return_value)

    def test_sample_interval_gap_and_clock_regression(self):
        for delta,eligible in ((59,False),(60,True),(90,True),(91,False),(-1,False)):
            state,_=p.advance({},physical())
            _,d=p.advance(state,physical(at=1000+delta))
            self.assertEqual(d['eligible'],eligible)
        state,_=p.advance({},physical(p.SSD_FLOOR))
        state,_=p.advance(state,physical(HIGH,1060))
        state,d=p.advance(state,physical(HIGH,1151));self.assertEqual(d['recovery_count'],1)
        state,d=p.advance(state,physical(HIGH,1150));self.assertEqual(d['recovery_count'],0)
        self.assertFalse(d['recovered']);self.assertTrue(d['eligible'])

    def test_contrary_fast_or_live_rechecks_break_runs_without_adding_samples(self):
        state,_=p.advance({},physical())
        state,d=p.advance(state,physical(at=1060),periodic=False)
        self.assertEqual(d['critical_count'],1);self.assertFalse(d['eligible'])
        state,_=p.advance(state,physical(LOW+1,1030),periodic=False)
        self.assertEqual(state['critical_count'],0)
        state,_=p.advance({},physical(p.SSD_FLOOR))
        state,_=p.advance(state,physical(HIGH,1060))
        state,_=p.advance(state,physical(HIGH,1120))
        state,d=p.advance(state,physical(HIGH,1180),periodic=False)
        self.assertFalse(d['recovered']);self.assertEqual(d['recovery_count'],2)
        state,d=p.advance(state,physical(HIGH-1,1150),periodic=False)
        self.assertEqual(d['recovery_count'],0)
        _,d=p.advance(state,physical(HIGH,1180));self.assertFalse(d['recovered'])

    def test_invalid_free_identity_and_policy_drift_fail_closed(self):
        for free in (-1,True,1.5,None):
            with self.assertRaises(ValueError):p.advance({},physical(free))
        state,_=p.advance({},physical())
        with self.assertRaisesRegex(ValueError,'identity_changed'):
            p.advance(state,{**physical(at=1060),'identity':'other'})
        with self.assertRaisesRegex(ValueError,'policy_changed'):
            p.advance(state,{**physical(at=1060),'policy':p.SSD})
        for state in ({'latched':True},{'policy':p.SSD}):
            with self.assertRaisesRegex(ValueError,'policy_changed'):p.advance(state,physical())

    def test_failed_observation_resets_counts_but_keeps_incident_latch(self):
        state,_=p.advance({},physical(p.SSD_FLOOR))
        for at in (1060,1120):state,_=p.advance(state,physical(HIGH,at))
        state=p.break_run(state)
        self.assertTrue(state['latched']);self.assertEqual(state['policy'],p.SSD_PHYSICAL)
        self.assertNotIn('last_sample_at',state)
        state,d=p.advance(state,physical(HIGH,1180))
        self.assertEqual(d['recovery_count'],1);self.assertFalse(d['recovered'])


class PhysicalJournal(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'journal.sqlite'
        self.now=1000;self.clock=patch.object(m.time,'time',side_effect=lambda:self.now);self.clock.start()
        self.store=m.Store(self.path);self.bridge=FakeBridge();self.samples={}
        self.bridge.observe=lambda key:dict(self.samples[key])

    def tearDown(self):self.store.close();self.clock.stop();self.temp.cleanup()

    def tick(self,free,at,os=None):
        self.now=at;self.samples={'ssd':physical(free,at)}
        if os is not None:self.samples['os']=dict(sample(os),identity='fixture-os')
        self.store.observations(self.samples,{},at)
        return self.store.dispatch(self.samples,self.bridge,self.path)

    def restart(self):self.store.close();self.store=m.Store(self.path)

    def test_restart_dedup_recovery_and_new_episode(self):
        self.assertEqual(self.tick(LOW,1000),'no_action');self.restart()
        self.assertEqual(self.tick(LOW,1060),'accepted');self.restart()
        self.assertEqual(self.tick(LOW,1120),'held_prior_delivery')
        self.assertEqual(len(self.bridge.calls),1)
        self.bridge.status='completed'
        self.assertEqual(self.tick(HIGH,1180),'no_action')
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM incidents WHERE recovered IS NULL').fetchone()[0],1)
        self.restart();self.tick(HIGH,1240);self.tick(HIGH,1300)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM incidents WHERE recovered IS NULL').fetchone()[0],0)
        self.assertEqual(self.tick(LOW,1360),'no_action')
        self.assertEqual(self.tick(LOW,1420),'accepted')
        self.assertEqual(len(self.bridge.calls),2)
        self.assertNotEqual(self.bridge.calls[0]['intent']['incidents'][0]['incident_id'],
                            self.bridge.calls[1]['intent']['incidents'][0]['incident_id'])

    def test_missing_mount_resets_debounce_and_does_not_recover(self):
        self.tick(LOW,1000)
        self.now=1060;self.store.observations({}, {'ssd':'mount_unavailable'},1060)
        self.restart();self.assertEqual(self.tick(LOW,1120),'no_action')
        self.assertEqual(self.tick(LOW,1180),'accepted')
        self.bridge.status='completed';self.tick(HIGH,1240);self.tick(HIGH,1300)
        self.now=1360;self.store.observations({}, {'ssd':'mount_unavailable'},1360)
        self.restart();self.tick(HIGH,1420)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM incidents WHERE recovered IS NULL').fetchone()[0],1)
        self.tick(HIGH,1480);self.tick(HIGH,1540)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM incidents WHERE recovered IS NULL').fetchone()[0],0)

    def test_missing_live_mount_prevents_post_and_resets_evidence(self):
        self.now=1000;self.samples={'ssd':physical(p.SSD_FLOOR)}
        self.store.observations(self.samples,{},self.now)
        self.bridge.observe=lambda key:(_ for _ in ()).throw(ValueError('missing mount'))
        self.assertEqual(self.store.dispatch(self.samples,self.bridge,self.path),'recovered_or_invalid_before_admission')
        self.assertEqual(self.bridge.calls,[])
        state=json.loads(self.store.db.execute('SELECT state FROM volume_state').fetchone()[0])
        self.assertTrue(state['latched']);self.assertEqual(state['recovery_count'],0)
        self.assertIsNone(state.get('last_sample_at'))
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM audit WHERE kind='observation_deferred'").fetchone()[0],1)

    def test_mixed_volume_batch_and_independent_recovery(self):
        self.assertEqual(self.tick(p.SSD_FLOOR,1000,os=92),'accepted')
        self.assertEqual({i['policy'] for i in self.bridge.calls[0]['intent']['incidents']},{p.OS,p.SSD_PHYSICAL})
        self.bridge.status='completed'
        self.tick(HIGH,1060,os=83)
        self.assertEqual(self.store.db.execute('SELECT volume FROM incidents WHERE recovered IS NULL').fetchone()[0],'ssd')
        self.tick(HIGH,1120,os=83);self.tick(HIGH,1180,os=83)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM incidents WHERE recovered IS NULL').fetchone()[0],0)

    def test_missing_ssd_keeps_os_admission_and_holds_ssd_recovery(self):
        self.store.observations({'ssd':physical(p.SSD_FLOOR)},{},1000)
        self.now=1060;self.samples={'os':dict(sample(98),identity='fixture-os')}
        self.store.observations(self.samples,{'ssd':'mount_unavailable'},self.now)
        self.assertEqual(self.store.dispatch(self.samples,self.bridge,self.path),'accepted')
        self.assertEqual([i['policy'] for i in self.bridge.calls[0]['intent']['incidents']],[p.OS])
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM incidents WHERE recovered IS NULL').fetchone()[0],2)

    def test_physical_phone_recovery_uses_free_bytes_and_requires_three_samples(self):
        self.tick(p.SSD_FLOOR,1000);sent=[]
        def send(*args):sent.append(args)
        self.store.phone('ssd',self.samples['ssd'],send,1000)
        self.assertEqual(sent[0][1],'critical');self.assertIn('policy='+p.SSD_PHYSICAL,sent[0][2])
        self.assertNotIn('headroom',sent[0][2])
        for at in (1060,1120):
            self.tick(HIGH,at);self.store.phone('ssd',self.samples['ssd'],send,at)
        self.assertEqual(len(sent),1)
        self.tick(HIGH,1180);self.store.phone('ssd',self.samples['ssd'],send,1180)
        self.assertEqual([x[1] for x in sent],['critical','normal'])


class PhysicalConfig(unittest.TestCase):
    def test_example_is_disabled_decimal_without_allocation_inputs(self):
        source=Path(__file__).resolve().parents[1]/'config.example.json'
        config=json.loads(source.read_text())
        self.assertEqual(config['volumes']['ssd']['policy'],p.SSD_DECIMAL)
        self.assertEqual(config['volumes']['os']['policy'],p.OS_DECIMAL)
        self.assertNotIn('allocation_input',config['volumes']['ssd'])
        self.assertFalse(config['activation_approved']);self.assertFalse(config['ssd_tuning_approved'])
        self.assertFalse(config['native_transport']['enabled'])
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'config.json';path.write_text(json.dumps(config));path.chmod(0o600)
            self.assertEqual(m.read_config(path)['volumes']['ssd']['policy'],p.SSD_DECIMAL)
            config['volumes']['ssd']['policy']=p.SSD;path.write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError,'reserve_aware_monitoring_disabled'):m.read_config(path)

    def test_physical_still_requires_ssd_tuning_activation_approval(self):
        c={'volumes':{'ssd':{'policy':p.SSD_PHYSICAL}},'activation_approved':True,'ssd_tuning_approved':False}
        with patch.object(m,'read_config',return_value=c),patch.object(m,'sample_volume',return_value=physical()), \
                patch.object(m.sys,'argv',['monitor','--config','unused','--activate']):
            with self.assertRaisesRegex(ValueError,'proposed_SSD_tuning_not_approved'):m.main()


if __name__=='__main__':unittest.main()
