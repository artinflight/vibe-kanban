#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="${VK_STATE_DIR:?Set VK_STATE_DIR to the verified live production state directory}"
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

if ! mountpoint -q /mnt/vk-storage; then
  echo "The secondary SSD must be mounted before publication preparation." >&2
  exit 1
fi

pnpm --filter @vibe/local-web run build

if [[ ! -f "$BUILD_DIR/index.html" ]]; then
  echo "Frontend build did not produce $BUILD_DIR/index.html" >&2
  exit 1
fi

# The snapshot must be Desktop-verified before any production asset mutation.
python3 "$ROOT_DIR/scripts/vk_workspace_review_snapshot.py" \
  --database "$STATE_DIR/db.v2.sqlite" \
  --output "/mnt/vk-storage/vk-review-snapshots/frontend-$STAMP.json" \
  --api-url "${VK_REVIEW_SNAPSHOT_API_URL:?Set the verified live backend API URL}" \
  --require-journal \
  --reason "before-frontend-publication-$STAMP"

mkdir -p "$RELEASES_DIR" "$(dirname "$CURRENT_LINK")"
mkdir -p "$RELEASE_DIR"
cp -a "$BUILD_DIR"/. "$RELEASE_DIR"/

ln -sfn "$RELEASE_DIR" "$TMP_LINK"
mv -Tf "$TMP_LINK" "$CURRENT_LINK"

echo "Published frontend dist:"
echo "  release: $RELEASE_DIR"
echo "  current: $CURRENT_LINK"
