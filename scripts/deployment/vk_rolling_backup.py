#!/usr/bin/env python3
"""Verified online checkpoint/deltas. Never freezes services or restores production."""

import argparse
from contextlib import closing
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
from vk_archive_store import Archive, chain, reference


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
    from vk_archive_stream import StreamingArchive
    folder = archive.parent if isinstance(archive, StreamingArchive) else Path(archive).parent
    return DesktopTransport(folder / "transport").mirror(archive, destination)


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
    # A verified Desktop receipt is authoritative; no parent archive download.
    Archive(reference(parent), desktop_only=True).verify()
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


def capture(plan, root, journal, mirror, parent=None, publish=None, *, verify_fence=None,
            max_snapshot_bytes=1024**3):
    """New captures stream directly to Desktop; no archive/snapshot SSD fallback."""
    from vk_direct_capture import capture as direct_capture
    return direct_capture(plan, root, journal, mirror, parent, publish,
                          verify_fence=verify_fence, max_snapshot_bytes=max_snapshot_bytes)


def recover_online_checkpoint(plan, root, folder, journal):
    """Validate a fully written, unpublished archive before resuming delivery.

    No database reuse proof is reconstructed. The next delta snapshots every DB.
    This cannot accept a changed scope, lost journal or a frozen capture.
    """
    root, folder = storage(root), storage(folder)
    if folder.parent.parent != root or any((folder / name).exists() for name in
            ('result.json', 'pending-delivery.json')):
        raise ValueError('Recovery requires an unpublished checkpoint')
    manifest_path = folder / 'payload/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if (manifest['parent'] is not None or not manifest['online_preparation']
            or manifest['frozen_boundary_requested'] or manifest['plan_sha256'] != identity(plan)
            or manifest['scope_sha256'] != identity(scope(plan))):
        raise ValueError('Recovery requires the original full online checkpoint plan')
    exclusions = Exclusions(plan)
    if manifest['exclusion_targets'] != list(map(str, exclusions.roots)):
        raise ValueError('Recovery exclusion targets changed')
    watched = journal(manifest['journal_sequence'])
    check_journal(watched, plan)
    if watched['instance'] != manifest['journal_instance'] or watched['sequence'] < manifest['journal_sequence']:
        raise ValueError('Recovery journal continuity lost')
    validate_archive_warnings((folder / 'tar.log').read_text(), watched, plan, True)
    archives = list(folder.glob('*.tar.zst'))
    if len(archives) != 1:
        raise ValueError('Recovery requires exactly one complete archive')
    archive = archives[0]
    verify_snapshot_archive(archive, manifest['sqlite_snapshots'], manifest_path)
    exclusions.validate()
    pending = {**manifest, 'folder': str(folder), 'archive': archive.name,
               'archive_sha256': digest(archive), 'database_proofs': {},
               'databases': sorted(manifest['sqlite_snapshots']),
               'copied_files': len((folder / 'paths.nul').read_bytes().split(b'\0')) - 1,
               'timings': {}, 'passed': False, 'recovered_online_archive': True}
    save(folder / 'pending-delivery.json', pending)
    return pending


def resume_delivery(plan, root, folder, journal, mirror, publish, parent=None):
    if (Path(folder) / 'direct-stream.json').exists():
        raise ValueError('Direct streams are never regenerated into a partial archive; start a fresh capture')
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
    expected = None if parent is None else reference(parent)
    # Legacy pending deliveries have only the original three parent fields.
    actual = pending["parent"]
    if ((actual is None) != (expected is None)
            or (actual is not None and any(expected.get(k) != v for k, v in actual.items()))
            or (actual is not None and not all(k in actual for k in ("folder", "archive", "sha256")))):
        raise ValueError("Resume parent changed")
    if Path(pending["archive"]).name != pending["archive"]:
        raise ValueError("Invalid backup archive name")
    archive = folder / pending["archive"]
    if digest(archive) != pending["archive_sha256"]:
        raise ValueError("Pending archive checksum mismatch")
    restored = folder / "payload"
    manifest = json.loads((restored / "manifest.json").read_text())
    for key in manifest:
        if manifest[key] != pending[key]:
            raise ValueError("Pending archive manifest changed")
    for row in pending["sqlite_snapshots"].values():
        if digest(restored / row["path"]) != row["sha256"]:
            raise ValueError("Pending restored SQLite checksum mismatch")
    verify_snapshot_archive(archive, pending["sqlite_snapshots"], restored / "manifest.json")
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


def restore_room(destination, additional=0):
    fs = os.statvfs(destination)
    if fs.f_bavail * fs.f_frsize - additional < 2 * 1024**3:
        raise ValueError('Restore would breach the two-GiB free-space floor')


def restore_copy(source, target, destination):
    while block := source.read(1024**2):
        restore_room(destination, len(block))
        target.write(block)


def detach_restore_alias(target):
    """Do not overwrite an untouched name through a prior archive's hardlink."""
    if target.is_symlink():
        raise ValueError('Refusing a symlink restore destination')
    if target.is_file() and target.stat().st_nlink > 1:
        target.unlink()


