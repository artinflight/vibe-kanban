"""Real SQLite/tar/inotify recovery tests, confined to SSD fixtures."""

import copy
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from vk_change_journal import Journal, OVERFLOW
from vk_prep_common import digest
from vk_rolling_backup import capture, restore_chain


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"])
        self.root = Path(self.temporary.name)
        self.source = self.root / "production-fixture"
        self.source.mkdir()
        self.backups = self.root / "backups"
        self.database = self.source / "state.sqlite"
        with sqlite3.connect(self.database) as db:
            db.execute("CREATE TABLE settings (id INTEGER PRIMARY KEY, value TEXT)")
            db.execute("INSERT INTO settings VALUES (1, 'saved messages; chosen model; goal checkpoint')")
        self.note = self.source / "dirty-untracked.txt"
        self.note.write_text("original agent work")
        self.history = self.source / "rollout.jsonl"
        self.history.write_text('{"thread":"original","turn":1}\n')
        self.attachment = self.source / "attachment.bin"
        self.attachment.write_bytes(b"exact attachment bytes")
        self.attachment.chmod(0o640)
        self.plan = {"sources": [str(self.source)], "sqlite_snapshots": [str(self.database)],
                     "excluded_rebuildable_directories": []}
        self.journal = Journal(self.plan)
        self.journal.tree(self.source)
        self.journal.ready = True

    def tearDown(self):
        self.journal.close()
        self.temporary.cleanup()

    def mirror(self, archive):
        return {"desktop_verified": True, "sha256": digest(archive), "bytes": archive.stat().st_size}

    def backup(self, parent=None, **kwargs):
        return capture(self.plan, self.backups, self.journal.report, kwargs.get("mirror", self.mirror), parent)

    def restored(self, result, name="verified"):
        destination = self.backups / name
        restored = restore_chain(result, destination)
        self.assertTrue(restored["passed"])
        return destination / "files" / str(self.source).lstrip("/")

    def test_checkpoint_restores_settings_history_attachment_and_permissions(self):
        first = self.backup()
        restored = self.restored(first)
        self.assertEqual((restored / self.note.name).read_text(), self.note.read_text())
        self.assertEqual((restored / self.history.name).read_text(), self.history.read_text())
        self.assertEqual((restored / self.attachment.name).read_bytes(), self.attachment.read_bytes())
        self.assertEqual((restored / self.attachment.name).stat().st_mode & 0o777, 0o640)
        with sqlite3.connect(restored / self.database.name) as db:
            self.assertEqual(db.execute("SELECT value FROM settings").fetchone()[0],
                             "saved messages; chosen model; goal checkpoint")

    def test_unchanged_database_is_reused_without_copy(self):
        first = self.backup()
        second = self.backup(first)
        self.assertEqual(second["sqlite_snapshots"], {})
        self.assertIn(str(self.database), second["reused_sqlite_snapshots"])
        self.assertEqual(second["parent"]["sha256"], first["receipt"]["sha256"])
        self.restored(second)

    def test_new_changes_and_dirty_work_are_caught_up_and_restored(self):
        first = self.backup()
        self.note.write_text("new dirty work since checkpoint")
        with self.history.open("a") as stream:
            stream.write('{"thread":"original","turn":2}\n')
        with sqlite3.connect(self.database) as db:
            db.execute("UPDATE settings SET value='new saved message and model choice'")
        second = self.backup(first)
        self.assertIn(str(self.database), second["sqlite_snapshots"])
        restored = self.restored(second)
        self.assertEqual((restored / self.note.name).read_text(), self.note.read_text())
        self.assertEqual((restored / self.history.name).read_text(), self.history.read_text())
        with sqlite3.connect(restored / self.database.name) as db:
            self.assertEqual(db.execute("SELECT value FROM settings").fetchone()[0], "new saved message and model choice")

    def test_new_subdirectory_content_is_captured(self):
        first = self.backup()
        directory = self.source / "new-worktree"
        directory.mkdir()
        (directory / "untracked.txt").write_text("new workspace")
        second = self.backup(first)
        restored = self.restored(second)
        self.assertEqual((restored / "new-worktree/untracked.txt").read_text(), "new workspace")

    def test_removed_file_is_removed_only_from_isolated_restore(self):
        first = self.backup()
        self.note.unlink()
        second = self.backup(first)
        restored = self.restored(second)
        self.assertFalse((restored / self.note.name).exists())
        self.assertFalse(self.note.exists())

    def test_writes_during_online_capture_are_recaptured(self):
        def mirror_with_write(archive):
            with sqlite3.connect(self.database) as db:
                db.execute("UPDATE settings SET value='work continued during backup'")
            self.note.write_text("work written during transfer")
            return self.mirror(archive)

        first = self.backup(mirror=mirror_with_write)
        self.assertNotIn(str(self.database), first["database_proofs"])
        second = self.backup(first)
        restored = self.restored(second)
        self.assertEqual((restored / self.note.name).read_text(), "work written during transfer")
        with sqlite3.connect(restored / self.database.name) as db:
            self.assertEqual(db.execute("SELECT value FROM settings").fetchone()[0], "work continued during backup")

    def test_journal_overflow_blocks_incremental_backup(self):
        first = self.backup()
        self.journal.event(-1, OVERFLOW, "")
        with self.assertRaisesRegex(ValueError, "coverage"):
            self.backup(first)

    def test_journal_replacement_blocks_old_parent(self):
        first = self.backup()
        self.journal.instance = "replacement"
        with self.assertRaisesRegex(ValueError, "journal instance"):
            self.backup(first)

    def test_moved_directory_blocks_incremental_backup(self):
        directory = self.source / "old"
        directory.mkdir()
        self.journal.report()
        first = self.backup()
        directory.rename(self.source / "new")
        with self.assertRaisesRegex(ValueError, "coverage"):
            self.backup(first)

    def test_changed_plan_requires_new_checkpoint(self):
        first = self.backup()
        self.plan["critical_sqlite"] = [str(self.database)]
        with self.assertRaisesRegex(ValueError, "plan changed"):
            self.backup(first)

    def test_bad_delivery_does_not_publish_latest(self):
        first = self.backup()
        before = (self.backups / "latest-result.json").read_bytes()
        self.note.write_text("new work")
        with self.assertRaisesRegex(ValueError, "unverified"):
            self.backup(first, mirror=lambda archive: {"desktop_verified": False, "sha256": digest(archive)})
        self.assertEqual((self.backups / "latest-result.json").read_bytes(), before)

    def test_failed_metadata_delivery_does_not_publish_latest(self):
        self.backup()
        before = (self.backups / "latest-result.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "metadata delivery"):
            capture(self.plan, self.backups, self.journal.report, self.mirror,
                    publish=lambda path: {"desktop_verified": False, "sha256": digest(path)})
        self.assertEqual((self.backups / "latest-result.json").read_bytes(), before)
        self.assertEqual(len(list(self.backups.glob("checkpoint-/*/result.json"))), 1)

    def test_corrupt_parent_blocks_incremental_backup(self):
        first = self.backup()
        (Path(first["folder"]) / first["archive"]).write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "unverified"):
            self.backup(first)

    def test_restore_refuses_corrupt_ancestor(self):
        first = self.backup()
        second = self.backup(first)
        (Path(first["folder"]) / first["archive"]).write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.restored(second)

    def test_restore_refuses_existing_or_non_task_destination(self):
        first = self.backup()
        with self.assertRaisesRegex(ValueError, "task directory"):
            restore_chain(first, self.source / "new-subdirectory")
        with self.assertRaisesRegex(ValueError, "empty"):
            restore_chain(first, self.backups)
        self.assertEqual(self.note.read_text(), "original agent work")

    def test_absolute_symlink_is_metadata_not_live_access(self):
        (self.source / "link-to-production").symlink_to(self.note)
        first = self.backup()
        restored = self.restored(first)
        self.assertFalse((restored / "link-to-production").exists())
        links = json.loads((self.backups / "verified/link-metadata.json").read_text())
        self.assertEqual(links[str(self.source / "link-to-production").lstrip("/")]["target"], str(self.note))
        self.assertEqual(self.note.read_text(), "original agent work")

    def test_hardlinked_work_survives_removal_of_original_name(self):
        alias = self.source / "other-name.txt"
        os.link(self.note, alias)
        first = self.backup()
        self.note.unlink()
        second = self.backup(first)
        restored = self.restored(second)
        self.assertEqual((restored / alias.name).read_text(), "original agent work")
        self.assertFalse((restored / self.note.name).exists())

    def test_directory_and_database_permissions_survive(self):
        self.source.chmod(0o750)
        self.database.chmod(0o640)
        first = self.backup()
        restored = self.restored(first)
        self.assertEqual(restored.stat().st_mode & 0o777, 0o750)
        self.assertEqual((restored / self.database.name).stat().st_mode & 0o777, 0o640)

    def test_staging_inside_watch_scope_is_refused(self):
        with self.assertRaisesRegex(ValueError, "outside watched"):
            capture(self.plan, self.source / "backups", self.journal.report, self.mirror)

    def test_critical_database_deletion_blocks_child(self):
        self.plan["critical_sqlite"] = self.plan.pop("sqlite_snapshots")
        first = self.backup()
        self.database.unlink()
        with self.assertRaisesRegex(ValueError, "Required SQLite"):
            self.backup(first)

    def test_frozen_boundary_captures_latest_work_and_restores(self):
        first = self.backup()
        self.note.write_text("work since online checkpoint")
        with sqlite3.connect(self.database) as db:
            db.execute("UPDATE settings SET value='latest frozen settings'")
        descriptors = []

        def publish(path):
            descriptors.append(json.loads(path.read_text()))
            return self.mirror(path)

        result = capture(self.plan, self.backups, self.journal.report, self.mirror, first, publish,
                         verify_fence=lambda: {"verified": True, "pid": 123})
        self.assertTrue(result["frozen_boundary_verified"])
        self.assertFalse(descriptors[0]["frozen_boundary_verified"])
        self.assertTrue(descriptors[0]["handover_acceptance_pending"])
        self.assertFalse(result["cutover_authorized"])
        restored = self.restored(result)
        self.assertEqual((restored / self.note.name).read_text(), self.note.read_text())
        with sqlite3.connect(restored / self.database.name) as db:
            self.assertEqual(db.execute("SELECT value FROM settings").fetchone()[0], "latest frozen settings")

    def test_online_capture_does_not_claim_frozen_boundary(self):
        self.assertFalse(self.backup()["frozen_boundary_verified"])

    def test_frozen_closed_wal_database_does_not_create_source_sidecars(self):
        first = self.backup()
        db = sqlite3.connect(self.database)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("UPDATE settings SET value='latest closed WAL work'")
        db.commit()
        db.close()
        self.assertFalse(Path(str(self.database) + "-wal").exists())
        result = capture(self.plan, self.backups, self.journal.report, self.mirror,
                         first, self.mirror, verify_fence=lambda: {"verified": True})
        self.assertTrue(result["frozen_boundary_verified"])
        self.assertFalse(Path(str(self.database) + "-wal").exists())
        self.assertFalse(Path(str(self.database) + "-shm").exists())
        restored = self.restored(result)
        with sqlite3.connect(restored / self.database.name) as db:
            self.assertEqual(db.execute("SELECT value FROM settings").fetchone()[0], "latest closed WAL work")

    def test_frozen_database_retains_committed_wal_frames(self):
        first = self.backup()
        db = sqlite3.connect(self.database)
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("UPDATE settings SET value='committed frames still in WAL'")
            db.commit()
            self.assertGreater(Path(str(self.database) + "-wal").stat().st_size, 0)
            result = capture(self.plan, self.backups, self.journal.report, self.mirror,
                             first, self.mirror, verify_fence=lambda: {"verified": True})
            restored = self.restored(result)
            with sqlite3.connect(restored / self.database.name) as restored_db:
                self.assertEqual(restored_db.execute("SELECT value FROM settings").fetchone()[0],
                                 "committed frames still in WAL")
        finally:
            db.close()

    def test_boundary_refuses_missing_or_changed_writer_fence(self):
        first = self.backup()
        for initial in ({"verified": False}, None):
            with self.assertRaisesRegex(ValueError, "fenced"):
                capture(self.plan, self.backups, self.journal.report, self.mirror, first, self.mirror,
                        verify_fence=lambda: initial)
        calls = []

        def changed():
            calls.append(True)
            return {"verified": True, "pid": len(calls)}

        with self.assertRaisesRegex(ValueError, "fence changed"):
            capture(self.plan, self.backups, self.journal.report, self.mirror, first, self.mirror,
                    verify_fence=changed)

    def test_boundary_detects_write_during_archive_delivery(self):
        first = self.backup()

        def writer(archive):
            self.note.write_text("unexpected live writer")
            return self.mirror(archive)

        with self.assertRaisesRegex(ValueError, "Protected data changed"):
            capture(self.plan, self.backups, self.journal.report, writer, first, self.mirror,
                    verify_fence=lambda: {"verified": True})
        self.assertEqual(json.loads((self.backups / "latest-result.json").read_text())["archive"], first["archive"])

    def test_boundary_detects_write_during_metadata_delivery(self):
        first = self.backup()

        def writer(metadata):
            with sqlite3.connect(self.database) as db:
                db.execute("UPDATE settings SET value='unexpected late writer'")
            return self.mirror(metadata)

        with self.assertRaisesRegex(ValueError, "Protected data changed"):
            capture(self.plan, self.backups, self.journal.report, self.mirror, first, writer,
                    verify_fence=lambda: {"verified": True})
        self.assertEqual(json.loads((self.backups / "latest-result.json").read_text())["archive"], first["archive"])

    def test_unchanged_wal_close_does_not_invalidate_snapshot(self):
        keeper = sqlite3.connect(self.database)
        try:
            keeper.execute("PRAGMA journal_mode=WAL")
            keeper.execute("UPDATE settings SET value='WAL fixture'")
            keeper.commit()
            first = self.backup()
            os.close(os.open(str(self.database) + "-wal", os.O_RDWR))
            second = self.backup(first)
            self.assertEqual(second["sqlite_snapshots"], {})
        finally:
            keeper.close()

    def test_frozen_boundary_accepts_only_unchanged_wal_close(self):
        keeper = sqlite3.connect(self.database)
        try:
            keeper.execute("PRAGMA journal_mode=WAL")
            keeper.execute("UPDATE settings SET value='WAL fixture'")
            keeper.commit()
            first = self.backup()

            def close_only(path):
                os.close(os.open(str(self.database) + "-wal", os.O_RDWR))
                return self.mirror(path)

            second = capture(self.plan, self.backups, self.journal.report, self.mirror, first, close_only,
                             verify_fence=lambda: {"verified": True})
            self.assertTrue(second["frozen_boundary_verified"])
            self.restored(second)
        finally:
            keeper.close()

    def test_journal_event_masks_do_not_hide_earlier_write(self):
        first = self.journal.report()["sequence"]
        self.note.write_text("real write")
        os.close(os.open(self.note, os.O_RDWR))
        observed = self.journal.report(first)
        self.assertTrue(observed["events"][str(self.note)] & 0x2)
        boundary = observed["sequence"]
        os.close(os.open(self.note, os.O_RDWR))
        later = self.journal.report(boundary)
        self.assertEqual(later["events"][str(self.note)], 0x8)


if __name__ == "__main__":
    unittest.main()
