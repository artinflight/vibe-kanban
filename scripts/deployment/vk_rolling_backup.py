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
from vk_desktop_transport import DesktopTransport


def generation(path):
    return {suffix: file_identity(str(path) + suffix) for suffix in ("", "-wal")}


def content_event(database, watched):
    changed = set(watched["changed"])
    return any(raw in changed and watched.get("events", {}).get(raw) != 0x8
               for raw in (database, database + "-wal"))


def check_journal(value, plan):
    if (not value.get("ready") or value.get("errors") or not value.get("instance")
            or value.get("scope_sha256") != identity(scope(plan))):
        raise ValueError("Backup journal coverage is lost or does not match the plan")


def excluded(path, plan):
    return any(Path(path).is_relative_to(Path(raw).resolve()) for raw in plan.get("excluded_rebuildable_directories", []))


class Exclusions:
    def __init__(self, plan):
        self.raw = tuple(plan.get("excluded_rebuildable_directories", []))
        self.roots = tuple(Path(raw).resolve() for raw in self.raw)
        self.exact = frozenset(map(str, self.roots))
        self.prefixes = tuple(str(root).rstrip("/") + "/" for root in self.roots)

    def __call__(self, path):
        value = str(Path(path))
        return value in self.exact or value.startswith(self.prefixes)

    def validate(self):
        if tuple(Path(raw).resolve() for raw in self.raw) != self.roots:
            raise ValueError("Exclusion link target changed during capture")


def scan(roots, plan, exclusions=None):
    exclusions = exclusions or Exclusions(plan)
    paths = set()
    for root in roots:
        root = Path(root)
        paths.add(str(root))
        if root.is_symlink():
            # Preserve the link plus its separately addressed target, never follow it on restore.
            paths.update(scan([root.resolve()], plan, exclusions))
        elif root.is_dir():
            for directory, dirs, names in os.walk(root, followlinks=False):
                dirs[:] = [name for name in dirs if not exclusions(Path(directory) / name)]
                paths.update(str(Path(directory) / name) for name in dirs + names
                             if not exclusions(Path(directory) / name))
    return paths


def mirror_desktop(archive, destination):
    return DesktopTransport(Path(archive).parent / "transport").mirror(archive, destination)


def validate_archive_warnings(log, watched, plan, online):
    allowed = []
    roots = [Path(raw).resolve() for raw in plan.get("online_ephemeral_roots", [])]
    for line in log.splitlines():
        if line == "tar: Exiting with failure status due to previous errors" and allowed:
            continue
        missing = re.fullmatch(r"tar: (.+?): (?:Warning: )?Cannot stat: No such file or directory", line)
        changed = re.fullmatch(r"tar: (.+?): (?:Warning: )?file changed as we read it", line)
        match = missing or changed
        raw = "/" + match.group(1).lstrip("/") if match else ""
        covered = raw in watched["changed"]
        if not online or not match or not covered:
            raise ValueError("Unexpected archive warning: " + line)
        if missing and (not any(Path(raw).is_relative_to(root) for root in roots)
                        or not watched.get("events", {}).get(raw, 0) & (0x200 | 0x400)
                        or Path(raw).exists() or Path(raw).is_symlink()):
            raise ValueError("Missing source is not a proven ephemeral deletion: " + raw)
        allowed.append(raw)
    return allowed


def verified_parent(parent, plan, watched):
    if parent["scope_sha256"] != identity(scope(plan)) or parent["journal_instance"] != watched["instance"]:
        raise ValueError("Changed scope or journal instance requires a new online checkpoint")
    if parent["plan_sha256"] != identity(plan):
        raise ValueError("Backup plan changed; take a new online checkpoint")
    if ("exclusion_targets" in parent
            and parent["exclusion_targets"] != list(map(str, Exclusions(plan).roots))):
        raise ValueError("Parent exclusion targets changed; take a new online checkpoint")
    receipt = parent["receipt"]
    if receipt.get("desktop_verified") is not True or digest(Path(parent["folder"]) / parent["archive"]) != receipt["sha256"]:
        raise ValueError("Parent backup is unavailable or unverified")
    if watched["sequence"] < parent["journal_sequence"]:
        raise ValueError("Journal sequence moved backwards")