def restore_chain(result, destination, archive_directory=None, *, desktop_only=True,
                  retire_verified_snapshots=False):
    destination = storage(destination)
    backup_root = Path(result["folder"]).parent.parent.resolve()
    if not destination.is_relative_to(backup_root):
        raise ValueError("Restore verification must stay within the isolated backup task directory")
    if destination.exists():
        raise ValueError("Restore verification requires a new empty isolated destination")
    destination.mkdir(parents=True, mode=0o700)
    restore_room(destination)
    archives = chain(result, archive_directory, desktop_only=desktop_only)
    links, directory_modes, retired = {}, {}, []
    for archive in reversed(archives):
        manifest, sqlite_payloads = None, {}
        with archive.contents() as tar:
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
                            restore_copy(tar.extractfile(member), stream, destination)
                        target.chmod(member.mode)
                        sqlite_payloads[str(name.relative_to("payload"))] = target
                    continue
                target = destination / "files" / name
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    directory_modes[str(target)] = member.mode
                elif member.isfile():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    detach_restore_alias(target)
                    with target.open("wb") as stream:
                        restore_copy(tar.extractfile(member), stream, destination)
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
            restore_room(destination, payload.stat().st_size)
            detach_restore_alias(target)
            shutil.copy2(payload, target)
            links.pop(str(name), None)
            with closing(sqlite3.connect(target.as_uri() + "?mode=ro", uri=True)) as connection:
                if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("Restored database integrity mismatch")
        if retire_verified_snapshots:
            # Full compressed-stream verification and every database assertion
            # above have completed. Only these newly created private duplicates
            # are disposable; restored files, metadata and originals remain.
            copies = {}
            for row in manifest['sqlite_snapshots'].values():
                payload = sqlite_payloads[row['path']]
                if (payload.is_symlink() or payload.stat().st_nlink != 1
                        or not payload.resolve().is_relative_to(destination / 'snapshots' / archive.stem)
                        or digest(payload) != row['sha256']):
                    raise ValueError('Verified private restore snapshot changed')
                copies[str(payload)] = {'sha256': row['sha256'], 'bytes': payload.stat().st_size}
            proof = {'archive': archive.key, 'archive_sha256': archive.sha256, 'files': copies,
                     'full_stream_verified': True, 'database_integrity_passed': True,
                     'connections_closed': True, 'original_archive_removed': False}
            save(destination / 'verified-snapshot-retirement' / (archive.stem + '.json'), proof)
            for raw in copies:
                Path(raw).unlink()
            retired.extend(copies)
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
            "private_snapshot_copies_retired": retired,
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
    backup.add_argument("--max-snapshot-bytes", type=int, default=1024**3,
                        help="Maximum single SQLite RAM snapshot; exceeding it fails, never stages on SSD")
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
    restore.add_argument("--desktop-only", action="store_true", default=True,
                         help="Required provider: Desktop; local archive override is rejected")
    restore.add_argument('--retire-verified-snapshots', action='store_true',
                         help='Retire only private duplicate snapshots after each archive passes all checks')
    audit = commands.add_parser("audit-chain", help="Read and verify the chain without extracting payloads")
    audit.add_argument("--result", required=True, type=Path)
    audit.add_argument("--desktop-only", action="store_true", default=True)
    for command in (restore, audit):
        command.add_argument('--desktop-hostname')
        command.add_argument('--desktop-host-key-alias')
    args = parser.parse_args()
    from vk_archive_store import configure_transport
    configure_transport(args.desktop_hostname, args.desktop_host_key_alias)
    os.umask(0o077)
    if args.action in ("capture", "resume-delivery"):
        transport = DesktopTransport(args.root / "transport", hostname=args.desktop_hostname,
                                     host_key_alias=args.desktop_host_key_alias)
        mirror = lambda archive: transport.mirror(archive, args.desktop_directory)
        parent = json.loads(args.parent.read_text()) if args.parent else None
        if parent is not None:
            Archive(reference(parent), desktop_only=True)
        reader = configured_reader(args.plan, args.socket, parent)
        if args.action == "resume-delivery":
            result = resume_delivery(json.loads(args.plan.read_text()), args.root, args.folder,
                                     reader, mirror, mirror, parent)
            print(json.dumps(result, indent=2))
            return
        plan = json.loads(args.plan.read_text())
        result = capture(plan, args.root, reader,
                         mirror, parent, mirror, max_snapshot_bytes=args.max_snapshot_bytes)
    elif args.action == "audit-chain":
        archives = chain(json.loads(args.result.read_text()), desktop_only=args.desktop_only)
        result = {"passed": True, "archives": len(archives),
                  "sources": [a.key for a in archives], "payloads_extracted": False}
    else:
        result = restore_chain(json.loads(args.result.read_text()), args.destination,
                               args.archive_directory, desktop_only=args.desktop_only,
                               retire_verified_snapshots=args.retire_verified_snapshots)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
