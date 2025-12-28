#!/bin/bash

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

black "$REPO_ROOT"
isort "$REPO_ROOT"
flake8 "$REPO_ROOT"
