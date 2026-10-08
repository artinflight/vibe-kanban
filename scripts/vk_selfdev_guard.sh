#!/usr/bin/env bash
set -euo pipefail

expected_repo_name="_vibe_kanban_repo"
expected_path="/home/mcp/_vibe_kanban_repo"
expected_remote_fragment="vibe-kanban"
canonical_repo="/home/mcp/_vibe_kanban_repo"
workspace_boundary='
## Workspace Safety Boundary

Normal feature/fix work may edit source, run focused checks, run previews, and update handoff docs from this generated workspace.

Do not restart `vibe-kanban.service`, switch `frontend-dist/current`, overwrite `/home/mcp/.local/bin/vibe-kanban-serve*`, edit the live VK SQLite DB, or prune live VK sessions/Codex state from an ordinary feature/fix task.

Deploys, restarts, frontend asset swaps, live DB edits, and live state cleanup require a separate operator-approved release/deploy task and must follow the repository deployment runbook.
'

fail() {
  printf 'VK self-development guard failed: %s\n' "$*" >&2
  printf 'This workspace is not safe for Vibe Kanban repo work. Check the project repo/defaults before starting an agent.\n' >&2
  exit 42
}

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[[ -n "$repo_root" ]] || fail "current directory is not inside a git repository"

repo_base="$(basename "$repo_root")"
[[ "$repo_base" == "$expected_repo_name" ]] || {
  # VK generated workspaces normally run setup scripts from the repo subdir.
  # A direct canonical checkout is also valid for external/manual validation.
  [[ "$repo_root" == "$expected_path" ]] || fail "expected repo basename '$expected_repo_name', got '$repo_base' at '$repo_root'"
}

[[ -f "$repo_root/AGENTS.md" ]] || fail "missing AGENTS.md in $repo_root"
[[ -f "$repo_root/VK_WORKFLOW.md" ]] || fail "missing VK_WORKFLOW.md in $repo_root"
if [[ ! -f "$repo_root/VK_SELF_DEVELOPMENT_WORKFLOW.md" ]]; then
  printf 'VK self-development guard warning: VK_SELF_DEVELOPMENT_WORKFLOW.md is not present in this branch yet.\n' >&2
fi

remotes="$(git -C "$repo_root" remote -v 2>/dev/null || true)"
printf '%s\n' "$remotes" | grep -q "$expected_remote_fragment" || fail "git remotes do not look like the Vibe Kanban repo"

workspace_root="$(dirname "$repo_root")"
for config_file in AGENTS.md CLAUDE.md; do
  config_path="$workspace_root/$config_file"
  [[ -f "$config_path" ]] || continue
  if ! grep -q "## Workspace Safety Boundary" "$config_path"; then
    if grep -Eq "# Vibe Kanban Workspace|## Repository Instructions|@$expected_repo_name/$config_file" "$config_path"; then
      printf '%s\n' "$workspace_boundary" >>"$config_path"
      printf 'Added workspace safety boundary to %s\n' "$config_path"
    fi
  fi
done

for doc_file in VK_SELF_DEVELOPMENT_WORKFLOW.md VK_AGENT_DEPLOYMENT_RUNBOOK.md; do
  source_doc="$canonical_repo/$doc_file"
  target_doc="$repo_root/$doc_file"
  if [[ "$repo_root" != "$canonical_repo" && ! -f "$target_doc" && -f "$source_doc" ]]; then
    cp "$source_doc" "$target_doc"
    printf 'Backfilled %s from canonical VK checkout\n' "$doc_file"
  fi
done

branch="$(git -C "$repo_root" branch --show-current 2>/dev/null || true)"
printf 'VK self-development guard passed: repo=%s branch=%s\n' "$repo_root" "${branch:-detached}"
