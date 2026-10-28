from types import SimpleNamespace
import unittest
from unittest.mock import patch

import vk_nightly_runtime_cycle as cycle
from vk_nightly_typed_worker import ResourceDeferred


class RuntimePhaseClockTests(unittest.TestCase):
    def run_wait(self,phase_elapsed):
        now=[0.0];seen=[]
        worker=dict(timeout_seconds=3600,B_controls={},maximum_source_bytes=1024,
            memory_floor_bytes=4096,root_floor_bytes=2048,swap_floor_bytes=1024,
            map_binding=dict(source_paths=['/fixture/gateway'],
                format='vk-nightly-explicit-runtime-dependency-component-v1',kernel_journal_coverage_claimed=False))
        config=dict(source_observer={},SQL_predecessor={'config':'fixture','config_sha256':'a'*64},
            maximum_predecessor_seconds=16*3600,runtime_paths=['/fixture/gateway'])
        def guard(bound,started):
            seen.append((bound['timeout_seconds'],now[0]-started))
            for key in ('memory_floor_bytes','root_floor_bytes','swap_floor_bytes'):
                self.assertEqual(bound[key],worker[key])
            if now[0]-started>bound['timeout_seconds']:raise ResourceDeferred('finite worker phase expired')
        def source(*_,guard):return SimpleNamespace(check=guard)
        def wait(reference,owner,**kwargs):
            now[0]=3601;owner.check() # Longer than capture, within original wait.
        def sample(paths,*,checkpoint,**kwargs):
            now[0]+=phase_elapsed;checkpoint()
            raise RuntimeError('reached capture with a separate deadline')
        with patch.object(cycle.time,'monotonic',side_effect=lambda:now[0]), \
             patch.object(cycle,'host_guard',side_effect=guard),patch.object(cycle,'Source',side_effect=source), \
             patch.object(cycle,'read_owned'),patch.object(cycle,'predecessor',side_effect=wait), \
             patch.object(cycle,'sample_runtime_files',side_effect=sample),patch.object(cycle,'DesktopControls') as B:
            expected=ResourceDeferred if phase_elapsed>3600 else RuntimeError
            with self.assertRaisesRegex(expected,'finite worker phase' if phase_elapsed>3600 else 'separate deadline'):
                cycle.run(config,worker,report=lambda _:None)
            B.assert_not_called()
        return seen

    def test_declared_sixteen_hour_wait_does_not_consume_one_hour_capture(self):
        seen=self.run_wait(1)
        self.assertIn((57600,3601),seen);self.assertIn((3600,1),seen)

    def test_capture_still_expires_under_its_original_one_hour_limit(self):
        self.run_wait(3601)


if __name__=='__main__':unittest.main()
