#!/usr/bin/env bash

# Update hosted frontend dependencies for Chesser.
#
# This script fetches specific pinned versions of third-party JS libraries
# (currently Alpine.js, chess.js, chessground), stores them under versioned
# paths in vendorfiles/, and then copies a stable reference into static/ for
# use by Django templates. The goal is reproducibility, auditability, and
# minimal frontend tooling — no npm, no bundler, no build step.
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
CHESSGROUND_VER="9.9.0"

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
#
# chessground is a core UI dependency, but the npm package is deprecated and can
# lag behind GitHub tags. To keep upgrades reproducible without committing a full
# git checkout, we build the standalone bundle from a GitHub source tarball.
#
# This DOES introduce a manual build tool dependency:
# - Node.js
# - pnpm (recommended: `brew install pnpm`)
#
# This is not part of Chesser's runtime or deployment cycle. It's only needed
# when you choose to upgrade chessground and re-vendor the built artifacts.
#
# Vendor copies are kept versioned under vendorfiles/; stable copies under
# static/ are what Django templates actually load.
#
# IMPORTANT: keep any local CSS customizations in a separate file such as:
#   static/chessground/chessground.overrides.css
# loaded AFTER the upstream chessground CSS, so upgrades are simple replaces.

CHESSGROUND_VENDOR_DIR="$VENDOR_DIR/chessground/$CHESSGROUND_VER"
CHESSGROUND_TARBALL="$CHESSGROUND_VENDOR_DIR/chessground-v${CHESSGROUND_VER}.tar.gz"
CHESSGROUND_TMP_DIR="$CHESSGROUND_VENDOR_DIR/_tmp"
CHESSGROUND_STABLE_DIR="$STATIC_DIR/chessground"

if [[ -f "$CHESSGROUND_VENDOR_DIR/chessground.min.js" && "$FORCE_UPDATE" -eq 0 ]]; then
  echo "chessground v$CHESSGROUND_VER already at $CHESSGROUND_VENDOR_DIR"
else
  mkdir -vp "$CHESSGROUND_VENDOR_DIR"

  # Fail early with a helpful message if build tooling isn't installed.
  if ! command -v pnpm >/dev/null 2>&1; then
    echo "ERROR: pnpm is required to build chessground from source." >&2
    echo "Install with: brew install pnpm" >&2
    echo "Then re-run this script (optionally with -f)." >&2
    exit 1
  fi

  if ! command -v node >/dev/null 2>&1; then
    echo "ERROR: node is required to build chessground from source." >&2
    echo "Install with: brew install node" >&2
    exit 1
  fi

  # Download source tarball (cached in vendorfiles/) and build dist output.
  if [[ -f "$CHESSGROUND_TARBALL" && "$FORCE_UPDATE" -eq 0 ]]; then
    echo "Chessground v$CHESSGROUND_VER tarball already at $CHESSGROUND_TARBALL"
  else
    echo "Fetching chessground v$CHESSGROUND_VER (github source tarball)"
    curl -fL --show-error --silent \
      "https://github.com/lichess-org/chessground/archive/refs/tags/v${CHESSGROUND_VER}.tar.gz" \
      -o "$CHESSGROUND_TARBALL"
  fi

  rm -rf "$CHESSGROUND_TMP_DIR"
  mkdir -vp "$CHESSGROUND_TMP_DIR"

  tar -xzf "$CHESSGROUND_TARBALL" -C "$CHESSGROUND_TMP_DIR"

  CHESSGROUND_EXTRACTED_DIR="$(find "$CHESSGROUND_TMP_DIR" -maxdepth 1 -type d -name "chessground-*" | head -n 1)"
  if [[ -z "$CHESSGROUND_EXTRACTED_DIR" ]]; then
    echo "ERROR: Could not locate extracted chessground directory" >&2
    exit 1
  fi

  echo "Building chessground v$CHESSGROUND_VER (pnpm install + pnpm run dist)"
  (
    cd "$CHESSGROUND_EXTRACTED_DIR"
    pnpm install --frozen-lockfile
    pnpm run dist
  )

  # Copy the built standalone bundle + CSS assets into our flat vendor dir.
  if [[ ! -f "$CHESSGROUND_EXTRACTED_DIR/dist/chessground.min.js" ]]; then
    echo "ERROR: Expected dist/chessground.min.js not found after build." >&2
    exit 1
  fi

  cp -f "$CHESSGROUND_EXTRACTED_DIR/dist/chessground.min.js" "$CHESSGROUND_VENDOR_DIR/chessground.min.js"
  cp -f "$CHESSGROUND_EXTRACTED_DIR/assets/chessground.base.css"     "$CHESSGROUND_VENDOR_DIR/chessground.base.css"
  cp -f "$CHESSGROUND_EXTRACTED_DIR/assets/chessground.brown.css"    "$CHESSGROUND_VENDOR_DIR/chessground.brown.css"
  cp -f "$CHESSGROUND_EXTRACTED_DIR/assets/chessground.cburnett.css" "$CHESSGROUND_VENDOR_DIR/chessground.cburnett.css"

  SOURCE_FILE="$CHESSGROUND_VENDOR_DIR/SOURCE.txt"

  echo "Writing $SOURCE_FILE"
  {
    echo "project: chessground"
    echo "version: v$CHESSGROUND_VER"
    echo "source: https://github.com/lichess-org/chessground"
    echo "tarball: https://github.com/lichess-org/chessground/archive/refs/tags/v${CHESSGROUND_VER}.tar.gz"
    echo "built_at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo
    echo "build_environment:"
    echo "  node: $(node --version)"
    echo "  pnpm: $(pnpm --version)"
    echo
    echo "artifacts:"
    echo "  chessground.min.js:"
    shasum -a 256 "$CHESSGROUND_VENDOR_DIR/chessground.min.js" | sed 's/^/    /'
  } >"$SOURCE_FILE"


  # Cleanup extracted source tree and tarball
  rm -rf "$CHESSGROUND_TMP_DIR" "$CHESSGROUND_TARBALL"
fi

echo "Updating chessground stable copies"
mkdir -vp "$CHESSGROUND_STABLE_DIR"
cp -f "$CHESSGROUND_VENDOR_DIR/chessground.min.js" "$CHESSGROUND_STABLE_DIR/chessground.min.js"
cp -f "$CHESSGROUND_VENDOR_DIR/chessground.base.css" "$CHESSGROUND_STABLE_DIR/chessground.base.css"
cp -f "$CHESSGROUND_VENDOR_DIR/chessground.brown.css" "$CHESSGROUND_STABLE_DIR/chessground.brown.css"
cp -f "$CHESSGROUND_VENDOR_DIR/chessground.cburnett.css" "$CHESSGROUND_STABLE_DIR/chessground.cburnett.css"
