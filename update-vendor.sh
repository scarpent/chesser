#!/usr/bin/env bash
#
# Update hosted frontend dependencies for Chesser.
#
# This script fetches specific pinned versions of third-party JS libraries
# (currently Alpine.js and chess.js), stores them under versioned paths in
# vendorfiles/, and then copies a stable reference into static/ for use by
# Django templates. The goal is reproducibility, auditability, and minimal
# frontend tooling — no npm, no bundler, no build step.
#
# Versioned vendor copies are kept so upgrades are explicit and reversible.
# The static/ copies represent the currently active version used by the app.
# A -f flag is provided to force re-fetching even if files already exist.
#
# Notes:
# - curl is run in fail-fast mode to avoid silently accepting partial downloads.
# - chess.js has its sourcemap reference stripped to avoid WhiteNoise issues.
# - Caching is handled explicitly at the template level where needed.
#
# This script is intended to be run manually when upgrading dependencies,
# not as part of deployment.

set -euo pipefail

STATIC_DIR="static"
VENDOR_DIR="vendorfiles"

ALPINE_VER="3.15.3"
CHESSJS_VER="1.4.0"
CHESSGROUND_VER="9.2.1"

FORCE_UPDATE=0

while getopts ":f" opt; do
  case "$opt" in
    f)
      FORCE_UPDATE=1
      ;;
    *)
      echo -e "Usage: $(basename "$0") [-f]\n-f: force update" >&2
      exit 2
      ;;
  esac
done

# ---- Alpine.js ----

ALPINE_VENDOR_DIR="$VENDOR_DIR/alpine/$ALPINE_VER"
ALPINE_VENDOR_FILE="$ALPINE_VENDOR_DIR/cdn.min.js"
ALPINE_STABLE_FILE="$STATIC_DIR/alpine/cdn.min.js"

if [[ -f "$ALPINE_VENDOR_FILE" && "$FORCE_UPDATE" -eq 0 ]]; then
  echo "Alpine.js v$ALPINE_VER already at $ALPINE_VENDOR_FILE"
else
  mkdir -vp "$ALPINE_VENDOR_DIR"

  echo "Fetching Alpine.js v$ALPINE_VER"
  # -f: fail on HTTP errors
  # -L: follow redirects (unpkg/jsdelivr)
  # --show-error: print errors even with --silent
  # --silent: no progress bar
  curl -fL --show-error --silent \
    "https://cdn.jsdelivr.net/npm/alpinejs@${ALPINE_VER}/dist/cdn.min.js" \
    -o "$ALPINE_VENDOR_FILE"
fi

echo "Updating Alpine.js stable copy"
cp -f "$ALPINE_VENDOR_FILE" "$ALPINE_STABLE_FILE"

# ---- chess.js ----

CHESSJS_VENDOR_DIR="$VENDOR_DIR/chessjs/$CHESSJS_VER/dist/esm"
CHESSJS_VENDOR_FILE="$CHESSJS_VENDOR_DIR/chess.js"
CHESSJS_STABLE_FILE="$STATIC_DIR/chessjs/chess.js"

if [[ -f "$CHESSJS_VENDOR_FILE" && "$FORCE_UPDATE" -eq 0 ]]; then
  echo "chess.js v$CHESSJS_VER already at $CHESSJS_VENDOR_FILE"
else
  mkdir -vp "$CHESSJS_VENDOR_DIR"

  echo "Fetching chess.js v$CHESSJS_VER..."
  curl -fL --show-error --silent \
    "https://unpkg.com/chess.js@${CHESSJS_VER}/dist/esm/chess.js" \
    -o "$CHESSJS_VENDOR_FILE"

  # Make it WhiteNoise-proof: strip sourcemap reference if upstream includes it.
  sed -i.bak '/sourceMappingURL=.*\.map/d' "$CHESSJS_VENDOR_FILE"
  rm -f "$CHESSJS_VENDOR_FILE.bak"
fi

echo "Updating chess.js stable copy"
cp -f "$CHESSJS_VENDOR_FILE" "$CHESSJS_STABLE_FILE"

# ---- chessground ----
