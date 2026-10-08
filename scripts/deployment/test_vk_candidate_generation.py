"""Retained small real-filesystem regressions; adapters simulate, never launch VK."""
import copy
from io import BytesIO
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from vk_candidate_generation import (
    Blocked, CandidateController, Layout, binding_environment, bind_reviewed_namespace, digest, inventory,
    open_regular, validate_manifest, verify_tree,
    namespace_runtime_identity,
)
from vk_candidate_scope import git_dependencies, query_paths
from vk_candidate_scope_plan import compile_plan, tool_dependencies


RETAINED = Path("/mnt/vk-storage/vk-safe-release-20261008/candidate-controller-tests")


class FixtureProvider:
    """In-memory authenticated fixture contract, NOT an authoritative B adapter."""
    def __init__(self, source):
        self.source = source
        self.captures = {}

    def capture(self, name, origin="incumbent", root=None):
        tree = root or self.source
        rows = inventory(tree)
        content = {}
        for path, row in rows.items():
            if row["kind"] == "file":
                with open_regular(tree, path) as stream:
                    content[path] = stream.read()
        self.captures[name] = ({"provider": "desktop-B", "capture_id": name,
            "scope_sha256": "a" * 64, "full_current_state": True, "entries": rows,
            "manifest_sha256": digest(rows), "origin_root_binding": origin}, content)

    def verify(self, capture):
        return copy.deepcopy(self.captures[capture][0])

    def open(self, capture, name):
        return BytesIO(self.captures[capture][1][name])


