#!/usr/bin/env python3
"""Verified online checkpoint/deltas. Never freezes services or restores production."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import shutil
import subprocess
import tarfile
import time
import uuid

from vk_change_journal import request, scope
from vk_prep_common import digest, file_identity, identity, measured, save, storage


def generation(path):
    return {suffix: file_identity(str(path) + suffix) for suffix in ("", "-wal")}


def check_journal(value, plan):
    if (not value.get("ready") or value.get("errors") or not value.get("instance")
            or value.get("scope_sha256") != identity(scope(plan))):
        raise ValueError("Backup journal coverage is lost or does not match the plan")


def excluded(path, plan):
    return any(Path(path).is_relative_to(Path(raw).resolve()) for raw in plan.get("excluded_rebuildable_directories", []))


def scan(roots, plan):
    paths = set()
    for root in roots:
        root = Path(root)
        paths.add(str(root))
        if root.is_symlink():
            # Preserve the link plus its separately addressed target, never follow it on restore.
            paths.update(scan([root.resolve()], plan))
        elif root.is_dir():
            for directory, dirs, names in os.walk(root, followlinks=False):
                dirs[:] = [name for name in dirs if not excluded(Path(directory) / name, plan)]
                paths.update(str(Path(directory) / name) for name in dirs + names
                             if not excluded(Path(directory) / name, plan))
    return paths


def mirror_desktop(archive, destination):
    if (not re.fullmatch(r"B:/vk-backups/[A-Za-z0-9_./-]+", destination)
            or ".." in PurePosixPath(destination).parts):
        raise ValueError("Use a Desktop B:/vk-backups task directory")
    options = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=15"]
    command = "powershell -NoProfile -Command \"New-Item -ItemType Directory -Force -Path '" + destination + "' | Out-Null\""
    subprocess.run(["ssh", *options, "desktop", command], check=True, timeout=60)
    subprocess.run(["scp", *options, str(archive), "desktop:" + destination + "/"], check=True, timeout=1800)
    command = "powershell -NoProfile -Command \"(Get-FileHash -Algorithm SHA256 -LiteralPath '" + destination + "/" + archive.name + "').Hash\""
    remote = subprocess.check_output(["ssh", *options, "desktop", command], text=True, timeout=1800).strip().lower()
    checksum = digest(archive)
    if remote != checksum:
        raise ValueError("Desktop backup checksum mismatch")
    return {"name": archive.name, "sha256": checksum, "bytes": archive.stat().st_size,
            "desktop_verified": True, "desktop_directory": destination}


def verified_parent(parent, plan, watched):
    if parent["scope_sha256"] != identity(scope(plan)) or parent["journal_instance"] != watched["instance"]:
        raise ValueError("Changed scope or journal instance requires a new online checkpoint")
    if parent["plan_sha256"] != identity(plan):
        raise ValueError("Backup plan changed; take a new online checkpoint")
    receipt = parent["receipt"]
    if receipt.get("desktop_verified") is not True or digest(Path(parent["folder"]) / parent["archive"]) != receipt["sha256"]:
        raise ValueError("Parent backup is unavailable or unverified")
    if watched["sequence"] < parent["journal_sequence"]:
        raise ValueError("Journal sequence moved backwards")


def capture(plan, root, journal, mirror, parent=None, publish=None):
    root = storage(root)
    if any(root.is_relative_to(Path(path).resolve()) for path in plan["sources"]):
        raise ValueError("Backup staging must be outside watched source roots")
    if any(not Path(path).exists() for path in plan["sources"]):
        raise ValueError("Missing source roots require an explicit reconciled backup plan")
    timings = {}
    started = time.monotonic()
    with measured(timings, "journal_and_parent"):
        before = journal(0 if parent is None else parent["journal_sequence"])
        check_journal(before, plan)
        if parent is not None:
            verified_parent(parent, plan, before)
    folder = root / ("checkpoint-" if parent is None else "delta-") / uuid.uuid4().hex
    folder.mkdir(parents=True, mode=0o700)
    payload = folder / "payload"
    payload.mkdir(mode=0o700)
    with measured(timings, "inventory"):
        paths = scan(plan["sources"], plan) if parent is None else set(before["changed"])
        if parent is not None:
            paths.update(scan([path for path in paths if Path(path).is_dir()], plan))
        paths = {path for path in paths if not excluded(path, plan)}
        absent = sorted(path for path in paths if not Path(path).exists() and not Path(path).is_symlink())
        files = sorted(paths - set(absent))
        databases = {str(Path(raw).resolve()) for raw in plan.get("sqlite_snapshots", [])}
        databases.update(str(Path(raw).resolve()) for raw in plan.get("critical_sqlite", []))
        proofs = dict(parent.get("database_proofs", {})) if parent else {}
        databases.update(parent.get("databases", []) if parent else [])
        for raw in files:
            path = Path(raw)
            if path.is_file() and not path.is_symlink():
                with path.open("rb") as stream:
                    if stream.read(16) == b"SQLite format 3\0":
                        databases.add(str(path.resolve()))
        for raw in databases:
            if not any(Path(raw).is_relative_to(Path(source).resolve()) for source in plan["sources"]):
                raise ValueError("Database is outside journal coverage: " + raw)
        changed = {str(Path(raw).resolve()) for raw in before["changed"]}
    snapshots, readers, versions, signatures, reused = {}, {}, {}, {}, []
    try:
        with measured(timings, "sqlite_snapshot_and_integrity"):
            for raw in sorted(databases):
                path = Path(raw)
                if not path.exists():
                    proofs.pop(raw, None)
                    if parent is None or raw in plan.get("sqlite_snapshots", []):
                        raise ValueError("Required SQLite database is missing: " + raw)
                    continue
                signatures[raw] = generation(path)
                previous = proofs.get(raw)
                if (previous and previous.get("generation") == signatures[raw]
                        and not any(raw + suffix in changed for suffix in ("", "-wal"))):
                    reused.append(raw)
                    continue
                source = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
                readers[raw] = source
                versions[raw] = source.execute("PRAGMA data_version").fetchone()[0]
                target = payload / "sqlite" / (hashlib.sha256(raw.encode()).hexdigest() + ".sqlite")
                target.parent.mkdir(exist_ok=True)
                with sqlite3.connect(target) as destination:
                    source.execute("BEGIN")
                    source.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
                    source.backup(destination, pages=4096)
                    source.rollback()
                    if destination.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise ValueError("SQLite snapshot integrity failed: " + raw)
                target.chmod(path.stat().st_mode & 0o777)
                snapshots[raw] = {"path": str(target.relative_to(payload)), "sha256": digest(target)}
                proofs[raw] = {"generation": signatures[raw], "snapshot_sha256": snapshots[raw]["sha256"]}
        omitted = {raw + suffix for raw in databases for suffix in ("", "-wal", "-shm")}
        file_list = folder / "paths.nul"
        file_list.write_bytes(b"".join(path.lstrip("/").encode() + b"\0" for path in files
                                     if Path(path).is_symlink() or str(Path(path).resolve()) not in omitted))
        parent_ref = None if parent is None else {"folder": parent["folder"], "archive": parent["archive"],
                                                  "sha256": parent["receipt"]["sha256"]}
        manifest = {"schema": 1, "at": time.time(), "scope_sha256": identity(scope(plan)), "plan_sha256": identity(plan),
                    "journal_instance": before["instance"], "journal_sequence": before["sequence"],
                    "parent": parent_ref, "sqlite_snapshots": snapshots, "absent_paths": absent,
                    "online_preparation": True, "production_boundary": False}
        save(payload / "manifest.json", manifest)
        archive = folder / (folder.parent.name + "-" + folder.name + ".tar.zst")
        with measured(timings, "archive"):
            with (folder / "tar.log").open("wb") as log:
                result = subprocess.run(["tar", "--use-compress-program=zstd -T2 -3", "-cf", str(archive),
                                         "-C", "/", "--no-recursion", "--null", "-T", str(file_list),
                                         "--recursion", "-C", str(folder), "payload"], stderr=log)
            if result.returncode not in (0, 1):
                raise RuntimeError("Backup archive failed; inspect " + str(folder / "tar.log"))
        with measured(timings, "archive_restore_verify"):
            restored = folder / "verified-payload"
            restored.mkdir()
            subprocess.run(["tar", "--zstd", "-xf", str(archive), "-C", str(restored), "payload"], check=True)
            for row in snapshots.values():
                if digest(restored / "payload" / row["path"]) != row["sha256"]:
                    raise ValueError("Restored SQLite snapshot checksum mismatch")
        with measured(timings, "desktop_transfer_and_verify"):
            receipt = mirror(archive)
            if receipt.get("desktop_verified") is not True or receipt["sha256"] != digest(archive):
                raise ValueError("Backup delivery is unverified")
        after = journal(before["sequence"])
        check_journal(after, plan)
        if after["instance"] != before["instance"] or after["sequence"] < before["sequence"]:
            raise ValueError("Journal changed during backup; refuse to advance the checkpoint")
        after_changed = {str(Path(raw).resolve()) for raw in after["changed"]}
        for raw in signatures:
            changed_version = raw in readers and readers[raw].execute("PRAGMA data_version").fetchone()[0] != versions[raw]
            if (generation(raw) != signatures[raw] or changed_version
                    or any(raw + suffix in after_changed for suffix in ("", "-wal"))):
                proofs.pop(raw, None)
        result = {**manifest, "folder": str(folder), "archive": archive.name, "receipt": receipt,
                  "database_proofs": proofs, "databases": sorted(databases), "reused_sqlite_snapshots": reused,
                  "copied_files": len(files), "changes_during_capture": after["changed"],
                  "timings": timings, "total_preparation_seconds": time.monotonic() - started,
                  "passed": True, "cutover_authorized": False}
        save(folder / "result.json", result)
        if publish is not None:
            metadata = folder / (archive.name + ".result.json")
            save(metadata, result)
            with measured(timings, "desktop_metadata_transfer_and_verify"):
                receipt = publish(metadata)
            if receipt.get("desktop_verified") is not True or receipt["sha256"] != digest(metadata):
                raise ValueError("Backup recovery metadata delivery is unverified")
            result["metadata_receipt"] = receipt
        result["total_preparation_seconds"] = time.monotonic() - started
        save(folder / "result.json", result)
        save(root / "latest-result.json", result)
        return result
    finally:
        for connection in readers.values():
            connection.close()


def restore_chain(result, destination, archive_directory=None):
    destination = storage(destination)
    backup_root = Path(result["folder"]).parent.parent.resolve()
    if not destination.is_relative_to(backup_root):
        raise ValueError("Restore verification must stay within the isolated backup task directory")
    if destination.exists():
        raise ValueError("Restore verification requires a new empty isolated destination")
    destination.mkdir(parents=True, mode=0o700)
    archives, seen = [], set()
    current = {"folder": result["folder"], "archive": result["archive"], "sha256": result["receipt"]["sha256"]}
    while current:
        if Path(current["archive"]).name != current["archive"]:
            raise ValueError("Invalid backup archive name")
        archive = (Path(archive_directory) if archive_directory else Path(current["folder"])) / current["archive"]
        if str(archive) in seen:
            raise ValueError("Backup parent cycle")
        seen.add(str(archive))
        if digest(archive) != current["sha256"]:
            raise ValueError("Backup chain checksum mismatch")
        archives.append(archive)
        with subprocess.Popen(["zstd", "-dc", str(archive)], stdout=subprocess.PIPE) as decompressor:
            with tarfile.open(fileobj=decompressor.stdout, mode="r|") as tar:
                found = None
                for member in tar:
                    if member.name == "payload/manifest.json":
                        found = json.load(tar.extractfile(member))
                if found is None:
                    raise ValueError("Missing backup manifest")
            if decompressor.wait():
                raise ValueError("Backup decompression failed")
        current = found["parent"]
    links, directory_modes = {}, {}
    for archive in reversed(archives):
        manifest, sqlite_payloads = None, {}
        with subprocess.Popen(["zstd", "-dc", str(archive)], stdout=subprocess.PIPE) as decompressor:
            with tarfile.open(fileobj=decompressor.stdout, mode="r|") as tar:
                for member in tar:
                    name = PurePosixPath(member.name)
                    if name.is_absolute() or ".." in name.parts:
                        raise ValueError("Unsafe archive member")
                    if member.name == "payload/manifest.json":
                        manifest = json.load(tar.extractfile(member))
                        continue
                    if member.name.startswith("payload/"):
                        if member.isfile():
                            target = destination / "snapshots" / archive.stem / name
                            target.parent.mkdir(parents=True, exist_ok=True)
                            with target.open("wb") as stream:
                                shutil.copyfileobj(tar.extractfile(member), stream)
                            target.chmod(member.mode)
                            sqlite_payloads[str(name.relative_to("payload"))] = target
                        continue
                    target = destination / "files" / name
                    if member.isdir():
                        target.mkdir(parents=True, exist_ok=True)
                        directory_modes[str(target)] = member.mode
                    elif member.isfile():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with target.open("wb") as stream:
                            shutil.copyfileobj(tar.extractfile(member), stream)
                        target.chmod(member.mode)
                        links.pop(str(name), None)
                    elif member.issym() or member.islnk():
                        # Retain link metadata without creating a route back to production.
                        if target.is_file():
                            target.unlink()
                        elif target.is_dir():
                            shutil.rmtree(target)
                        links[str(name)] = {"target": member.linkname, "hardlink": member.islnk()}
                    else:
                        raise ValueError("Unsupported special backup member")
            if decompressor.wait():
                raise ValueError("Backup decompression failed")
        if manifest is None:
            raise ValueError("Missing backup manifest")
        for raw in manifest["absent_paths"]:
            name = PurePosixPath(raw.lstrip("/"))
            if ".." in name.parts:
                raise ValueError("Unsafe removed path")
            target = destination / "files" / name
            if target.is_file():
                target.unlink()
            elif target.is_dir():
                shutil.rmtree(target)
            links.pop(str(name), None)
        for raw, row in manifest["sqlite_snapshots"].items():
            payload = sqlite_payloads[row["path"]]
            if digest(payload) != row["sha256"]:
                raise ValueError("Restored database hash mismatch")
            name = PurePosixPath(raw.lstrip("/"))
            if ".." in name.parts:
                raise ValueError("Unsafe database path")
            target = destination / "files" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(payload, target)
            with sqlite3.connect(target.as_uri() + "?mode=ro", uri=True) as connection:
                if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("Restored database integrity mismatch")
        pending = {name: row for name, row in links.items() if row["hardlink"]}
        while pending:
            progress = False
            for name, row in list(pending.items()):
                linked = PurePosixPath(row["target"])
                if linked.is_absolute() or ".." in linked.parts:
                    raise ValueError("Unsafe hardlink target")
                target = destination / "files" / name
                if target.is_file() and not target.is_symlink():
                    del pending[name]
                    progress = True
                    continue
                original = destination / "files" / linked
                if original.is_file() and not original.is_symlink():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if not target.exists():
                        os.link(original, target)
                    del pending[name]
                    progress = True
            if not progress:
                raise ValueError("Unresolved hardlink in backup chain")
    for raw, mode in sorted(directory_modes.items(), key=lambda row: len(Path(row[0]).parts), reverse=True):
        if Path(raw).is_dir():
            Path(raw).chmod(mode)
    save(destination / "link-metadata.json", links)
    return {"passed": True, "archives": len(archives), "destination": str(destination),
            "production_restored": False, "absolute_symlinks_materialized": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    backup = commands.add_parser("capture")
    backup.add_argument("--plan", required=True, type=Path)
    backup.add_argument("--root", required=True, type=Path)
    backup.add_argument("--socket", required=True, type=Path)
    backup.add_argument("--parent", type=Path)
    backup.add_argument("--desktop-directory", required=True)
    restore = commands.add_parser("verify-restore")
    restore.add_argument("--result", required=True, type=Path)
    restore.add_argument("--destination", required=True, type=Path)
    restore.add_argument("--archive-directory", type=Path, help="Directory of archive copies fetched from Desktop")
    args = parser.parse_args()
    os.umask(0o077)
    if args.action == "capture":
        result = capture(json.loads(args.plan.read_text()), args.root, lambda since: request(args.socket, since),
                         lambda archive: mirror_desktop(archive, args.desktop_directory),
                         json.loads(args.parent.read_text()) if args.parent else None,
                         lambda metadata: mirror_desktop(metadata, args.desktop_directory))
    else:
        result = restore_chain(json.loads(args.result.read_text()), args.destination, args.archive_directory)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
