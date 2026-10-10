import ast, datetime, hashlib, importlib.util, json, shutil, subprocess, unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.dont_write_bytecode=True
Q=Path('/mnt/vk-storage/vk-next-restart-20261010/full-recovery-readiness')
spec=importlib.util.spec_from_file_location('actor',Q/'publish-full-measured-catchup-r2.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
GiB=1024**3
class Budgets(unittest.TestCase):
    def check(self,raw=15*GiB,count=500,bfree=69*GiB,sfree=17*GiB,snap=2*GiB):
        return a.check_catchup_budget(raw,count,bfree,sfree,snap)
    def test_previous_failure_range_now_measured(self):self.assertEqual(self.check()['source_payload_bytes'],15*GiB)
    def test_full_input_over_allocation_fails(self):
        with self.assertRaisesRegex(AssertionError,'24GiB'):self.check(raw=24*GiB+1)
    def test_distinct_stream_metadata_bound_fails(self):
        with self.assertRaisesRegex(AssertionError,'tar metadata'):self.check(raw=24*GiB,count=40000)
    def test_desktop_requires_stream_plus_reserve(self):
        with self.assertRaisesRegex(AssertionError,'Desktop B'):self.check(bfree=28*GiB-1)
    def test_ssd_requires_snapshots_plus_reserve(self):
        with self.assertRaisesRegex(AssertionError,'SSD'):self.check(sfree=4*GiB-1)
    def test_exact_capacity_boundary_passes(self):self.check(bfree=28*GiB,sfree=4*GiB)
    def test_negative_payload_fails(self):
        with self.assertRaises(AssertionError):self.check(raw=-1)
    def test_preflight_precedes_service_effects_and_runs_after_drain(self):
        tree=ast.parse((Q/'publish-full-measured-catchup-r2.py').read_text());f=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        calls=[(n.lineno,ast.unparse(n.func)) for n in ast.walk(f) if isinstance(n,ast.Call)]
        pres=sorted(l for l,n in calls if n=='catchup_preflight')
        effects=sorted(l for l,n in calls if n=='handoff.route')
        self.assertEqual(len(pres),2);self.assertLess(max(pres),min(effects))
    def test_unknown_exception_is_not_published_and_http_readback_verified(self):
        import tempfile
        with tempfile.TemporaryDirectory(dir=Q,prefix='terminal-checkpoint-fixture-') as d:
            root=Path(d);(root/'actor-state.safe.json').write_text(json.dumps({'phase':'fixture'}));(root/'failure.safe.json').write_text(json.dumps({'reason':'PRIVATE-FIXTURE-DO-NOT-PUBLISH','error_type':'AssertionError','candidate_started':False}))
            seen=[]
            def fake(args,**kwargs):
                seen.append(args)
                if '--method' in args:
                    text=json.loads((root/'github-terminal-request.safe.json').read_text())['body'];self.assertNotIn('PRIVATE-FIXTURE',text)
                    return json.dumps({'id':42,'html_url':'https://github.com/artinflight/vibe-kanban/pull/242#issuecomment-42'})
                return json.dumps({'id':42,'html_url':'https://github.com/artinflight/vibe-kanban/pull/242#issuecomment-42','body':json.loads((root/'github-terminal-request.safe.json').read_text())['body']})
            with patch.object(a,'ATTEMPT',root),patch.object(a,'save',lambda n,v,**kw:(root/n).write_text(json.dumps(v))),patch.object(a,'terminal_live_readback',lambda:{'fixture':True}),patch.object(a.subprocess,'check_output',fake):a.publish_github_terminal_outcome()
            self.assertEqual(len(seen),2);self.assertTrue(json.loads((root/'github-terminal-checkpoint.safe.json').read_text())['verified'])
suite=unittest.defaultTestLoader.loadTestsFromTestCase(Budgets);result=unittest.TextTestRunner(verbosity=2).run(suite);assert result.wasSuccessful()
# Reproduce the exact formerly failing sum against real selected paths + retained consistent images.
selected,signatures,roots=a.select_native_catchup()
old_images=list((Q/'attempt-schema-fix-20261010T1720/final-native-db-images').iterdir())
assert len(selected)==len(set(selected))
raw=sum(p.lstat().st_size for p in selected+old_images)
assert raw>8*GiB
budget=a.catchup_preflight()
a.check_catchup_budget(raw,len(selected)+len(old_images),budget['B_free_bytes'],budget['SSD_free_bytes'],budget['snapshot_allocation_bytes'])
# Bind actual selected scope to old source logic; no omission to make the guard pass.
tree=ast.parse((Q/'publish-full-schema-fixed-r1.py').read_text());f=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='final_native_catchup')
stop=next(i for i,n in enumerate(f.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='images' for t in n.targets));f.body=f.body[3:stop]+ast.parse('return selected, signatures, existing_attachment_roots').body
helper=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='workspace_attachment_bases')
env=dict(a.__dict__);env['timezone']=datetime.timezone
exec(compile(ast.Module(body=[helper,f],type_ignores=[]),'<old-selection-comparison>','exec'),env)
original,_,_=env['final_native_catchup']();assert set(original)==set(selected)
# Exact tar producer subprocess contract unchanged; only stream allocation corrected.
newtree=ast.parse((Q/'publish-full-measured-catchup-r2.py').read_text())
orig=ast.parse((Q/'publish-full-schema-fixed-r1.py').read_text())
oldprod=next(n for n in ast.walk(orig) if isinstance(n,ast.FunctionDef) and n.name=='produce')
newprod=next(n for n in ast.walk(newtree) if isinstance(n,ast.FunctionDef) and n.name=='produce')
assert ast.dump(oldprod,include_attributes=False)==ast.dump(newprod,include_attributes=False)
r={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'regressions_passed':result.testsRun,'actual_current_selection_entries':len(selected),'actual_raw_bytes_with_retained_verified_images':raw,'same_old_selected_path_set':True,'same_tar_producer_AST':True,'actual_preflight':budget,'source_sha256':hashlib.sha256((Q/'publish-full-measured-catchup-r2.py').read_bytes()).hexdigest(),'production_changed':False,'new_candidate_started':False}
(Q/'MEASURED_CATCHUP_TESTS.safe.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
