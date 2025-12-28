#!/bin/bash

# Safety first ➤ fail early and often
set -euo pipefail

DB_FILE="./data/chesser.sqlite3"

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
./manage.py flush --no-input

echo "✅ Database reset!"

# Look for the most recent backup
DB_BACKUP=$(ls -t ./temp/db_backup_*.json 2>/dev/null | head -n 1 || true)

if [ -z "$DB_BACKUP" ]; then
  echo "🟡 No db_backup_*.json file found in ./temp — skipping loaddata."
  exit 0
fi

echo "📦 Found latest backup: $DB_BACKUP ($(stat -c '%y' "$DB_BACKUP" | cut -d'.' -f1))"

read -p "🚀 Load it? (yes/no) " confirm
if [ "$confirm" != "yes" ]; then
  echo "👍️ Not loading from backup"
  exit 0
fi

./manage.py loaddata "$DB_BACKUP" --verbosity 3

echo "🦸‍♀️ Creating superuser..."
./manage.py createsuperuser
