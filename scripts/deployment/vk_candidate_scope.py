"""Read-only configured dependency accounting; no payload capture or scope approval.

Only allowlisted environment paths and SQL path columns are read. The private
receipt contains paths, never credentials, prompts, titles or transcript bodies.
The public summary contains counts and receipt hashes. Missing paths/old-plan
coverage gaps are blockers, not inferred retirement or a reduced backup scope.
"""
import argparse
from collections import Counter
from functools import lru_cache
import hashlib
import json
import os
import re
from pathlib import Path
import sqlite3

PATH_KEYS = (
    "HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "CODEX_HOME", "VK_FRONTEND_DIST_DIR",
    "VK_CAPACITY_STATE_DIR", "VK_CAPACITY_TOKEN_FILE", "VK_CODEX_ROUTING_MODULE",
    "VK_ROUTING_EVENTS_FILE", "CU_CODEX_HOME", "CU_VK_DATABASE", "CU_VK_TOKEN_FILE",
    "CU_USAGE_CACHE_DIR", "CU_ROUTING_EVENTS_FILE", "CU_TELEMETRY_DB", "CU_API_PRICING_FILE",
    "CU_APP_USAGE_FILE", "CU_DESKTOP_CACHE_HOME", "CU_HOME",
)


def bounded_text(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError("path metadata exceeds bounded read")
    return raw.decode()


def process_paths(pid):
    proc = Path("/proc") / str(int(pid))
    before = bounded_text(proc / "stat").rsplit(")", 1)[1].split()[19]
    # Select keys in-process. Do not persist/dump the original environ.
    raw = (proc / "environ").read_bytes()
    selected = {}
    for entry in raw.split(b"\0"):
        key, sep, value = entry.partition(b"=")
        key = key.decode(errors="replace")
        if sep and key in PATH_KEYS:
            path = value.decode()
            if not path.startswith("/"):
                raise ValueError("configured dependency is not absolute")
            selected[key] = path
        if key == "VK_CAPACITY_BUILD_ROOTS":
            selected[key] = json.loads(value)
        if key == "CU_SCAN_ROOTS":
            selected[key] = [p for p in value.decode().split(":") if p]
            if not all(p.startswith("/") for p in selected[key]):
                raise ValueError("CU scan root requires absolute binding")
        if key == "CU_DISCOVER_ALL":
            selected[key] = value.decode() == "1"
    identity = {"pid": int(pid), "start_ticks": before, "cwd": os.readlink(proc / "cwd"),
                "exe": os.readlink(proc / "exe"), "paths": selected}
    after = bounded_text(proc / "stat").rsplit(")", 1)[1].split()[19]
    if before != after:
        raise ValueError("process identity changed during read")
    return identity


def query_paths(database, queries):
    """Use live read-only WAL semantics. These rows are NOT a consistent backup."""
    result = {}
    with sqlite3.connect(Path(database).as_uri() + "?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        for label, query in queries.items():
            result[label] = db.execute(query).fetchall()
        db.rollback()
    return result


def git_dependencies(root):
    """Read only Git pointer files; never run scanners/hooks/Git maintenance."""
    root = Path(root)
    marker = root / ".git"
    if not marker.exists():
        return []
    if marker.is_dir():
        directory = marker.resolve()
    else:
        text = bounded_text(marker).strip()
        if not text.startswith("gitdir: "):
            raise ValueError("unrecognized worktree Git pointer")
        directory = (root / text[8:]).resolve()
    result = [(str(directory), "git-registration")]
    common_pointer = directory / "commondir"
    common = (directory / bounded_text(common_pointer).strip()).resolve() if common_pointer.exists() else directory
    result.append((str(common), "git-common-objects"))
    seen, todo = set(), [common / "objects"]
    while todo:
        objects = todo.pop().resolve()
        if objects in seen:
            continue
        if len(seen) >= 128:
            raise ValueError("unbounded Git object alternate closure")
        seen.add(objects)
        result.append((str(objects), "git-object-store"))
        alternate = objects / "info" / "alternates"
        if alternate.exists():
            for line in bounded_text(alternate).splitlines():
                if line.startswith('"') or not line:
                    raise ValueError("quoted/empty alternate requires explicit interpretation")
                todo.append(objects / line)
    return result


def local_path_overrides(release, inherited):
    """Match CU's source loader for allowlisted PATH keys only; discard other values."""
    path = Path(release) / ".env.local"
    result = {}
    if not path.exists():
        return result
    for line in bounded_text(path).splitlines():
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line.strip())
        if not match or match[1] not in PATH_KEYS + ("CU_SCAN_ROOTS", "CU_DISCOVER_ALL") or match[1] in inherited:
            continue
        value = match[2].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "\'"):
            value = value[1:-1]
        if match[1] == "CU_SCAN_ROOTS":
            value = [p for p in value.split(":") if p]
            if not all(p.startswith("/") for p in value):
                raise ValueError("CU local scan root needs absolute binding")
        elif match[1] == "CU_DISCOVER_ALL":
            value = value == "1"
        elif not value.startswith("/"):
            raise ValueError("CU local configured path requires explicit absolute binding")
        result[match[1]] = value
    return result


