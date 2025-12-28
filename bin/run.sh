#!/bin/bash

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

DEBUG=true

while getopts ":d" opt; do
  case $opt in
    d)
      DEBUG=false
      ;;
    \?)
      echo "Invalid option: -$OPTARG" >&2
      exit 1
      ;;
  esac
done

echo "👀 watchmedo auto-restart collectstatic runserver 🐍 (DEBUG=$DEBUG)"

watchmedo auto-restart \
  --directory=static --directory=templates --directory=chesser \
  --pattern="*.js;*.css;*.html;*.py" \
  --recursive \
  -- bash -c "export DEBUG=$DEBUG && python $REPO_ROOT/manage.py collectstatic --noinput && python $REPO_ROOT/manage.py runserver 0.0.0.0:8000"
