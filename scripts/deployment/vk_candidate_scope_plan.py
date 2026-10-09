"""Compile private configured-path discovery into explicit candidate/B accounting.

No payload walks, archive writes, endpoint calls or scope waiver. Context parents
do not authorize a copy of the entire host. The resulting proposal is not a
restore manifest: pinned B content/metadata and supervisor acceptance remain
required. Historical sources stay preserved on B even when operationally unused.
"""
import hashlib
import json
from pathlib import Path
import shutil
import shlex
import tomllib
from urllib.parse import urlsplit

CONTEXT = {"/", "/home", "/home/mcp", "/mnt", "/mnt/vk-storage", "/tmp"}
OS_ROOTS = (Path("/usr"), Path("/bin"), Path("/lib"), Path("/lib64"))


def execution_dependencies(pid):
    """Select launcher/guard paths in-process; never retain the full environment."""
    paths, unresolved = set(), []
    keys = {"VK_CAPACITY_GUARD", "VK_CAPACITY_PERMISSION_DIR", "CODEX_CLI_PATH", "VK_CODEX_BIN",
            "VK_TURN_PRESERVATION_CONFIG", "VK_GIT_SYNC_ENFORCEMENT_CONFIG"}
    fields = (Path('/proc') / str(int(pid)) / 'environ').read_bytes().split(b'\0')
    for field in fields:
        key, _, value = field.partition(b'=')
        key = key.decode(errors='replace')
        if key in keys:
            path = value.decode()
            if not path.startswith('/'):
                unresolved.append(key + '-requires-explicit-path-base')
            else:
                paths.add(path)
        if key == 'VK_CODEX_BASE_COMMAND':
            # Do not serialize the remaining arguments, which may be private.
            argv = shlex.split(value.decode())
            if argv and argv[0].startswith('/'):
                paths.add(argv[0])
                paths.add(str(Path(argv[0]).parent))
            else:
                unresolved.append('native-base-command-needs-explicit-executable')
        if key == 'PATH':
            for path in value.decode().split(':'):
                if path.startswith('/') and Path(path).exists():
                    paths.add(path)
                elif path and not path.startswith('/'):
                    unresolved.append('relative-executable-search-root')
    return {"path_dependencies": sorted(paths), "unresolved": unresolved,
            "command_arguments_published": False, "production_process_modified": False}


def tool_dependencies(native_home, command_path):
    """Read configured selectors only; discard headers, credentials and full URLs."""
    config_path = Path(native_home) / "config.toml"
    data = tomllib.loads(config_path.read_text())
    rows, paths = [], set()
    for name, settings in sorted(data.get("mcp_servers", {}).items()):
        row = {"server_id_sha256": hashlib.sha256(name.encode()).hexdigest(),
               "external_writer_boundary_required": True}
        command = settings.get("command")
        if command:
            executable = command if command.startswith("/") else shutil.which(command, path=command_path)
            if executable:
                paths.add(executable)
            row.update(transport="local-command", executable=executable,
                       nonpath_command_arguments_uninterpreted=True)
            cwd = settings.get("cwd")
            if cwd:
                if not isinstance(cwd, str) or not cwd.startswith("/"):
                    raise ValueError("local MCP cwd requires explicit absolute base")
                paths.add(cwd)
            # Record only existing absolute argument paths; do not serialize argv
            # (which could include credentials). Missing/unrecognized arguments
            # remain an execution-boundary acceptance requirement.
            for arg in settings.get("args", []):
                if isinstance(arg, str) and arg.startswith("/") and Path(arg).exists():
                    paths.add(arg)
        elif settings.get("url"):
            parsed = urlsplit(settings["url"])
            row.update(transport="remote", endpoint_scheme=parsed.scheme,
                       endpoint_hostname_sha256=hashlib.sha256((parsed.hostname or "").encode()).hexdigest(),
                       production_endpoint_not_contacted=True)
        else:
            row["transport"] = "unresolved"
        rows.append(row)
    return {"servers": rows, "path_dependencies": sorted(paths), "configuration_values_published": False}


def compile_plan(discovery, tools, execution=None):
    dependencies = discovery["dependencies"]
    candidates, context, immutable, exceptions = {}, [], [], []
    for row in dependencies:
        if not row["exists"]:
            exceptions.append({"path": row["path"], "reason": "retained reference unavailable; lifecycle/content unknown"})
            continue
        for path in {row["path"], row["resolved"]}:
            if path in CONTEXT:
                context.append(path)
            elif any(Path(path) == p or Path(path).is_relative_to(p) for p in OS_ROOTS):
                immutable.append(path)
            else:
                candidates.setdefault(path, set()).update(row["reasons"])
    execution = execution or {"path_dependencies": [], "unresolved": []}
    for path in set(tools["path_dependencies"]) | set(execution["path_dependencies"]):
        resolved = str(Path(path).resolve())
        for p in {path, resolved}:
            if p in CONTEXT:
                context.append(p)
            elif any(Path(p).is_relative_to(root) for root in OS_ROOTS):
                immutable.append(p)
            else:
                candidates.setdefault(p, set()).add("configured-MCP-or-native-launcher-dependency")
    # Reduction only merges nested payload roots; symlink selectors remain
    # explicit rows in discovery, and their resolved backing is included too.
    ordered = sorted(candidates, key=lambda p: (len(Path(p).parts), p))
    roots = []
    for path in ordered:
        if not any(Path(path).is_relative_to(Path(parent)) and Path(parent).is_dir()
                   and not Path(parent).is_symlink() for parent in roots):
            roots.append(path)
    account = []
    for original in discovery["baseline_accounting"]:
        source = original["path"]
        related = [p for p in roots if Path(p) == Path(source) or Path(p).is_relative_to(Path(source))
                   or Path(source).is_relative_to(Path(p))]
        account.append({"path": source, "B_preservation": "required; no change or cleanup",
                        "candidate": "configured-dependency-payload" if related else "B-only-operational-proposal",
                        "related_candidate_roots": related,
                        "historical_retirement_proven": False})
    return {"candidate_payload_roots": [{"path": p, "reasons": sorted(candidates[p])} for p in roots],
            "namespace_context_only": sorted(set(context)), "immutable_host_prerequisites": sorted(set(immutable)),
            "baseline_accounting": account, "unavailable_reference_exceptions": exceptions,
            "relative_native_references": discovery.get("relative_native_references", []),
            "external_tool_boundaries": tools, "native_execution_dependencies": execution,
            "whole_historical_B_verification_required": True,
            "restore_or_operational_scope_approved": False,
            "blockers": ["Fresh authenticated B capture/metadata and all required current SQLite snapshots.",
                "Relative session/native paths need source-based interpretation; missing refs retain lifecycle exceptions.",
                "External tool writers must be fenced/rebound to candidate paths before live acceptance.",
                "Unclassified backup subtrees inside included homes remain included; no automatic intra-root exclusion.",
                "Configured build roots are included until an explicit tested rebuild policy is bound.",
                "Whole-state capacity and adapters are supplied by OP/root, not inferred from these counts."]}
