"""No network, Vibe writes, native processes or model inference."""
import ast
import json
import sqlite3
import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "advisory_worker_profile.py"
spec = importlib.util.spec_from_file_location("worker_profile", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ProfileTests(unittest.TestCase):
    def fixture(self):
        return {"executors": {"CODEX": {
            "DEFAULT": {"CODEX": {"model": "gpt-6.1-sol",
                "model_reasoning_effort": "high", "sandbox": "workspace-write",
                "append_prompt": "Preserve explicit owner constraints", "plan": False}},
            "recently_used_models": ["gpt-6.1-sol"],
            "OWNER": {"CODEX": {"sandbox": "read-only", "model": "owner-choice"}}},
            "CLAUDE_CODE": {"DEFAULT": {"CLAUDE_CODE": {"model": "sonnet"}}}}}

    def test_only_adds_the_isolated_profile(self):
        before = self.fixture()
        after = module.prepare(before)
        worker = after["executors"]["CODEX"].pop(module.NAME)["CODEX"]
        self.assertEqual(after, before)
        self.assertNotIn(module.NAME, before["executors"]["CODEX"])
        expected = dict(before["executors"]["CODEX"]["DEFAULT"]["CODEX"],
                        sandbox="read-only", ask_for_approval="never")
        self.assertEqual(worker, expected)

    def test_idempotent_readback(self):
        before = self.fixture()
        after = module.prepare(before)
        self.assertEqual(module.prepare(after), after)
        self.assertTrue(module.verify(before, after))

    def test_collision_is_not_overwritten(self):
        before = self.fixture()
        before["executors"]["CODEX"][module.NAME] = {"CODEX": {"model": "owner-choice"}}
        with self.assertRaisesRegex(ValueError, "already"):
            module.prepare(before)

    def test_changed_default_is_not_guessed(self):
        before = self.fixture()
        before["executors"]["CODEX"]["DEFAULT"]["CODEX"]["model"] = "owner-choice"
        with self.assertRaisesRegex(ValueError, "Default"):
            module.prepare(before)

    def test_intervening_change_is_not_accepted(self):
        before = self.fixture()
        after = module.prepare(before)
        after["executors"]["CODEX"]["DEFAULT"]["CODEX"]["model_reasoning_effort"] = "xhigh"
        with self.assertRaisesRegex(ValueError, "Readback"):
            module.verify(before, after)


class ExistingGuardTests(unittest.TestCase):
    def recommend(self, config):
        root = SOURCE.parents[1]
        path = root / "scripts/dot-connector/deployed-20261029/connector/adapter.py"
        tree = ast.parse(path.read_text())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                        and n.name == "codex_recommend_config")
        namespace = {"json": json}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), namespace)
        return namespace["codex_recommend_config"](config)

    def test_recommend_preserves_selected_settings_and_owner_constraints(self):
        config = {"executor": "CODEX", "variant": module.NAME,
                  "model_id": "gpt-6.1-sol", "reasoning_id": "xhigh",
                  "routing": {"mode": "shadow", "floor": "workhorse",
                              "denied_models": ["gpt-6-astra"], "allow_escalation": False}}
        self.assertEqual(self.recommend(config), config)

    def test_advisory_transformation_does_not_impose_read_only_on_any_worker_profile(self):
        # The normal configuration transform preserves a supplied configuration;
        # this does not prove every connector tool can express all these fields.
        for variant in ("DEFAULT", "NATIVE_APPROVE_FOR_ME", module.NAME):
            for permission in ("SUPERVISED", "AUTO", "PLAN"):
                with self.subTest(variant=variant, permission=permission):
                    config = {"executor": "CODEX", "variant": variant,
                              "model_id": "gpt-6.1-sol", "reasoning_id": "xhigh",
                              "permission_policy": permission,
                              "routing": {"mode": "shadow", "floor": "workhorse",
                                          "denied_models": ["gpt-6-astra"],
                                          "allow_escalation": False}}
                    self.assertEqual(self.recommend(config), config)

    def test_unknown_policy_is_rejected(self):
        with self.assertRaises(ValueError):
            self.recommend({"executor": "CODEX", "routing": {"unknown": True}})

    def database(self):
        db = sqlite3.connect(":memory:")
        self.addCleanup(db.close)
        db.executescript("""
CREATE TABLE issue_workflows(request_id,request_hash,operation,phase,chat_completed,workspace_id,issue_id,project_id,session_id,dot_user_id,link_revision,updated_at);
CREATE TABLE workspaces(id,task_id,archived,worktree_deleted);
CREATE TABLE tasks(id,project_id);
CREATE TABLE projects(id,archived,remote_project_id);
CREATE TABLE sessions(id,workspace_id);
CREATE TABLE local_issue_assignees(issue_id,user_id);
CREATE TABLE local_participants(id,username);
CREATE TABLE workspace_issue_link_revisions(workspace_id,revision);
CREATE TABLE execution_processes(id,session_id);
CREATE TABLE workspace_repos(workspace_id,repo_id);
CREATE TABLE project_repos(project_id,repo_id);
INSERT INTO issue_workflows VALUES('request','hash','start','reserved',1,'workspace','task','project','session','owner',0,NULL);
INSERT INTO workspaces VALUES('workspace','task',0,0);
INSERT INTO tasks VALUES('task','project');
INSERT INTO projects VALUES('project',0,NULL);
INSERT INTO sessions VALUES('session','workspace');
INSERT INTO local_issue_assignees VALUES('task','owner');
INSERT INTO local_participants VALUES('owner','dot');
INSERT INTO workspace_repos VALUES('workspace','repo');
INSERT INTO project_repos VALUES('project','repo');
""")
        return db

    def claim(self, db):
        sql = (SOURCE.parents[1] / "crates/db/src/models/issue_workflow_sql/claim_launch.sql").read_text()
        return db.execute(sql, ("request", "hash")).rowcount

    def test_actual_sql_claim_prevents_duplicate_or_uncertain_replay(self):
        db = self.database()
        self.assertEqual(self.claim(db), 1)
        self.assertEqual(self.claim(db), 0)
        self.assertEqual(db.execute("SELECT phase FROM issue_workflows").fetchone(), ("launching",))

    def test_actual_sql_requires_owner_repo_scope_and_unused_workspace(self):
        mutations = [
            "UPDATE issue_workflows SET chat_completed=0",
            "UPDATE issue_workflows SET request_hash='changed'",
            "DELETE FROM local_issue_assignees",
            "UPDATE local_participants SET username='other'",
            "UPDATE projects SET archived=1",
            "DELETE FROM project_repos",
            "INSERT INTO execution_processes VALUES('existing','session')",
            "INSERT INTO workspace_issue_link_revisions VALUES('workspace',1)",
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                db = self.database()
                db.execute(mutation)
                self.assertEqual(self.claim(db), 0)


if __name__ == "__main__":
    unittest.main()
