# bin/

Utility scripts for development and maintenance.

These scripts are not part of the runtime application and are
intended for local use by the developer.

## Scripts

### run.sh

Convenience wrapper for running the local Django server with
the expected environment.

### js_tests.sh

Runs all JavaScript tests using Node's built-in test runner.
Test files live in `js_tests/`.

### all_tests.sh

Runs both JS and Python test suites in sequence.

### flush_dev_db.sh

Wipes and recreates the local development database.
**Destructive. Dev only.**

### quickprep.sh

Runs code formatting and linting (black, isort, flake8) across the repo.
Useful for cleaning up the working tree before committing; complements
the pre-commit hook, which enforces the same checks.

### get_noto_emoji.py

Fetches selected Noto Emoji SVG assets used by the UI. Relies on local
github checkout.

### update-vendor.sh

Updates vendored third-party frontend assets (e.g. Chessground).
May overwrite files under `static/`.
