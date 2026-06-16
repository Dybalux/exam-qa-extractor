#!/usr/bin/env bash
set -euo pipefail
DB_DIR="/app/data/db"
DB_FILE="${DB_DIR}/database.db"
mkdir -p "${DB_DIR}"

# alembic.ini now lives inside app/ (moved by refactor/move-alembic-into-app).
# Run all alembic commands from /app so the `prepend_sys_path = ..` in
# app/alembic.ini resolves to /app (the repo root inside the container).
ALEMBIC="alembic -c /app/app/alembic.ini"

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
  ${ALEMBIC} upgrade head
elif table_exists; then
  echo "[entrypoint] Managed DB — applying pending."
  ${ALEMBIC} upgrade head
else
  echo "[entrypoint] Unmanaged DB — stamping then migrating."
  ${ALEMBIC} stamp head
  ${ALEMBIC} upgrade head
fi

echo "[entrypoint] Launching: $*"
exec "$@"
