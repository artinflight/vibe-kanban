#!/usr/bin/env bash
set -euo pipefail

service="${1:-vibe-kanban.service}"

if ! command -v systemctl >/dev/null 2>&1; then
  echo "systemctl not found; cannot check live VK runtime guardrails" >&2
  exit 2
fi

environment="$(systemctl --user show "$service" -p Environment --value)"

required=(
  "CODEX_HOME=/home/mcp/.local/share/vibe-kanban/codex-home"
  "VK_DISABLE_PR_MONITOR=1"
  "VK_USE_SYSTEMD_RUN=1"
  "VK_TRANSIENT_MEMORY_HIGH=1500M"
  "VK_TRANSIENT_MEMORY_MAX=3000M"
  "VK_CODEX_BASE_COMMAND=/home/mcp/.local/bin/codex"
)

missing=()
for item in "${required[@]}"; do
  if [[ "$environment" != *"$item"* ]]; then
    missing+=("$item")
  fi
done

if (( ${#missing[@]} > 0 )); then
  echo "Live VK runtime guardrail check failed for $service:" >&2
  for item in "${missing[@]}"; do
    echo "- missing $item" >&2
  done
  echo "Install docs/self-hosting/systemd/runtime-guardrails.conf as a service drop-in and run systemctl --user daemon-reload." >&2
  exit 1
fi

echo "Live VK runtime guardrails are present for $service."
