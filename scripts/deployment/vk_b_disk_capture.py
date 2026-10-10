"""Isolated B-disk snapshot extension of the exact PR229 capture driver.

The original reviewed module remains unchanged. This extension adds an explicit
verified B snapshot factory; all parent, journal, stream and fence checks remain.
Explicit fenced B-disk factories require stopped writers and the unchanged held
lease; otherwise the original guarded memory path remains unchanged.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tarfile
import threading
import time
import uuid

from vk_archive_stream import StreamingArchive
from vk_archive_store import Archive, reference
from vk_prep_common import digest, identity, measured, save, storage


MAX_SNAPSHOT_BYTES = 1024**3
MAX_METADATA_BYTES = 64 * 1024**2
MAX_MANIFEST_BYTES = 32 * 1024**2  # Retain the existing restore-reader bound.
MAX_WARNING_BYTES = 8 * 1024**2
MAX_CAPTURE_METADATA_BYTES = 256 * 1024**2


def memory_snapshot(source, maximum):
    """One consistent SQLite image at a time; no destination file or temp DB."""
    snapshot = sqlite3.connect(":memory:")
    try:
        snapshot.execute("PRAGMA temp_store=MEMORY")

        def progress(status, remaining, pages):
            if pages * page_size > maximum:
                raise ValueError("SQLite snapshot exceeds the configured memory bound")

        page_size = source.execute("PRAGMA page_size").fetchone()[0]
        if source.execute("PRAGMA page_count").fetchone()[0] * page_size > maximum:
            raise ValueError("SQLite snapshot exceeds the configured memory bound")
        source.backup(snapshot, pages=4096, progress=progress)
        if snapshot.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("SQLite snapshot integrity failed")
        image = snapshot.serialize()
        if len(image) > maximum:
            raise ValueError("SQLite snapshot exceeds the configured memory bound")
        return image
    finally:
        snapshot.close()


def source_members(output, file_list, log, online, validate, *, workspace=None):
    """GNU tar records Linux metadata; reframe those members into the same stream.

