#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="$ROOT_DIR/.vk-preview"
PID_FILE="$STATE_DIR/pid"
PORT_FILE="$STATE_DIR/port"
LOG_FILE="$STATE_DIR/preview.log"

BACKEND_PORT="${VK_PREVIEW_BACKEND_PORT:-4311}"
PORT_START="${VK_PREVIEW_PORT_START:-3002}"
HOST="${VK_PREVIEW_HOST:-127.0.0.1}"

usage() {
  cat <<'EOF'
Usage:
  scripts/vk-preview.sh start    Start a lightweight frontend-only VK preview
  scripts/vk-preview.sh stop     Stop the preview for this worktree
  scripts/vk-preview.sh restart  Restart the preview for this worktree
  scripts/vk-preview.sh status   Show preview status
  scripts/vk-preview.sh logs     Tail preview logs

Environment:
  VK_PREVIEW_PORT=3002          Use a specific frontend port
  VK_PREVIEW_PORT_START=3002    First port to try when auto-selecting
  VK_PREVIEW_BACKEND_PORT=4311  Existing VK backend port to proxy /api to
  VK_PREVIEW_HOST=127.0.0.1     Bind host for the Vite preview
EOF
}

is_running() {
  local pid="${1:-}"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

current_pid() {
  [[ -f "$PID_FILE" ]] && cat "$PID_FILE"
}

current_port() {
  [[ -f "$PORT_FILE" ]] && cat "$PORT_FILE"
}

find_port() {
  if [[ -n "${VK_PREVIEW_PORT:-}" ]]; then
    printf '%s\n' "$VK_PREVIEW_PORT"
    return
  fi

  python3 - "$PORT_START" "$HOST" <<'PY'
import socket
import sys

start = int(sys.argv[1])
host = sys.argv[2]
for port in range(start, 65535):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        if sock.connect_ex((host, port)) != 0:
            print(port)
            sys.exit(0)
raise SystemExit("no free preview port found")
PY
}

wait_for_port() {
  local port="$1"
  python3 - "$HOST" "$port" <<'PY'
import socket
import sys
import time

host = sys.argv[1]
port = int(sys.argv[2])
deadline = time.time() + 30
while time.time() < deadline:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        if sock.connect_ex((host, port)) == 0:
            sys.exit(0)
    time.sleep(0.25)
raise SystemExit(1)
PY
}

check_backend() {
  if command -v curl >/dev/null 2>&1; then
    curl -fsS "http://127.0.0.1:${BACKEND_PORT}/api/info" >/dev/null || {
      echo "Backend check failed: http://127.0.0.1:${BACKEND_PORT}/api/info" >&2
      echo "Start or deploy the normal VK backend first, then retry." >&2
      exit 1
    }
  fi
}

start_preview() {
  mkdir -p "$STATE_DIR"

  local existing
  existing="$(current_pid || true)"
  if is_running "$existing"; then
    echo "Preview already running: http://${HOST}:$(current_port)"
    echo "PID: $existing"
    echo "Log: $LOG_FILE"
    exit 0
  fi

  check_backend

  local port
  port="$(find_port)"

  : >"$LOG_FILE"
  (
    cd "$ROOT_DIR"
    exec env \
      VITE_OPEN=false \
      BROWSER=none \
      FRONTEND_PORT="$port" \
      BACKEND_PORT="$BACKEND_PORT" \
      pnpm --filter @vibe/local-web run dev -- \
        --host "$HOST" \
        --port "$port" \
        --strictPort
  ) >>"$LOG_FILE" 2>&1 &

  local pid="$!"
  echo "$pid" >"$PID_FILE"
  echo "$port" >"$PORT_FILE"

  if ! wait_for_port "$port"; then
    echo "Preview did not become ready. See: $LOG_FILE" >&2
    exit 1
  fi

  echo "Preview running: http://${HOST}:${port}/"
  echo "Backend proxy: http://127.0.0.1:${BACKEND_PORT}/"
  echo "PID: $pid"
  echo "Log: $LOG_FILE"
}

stop_preview() {
  local pid
  pid="$(current_pid || true)"
  if ! is_running "$pid"; then
    rm -f "$PID_FILE" "$PORT_FILE"
    echo "No preview running for this worktree."
    return
  fi

  kill "$pid" 2>/dev/null || true
  for _ in {1..20}; do
    if ! is_running "$pid"; then
      rm -f "$PID_FILE" "$PORT_FILE"
      echo "Stopped preview."
      return
    fi
    sleep 0.2
  done

  kill -9 "$pid" 2>/dev/null || true
  rm -f "$PID_FILE" "$PORT_FILE"
  echo "Force-stopped preview."
}

status_preview() {
  local pid port
  pid="$(current_pid || true)"
  port="$(current_port || true)"
  if is_running "$pid"; then
    echo "Preview running: http://${HOST}:${port}/"
    echo "PID: $pid"
    echo "Log: $LOG_FILE"
  else
    echo "No preview running for this worktree."
  fi
}

case "${1:-}" in
  start)
    start_preview
    ;;
  stop)
    stop_preview
    ;;
  restart)
    stop_preview
    start_preview
    ;;
  status)
    status_preview
    ;;
  logs)
    mkdir -p "$STATE_DIR"
    touch "$LOG_FILE"
    tail -n 80 -f "$LOG_FILE"
    ;;
  -h|--help|help|"")
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
