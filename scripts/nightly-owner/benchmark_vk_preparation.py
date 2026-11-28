#!/usr/bin/env python3
"""Bounded backup fixture benchmark, not a production cutover or full preparation SLA."""

import argparse
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import time
import uuid

from vk_change_journal import Journal
from vk_prep_common import digest, measured, save, storage
from vk_rolling_backup import capture, mirror_desktop, restore_chain


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--desktop-directory", required=True)
    args = parser.parse_args()
    os.umask(0o077)
    root = storage(args.root) / ("fixture-" + uuid.uuid4().hex)
    source = root / "source"
    source.mkdir(parents=True)
    # Fixed-size incompressible content makes byte savings meaningful and bounds cost.
    with (source / "unchanged.bin").open("wb") as output:
        for _ in range(16):
            output.write(os.urandom(1024 * 1024))
    database = source / "state.sqlite"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE settings (value TEXT, padding BLOB)")
        db.execute("INSERT INTO settings VALUES (?, ?)",
                   ("saved messages; explicit model; goal checkpoint", os.urandom(1024 * 1024)))
    note = source / "untracked-agent-work.txt"
    note.write_text("original dirty work")
    history = source / "rollout-original.jsonl"
    history.write_text('{"thread":"original","turn":1}\n')
    attachment = source / "attachment.bin"
    attachment.write_bytes(b"attachment upload and retrieval fixture")
    attachment.chmod(0o640)
    plan = {"sources": [str(source)], "sqlite_snapshots": [str(database)],
            "excluded_rebuildable_directories": []}
    journal = Journal(plan)
    journal.tree(source)
    journal.ready = True
    mirror = lambda path: mirror_desktop(path, args.desktop_directory)
    timings, captures = {}, []
    try:
        with measured(timings, "checkpoint"):
            captures.append(capture(plan, root / "backups", journal.report, mirror, publish=mirror))
        note.write_text("new dirty work since checkpoint")
        with history.open("a") as stream:
            stream.write('{"thread":"original","turn":2}\n')
        with measured(timings, "file_only_catch_up"):
            captures.append(capture(plan, root / "backups", journal.report, mirror, captures[-1], mirror))
        with sqlite3.connect(database) as db:
            db.execute("UPDATE settings SET value='new saved message; retained model; original goal'")
        with measured(timings, "database_catch_up"):
            captures.append(capture(plan, root / "backups", journal.report, mirror, captures[-1], mirror))
        download = root / "desktop-recovery"
        download.mkdir()
        with measured(timings, "desktop_download_and_full_chain_restore"):
            for row in captures:
                subprocess.run(["scp", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                                "desktop:" + args.desktop_directory + "/" + row["archive"], str(download)],
                               check=True, timeout=120)
            metadata = captures[-1]["metadata_receipt"]["name"]
            subprocess.run(["scp", "-o", "BatchMode=yes", "desktop:" + args.desktop_directory + "/" + metadata,
                            str(download)], check=True, timeout=120)
            fetched = json.loads((download / metadata).read_text())
            restored = restore_chain(fetched, root / "backups/desktop-restored", download)
        files = Path(restored["destination"]) / "files" / str(source).lstrip("/")
        for name in (note.name, history.name, attachment.name, "unchanged.bin"):
            if digest(files / name) != digest(source / name):
                raise ValueError("Fixture recovery mismatch: " + name)
        if (files / attachment.name).stat().st_mode & 0o777 != 0o640:
            raise ValueError("Attachment permissions changed")
        with sqlite3.connect(files / database.name) as db:
            if db.execute("SELECT value FROM settings").fetchone()[0] != "new saved message; retained model; original goal":
                raise ValueError("Saved selection/checkpoint fixture recovery failed")
        report = {"at": time.time(), "fixture_only": True, "production_modified": False,
                  "fixture_bytes": 17 * 1024 * 1024, "timings_seconds": timings,
                  "archive_bytes": [row["receipt"]["bytes"] for row in captures],
                  "sqlite_snapshots_copied": [len(row["sqlite_snapshots"]) for row in captures],
                  "desktop_directory": args.desktop_directory, "desktop_round_trip": restored,
                  "archive_sha256": [row["receipt"]["sha256"] for row in captures],
                  "file_only_delta_fraction": captures[1]["receipt"]["bytes"] / captures[0]["receipt"]["bytes"],
                  "passed": True, "cutover_authorized": False}
        save(root / "benchmark.json", report)
        print(json.dumps({"report": str(root / "benchmark.json"), **report}, indent=2))
    finally:
        journal.close()


if __name__ == "__main__":
    main()