No sparse encoding is requested: the resulting ordinary member size is truthful.
PAX headers retain ACLs/xattrs/SELinux, numeric IDs, times and link information.
"""
    command = ["tar", "--atime-preserve=system", "--format=pax", "--numeric-owner", "--acls", "--xattrs",
               "--xattrs-include=*", "--selinux", *(["--ignore-failed-read"] if online else []),
               "-cf", "-", "-C", "/", "--no-recursion", "--null", "-T", str(file_list)]
    process = (workspace.producer if workspace else subprocess.Popen)(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    errors = []

    def warnings():
        size = 0
        try:
            with (workspace.open_new(log) if workspace else log.open("xb")) as sink:
                while block := process.stderr.read(65536):
                    size += len(block)
                    if size > MAX_WARNING_BYTES:
                        raise ValueError("Archive warning log exceeds metadata bound")
                    sink.write(block)
                sink.flush();os.fsync(sink.fileno())
            if workspace: workspace.seal(log)
        except BaseException as error:
            errors.append(error)
            if process.poll() is None:
                process.kill()

    reader = threading.Thread(target=warnings, daemon=True)
    reader.start()
    try:
        with tarfile.open(fileobj=process.stdout, mode="r|", bufsize=1024**2) as source:
            for member in source:
                # Preserve directory/link headers too; no new scope filtering.
                output.addfile(member, source.extractfile(member) if member.isfile() else None)
                # These are streaming copies, not random-access tar catalogs.
                # Keep no half-million-member header history on either side.
                source.members.clear(); output.members.clear()
        while process.stdout.read(1024**2):
            pass
        code = process.wait(timeout=60)
        reader.join(timeout=30)
        if reader.is_alive() or errors:
            raise ValueError("Could not retain complete archive warning evidence")
        if code not in ((0, 1) if online else (0,)):
            raise ValueError("Backup archive failed; inspect " + str(log))
        return validate(log.read_text())
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        reader.join(timeout=30)
        process.stdout.close()
        process.stderr.close()


def verify_remote_snapshots(result, snapshots, manifest):
    expected = {"payload/" + row["path"]: row["sha256"] for row in snapshots.values()}
    seen = set()
    with Archive(reference(result), desktop_only=True).contents() as archive:
        for member in archive:
            if member.name == "payload/manifest.json":
                if member.name in seen or not member.isfile() or member.size > MAX_MANIFEST_BYTES:
                    raise ValueError("Invalid streamed manifest")
                if json.load(archive.extractfile(member)) != manifest:
                    raise ValueError("Remote manifest differs from captured scope")
                seen.add(member.name)
            elif member.name in expected:
                if member.name in seen or not member.isfile():
                    raise ValueError("Duplicate or invalid snapshot archive member")
                with archive.extractfile(member) as stream:
                    if hashlib.file_digest(stream, "sha256").hexdigest() != expected[member.name]:
                        raise ValueError("Restored SQLite snapshot checksum mismatch")
                seen.add(member.name)
    if seen != set(expected) | {"payload/manifest.json"}:
        raise ValueError("Incomplete streamed archive verification")


def capture(plan, root, journal, mirror, parent=None, publish=None, *, verify_fence=None,
            max_snapshot_bytes=MAX_SNAPSHOT_BYTES, disk_snapshot=None, disk_inventory_root=None, fenced_disk_snapshot=None, workspace=None,
            nightly_selection=None):
    # Import the authoritative journal/scope rules without duplicating them.
    from vk_rolling_backup import (Exclusions, check_journal, content_event, generation,
                                   scan, validate_archive_warnings, verified_parent)
    from vk_candidate_direct_b import source_pins
    base_pins = source_pins()
    driver = {"reviewed_base_head": "754129c5fff55da2f5598d8c7beb4d4325587ead",
              "reviewed_base_pins": base_pins, "extension_sha256": digest(Path(__file__)),
              "operational_acceptance": False}
    root = workspace.checked_root(root) if workspace else storage(root)
    if any(root.is_relative_to(Path(p).resolve()) for p in plan["sources"]):
        raise ValueError("Backup staging must be outside watched source roots")
    if any(not Path(p).exists() for p in plan["sources"]):
        raise ValueError("Missing source roots require an explicit reconciled backup plan")
    if type(max_snapshot_bytes) is not int or max_snapshot_bytes <= 0:
        raise ValueError("A positive SQLite snapshot memory bound is required")
    timings, started = {}, time.monotonic()
    exclusions = Exclusions(plan)
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
    folder = root if workspace else root / ("checkpoint-" if parent is None else "delta-") / uuid.uuid4().hex
    if not workspace: folder.mkdir(parents=True, mode=0o700)
    if workspace and (parent is not None or verify_fence is not None):
        raise ValueError("Registered nightly workspace supports independent online capture only")
    def bounded_save(path, value):
        # Include atomic replacement scratch and the new local head. Existing
        # historical receipts are not silently deleted to satisfy this budget.
        data_size = len(json.dumps(value, indent=2, sort_keys=True).encode()) + 1
        used = sum(p.stat().st_blocks * 512 for p in folder.iterdir() if p.is_file()
                   and (not workspace or not p.name.endswith((".sqlite", ".tar.zst"))))
        if data_size > MAX_METADATA_BYTES or used + data_size + 8192 > MAX_CAPTURE_METADATA_BYTES:
            raise ValueError("Capture metadata exceeds its bounded local allowance")
        if workspace:
            workspace.save_json(path, value)
        else:
            save(path, value)

    bounded_save(folder / "direct-stream.json", {"schema": 1, "local_archive": False,
         "retry": "A failed stream requires a fresh capture; never concatenate or silently stage locally",
         "max_snapshot_bytes": max_snapshot_bytes, "metadata_file_limit": MAX_METADATA_BYTES,
         "capture_metadata_limit": MAX_CAPTURE_METADATA_BYTES})
    with measured(timings, "inventory"):
        if nightly_selection is not None:
            from vk_nightly_delta import strict_scan
            paths = strict_scan(plan["sources"], exclusions)
        else:
            paths = scan(plan["sources"], plan, exclusions) if parent is None else set(before["changed"])
        if parent is not None:
            paths.update(scan([p for p in paths if Path(p).is_dir()], plan, exclusions))
        paths = {p for p in paths if not exclusions(p)}
        absent = sorted(p for p in paths if not Path(p).exists() and not Path(p).is_symlink())
        files = sorted(paths - set(absent))
        if nightly_selection is not None:
            if workspace is None or parent is not None or verify_fence is not None:
                raise ValueError('nightly delta only supports registered online workspace')
            nightly_selection.inventory(files)
        required = {str(Path(p).resolve()) for p in
                    [*plan.get("sqlite_snapshots", []), *plan.get("critical_sqlite", [])]}
        databases = required | set(parent.get("databases", []) if parent else [])
        for raw in files:
            p = Path(raw)
            if p.is_file() and not p.is_symlink():
                with p.open("rb") as stream:
                    if stream.read(16) == b"SQLite format 3\0":
                        databases.add(str(p.resolve()))
        for raw in databases:
            if not any(Path(raw).is_relative_to(Path(p).resolve()) for p in plan["sources"]):
                raise ValueError("Database is outside journal coverage: " + raw)
    proofs = dict(parent.get("database_proofs", {})) if parent else {}
    readers, signatures, versions, snapshots = {}, {}, {}, {}
    reused, warnings = [], []
    manifest = None
    peak_snapshot = 0
    disk_proofs = {}
    disk_inventory = None
    disk_root = None
    if disk_inventory_root is not None:
        from vk_b_disk_snapshot import checked_mount
        disk_root = workspace.checked_root(disk_inventory_root) if workspace else checked_mount(disk_inventory_root)

    def stable_boundary():
        exclusions.validate()
        watched = journal(before["sequence"])
        check_journal(watched, plan)
        if watched["instance"] != before["instance"] or watched["sequence"] < before["sequence"]:
            raise ValueError("Final boundary journal identity changed")
        shm = {p + "-shm" for p in databases}
        db_files = {p + suffix for p in databases for suffix in ("", "-wal")}
        changed = [p for p in watched["changed"] if str(Path(p).resolve()) not in shm
                   and not (p in db_files and watched.get("events", {}).get(p) == 0x8)]
        generations = {p: {"before": value, "after": generation(p)} for p, value in signatures.items()
                       if generation(p) != value}
        logical = [p for p, c in readers.items() if c.execute("PRAGMA data_version").fetchone()[0] != versions[p]]
        if changed or generations or logical:
            bounded_save(folder / "boundary-instability.json", {"changed_paths": changed,
                "database_generations": generations, "logical_database_changes": logical,
                "sequence_before": before["sequence"], "sequence_after": watched["sequence"]})
            raise ValueError("Protected data changed during final boundary capture")
        if verify_fence() != fence_before:
            raise ValueError("Final boundary writer fence changed")

    def produce(stream):
        nonlocal manifest, peak_snapshot, disk_inventory
        with tarfile.open(fileobj=stream, mode="w|", format=tarfile.PAX_FORMAT,
                          bufsize=1024**2, copybufsize=1024**2) as archive:
            with measured(timings, "sqlite_snapshot_and_integrity"):
                for raw in sorted(databases):
                    path = Path(raw)
                    if not path.exists():
                        proofs.pop(raw, None)
                        if parent is None or raw in required:
                            raise ValueError("Required SQLite database is missing: " + raw)
                        continue
                    signatures[raw] = generation(raw)
                    previous = proofs.get(raw)
                    if previous and previous.get("generation") == signatures[raw] and not content_event(raw, before):
                        reused.append(raw)
                        continue
                    # Never immutable=1 on live data. A normal read transaction
                    # plus SQLite backup API includes WAL state consistently.
                    private = verify_fence is not None and not any(
                        os.path.lexists(raw + suffix) for suffix in ("-wal", "-journal"))
                    disk_image = None
                    if verify_fence is not None and fenced_disk_snapshot is not None and not private:
                        raise ValueError('Final B-disk source requires checkpointed, stopped databases')
                    if private and fenced_disk_snapshot is not None:
                        disk_image = fenced_disk_snapshot(raw)
                        if (disk_image.get('source') != raw
                                or disk_image.get('writer_fenced') is not True
                                or disk_image.get('consistent_held_fence_raw_image') is not True
                                or disk_image.get('writer_fence') != fence_before
                                or disk_image.get('physical_b_verified') is not True
                                or disk_image.get('integrity') != 'ok'
                                or disk_image.get('local_snapshot_payload_bytes') != 0):
                            raise ValueError('Fenced disk image lacks actual bound writer/readback proof')
                        disk_proofs[raw] = {k: v for k, v in disk_image.items() if k != 'mount_root'}
                        image = None
                        connection = None
                    else:
                        if private:
                            # Fenced/checkpointed files may be copied into RAM without
                            # opening live SQLite bookkeeping files. Never immutable
                            # live reads or a raw online copy of a WAL database.
                            if path.stat().st_size > max_snapshot_bytes:
                                raise ValueError("SQLite snapshot exceeds the configured memory bound")
                            image = path.read_bytes()
                            if (len(image) > max_snapshot_bytes or generation(raw) != signatures[raw]
                                    or any(os.path.lexists(raw + s) for s in ("-wal", "-journal"))):
                                raise ValueError("Fenced database changed while copying: " + raw)
                            connection = sqlite3.connect(":memory:", check_same_thread=False)
                            # deserialize cannot open a WAL-mode image in RAM. For
                            # integrity validation ONLY, switch the private header
                            # to rollback mode. Archive the unchanged fenced bytes.
                            validation = image
                            if image[:16] == b"SQLite format 3\0" and image[18:20] == b"\x02\x02":
                                validation = image[:18] + b"\x01\x01" + image[20:]
                            connection.deserialize(validation)
                            del validation
                        else:
                            connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, check_same_thread=False)
                        readers[raw] = connection
                        versions[raw] = connection.execute("PRAGMA data_version").fetchone()[0]
                        connection.execute("BEGIN")
                        connection.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
                        if private:
                            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                                raise ValueError("SQLite snapshot integrity failed")
                        else:
                            page_bytes = (connection.execute("PRAGMA page_count").fetchone()[0]
                                          * connection.execute("PRAGMA page_size").fetchone()[0])
                            if page_bytes > max_snapshot_bytes and disk_snapshot is not None:
                                if verify_fence is not None:
                                    raise ValueError("Large fenced B-disk images require a reviewed final-boundary adapter")
                                # The factory owns an independent normal SQLite read
                                # transaction and verifies physical B, not local SSD.
                                connection.rollback()
                                disk_image = disk_snapshot(raw)
                                if (disk_image.get('source') != raw
                                        or disk_image.get('backup_api_consistent_image') is not True
                                        or disk_image.get('online_preparation_only') is not True
                                        or disk_image.get('writer_fenced') is not False
                                        or disk_image.get('physical_b_verified') is not True
                                        or disk_image.get('integrity') != 'ok'
                                        or disk_image.get('local_snapshot_payload_bytes') != 0):
                                    raise ValueError('B-disk snapshot factory returned unverified evidence')
                                disk_proofs[raw] = {k: v for k, v in disk_image.items() if k != 'mount_root'}
                                image = None
                            else:
                                image = memory_snapshot(connection, max_snapshot_bytes)
                        connection.rollback()
                    image_bytes = disk_image['bytes'] if disk_image else len(image)
                    peak_snapshot = max(peak_snapshot, 0 if disk_image else image_bytes)
                    relative = "sqlite/" + hashlib.sha256(raw.encode()).hexdigest() + ".sqlite"
                    member = archive.gettarinfo(raw, "payload/" + relative)
                    member.type, member.linkname, member.size = tarfile.REGTYPE, "", image_bytes
                    for name in os.listxattr(raw):
                        member.pax_headers["SCHILY.xattr." + name] = os.getxattr(raw, name).decode("utf-8", "surrogateescape")
                    # Bind integer nanosecond source times, not float rounding.
                    st = path.stat()
                    times = disk_image.get("source_metadata_before", {}) if disk_image else {}
                    from decimal import Decimal
                    member.pax_headers['mtime'] = str(Decimal(times.get("mtime_ns", st.st_mtime_ns)) / 10**9)
                    member.pax_headers['atime'] = str(Decimal(times.get("atime_ns", st.st_atime_ns)) / 10**9)
                    checksum = disk_image['sha256'] if disk_image else hashlib.sha256(image).hexdigest()
                    if disk_image:
                        from vk_b_disk_snapshot import checked_mount
                        mounted = workspace.checked_root(disk_image['mount_root']) if workspace else checked_mount(disk_image['mount_root'])
                        if (Path(disk_image['snapshot']).name != disk_image['snapshot']
                                or not disk_image['snapshot'].startswith('sqlite-consistent-')):
                            raise ValueError('Unsafe disk snapshot selector')
                        with (mounted / disk_image['snapshot']).open('rb') as payload:
                            if nightly_selection is None:
                                if hashlib.file_digest(payload, 'sha256').hexdigest() != checksum:
                                    raise ValueError('B snapshot changed before archiving')
                                payload.seek(0)
                            archive.addfile(member, payload)
                    else:
                        with io.BytesIO(image) as payload:
                            archive.addfile(member, payload)
                    del image
                    snapshots[raw] = {"path": relative, "sha256": checksum}
                    proofs[raw] = {"generation": signatures[raw], "snapshot_sha256": checksum}
                    if private and connection is not None:
                        # Do not retain every in-memory database until EOF.
                        connection.close()
                        readers.pop(raw)
            omitted = {p + suffix for p in databases for suffix in ("", "-wal", "-shm")}
            file_list = (disk_root / ('capture-paths-' + uuid.uuid4().hex + '.nul')
                         if disk_root else folder / "paths.nul")
            inventory_limit = 256 * 1024**2 if disk_root else MAX_METADATA_BYTES
            list_hash = hashlib.sha256()
            path_count = 0
            with (workspace.open_new(file_list) if workspace else file_list.open("xb")) as listing:
                for raw in files:
                    if Path(raw).is_symlink() or str(Path(raw).resolve()) not in omitted:
                        if nightly_selection is not None and not nightly_selection.include(raw):
                            continue
                        item = os.fsencode(raw.lstrip("/")) + b"\0"
                        if listing.tell() + len(item) > inventory_limit:
                            raise ValueError("Backup path inventory exceeds metadata bound")
                        listing.write(item)
                        list_hash.update(item)
                        path_count += 1
                listing.flush()
                os.fsync(listing.fileno())
            if workspace: workspace.seal(file_list)
            if disk_root:
                from vk_b_disk_snapshot import checked_mount
                workspace.checked_root(disk_root) if workspace else checked_mount(disk_root)
                with file_list.open('rb') as stream:
                    if hashlib.file_digest(stream, 'sha256').hexdigest() != list_hash.hexdigest():
                        raise ValueError('B path inventory differs from generated source scope')
                disk_inventory = {'name': file_list.name, 'sha256': list_hash.hexdigest(),
                                  'bytes': file_list.stat().st_size, 'paths': path_count,
                                  'storage': 'exact existing Desktop B mount',
                                  'limit_bytes': inventory_limit, 'local_payload_bytes': 0}
            from vk_change_journal import scope
            manifest = {"schema": 1, "at": time.time(), "capture_driver": driver,
                        "large_b_disk_snapshots": disk_proofs, "b_path_inventory": disk_inventory, "scope_sha256": identity(scope(plan)),
                        "plan_sha256": identity(plan), "exclusion_targets": list(map(str, exclusions.roots)),
                        "journal_instance": before["instance"], "journal_sequence": before["sequence"],
                        "parent": None if parent is None else reference(parent), "sqlite_snapshots": snapshots,
                        "absent_paths": absent, "online_preparation": verify_fence is None,
                        "production_boundary": False, "frozen_boundary_requested": verify_fence is not None}
            if "recopy_baseline" in before:
                manifest["recopy_baseline"] = before["recopy_baseline"]
            data = json.dumps(manifest, sort_keys=True).encode()
            if len(data) > MAX_MANIFEST_BYTES:
                raise ValueError("Backup manifest exceeds metadata bound")
            bounded_save(folder / "manifest.json", manifest)
            member = tarfile.TarInfo("payload/manifest.json")
            member.size, member.mode = len(data), 0o600
            archive.addfile(member, io.BytesIO(data))

            def validate(log):
                watched = journal(before["sequence"])
                check_journal(watched, plan)
                if watched["instance"] != before["instance"]:
                    raise ValueError("Journal changed during archive")
                return validate_archive_warnings(log, watched, plan, verify_fence is None)

            warnings.extend(source_members(archive, file_list, folder / "tar.log", verify_fence is None, validate, workspace=workspace))
            if disk_root:
                workspace.checked_root(disk_root) if workspace else checked_mount(disk_root)
                with file_list.open('rb') as stream:
                    if hashlib.file_digest(stream, 'sha256').hexdigest() != list_hash.hexdigest():
                        raise ValueError('B source inventory changed while archiving')
            if verify_fence is not None:
                stable_boundary()
            exclusions.validate()

    archive = StreamingArchive(folder, folder.parent.name + "-" + folder.name + ".tar.zst", produce)
    try:
        with measured(timings, "stream_and_desktop_readback"):
            receipt = mirror(archive)
            if (manifest is None or not archive.sha256 or receipt.get("desktop_verified") is not True
                    or receipt.get("sha256") != archive.sha256 or receipt.get("bytes") != archive.bytes
                    or receipt.get("name") != archive.name or receipt.get("direct_stream") is not True):
                raise ValueError("Direct Desktop backup delivery is unverified; no local fallback")
        partial_result = {"folder": str(folder), "archive": archive.name, "receipt": receipt}
        with measured(timings, "remote_archive_snapshot_verification"):
            if nightly_selection is None:
                verify_remote_snapshots(partial_result, snapshots, manifest)
            # Registered nightly inputs already passed native integrity/hash.
            # NightlyArchiveProvider subsequently verifies the entire sealed
            # archive, every SQL payload/hash and its embedded manifest together
            # before any generation can publish. Avoid a redundant full replay.
        after = journal(before["sequence"])
        check_journal(after, plan)
        if after["instance"] != before["instance"] or after["sequence"] < before["sequence"]:
            raise ValueError("Journal changed during backup; refuse to advance the checkpoint")
        if nightly_selection is not None: nightly_selection.finish(after)
        for raw in signatures:
            if (generation(raw) != signatures[raw] or content_event(raw, after)
                    or raw in readers and readers[raw].execute("PRAGMA data_version").fetchone()[0] != versions[raw]):
                proofs.pop(raw, None)
        if verify_fence is not None:
            stable_boundary()
        exclusions.validate()
        result = {**manifest, **partial_result, "database_proofs": proofs, "databases": sorted(databases),
                  "reused_sqlite_snapshots": reused, "copied_files": len(files), "changes_during_capture": after["changed"],
                  "timings": timings, "total_preparation_seconds": time.monotonic() - started, "passed": True,
                  "cutover_authorized": False, "frozen_boundary_verified": verify_fence is not None,
                  "writer_fence": fence_before, "online_archive_warnings_recaptured_by_next_delta": warnings,
                  "direct_stream": True, "local_archive_bytes": 0, "local_snapshot_bytes": 0,
                  "largest_serialized_snapshot_bytes": peak_snapshot,
                  "snapshot_memory_bound_bytes": max_snapshot_bytes,
                  "capture_metadata_bound_bytes": MAX_CAPTURE_METADATA_BYTES,
                  "local_metadata_bytes": sum(p.stat().st_size for p in folder.iterdir() if p.is_file())}
        if publish is not None:
            metadata = folder / (archive.name + ".result.json")
            bounded_save(metadata, {**result, "frozen_boundary_verified": False, "handover_acceptance_pending": verify_fence is not None})
            delivered = publish(metadata)
            if delivered.get("desktop_verified") is not True or delivered["sha256"] != digest(metadata):
                raise ValueError("Backup recovery metadata delivery is unverified")
            result["metadata_receipt"] = delivered
        if verify_fence is not None:
            stable_boundary()
        exclusions.validate()
        bounded_save(folder / "result.json", result)
        bounded_save(root / "latest-result.json", result)
        return result
    finally:
        for connection in readers.values():
            connection.close()
