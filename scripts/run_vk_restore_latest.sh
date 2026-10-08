#!/usr/bin/env bash
set -euo pipefail
cd /home/mcp/_vibe_kanban_repo

local_latest="/home/mcp/backups/vk-lean-restore-latest.tar.gz"
desktop_pointer="/home/mcp/backups/vk-lean-restore-latest.desktop.json"
restore_copy="/home/mcp/backups/vk-lean-restore-latest-from-desktop.tar.gz"

if [[ -f "$local_latest" ]]; then
  python3 scripts/vk_restore_lean_backup.py "$local_latest"
  exit 0
fi

if [[ ! -f "$desktop_pointer" ]]; then
  echo "No local latest backup and no Desktop pointer at $desktop_pointer" >&2
  exit 1
fi

desktop_latest="$(python3 - <<'PY'
import json
from pathlib import Path
pointer = Path("/home/mcp/backups/vk-lean-restore-latest.desktop.json")
print(json.loads(pointer.read_text())["desktop_latest"])
PY
)"

scp -q "$desktop_latest" "$restore_copy"
python3 scripts/vk_restore_lean_backup.py "$restore_copy"
