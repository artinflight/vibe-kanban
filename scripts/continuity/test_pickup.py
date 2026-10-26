"""Lossless continuity and concise pickup checks; no model or production calls."""

import copy
import json
from pathlib import Path
import re
import tempfile
import unittest

from pickup import ROOT, find, manifest, verify


class PickupTests(unittest.TestCase):
    def test_all_original_bytes_preserved(self):
        self.assertEqual(verify()["historical_bytes_preserved"], 1032169)
        self.assertLessEqual(verify()["mandatory_bytes"], 16384)

    def test_original_sha_pins(self):
        self.assertEqual([r["sha256"] for r in manifest()["archives"]], [
            "5d2a96b467069f26648ff826f3ad3ee8ad5cd468ac6f98e1a4b6d4abaa542959",
            "98cfdd009da2892714abc42420d6da7829fab679e04e4fc65597ed90919d075c",
            "3c659ced2310fefe31e79bde266299a819496689f8c6f6c7d355c5a54e62e42d"])

    def test_current_index_local_links_resolve(self):
        for row in manifest()["archives"]:
            for target in re.findall(r"\]\(([^)]+)\)", (ROOT / row["original"]).read_text()):
                if "://" not in target:
                    self.assertTrue((ROOT / target.split("#")[0]).is_file(), target)

    def test_duplicate_headings_remain_individually_locatable(self):
        matches = find("publication-admission recurrence")
        self.assertGreaterEqual(len(matches), 2)
        self.assertEqual(len(matches), len({(r["archive"], r["line"]) for r in matches}))

    def test_no_silent_archive_or_budget_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = copy.deepcopy(manifest())
            for row in data["archives"]:
                (root / row["archive"]).write_bytes((ROOT / row["archive"]).read_bytes())
                (root / row["original"]).write_text(row["archive"])
            path = root / "CONTINUITY_ARCHIVE.json"
            path.write_text(json.dumps(data))
            self.assertTrue(verify(root)["passed"])
            archive = root / data["archives"][0]["archive"]
            raw = archive.read_bytes()
            archive.write_bytes(raw + b"changed decision")
            with self.assertRaisesRegex(ValueError, "evidence changed"):
                verify(root)
            archive.write_bytes(raw)
            (root / "STATE.md").write_text(data["archives"][0]["archive"] + "x" * 16384)
            with self.assertRaisesRegex(ValueError, "16 KiB"):
                verify(root)


if __name__ == "__main__":
    unittest.main()
