import ast, importlib.util, sqlite3, sys, unittest, json, hashlib, datetime
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = Path('/mnt/vk-storage/vk-next-restart-20261010/full-recovery-readiness')
spec = importlib.util.spec_from_file_location('schema_fixed_actor', ROOT / 'publish-full-measured-catchup-r2.py')
actor = importlib.util.module_from_spec(spec); spec.loader.exec_module(actor)

class AttachmentSchemaTests(unittest.TestCase):
    def fixture(self, workspaces, sessions):
        c=sqlite3.connect(':memory:')
        c.executescript('CREATE TABLE workspaces(id INTEGER PRIMARY KEY, container_ref TEXT); CREATE TABLE sessions(id INTEGER PRIMARY KEY, workspace_id INTEGER, agent_working_dir TEXT);')
        c.executemany('INSERT INTO workspaces VALUES(?,?)',workspaces)
        c.executemany('INSERT INTO sessions VALUES(?,?,?)',sessions)
        return c
    def test_workspace_without_session_retains_base(self):
        self.assertEqual(actor.workspace_attachment_bases(self.fixture([(1,'/fixture/w')],[])),{Path('/fixture/w')})
    def test_relative_session_directory_matches_runtime(self):
        self.assertEqual(actor.workspace_attachment_bases(self.fixture([(1,'/fixture/w')],[(1,1,'repo')])),{Path('/fixture/w'),Path('/fixture/w/repo')})
    def test_null_and_empty_session_directories_preserve_container(self):
        self.assertEqual(actor.workspace_attachment_bases(self.fixture([(1,'/fixture/w')],[(1,1,None),(2,1,'')])),{Path('/fixture/w')})
    def test_multiple_sessions_and_workspaces_deduplicate(self):
        got=actor.workspace_attachment_bases(self.fixture([(1,'/fixture/a'),(2,'/fixture/b')],[(1,1,'r'),(2,1,'r'),(3,2,'q')]))
        self.assertEqual(got,{Path('/fixture/a'),Path('/fixture/a/r'),Path('/fixture/b'),Path('/fixture/b/q')})
    def test_null_container_is_not_guessed_or_created(self):
        self.assertEqual(actor.workspace_attachment_bases(self.fixture([(1,None)],[(1,1,'r')])),set())
    def test_empty_registered_container_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'Empty registered'):actor.workspace_attachment_bases(self.fixture([(1,'')],[]))
    def test_absolute_session_directory_matches_pathbuf_join(self):
        self.assertEqual(actor.workspace_attachment_bases(self.fixture([(1,'/fixture/a')],[(1,1,'/fixture/b')])),{Path('/fixture/a'),Path('/fixture/b')})
    def test_fresh_attempt_preserves_original_backup(self):
        self.assertNotEqual(actor.ATTEMPT,actor.ROOT)
        self.assertTrue((actor.ROOT/'final-fenced-current-db.sqlite').exists())
        self.assertFalse((actor.ATTEMPT/'final-fenced-current-db.sqlite').exists())

suite=unittest.defaultTestLoader.loadTestsFromTestCase(AttachmentSchemaTests)
result=unittest.TextTestRunner(verbosity=2).run(suite)
assert result.wasSuccessful()
live=sqlite3.connect(actor.DB.as_uri()+'?mode=ro',uri=True)
live.execute('pragma query_only=ON')
live_bases=actor.workspace_attachment_bases(live)
# Test the exact query on a disposable copy with the prepared candidate migration.
preimage=sqlite3.connect((ROOT/'final-fenced-current-db.sqlite').as_uri()+'?mode=ro',uri=True)
candidate=sqlite3.connect(':memory:');preimage.backup(candidate)
before=actor.workspace_attachment_bases(candidate)
migration=ROOT.parent/'full-recovery-readiness-source/crates/db/migrations/20261009000000_local_issue_assignments.sql'
candidate.executescript(migration.read_text())
after=actor.workspace_attachment_bases(candidate)
assert before==after and candidate.execute('pragma integrity_check').fetchone()[0]=='ok'
# Run the actual actor's prepared-input guard statements; stop before phase/wait/start.
tree=ast.parse((ROOT/'publish-full-measured-catchup-r2.py').read_text())
main=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='main')
guards=[]
for node in main.body[2:]:
    if isinstance(node,ast.Expr) and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id=='phase':break
    guards.append(node)
exec(compile(ast.Module(body=guards,type_ignores=[]),'<actual-prepared-actor-guards>','exec'),actor.__dict__)
assert not (actor.ATTEMPT/'final-native-db-images').exists()
receipt={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'fixture_tests_passed':result.testsRun,'real_current_schema_query':'passed read-only','live_resolved_bases':len(live_bases),'existing_attachment_dirs':sum((p/'.vibe-attachments').is_dir() for p in live_bases),'copied_preimage_bases':len(before),'prepared_candidate_migration_query':'passed; exact same paths before/after migration; integrity ok','actual_prepared_actor_input_guards':'passed against actual server/backstop/frontend artifact and incumbent identity','new_candidate_launched':False,'production_changed':False,'source_query_contract':'workspace.container_ref + session.agent_working_dir; no ensure/create or guessed worktree_path','actor_sha256':hashlib.sha256((ROOT/'publish-full-measured-catchup-r2.py').read_bytes()).hexdigest()}
(ROOT/'MEASURED_CATCHUP_SCHEMA_TESTS.safe.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
