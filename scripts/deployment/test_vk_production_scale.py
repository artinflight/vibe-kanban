"""Production-observed preparation failures, isolated on the mounted SSD."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import test_vk_rolling_backup as fixtures
from vk_change_journal import IGNORED
from vk_desktop_transport import DesktopTransport
from vk_prep_common import digest
from vk_prepare import Preparation, promotion_ancestry
from vk_rolling_backup import Exclusions, capture, excluded, resume_delivery, validate_archive_warnings
from vk_writer_fence import ServiceFence


class ProductionBackupTests(unittest.TestCase):
    setUp = fixtures.BackupTests.setUp
    tearDown = fixtures.BackupTests.tearDown
    mirror = fixtures.BackupTests.mirror
    backup = fixtures.BackupTests.backup
    restored = fixtures.BackupTests.restored

    def test_directory_delete_recreate_keeps_coverage_and_new_content(self):
        directory = self.source / "scratch"
        directory.mkdir()
        self.journal.report()
        first = self.backup()
        directory.rmdir()
        self.assertTrue(self.journal.report()["ready"])
        directory.mkdir()
        (directory / "new.txt").write_text("new agent work")
        second = self.backup(first)
        self.assertEqual((self.restored(second) / "scratch/new.txt").read_text(), "new agent work")

    def test_unexpected_ignored_watch_still_fails_closed(self):
        wd = next(iter(self.journal.watches))
        self.journal.event(wd, IGNORED, "")
        self.assertFalse(self.journal.report()["ready"])

    def test_exclusion_cache_matches_original_and_rejects_link_retarget(self):
        target = self.root / "excluded"
        target.mkdir()
        link = self.root / "link"
        link.symlink_to(target)
        self.plan["excluded_rebuildable_directories"] = [str(link)]
        match = Exclusions(self.plan)
        for path in [target, target / "child", self.source, str(target) + "-other", target / "../other"]:
            self.assertEqual(match(path), excluded(path, self.plan))
        link.unlink()
        link.symlink_to(self.source)
        with self.assertRaisesRegex(ValueError, "target changed"):
            match.validate()

    def test_online_missing_warning_requires_ephemeral_scope_and_deletion(self):
        raw = str(self.source / "tmp/arg0/gone")
        watched = {"changed": [raw], "events": {raw: 0x200}}
        log = "tar: " + raw.lstrip("/") + ": Warning: Cannot stat: No such file or directory\n"
        with self.assertRaises(ValueError):
            validate_archive_warnings(log, watched, self.plan, True)
        self.plan["online_ephemeral_roots"] = [str(self.source / "tmp/arg0")]
        self.assertEqual(validate_archive_warnings(log, watched, self.plan, True), [raw])
        for online, events in [(False, 0x200), (True, 0x2)]:
            watched["events"][raw] = events
            with self.assertRaises(ValueError):
                validate_archive_warnings(log, watched, self.plan, online)

    def test_unknown_tar_warning_never_publishes(self):
        with self.assertRaisesRegex(ValueError, "Unexpected archive"):
            validate_archive_warnings("tar: Permission denied", {"changed": []}, self.plan, True)

    def test_legacy_manifest_last_archive_still_restores(self):
        first = self.backup()
        folder = Path(first["folder"])
        archive = folder / first["archive"]
        subprocess.run(["tar", "--use-compress-program=zstd -T2 -3", "-cf", str(archive),
            "-C", "/", "--no-recursion", "--null", "-T", str(folder / "paths.nul"),
            "--recursion", "-C", str(folder), "payload"], check=True)
        first["receipt"] = self.mirror(archive)
        self.assertEqual((self.restored(first) / self.note.name).read_text(), self.note.read_text())

    def failed_delivery(self, parent):
        with self.assertRaisesRegex(RuntimeError, "transport"):
            capture(self.plan, self.backups, self.journal.report,
                    lambda archive: (_ for _ in ()).throw(RuntimeError("transport")), parent, self.mirror)
        return next(self.backups.glob("delta-/*/pending-delivery.json")).parent

    def test_resume_delivers_existing_archive_and_keeps_later_changes_due(self):
        first = self.backup()
        self.note.write_text("captured work")
        folder = self.failed_delivery(first)
        archive = next(folder.glob("*.tar.zst"))
        checksum = digest(archive)
        self.note.write_text("new work during failed transfer")
        resumed = resume_delivery(self.plan, self.backups, folder, self.journal.report, self.mirror, self.mirror, first)
        self.assertEqual(digest(archive), checksum)
        self.assertFalse(resumed["frozen_boundary_verified"])
        self.assertEqual((self.restored(resumed) / self.note.name).read_text(), "captured work")
        latest = self.backup(resumed)
        self.assertEqual((self.restored(latest, "latest") / self.note.name).read_text(), self.note.read_text())

    def test_resume_corrupt_archive_and_replaced_journal_refused(self):
        first = self.backup()
        folder = self.failed_delivery(first)
        original = self.journal.instance
        self.journal.instance = "replacement"
        with self.assertRaises(ValueError):
            resume_delivery(self.plan, self.backups, folder, self.journal.report, self.mirror, self.mirror, first)
        self.journal.instance = original
        next(folder.glob("*.tar.zst")).write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "checksum"):
            resume_delivery(self.plan, self.backups, folder, self.journal.report, self.mirror, self.mirror, first)

    def test_resume_metadata_failure_keeps_previous_latest(self):
        first = self.backup()
        folder = self.failed_delivery(first)
        with self.assertRaisesRegex(ValueError, "metadata"):
            resume_delivery(self.plan, self.backups, folder, self.journal.report, self.mirror,
                lambda path: {"desktop_verified": False}, first)
        self.assertEqual(json.loads((self.backups / "latest-result.json").read_text())["archive"], first["archive"])

    def test_changed_exclusion_link_during_delivery_refuses_checkpoint(self):
        one, two = self.root / "one", self.root / "two"
        one.mkdir(); two.mkdir()
        link = self.root / "exclude"
        link.symlink_to(one)
        self.plan["excluded_rebuildable_directories"] = [str(link)]
        # Scope change intentionally requires a new watcher, not reused evidence.
        self.journal.plan["excluded_rebuildable_directories"] = [str(link)]
        def changed(archive):
            link.unlink(); link.symlink_to(two)
            return self.mirror(archive)
        with self.assertRaisesRegex(ValueError, "target changed"):
            self.backup(mirror=changed)


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"])
        self.root = Path(self.temporary.name)
        self.transport = DesktopTransport(self.root)
    def tearDown(self):
        self.temporary.cleanup()
    def test_direct_transport_preserves_strict_existing_host_key(self):
        with self.assertRaises(ValueError):
            DesktopTransport(self.root, hostname="10.0.0.109")
        options = DesktopTransport(self.root, hostname="10.0.0.109", host_key_alias="100.70.23.123").options
        self.assertIn("StrictHostKeyChecking=yes", options)
        self.assertIn("HostKeyAlias=100.70.23.123", options)
    def test_only_exec_channel_refusal_retries(self):
        failure = subprocess.CalledProcessError(255, "ssh", stderr="exec request failed on channel 0")
        with patch("vk_desktop_transport.subprocess.check_output", side_effect=[failure, "ok"]), patch("vk_desktop_transport.time.sleep"):
            self.assertEqual(self.transport.command("read-only probe"), "ok")
        with patch("vk_desktop_transport.subprocess.check_output", side_effect=subprocess.CalledProcessError(255, "ssh", stderr="Permission denied")) as call:
            with self.assertRaises(subprocess.CalledProcessError):
                self.transport.command("read-only probe")
            self.assertEqual(call.call_count, 1)
    def test_large_upload_create_resume_and_oversize_are_checked(self):
        archive = self.root / "unique.tar.zst"
        with archive.open("wb") as stream:
            stream.truncate(10_000_000)
        for size, verb in [(-1, "put"), (100, "reput")]:
            batches = []
            def run(command, **kwargs):
                if command[0] == "sftp":
                    batches.append(Path(command[command.index("-b") + 1]).read_text())
            with patch.object(self.transport, "command", side_effect=["", str(size), digest(archive)]), patch("vk_desktop_transport.subprocess.run", side_effect=run):
                self.assertTrue(self.transport.mirror(archive, "B:/vk-backups/fixture")["desktop_verified"])
            self.assertTrue(batches[0].startswith(verb + " "))
            self.assertIn('"/B:/vk-backups/fixture/', batches[0])
        with patch.object(self.transport, "command", side_effect=["", "10000001"]):
            with self.assertRaisesRegex(ValueError, "remote size"):
                self.transport.mirror(archive, "B:/vk-backups/fixture")


class MaterializationTests(unittest.TestCase):
    def test_missing_production_ancestry_is_detected_before_build(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as temporary:
            source = Path(temporary)
            subprocess.run(["git", "init", "-q", str(source)], check=True)
            subprocess.run(["git", "-C", str(source), "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "commit", "--allow-empty", "-qm", "fixture"], check=True)
            head = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
            self.assertEqual(promotion_ancestry(source, head), head)
            with self.assertRaisesRegex(ValueError, "ancestry"):
                promotion_ancestry(source, "0000000000000000000000000000000000000000")

    def test_previous_output_is_retained_outside_source(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as temporary:
            root = Path(temporary)
            source, cached = root / "source", root / "cached"
            source.mkdir(); cached.mkdir()
            (source / "dist").mkdir()
            (source / "dist/entry").write_text("old")
            (cached / "entry").write_text("new")
            runner = Preparation(source, root / "run", {"steps": []})
            runner.materialize(["frontend"], {"frontend": {"artifact_roots": [{"original": "dist", "path": str(cached)}]}})
            self.assertEqual((source / "dist/entry").read_text(), "new")
            self.assertEqual(list(source.iterdir()), [source / "dist"])
            self.assertEqual(next(runner.run_root.glob("materialized/*/previous/entry")).read_text(), "old")


class WriterTests(unittest.TestCase):
    def test_freeze_and_thaw_keep_original_service_identity_and_children(self):
        identity = {"pid": 123, "start": "456", "device": 1, "inode": 2, "cgroup": "fixture"}
        frozen = [False]
        def prop(unit, key):
            return "123" if key == "MainPID" else "frozen" if frozen[0] else "running"
        def command(argv, **kwargs):
            frozen[0] = "freeze" in argv
        calls = []
        fence = ServiceFence("fixture.service", identity, calls.append, approved=True)
        with patch("vk_writer_fence.prop", side_effect=prop), patch("vk_writer_fence.process_identity", return_value=identity), patch("vk_writer_fence.subprocess.run", side_effect=command):
            fence.freeze()
            self.assertTrue(fence.verify()["verified"])
            fence.thaw()
        self.assertEqual(calls, [False, True, True])
        self.assertFalse(frozen[0])
    def test_no_approval_and_restarted_process_are_rejected(self):
        with self.assertRaises(ValueError):
            ServiceFence("fixture.service", {"pid": 123}, lambda frozen: None)
        fence = ServiceFence("fixture.service", {"pid": 123}, lambda frozen: None, approved=True)
        with patch("vk_writer_fence.prop", return_value="999"):
            with self.assertRaisesRegex(ValueError, "restarted"):
                fence.thaw()


if __name__ == "__main__":
    unittest.main()
