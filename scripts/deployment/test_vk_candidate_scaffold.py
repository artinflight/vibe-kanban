import copy
import os
import unittest
from unittest.mock import patch

from vk_candidate_generation import Blocked, digest, validate_manifest
from vk_candidate_scaffold import authenticate_plan, add_context


class ScaffoldTests(unittest.TestCase):
    def setUp(self):
        self.plan = {"sources": ["/home/mcp/state"], "sqlite_snapshots": [],
                     "excluded_rebuildable_directories": []}
        self.scope = {"sources": self.plan["sources"], "excluded_rebuildable_directories": []}
        self.row = {"kind": "directory", "mode": 0o555, "uid": os.getuid(),
                    "gid": os.getgid(), "mtime_ns": 123, "xattrs": {}}

    def test_only_context_is_generated_source_metadata_is_preserved(self):
        rows = {"home/mcp/state": copy.deepcopy(self.row)}
        proof = add_context(rows, self.plan, "/")
        self.assertEqual(proof["generated_context_names"], ["home", "home/mcp"])
        self.assertEqual(rows["home/mcp/state"], self.row)
        self.assertFalse(proof["original_context_metadata_verified"])
        self.assertEqual(proof["source_entries_reconstructed"], 0)
        validate_manifest(rows)

    def test_missing_directory_inside_source_never_reconstructed(self):
        rows = {"home/mcp/state/inside/deep": copy.deepcopy(self.row)}
        before = copy.deepcopy(rows)
        with self.assertRaisesRegex(Blocked, "missing source"):
            add_context(rows, self.plan, "/")
        self.assertEqual(rows, before)

    def test_unrelated_archived_parent_is_not_scaffold_authority(self):
        with self.assertRaisesRegex(Blocked, "declared source ancestor"):
            add_context({"other/tree": self.row}, self.plan, "/")

    def test_existing_non_directory_parent_is_not_replaced(self):
        rows = {"home": {**self.row, "kind": "symlink", "target": "/home/mcp/state"},
                "home/mcp/state": copy.deepcopy(self.row)}
        add_context(rows, self.plan, "/")
        self.assertEqual(rows["home"]["kind"], "symlink")
        with self.assertRaisesRegex(Blocked, "parent"):
            validate_manifest(rows)

    def test_plan_and_scope_are_independently_bound_and_immutable(self):
        accepted = authenticate_plan(self.plan, digest(self.plan), digest(self.scope))
        self.plan["sources"].append("/other")
        self.assertEqual(accepted["sources"], ["/home/mcp/state"])
        with self.assertRaisesRegex(Blocked, "plan digest"):
            authenticate_plan(self.plan, digest(accepted), digest(self.scope))
        with self.assertRaisesRegex(Blocked, "scope digest"):
            authenticate_plan(accepted, digest(accepted), "0" * 64)

    def test_noncanonical_roots_and_different_prefix_fail_closed(self):
        for raw in ("relative", "/home/../state", "/home//mcp/state"):
            plan = {**self.plan, "sources": [raw]}
            with self.assertRaisesRegex(Blocked, "canonical"):
                authenticate_plan(plan, digest(plan), digest(self.scope))
        with self.assertRaisesRegex(Blocked, "outside pinned prefix"):
            add_context({"state": self.row}, self.plan, "/other")

    def test_actual_sparse_capture_requires_authenticated_context_policy(self):
        from test_vk_candidate_direct_b import ContractTests
        from vk_candidate_direct_b import DirectBProvider
        from vk_change_journal import Journal, scope
        import vk_direct_capture
        import vk_rolling_backup

        fixture = ContractTests()
        fixture.setUp()
        try:
            plan = {"sources": [str(fixture.inc / "home/state")],
                    "sqlite_snapshots": [str(fixture.db)], "excluded_rebuildable_directories": []}
            journal = Journal(plan)
            journal.tree(fixture.inc / "home/state")
            journal.ready = True
            fixture.journals.append(journal)
            with patch.object(vk_direct_capture, "Archive", fixture.factory), \
                    patch.object(vk_rolling_backup, "Archive", fixture.factory):
                result = vk_direct_capture.capture(plan, fixture.root / "sparse-capture", journal.report,
                        fixture.mirror, None, fixture.mirror, max_snapshot_bytes=64*1024)
            provider = DirectBProvider(fixture.scope, ["home/state/state.sqlite"],
                                       archive_factory=fixture.factory, fixture_only=True)
            kwargs = dict(origin_root_binding="incumbent")
            provider.register("no-context", result, digest(plan), digest(scope(plan)), fixture.inc, **kwargs)
            with self.assertRaisesRegex(Blocked, "parent"):
                provider.verify("no-context")
            provider.register("bound-context", result, digest(plan), digest(scope(plan)), fixture.inc,
                              namespace_plan=plan, **kwargs)
            proof = provider.verify("bound-context")
            self.assertEqual(proof["namespace_scaffold"]["generated_context_names"], ["home"])
            self.assertEqual(proof["namespace_scaffold"]["source_entries_reconstructed"], 0)
            self.assertTrue(proof["fixture_only"])
            self.assertIn("home/state/state.sqlite", proof["entries"])
        finally:
            fixture.tearDown()


if __name__ == "__main__":
    unittest.main()
