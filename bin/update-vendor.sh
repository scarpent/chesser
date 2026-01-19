#!/usr/bin/env bash

# Update vendored frontend dependencies for Chesser.
#
# This script fetches pinned versions of third-party frontend libraries
# (currently Alpine.js, chess.js, and chessground), stores versioned copies
# under vendorfiles/, and updates the corresponding stable files in static/
# that are served by Django templates.
#
# Usage:
#   bin/update-vendor.sh        # update missing dependencies
#   bin/update-vendor.sh -f     # force re-fetch even if files already exist
#   bin/update-vendor.sh -n     # check if newer upstream versions are available
#
# This script is intended to be run manually when upgrading dependencies.
# It is not part of the normal development or deployment workflow.
#
# For background on the vendorfiles/ layout and philosophy, see:
#   vendorfiles/README.md
#
# Notes:
# - Downloads use curl in fail-fast mode to avoid partial or silent failures.
# - Static file caching is handled by Django/WhiteNoise and template-level
#   cache busting where needed.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

STATIC_DIR="$REPO_ROOT/static"
VENDOR_DIR="$REPO_ROOT/vendorfiles"

ALPINE_VER="3.15.4"
CHESSJS_VER="1.4.0"
CHESSGROUND_VER="9.10.3"

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
    echo "📌 $pkg pinned=$pinned latest=$latest"
    return 1
  fi

  echo "✅ $pkg pinned=$pinned"
  return 0
}

if [[ "$CHECK_NEWER" -eq 1 ]]; then
  outdated=0

  check_newer "alpinejs" "$ALPINE_VER" || outdated=1
  check_newer "chess.js" "$CHESSJS_VER" || outdated=1
  check_newer "@lichess-org/chessground" "$CHESSGROUND_VER" || outdated=1

  if [[ "$outdated" -eq 1 ]]; then
    cat <<'EOF'

⬆️  Updates available.
To upgrade Chesser's vendored frontend deps:
  1) Edit the pinned version constants near the top of this script:
       ALPINE_VER / CHESSJS_VER / CHESSGROUND_VER
  2) Re-run:
       bin/update-vendor.sh -f

EOF
  fi

  exit "$outdated"
fi
fi

# ---- Alpine.js ----

ALPINE_VENDOR_DIR="$VENDOR_DIR/alpine/$ALPINE_VER"
ALPINE_VENDOR_FILE="$ALPINE_VENDOR_DIR/cdn.min.js"
ALPINE_STABLE_FILE="$STATIC_DIR/alpine/cdn.min.js"

if [[ -f "$ALPINE_VENDOR_FILE" && "$FORCE_UPDATE" -eq 0 ]]; then
  echo "✅ Alpine.js v$ALPINE_VER already in vendorfiles"
else
  mkdir -vp "$ALPINE_VENDOR_DIR"

  echo "🦴 Fetching Alpine.js v$ALPINE_VER"
  # -f: fail on HTTP errors
  # -L: follow redirects (unpkg/jsdelivr)
  # --show-error: print errors even with --silent
  # --silent: no progress bar
  curl -fL --show-error --silent \
    "https://cdn.jsdelivr.net/npm/alpinejs@${ALPINE_VER}/dist/cdn.min.js" \
    -o "$ALPINE_VENDOR_FILE"
fi

echo "💾 Updating Alpine.js stable copy"
cp -f "$ALPINE_VENDOR_FILE" "$ALPINE_STABLE_FILE"

# ---- chess.js ----

CHESSJS_VENDOR_DIR="$VENDOR_DIR/chessjs/$CHESSJS_VER/dist/esm"
CHESSJS_VENDOR_FILE="$CHESSJS_VENDOR_DIR/chess.js"
CHESSJS_VENDOR_MAP_FILE="$CHESSJS_VENDOR_DIR/chess.js.map"

CHESSJS_STABLE_FILE="$STATIC_DIR/chessjs/chess.js"
CHESSJS_STABLE_MAP_FILE="$STATIC_DIR/chessjs/chess.js.map"

if [[ -f "$CHESSJS_VENDOR_FILE" && "$FORCE_UPDATE" -eq 0 ]]; then
  echo "✅ chess.js v$CHESSJS_VER already in vendorfiles"
else
  mkdir -vp "$CHESSJS_VENDOR_DIR"

  echo "🦴 Fetching chess.js v$CHESSJS_VER"
  curl -fL --show-error --silent \
    "https://unpkg.com/chess.js@${CHESSJS_VER}/dist/esm/chess.js" \
    -o "$CHESSJS_VENDOR_FILE"

  # Sourcemap (optional but nice for debugging).
  # If upstream stops shipping it, this should not fail the script.
  curl -fL --show-error --silent \
    "https://unpkg.com/chess.js@${CHESSJS_VER}/dist/esm/chess.js.map" \
    -o "$CHESSJS_VENDOR_MAP_FILE" \
    || true
fi

echo "💾 Updating chess.js stable copy"
cp -f "$CHESSJS_VENDOR_FILE" "$CHESSJS_STABLE_FILE"

if [[ -f "$CHESSJS_VENDOR_MAP_FILE" ]]; then
  cp -f "$CHESSJS_VENDOR_MAP_FILE" "$CHESSJS_STABLE_MAP_FILE"
fi

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
  echo "✅ chessground v$CHESSGROUND_VER already in vendorfiles"
else
  mkdir -vp "$CHESSGROUND_VENDOR_DIR"

  echo "🦴 Fetching chessground v$CHESSGROUND_VER"
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

echo "💾 Updating chessground stable copies"
mkdir -vp "$CHESSGROUND_STABLE_DIR"
cp -f "$CHESSGROUND_VENDOR_DIR/chessground.min.js" "$CHESSGROUND_STABLE_DIR/chessground.min.js"
cp -f "$CHESSGROUND_VENDOR_DIR/chessground.base.css" "$CHESSGROUND_STABLE_DIR/chessground.base.css"
cp -f "$CHESSGROUND_VENDOR_DIR/chessground.brown.css" "$CHESSGROUND_STABLE_DIR/chessground.brown.css"
cp -f "$CHESSGROUND_VENDOR_DIR/chessground.cburnett.css" "$CHESSGROUND_STABLE_DIR/chessground.cburnett.css"
