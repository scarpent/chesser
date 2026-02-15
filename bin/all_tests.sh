#!/bin/bash

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

echo "=== JS tests ==="
node --test "$REPO_ROOT"/js_tests/test_*.js
js_status=$?

echo ""
echo "=== Python tests ==="
pytest "$REPO_ROOT"
py_status=$?

if [ $js_status -ne 0 ] || [ $py_status -ne 0 ]; then
    exit 1
fi
