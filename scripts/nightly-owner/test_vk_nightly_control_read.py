"""Actual embedded current-control policy; synthetic reads, no live controls."""
import ast,json,unittest
from types import SimpleNamespace
from vk_nightly_desktop_objects import NATIVE

class ControlReadTests(unittest.TestCase):
    def policy(self,read,*,deadline=100):
        now=[0.0];sleeps=[]
        def sleep(delay):sleeps.append(delay);now[0]+=delay
        def budget(maximum=None):
            if now[0]>=deadline:raise TimeoutError('actual whole deadline')
            return deadline-now[0] if maximum is None else min(maximum,deadline-now[0])
        def pause(value):
            if 'OwnerPause' in value and value['OwnerPause'] is not False:raise ValueError('actual owner pause')
        space=dict(time=SimpleNamespace(monotonic=lambda:now[0],sleep=sleep),time_budget=budget,
            mm=SimpleNamespace(STOP_PATH='current-stop',STATE_PATH='current-state',parse=json.loads,pause=pause),
            current_control_bytes=read)
        nodes=[n for n in ast.parse(NATIVE).body if isinstance(n,(ast.ClassDef,ast.FunctionDef))
               and n.name in ('CurrentControlReplaced','current_controls')]
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'<actual-current-controls>','exec'),space)
        return space,now,sleeps

    def error(self,code):
        error=PermissionError(13,'synthetic Windows control unavailable');error.winerror=code;return error

    def test_short_sharing_retries_whole_pair_and_observes_new_STOP(self):
        reads=[];stopped=[False]
        def read(path):
            reads.append(path)
            if path=='current-state':stopped[0]=True;raise self.error(32)
            return json.dumps({'OwnerPause':stopped[0]}).encode()
        p,now,sleeps=self.policy(read)
        with self.assertRaisesRegex(ValueError,'actual owner pause'):p['current_controls']()
        self.assertEqual(reads,['current-stop','current-state','current-stop'])
        self.assertEqual(sleeps,[.1]);self.assertLess(now[0],2)

    def test_only_supported_atomic_gap_and_lock_codes_retry_same_current_paths(self):
        for code in (2,3,32,33):
            with self.subTest(code=code):
                reads=[]
                def read(path):
                    reads.append(path)
                    if len(reads)==1:raise self.error(code)
                    return b'{"OwnerPause":false}'
                p,_,sleeps=self.policy(read);result=p['current_controls']()
                self.assertEqual(set(result),{'current-stop','current-state'})
                self.assertEqual(reads,['current-stop','current-stop','current-state']);self.assertEqual(sleeps,[.1])

    def test_true_access_denial_and_unknown_permission_error_never_retry(self):
        for error in (self.error(5),PermissionError(13,'unknown denial')):
            reads=[]
            def denied(path):reads.append(path);raise error
            p,_,sleeps=self.policy(denied)
            with self.assertRaises(PermissionError) as caught:p['current_controls']()
            self.assertIs(caught.exception,error);self.assertEqual(len(reads),1);self.assertEqual(sleeps,[])

    def test_persistent_lock_or_missing_record_fails_despite_readable_stale_backup(self):
        for code in (2,32,33):
            reads=[]
            def unavailable(path):
                reads.append(path)
                if path.endswith('.bak'):return b'{"OwnerPause":false}'
                raise self.error(code)
            p,now,sleeps=self.policy(unavailable)
            with self.assertRaises(PermissionError):p['current_controls']()
            self.assertEqual(len(reads),20);self.assertEqual(set(reads),{'current-stop'})
            self.assertEqual(len(sleeps),19);self.assertLessEqual(now[0],2)

    def test_malformed_or_paused_current_record_never_uses_fallback(self):
        for raw in (b'{',b'{"OwnerPause":true}',b'{"OwnerPause":"false"}'):
            reads=[]
            def read(path):reads.append(path);return raw
            p,_,sleeps=self.policy(read)
            with self.assertRaises(ValueError):p['current_controls']()
            self.assertEqual(reads,['current-stop']);self.assertEqual(sleeps,[])

    def test_whole_deadline_caps_observation_and_restarts_no_more_reads(self):
        reads=[]
        def read(path):reads.append(path);raise self.error(32)
        p,now,_=self.policy(read,deadline=.15)
        with self.assertRaises(TimeoutError):p['current_controls']()
        self.assertAlmostEqual(now[0],.15);self.assertEqual(len(reads),2)

    def test_replaced_inode_restarts_pair_without_accepting_old_allow(self):
        reads=[];namespace={}
        def read(path):
            reads.append(path)
            if len(reads)==2:raise namespace['CurrentControlReplaced']('replaced')
            return b'{"OwnerPause":true}' if len(reads)>2 else b'{"OwnerPause":false}'
        p,_,sleeps=self.policy(read);namespace.update(p)
        with self.assertRaisesRegex(ValueError,'owner pause'):p['current_controls']()
        self.assertEqual(reads,['current-stop','current-state','current-stop']);self.assertEqual(sleeps,[.1])

if __name__=='__main__':unittest.main()
