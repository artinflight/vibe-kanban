#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="$ROOT_DIR/.preview"
UNIT_FILE="$STATE_DIR/unit"
PORT_FILE="$STATE_DIR/port"
LOG_FILE="$STATE_DIR/preview.log"

APP_SLUG="${PREVIEW_APP_SLUG:-vibe-kanban}"
LOCAL_DOMAIN="${PREVIEW_LOCAL_DOMAIN:-vk-preview.local}"
PORT="${PREVIEW_PORT:-3025}"
HOST="${PREVIEW_HOST:-0.0.0.0}"
BACKEND_PORT="${PREVIEW_BACKEND_PORT:-4311}"
DNS_OR_PROXY_IP="${PREVIEW_DNS_OR_PROXY_IP:-10.0.0.97}"
EXPECTED_TEXT="${PREVIEW_EXPECTED_TEXT:-Vibe Kanban}"
UNIT_NAME="${PREVIEW_UNIT_NAME:-vk-preview-${APP_SLUG}}"
LOCAL_URL="http://127.0.0.1:${PORT}/"
HTTPS_URL="https://${LOCAL_DOMAIN}/"

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

ensure_dependencies() {
  for cmd in pnpm curl rg systemctl systemd-run; do
    if ! command_exists "$cmd"; then
      echo "$cmd is required to run this preview." >&2
      exit 1
    fi
  done
}

is_unit_active() {
  systemctl --user is-active --quiet "$UNIT_NAME"
}

wait_for_local_origin() {
  local deadline=$((SECONDS + 30))
  until curl --silent --fail --max-time 2 "$LOCAL_URL" >/dev/null; do
    if (( SECONDS >= deadline )); then
      echo "Preview origin did not become ready at ${LOCAL_URL}." >&2
      return 1
    fi
    sleep 1
  done
}

check_backend() {
  local backend_url="http://127.0.0.1:${BACKEND_PORT}/api/info"
  if ! curl --silent --fail --max-time 2 "$backend_url" >/dev/null; then
    cat >&2 <<EOF
No Vibe Kanban backend responded at ${backend_url}.
Start the main local Vibe Kanban instance first, or set PREVIEW_BACKEND_PORT.
EOF
    exit 1
  fi
}

start() {
  ensure_dependencies
  check_backend
  mkdir -p "$STATE_DIR"
  echo "$UNIT_NAME" >"$UNIT_FILE"
  echo "$PORT" >"$PORT_FILE"
  : >"$LOG_FILE"

  if is_unit_active; then
    echo "Preview already running."
  else
    cd "$ROOT_DIR"
    systemd-run \
      --user \
      --unit "$UNIT_NAME" \
      --same-dir \
      --working-directory="$ROOT_DIR" \
      --property=MemoryHigh=1500M \
      --property=MemoryMax=2G \
      --setenv=PATH="/usr/bin:/bin:/home/mcp/.local/bin" \
      --setenv=VITE_OPEN=false \
      --setenv=BROWSER=none \
      --setenv=__VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS="$LOCAL_DOMAIN" \
      --setenv=FRONTEND_PORT="$PORT" \
      --setenv=BACKEND_PORT="$BACKEND_PORT" \
      /home/mcp/.local/bin/pnpm \
      --filter @vibe/local-web run dev -- \
      --host "$HOST" \
      --port "$PORT" \
      --strictPort >/dev/null
  fi

  wait_for_local_origin

  echo "Preview origin: ${LOCAL_URL}"
  echo "Preview URL: ${HTTPS_URL}"
  echo "Unit: ${UNIT_NAME}"
  echo "Logs: journalctl --user -u ${UNIT_NAME}"
  echo "Run scripts/preview.sh verify to verify the operator-facing HTTPS URL."
}

verify() {
  ensure_dependencies
  wait_for_local_origin

  echo "Verifying local origin: ${LOCAL_URL}"
  curl --silent --fail --max-time 5 "$LOCAL_URL" | rg -q "$EXPECTED_TEXT"

  echo "Verifying HTTPS route: ${HTTPS_URL} via ${DNS_OR_PROXY_IP}"
  curl -k -I --fail --max-time 5 \
    --resolve "${LOCAL_DOMAIN}:443:${DNS_OR_PROXY_IP}" \
    "$HTTPS_URL"
  if ! curl -k --fail --max-time 10 \
    --resolve "${LOCAL_DOMAIN}:443:${DNS_OR_PROXY_IP}" \
    "$HTTPS_URL" | rg -q "$EXPECTED_TEXT"; then
    cat >&2 <<EOF
HTTPS .local route is not serving this preview.
Expected to find: ${EXPECTED_TEXT}
URL checked: ${HTTPS_URL}
Proxy IP: ${DNS_OR_PROXY_IP}

Required route owner action:
- Add DNS for ${LOCAL_DOMAIN} -> ${DNS_OR_PROXY_IP}
- Add homelab nginx HTTPS server_name ${LOCAL_DOMAIN}
- Proxy ${LOCAL_DOMAIN} to http://10.0.0.129:3010
- Confirm the MCP host local router maps ${LOCAL_DOMAIN} -> 127.0.0.1:${PORT}
EOF
    exit 1
  fi

  echo "Preview URL: ${HTTPS_URL}"
}

status() {
  if is_unit_active; then
    echo "Preview running."
    echo "Port: ${PORT}"
    echo "Local URL: ${LOCAL_URL}"
    echo "HTTPS URL: ${HTTPS_URL}"
    echo "Unit: ${UNIT_NAME}"
    echo "Logs: journalctl --user -u ${UNIT_NAME}"
  else
    echo "Preview not running."
  fi
}

stop() {
  if is_unit_active; then
    systemctl --user stop "$UNIT_NAME"
    systemctl --user reset-failed "$UNIT_NAME" >/dev/null 2>&1 || true
    echo "Stopped preview."
  else
    echo "Preview not running."
  fi
}

logs() {
  journalctl --user -u "$UNIT_NAME" -n "${PREVIEW_LOG_LINES:-120}" --no-pager
}

case "${1:-start}" in
  start)
    start
    ;;
  verify)
    verify
    ;;
  status)
    status
    ;;
  stop)
    stop
    ;;
  logs)
    logs
    ;;
  *)
    cat >&2 <<EOF
Usage: scripts/preview.sh [start|verify|status|stop|logs]

Environment:
  PREVIEW_PORT             Fixed frontend port. Default: 3025
  PREVIEW_HOST             Frontend bind host. Default: 0.0.0.0
  PREVIEW_BACKEND_PORT     Existing Vibe Kanban backend port. Default: 4311
  PREVIEW_LOCAL_DOMAIN     Operator-facing .local host. Default: vk-preview.local
  PREVIEW_DNS_OR_PROXY_IP  Private DNS/proxy IP. Default: 10.0.0.97
  PREVIEW_EXPECTED_TEXT    Content proof text. Default: Vibe Kanban
EOF
    exit 2
    ;;
esac
