#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="${VK_STATE_DIR:-$HOME/.local/share/vibe-kanban}"
DIST_BASE_DIR="${VK_FRONTEND_RELEASES_DIR:-$STATE_DIR/frontend-dist}"
CURRENT_LINK="${VK_FRONTEND_DIST_DIR:-$DIST_BASE_DIR/current}"
RELEASES_DIR="$DIST_BASE_DIR/releases"
BUILD_DIR="$ROOT_DIR/packages/local-web/dist"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RELEASE_DIR="$RELEASES_DIR/$STAMP"
TMP_LINK="$CURRENT_LINK.tmp"

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

if ! command_exists pnpm; then
  echo "pnpm is required to build the frontend." >&2
  exit 1
fi

mkdir -p "$RELEASES_DIR" "$(dirname "$CURRENT_LINK")"

pnpm --filter @vibe/local-web run build

if [[ ! -f "$BUILD_DIR/index.html" ]]; then
  echo "Frontend build did not produce $BUILD_DIR/index.html" >&2
  exit 1
fi

mkdir -p "$RELEASE_DIR"
cp -a "$BUILD_DIR"/. "$RELEASE_DIR"/

ln -sfn "$RELEASE_DIR" "$TMP_LINK"
mv -Tf "$TMP_LINK" "$CURRENT_LINK"

echo "Published frontend dist:"
echo "  release: $RELEASE_DIR"
echo "  current: $CURRENT_LINK"
