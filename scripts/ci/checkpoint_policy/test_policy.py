"""Offline negative/positive acceptance; no hosted tests, Git writes or API calls."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

import audit_protection
import render
import verify_result

HERE = Path(__file__).resolve().parent
POLICY = json.loads((HERE / "policy.json").read_text())


class FinalGate(unittest.TestCase):
    def setUp(self):
        pr = {"state": "open", "draft": False,
              "head": {"sha": "a" * 40},
              "base": {"ref": "staging", "sha": "b" * 40,
                       "repo": {"full_name": POLICY["repository"]}},
              "merge_commit_sha": "c" * 40}
        self.args = [
            {"number": 1, "pull_request": deepcopy(pr)}, pr,
            {"commit": {"sha": "b" * 40}},
            {"sha": "c" * 40, "parents": [{"sha": "b" * 40}, {"sha": "a" * 40}]},
            {"test": {"result": "success"}}, ["test"], "c" * 40, POLICY["repository"],
        ]

    def test_real_current_merge_passes(self):
        receipt = verify_result.verify(*self.args)
        self.assertEqual(receipt["base"], "b" * 40)
        self.assertEqual(receipt["tested_merge"], "c" * 40)

    def test_draft_at_start_or_end_fails(self):
        for index in (0, 1):
            with self.subTest(index=index):
                args = deepcopy(self.args)
                (args[0]["pull_request"] if index == 0 else args[1])["draft"] = True
                with self.assertRaises(ValueError):
                    verify_result.verify(*args)

    def test_head_or_base_change_invalidates_green(self):
        for section in ("head", "base"):
            args = deepcopy(self.args)
            args[1][section]["sha"] = "d" * 40
            with self.subTest(section=section), self.assertRaises(ValueError):
                verify_result.verify(*args)
        self.args[2]["commit"]["sha"] = "d" * 40
        with self.assertRaises(ValueError):
            verify_result.verify(*self.args)

    def test_stale_merge_or_wrong_parent_order_fails(self):
        for index in (0, 1):
            args = deepcopy(self.args)
            args[3]["parents"][index]["sha"] = "e" * 40
            with self.subTest(index=index), self.assertRaises(ValueError):
                verify_result.verify(*args)
        self.args[1]["merge_commit_sha"] = "e" * 40
        with self.assertRaises(ValueError):
            verify_result.verify(*self.args)

    def test_skipped_missing_cancelled_neutral_fail(self):
        for result in ("skipped", "cancelled", "failure", "neutral", "timed_out", "pending", None):
            args = deepcopy(self.args)
            args[4]["test"]["result"] = result
            with self.subTest(result=result), self.assertRaises(ValueError):
                verify_result.verify(*args)
        for value in ({}, {"other": {"result": "success"}}):
            self.args[4] = value
            with self.assertRaises(ValueError):
                verify_result.verify(*self.args)

    def test_retarget_closed_other_repository_fail(self):
        for key, value in (("state", "closed"), ("draft", None)):
            args = deepcopy(self.args)
            args[1][key] = value
            with self.assertRaises(ValueError):
                verify_result.verify(*args)
        self.args[1]["base"]["ref"] = "main"
        with self.assertRaises(ValueError):
            verify_result.verify(*self.args)
        self.args[7] = "another/repository"
        with self.assertRaises(ValueError):
            verify_result.verify(*self.args)


class WorkflowContract(unittest.TestCase):
    def test_all_seven_workflows_keep_commands_and_fail_closed(self):
        self.assertEqual(len(POLICY["workflows"]), 7)
        for name, spec in POLICY["workflows"].items():
            with self.subTest(workflow=name):
                path = HERE / "baseline" / name
                raw = path.read_text()
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), spec["source_sha256"])
                old = yaml.load(raw, Loader=yaml.BaseLoader)
                candidate = yaml.load(render.candidate(name, spec), Loader=yaml.BaseLoader)
                self.assertEqual(set(candidate["on"]), set(old["on"]))
                self.assertEqual(candidate["on"]["workflow_dispatch"], old["on"]["workflow_dispatch"])
                trigger = candidate["on"]["pull_request"]
                self.assertEqual(trigger["branches"], ["staging", "main"])
                self.assertNotIn("paths", trigger)
                self.assertNotIn("paths-ignore", trigger)
                for event in ("synchronize", "ready_for_review", "converted_to_draft", "edited"):
                    self.assertIn(event, trigger["types"])
                if "push" in old["on"]:
                    self.assertEqual(old["on"]["push"], candidate["on"]["push"])
                for job in spec["required_jobs"]:
                    self.assertIn(render.READY, candidate["jobs"][job]["if"])
                    before = old["jobs"][job]["steps"]
                    after = candidate["jobs"][job]["steps"]
                    self.assertEqual(len(before) + (job == "ops-governance"), len(after))
                    for a, b in zip(before, after):
                        if job == "branch-policy" and "run" in a:
                            self.assertEqual(b["env"]["VK_CI_HEAD_BRANCH"], "${{ github.head_ref }}")
                            self.assertIn('"$VK_CI_HEAD_BRANCH"', b["run"])
                            self.assertNotIn("${{", b["run"])
                        elif "run" in a and "::notice::VK_PRIVATE_DEPLOY_KEY" not in a["run"]:
                            self.assertEqual(a["run"], b["run"])
                gate = candidate["jobs"]["checkpoint-result"]
                self.assertEqual(gate["if"], "always()")
                self.assertEqual(gate["needs"], spec["required_jobs"])
                self.assertIn("Non-PR /", gate["name"])
                self.assertEqual(candidate["permissions"], {"contents": "read", "pull-requests": "read"})

    def test_missing_remote_credentials_cannot_pass(self):
        spec = POLICY["workflows"]["test.yml"]
        doc = yaml.load(render.candidate("test.yml", spec), Loader=yaml.BaseLoader)
        job = doc["jobs"]["backend-remote-checks"]
        require = next(s for s in job["steps"] if s.get("name") == "Require private dependency access")
        self.assertIn("exit 1", require["run"])
        for value in doc["jobs"]["changes"]["outputs"].values():
            self.assertIn("github.event_name == 'pull_request' && 'true'", value)

    def test_renderer_cannot_install_workflows(self):
        proc = subprocess.run([sys.executable, str(HERE / "render.py"), "--output", str(render.ROOT / ".github/workflows")], capture_output=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn(b"installation needs separate owner authorization", proc.stderr)

    def test_cli_renders_complete_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run([sys.executable, str(HERE / "render.py"), "--output", tmp], check=True, capture_output=True)
            self.assertEqual({p.name for p in Path(tmp).glob("*.yml")}, set(POLICY["workflows"]))

    def test_installed_candidate_tests_pass_and_workflow_drift_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflows = root / ".github/workflows"
            workflows.mkdir(parents=True)
            for name, spec in POLICY["workflows"].items():
                (workflows / name).write_text(render.candidate(name, spec))
            with patch.object(render, "ROOT", root):
                for name, spec in POLICY["workflows"].items():
                    self.assertEqual(render.candidate(name, spec), (workflows / name).read_text())
                (workflows / "test.yml").write_text("name: changed after review\n")
                with self.assertRaisesRegex(ValueError, "re-review"):
                    render.candidate("test.yml", POLICY["workflows"]["test.yml"])


class ProtectionContract(unittest.TestCase):
    def setUp(self):
        self.expected = json.loads((HERE / "proposed-branch-protection.json").read_text())
        self.live = deepcopy(self.expected)
        for key in ("enforce_admins", "allow_force_pushes", "allow_deletions", "required_conversation_resolution"):
            self.live[key] = {"enabled": self.live[key]}
        self.permissions = json.loads((HERE / "proposed-actions-permissions.json").read_text())

    def test_exact_proposal_passes(self):
        self.assertEqual(audit_protection.validate(self.live, self.permissions, self.expected), [])
        self.assertEqual(len(self.expected["required_status_checks"]["checks"]), 7)

    def test_no_protection_loose_base_wrong_app_or_context_fail(self):
        self.assertTrue(audit_protection.validate({}, self.permissions, self.expected))
        for mutation in ("loose", "wrong_app", "missing"):
            live = deepcopy(self.live)
            checks = live["required_status_checks"]
            if mutation == "loose":
                checks["strict"] = False
            elif mutation == "wrong_app":
                checks["checks"][0]["app_id"] = 1
            else:
                checks["checks"].pop()
            self.assertTrue(audit_protection.validate(live, self.permissions, self.expected))

    def test_admin_review_bypass_or_write_token_fail(self):
        for key in ("enforce_admins", "required_conversation_resolution"):
            live = deepcopy(self.live)
            live[key]["enabled"] = False
            self.assertTrue(audit_protection.validate(live, self.permissions, self.expected))
        live = deepcopy(self.live)
        live["required_pull_request_reviews"]["bypass_pull_request_allowances"]["users"] = [{"login": "someone"}]
        self.assertTrue(audit_protection.validate(live, self.permissions, self.expected))
        for key in ("default_workflow_permissions", "can_approve_pull_request_reviews"):
            permissions = deepcopy(self.permissions)
            permissions[key] = "write" if key.startswith("default") else True
            self.assertTrue(audit_protection.validate(self.live, permissions, self.expected))


if __name__ == "__main__":
    unittest.main()
