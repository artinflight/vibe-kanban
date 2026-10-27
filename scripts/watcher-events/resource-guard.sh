#!/usr/bin/env bash
set -euo pipefail

STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/resource-guard"
LOG_FILE="$STATE_DIR/guard.log"
SNAPSHOT_DIR="$STATE_DIR/snapshots"
COOLDOWN_FILE="$STATE_DIR/last-action-at"
DISK_STATE_FILE="$STATE_DIR/disk-alert-state"
DISK_LAST_ALERT_FILE="$STATE_DIR/disk-last-alert-at"
ROOT_HEADROOM_STATE_FILE="$STATE_DIR/root-headroom-alert-state"
ROOT_HEADROOM_LAST_ALERT_FILE="$STATE_DIR/root-headroom-last-alert-at"

WARN_MEM_AVAILABLE_KB=${WARN_MEM_AVAILABLE_KB:-2097152}
CRITICAL_MEM_AVAILABLE_KB=${CRITICAL_MEM_AVAILABLE_KB:-1572864}
WARN_SWAP_FREE_KB=${WARN_SWAP_FREE_KB:-524288}
CRITICAL_SWAP_FREE_KB=${CRITICAL_SWAP_FREE_KB:-262144}
ACTION_COOLDOWN_SECONDS=${ACTION_COOLDOWN_SECONDS:-900}
DISK_PATH=${DISK_PATH:-/}
WARN_DISK_PERCENT=${WARN_DISK_PERCENT:-85}
CRITICAL_DISK_PERCENT=${CRITICAL_DISK_PERCENT:-92}
EMERGENCY_DISK_PERCENT=${EMERGENCY_DISK_PERCENT:-97}
DISK_RECOVERY_PERCENT=${DISK_RECOVERY_PERCENT:-83}
DISK_REMINDER_SECONDS=${DISK_REMINDER_SECONDS:-21600}
# Owner's final disk alert threshold, 2026-10-24. Decimal GB; no admission change.
# This adds notification coverage only; it never deletes data or dispatches work.
ROOT_MIN_AVAILABLE_BYTES=${ROOT_MIN_AVAILABLE_BYTES:-10000000000}
ROOT_HEADROOM_REMINDER_SECONDS=${ROOT_HEADROOM_REMINDER_SECONDS:-300}
MCP_NOTIFICATIONS_NTFY_URL=${MCP_NOTIFICATIONS_NTFY_URL:-}
MCP_NOTIFICATIONS_NTFY_TOPIC=${MCP_NOTIFICATIONS_NTFY_TOPIC:-}
MCP_NOTIFICATIONS_NTFY_TOKEN=${MCP_NOTIFICATIONS_NTFY_TOKEN:-}
MCP_NOTIFICATIONS_NTFY_TLS_PIN_SHA256=${MCP_NOTIFICATIONS_NTFY_TLS_PIN_SHA256:-}

NONESSENTIAL_UNITS=(
  "programming-ui-staging.service"
  "fitrdy-deck.service"
)

LAST_RESORT_UNITS=(
  "vibe-kanban.service"
)

mkdir -p "$STATE_DIR" "$SNAPSHOT_DIR"

