"""Plan-bound namespace context, never reconstruction of missing source data."""
import copy
import os
from pathlib import PurePosixPath

from vk_candidate_generation import digest, require


def authenticate_plan(plan, plan_sha256, scope_sha256):
    require(isinstance(plan, dict) and digest(plan) == plan_sha256,
            "namespace scaffold source plan digest mismatch")
    sources = plan.get("sources")
    require(isinstance(sources, list) and sources and all(isinstance(p, str) for p in sources),
            "namespace scaffold source roots missing")
    for raw in sources:
        path = PurePosixPath(raw)
        require(path.is_absolute() and raw == str(path) and ".." not in path.parts,
                "namespace scaffold source root is not canonical")
    scope = {"sources": sorted(set(sources)), "excluded_rebuildable_directories":
             sorted(set(plan.get("excluded_rebuildable_directories", [])))}
    require(digest(scope) == scope_sha256, "namespace scaffold source scope digest mismatch")
    return copy.deepcopy(plan)


def add_context(entries, plan, prefix):
    """Add only missing strict ancestors outside every declared source root.

    Context directories are generated with explicit private defaults. Their
    original ownership, mode and timestamps are unknown and are not asserted.
    Existing archive entries always win; an omitted source parent fails closed.
    """
    prefix = PurePosixPath(prefix)
    roots = tuple(PurePosixPath(raw) for raw in plan["sources"])
    require(all(root == prefix or root.is_relative_to(prefix) for root in roots),
            "namespace scaffold source root outside pinned prefix")
    missing = {parent for name in entries for parent in PurePosixPath(name).parents
               if str(parent) != "." and str(parent) not in entries}
    for parent in missing:
        absolute = prefix / parent
        require(not any(absolute == root or absolute.is_relative_to(root) for root in roots),
                "namespace scaffold cannot reconstruct missing source directories")
        require(any(root != absolute and root.is_relative_to(absolute) for root in roots),
                "namespace scaffold parent is not a declared source ancestor")
    generated = sorted(str(parent) for parent in missing)
    for name in generated:
        entries[name] = {"kind": "directory", "mode": 0o700, "uid": os.getuid(),
                         "gid": os.getgid(), "mtime_ns": 0, "xattrs": {}}
    return {"policy": "strict-source-ancestors-v1", "source_plan_sha256": digest(plan),
            "generated_context_names": generated, "original_context_metadata_verified": False,
            "generated_mode": 0o700, "generated_uid": os.getuid(), "generated_gid": os.getgid(),
            "generated_mtime_ns": 0, "source_entries_reconstructed": 0}
