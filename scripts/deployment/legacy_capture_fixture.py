"""TEST ONLY: pinned pre-stream capture to exercise existing archive recovery.

Source: PR149 49cf82d603b765b4ceaf5a8b4462f046e6181c0f. Production capture
never imports this module. Legacy fixtures are bounded to eight MiB and an
explicit test TMPDIR; preserve regression tests for retained old backups.
"""
import vk_rolling_backup as backup
from vk_rolling_backup import *

def legacy_capture(plan, root, journal, mirror, parent=None, publish=None, *, verify_fence=None):
    fixture = Path(os.environ["TMPDIR"]).resolve()
    if not Path(root).resolve().is_relative_to(fixture) or Path(root).resolve() == fixture:
        raise ValueError("Legacy fixture must stay in the owned test root")
    total = sum(p.stat().st_size for source in plan["sources"] for p in Path(source).rglob("*")
                if p.is_file() and not p.is_symlink())
    if total > 8 * 1024**2:
        raise ValueError("Legacy fixture exceeds eight MiB")
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
        parent_ref = None if parent is None else reference(parent)
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
            warnings = backup.validate_archive_warnings((folder / "tar.log").read_text(), watched, plan, verify_fence is None)
        with measured(timings, "archive_restore_verify"):
            # Verify every snapshot from the archive without keeping a second
            # extracted database tree on the SSD.
            verify_snapshot_archive(archive, snapshots, payload / "manifest.json")
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


