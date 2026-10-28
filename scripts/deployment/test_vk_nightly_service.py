import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import vk_nightly_service as service
from vk_typed_recovery import checksum


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir='/dev/shm');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.ref=dict(unit='vk-nightly-test.service',owner_pid=123,owner_start_ticks=456,
            config=str(self.root/'controller'),result=str(self.root/'result'),result_binding=dict(phase='complete'))

    def saved(self,name,value):
        p=self.root/name;raw=json.dumps(value).encode();p.write_bytes(raw);p.chmod(0o600)
        return str(p),hashlib.sha256(raw).hexdigest()

    def test_service_package_includes_actual_dynamic_normal_reader(self):
        from vk_nightly_typed_worker import source_closure
        from vk_nightly_remote_consumer import bundle
        source=Path(__file__).parent
        closure=source_closure(source,'vk_nightly_service')
        self.assertTrue({'vk_nightly_composed_consumer.py','vk_nightly_composed_restore.py'}<=closure)
        with tempfile.TemporaryDirectory(dir='/dev/shm') as folder:
            for name in closure:(Path(folder)/name).write_bytes((source/name).read_bytes())
            wire=bundle(dict(fixture='source-package-only'),folder=folder)
            payload=json.loads(wire.splitlines()[0])
            self.assertIn('vk_nightly_composed_consumer',payload['sources'])
            self.assertIn('vk_nightly_composed_restore',payload['sources'])


    def test_only_exact_successful_terminal_invocation_can_be_adopted(self):
        def show(**changes):
            value=dict(MainPID='0',ActiveState='inactive',ExecMainStatus='0',ControlGroup='',
                       ExecMainPID='123',ExecMainStartTimestampMonotonic='4560000')
            value.update(changes);return '\n'.join(k+'='+v for k,v in value.items())
        self.assertTrue(service.terminal(self.ref,inspect=lambda *a,**k:show()))
        self.assertFalse(service.terminal(self.ref,inspect=lambda *a,**k:show(MainPID='123',ActiveState='active')))
        for changes in [dict(MainPID='124',ActiveState='active'),dict(ActiveState='failed'),
                        dict(ExecMainStatus='1'),dict(ControlGroup='/still-populated'),
                        dict(ExecMainPID='124'),dict(ExecMainStartTimestampMonotonic='5550000')]:
            with self.assertRaises(ValueError):service.terminal(self.ref,inspect=lambda *a,**k:show(**changes))
        with self.assertRaises(subprocess.TimeoutExpired):
            service.terminal(self.ref,inspect=lambda *a,**k:(_ for _ in ()).throw(subprocess.TimeoutExpired('same unit',15)))
        collected=lambda *a,**k:show(LoadState='not-found',ExecMainPID='0',ExecMainStartTimestampMonotonic='0')
        self.assertFalse(service.terminal(self.ref,inspect=collected,process_check=lambda _:True))
        # This only establishes former process absence. Native result/leases
        # remain independently mandatory in execute/reopen_component.
        self.assertTrue(service.terminal(self.ref,inspect=collected,process_check=lambda _:False))

    def test_terminal_reopen_authenticates_artifact_under_live_parent_guard(self):
        worker_path=self.root/'old-worker'
        control,sha=self.saved('controller',dict(worker_config=str(worker_path),worker_config_sha256='1'*64))
        result=dict(phase='complete',actual_independent_B_file_cycle_receipt_reopen_verified=True,
                    final_B_delivery=dict(instance='source'))
        self.saved('result',result)
        reference=dict(self.ref,config=control,config_sha256=sha)
        actual={k:v for k,v in result.items() if k!=service.PROOF['files']}
        db=SimpleNamespace(execute=lambda _:SimpleNamespace(fetchone=lambda:(json.dumps(actual),)),close=lambda:None)
        client=SimpleNamespace(connect=lambda *a,**kw:db)
        source=SimpleNamespace(reference=dict(instance='source'),check=lambda:None)
        worker=dict(B_index_name='map',B_checkpoint_sha256='2'*64)
        with patch.object(service,'terminal',return_value=True),patch.object(service,'configuration',return_value=worker) as config:
            self.assertEqual(service.reopen_component(client,reference,'files',source,guard=lambda:None),result)
            self.assertTrue(config.call_args.kwargs['authenticate_only'])
            with self.assertRaises(TimeoutError):
                service.reopen_component(client,reference,'files',source,
                    guard=lambda:(_ for _ in ()).throw(TimeoutError('parent deadline')))

    def test_SQL_membership_queries_preserve_rows_and_search_the_member_primary_key(self):
        import ast,sqlite3
        db=sqlite3.connect(':memory:');self.addCleanup(db.close)
        db.execute('create table members(name text primary key,state text,row blob) without rowid')
        db.execute('create table SQL_sources(path text primary key) without rowid')
        db.executemany('insert into members values(?,?,?)',(('sample/'+str(i),'verified-file',b'point') for i in range(2048)))
        db.executemany('insert into SQL_sources values(?)',(('/sample/'+str(i*100),) for i in range(20)))
        db.execute("insert into SQL_sources values('/missing')")
        db.execute("insert into SQL_sources values('invalid-prefix')")
        checked=0
        for filename in ('vk_nightly_sql_cycle.py','vk_nightly_finalize_current.py','vk_nightly_recovery_descriptor.py','vk_nightly_current_cycle.py'):
            tree=ast.parse(Path(service.__file__).with_name(filename).read_text())
            for node in ast.walk(tree):
                if not isinstance(node,ast.Constant) or not isinstance(node.value,str):continue
                sql=node.value
                if 'SQL_sources s' not in sql or 'members m on' not in sql:continue
                original=sql.replace('m.name=substr(s.path,2) and ','')
                self.assertEqual(set(db.execute(sql).fetchall()),set(db.execute(original).fetchall()))
                plan=db.execute('explain query plan '+sql).fetchall()
                self.assertTrue(any('SEARCH m USING PRIMARY KEY' in row[3] for row in plan),(filename,plan))
                checked+=1
        self.assertEqual(checked,5)

    def test_CLI_wrong_digest_refuses_without_source_or_B_work(self):
        path,_=self.saved('wrong-config',{'format':'vk-nightly-current-service-v1'})
        before=set(self.root.iterdir())
        result=subprocess.run([sys.executable,'-B',str(Path(service.__file__)),'--config',path,
            '--config-sha256','0'*64,'--preflight'],capture_output=True,text=True,timeout=10)
        self.assertNotEqual(result.returncode,0);self.assertIn('binding differs',result.stderr)
        self.assertEqual(set(self.root.iterdir()),before)

    def test_main_preserves_first_error_and_records_retryable_transport_without_acceptance(self):
        import io
        from vk_nightly_transport_diagnostics import finish
        process=SimpleNamespace(args=['ssh','desktop'],stdin=io.BytesIO(),stdout=io.BytesIO(),
            stderr=io.BytesIO(b'ssh: connect to host 10.0.0.109 port 22: Connection refused\n'),wait=lambda **_:255)
        error=EOFError('actual readiness EOF');finish(process,original=error)
        value=dict(status=str(self.root/'STATUS.private.json'))
        argv=['vk_nightly_service','--config',str(self.root/'unused'), '--config-sha256','a'*64]
        with patch.object(service.sys,'argv',argv),patch.object(service,'load',return_value=(value,{})), \
             patch.object(service,'execute',side_effect=error):
            with self.assertRaises(EOFError) as caught:service.main()
        self.assertIs(caught.exception,error);self.assertEqual(service.failure_exit_code(error),75)
        stopped=json.loads((self.root/'STOP.private.json').read_text())
        self.assertTrue(stopped['retryable_Desktop_transport_unavailable'])
        self.assertFalse(stopped['baseline_accepted']);self.assertFalse(stopped['schedule_enabled'])
        self.assertEqual(stopped['reason'],'actual readiness EOF')

    def test_scheduled_cohort_is_deterministic_per_evening_with_new_next_day_and_DST_end(self):
        template=dict(cycle=dict(cycle_binding=dict(cycle_kind='incremental'),
            SQL=dict(SQL_phase_index=dict(index_name='template',checkpoint_sha256='3'*64)),finalize={}))
        first=service.scheduled_cycle(template,'2026-10-27','4'*64)
        self.assertEqual(first,service.scheduled_cycle(template,'2026-10-27','4'*64))
        cycle=first['cycle'];binding=cycle['cycle_binding']
        self.assertEqual(binding['deadline_UTC'],'2026-10-28T08:00:00+00:00')
        self.assertEqual(binding['started_UTC'],'2026-10-28T02:00:00+00:00')
        self.assertEqual(cycle['SQL']['SQL_phase_index'],cycle['finalize']['SQL_phase'])
        self.assertEqual(cycle['SQL']['cohort_tag'],binding['SQL_cohort_tag'])
        from vk_nightly_b_controls import name as index_name
        self.assertEqual(index_name(cycle['SQL']['SQL_phase_index']['index_name']),
                         cycle['SQL']['SQL_phase_index']['index_name'])
        later=service.scheduled_cycle(template,'2026-10-28','4'*64)
        self.assertNotEqual(later['cycle']['SQL']['cohort_tag'],cycle['SQL']['cohort_tag'])
        self.assertEqual(template['cycle']['SQL']['SQL_phase_index']['index_name'],'template')
        bad=dict(template,existing_components={'files':{}})
        with self.assertRaises(ValueError):service.scheduled_cycle(bad,'2026-10-27','4'*64)

    def test_adopted_components_cannot_be_relabelled_as_an_ordinary_timed_cycle(self):
        from vk_nightly_current_cycle import run
        workers={name:dict(B_controls={},B_index_name='current',B_checkpoint_sha256='1'*64) for name in service.PROOF}
        owner=dict(config='fixture',sha256='2'*64,instance='one')
        settings=dict(cycle_binding=dict(deadline_UTC='2099-01-01T00:00:00+00:00',cycle_kind='incremental',
            SQL_cohort_tag='one',SQL_phase_index={'index_name':'SQL','checkpoint_sha256':'3'*64}),
            files=dict(source_observer=owner),SQL=dict(source_observer=owner,cohort_tag='one',
            SQL_phase_index={'index_name':'SQL','checkpoint_sha256':'3'*64}),runtime=dict(source_observer=owner),
            finalize=dict(current_map=dict(index_name='current',checkpoint_sha256='1'*64)))
        with patch('vk_nightly_current_cycle.file_cycle') as capture:
            with self.assertRaisesRegex(ValueError,'masquerade'):
                run(settings,workers,None,consumer=None,guard=lambda:None,
                    completed_components={name:{} for name in service.PROOF})
            capture.assert_not_called()


if __name__=='__main__':unittest.main()
