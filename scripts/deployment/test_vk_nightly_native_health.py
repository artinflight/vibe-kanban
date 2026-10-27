"""Exercise the actual embedded native guard with synthetic OS observations."""
import ast
import base64
from contextlib import nullcontext,contextmanager
import datetime
import io
import json
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from vk_nightly_desktop_objects import NATIVE,native_admission_timeout


class NativeHealthTests(unittest.TestCase):
    def guard(self, results):
        tree=ast.parse(NATIVE)
        functions=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in ('control_identity','actual_guard')]
        baseline=dict(NativeSerial='drive',Attributes=[dict(id=5,raw=dict(value=0))],Phy=[dict(id=10,value=2)])
        smart=dict(serial_number='drive',smart_status=dict(passed=True),temperature=dict(current=33),
            ata_smart_attributes=dict(table=baseline['Attributes']),sata_phy_event_counters=dict(table=baseline['Phy']))
        def result(value):
            if isinstance(value,BaseException):raise value
            return SimpleNamespace(stdout=json.dumps(value).encode(),check_returncode=lambda:None)
        calls=[]
        def run(command,**kwargs):
            calls.append(command)
            if command[0]=='powershell.exe':return result(dict(disk_number=3))
            self.assertEqual(kwargs['timeout'],90)
            return result(next(results))
        mm=SimpleNamespace(STOP_PATH='stop',STATE_PATH='state',bounded_read=lambda _: '{}',parse=json.loads,
            pause=Mock(),b_outside_monitor_scope=lambda *_:True,check_identity=Mock(),check_health=Mock())
        class Job:
            def __truediv__(self,_):return self
            def stat(self):raise FileNotFoundError
        space=dict(admitted_identity=dict(disk_number=3),health_timeout_used=False,job=Job(),baseline=baseline,
            CONFIG=dict(native_identity_mode='admission-plus-kernel-continuity-v1',identity_ps='probe',
                volume_device=123,protected_B_bytes=0),mm=mm,kernel_identity=lambda:dict(disk_number=3),
            subprocess=SimpleNamespace(run=run,TimeoutExpired=subprocess.TimeoutExpired),base64=base64,json=json,
            datetime=datetime,sys=SimpleNamespace(stderr=io.StringIO()),
            os=SimpleNamespace(stat=lambda _:SimpleNamespace(st_dev=123)),
            health_gate=nullcontext,shutil=SimpleNamespace(disk_usage=lambda _:SimpleNamespace(free=10**10)))
        exec(compile(ast.Module(body=functions,type_ignores=[]),'<actual-native-guard>','exec'),space)
        return space,calls,smart

    def test_timeout_requires_fresh_full_identity_and_all_controls_before_success(self):
        values=[];space,calls,smart=self.guard(iter(values))
        values.extend([subprocess.TimeoutExpired('smartctl',15),smart])
        outcome=space['actual_guard'](0)
        self.assertTrue(outcome['health_timeout_requalification_used'])
        self.assertEqual([x[0] for x in calls],['C:/ProgramData/MediaArchiveMonitor/smartctl/bin/smartctl.exe',
            'powershell.exe','C:/ProgramData/MediaArchiveMonitor/smartctl/bin/smartctl.exe'])
        self.assertEqual(space['mm'].pause.call_count,6)
        self.assertEqual(space['mm'].check_health.call_count,1)

    def test_second_timeout_fails_closed_without_unbounded_retry(self):
        space,calls,_=self.guard(iter([subprocess.TimeoutExpired('smartctl',15)]*2))
        with self.assertRaises(subprocess.TimeoutExpired):space['actual_guard'](0)
        self.assertEqual(len(calls),3)

    def test_new_STOP_during_requalification_prevents_second_health_read(self):
        space,calls,_=self.guard(iter([subprocess.TimeoutExpired('smartctl',15)]))
        space['mm'].pause.side_effect=[None,None,PermissionError('actual owner stop')]
        with self.assertRaisesRegex(PermissionError,'actual owner stop'):space['actual_guard'](0)
        self.assertEqual(len(calls),1)

    def test_permission_denial_or_failed_SMART_is_not_retried(self):
        space,calls,_=self.guard(iter([PermissionError('denied')]))
        with self.assertRaises(PermissionError):space['actual_guard'](0)
        self.assertEqual(len(calls),1)
        values=[];space,calls,smart=self.guard(iter(values));smart['smart_status']['passed']=False;values.append(smart)
        with self.assertRaises(AssertionError):space['actual_guard'](0)
        self.assertEqual(len(calls),1)

    def test_changed_hardware_counters_after_timeout_still_fail(self):
        values=[];space,calls,smart=self.guard(iter(values));smart['ata_smart_attributes']['table']=[dict(id=5,raw=dict(value=1))]
        values.extend([subprocess.TimeoutExpired('smartctl',15),smart])
        with self.assertRaisesRegex(AssertionError,'SMART counters changed'):space['actual_guard'](0)
        self.assertEqual(len(calls),3)

    def test_STOP_appearing_during_successful_health_read_prevents_IO(self):
        values=[];space,calls,smart=self.guard(iter(values));values.append(smart)
        space['mm'].pause.side_effect=[None,None,PermissionError('STOP arrived while reading health')]
        with self.assertRaisesRegex(PermissionError,'STOP arrived'):
            space['actual_guard'](0)
        self.assertEqual(len(calls),1);self.assertEqual(space['mm'].check_health.call_count,1)

    def test_busy_health_gate_never_admits_probe_or_cached_result(self):
        space,calls,_=self.guard(iter([]))
        @contextmanager
        def held_elsewhere():
            raise TimeoutError('bounded native observation ownership unavailable')
            yield
        space['health_gate']=held_elsewhere
        with self.assertRaisesRegex(TimeoutError,'ownership unavailable'):space['actual_guard'](0)
        self.assertEqual(calls,[])

    def test_transport_wait_covers_child_observation_budget_without_IO_grace(self):
        self.assertEqual(native_admission_timeout({'native_health_read_timeout_seconds':90,'identity_admission_timeout_seconds':45}),510)
        self.assertEqual(native_admission_timeout({'native_health_read_timeout_seconds':15,'identity_admission_timeout_seconds':45}),210)
        for bad in [0,-1,True,1000000]:
            with self.assertRaises(ValueError):native_admission_timeout({'native_health_read_timeout_seconds':bad})


if __name__=='__main__':unittest.main()