log() {
  local message=$1 size=0 line
  local LC_ALL=C
  # Preserve existing log history; stop appending at 2 MiB rather than growing forever.
  if [[ -f "$LOG_FILE" ]]; then
    size=$(stat -c %s -- "$LOG_FILE" 2>/dev/null) || return 0
  fi
  line="$(date -u +'%Y-%m-%dT%H:%M:%SZ') $message"
  ((size + ${#line} + 1 <= 2097152)) || return 0
  printf '%s\n' "$line" >>"$LOG_FILE"
}

disk_percent() {
  df -P "$DISK_PATH" | awk 'NR == 2 { gsub(/%/, "", $5); print $5 }'
}

disk_available_human() {
  df -hP "$DISK_PATH" | awk 'NR == 2 { print $4 }'
}

disk_level() {
  local percent=$1
  if ((percent >= EMERGENCY_DISK_PERCENT)); then
    printf 'emergency\n'
  elif ((percent >= CRITICAL_DISK_PERCENT)); then
    printf 'critical\n'
  elif ((percent >= WARN_DISK_PERCENT)); then
    printf 'warning\n'
  else
    printf 'normal\n'
  fi
}

read_state_file() {
  local file=$1 fallback=$2 value
  if [[ -r "$file" ]]; then
    read -r value <"$file" || value=$fallback
    printf '%s\n' "$value"
  else
    printf '%s\n' "$fallback"
  fi
}

send_notification() {
  local title=$1 priority=$2 tags=$3 message=$4
  if [[ -z "$MCP_NOTIFICATIONS_NTFY_URL" || -z "$MCP_NOTIFICATIONS_NTFY_TOPIC" ]]; then
    log "disk_notification_skipped reason=ntfy_not_configured title=$title"
    return 1
  fi

  local url
  url="${MCP_NOTIFICATIONS_NTFY_URL%/}/$MCP_NOTIFICATIONS_NTFY_TOPIC"
  local -a curl_args=(
    --fail --silent --show-error
    --connect-timeout 5 --max-time 10
    -H "Title: $title"
    -H "Priority: $priority"
    -H "Tags: $tags"
    --data-binary "$message"
  )
  if [[ -n "$MCP_NOTIFICATIONS_NTFY_TOKEN" ]]; then
    curl_args+=( -H "Authorization: Bearer $MCP_NOTIFICATIONS_NTFY_TOKEN" )
  fi
  if [[ -n "$MCP_NOTIFICATIONS_NTFY_TLS_PIN_SHA256" && "$url" == https://* ]]; then
    local authority host port actual_pin expected_pin
    authority=${url#https://}
    authority=${authority%%/*}
    host=${authority%%:*}
    port=443
    if [[ "$authority" == *:* ]]; then
      port=${authority##*:}
    fi
    actual_pin=$(openssl s_client -connect "$host:$port" -servername "$host" </dev/null 2>/dev/null \
      | openssl x509 -noout -fingerprint -sha256 2>/dev/null \
      | sed 's/^[^=]*=//' | tr -d ':' | tr '[:lower:]' '[:upper:]')
    expected_pin=$(printf '%s' "$MCP_NOTIFICATIONS_NTFY_TLS_PIN_SHA256" \
      | tr -d ':' | tr '[:lower:]' '[:upper:]')
    if [[ -z "$actual_pin" || "$actual_pin" != "$expected_pin" ]]; then
      log "disk_notification_failed reason=tls_pin_mismatch host=$host"
      return 1
    fi
    curl_args+=( --insecure )
  fi

  if curl "${curl_args[@]}" "$url" >/dev/null; then
    log "disk_notification_sent title=$title"
  else
    log "disk_notification_failed title=$title"
    return 1
  fi
}

check_disk() {
  local percent available level previous now last_alert should_alert=0
  percent=$(disk_percent)
  available=$(disk_available_human)
  level=$(disk_level "$percent")
  previous=$(read_state_file "$DISK_STATE_FILE" normal)
  now=$(date +%s)
  last_alert=$(read_state_file "$DISK_LAST_ALERT_FILE" 0)

  if [[ "$level" == normal ]]; then
    if [[ "$previous" != normal && $percent -le $DISK_RECOVERY_PERCENT ]]; then
      if send_notification \
        "Disk space recovered on $(hostname)" \
        3 white_check_mark \
        "Root disk is back to ${percent}% used with ${available} available."; then
        printf 'normal\n' >"$DISK_STATE_FILE"
      fi
    fi
    return 0
  fi

  if [[ "$level" != "$previous" || $((now - last_alert)) -ge $DISK_REMINDER_SECONDS ]]; then
    should_alert=1
  fi
  ((should_alert == 1)) || return 0

  local priority tags title
  case "$level" in
    warning)
      priority=3; tags=warning; title="Disk warning on $(hostname): ${percent}% used" ;;
    critical)
      priority=4; tags=warning,floppy_disk; title="Disk CRITICAL on $(hostname): ${percent}% used" ;;
    emergency)
      priority=5; tags=rotating_light,floppy_disk; title="Disk EMERGENCY on $(hostname): ${percent}% used" ;;
  esac
  if send_notification "$title" "$priority" "$tags" \
    "Root disk has ${available} available. Warning=${WARN_DISK_PERCENT}%, critical=${CRITICAL_DISK_PERCENT}%, emergency=${EMERGENCY_DISK_PERCENT}%. Free space now to prevent service failure."; then
    printf '%s\n' "$level" >"$DISK_STATE_FILE"
    printf '%s\n' "$now" >"$DISK_LAST_ALERT_FILE"
    log "disk_pressure level=$level percent=$percent available=$available"
  fi
}

root_available_bytes() {
  df -B1 --output=avail / | awk 'NR == 2 { print $1 }'
}

storage_gb() {
  LC_ALL=C awk -v value="$1" 'BEGIN { printf "%.1f GB", value / 1000000000 }'
}

check_root_headroom() {
  local available previous now last_alert deficit
  available=$(root_available_bytes)
  if [[ ! "$available" =~ ^[0-9]+$ || ! "$ROOT_MIN_AVAILABLE_BYTES" =~ ^[0-9]+$ ||
        ! "$ROOT_HEADROOM_REMINDER_SECONDS" =~ ^[0-9]+$ ]]; then
    log "root_headroom_unknown reason=invalid_measurement_or_configuration"
    return 0
  fi
  previous=$(read_state_file "$ROOT_HEADROOM_STATE_FILE" normal)
  now=$(date +%s)
  last_alert=$(read_state_file "$ROOT_HEADROOM_LAST_ALERT_FILE" 0)
  [[ "$last_alert" =~ ^[0-9]+$ ]] || last_alert=0
  log "root_headroom_sample available_bytes=$available minimum_bytes=$ROOT_MIN_AVAILABLE_BYTES"
  if ((available >= ROOT_MIN_AVAILABLE_BYTES)); then
    if [[ "$previous" == low ]]; then
      if send_notification "OS headroom restored on $(hostname)" 3 white_check_mark \
        "OS drive /: $(storage_gb "$available") free ($available bytes). Threshold: $(storage_gb "$ROOT_MIN_AVAILABLE_BYTES") ($ROOT_MIN_AVAILABLE_BYTES bytes). Recovery only; no Disk Space wake request."; then
        printf 'normal\n' >"$ROOT_HEADROOM_STATE_FILE"
        log "root_headroom_recovered available_bytes=$available"
      fi
    fi
    return 0
  fi
  if [[ "$previous" == low ]] && ((now - last_alert < ROOT_HEADROOM_REMINDER_SECONDS)); then
    return 0
  fi
  deficit=$((ROOT_MIN_AVAILABLE_BYTES - available))
  if send_notification "Disk CRITICAL on $(hostname): OS below $(storage_gb "$ROOT_MIN_AVAILABLE_BYTES")" 4 warning,floppy_disk \
    "OS drive /: $(storage_gb "$available") free ($available bytes). Threshold: $(storage_gb "$ROOT_MIN_AVAILABLE_BYTES") ($ROOT_MIN_AVAILABLE_BYTES bytes; trigger strictly below). Space needed: $(storage_gb "$deficit"). Existing Disk Space wake delivery is tracked separately; preserve active work and recovery data."; then
    printf 'low\n' >"$ROOT_HEADROOM_STATE_FILE"
    printf '%s\n' "$now" >"$ROOT_HEADROOM_LAST_ALERT_FILE"
    log "root_headroom_low available_bytes=$available shortfall_bytes=$deficit"
  fi
}

read_mem_value_kb() {
  local key=$1
  awk -v target="$key" '$1 == target ":" { print $2; exit }' /proc/meminfo
}

mem_available_kb() {
  read_mem_value_kb MemAvailable
}

swap_free_kb() {
  read_mem_value_kb SwapFree
}

unit_memory_current_bytes() {
  local unit=$1
  systemctl --user show --property=MemoryCurrent --value "$unit" 2>/dev/null || printf '0\n'
}

seconds_since_last_action() {
  local now last
  now=$(date +%s)
  if [[ ! -r "$COOLDOWN_FILE" ]]; then
    printf '%s\n' "$ACTION_COOLDOWN_SECONDS"
    return
  fi

  read -r last <"$COOLDOWN_FILE" || last=0
  if [[ ! "$last" =~ ^[0-9]+$ ]]; then
    printf '%s\n' "$ACTION_COOLDOWN_SECONDS"
    return
  fi

  printf '%s\n' "$((now - last))"
}

mark_action() {
  date +%s >"$COOLDOWN_FILE"
}

write_snapshot() {
  local snapshot_file
  snapshot_file="$SNAPSHOT_DIR/$(date -u +'%Y%m%dT%H%M%SZ').log"
  {
    echo "resource guard snapshot"
    echo "created_at=$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    echo
    free -h
    echo
    grep -E 'MemAvailable|SwapTotal|SwapFree' /proc/meminfo
    echo
    ps -eo pid,ppid,pmem,rss,vsz,etimes,cmd --sort=-rss | head -n 40
    echo
    systemctl --user show \
      vibe-kanban.service \
      programming-ui.service \
      programming-ui-staging.service \
      fitrdy-deck.service \
      fitrdy-manager.service \
      redis-user.service \
      --property=Names,MemoryCurrent,MemoryPeak
  } >"$snapshot_file"
  log "snapshot_written file=$snapshot_file"
}

stop_unit_if_active() {
  local unit=$1
  if systemctl --user is-active --quiet "$unit"; then
    log "stopping unit=$unit"
    systemctl --user stop "$unit"
  fi
}

restart_unit_if_active() {
  local unit=$1
  if systemctl --user is-active --quiet "$unit"; then
    log "restarting unit=$unit"
    systemctl --user restart "$unit"
  fi
}

main() {
  local mem_kb swap_kb vibe_bytes cooldown_elapsed
  check_root_headroom
  check_disk
  mem_kb=$(mem_available_kb)
  swap_kb=$(swap_free_kb)

  if ((mem_kb > WARN_MEM_AVAILABLE_KB && swap_kb > WARN_SWAP_FREE_KB)); then
    exit 0
  fi

  vibe_bytes=$(unit_memory_current_bytes vibe-kanban.service)
  log "pressure_detected mem_available_kb=$mem_kb swap_free_kb=$swap_kb vibe_memory_bytes=$vibe_bytes"
  write_snapshot

  if ((mem_kb > CRITICAL_MEM_AVAILABLE_KB && swap_kb > CRITICAL_SWAP_FREE_KB)); then
    exit 0
  fi

  cooldown_elapsed=$(seconds_since_last_action)
  if ((cooldown_elapsed < ACTION_COOLDOWN_SECONDS)); then
    log "critical_but_in_cooldown elapsed_seconds=$cooldown_elapsed"
    exit 0
  fi

  local unit
  for unit in "${NONESSENTIAL_UNITS[@]}"; do
    stop_unit_if_active "$unit"
  done

  sleep 5

  mem_kb=$(mem_available_kb)
  swap_kb=$(swap_free_kb)
  log "post_shed_check mem_available_kb=$mem_kb swap_free_kb=$swap_kb"

  if ((mem_kb <= CRITICAL_MEM_AVAILABLE_KB || swap_kb <= CRITICAL_SWAP_FREE_KB)); then
    for unit in "${LAST_RESORT_UNITS[@]}"; do
      restart_unit_if_active "$unit"
    done
    sleep 5
    mem_kb=$(mem_available_kb)
    swap_kb=$(swap_free_kb)
    log "post_restart_check mem_available_kb=$mem_kb swap_free_kb=$swap_kb"
  fi

  mark_action
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