class FixtureSupervisor:
    """No process/systemd/network/route operations; exercise receipt boundaries."""
    def __init__(self, layout):
        self.layout = layout
        self.stopped, self.fenced = True, True
        self.capture, self.activations, self.fence_calls = "initial", [], 0
        self.receipt_mutator = lambda receipt: receipt
        self.fence_mutator = lambda count: None
        self.reserve = 1024 * 1024  # Synthetic fixture policy; not OP's production reserve.

    def verify_capacity(self, verified, layout, stage, payload_bytes):
        return {"policy_sha256": "d" * 64, "scope": "a" * 64, "source": "b" * 64,
                "capture_id": verified['capture_id'], "stage": stage,
                "payload_bytes": payload_bytes, "reserve_bytes": self.reserve}

    def verify_stopped(self, binding):
        if not self.stopped:
            raise Blocked("fixture writer still active")
        if binding is not None and binding != self.layout.binding():
            raise Blocked("fixture stopped writer bound to wrong roots")

    def verify_fence(self, capture):
        self.fence_calls += 1
        self.fence_mutator(self.fence_calls)
        if not self.fenced or capture["capture_id"] != self.capture:
            raise Blocked("fixture fresh writer fence missing")

    def acceptance(self, binding, source, scope, stage):
        checks = ("private_filesystem_pid_network_manager_boundary", "no_incumbent_write_access",
                  "binary_module_scanner_bound", "capacity_controller_ready",
                  "runtime_database_workspace_identity_bound",
                  "whole_state_capacity_restore_verified",
                  "recommend_and_usage_controls_preserved", "consent_accepted",
                  "current_report_receipts_preserved", "cleanup_unavailable", "fallback_latest_data_compatible")
        receipt = {"root_binding": binding, "source": source, "scope": scope, "stage": stage,
                   "capture_id": self.capture, "manifest_sha256": digest(inventory(self.layout.tree)),
                   "fallback_artifact_sha256": "c" * 64,
                   "checks": {key: True for key in checks}}
        return self.receipt_mutator(receipt)

    def activate_candidate(self, proof, receipt):
        self.activations.append(("candidate", proof["root_binding"]))
        self.stopped = False
        return {"root_binding": proof["root_binding"], "fixture_only": True}

    def activate_compatible_fallback(self, proof, receipt):
        self.activations.append(("compatible-fallback", proof["root_binding"]))
        self.stopped = False
        return {"root_binding": proof["root_binding"], "fixture_only": True}


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix=self._testMethodName + "-", dir=RETAINED))
        self.incumbent = self.root / "incumbent"
        self.incumbent.mkdir()
        (self.incumbent / "home").mkdir()
        (self.incumbent / "home" / "state").mkdir()
        self.database = self.incumbent / "home/state/state.sqlite"
        with sqlite3.connect(self.database) as db:
            db.execute("CREATE TABLE retained(value TEXT)")
            db.execute("INSERT INTO retained VALUES('before')")
        (self.incumbent / "home/state/note").write_bytes(b"original dirty work")
        os.chmod(self.incumbent / "home/state/note", 0o640)
        os.setxattr(self.incumbent / "home/state/note", "user.retained", b"metadata-proof")
        os.link(self.incumbent / "home/state/note", self.incumbent / "home/state/note-link")
        (self.incumbent / "home/worktrees").symlink_to("/home/state", target_is_directory=True)
        self.layout = Layout(self.root / "isolated", self.root / "isolated/tree",
                             self.root / "isolated/evidence", (self.incumbent,))
        self.provider = FixtureProvider(self.incumbent)
        self.provider.capture("initial")
        self.supervisor = FixtureSupervisor(self.layout)
        self.controller = CandidateController(self.layout, "a" * 64, "b" * 64, self.provider,
                                              self.supervisor, ("home/state/state.sqlite",), "c" * 64, "d" * 64)
        self.original = inventory(self.incumbent)

    def tearDown(self):
        # Retain every fixture and quarantine; no deletion or global cleanup.
        pass

    def restored(self):
        self.controller.restore("initial")

    def accepted_rehearsal(self):
        self.restored()
        self.controller.accept_rehearsal()

    def refreshed(self):
        self.accepted_rehearsal()
        self.provider.capture("final")
        self.supervisor.capture = "final"
        self.controller.catch_up("final")

    def test_restore_full_files_db_modes_links_xattrs_timestamps(self):
        proof = self.controller.restore("initial")
        self.assertEqual(inventory(self.layout.tree), self.original)
        self.assertEqual(inventory(self.incumbent), self.original)
        self.assertEqual(proof["root_binding"], self.layout.binding())
        a = (self.layout.tree / "home/state/note").stat()
        b = (self.layout.tree / "home/state/note-link").stat()
        self.assertEqual(a.st_ino, b.st_ino)
        self.assertEqual(a.st_nlink, 2)

    def test_namespace_absolute_link_binding_uses_candidate_backing(self):
        self.restored()
        proof = binding_environment(self.layout, {"WORKSPACES": "/home/worktrees"})
        self.assertEqual(proof["selectors"]["WORKSPACES"]["backing"], str(self.layout.tree / "home/state"))
        self.assertFalse(proof["host_launch_authorized"])

    def test_reviewed_namespace_command_retains_kernel_flags_and_binds_virtual_home(self):
        self.restored()
        argv = ["pinned-bwrap", "--ro-bind", "/", "/", "--bind", str(self.layout.tree), str(self.layout.tree),
                "--tmpfs", "/run", "--unshare-user", "--unshare-pid", "--unshare-net",
                "--new-session", "--die-with-parent", "--proc", "/proc", "--dev", "/dev", "--", "/usr/bin/true"]
        result = bind_reviewed_namespace(self.layout, argv, ["/home"], {"WORKSPACE": "/home/worktrees"})
        end = result["argv"].index("--")
        self.assertEqual(result["argv"][end - 3:end], ["--bind", str(self.layout.tree / "home"), "/home"])
        self.assertEqual(result["argv"][end + 1:], ["/usr/bin/true"])
        self.assertTrue(result["boundary_reacceptance_required"])
        self.assertFalse(result["operational_authorization"])
        for flag in ("--unshare-net", "--unshare-pid", "--unshare-user"):
            with self.assertRaises(Blocked):
                bind_reviewed_namespace(self.layout, [x for x in argv if x != flag], ["/home"], {})
        with self.assertRaises(Blocked):
            bind_reviewed_namespace(self.layout, argv, ["/"], {})
        with self.assertRaises(Blocked):
            bind_reviewed_namespace(self.layout, argv, ["/missing"], {"WORKSPACE": "/home/worktrees"})
        unsafe = argv[:argv.index("--")] + ["--bind", str(self.incumbent), str(self.incumbent)] + argv[argv.index("--"):]
        with self.assertRaisesRegex(Blocked, "writable host bind"):
            bind_reviewed_namespace(self.layout, unsafe, ["/home"], {})

    def test_namespace_cross_prefix_link_matches_actual_worktree_alias_pattern(self):
        self.restored()
        (self.layout.tree / "mnt/vk-storage/worktrees").mkdir(parents=True)
        (self.layout.tree / "home/cross-link").symlink_to('/mnt/vk-storage/worktrees')
        argv = ["pinned-bwrap", "--ro-bind", "/", "/", "--bind", str(self.layout.tree), str(self.layout.tree),
                "--tmpfs", "/run", "--unshare-user", "--unshare-pid", "--unshare-net",
                "--new-session", "--die-with-parent", "--proc", "/proc", "--dev", "/dev", "--", "/usr/bin/true"]
        result = bind_reviewed_namespace(self.layout, argv, ["/home", "/mnt/vk-storage"], {"WORKSPACE": "/home/cross-link"})
        self.assertEqual(result["bindings"]["selectors"]["WORKSPACE"]["resolved_virtual"], '/mnt/vk-storage/worktrees')
        with self.assertRaises(Blocked):
            bind_reviewed_namespace(self.layout, argv, ["/home"], {"WORKSPACE": "/home/cross-link"})

    def test_runtime_identity_missing_table_fails_without_enrollment(self):
        self.restored()
        before = inventory(self.layout.tree)
        with self.assertRaisesRegex(Blocked, "one-time enrollment"):
            namespace_runtime_identity(self.layout, '/home/state/state.sqlite', '/home/worktrees')
        self.assertEqual(inventory(self.layout.tree), before)

    def test_runtime_identity_rebinds_replaced_db_after_catch_up(self):
        # Explicit fixture identity exists before either capture, never auto-enrolled.
        with sqlite3.connect(self.database) as db:
            db.execute('CREATE TABLE vk_runtime_identity(singleton INTEGER PRIMARY KEY, dataset_id TEXT)')
            db.execute('INSERT INTO vk_runtime_identity VALUES(1, ?)', ['0123456789abcdef' * 2])
        self.provider.capture('initial')
        self.accepted_rehearsal()
        initial = namespace_runtime_identity(self.layout, '/home/state/state.sqlite', '/home/worktrees')
        with sqlite3.connect(self.database) as db:
            db.execute("INSERT INTO retained VALUES('new incumbent write')")
        self.provider.capture('final')
        self.supervisor.capture = 'final'
        self.controller.catch_up('final')
        final = namespace_runtime_identity(self.layout, '/home/state/state.sqlite', '/home/worktrees')
        self.assertNotEqual(initial['sha256'], final['sha256'])
        self.assertEqual(initial['root_binding'], final['root_binding'])
        self.assertIn('workspace_root=/home/state\n', final['text'])
        self.assertIn('dataset_id=' + '0123456789abcdef' * 2, final['text'])
        self.assertFalse(final['enrollment_performed'])

    def test_catch_up_preserves_new_incumbent_writes_and_quarantines_test_edits(self):
        self.restored()
        (self.layout.tree / "home/state/test-only").write_bytes(b"test artifact retained")
        (self.layout.tree / "home/state/note").write_bytes(b"test edits to both aliases")
        with sqlite3.connect(self.layout.tree / "home/state/state.sqlite") as db:
            db.execute("INSERT INTO retained VALUES('test edit')")
        self.controller.accept_rehearsal()
        with sqlite3.connect(self.database) as db:
            db.execute("INSERT INTO retained VALUES('incumbent since initial')")
        self.provider.capture("final")
        before = inventory(self.incumbent)
        self.supervisor.capture = "final"
        root_binding = self.layout.binding()
        self.controller.catch_up("final")
        self.assertEqual(self.layout.binding(), root_binding)
        self.assertEqual(inventory(self.layout.tree), before)
        self.assertEqual(inventory(self.incumbent), before)
        quarantines = list(self.layout.evidence.glob("*-test-and-prior-state"))
        self.assertEqual((quarantines[0] / "home/state/test-only").read_bytes(), b"test artifact retained")
        self.assertEqual((quarantines[0] / "home/state/note").read_bytes(), b"test edits to both aliases")
        with sqlite3.connect(quarantines[0] / "home/state/state.sqlite") as db:
            self.assertIn(("test edit",), db.execute("SELECT value FROM retained").fetchall())

    def test_promotion_and_post_write_fallback_use_same_latest_candidate(self):
        self.refreshed()
        binding = self.layout.binding()
        self.controller.promote()
        with sqlite3.connect(self.layout.tree / "home/state/state.sqlite") as db:
            db.execute("INSERT INTO retained VALUES('after promotion')")
        self.supervisor.stopped = True
        self.provider.capture("latest", origin=binding, root=self.layout.tree)
        self.supervisor.capture = "latest"
        self.controller.fallback("latest")
        self.assertEqual(self.supervisor.activations, [("candidate", binding), ("compatible-fallback", binding)])
        with sqlite3.connect(self.layout.tree / "home/state/state.sqlite") as db:
            self.assertIn(("after promotion",), db.execute("SELECT value FROM retained").fetchall())
        self.assertEqual(inventory(self.incumbent), self.original)

    def test_stale_incumbent_fallback_is_blocked(self):
        self.refreshed()
        self.controller.promote()
        self.supervisor.stopped = True
        self.provider.capture("old")
        self.supervisor.capture = "old"
        with self.assertRaisesRegex(Blocked, "stale incumbent"):
            self.controller.fallback("old")
        self.assertEqual(len(self.supervisor.activations), 1)

    def test_fallback_normalizes_latest_capture_and_retains_old_sidecars(self):
        self.refreshed()
        self.controller.promote()
        db_path = self.layout.tree / 'home/state/state.sqlite'
        with sqlite3.connect(db_path) as db:
            db.execute("INSERT INTO retained VALUES('after promotion normalization')")
        # Retained fixture represents a sidecar removed only from the provider's
        # normalized manifest. Controller must quarantine it, never unlink it.
        (self.layout.tree / 'home/state/state.sqlite-wal').write_bytes(b'retained fixture sidecar')
        self.supervisor.stopped = True
        self.provider.capture('latest-normalized', origin=self.layout.binding(), root=self.layout.tree)
        metadata, content = self.provider.captures['latest-normalized']
        del metadata['entries']['home/state/state.sqlite-wal']
        del content['home/state/state.sqlite-wal']
        metadata['manifest_sha256'] = digest(metadata['entries'])
        self.supervisor.capture = 'latest-normalized'
        self.controller.fallback('latest-normalized')
        preserved = list(self.layout.evidence.glob('*-test-and-prior-state/home/state/state.sqlite-wal'))
        self.assertEqual(preserved[0].read_bytes(), b'retained fixture sidecar')
        with sqlite3.connect(db_path) as db:
            self.assertIn(('after promotion normalization',), db.execute('SELECT value FROM retained').fetchall())

    def test_stale_initial_capture_cannot_promote(self):
        self.accepted_rehearsal()
        with self.assertRaisesRegex(Blocked, "stale initial"):
            self.controller.catch_up("initial")

    def test_writers_not_stopped_blocks_initial_and_refresh(self):
        self.supervisor.stopped = False
        with self.assertRaises(Blocked):
            self.controller.restore("initial")
        self.assertFalse(self.layout.tree.exists())
        self.supervisor.stopped = True
        self.accepted_rehearsal()
        self.supervisor.stopped = False
        with self.assertRaises(Blocked):
            self.controller.catch_up("initial")

    def test_fence_loss_after_refresh_blocks_promotion(self):
        self.refreshed()
        self.supervisor.fenced = False
        with self.assertRaises(Blocked):
            self.controller.promote()
        self.assertEqual(self.supervisor.activations, [])

    def test_fence_loss_at_last_activation_check_blocks_owner(self):
        self.refreshed()
        lose_at = self.supervisor.fence_calls + 3
        self.supervisor.fence_mutator = lambda count: setattr(self.supervisor, "fenced", count != lose_at)
        with self.assertRaises(Blocked):
            self.controller.promote()
        self.assertEqual(self.supervisor.activations, [])

    def test_wrong_receipt_fields_and_skipped_acceptance_block(self):
        self.refreshed()
        for field in ("source", "scope", "capture_id", "root_binding", "manifest_sha256", "stage", "fallback_artifact_sha256"):
            with self.subTest(field=field):
                self.supervisor.receipt_mutator = lambda r, field=field: {**r, field: "wrong"}
                with self.assertRaises(Blocked):
                    self.controller.promote()
        self.supervisor.receipt_mutator = lambda r: {**r, "checks": {}}
        with self.assertRaises(Blocked):
            self.controller.promote()
        self.assertEqual(self.supervisor.activations, [])

    def test_promotion_without_pinned_latest_data_fallback_is_blocked(self):
        self.refreshed()
        self.controller.fallback_artifact = None
        with self.assertRaisesRegex(Blocked, "fallback artifact"):
            self.controller.promote()
        self.assertEqual(self.supervisor.activations, [])

    def test_missing_or_insufficient_measured_capacity_blocks_before_restore(self):
        self.controller.capacity_policy = None
        with self.assertRaisesRegex(Blocked, "capacity policy"):
            self.controller.restore('initial')
        self.assertFalse(self.layout.tree.exists())
        self.controller.capacity_policy = 'd' * 64
        self.supervisor.reserve = 2 ** 64
        with self.assertRaisesRegex(Blocked, "reserve insufficient"):
            self.controller.restore('initial')
        self.assertFalse(self.layout.tree.exists())

    def test_provider_binding_missing_db_and_sidecars_fail_closed(self):
        base = self.provider.captures["initial"][0]
        for field, value in (("scope_sha256", "c" * 64), ("capture_id", "wrong"),
                             ("full_current_state", False), ("provider", "local"),
                             ("manifest_sha256", "wrong")):
            with self.subTest(field=field):
                self.provider.captures["initial"] = ({**base, field: value}, {})
                with self.assertRaises(Blocked):
                    self.controller.restore("initial")
        missing = copy.deepcopy(base)
        del missing["entries"]["home/state/state.sqlite"]
        missing["manifest_sha256"] = digest(missing["entries"])
        self.provider.captures["initial"] = (missing, {})
        with self.assertRaisesRegex(Blocked, "database omitted"):
            self.controller.restore("initial")
        sidecar = copy.deepcopy(base)
        sidecar["entries"]["home/state/state.sqlite-wal"] = sidecar["entries"]["home/state/state.sqlite"]
        sidecar["manifest_sha256"] = digest(sidecar["entries"])
        self.provider.captures["initial"] = (sidecar, {})
        with self.assertRaisesRegex(Blocked, "sidecars"):
            self.controller.restore("initial")

    def test_member_hash_mismatch_cannot_claim_restore(self):
        self.provider.captures["initial"][1]["home/state/note"] = b"bad bytes"
        with self.assertRaisesRegex(Blocked, "bytes mismatch"):
            self.controller.restore("initial")
        self.assertEqual(self.controller.phase, "restoring")
        with self.assertRaises(Blocked):
            self.controller.promote()
        self.assertEqual(inventory(self.incumbent), self.original)

    def test_non_sqlite_bytes_even_with_authentic_hash_block_restore(self):
        (self.incumbent / "home/state/state.sqlite").write_bytes(b"authentic non-SQLite bytes")
        self.provider.capture("invalid-db")
        with self.assertRaisesRegex(Blocked, "invalid SQLite"):
            self.controller.restore("invalid-db")
        self.assertNotEqual(self.controller.phase, "restored")

    def test_refresh_member_failure_leaves_quarantine_and_blocks_owner(self):
        self.accepted_rehearsal()
        (self.incumbent / "home/state/note").write_bytes(b"new retained bytes")
        self.provider.capture("final")
        self.provider.captures["final"][1]["home/state/note"] = b"bad stream"
        self.supervisor.capture = "final"
        before = inventory(self.incumbent)
        with self.assertRaises(Blocked):
            self.controller.catch_up("final")
        self.assertEqual(self.controller.phase, "refreshing")
        self.assertTrue(list(self.layout.evidence.glob("*-test-and-prior-state/home/state/note")))
        with self.assertRaises(Blocked):
            self.controller.promote()
        self.assertEqual(inventory(self.incumbent), before)

    def test_missing_extended_metadata_and_privileged_modes_block(self):
        for edit in (lambda r: r.pop("xattrs"), lambda r: r.update(mode=0o4755),
                     lambda r: r.update(xattrs={"security.selinux": "YQ=="})):
            rows = copy.deepcopy(self.original)
            edit(rows["home/state/note"])
            with self.assertRaises(Blocked):
                validate_manifest(rows)

    def test_symlink_escape_cycle_and_host_alias_rejected(self):
        for target in ("../../outside", "/outside", "/home/worktrees"):
            rows = copy.deepcopy(self.original)
            rows["home/worktrees"]["target"] = target
            with self.assertRaises(Blocked):
                validate_manifest(rows)
        alias = self.root / "host-alias"
        alias.symlink_to(self.incumbent, target_is_directory=True)
        with self.assertRaises(Blocked):
            Layout(alias / "task", alias / "task/tree", alias / "task/evidence", (self.incumbent,)).validate()

    def test_external_hardlink_to_incumbent_blocks_inventory(self):
        self.restored()
        os.link(self.incumbent / "home/state/note", self.layout.tree / "external")
        with self.assertRaisesRegex(Blocked, "hardlink escapes"):
            inventory(self.layout.tree)

    def test_changed_directory_metadata_preserves_subtree_without_delete(self):
        self.accepted_rehearsal()
        os.chmod(self.incumbent / "home/state", 0o750)  # Fixture only.
        self.provider.capture("final")
        self.supervisor.capture = "final"
        self.controller.catch_up("final")
        self.assertEqual(inventory(self.layout.tree), inventory(self.incumbent))
        self.assertTrue(list(self.layout.evidence.glob("*-test-and-prior-state/home/state/note")))

    def test_crash_restart_with_retained_journal_cannot_forge_new_owner(self):
        self.restored()
        with self.assertRaisesRegex(Blocked, "journal needs explicit recovery"):
            CandidateController(self.layout, "a" * 64, "b" * 64, self.provider, self.supervisor,
                                ("home/state/state.sqlite",))

    def test_cleanup_unavailable_at_all_phases(self):
        for action in (lambda: None, self.restored, self.controller.accept_rehearsal):
            action()
            with self.assertRaisesRegex(Blocked, "human QA"):
                self.controller.cleanup()

    def test_scope_queries_read_only_and_git_alternates_are_accounted(self):
        rows = query_paths(self.database, {"allowed": "SELECT value FROM retained"})
        self.assertEqual(rows["allowed"], [("before",)])
        with self.assertRaises(sqlite3.OperationalError):
            query_paths(self.database, {"denied": "DELETE FROM retained"})
        repo = self.root / "repo"
        (repo / ".git/objects/info").mkdir(parents=True)
        alternate = self.root / "alternate-objects"
        alternate.mkdir()
        (repo / ".git/objects/info/alternates").write_text(str(alternate) + "\n")
        self.assertIn((str(alternate), "git-object-store"), git_dependencies(repo))
        self.assertEqual(inventory(self.incumbent), self.original)

    def test_scope_plan_keeps_unavailable_rows_and_B_only_sources_explicit(self):
        row = {"path": str(self.incumbent), "resolved": str(self.incumbent), "exists": True,
               "reasons": ["registered-repository"]}
        receipt = {"dependencies": [row, {**row, "path": '/home/mcp', "resolved": '/home/mcp'},
                                    {**row, "path": '/unavailable-original', "exists": False}],
                   "baseline_accounting": [{"path": str(self.incumbent)}, {"path": '/preserved-historical-only'}]}
        plan = compile_plan(receipt, {"path_dependencies": [], "servers": []})
        self.assertIn('/home/mcp', plan['namespace_context_only'])
        self.assertEqual(len(plan['unavailable_reference_exceptions']), 1)
        self.assertEqual(plan['baseline_accounting'][1]['candidate'], 'B-only-operational-proposal')
        self.assertFalse(plan['baseline_accounting'][1]['historical_retirement_proven'])
        self.assertFalse(plan['restore_or_operational_scope_approved'])

    def test_tool_dependency_receipt_excludes_tokens_headers_and_full_urls(self):
        home = self.root / 'fixture-native-config'
        home.mkdir()
        (home / 'config.toml').write_text('''[mcp_servers.local]
command = "/usr/bin/python3"
args = ["--private", "SYNTHETIC-CREDENTIAL-CANARY"]
[mcp_servers.remote]
url = "https://example.invalid/mcp?token=SYNTHETIC-CREDENTIAL-CANARY"
http_headers = {Authorization = "SYNTHETIC-CREDENTIAL-CANARY"}
''')
        result = tool_dependencies(home, '/usr/bin')
        encoded = json.dumps(result)
        self.assertNotIn('SYNTHETIC-CREDENTIAL-CANARY', encoded)
        self.assertNotIn('example.invalid', encoded)
        self.assertEqual(len(result['servers']), 2)
        self.assertTrue(all(r['external_writer_boundary_required'] for r in result['servers']))


if __name__ == "__main__":
    if not os.path.ismount("/mnt/vk-storage"):
        raise SystemExit("mounted secondary SSD required")
    RETAINED.mkdir(exist_ok=True)
    unittest.main(verbosity=2)
