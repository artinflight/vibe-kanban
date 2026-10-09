"""Retained small real-filesystem regressions; adapters simulate, never launch VK."""
import copy
import hashlib
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
    namespace_runtime_identity, recorded_link_exceptions,
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
            "scope_sha256": "a" * 64, "full_current_state": True, "fixture_only": True, "entries": rows,
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
                  "operational_dependency_closure_verified",
                  "whole_state_capacity_restore_verified",
                  "full_required_linux_metadata_verified",
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
    def test_hardlink_primary_uses_full_path_order_not_directory_traversal(self):
        for name in ('z', 'z-'):
            (self.incumbent / name).mkdir()
        first_visited = self.incumbent / 'z/file'
        first_visited.write_bytes(b'preserved linked content')
        os.link(first_visited, self.incumbent / 'z-/file')
        rows = inventory(self.incumbent)
        self.assertEqual(rows['z-/file']['kind'], 'file')
        self.assertEqual(rows['z/file']['kind'], 'hardlink')
        self.assertEqual(rows['z/file']['target'], 'z-/file')
        self.provider.capture('initial')
        self.restored()
        a, b = (self.layout.tree / n for n in ('z/file', 'z-/file'))
        self.assertEqual(a.stat().st_ino, b.stat().st_ino)
        self.assertEqual(inventory(self.layout.tree), rows)

    def suffix_binary(self):
        header = bytearray(64)
        header[:7] = b'\x7fELF\x02\x01\x01'
        header[16:24] = b'\x03\x00\x3e\x00\x01\x00\x00\x00'
        header[52:54] = (64).to_bytes(2, 'little')
        p = self.incumbent / 'home/state/server-wal'
        p.write_bytes(header + b'fixture executable contents')
        p.chmod(0o755)
        return p

    def test_suffix_named_elf_is_authenticated_and_preserved(self):
        p = self.suffix_binary()
        self.provider.capture('initial')
        self.restored()
        self.assertEqual((self.layout.tree / 'home/state/server-wal').read_bytes(), p.read_bytes())

    def test_suffix_named_elf_with_database_base_still_blocks(self):
        self.suffix_binary()
        (self.incumbent / 'home/state/server').write_bytes(self.database.read_bytes())
        self.provider.capture('initial')
        with self.assertRaisesRegex(Blocked, 'sidecars'):
            self.restored()
        self.assertFalse(self.layout.tree.exists())

    def test_orphan_wal_and_text_are_not_exempted_by_executable_mode(self):
        p = self.suffix_binary()
        for content in (b'\x37\x7f\x06\x82' + bytes(100), b'ordinary file, format unknown'):
            p.write_bytes(content)
            self.provider.capture('initial')
            with self.assertRaisesRegex(Blocked, 'not ELF'):
                self.restored()
            self.assertFalse(self.layout.tree.exists())

    def test_suffix_named_elf_tampering_and_link_fail_closed(self):
        p = self.suffix_binary()
        self.provider.capture('initial')
        self.provider.captures['initial'][1]['home/state/server-wal'] += b'changed'
        with self.assertRaisesRegex(Blocked, 'authenticated size'):
            self.restored()
        os.link(p, self.incumbent / 'home/state/server-shm')
        self.provider.capture('initial')
        with self.assertRaisesRegex(Blocked, 'sidecars'):
            self.restored()
        self.assertFalse(self.layout.tree.exists())

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

    def recover_initial(self, prior_source="b" * 64):
        return CandidateController.recover_initial_restore(self.layout, "a" * 64, "b" * 64,
            self.provider, self.supervisor, ("home/state/state.sqlite",),
            prior_source_sha256=prior_source, fallback_artifact_sha256="c" * 64,
            capacity_policy_sha256="d" * 64)

    def materialized_without_journal(self):
        verified = self.controller.authenticated('initial')
        self.controller.capacity(verified, 'initial-restore', 0)
        self.layout.tree.mkdir(parents=True)
        self.controller.materialize(verified, set(verified['entries']))

    def test_full_materialization_reverified_without_restoring_or_accepting(self):
        self.materialized_without_journal()
        inode = (self.layout.tree / 'home/state/note').stat().st_ino
        proof = self.controller.verify_initial_materialization('initial')
        self.assertEqual(self.controller.phase, 'restored')
        self.assertEqual(inventory(self.layout.tree), self.original)
        self.assertEqual((self.layout.tree / 'home/state/note').stat().st_ino, inode)
        journal = json.loads((self.layout.evidence / '0001-initial-materialization-verified.json').read_text())
        self.assertEqual(proof['root_binding'], self.layout.binding())
        self.assertFalse(journal['restored_again'])
        self.assertFalse(journal['prior_attempt_reconstructed'])
        self.assertFalse(journal['activation_authorized'])
        with self.assertRaisesRegex(Blocked, 'final fenced'):
            self.controller.promote()

    def test_materialization_verification_rejects_partial_or_changed_bytes(self):
        self.layout.tree.mkdir(parents=True)
        with self.assertRaisesRegex(Blocked, 'inventory differs'):
            self.controller.verify_initial_materialization('initial')
        self.assertFalse(self.layout.evidence.exists())
        # Fill only this originally empty fixture using its authenticated bytes.
        verified = self.controller.authenticated('initial')
        self.controller.materialize(verified, set(verified['entries']))
        (self.layout.tree / 'home/state/note').write_bytes(b'changed')
        with self.assertRaisesRegex(Blocked, 'inventory differs'):
            self.controller.verify_initial_materialization('initial')
        self.assertFalse(self.layout.evidence.exists())

    def test_materialization_verification_rejects_live_writer_and_prior_journal(self):
        self.materialized_without_journal()
        self.supervisor.stopped = False
        with self.assertRaisesRegex(Blocked, 'writer still active'):
            self.controller.verify_initial_materialization('initial')
        self.supervisor.stopped = True
        self.layout.evidence.mkdir()
        (self.layout.evidence / '0001-interrupted.json').write_text('{}')
        with self.assertRaisesRegex(Blocked, 'retained journal'):
            self.controller.verify_initial_materialization('initial')

    def test_materialization_verification_rejects_bad_b_binding(self):
        self.materialized_without_journal()
        self.provider.captures['initial'][0]['manifest_sha256'] = 'e' * 64
        with self.assertRaisesRegex(Blocked, 'manifest binding'):
            self.controller.verify_initial_materialization('initial')
        self.assertFalse(self.layout.evidence.exists())

    def test_recover_initial_restore_reverifies_same_tree_without_acceptance(self):
        self.restored()
        before = (self.layout.evidence / '0001-restored.json').read_bytes()
        restored = self.recover_initial()
        self.assertEqual(restored.phase, 'restored')
        self.assertEqual(restored.sequence, 2)
        self.assertIsNone(restored.test_receipt)
        self.assertEqual((self.layout.evidence / '0001-restored.json').read_bytes(), before)
        self.assertEqual(inventory(self.layout.tree), self.original)
        with self.assertRaisesRegex(Blocked, 'final fenced'):
            restored.promote()

    def test_recover_completed_materialization_preserves_truthful_journal(self):
        self.materialized_without_journal()
        self.controller.verify_initial_materialization('initial')
        journal = self.layout.evidence / '0001-initial-materialization-verified.json'
        before = journal.read_bytes()
        recovered = self.recover_initial()
        self.assertEqual(recovered.phase, 'restored')
        self.assertEqual(journal.read_bytes(), before)
        new = json.loads((self.layout.evidence / '0002-initial-owner-recovered.json').read_text())
        self.assertEqual(new['prior_journal'], journal.name)
        self.assertFalse(new['activation_authorized'])

    def test_recover_materialization_rejects_unsupported_acceptance_and_scope(self):
        self.materialized_without_journal()
        self.controller.verify_initial_materialization('initial')
        journal = self.layout.evidence / '0001-initial-materialization-verified.json'
        before = json.loads(journal.read_text())
        for key, value in [('scope', 'e' * 64), ('activation_authorized', True),
                           ('rehearsal_accepted', True), ('restored_again', True)]:
            changed = {**before, key: value}
            journal.write_text(json.dumps(changed))
            with self.assertRaisesRegex(Blocked, 'unsupported operation'):
                self.recover_initial()

    def test_recover_rejects_partial_or_later_operation_journal(self):
        self.restored()
        (self.layout.evidence / '0002-refresh-intent.json').write_text('{}')
        with self.assertRaisesRegex(Blocked, 'single completed'):
            self.recover_initial()
        self.assertEqual(len(list(self.layout.evidence.iterdir())), 2)

    def test_recover_rejects_modified_candidate_and_live_writer(self):
        self.restored()
        self.supervisor.stopped = False
        with self.assertRaisesRegex(Blocked, 'writer still active'):
            self.recover_initial()
        self.supervisor.stopped = True
        (self.layout.tree / 'home/state/note').write_bytes(b'unaccepted test edit')
        with self.assertRaisesRegex(Blocked, 'inventory differs'):
            self.recover_initial()
        self.assertEqual(len(list(self.layout.evidence.iterdir())), 1)

    def test_recover_rejects_source_root_or_manifest_mismatch(self):
        self.restored()
        with self.assertRaisesRegex(Blocked, 'source/root'):
            self.recover_initial('e' * 64)
        journal = self.layout.evidence / '0001-restored.json'
        value = json.loads(journal.read_text())
        for key in ('root_binding', 'manifest_sha256'):
            changed = dict(value); changed[key] = 'e' * 64
            journal.write_text(json.dumps(changed))
            with self.assertRaises(Blocked):
                self.recover_initial()
        self.assertEqual(len(list(self.layout.evidence.iterdir())), 1)

    def recovery_chain(self):
        self.restored()
        recovered = self.recover_initial()
        pins = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.layout.evidence.iterdir()}
        return recovered, pins

    def recover_pinned_chain(self, pins):
        return CandidateController.recover_initial_restore(self.layout, "a" * 64, "e" * 64,
            self.provider, self.supervisor, ("home/state/state.sqlite",),
            prior_source_sha256="b" * 64, prior_journals_sha256=pins,
            fallback_artifact_sha256="c" * 64, capacity_policy_sha256="d" * 64)

    def test_initial_only_owner_handoff_preserves_chain_without_restore_or_acceptance(self):
        _, pins = self.recovery_chain()
        inode = (self.layout.tree / 'home/state/note').stat().st_ino
        recovered = self.recover_pinned_chain(pins)
        self.assertEqual(recovered.phase, 'restored')
        self.assertEqual(recovered.sequence, 3)
        self.assertEqual((self.layout.tree / 'home/state/note').stat().st_ino, inode)
        for name, expected in pins.items():
            self.assertEqual(hashlib.sha256((self.layout.evidence / name).read_bytes()).hexdigest(), expected)
        proof = json.loads((self.layout.evidence / '0003-initial-owner-recovered.json').read_text())
        self.assertEqual(proof['prior_journals_sha256'], pins)
        self.assertFalse(proof['activation_authorized'])
        self.assertIsNone(recovered.test_receipt)

    def test_initial_only_chain_rejects_missing_or_changed_pins(self):
        _, pins = self.recovery_chain()
        with self.assertRaisesRegex(Blocked, 'single completed'):
            self.recover_initial()
        bad = {**pins, '0002-initial-owner-recovered.json': 'f' * 64}
        with self.assertRaisesRegex(Blocked, 'hash pin'):
            self.recover_pinned_chain(bad)
        with self.assertRaisesRegex(Blocked, 'exact chain pins'):
            self.recover_pinned_chain({next(iter(pins)): next(iter(pins.values()))})

    def test_initial_only_chain_rejects_later_operation_even_if_hash_pinned(self):
        _, pins = self.recovery_chain()
        p = self.layout.evidence / '0003-rehearsal.json'
        p.write_text('{}')
        pins[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
        with self.assertRaisesRegex(Blocked, 'only initial-owner'):
            self.recover_pinned_chain(pins)

    def test_initial_only_chain_rejects_unlinked_or_false_binding_even_if_pinned(self):
        _, pins = self.recovery_chain()
        p = self.layout.evidence / '0002-initial-owner-recovered.json'
        before = json.loads(p.read_text())
        for key, value in [('prior_journal', 'missing'), ('prior_source', 'f' * 64),
                           ('scope', 'f' * 64), ('manifest_sha256', 'f' * 64),
                           ('capture_id', 'different'), ('activation_authorized', True),
                           ('rehearsal_accepted', True)]:
            p.write_text(json.dumps({**before, key: value}))
            pins[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
            with self.assertRaisesRegex(Blocked, 'chain binding'):
                self.recover_pinned_chain(pins)

    def test_initial_only_chain_rejects_live_writer_and_changed_tree(self):
        _, pins = self.recovery_chain()
        self.supervisor.stopped = False
        with self.assertRaisesRegex(Blocked, 'writer still active'):
            self.recover_pinned_chain(pins)
        self.supervisor.stopped = True
        (self.layout.tree / 'home/state/note').write_bytes(b'changed test edit')
        with self.assertRaisesRegex(Blocked, 'inventory differs'):
            self.recover_pinned_chain(pins)

    def test_recover_requires_completed_restore_proof(self):
        with self.assertRaisesRegex(Blocked, 'journal missing'):
            self.recover_initial()
        self.assertFalse(self.layout.tree.exists())

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

    def test_recorded_missing_link_preserved_but_not_launch_authority(self):
        (self.incumbent / "home/history-link").symlink_to("/missing-original-target")
        self.provider.capture("initial")
        proof = self.provider.captures["initial"][0]
        exceptions = recorded_link_exceptions(proof["entries"])
        proof.update(recorded_link_exceptions=exceptions,
                     recorded_link_exceptions_sha256=digest({
                         "manifest_sha256": proof["manifest_sha256"], "targets": exceptions}))
        self.restored()
        self.assertEqual(os.readlink(self.layout.tree / "home/history-link"), "/missing-original-target")
        self.assertEqual(inventory(self.layout.tree), inventory(self.incumbent))
        with self.assertRaisesRegex(Blocked, "namespace dependency missing"):
            binding_environment(self.layout, {"HISTORY": "/home/history-link"})
        configured = binding_environment(self.layout, {"WORKSPACES": "/home/worktrees"},
                                         preserved_capture=proof)
        self.assertEqual(configured["selectors"]["WORKSPACES"]["resolved_virtual"], "/home/state")
        self.assertFalse(configured["host_launch_authorized"])
        with self.assertRaisesRegex(Blocked, "namespace dependency missing"):
            binding_environment(self.layout, {"HISTORY": "/home/history-link"}, preserved_capture=proof)
        self.supervisor.receipt_mutator = lambda r: {**r, "checks": {
            **r["checks"], "operational_dependency_closure_verified": False}}
        with self.assertRaisesRegex(Blocked, "acceptance check"):
            self.controller.accept_rehearsal()
        self.assertEqual(self.controller.phase, "restored")
        (self.layout.tree / "home/history-link").rename(self.layout.evidence / "retained-original-link")
        (self.layout.tree / "home/history-link").symlink_to("/changed-unproven-target")
        with self.assertRaisesRegex(Blocked, "exception changed"):
            self.controller.accept_rehearsal()

    def test_recorded_link_exceptions_exact_and_manifest_bound(self):
        rows = copy.deepcopy(self.original)
        rows["home/worktrees"]["target"] = "/missing"
        exceptions = recorded_link_exceptions(rows)
        for altered in ({"home/worktrees": "/other"}, {"home/non-link": "/missing"}):
            with self.assertRaises(Blocked):
                validate_manifest(rows, recorded_link_exceptions=altered)
        for target in ("../../escape", "/home/worktrees"):
            rows["home/worktrees"]["target"] = target
            with self.assertRaises(Blocked):
                validate_manifest(rows, recorded_link_exceptions={"home/worktrees": target})
        proof = self.provider.captures["initial"][0]
        proof.update(entries=rows, manifest_sha256=digest(rows), recorded_link_exceptions=exceptions,
                     recorded_link_exceptions_sha256="f" * 64)
        with self.assertRaisesRegex(Blocked, "exception binding mismatch"):
            self.controller.restore("initial")
        self.assertFalse(self.layout.tree.exists())

    def test_virtual_link_through_another_link_is_in_scope(self):
        rows = copy.deepcopy(self.original)
        rows["home/via-link"] = {**rows["home/worktrees"], "target": "worktrees/note"}
        self.assertIs(validate_manifest(rows), rows)
        self.assertEqual(recorded_link_exceptions(rows), {})

    def test_explicit_candidate_bootstrap_requires_new_B_capture_after_catchup(self):
        before = inventory(self.incumbent)
        self.restored()
        token = "0123456789abcdef" * 2  # Isolated fixture, not a production identity.
        self.controller.bootstrap_identity('/home/state/state.sqlite', '/home/worktrees', token)
        self.assertEqual(inventory(self.incumbent), before)
        self.controller.accept_rehearsal()
        self.provider.capture('final')
        self.supervisor.capture = 'final'
        self.controller.catch_up('final')
        with self.assertRaisesRegex(Blocked, 'one-time enrollment'):
            namespace_runtime_identity(self.layout, '/home/state/state.sqlite', '/home/worktrees')
        self.controller.bootstrap_identity('/home/state/state.sqlite', '/home/worktrees', token)
        with self.assertRaisesRegex(Blocked, 'catch-up required'):
            self.controller.promote()
        self.provider.capture('bootstrap', root=self.layout.tree, origin=self.layout.binding())
        self.supervisor.capture = 'bootstrap'
        self.controller.accept_bootstrap_capture('bootstrap')
        self.controller.promote()
        self.assertEqual(self.controller.phase, 'active')
        self.assertEqual(inventory(self.incumbent), before)
        with sqlite3.connect(self.layout.tree / 'home/state/state.sqlite') as db:
            self.assertEqual(db.execute('SELECT value FROM retained').fetchall(), [('before',)])
            self.assertEqual(db.execute('SELECT dataset_id FROM vk_runtime_identity').fetchall(), [(token,)])

    def test_bootstrap_cannot_overwrite_identity_or_enroll_an_unverified_DB(self):
        self.restored()
        with self.assertRaisesRegex(Blocked, 'invalid explicit'):
            self.controller.bootstrap_identity('/home/state/state.sqlite', '/home/worktrees', 'not-a-token')
        with self.assertRaisesRegex(Blocked, 'outside authenticated required'):
            self.controller.bootstrap_identity('/home/state/note', '/home/worktrees', 'a' * 32)
        self.controller.bootstrap_identity('/home/state/state.sqlite', '/home/worktrees', 'a' * 32)
        with self.assertRaises(Blocked):
            self.controller.bootstrap_identity('/home/state/state.sqlite', '/home/worktrees', 'b' * 32)
        self.assertEqual(self.controller.phase, 'restored')

    def test_bootstrap_closes_WAL_owner_and_preserves_existing_rows(self):
        db = sqlite3.connect(self.database)
        db.execute('PRAGMA journal_mode=WAL')
        db.close()
        self.provider.capture('initial')
        self.restored()
        self.controller.bootstrap_identity('/home/state/state.sqlite', '/home/worktrees', 'a' * 32)
        path = self.layout.tree / 'home/state/state.sqlite'
        self.assertFalse(any(os.path.lexists(str(path) + s) for s in ('-wal', '-shm', '-journal')))
        with sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True) as checked:
            self.assertEqual(checked.execute('SELECT value FROM retained').fetchall(), [('before',)])

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

    def test_read_only_child_preserved_inside_writable_ancestor_without_permission_change(self):
        os.chmod(self.incumbent / 'home/state', 0o555)
        self.provider.capture('initial')
        self.accepted_rehearsal()
        os.chmod(self.incumbent / 'home/state', 0o755)  # Private fixture producer only.
        (self.incumbent / 'home/state/new-file').write_bytes(b'new authoritative file')
        os.chmod(self.incumbent / 'home/state', 0o555)
        self.provider.capture('final')
        self.supervisor.capture = 'final'
        old_inode = (self.layout.tree / 'home/state').stat().st_ino
        self.controller.catch_up('final')
        self.assertEqual(inventory(self.layout.tree), inventory(self.incumbent))
        retained = list(self.layout.evidence.glob('*-test-and-prior-state/home/state'))[0]
        self.assertEqual(retained.stat().st_mode & 0o777, 0o555)
        self.assertEqual(retained.stat().st_ino, old_inode)

    def test_read_only_top_directory_still_blocks_without_chmod_or_new_root(self):
        os.chmod(self.incumbent / 'home', 0o555)
        self.provider.capture('initial')
        self.accepted_rehearsal()
        (self.incumbent / 'home/state/note').write_bytes(b'new write in writable child')
        self.provider.capture('final')
        self.supervisor.capture = 'final'
        before, binding = inventory(self.layout.tree), self.layout.binding()
        with self.assertRaisesRegex(Blocked, 'no writable ancestor'):
            self.controller.catch_up('final')
        self.assertEqual(inventory(self.layout.tree), before)
        self.assertEqual(self.layout.binding(), binding)

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
