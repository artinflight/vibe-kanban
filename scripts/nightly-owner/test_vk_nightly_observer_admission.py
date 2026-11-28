"""Observer allocation admission is distinct from keeping existing watches alive."""
import unittest
from vk_nightly_local_tracker import observer_guard


class ObserverAdmissionTests(unittest.TestCase):
    def config(self,**extra):
        return dict(minimum_mem_available_bytes=4000,minimum_swap_available_bytes=1000,
            maximum_observer_memory_bytes=2000,
            steady_resource_policy='bounded-cgroup-preserve-inode-drain-v1',**extra)

    def test_admit_first_then_preserve_bounded_drain_after_global_headroom_drop(self):
        memory={'MemAvailable':8000,'SwapFree':2000}
        guard=observer_guard(self.config(),mounted=lambda:True,memory=lambda:memory,
            cgroup_limits=lambda:('2000','0'))
        guard();guard.on_enrolled();memory.update(MemAvailable=1,SwapFree=0)
        guard() # no source FD close solely because another owner uses RAM

    def test_memory_floor_still_refuses_new_enrollment(self):
        guard=observer_guard(self.config(),mounted=lambda:True,
            memory=lambda:{'MemAvailable':3999,'SwapFree':2000},cgroup_limits=lambda:('2000','0'))
        with self.assertRaisesRegex(ValueError,'before enrollment'):guard()

    def test_transition_checks_real_enforcement_without_requiring_unused_allocation_again(self):
        memory={'MemAvailable':5000,'SwapFree':2000}
        guard=observer_guard(self.config(),mounted=lambda:True,memory=lambda:memory,cgroup_limits=lambda:('2000','0'))
        guard();memory['MemAvailable']=3900;guard.on_enrolled();guard()

    def test_unbounded_increased_or_swapping_cgroup_never_qualifies(self):
        for limits in [('max','0'),('2001','0'),('2000','max'),('2000','1')]:
            with self.subTest(limits=limits):
                guard=observer_guard(self.config(),mounted=lambda:True,
                    memory=lambda:{'MemAvailable':8000,'SwapFree':2000},cgroup_limits=lambda:limits)
                with self.assertRaisesRegex(ValueError,'enforcement'):guard()

    def test_mount_and_limit_loss_remain_fatal_after_ready(self):
        state={'mounted':True,'limits':('2000','0')}
        guard=observer_guard(self.config(),mounted=lambda:state['mounted'],
            memory=lambda:{'MemAvailable':8000,'SwapFree':2000},cgroup_limits=lambda:state['limits'])
        guard();guard.on_enrolled();state['mounted']=False
        with self.assertRaisesRegex(ValueError,'SSD unavailable'):guard()
        state['mounted']=True;state['limits']=('max','0')
        with self.assertRaisesRegex(ValueError,'enforcement'):guard()

    def test_legacy_policy_keeps_original_memory_behaviour(self):
        config=self.config();config.pop('steady_resource_policy');state={'MemAvailable':8000,'SwapFree':2000}
        guard=observer_guard(config,mounted=lambda:True,memory=lambda:state)
        guard();guard.on_enrolled();state['MemAvailable']=1
        with self.assertRaisesRegex(ValueError,'headroom'):guard()

    def test_opt_in_enrollment_reserves_actual_enforced_allocation(self):
        calls=[]
        config=self.config(allocation_admission_policy='actual-enforced-unused-cgroup-budget-v1',maximum_outbox_bytes=100)
        guard=observer_guard(config,mounted=lambda:True,memory=lambda:{'MemAvailable':2500,'SwapFree':0},
            cgroup_limits=lambda:('2000','0'),metadata_admission=lambda **kw:calls.append(kw))
        guard();self.assertEqual(calls[0]['maximum_memory_bytes'],2000)
        self.assertEqual(calls[0]['memory'](),2500);self.assertTrue(calls[0]['metadata_only'])
        guard.on_enrolled();guard();self.assertEqual(len(calls),1)

    def test_real_inode_observer_keeps_recording_after_steady_memory_dip(self):
        import json,tempfile,threading,time
        from pathlib import Path
        from vk_nightly_tracking import serve,request
        from vk_nightly_inode_journal import Journal
        with tempfile.TemporaryDirectory(dir='/dev/shm') as tmp:
            root=Path(tmp);source=root/'source';source.mkdir();body=source/'file';body.write_text('before')
            endpoint=root/'observer.sock';status=root/'status.json';stop=threading.Event();errors=[]
            memory={'MemAvailable':8000,'SwapFree':2000}
            guard=observer_guard(self.config(),mounted=lambda:True,memory=lambda:memory,cgroup_limits=lambda:('2000','0'))
            def worker():
                try:serve({'sources':[str(source)]},root/'journal.sqlite',endpoint,guard=guard,
                    status_path=status,journal_factory=Journal,stop=stop,on_enrolled=guard.on_enrolled)
                except BaseException as error:errors.append(error)
            thread=threading.Thread(target=worker);thread.start()
            try:
                end=time.monotonic()+10
                while not endpoint.exists():
                    if errors:raise errors[0]
                    if time.monotonic()>end:self.fail('real tiny observer did not enroll')
                    time.sleep(.01)
                h=json.loads(status.read_text());memory.update(MemAvailable=1,SwapFree=0);body.write_text('after')
                while True:
                    if errors:raise errors[0]
                    r=request(endpoint,h['instance'],0)
                    if str(body) in r['changed']:break
                    if time.monotonic()>end:self.fail('event not durably recorded after memory dip')
                    time.sleep(.01)
                self.assertTrue(r['ready']);self.assertEqual(r['errors'],[]);self.assertTrue(thread.is_alive())
            finally:stop.set();thread.join(timeout=5)
            self.assertFalse(thread.is_alive());self.assertEqual(errors,[])


if __name__=='__main__':unittest.main()