def collect(vk_pid, cu_pid, plan_path):
    identities = {"vk": process_paths(vk_pid), "cu": process_paths(cu_pid)}
    plan_bytes = Path(plan_path).read_bytes()
    plan = json.loads(plan_bytes)
    baseline = plan["sources"]
    exclusions = plan.get("excluded_rebuildable_directories", [])
    if not baseline or not all(isinstance(x, str) and x.startswith("/") for x in baseline):
        raise ValueError("invalid whole-state baseline")
    vk, cu = identities["vk"]["paths"], identities["cu"]["paths"]
    cu_release = Path(identities["cu"]["exe"]).parent if identities["cu"]["cwd"] == "/" else Path(identities["cu"]["cwd"])
    overrides = local_path_overrides(cu_release, cu)
    entries = {}
    unresolved_relative = []

    def add(path, reason):
        if not isinstance(path, str) or not path.startswith("/"):
            raise ValueError("relative configured dependency needs explicit base")
        entries.setdefault(path, set()).add(reason)

    for name, identity in identities.items():
        add(identity["cwd"], name + "-working-directory-context")
        add(identity["exe"], name + "-release-artifact")
        for key, value in identity["paths"].items():
            if key in ("HOME", "CU_HOME", "CU_DISCOVER_ALL"):
                continue  # HOME is namespace context, not authorization to clone the entire host.
            if key in ("VK_CAPACITY_BUILD_ROOTS", "CU_SCAN_ROOTS"):
                if not isinstance(value, list) or not all(isinstance(p, str) and p.startswith("/") for p in value):
                    raise ValueError("invalid build-root configuration")
                for p in value:
                    add(p, "configured-build-write-root-needs-explicit-payload-policy" if key == "VK_CAPACITY_BUILD_ROOTS"
                        else "cu-configured-native-scan-root")
            else:
                add(value, name + "-" + key)
    for key, path in overrides.items():
        if key == "CU_SCAN_ROOTS":
            for p in path:
                add(p, "cu-file-loaded-scan-root")
        elif key not in ("CU_DISCOVER_ALL", "CU_HOME"):
            add(path, "cu-file-loaded-" + key)
    effective_cu = {**overrides, **cu}

    xdg = Path(vk["XDG_DATA_HOME"])
    runtime = xdg / "vibe-kanban"
    configuration = json.loads((runtime / "config.json").read_text())
    add(str(runtime), "whole-current-runtime-including-unclassified-internal-history")
    workspace = configuration.get("workspace_dir")
    if not workspace:
        raise ValueError("workspace directory is not explicitly configured")
    add(workspace, "configured-workspace-root-including-dirty-untracked-attachments")
    database = runtime / "db.v2.sqlite"
    add(str(database), "required-current-database")
    cache = Path(vk.get("XDG_CACHE_HOME", str(Path(vk["HOME"]) / ".cache"))) / "utils"
    for p in (cache / "attachments", cache / "images"):
        add(str(p), "attachment-primary-or-legacy-cache")
    rows = query_paths(database, {
        "repositories": "SELECT path FROM repos",
        "workspaces": "SELECT container_ref, archived, worktree_deleted FROM workspaces WHERE container_ref IS NOT NULL",
        "sessions": "SELECT agent_working_dir FROM sessions WHERE agent_working_dir IS NOT NULL",
        "attachments": "SELECT file_path FROM attachments",
    })
    git_roots = set()
    for (path,) in rows["repositories"]:
        add(path, "registered-repository-no-retirement-inferred")
        git_roots.add(path)
    for path, archived, deleted in rows["workspaces"]:
        if path and path.startswith("/"):
            add(path, "recorded-worktree-deleted-or-archived" if archived or deleted else "active-recorded-worktree")
            git_roots.add(path)
    relative_sessions = 0
    for (path,) in rows["sessions"]:
        if path and path.startswith("/"):
            add(path, "absolute-session-working-directory")
        elif path:
            relative_sessions += 1
    for (path,) in rows["attachments"]:
        if path.startswith("/"):
            add(path, "absolute-attachment-reference")
        else:
            # Both locations accounted; existence alone cannot prove content.
            add(str(cache / "attachments" / path), "relative-attachment-reference")
            add(str(cache / "images" / path), "relative-attachment-legacy-alternative")
    cu_home = Path(effective_cu.get("CU_HOME", "/home/mcp"))
    native_homes = {vk["CODEX_HOME"], cu["CU_CODEX_HOME"]}
    for p in [*effective_cu.get("CU_SCAN_ROOTS", []), str(cu_home / ".codex"),
              effective_cu.get("CU_DESKTOP_CACHE_HOME", str(cu_home / ".cache/codexusage/desktop-cli")),
              str(cu_home / ".local/share/vibe-kanban/codex-home")]:
        add(p, "cu-source-default-or-configured-scan-root")
        if Path(p).exists():
            native_homes.add(p)
    native_counts = {}
    for home in sorted(native_homes):
        index = Path(home) / "state_5.sqlite"
        add(home, "whole-active-native-home-including-unclassified-historical-material")
        native = query_paths(index, {"threads": "SELECT rollout_path, cwd FROM threads"})["threads"] if index.exists() else []
        native_counts[home] = len(native)
        for rollout, cwd in native:
            if rollout and rollout.startswith("/"):
                add(rollout, "native-thread-rollout-reference")
            elif rollout:
                unresolved_relative.append({"home": home, "path": rollout, "kind": "native-rollout-relative-base-unproven"})
            if cwd and cwd.startswith("/"):
                add(cwd, "native-thread-working-directory")
                git_roots.add(cwd)
        for p in sorted(Path(home).glob("*.sqlite")):
            if p.name.startswith("logs_"):
                add(str(p), "configured-native-log-database-no-rebuildability-assumed")
            else:
                add(str(p), "required-current-native-database")
    # Source-bound defaults of this actual CU release; raw .env contents are never read.
    for name in ("routing-usage.sqlite", "capacity-audit.sqlite", "state.json"):
        add("/mnt/vk-storage/codexusage-android/monitor/" + name, "cu-current-source-monitor-dependency")
    errors = []
    for path in sorted(git_roots):
        try:
            for dep, reason in git_dependencies(path):
                add(dep, reason)
        except (OSError, ValueError) as error:
            errors.append({"path": path, "error_type": type(error).__name__})
    # Add resolved backing paths separately, preserving each original selector/link.
    for path in list(entries):
        if Path(path).is_symlink():
            add(str(Path(path).resolve()), "configured-or-recorded-symlink-backing")
    normalized = []
    baseline_paths = [(b, Path(b), Path(b).resolve()) for b in baseline]

    @lru_cache(maxsize=None)
    def resolve(path):
        # Cache each original path; discovery never walks/copies its payload.
        return Path(path).resolve()

    for path, reasons in sorted(entries.items()):
        p = Path(path)
        lexical = [b for b, prefix, _ in baseline_paths if p == prefix or p.is_relative_to(prefix)]
        resolved = resolve(path)
        physical = [b for b, _, prefix in baseline_paths if resolved == prefix or resolved.is_relative_to(prefix)]
        normalized.append({"path": path, "resolved": str(resolved), "exists": p.exists(),
                           "symlink": p.is_symlink(), "reasons": sorted(reasons),
                           "baseline_lexical_coverage": lexical, "baseline_physical_coverage": physical,
                           "baseline_excluded_by": [x for x in exclusions if p == Path(x) or p.is_relative_to(Path(x))],
                           "candidate_disposition": "include-existing-dependency-with-content-proof-required" if p.exists()
                               else "unavailable-reference; preserve-explicit-exception-not-retirement-proof"})
    # Every original source remains retained B scope. No automatic historical-only exclusions.
    account = [{"path": p, "disposition": "retain-on-B; operational-subtree-disposition-not-yet-proven",
                "related_dependency_count": sum(bool(r["baseline_lexical_coverage"] and p in r["baseline_lexical_coverage"])
                                                for r in normalized)} for p in baseline]
    current_identities = {"vk": process_paths(vk_pid), "cu": process_paths(cu_pid)}
    if identities != current_identities:
        raise ValueError("runtime dependency identity changed during accounting")
    summary = {"baseline_sources": len(baseline), "dependencies": len(normalized),
               "registered_repositories": len(rows["repositories"]),
               "recorded_workspaces": len(rows["workspaces"]), "relative_session_rows_requiring_base": relative_sessions,
               "native_threads": sum(native_counts.values()),
               "relative_native_rollout_rows_requiring_base": len(unresolved_relative),
               "missing_dependencies": sum(not r["exists"] for r in normalized),
               "outside_baseline_dependencies": sum(not r["baseline_lexical_coverage"] and not r["baseline_physical_coverage"]
                                                     for r in normalized),
               "dependencies_inside_baseline_exclusions": sum(bool(r["baseline_excluded_by"]) for r in normalized),
               "git_pointer_errors": len(errors), "production_modified": False,
               "cu_recursive_discovery_requires_additional_binding": effective_cu.get("CU_DISCOVER_ALL", False),
               "backup_or_restore_verified": False, "scope_reduction_approved": False}
    if overrides != local_path_overrides(cu_release, cu):
        raise ValueError("CU allowlisted local dependency paths changed during accounting")
    return {"identities": identities, "cu_selected_local_path_overrides": overrides,
            "baseline_plan_sha256": hashlib.sha256(plan_bytes).hexdigest(),
            "dependencies": normalized, "baseline_accounting": account, "git_pointer_errors": errors,
            "relative_native_references": unresolved_relative,
            "summary": summary, "limitations": ["Live path rows are discovery, not a capture boundary.",
                "Absent historical references do not prove retirement or data loss.",
                "Repository hooks/scripts, relative working dirs and external services need explicit execution-boundary acceptance.",
                "CU selected current file-loaded paths are recorded; startup-time file values cannot be authenticated from /proc.",
                "Credential files are path dependencies only; access/consent is separately gated."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vk-pid", type=int, required=True)
    parser.add_argument("--cu-pid", type=int, required=True)
    parser.add_argument("--baseline-plan", required=True)
    parser.add_argument("--receipt", required=True)
    args = parser.parse_args()
    receipt = collect(args.vk_pid, args.cu_pid, args.baseline_plan)
    encoded = json.dumps(receipt, indent=2, sort_keys=True).encode() + b"\n"
    destination = Path(args.receipt).absolute()
    if not destination.is_relative_to(Path("/mnt/vk-storage")) or not os.path.ismount("/mnt/vk-storage"):
        raise ValueError("receipt must be on mounted secondary storage")
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps({**receipt["summary"], "private_receipt_sha256": hashlib.sha256(encoded).hexdigest()}))


if __name__ == "__main__":
    main()