def verify_snapshot_archive(archive, snapshots, manifest_path):
    expected = {"payload/" + row["path"]: row["sha256"] for row in snapshots.values()}
    expected["payload/manifest.json"] = digest(manifest_path)
    seen = set()
    process = subprocess.Popen(["zstd", "-dc", str(archive)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        with tarfile.open(fileobj=process.stdout, mode="r|") as contents:
            for member in contents:
                if member.name not in expected:
                    continue
                if member.name in seen or not member.isfile():
                    raise ValueError("Duplicate or invalid snapshot archive member")
                checksum = hashlib.sha256()
                with contents.extractfile(member) as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        checksum.update(chunk)
                if checksum.hexdigest() != expected[member.name]:
                    raise ValueError("Restored SQLite snapshot checksum mismatch")
                seen.add(member.name)
        while process.stdout.read(1024 * 1024):
            pass
        if process.wait() != 0 or seen != set(expected):
            raise ValueError("Incomplete or corrupt snapshot archive")
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()


def capture(plan, root, journal, mirror, parent=None, publish=None, *, verify_fence=None):
    root = storage(root)
    if any(root.is_relative_to(Path(path).resolve()) for path in plan["sources"]):
        raise ValueError("Backup staging must be outside watched source roots")
    if any(not Path(path).exists() for path in plan["sources"]):
        raise ValueError("Missing source roots require an explicit reconciled backup plan")
    timings = {}
    exclusions = Exclusions(plan)
    started = time.monotonic()
    fence_before = None
    if verify_fence is not None:
        if parent is None or publish is None:
            raise ValueError("Final boundary requires a verified online parent and metadata delivery")
        fence_before = verify_fence()
        if not isinstance(fence_before, dict) or fence_before.get("verified") is not True:
            raise ValueError("Final boundary writers are not verified fenced")
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
        paths = scan(plan["sources"], plan, exclusions) if parent is None else set(before["changed"])
        if parent is not None:
            paths.update(scan([path for path in paths if Path(path).is_dir()], plan, exclusions))
        paths = {path for path in paths if not exclusions(path)}
        absent = sorted(path for path in paths if not Path(path).exists() and not Path(path).is_symlink())
        files = sorted(paths - set(absent))
        required_databases = {str(Path(raw).resolve()) for raw in
                              [*plan.get("sqlite_snapshots", []), *plan.get("critical_sqlite", [])]}
        databases = set(required_databases)
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
    snapshots, readers, versions, signatures, reused = {}, {}, {}, {}, []

    def stable_boundary():
        exclusions.validate()
        watched = journal(before["sequence"])
        check_journal(watched, plan)
        if watched["instance"] != before["instance"] or watched["sequence"] < before["sequence"]:
            raise ValueError("Final boundary journal identity changed")
        # SQLite reader bookkeeping is not content; DB/WAL generations are checked separately.
        shm = {raw + "-shm" for raw in databases}
        database_files = {raw + suffix for raw in databases for suffix in ("", "-wal")}
        changes = [raw for raw in watched["changed"] if str(Path(raw).resolve()) not in shm
                   and not (raw in database_files and watched.get("events", {}).get(raw) == 0x8)]
        generations = {raw: {"before": value, "after": generation(raw)} for raw, value in signatures.items()
                       if generation(raw) != value}
        logical_changes = [raw for raw, connection in readers.items()
                           if connection.execute("PRAGMA data_version").fetchone()[0] != versions[raw]]
        if changes or generations or logical_changes:
            save(folder / "boundary-instability.json", {"changed_paths": changes, "database_generations": generations,
                                                       "logical_database_changes": logical_changes,
                                                       "sequence_before": before["sequence"], "sequence_after": watched["sequence"]})
            raise ValueError("Protected data changed during final boundary capture")
        if verify_fence() != fence_before:
            raise ValueError("Final boundary writer fence changed")

    try:
        with measured(timings, "sqlite_snapshot_and_integrity"):
            for raw in sorted(databases):
                path = Path(raw)
                if not path.exists():
                    proofs.pop(raw, None)
                    if parent is None or raw in required_databases:
                        raise ValueError("Required SQLite database is missing: " + raw)
                    continue
                signatures[raw] = generation(path)
                previous = proofs.get(raw)
                if (previous and previous.get("generation") == signatures[raw]
                        and not content_event(raw, before)):
                    reused.append(raw)
                    continue
                source_path = path
                sidecars = (raw + "-wal", raw + "-journal")
                target = payload / "sqlite" / (hashlib.sha256(raw.encode()).hexdigest() + ".sqlite")
                target.parent.mkdir(exist_ok=True)
                private_snapshot = verify_fence is not None and not any(os.path.lexists(p) for p in sidecars)
                if private_snapshot:
                    # A fenced, fully checkpointed copy is already the snapshot.
                    # Immutable reading is confined to that private copy, never live data.
                    source_path = target
                    shutil.copyfile(path, source_path)
                    if generation(path) != signatures[raw] or any(os.path.lexists(p) for p in sidecars):
                        raise ValueError("Fenced database changed while copying: " + raw)
                source = sqlite3.connect(source_path.as_uri() + ("?immutable=1" if private_snapshot else "?mode=ro"), uri=True)
                readers[raw] = source
                versions[raw] = source.execute("PRAGMA data_version").fetchone()[0]
                if private_snapshot:
                    if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise ValueError("SQLite snapshot integrity failed: " + raw)
                else:
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
                    "exclusion_targets": list(map(str, exclusions.roots)),
                    "journal_instance": before["instance"], "journal_sequence": before["sequence"],
                    "parent": parent_ref, "sqlite_snapshots": snapshots, "absent_paths": absent,
                    "online_preparation": verify_fence is None, "production_boundary": False,
                    "frozen_boundary_requested": verify_fence is not None}
        if "recopy_baseline" in before:
            manifest["recopy_baseline"] = before["recopy_baseline"]
        save(payload / "manifest.json", manifest)
        archive = folder / (folder.parent.name + "-" + folder.name + ".tar.zst")
        with measured(timings, "archive"):
            with (folder / "tar.log").open("wb") as log:
                online_options = ["--ignore-failed-read"] if verify_fence is None else []
                payload_members = ["payload/manifest.json"]
                if (payload / "sqlite").exists():
                    payload_members.append("payload/sqlite")
                result = subprocess.run(["tar", *online_options, "--use-compress-program=zstd -T2 -3", "-cf", str(archive),
                                         "--recursion", "-C", str(folder), *payload_members,
                                         "-C", "/", "--no-recursion", "--null", "-T", str(file_list)], stderr=log)
            if result.returncode not in ((0,) if verify_fence is not None else (0, 1)):
                raise RuntimeError("Backup archive failed; inspect " + str(folder / "tar.log"))
            watched = journal(before["sequence"])
            check_journal(watched, plan)
            if watched["instance"] != before["instance"]:
                raise ValueError("Journal changed during archive")
            warnings = validate_archive_warnings((folder / "tar.log").read_text(), watched, plan, verify_fence is None)
        with measured(timings, "archive_restore_verify"):
            if verify_fence is not None:
                verify_snapshot_archive(archive, snapshots, payload / "manifest.json")
            else:
                restored = folder / "verified-payload"
                restored.mkdir()
                subprocess.run(["tar", "--zstd", "-xf", str(archive), "-C", str(restored), "payload"], check=True)
                for row in snapshots.values():
                    if digest(restored / "payload" / row["path"]) != row["sha256"]:
                        raise ValueError("Restored SQLite snapshot checksum mismatch")
        if verify_fence is None:
            save(folder / "pending-delivery.json", {**manifest, "folder": str(folder), "archive": archive.name,
                "archive_sha256": digest(archive), "database_proofs": proofs, "databases": sorted(databases),
                "copied_files": len(files), "timings": dict(timings), "passed": False})
        with measured(timings, "desktop_transfer_and_verify"):
            exclusions.validate()
            receipt = mirror(archive)
            if receipt.get("desktop_verified") is not True or receipt["sha256"] != digest(archive):
                raise ValueError("Backup delivery is unverified")
        after = journal(before["sequence"])
        check_journal(after, plan)
        if after["instance"] != before["instance"] or after["sequence"] < before["sequence"]:
            raise ValueError("Journal changed during backup; refuse to advance the checkpoint")
        for raw in signatures:
            changed_version = raw in readers and readers[raw].execute("PRAGMA data_version").fetchone()[0] != versions[raw]
            if (generation(raw) != signatures[raw] or changed_version
                    or content_event(raw, after)):
                proofs.pop(raw, None)
        if verify_fence is not None:
            stable_boundary()
        exclusions.validate()
        result = {**manifest, "folder": str(folder), "archive": archive.name, "receipt": receipt,
                  "database_proofs": proofs, "databases": sorted(databases), "reused_sqlite_snapshots": reused,
                  "copied_files": len(files), "changes_during_capture": after["changed"],
                  "timings": timings, "total_preparation_seconds": time.monotonic() - started,
                  "passed": True, "cutover_authorized": False,
                  "frozen_boundary_verified": verify_fence is not None, "writer_fence": fence_before}
        result["online_archive_warnings_recaptured_by_next_delta"] = warnings
        if publish is not None:
            metadata = folder / (archive.name + ".result.json")
            # A restore descriptor cannot certify the still-pending post-delivery fence check.
            save(metadata, {**result, "frozen_boundary_verified": False,
                            "handover_acceptance_pending": verify_fence is not None})
            with measured(timings, "desktop_metadata_transfer_and_verify"):
                receipt = publish(metadata)
            if receipt.get("desktop_verified") is not True or receipt["sha256"] != digest(metadata):
                raise ValueError("Backup recovery metadata delivery is unverified")
            result["metadata_receipt"] = receipt
        if verify_fence is not None:
            stable_boundary()
        exclusions.validate()
        result["total_preparation_seconds"] = time.monotonic() - started
        save(folder / "result.json", result)
        save(root / "latest-result.json", result)
        return result
    finally:
        for connection in readers.values():
            connection.close()


def resume_delivery(plan, root, folder, journal, mirror, publish, parent=None):
    """Deliver an unchanged completed online archive, never a frozen boundary."""
    root, folder = storage(root), storage(folder)
    if folder.parent.parent != root or (folder / "result.json").exists():
        raise ValueError("Resume requires an unpublished archive in this backup root")
    pending = json.loads((folder / "pending-delivery.json").read_text())
    if (pending["folder"] != str(folder) or not pending["online_preparation"]
            or pending["frozen_boundary_requested"] or pending["plan_sha256"] != identity(plan)):
        raise ValueError("Resume is only for the exact completed online backup plan")
    exclusions = Exclusions(plan)
    if pending["exclusion_targets"] != list(map(str, exclusions.roots)):
        raise ValueError("Resume exclusion targets changed")
    watched = journal(pending["journal_sequence"])
    check_journal(watched, plan)
    if watched["instance"] != pending["journal_instance"]:
        raise ValueError("Resume journal instance changed")
    if parent:
        verified_parent(parent, plan, watched)
    expected = None if parent is None else {"folder": parent["folder"], "archive": parent["archive"],
                                           "sha256": parent["receipt"]["sha256"]}
    if pending["parent"] != expected:
        raise ValueError("Resume parent changed")
    if Path(pending["archive"]).name != pending["archive"]:
        raise ValueError("Invalid backup archive name")
    archive = folder / pending["archive"]
    if digest(archive) != pending["archive_sha256"]:
        raise ValueError("Pending archive checksum mismatch")
    restored = folder / "verified-payload/payload"
    manifest = json.loads((restored / "manifest.json").read_text())
    for key in manifest:
        if manifest[key] != pending[key]:
            raise ValueError("Pending archive manifest changed")
    for row in pending["sqlite_snapshots"].values():
        if digest(restored / row["path"]) != row["sha256"]:
            raise ValueError("Pending restored SQLite checksum mismatch")
    validate_archive_warnings((folder / "tar.log").read_text(), watched, plan, True)
    started = time.monotonic()
    receipt = mirror(archive)
    if receipt.get("desktop_verified") is not True or receipt["sha256"] != digest(archive):
        raise ValueError("Backup delivery is unverified")
    # Conservatively drop proofs for any DB changed since the archive inventory.
    watched = journal(0 if parent is None else parent["journal_sequence"])
    check_journal(watched, plan)
    if watched["instance"] != pending["journal_instance"]:
        raise ValueError("Resume journal changed during delivery")
    proofs = {raw: proof for raw, proof in pending["database_proofs"].items()
              if generation(raw) == proof["generation"] and not content_event(raw, watched)}
    result = {**pending, "receipt": receipt, "database_proofs": proofs, "passed": True,
              "delivery_resumed_without_recapture": True, "frozen_boundary_verified": False,
              "writer_fence": None, "cutover_authorized": False,
              "changes_during_capture": watched["changed"],
              "total_preparation_seconds": time.time() - pending["at"]}
    result["timings"] = {**pending["timings"], "resumed_delivery": time.monotonic() - started}
    metadata = folder / (archive.name + ".result.json")
    save(metadata, result)
    delivered = publish(metadata)
    if delivered.get("desktop_verified") is not True or delivered["sha256"] != digest(metadata):
        raise ValueError("Backup recovery metadata delivery is unverified")
    result["metadata_receipt"] = delivered
    exclusions.validate()
    save(folder / "result.json", result)
    save(root / "latest-result.json", result)
    return result


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
                        break
                if found is None:
                    raise ValueError("Missing backup manifest")
            # The archive's full SHA256 is already checked. Stop the header lookup
            # once found; recovery below still reads and validates the whole stream.
            decompressor.stdout.close()
            if decompressor.poll() is None:
                decompressor.terminate()
            decompressor.wait()
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


def configured_reader(plan_path, endpoint, parent=None):
    plan = json.loads(plan_path.read_text())
    if plan.get('move_coverage') or (plan_path.parent/'move-coverage.json').exists():
        from journal_compat import journal as covered_journal
        from subtree_recopy import RecopyJournal
        return RecopyJournal(lambda since: covered_journal(plan_path.parent, since, plan_path=plan_path), parent)
    return lambda since: request(endpoint, since)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    backup = commands.add_parser("capture")
    backup.add_argument("--plan", required=True, type=Path)
    backup.add_argument("--root", required=True, type=Path)
    backup.add_argument("--socket", required=True, type=Path)
    backup.add_argument("--parent", type=Path)
    backup.add_argument("--desktop-directory", required=True)
    backup.add_argument("--desktop-hostname")
    backup.add_argument("--desktop-host-key-alias")
    resume = commands.add_parser("resume-delivery")
    resume.add_argument("--plan", required=True, type=Path)
    resume.add_argument("--root", required=True, type=Path)
    resume.add_argument("--folder", required=True, type=Path)
    resume.add_argument("--socket", required=True, type=Path)
    resume.add_argument("--parent", type=Path)
    resume.add_argument("--desktop-directory", required=True)
    resume.add_argument("--desktop-hostname")
    resume.add_argument("--desktop-host-key-alias")
    restore = commands.add_parser("verify-restore")
    restore.add_argument("--result", required=True, type=Path)
    restore.add_argument("--destination", required=True, type=Path)
    restore.add_argument("--archive-directory", type=Path, help="Directory of archive copies fetched from Desktop")
    args = parser.parse_args()
    os.umask(0o077)
    if args.action in ("capture", "resume-delivery"):
        transport = DesktopTransport(args.root / "transport", hostname=args.desktop_hostname,
                                     host_key_alias=args.desktop_host_key_alias)
        mirror = lambda archive: transport.mirror(archive, args.desktop_directory)
        parent = json.loads(args.parent.read_text()) if args.parent else None
        reader = configured_reader(args.plan, args.socket, parent)
        if args.action == "resume-delivery":
            result = resume_delivery(json.loads(args.plan.read_text()), args.root, args.folder,
                                     reader, mirror, mirror, parent)
            print(json.dumps(result, indent=2))
            return
        plan = json.loads(args.plan.read_text())
        result = capture(plan, args.root, reader,
                         mirror, parent, mirror)
    else:
        result = restore_chain(json.loads(args.result.read_text()), args.destination, args.archive_directory)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
