#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

# Defaults
CHESSER_ENV="development"
DEBUG="true"
PORT="8000"

usage() {
  cat <<EOF
🧩 Chesser dev runner

Usage:
  $(basename "$0") [options]

Options:
  -d    🧪 Demo mode      (CHESSER_ENV=demo,        DEBUG=true)
  -p    🚀 Prod-like mode (CHESSER_ENV=development, DEBUG=false)
  -h    ❓ Show help

-p may be needed for proper refreshing on mobile

EOF
}

while getopts ":dph" opt; do
  case $opt in
    d)
      CHESSER_ENV="demo"
      DEBUG="true"
      ;;
    p)
      CHESSER_ENV="development"
      DEBUG="false"
      ;;
    h)
      usage
      exit 0
      ;;
    \?)
      echo "❌ Invalid option: -$OPTARG" >&2
      echo
      usage >&2
      exit 1
      ;;
  esac
done

MODE_EMOJI="🛠️"
if [ "$CHESSER_ENV" = "demo" ]; then
  MODE_EMOJI="🧪"
elif [ "$DEBUG" = "false" ]; then
  MODE_EMOJI="🚀"
fi

export DEBUG="$DEBUG"
export CHESSER_ENV="$CHESSER_ENV"

echo "$MODE_EMOJI Starting Chesser"
echo "  🌍 CHESSER_ENV=$CHESSER_ENV"
echo "  🪲 DEBUG=$DEBUG"
echo "  📁 REPO_ROOT=$REPO_ROOT"
echo "  🔌 http://0.0.0.0:$PORT"
echo "  👀 watchmedo: static/, templates/, chesser/"

if [[ "$CHESSER_ENV" == "demo" ]]; then
  python "$REPO_ROOT/manage.py" migrate --noinput
  # python "$REPO_ROOT/manage.py" seed_demo   # add later
fi

# Re-run collectstatic on every restart because we intentionally use
# production-style static handling (WhiteNoise + hashed manifest)
# instead of Django's default dev static serving.

watchmedo auto-restart \
  --directory=static \
  --directory=templates \
  --directory=chesser \
  --pattern="*.js;*.css;*.html;*.py" \
  --recursive \
  -- bash -c "
    export DEBUG=$DEBUG
    export CHESSER_ENV=$CHESSER_ENV
    python \"$REPO_ROOT/manage.py\" collectstatic --noinput &&
    python \"$REPO_ROOT/manage.py\" runserver 0.0.0.0:$PORT
  "
