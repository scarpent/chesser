#!/bin/bash

# Safety first ➤ fail early and often
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

DB_FILE="$REPO_ROOT/data/chesser.sqlite3"

if [ ! -f "$DB_FILE" ]; then
  echo "❌ Safety check failed: $DB_FILE not found."
  exit 1
fi
echo "✅ Safety check passed (found dev SQLite DB at $DB_FILE)"

read -p "⚠️  Flush your local dev DB? Are you sure? (yes/no) " confirm
if [ "$confirm" != "yes" ]; then
  echo "❌ Cancelled"
  exit 1
fi

echo "💥 Flushing dev database..."
"$REPO_ROOT/manage.py" flush --no-input

echo "✅ Database reset!"

# Look for the most recent backup
DB_BACKUP=$(ls -t $REPO_ROOT/temp/db_backup_*.json 2>/dev/null | head -n 1 || true)

if [ -z "$DB_BACKUP" ]; then
  echo "🟡 No db_backup_*.json file found in $REPO_ROOT/temp — skipping loaddata."
  exit 0
fi

echo "📦 Found latest backup: $DB_BACKUP ($(stat -c '%y' "$DB_BACKUP" | cut -d'.' -f1))"

read -p "🚀 Load it? (yes/no) " confirm
if [ "$confirm" != "yes" ]; then
  echo "👍️ Not loading from backup"
else
  "$REPO_ROOT/manage.py" loaddata "$DB_BACKUP" --verbosity 3
fi

echo "🦸‍♀️ Creating superuser..."
"$REPO_ROOT/manage.py" createsuperuser
