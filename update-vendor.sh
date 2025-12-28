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
CHECK_NEWER=0

while getopts ":fn" opt; do
  case "$opt" in
    f)
      FORCE_UPDATE=1
      ;;
    n)
      CHECK_NEWER=1
      ;;
    *)
      echo -e "Usage: $(basename "$0") [-f] [-n]\n-f: force update\n-n: check for newer versions" >&2
      exit 2
      ;;
  esac
done

npm_latest() {
  # Prints dist-tags.latest for an npm package, or empty on failure.
  # Uses Python for URL encoding + JSON parsing to avoid jq dependency.
  local pkg="$1"

  python3 - "$pkg" <<'PY'
import json
import sys
import urllib.parse
import urllib.request

pkg = sys.argv[1]
url = "https://registry.npmjs.org/" + urllib.parse.quote(pkg, safe="")
try:
    with urllib.request.urlopen(url, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    print(data.get("dist-tags", {}).get("latest", ""))
except Exception:
    # Silence errors; caller prints WARN.
    print("")
PY
}


check_newer() {
  local pkg="$1"
  local pinned="$2"
  local latest

  latest="$(npm_latest "$pkg")"
  if [[ -z "$latest" ]]; then
   echo "WARN: could not determine latest for $pkg (npm registry lookup failed)"
   return 0
  fi

  if [[ "$latest" != "$pinned" ]]; then
    echo "UPDATE: $pkg pinned=$pinned latest=$latest"
    return 1
  fi

  echo "OK: $pkg pinned=$pinned"
  return 0
}

if [[ "$CHECK_NEWER" -eq 1 ]]; then
  outdated=0

  check_newer "alpinejs" "$ALPINE_VER" || outdated=1
  check_newer "chess.js" "$CHESSJS_VER" || outdated=1
  check_newer "@lichess-org/chessground" "$CHESSGROUND_VER" || outdated=1

  exit "$outdated"
fi

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

# chessground is a core UI dependency. The old unscoped npm package "chessground"
# is deprecated; we instead fetch from the current scoped package
# "@lichess-org/chessground" via jsDelivr.
#
# IMPORTANT: keep any local CSS customizations in a separate file such as:
#   static/chessground/chessground.overrides.css
# loaded AFTER the upstream chessground CSS, so upgrades are simple replaces.

CHESSGROUND_VENDOR_DIR="$VENDOR_DIR/chessground/$CHESSGROUND_VER"
CHESSGROUND_STABLE_DIR="$STATIC_DIR/chessground"
CHESSGROUND_CDN_BASE="https://cdn.jsdelivr.net/npm/@lichess-org/chessground@${CHESSGROUND_VER}"

if [[ -f "$CHESSGROUND_VENDOR_DIR/chessground.min.js" && "$FORCE_UPDATE" -eq 0 ]]; then
  echo "chessground v$CHESSGROUND_VER already at $CHESSGROUND_VENDOR_DIR"
else
  mkdir -vp "$CHESSGROUND_VENDOR_DIR"

  echo "Fetching chessground v$CHESSGROUND_VER"

  curl -fL --show-error --silent \
    "${CHESSGROUND_CDN_BASE}/dist/chessground.min.js" \
    -o "$CHESSGROUND_VENDOR_DIR/chessground.min.js"

  curl -fL --show-error --silent \
    "${CHESSGROUND_CDN_BASE}/assets/chessground.base.css" \
    -o "$CHESSGROUND_VENDOR_DIR/chessground.base.css"

  curl -fL --show-error --silent \
    "${CHESSGROUND_CDN_BASE}/assets/chessground.brown.css" \
    -o "$CHESSGROUND_VENDOR_DIR/chessground.brown.css"

  curl -fL --show-error --silent \
    "${CHESSGROUND_CDN_BASE}/assets/chessground.cburnett.css" \
    -o "$CHESSGROUND_VENDOR_DIR/chessground.cburnett.css"
fi

echo "Updating chessground stable copies"
mkdir -vp "$CHESSGROUND_STABLE_DIR"
cp -f "$CHESSGROUND_VENDOR_DIR/chessground.min.js" "$CHESSGROUND_STABLE_DIR/chessground.min.js"
cp -f "$CHESSGROUND_VENDOR_DIR/chessground.base.css" "$CHESSGROUND_STABLE_DIR/chessground.base.css"
cp -f "$CHESSGROUND_VENDOR_DIR/chessground.brown.css" "$CHESSGROUND_STABLE_DIR/chessground.brown.css"
cp -f "$CHESSGROUND_VENDOR_DIR/chessground.cburnett.css" "$CHESSGROUND_STABLE_DIR/chessground.cburnett.css"
