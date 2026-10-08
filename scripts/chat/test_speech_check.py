import json
from pathlib import Path
import unittest

from check_speech import evaluate, structural_issues


class SpeechCheckTests(unittest.TestCase):
    def test_natural_prose_and_meaningful_quantities_are_allowed(self):
        for text in ["The Android agent matched onboarding to web. Nothing needs your attention.",
                     "There are two decisions waiting for you.",
                     "The retry delay is now 30 seconds because the service asked us to slow down."]:
            self.assertEqual(structural_issues(text), [])

    def test_visual_material_is_not_spoken(self):
        for text in ["1. Updated onboarding\n2. Ran tests", "- Mobile is blocked", "`cargo test`",
                     '{"status": "completed"}', "Validation:: 42 tests passed",
                     "Read https://example.com/report", "Changed crates/db/schema.rs",
                     "Commit 49de8f72aa123abc", "| Agent | State |\n| mobile | done |"]:
            self.assertTrue(structural_issues(text), text)

    def test_corpus_has_distinct_cases_and_evidence(self):
        corpus = json.loads(Path(__file__).with_name("speech_cases.json").read_text())
        cases = corpus["cases"]
        self.assertGreaterEqual(len(cases),10)
        self.assertEqual(len(cases),len({case["id"] for case in cases}))
        for case in cases:
            self.assertTrue(case["user_request"])
            self.assertTrue(case["review_criteria"])
            self.assertTrue(case["reports"])

    def test_structure_success_does_not_claim_semantic_acceptance(self):
        cases = [{"id":"case","reports":[{"id":"source"}]}]
        outputs = [{"case_id":"case","model":"configured-model","prompt_version":"revision",
                    "spoken_text":"The agent needs your decision.","evidence_ids":["source"]}]
        report = evaluate(cases,outputs)
        self.assertTrue(report["structural_pass"])
        self.assertIn("unverified",report["acceptance"])
        outputs[0]["evidence_ids"] = ["invented"]
        self.assertFalse(evaluate(cases,outputs)["structural_pass"])

    def test_missing_duplicate_and_unattributed_outputs_fail(self):
        cases = [{"id":"one","reports":[]},{"id":"two","reports":[]}]
        outputs = [{"case_id":"one","spoken_text":"It is done."}]*2
        report = evaluate(cases,outputs)
        self.assertFalse(report["structural_pass"])
        self.assertEqual(report["missing_cases"],["two"])
        self.assertIn("duplicate case",report["cases"][1]["structural_issues"])


if __name__ == "__main__":
    unittest.main()
