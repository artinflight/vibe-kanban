"""Injected producer/Store/codec tests; these do NOT prove a live native wake."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import monitor
import native_adapter as native
import pressure
import t26_watch as watch
from test_t26 import sample

HERE = Path(__file__).resolve().parents[1]


class CodecFixture(native.NativeAdapter):
    """Existing native codec over injected receipts; never addresses a real owner."""
    def __init__(self, samples):
        self.samples = samples
        self.posts = []
        self.gets = []
        self.receipts = {}
        binding = {'workspace_id': '00000000-0000-4000-8000-000000000001',
                   'session_id': '00000000-0000-4000-8000-000000000002',
                   'executor_config_sha256': '0'*64}
        super().__init__(binding, self.exchange, self.observe, 30)

    def observe(self, key):
        return copy.deepcopy(self.samples[key])

    def exchange(self, method, path, body):
        if method == 'POST':
            self.posts.append(copy.deepcopy(body))
            intent = body['intent']
            response = {'protocol':native.PROTOCOL, 'outcome':'accepted', 'reason':'execution_bound',
                        'no_admission':False, 'automatic_launch_queued':False, 'replay':False,
                        'receipt': {'batch_id':body['batch_id'], 'workspace_id':intent['workspace_id'],
                                    'session_id':intent['session_id'], 'intent_sha256':body['intent_sha256'],
                                    'attempt_id':body['attempt_id'], 'state':'accepted', 'reason':'execution_bound',
                                    'execution_id':str(uuid.uuid4())}, 'execution_status':'completed'}
            self.receipts[body['batch_id']] = response
            return response
        self.gets.append(path)
        batch = path.split('/')[-1].split('?')[0]
        return self.receipts[batch]


class NtfyWake(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = monitor.Store(self.root/'incidents.sqlite')
        self.config = {'state_file':str(self.root/'incidents.sqlite'), 'ntfy_wake':True,
                       'root_notification_state_dir':str(self.root/'resource-guard'),
                       'native_transport':{'enabled':True},
                       'volumes':{'os':{'phone':False}, 'ssd':{'phone':True}}}
        self.owner = {'coding_or_script_turns':[], 'independent_jobs':[], 'queued':[],
                      'process_ids':[], 'inventory_unknown':False}
        self.notifications = []
        self.meta = {}

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def root_receipt(self, now, kind='low'):
        root = Path(self.config['root_notification_state_dir']);root.mkdir(exist_ok=True)
        (root/'root-headroom-alert-state').write_text('low' if kind == 'low' else 'normal')
        (root/'root-headroom-last-alert-at').write_text(str(int(now)))

    def run_cycle(self, now, samples, owner=None, bridge=None, publisher=None):
        bridge = bridge or CodecFixture(samples)
        def publish(key, severity, detail):
            self.notifications.append((key,severity,detail))
        with patch.object(monitor.time,'time',return_value=now):
            self.meta, result = watch.cycle(self.store,self.config,samples,{},owner or self.owner,self.meta,now,
                                           bridge_factory=lambda _:bridge,
                                           publisher_factory=lambda _:publisher or publish)
        return result,bridge

    def test_each_low_drive_reaches_existing_codec_with_drive_free_and_threshold(self):
        for key, free in [('os',9_999_999_999),('ssd',24_999_999_999)]:
            with self.subTest(drive=key):
                self.store.close()
                self.store = monitor.Store(self.root/(key+'.sqlite'))
                self.meta = {}
                self.root_receipt(1000)
                values = {'os':sample('os',20_000_000_000), 'ssd':sample('ssd',30_000_000_000)}
                values[key] = sample(key,free)
                result, bridge = self.run_cycle(1000,values)
                self.assertEqual(result['status'],'accepted')
                self.assertEqual(len(bridge.posts),1)
                intent = bridge.posts[0]['intent']
                self.assertEqual(len(intent['incidents']),1)
                self.assertEqual(intent['incidents'][0]['policy'],values[key]['policy'])
                self.assertIn(str(free)+' bytes',intent['prompt'])
                self.assertIn(str(pressure.DECIMAL_POLICIES[values[key]['policy']])+' bytes',intent['prompt'])
                self.assertIn('/dev/test-'+key,intent['prompt'])
                self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM incidents').fetchone()[0],1)
                # Repeated low observations are not another accepted dispatch.
                values = {k:dict(v,at=1060) for k,v in values.items()}
                self.run_cycle(1060,values,bridge=bridge)
                self.assertEqual(len(bridge.posts),1)

    def test_ssd_ntfy_uses_exact_bytes_threshold_and_affected_drive(self):
        result,_ = self.run_cycle(1000,{'ssd':sample('ssd',2_000_000_000)})
        self.assertEqual(result['ntfy']['ssd'],'sent')
        key,level,text = self.notifications[0]
        self.assertEqual(key,'Work SSD (/mnt/vk-storage)')
        self.assertEqual(level,'warning')
        for value in ['available=2000000000 bytes','threshold=25000000000 bytes','device=/dev/test-ssd']:
            self.assertIn(value,text)

    def test_root_requires_successful_existing_ntfy_receipt_not_recovery_or_future(self):
        values={'os':sample('os',9_999_999_999)}
        for kind,stamp in [('recovery',1000),('low',1001)]:
            self.root_receipt(stamp,kind)
            result,bridge=self.run_cycle(1000,values)
            self.assertEqual(result['status'],'pending_ntfy_receipt')
            self.assertEqual(bridge.posts,[])
            self.meta={}
        self.root_receipt(1000)
        result,bridge=self.run_cycle(1000,values)
        self.assertEqual(result['status'],'accepted')

    def test_unknown_ntfy_delivery_is_durable_and_does_not_start_or_blindly_republish(self):
        def lost(*args):raise TimeoutError()
        result,bridge=self.run_cycle(1000,{'ssd':sample('ssd',1)},publisher=lost)
        self.assertEqual(result['ntfy']['ssd'],'unknown')
        self.assertEqual(result['status'],'pending_ntfy_receipt')
        self.assertEqual(bridge.posts,[])
        self.run_cycle(1060,{'ssd':sample('ssd',1,1060)},bridge=bridge,
                       publisher=lambda *args:self.fail('no blind duplicate publish'))
        self.assertEqual(bridge.posts,[])
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM incidents').fetchone()[0],1)

    def test_busy_owner_preserves_pending_then_wakes_once_when_idle(self):
        values={'ssd':sample('ssd',1)}
        result,bridge=self.run_cycle(1000,values,owner=dict(self.owner,coding_or_script_turns=['active']))
        self.assertEqual(result['status'],'pending_owner_busy_or_inventory_unknown')
        self.assertEqual(bridge.posts,[])
        self.assertEqual(self.store.db.execute('SELECT delivery FROM incidents').fetchone()[0],'pending')
        bridge.samples={'ssd':sample('ssd',1,1060)}
        result,_=self.run_cycle(1060,bridge.samples,bridge=bridge)
        self.assertEqual(result['status'],'accepted')
        self.run_cycle(1120,{'ssd':sample('ssd',1,1120)},bridge=bridge)
        self.assertEqual(len(bridge.posts),1)
        self.assertEqual(len(self.notifications),1)

    def test_recovery_reaches_ntfy_but_never_new_wake(self):
        _,bridge=self.run_cycle(1000,{'ssd':sample('ssd',1)})
        for now in [1060,1120,1180]:
            self.run_cycle(now,{'ssd':sample('ssd',27_000_000_000,now)},bridge=bridge)
        self.assertEqual(len(bridge.posts),1)
        self.assertEqual([r[1] for r in self.notifications],['warning','normal'])
        self.assertIn('Recovery',self.notifications[-1][2])
        self.assertIsNotNone(self.store.db.execute('SELECT recovered FROM incidents').fetchone()[0])

    def test_native_disabled_preserves_low_event_without_any_request(self):
        self.config['native_transport']['enabled']=False
        result,bridge=self.run_cycle(1000,{'ssd':sample('ssd',1)})
        self.assertEqual(result['status'],'pending_native_release_and_binding')
        self.assertEqual(result['ntfy']['ssd'],'sent')
        self.assertEqual(bridge.posts,[])

    def test_equality_does_not_publish_or_wake(self):
        result,bridge=self.run_cycle(1000,{'os':sample('os',10_000_000_000),
                                         'ssd':sample('ssd',25_000_000_000)})
        self.assertEqual(self.notifications,[])
        self.assertEqual(bridge.posts,[])
        self.assertEqual(result['pending_incidents'],0)

    def test_guard_log_cap_preserves_old_history_and_notification_still_works(self):
        state=self.root/'resource-guard';state.mkdir()
        history=state/'guard.log'
        with history.open('wb') as stream:
            stream.write(b'old-history-preserved\n')
            stream.truncate(2097152)
        code='source "$GUARD_SOURCE"; log "must not grow"; printf "done\n"'
        env={'PATH':os.environ['PATH'],'HOME':str(self.root),'XDG_STATE_HOME':str(self.root),
             'GUARD_SOURCE':str(HERE/'resource-guard.sh')}
        run=subprocess.run(['bash'],input=code,text=True,capture_output=True,env=env,timeout=5)
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertEqual(history.stat().st_size,2097152)
        with history.open('rb') as stream:
            self.assertEqual(stream.read(22),b'old-history-preserved\n')

    def test_actual_root_bash_producer_receipt_and_exact_low_recovery_payloads(self):
        code = '''source "$GUARD_SOURCE"
root_available_bytes() { printf '%s\\n' "$INJECTED_FREE"; }
send_notification() { printf '%s\\n%s\\n' "$1" "$4" >> "$STATE_DIR/notifications.txt"; }
check_root_headroom
'''
        env={'PATH':os.environ['PATH'],'HOME':str(self.root),'XDG_STATE_HOME':str(self.root),
             'GUARD_SOURCE':str(HERE/'resource-guard.sh'),'INJECTED_FREE':'9999999999'}
        run=subprocess.run(['bash'],input=code,text=True,capture_output=True,env=env,timeout=5)
        self.assertEqual(run.returncode,0,run.stderr)
        body=(self.root/'resource-guard/notifications.txt').read_text()
        self.assertIn('9999999999 bytes',body)
        self.assertIn('10000000000 bytes',body)
        receipt=watch.root_notification_receipt(self.config)
        self.assertEqual(receipt['kind'],'low')
        # This root producer never calls the wake adapter itself; its receipt is consumed by cycle().
        now=time.time()
        result,bridge=self.run_cycle(now,{'os':sample('os',9_999_999_999,now)})
        self.assertEqual(result['status'],'accepted')
        env['INJECTED_FREE']='12000000000'
        run=subprocess.run(['bash'],input=code,text=True,capture_output=True,env=env,timeout=5)
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertEqual(watch.root_notification_receipt(self.config)['kind'],'recovery')
        now=time.time()
        self.run_cycle(now,{'os':sample('os',12_000_000_000,now)},bridge=bridge)
        self.assertEqual(len(bridge.posts),1)


if __name__=='__main__':unittest.main()
