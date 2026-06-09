#!/usr/bin/env bash
set -euo pipefail
DB_DIR="/app/data/db"
DB_FILE="${DB_DIR}/database.db"
mkdir -p "${DB_DIR}"

table_exists() {
  python - <<'PY'
import sqlite3, sys
con = sqlite3.connect("/app/data/db/database.db")
sys.exit(0 if con.execute(
  "SELECT 1 FROM sqlite_master WHERE type='table' AND name='alembic_version'"
).fetchone() else 1)
PY
}

if [ ! -f "${DB_FILE}" ]; then
  echo "[entrypoint] No DB — fresh migrations."
  alembic upgrade head
elif table_exists; then
  echo "[entrypoint] Managed DB — applying pending."
  alembic upgrade head
else
  echo "[entrypoint] Unmanaged DB — stamping then migrating."
  alembic stamp head
  alembic upgrade head
fi

echo "[entrypoint] Launching: $*"
exec "$@"
